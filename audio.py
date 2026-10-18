"""Function 03: speech audio and word-level timings."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import edge_tts

CACHE_DIR = Path(__file__).resolve().with_name(".audio_cache")
ROOT_DIR = Path(__file__).resolve().parent
AUDIO_REFERENCE = Path(os.getenv("AUDIO_REFERENCE", ROOT_DIR / "audio_reference.wav"))
CHATTERBOX_VOICE_REFERENCES = {
    "Voice 1 · Original": AUDIO_REFERENCE,
    "Voice 2": ROOT_DIR / "audio_reference_2.wav",
    "Voice 3": ROOT_DIR / "audio_reference_3.wav",
}
CHATTERBOX_OUTPUT_ROOT = ROOT_DIR / "output" / "generated_audio"
_CHATTERBOX_MODEL = None
_CHATTERBOX_CONDITIONALS_MODEL_ID: int | None = None
_CHATTERBOX_DEFAULT_CONDITIONALS = None
_CHATTERBOX_CONDITIONALS_CACHE: dict[str, Any] = {}
MAX_CONCURRENCY = 2
MAX_ATTEMPTS = 2
MAX_DURATION_SECONDS = 30.0
CORRECTION_TARGET_SECONDS = 29.6
TOP5_SCENE_COUNT = 6
TOP5_MAX_TOTAL_DURATION_SECONDS = 30.0
TOP5_TOTAL_CORRECTION_TARGET_SECONDS = 29.6

VOICE_ROSTER = {
    "english": {
        "female": "en-IN-NeerjaNeural",
        "male": "en-IN-PrabhatNeural",
    },
    "hindi": {
        "female": "hi-IN-SwaraNeural",
        "male": "hi-IN-MadhurNeural",
    },
    "telugu": {
        "female": "te-IN-ShrutiNeural",
        "male": "te-IN-MohanNeural",
    },
}

VOICES = {
    "english": "en-IN-NeerjaNeural",
    "hindi": "hi-IN-SwaraNeural",
    "telugu": "te-IN-ShrutiNeural",
}


def resolve_voice(language: str, gender: str | None = None, voice: str | None = None) -> str:
    if voice:
        return voice
    lang_key = str(language or "english").strip().casefold()
    if gender and lang_key in VOICE_ROSTER:
        gender_key = str(gender).strip().casefold()
        if gender_key in VOICE_ROSTER[lang_key]:
            return VOICE_ROSTER[lang_key][gender_key]
    return VOICES.get(lang_key, VOICES["english"])

BASE_RATE_PERCENT = 8.0
PITCH = "+4Hz"
_MARKUP_RE = re.compile(r"[*_#\[\]()~^\"“”‘’]")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _MARKUP_RE.sub("", str(value or ""))).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _cache_key(text: str, language: str, rate_percent: float, voice: str | None = None) -> str:
    selected_voice = voice or VOICES[language]
    payload = json.dumps(
        {
            "text": text,
            "language": language,
            "voice": selected_voice,
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


def _validate_timings(
    text: str,
    timings: list[dict[str, Any]],
    duration: float,
) -> None:
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
    voice: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    timings: list[dict[str, Any]] = []
    selected_voice = voice or VOICES.get(language, VOICES["english"])
    communicate = edge_tts.Communicate(
        text,
        selected_voice,
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
    return timings, duration


async def _scene(
    scene_number: int,
    text: str,
    language: str,
    rate_percent: float,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
    voice: str | None = None,
) -> dict[str, Any]:
    key = _cache_key(text, language, rate_percent, voice=voice)
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
            temp_audio: Path | None = None
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                output_dir.mkdir(parents=True, exist_ok=True)

                fd, raw_path = tempfile.mkstemp(
                    prefix=f"voiceover_{scene_number}_",
                    suffix=".mp3",
                    dir=output_dir,
                )
                os.close(fd)
                temp_audio = Path(raw_path)

                timings, duration = await asyncio.wait_for(
                    _synthesise_once(
                        text,
                        language,
                        rate_percent,
                        temp_audio,
                        voice=voice,
                    ),
                    timeout=45,
                )

                cache_fd, cache_raw = tempfile.mkstemp(
                    prefix=f".{key}_",
                    suffix=".mp3.tmp",
                    dir=CACHE_DIR,
                )
                os.close(cache_fd)
                meta_fd, meta_raw = tempfile.mkstemp(
                    prefix=f".{key}_",
                    suffix=".json.tmp",
                    dir=CACHE_DIR,
                )
                os.close(meta_fd)

                cache_temp = Path(cache_raw)
                meta_temp = Path(meta_raw)
                shutil.copy2(temp_audio, cache_temp)
                meta_temp.write_text(
                    json.dumps(
                        {"duration": duration, "timings": timings},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                cache_temp.replace(cache_audio)
                meta_temp.replace(cache_meta)
                temp_audio.replace(output_path)

                return {
                    "scene": scene_number,
                    "path": str(output_path),
                    "duration": duration,
                    "timings": timings,
                    "from_cache": False,
                }
            except Exception as exc:
                if temp_audio:
                    temp_audio.unlink(missing_ok=True)
                if attempt >= MAX_ATTEMPTS or not _retryable(exc):
                    raise RuntimeError(
                        f"Scene {scene_number} audio failed: {exc}"
                    ) from exc
                await asyncio.sleep(1.0 * attempt)

    raise RuntimeError(f"Scene {scene_number} audio failed.")


async def _generate_at_rate(
    scenes: list[dict[str, Any]],
    language: str,
    rate_percent: float,
    output_dir: Path,
    voice: str | None = None,
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
                voice=voice,
            )
        )
        for number, scene in enumerate(scenes, 1)
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


def synthesize_linear_timings(text: str, duration: float) -> list[dict[str, Any]]:
    """Synthesize uniform word timestamps across duration for human-recorded voiceovers."""
    words = _clean_text(text).split()
    if not words or duration <= 0:
        return []
    slot = duration / len(words)
    return [
        {"word": w, "start": round(i * slot, 3), "end": round((i + 1) * slot, 3)}
        for i, w in enumerate(words)
    ]


def package_human_audio(
    scene_number: int,
    audio_path: str | Path,
    narration_text: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Package an uploaded or mic-recorded human audio file into an audio scene."""
    src = Path(audio_path)
    if not src.exists() or src.stat().st_size <= 500:
        raise ValueError("Invalid human audio file.")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"voiceover_{scene_number}.mp3"
    shutil.copy2(src, target)
    duration = _probe_duration(target)
    timings = synthesize_linear_timings(narration_text, duration)
    return {
        "scene": scene_number,
        "path": str(target),
        "duration": duration,
        "timings": timings,
    }


