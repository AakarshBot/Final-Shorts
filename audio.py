"""Function 03: speech audio and word-level timings."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import edge_tts

CACHE_DIR = Path(__file__).resolve().with_name(".audio_cache")
MAX_CONCURRENCY = 2
MAX_ATTEMPTS = 2
MAX_DURATION_SECONDS = 30.0
CORRECTION_TARGET_SECONDS = 29.6

VOICES = {
    "english": "en-IN-NeerjaNeural",
    "hindi": "hi-IN-SwaraNeural",
    "telugu": "te-IN-ShrutiNeural",
}

BASE_RATE_PERCENT = 8.0
PITCH = "+4Hz"
_MARKUP_RE = re.compile(r"[*_#\[\]()~^\"“”‘’]")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _MARKUP_RE.sub("", str(value or ""))).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _cache_key(text: str, language: str, rate_percent: float) -> str:
    payload = json.dumps(
        {
            "text": text,
            "language": language,
            "voice": VOICES[language],
            "rate_percent": round(rate_percent, 2),
            "pitch": PITCH,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _probe_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        value = float((result.stdout or "").strip())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RuntimeError("ffprobe could not determine audio duration.") from exc
    if value <= 0:
        raise RuntimeError("Encoded audio duration is not positive.")
    return value


def _normalise_timings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    previous_start = -1.0
    for item in items or []:
        try:
            word = str(item.get("word", "")).strip()
            start = max(0.0, float(item.get("start", 0.0)))
            end = max(start, float(item.get("end", start)))
        except (AttributeError, TypeError, ValueError):
            continue
        if not word or start < previous_start:
            continue
        result.append({"word": word, "start": start, "end": end})
        previous_start = start
    return result


def _validate_timings(text: str, timings: list[dict[str, Any]], duration: float) -> None:
    if not timings:
        raise RuntimeError("Edge-TTS returned no word-boundary timings.")
    expected = _word_count(text)
    if len(timings) < max(1, int(expected * 0.55)):
        raise RuntimeError(
            f"Word-boundary timing coverage is too low ({len(timings)}/{expected})."
        )
    previous_end = -0.05
    for item in timings:
        if item["start"] < previous_end:
            raise RuntimeError("Word timings are not monotonic.")
        if item["end"] < item["start"]:
            raise RuntimeError("Word timing contains a negative duration.")
        previous_end = item["end"]
    if timings[-1]["end"] > duration + 0.10:
        raise RuntimeError("Word timing extends beyond encoded audio duration.")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError)):
        return True
    message = str(exc or "").casefold()
    return any(
        marker in message
        for marker in (
            "429",
            "rate limit",
            "503",
            "service unavailable",
            "temporarily unavailable",
            "connection reset",
            "timed out",
            "timeout",
        )
    )


async def _synthesise_once(
    text: str,
    language: str,
    rate_percent: float,
    path: Path,
) -> list[dict[str, Any]]:
    timings: list[dict[str, Any]] = []
    communicate = edge_tts.Communicate(
        text,
        VOICES[language],
        rate=f"{rate_percent:+.0f}%",
        pitch=PITCH,
        boundary="WordBoundary",
    )
    with open(path, "wb") as handle:
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                handle.write(chunk["data"])
            elif chunk.get("type") == "WordBoundary":
                offset = max(0.0, float(chunk.get("offset", 0)) / 10_000_000.0)
                length = max(0.0, float(chunk.get("duration", 0)) / 10_000_000.0)
                word = str(chunk.get("text", "")).strip()
                if word:
                    timings.append(
                        {"word": word, "start": offset, "end": offset + length}
                    )
    if path.stat().st_size <= 500:
        raise RuntimeError("Edge-TTS returned an empty or invalid audio file.")
    timings = _normalise_timings(timings)
    duration = _probe_duration(path)
    _validate_timings(text, timings, duration)
    return timings


async def _scene(
    scene_number: int,
    text: str,
    language: str,
    rate_percent: float,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    key = _cache_key(text, language, rate_percent)
    cache_audio = CACHE_DIR / f"{key}.mp3"
    cache_meta = CACHE_DIR / f"{key}.json"
    output_path = output_dir / f"voiceover_{scene_number}.mp3"

    if cache_audio.exists() and cache_meta.exists():
        try:
            metadata = json.loads(cache_meta.read_text(encoding="utf-8"))
            timings = _normalise_timings(metadata.get("timings") or [])
            duration = float(metadata["duration"])
            _validate_timings(text, timings, duration)
            shutil.copy2(cache_audio, output_path)
            return {
                "scene": scene_number,
                "path": str(output_path),
                "duration": duration,
                "timings": timings,
                "from_cache": True,
            }
        except (OSError, KeyError, TypeError, ValueError, RuntimeError, json.JSONDecodeError):
            try:
                cache_audio.unlink(missing_ok=True)
                cache_meta.unlink(missing_ok=True)
            except OSError:
                pass

    async with semaphore:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            temp_path: Path | None = None
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                output_dir.mkdir(parents=True, exist_ok=True)
                fd, raw_path = tempfile.mkstemp(
                    prefix=f"voiceover_{scene_number}_",
                    suffix=".mp3",
                    dir=output_dir,
                )
                Path(raw_path).unlink(missing_ok=True)
                temp_path = Path(raw_path)
                await asyncio.wait_for(
                    _synthesise_once(text, language, rate_percent, temp_path),
                    timeout=45,
                )
                duration = _probe_duration(temp_path)

                cache_temp = CACHE_DIR / f".{key}.mp3.tmp"
                meta_temp = CACHE_DIR / f".{key}.json.tmp"
                shutil.copy2(temp_path, cache_temp)
                meta_temp.write_text(
                    json.dumps(
                        {"duration": duration, "timings": _normalise_timings(
                            json.loads(json.dumps([]))
                        )},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                timings = _normalise_timings(
                    json.loads(meta_temp.read_text(encoding="utf-8")).get("timings") or []
                )
                cache_temp.replace(cache_audio)
                meta_temp.unlink(missing_ok=True)
                temp_path.replace(output_path)

                return {
                    "scene": scene_number,
                    "path": str(output_path),
                    "duration": duration,
                    "timings": timings,
                    "from_cache": False,
                }
            except Exception as exc:
                if temp_path:
                    temp_path.unlink(missing_ok=True)
                if attempt >= MAX_ATTEMPTS or not _retryable(exc):
                    raise RuntimeError(f"Scene {scene_number} audio failed: {exc}") from exc
                await asyncio.sleep(1.0 * attempt)

    raise RuntimeError(f"Scene {scene_number} audio failed.")


async def _generate_at_rate(
    script: dict,
    language: str,
    rate_percent: float,
    output_dir: Path,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = [
        asyncio.create_task(
            _scene(
                number,
                _clean_text(scene.get("voiceover")),
                language,
                rate_percent,
                output_dir,
                semaphore,
            )
        )
        for number, scene in enumerate(script["script"], 1)
    ]
    try:
        results = await asyncio.gather(*tasks)
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return sorted(results, key=lambda item: item["scene"])


def generate_audio(
    approved_script: dict,
    output_dir: str | Path = "output/audio_test",
) -> dict[str, Any]:
    """Generate approved narration audio with native Edge-TTS word timings."""
    if (
        not isinstance(approved_script, dict)
        or approved_script.get("approved_for_audio") is not True
    ):
        raise ValueError("Audio requires the approved Scriptwriter handoff.")

    scenes = approved_script.get("script")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Approved script contains no scenes.")

    language = str(
        approved_script.get("language_used") or "english"
    ).strip().casefold()
    if language not in VOICES:
        raise ValueError(f"Unsupported audio language: {language}")

    for index, scene in enumerate(scenes, 1):
        if not _clean_text(scene.get("voiceover")):
            raise ValueError(f"Scene {index} has no narration text.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rate_percent = BASE_RATE_PERCENT
    results = asyncio.run(
        _generate_at_rate(approved_script, language, rate_percent, output_path)
    )
    total = round(sum(float(item["duration"]) for item in results), 3)
    corrected = False

    if total > MAX_DURATION_SECONDS:
        multiplier = total / CORRECTION_TARGET_SECONDS
        adjusted = (
            (1.0 + rate_percent / 100.0) * multiplier - 1.0
        ) * 100.0
        adjusted = min(100.0, max(rate_percent + 1.0, adjusted))
        results = asyncio.run(
            _generate_at_rate(approved_script, language, adjusted, output_path)
        )
        total = round(sum(float(item["duration"]) for item in results), 3)
        rate_percent = round(adjusted, 2)
        corrected = True
        if total > MAX_DURATION_SECONDS:
            raise RuntimeError(
                "Audio remains over 30 seconds after one measured speed correction "
                f"({total:.2f}s)."
            )

    return {
        "language": language,
        "voice": VOICES[language],
        "rate_percent": rate_percent,
        "pitch": PITCH,
        "scenes": results,
        "total_duration": total,
        "duration_corrected": corrected,
    }


def approve_audio(audio: dict[str, Any]) -> dict[str, Any]:
    """Mark verified generated audio as the handoff for Visuals."""
    if not isinstance(audio, dict) or not audio.get("scenes"):
        raise ValueError("No generated audio is available for approval.")
    total = float(audio.get("total_duration") or 0)
    if total <= 0 or total > MAX_DURATION_SECONDS:
        raise ValueError("Audio duration is outside the factory limit.")
    for scene in audio["scenes"]:
        path = Path(scene.get("path", ""))
        if not path.exists() or path.stat().st_size <= 500:
            raise ValueError(
                f"Audio file for scene {scene.get('scene')} is missing or invalid."
            )
    result = json.loads(json.dumps(audio, ensure_ascii=False))
    result["approved_for_visuals"] = True
    return result
