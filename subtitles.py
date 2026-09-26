"""Function 05: deterministic subtitles built from approved Edge-TTS timings."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


MAX_WORDS_PER_CUE = 6
MAX_CHARS_PER_CUE = 40
MAX_CUE_SECONDS = 1.8
MAX_GAP_SECONDS = 0.45
MIN_CUE_SECONDS = 0.15
MAX_DURATION_SECONDS = 30.0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _normalise_timings(
    timings: list[dict[str, Any]],
    duration: float,
) -> list[dict[str, Any]]:
    if duration <= 0:
        raise ValueError("Subtitle scene duration must be positive.")

    result = []
    previous_start = -0.001
    for item in timings or []:
        if not isinstance(item, dict):
            continue
        word = _clean(item.get("word"))
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        if not word or start < previous_start or end < start:
            raise ValueError("Subtitle word timings are invalid or out of order.")
        if start > duration + 0.10:
            raise ValueError("Subtitle timing starts after the audio duration.")
        end = min(duration, end)
        if end <= start:
            end = min(duration, start + MIN_CUE_SECONDS)
        result.append(
            {
                "word": word,
                "start": max(0.0, start),
                "end": end,
            }
        )
        previous_start = start

    if not result:
        raise ValueError("Approved audio contains no usable word timings.")
    return result


def _build_cues(timings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    words: list[str] = []
    cue_start = 0.0
    cue_end = 0.0
    previous_end = 0.0

    def flush() -> None:
        nonlocal words, cue_start, cue_end
        if not words:
            return
        cues.append(
            {
                "start": round(cue_start, 3),
                "end": round(max(cue_start + MIN_CUE_SECONDS, cue_end), 3),
                "text": " ".join(words),
            }
        )
        words = []

    for timing in timings:
        word = timing["word"]
        start = timing["start"]
        end = timing["end"]
        projected = " ".join(words + [word])
        too_many_words = len(words) >= MAX_WORDS_PER_CUE
        too_long = bool(words) and len(projected) > MAX_CHARS_PER_CUE
        too_slow = bool(words) and end - cue_start > MAX_CUE_SECONDS
        too_large_gap = bool(words) and start - previous_end > MAX_GAP_SECONDS

        if too_many_words or too_long or too_slow or too_large_gap:
            flush()
        if not words:
            cue_start = start
        words.append(word)
        cue_end = end
        previous_end = end

    flush()
    return cues


def _srt(cues: list[dict[str, Any]], offset: float = 0.0) -> str:
    blocks = []
    for index, cue in enumerate(cues, 1):
        blocks.append(
            f"{index}\n"
            f"{_timestamp(cue['start'] + offset)} --> "
            f"{_timestamp(cue['end'] + offset)}\n"
            f"{cue['text']}\n"
        )
    return "\n".join(blocks).strip() + ("\n" if blocks else "")


def generate_subtitles(
    approved_audio: dict[str, Any],
    output_dir: str | Path = "output/subtitles_test",
) -> dict[str, Any]:
    if (
        not isinstance(approved_audio, dict)
        or approved_audio.get("approved_for_visuals") is not True
    ):
        raise ValueError("Subtitles require the approved Audio handoff.")

    scenes = approved_audio.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Approved audio contains no scenes.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    scene_results = []
    combined_cues = []
    combined_offset = 0.0

    for index, scene in enumerate(scenes, 1):
        try:
            duration = float(scene.get("duration"))
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f"Scene {index} has no valid audio duration.")

        if combined_offset + duration > MAX_DURATION_SECONDS + 0.10:
            raise ValueError("Approved audio exceeds the 30-second subtitle limit.")

        timings = _normalise_timings(scene.get("timings") or [], duration)
        cues = _build_cues(timings)
        srt = _srt(cues)

        path = output_path / f"scene_{index}.srt"
        path.write_text(srt, encoding="utf-8")

        scene_results.append(
            {
                "scene": index,
                "duration": round(duration, 3),
                "cues": cues,
                "srt": srt,
                "path": str(path),
            }
        )
        for cue in cues:
            combined_cues.append(
                {
                    "start": round(cue["start"] + combined_offset, 3),
                    "end": round(cue["end"] + combined_offset, 3),
                    "text": cue["text"],
                }
            )
        combined_offset += duration

    combined_srt = _srt(combined_cues)
    combined_path = output_path / "final_shorts.srt"
    combined_path.write_text(combined_srt, encoding="utf-8")

    return {
        "language": _clean(approved_audio.get("language")) or "english",
        "format": "srt",
        "scenes": scene_results,
        "cues": combined_cues,
        "srt": combined_srt,
        "srt_path": str(combined_path),
        "total_duration": round(combined_offset, 3),
    }


def approve_subtitles(subtitles: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(subtitles, dict) or not subtitles.get("scenes"):
        raise ValueError("No generated subtitles are available for approval.")
    combined_path = Path(str(subtitles.get("srt_path") or ""))
    try:
        valid_combined = combined_path.is_file() and combined_path.stat().st_size > 0
    except OSError:
        valid_combined = False
    if not valid_combined:
        raise ValueError("The combined subtitle file is missing or empty.")
    for scene in subtitles["scenes"]:
        path = Path(str(scene.get("path") or ""))
        try:
            valid_scene = path.is_file() and path.stat().st_size > 0
        except OSError:
            valid_scene = False
        if not valid_scene:
            raise ValueError(
                f"Subtitle file for scene {scene.get('scene')} is missing or empty."
            )
    result = json.loads(json.dumps(subtitles, ensure_ascii=False))
    result["approved_for_renderer"] = True
    return result