def get_chatterbox_model():
    """Lazily loads and reuses Chatterbox Turbo for the lifetime of the Python process."""
    global _CHATTERBOX_MODEL
    if _CHATTERBOX_MODEL is None:
        try:
            import torch
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _CHATTERBOX_MODEL = ChatterboxTurboTTS.from_pretrained(device=device)
        except Exception as exc:
            raise RuntimeError(f"Chatterbox Audio could not be loaded: {exc}") from exc
    return _CHATTERBOX_MODEL


def resolve_chatterbox_reference(selection: str | Path | None = None) -> Path | None:
    """Resolve a local voice choice; an omitted choice may use Chatterbox's built-in voice."""
    if selection is None:
        return AUDIO_REFERENCE if AUDIO_REFERENCE.is_file() else None
    if isinstance(selection, str) and selection in CHATTERBOX_VOICE_REFERENCES:
        path = CHATTERBOX_VOICE_REFERENCES[selection]
        if not path.is_file():
            raise FileNotFoundError(
                f"{selection} needs the local reference file '{path.name}' in the factory root."
            )
        return path
    path = Path(selection)
    if not path.is_file():
        raise FileNotFoundError(f"Chatterbox reference file is missing: {path}")
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_chatterbox_reference(
    model: Any,
    reference: Path | None,
    reference_fingerprint: dict[str, str] | None = None,
) -> None:
    """Keep the built-in conditionals and cache each local reference for reuse."""
    global _CHATTERBOX_CONDITIONALS_MODEL_ID, _CHATTERBOX_DEFAULT_CONDITIONALS
    global _CHATTERBOX_CONDITIONALS_CACHE

    model_id = id(model)
    if _CHATTERBOX_CONDITIONALS_MODEL_ID != model_id:
        _CHATTERBOX_CONDITIONALS_MODEL_ID = model_id
        _CHATTERBOX_DEFAULT_CONDITIONALS = getattr(model, "conds", None)
        _CHATTERBOX_CONDITIONALS_CACHE = {}

    if reference is None:
        model.conds = _CHATTERBOX_DEFAULT_CONDITIONALS
        return

    fingerprint = reference_fingerprint or {
        "path": str(reference.resolve()),
        "sha256": _file_sha256(reference),
    }
    key = f'{fingerprint["path"]}:{fingerprint["sha256"]}'
    if key in _CHATTERBOX_CONDITIONALS_CACHE:
        model.conds = _CHATTERBOX_CONDITIONALS_CACHE[key]
        return

    try:
        model.prepare_conditionals(str(reference), exaggeration=0.5)
        _CHATTERBOX_CONDITIONALS_CACHE[key] = getattr(model, "conds", None)
    except Exception as exc:
        raise RuntimeError(
            f"Chatterbox could not use the voice reference file '{reference}': {exc}. "
            "Use a clean voice clip longer than five seconds, or select another reference."
        ) from exc


_SERIOUS_AUDIO_RE = re.compile(
    r"\b(?:death|died|fatal|tragedy|tragic|injur(?:y|ies|ed)|hospitalised|hospitalized|"
    r"assault|abuse|mourning|heartbreaking|heartbroken|bereavement|scandal|suspended)\b",
    re.IGNORECASE,
)
_SURPRISE_AUDIO_RE = re.compile(
    r"\b(?:unbelievable|unthinkable|against all odds|stuns?|shocks?|shock win|"
    r"stunning comeback|dramatic comeback|miracle|last[- ]ball(?: thriller| finish| win)?|"
    r"last[- ]gasp|defied expectations)\b",
    re.IGNORECASE,
)
_HIGH_ENERGY_AUDIO_RE = re.compile(
    r"\b(?:thriller|comeback|record[- ]breaking|clutch|clinches?|dominates?|smashes?|"
    r"crushes?|century|hat[- ]trick|champion|title win|match[- ]winner)\b",
    re.IGNORECASE,
)


def _chatterbox_audio_texts(texts: list[str]) -> list[str]:
    """Add at most one native Turbo cue to an otherwise unchanged script when surprise is explicit."""
    audio_texts = list(texts)
    if any(_SERIOUS_AUDIO_RE.search(text) for text in texts):
        return audio_texts
    surprise_scene = next(
        (index for index, text in enumerate(texts) if _SURPRISE_AUDIO_RE.search(text)),
        None,
    )
    if surprise_scene is not None:
        audio_texts[surprise_scene] = "[gasp] " + audio_texts[surprise_scene]
    return audio_texts


def _chatterbox_delivery(text: str, scene_number: int, scene_count: int) -> tuple[str, float]:
    """Use script meaning for conservative line-level sampling; Turbo has no emotion slider."""
    serious = bool(_SERIOUS_AUDIO_RE.search(text))
    high_energy = bool(_HIGH_ENERGY_AUDIO_RE.search(text)) or bool(_SURPRISE_AUDIO_RE.search(text)) or "!" in text

    if serious:
        temperature = 0.72
    elif high_energy:
        temperature = 0.88
    elif scene_number == 1:
        temperature = 0.84
    elif scene_number == scene_count:
        temperature = 0.82
    else:
        temperature = 0.77
    return text, temperature


def _chatterbox_result_from_manifest(
    texts: list[str],
    output_dir: Path,
    manifest: dict[str, Any],
    actual_ref: Path | None,
    from_cache: bool,
    voice_label: str | None = None,
) -> dict[str, Any]:
    durations = [float(value) for value in manifest["scene_durations"]]
    scenes = []
    paths = []
    for number, (text, duration) in enumerate(zip(texts, durations), 1):
        slide_file = output_dir / f"slide_{number:02d}.wav"
        paths.append(str(slide_file))
        scenes.append(
            {
                "scene": number,
                "path": str(slide_file),
                "duration": round(duration, 3),
                "timings": synthesize_linear_timings(text, duration),
                "from_cache": from_cache,
            }
        )

    total_duration = float(manifest["total_duration"])
    result = {
        "full_path": str(output_dir / "full.wav"),
        "slide_paths": paths,
        "duration": round(total_duration, 3),
        "total_duration": round(total_duration, 3),
        "model": "Chatterbox-Turbo",
        "reference": str(actual_ref) if actual_ref else "Built-in Chatterbox voice",
        "voice_label": voice_label or ("Voice reference" if actual_ref else "Built-in voice"),
        "scenes": scenes,
        "language": "english",
        "voice": "chatterbox-turbo",
        "rate_percent": 0.0,
        "pitch": PITCH,
        "duration_corrected": bool(manifest["duration_corrected"]),
        "delivery": "Script-led",
    }
    if manifest.get("top5"):
        result["schema"] = "final-shorts.top5-audio.v1"
        result["source_schema"] = "final-shorts.top5-script.v1"
        result["max_scene_duration"] = (
            round(max(float(scene["duration"]) for scene in scenes), 3) if scenes else 0.0
        )
    return result


def generate_chatterbox_audio(
    version_or_slides: list[dict[str, Any]] | dict[str, Any],
    run_number: int = 1,
    output_dir: str | Path | None = None,
    reference: Path | str | None = None,
) -> dict[str, Any]:
    """Generate script-led Turbo narration and reuse exact outputs when available."""
    if isinstance(version_or_slides, dict):
        language = str(version_or_slides.get("language_used") or "english").strip().casefold()
        if language not in {"english", "en"}:
            raise ValueError(
                "Chatterbox Turbo supports English only. Select Edge-TTS for Hindi or Telugu narration."
            )
        slides = version_or_slides.get("slides") or version_or_slides.get("script") or []
        is_top5 = version_or_slides.get("schema") == "final-shorts.top5-script.v1"
    else:
        slides = list(version_or_slides or [])
        is_top5 = False

    if not slides:
        raise ValueError("The approved Scriptwriter version has no slides.")

    texts = [
        _clean_text(slide.get("voiceover") or slide.get("headline"))
        if isinstance(slide, dict)
        else ""
        for slide in slides
    ]
    for number, text in enumerate(texts, 1):
        if not text:
            raise ValueError(f"Slide {number} has no voiceover.")

    if reference is not None:
        actual_ref = Path(reference)
        if not actual_ref.is_file():
            raise FileNotFoundError(f"Chatterbox reference file is missing: {actual_ref}")
    else:
        actual_ref = AUDIO_REFERENCE if AUDIO_REFERENCE.is_file() else None

    reference_fingerprint = None
    if actual_ref:
        reference_fingerprint = {
            "path": str(actual_ref.resolve()),
            "sha256": _file_sha256(actual_ref),
        }

    audio_texts = _chatterbox_audio_texts(texts)

    temperatures = [
        _chatterbox_delivery(text, number, len(texts))[1]
        for number, text in enumerate(texts, 1)
    ]
    signature_payload = {
        "cache_version": "chatterbox-turbo-audio-v2-script-led",
        "texts": texts,
        "audio_texts": audio_texts,
        "temperatures": temperatures,
        "run_number": int(run_number),
        "reference": reference_fingerprint,
        "gap_seconds": 0.08,
        "max_duration_seconds": 30.0,
        "top5": is_top5,
    }
    signature = hashlib.sha256(
        json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    output_key = hashlib.sha1(" ".join(texts).encode("utf-8")).hexdigest()[:12]
    output_base = Path(output_dir) if output_dir is not None else CHATTERBOX_OUTPUT_ROOT / output_key
    # A unique directory per exact input lets QC compare voices without overwriting old variants.
    out_path = output_base / f".chatterbox_{signature[:20]}"
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / ".chatterbox_manifest.json"
    manifest = None

    try:
        candidate = json.loads(manifest_path.read_text(encoding="utf-8"))
        durations = candidate.get("scene_durations")
        required_paths = [out_path / "full.wav"] + [
            out_path / f"slide_{number:02d}.wav" for number in range(1, len(texts) + 1)
        ]
        if (
            candidate.get("signature") == signature
            and isinstance(durations, list)
            and len(durations) == len(texts)
            and all(float(value) > 0 for value in durations)
            and float(candidate.get("total_duration", 0)) > 0
            and all(path.is_file() and path.stat().st_size > 500 for path in required_paths)
        ):
            manifest = candidate
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        manifest = None

    voice_label = next(
        (
            label for label, path in CHATTERBOX_VOICE_REFERENCES.items()
            if actual_ref is not None and path.resolve() == actual_ref.resolve()
        ),
        "Custom reference" if actual_ref else "Built-in voice",
    )
    if manifest is not None:
        return _chatterbox_result_from_manifest(
            texts, out_path, manifest, actual_ref, from_cache=True, voice_label=voice_label
        )

    import torch
    import torchaudio

    model = get_chatterbox_model()
    _prepare_chatterbox_reference(model, actual_ref, reference_fingerprint)

    for path in out_path.glob("*.wav"):
        try:
            path.unlink()
        except OSError:
            pass
    manifest_path.unlink(missing_ok=True)

    waves = []
    durations = []
    for number, text in enumerate(audio_texts, 1):
        torch.manual_seed(run_number * 100 + number)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(run_number * 100 + number)

        wav = model.generate(text, temperature=temperatures[number - 1])
        wav = wav.detach().cpu()
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        waves.append(wav)
        durations.append(wav.shape[-1] / model.sr)

    gap_samples = int(model.sr * 0.08)
    raw_duration = sum(durations) + max(0, len(waves) - 1) * 0.08
    if raw_duration > 30.0:
        try:
            import librosa
            rate = min(1.05, raw_duration / 29.7)
            waves = [
                torch.from_numpy(
                    librosa.effects.time_stretch(w.squeeze(0).numpy(), rate=rate)
                ).unsqueeze(0)
                for w in waves
            ]
        except Exception as exc:
            raise RuntimeError("Audio is over 30 seconds and librosa time-stretch failed.") from exc

    final_duration = sum(w.shape[-1] / model.sr for w in waves) + max(0, len(waves) - 1) * 0.08
    if final_duration > 30.0:
        raise RuntimeError("The generated narration is too long to fit the 30-second Short even with slight speed adjustment.")

    scenes = []
    for number, (wav, text) in enumerate(zip(waves, texts), 1):
        slide_file = out_path / f"slide_{number:02d}.wav"
        torchaudio.save(str(slide_file), wav, model.sr)
        duration = wav.shape[-1] / model.sr
        scenes.append(
            {
                "scene": number,
                "path": str(slide_file),
                "duration": round(duration, 3),
                "timings": synthesize_linear_timings(text, duration),
                "from_cache": False,
            }
        )

    silence = torch.zeros((1, gap_samples))
    combined = []
    for number, wav in enumerate(waves):
        combined.append(wav)
        if number < len(waves) - 1:
            combined.append(silence)
    full_wav = torch.cat(combined, dim=-1)
    peak = full_wav.abs().max()
    if peak.item() > 0:
        full_wav = full_wav * (0.94 / peak)
    torchaudio.save(str(out_path / "full.wav"), full_wav, model.sr)
    total_duration = full_wav.shape[-1] / model.sr

    manifest = {
        "signature": signature,
        "scene_durations": [round(wav.shape[-1] / model.sr, 6) for wav in waves],
        "total_duration": round(total_duration, 6),
        "duration_corrected": raw_duration > 30.0,
        "top5": is_top5,
    }
    fd, raw_manifest_path = tempfile.mkstemp(
        prefix=".chatterbox_manifest_", suffix=".json.tmp", dir=out_path
    )
    os.close(fd)
    temp_manifest = Path(raw_manifest_path)
    try:
        temp_manifest.write_text(json.dumps(manifest), encoding="utf-8")
        temp_manifest.replace(manifest_path)
    finally:
        temp_manifest.unlink(missing_ok=True)

    return _chatterbox_result_from_manifest(
        texts, out_path, manifest, actual_ref, from_cache=False, voice_label=voice_label
    )

def _use_chatterbox_engine(engine: str | None, voice: str | None, handoff: dict[str, Any]) -> bool:
    """Select Chatterbox by default; use Edge-TTS only when explicitly requested."""
    selected = engine if engine is not None else handoff.get("voice_engine")
    chatterbox_names = {
        "chatterbox",
        "chatterbox-turbo",
        "chatterbox turbo",
        "chatterbox turbo (voice cloning)",
        "clone",
    }
    edge_names = {"edge", "edge-tts", "edge tts", "edge-tts neural"}
    if selected is not None:
        name = str(selected).strip().casefold()
        if name in chatterbox_names:
            return True
        if name in edge_names:
            return False
        raise ValueError(f"Unsupported audio engine: {selected}")
    if voice:
        return str(voice).strip().casefold() in chatterbox_names
    return True


def generate_audio(
    approved_script: dict,
    output_dir: str | Path = "output/audio_test",
    voice: str | None = None,
    engine: str | None = None,
    run_number: int = 1,
    reference: str | Path | None = None,
) -> dict[str, Any]:
    """Generate approved narration audio with Chatterbox Turbo voice cloning or Edge-TTS."""
    if (
        not isinstance(approved_script, dict)
        or approved_script.get("approved_for_audio") is not True
    ):
        raise ValueError("Audio requires the approved Scriptwriter handoff.")

    scenes = approved_script.get("script")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Approved script contains no scenes.")

    is_chatterbox = _use_chatterbox_engine(engine, voice, approved_script)
    if is_chatterbox:
        return generate_chatterbox_audio(
            approved_script,
            run_number=run_number,
            output_dir=output_dir,
            reference=reference,
        )

    language = str(
        approved_script.get("language_used") or "english"
    ).strip().casefold()
    if language not in VOICES:
        raise ValueError(f"Unsupported audio language: {language}")

    selected_voice = resolve_voice(
        language,
        gender=approved_script.get("voice_gender"),
        voice=voice or approved_script.get("voice"),
    )

    for index, scene in enumerate(scenes, 1):
        if not _clean_text(scene.get("voiceover")):
            raise ValueError(f"Scene {index} has no narration text.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    def _call_rate(sc, lang, rate, out, vc):
        try:
            import inspect
            if "voice" in inspect.signature(_generate_at_rate).parameters:
                return asyncio.run(_generate_at_rate(sc, lang, rate, out, voice=vc))
        except (TypeError, ValueError):
            pass
        return asyncio.run(_generate_at_rate(sc, lang, rate, out))

    rate_percent = BASE_RATE_PERCENT
    results = _call_rate(scenes, language, rate_percent, output_path, selected_voice)
    total = round(sum(float(item["duration"]) for item in results), 3)
    corrected = False

    if total > MAX_DURATION_SECONDS:
        multiplier = total / CORRECTION_TARGET_SECONDS
        adjusted = (
            (1.0 + rate_percent / 100.0) * multiplier - 1.0
        ) * 100.0
        adjusted = min(100.0, max(rate_percent + 1.0, adjusted))
        results = _call_rate(scenes, language, adjusted, output_path, selected_voice)
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
        "voice": selected_voice,
        "rate_percent": rate_percent,
        "pitch": PITCH,
        "scenes": results,
        "total_duration": total,
        "duration_corrected": corrected,
    }


def generate_top5_audio(
    approved_top5_script: dict[str, Any],
    output_dir: str | Path = "output/audio_top5_test",
    voice: str | None = None,
    engine: str | None = None,
    run_number: int = 1,
    reference: str | Path | None = None,
) -> dict[str, Any]:
    """Generate one audio scene for each of the six approved Top-5 spoken headlines."""
    if not isinstance(approved_top5_script, dict):
        raise ValueError("Top-5 Audio requires the approved Top-5 Scriptwriter handoff.")
    if approved_top5_script.get("schema") != "final-shorts.top5-script.v1":
        raise ValueError("Top-5 Audio requires the approved Top-5 Scriptwriter handoff.")

    is_chatterbox = _use_chatterbox_engine(engine, voice, approved_top5_script)
    if is_chatterbox:
        return generate_chatterbox_audio(
            approved_top5_script,
            run_number=run_number,
            output_dir=output_dir,
            reference=reference,
        )

    slides = approved_top5_script.get("slides")
    if not isinstance(slides, list) or len(slides) != TOP5_SCENE_COUNT:
        raise ValueError("Top-5 Audio requires exactly six spoken slides.")

    scenes = []
    for expected_number, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            raise ValueError(f"Top-5 slide {expected_number} is malformed.")
        if slide.get("slide_number") != expected_number:
            raise ValueError(f"Top-5 slide {expected_number} has the wrong slide number.")
        headline = _clean_text(slide.get("headline"))
        if not headline:
            raise ValueError(f"Top-5 slide {expected_number} has no spoken headline.")
        scenes.append({"voiceover": headline})

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    def _call_rate(sc, lang, rate, out, vc):
        try:
            import inspect
            if "voice" in inspect.signature(_generate_at_rate).parameters:
                return asyncio.run(_generate_at_rate(sc, lang, rate, out, voice=vc))
        except (TypeError, ValueError):
            pass
        return asyncio.run(_generate_at_rate(sc, lang, rate, out))

    language = str(approved_top5_script.get("language_used") or "english").strip().casefold()
    if language not in VOICES:
        language = "english"
    selected_voice = resolve_voice(
        language,
        gender=approved_top5_script.get("voice_gender"),
        voice=voice or approved_top5_script.get("voice"),
    )

    rate_percent = BASE_RATE_PERCENT
    results = _call_rate(scenes, language, rate_percent, output_path, selected_voice)
    corrected = False

    total_duration = sum(float(scene["duration"]) for scene in results)
    max_duration = max(float(scene["duration"]) for scene in results)
    if total_duration > TOP5_MAX_TOTAL_DURATION_SECONDS:
        multiplier = total_duration / TOP5_TOTAL_CORRECTION_TARGET_SECONDS
        adjusted = (
            (1.0 + rate_percent / 100.0) * multiplier - 1.0
        ) * 100.0
        adjusted = min(100.0, max(rate_percent + 1.0, adjusted))
        results = _call_rate(scenes, language, adjusted, output_path, selected_voice)
        total_duration = sum(float(scene["duration"]) for scene in results)
        max_duration = max(float(scene["duration"]) for scene in results)
        rate_percent = round(adjusted, 2)
        corrected = True

    if total_duration > TOP5_MAX_TOTAL_DURATION_SECONDS:
        raise RuntimeError(
            "Top-5 audio remains over the 30-second Shorts limit after one "
            f"measured speed correction (total {total_duration:.2f}s)."
        )

    return {
        "schema": "final-shorts.top5-audio.v1",
        "source_schema": "final-shorts.top5-script.v1",
        "language": language,
        "voice": selected_voice,
        "rate_percent": rate_percent,
        "pitch": PITCH,
        "scenes": results,
        "total_duration": round(total_duration, 3),
        "max_scene_duration": round(max_duration, 3),
        "duration_corrected": corrected,
    }


def approve_top5_audio(audio: dict[str, Any]) -> dict[str, Any]:
    """Mark verified six-scene Top-5 audio as the handoff for Visuals."""
    if not isinstance(audio, dict) or audio.get("schema") != "final-shorts.top5-audio.v1":
        raise ValueError("Top-5 Audio output is required for approval.")

    scenes = audio.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != TOP5_SCENE_COUNT:
        raise ValueError("Top-5 Audio approval requires exactly six scenes.")

    for expected_number, scene in enumerate(scenes, 1):
        if scene.get("scene") != expected_number:
            raise ValueError(f"Top-5 Audio scene {expected_number} is out of order.")
        path = Path(scene.get("path", ""))
        if not path.exists() or path.stat().st_size <= 500:
            raise ValueError(
                f"Top-5 Audio file for scene {expected_number} is missing or invalid."
            )

    result = dict(audio)
    result["approved_for_visuals"] = True
    return result


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
    result = dict(audio)
    result["approved_for_visuals"] = True
    return result
