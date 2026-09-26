"""Function 05: subtitle generation from approved script and audio timings."""

from __future__ import annotations

import re
from typing import Any

SCHEMA = "final-shorts.subtitles.v1"
MAX_WORDS_PER_CUE = 4
MAX_CUE_SECONDS = 1.6
STRONG_BREAK = re.compile(r"[.!?][\"'”’)]?$")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalise_word(value: str) -> str:
    return re.sub(r"[^\w]+", "", str(value or "").casefold())


def _display_words(script_text: str, timings: list[dict[str, Any]]) -> list[str]:
    tokens = _clean(script_text).split()
    result = []

    for index, timing in enumerate(timings):
        timed_word = _clean(timing.get("word"))
        if not timed_word:
            result.append("")
            continue

        if index < len(tokens):
            script_word = tokens[index]
            if _normalise_word(script_word) == _normalise_word(timed_word):
                result.append(script_word)
                continue

        result.append(timed_word)

    return result


def _group(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    cues: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for word in words:
        current.append(word)
        duration = float(word["end"]) - float(current[0]["start"])
        if (
            len(current) >= MAX_WORDS_PER_CUE
            or duration >= MAX_CUE_SECONDS
            or bool(STRONG_BREAK.search(str(word["text"])))
        ):
            cues.append(current)
            current = []

    if current:
        cues.append(current)

    return cues


def generate_subtitles(
    approved_script: dict,
    approved_audio: dict,
) -> dict[str, Any]:
    """Build the renderer handoff using only existing script and audio timings."""
    if (
        not isinstance(approved_script, dict)
        or approved_script.get("approved_for_audio") is not True
    ):
        raise ValueError("Subtitles require the approved Scriptwriter handoff.")

    if (
        not isinstance(approved_audio, dict)
        or approved_audio.get("approved_for_visuals") is not True
    ):
        raise ValueError("Subtitles require the approved Audio handoff.")

    script_scenes = approved_script.get("script")
    audio_scenes = approved_audio.get("scenes")
    if (
        not isinstance(script_scenes, list)
        or not isinstance(audio_scenes, list)
        or not script_scenes
        or len(script_scenes) != len(audio_scenes)
    ):
        raise ValueError("Script and audio scene counts do not match.")

    script_language = _clean(approved_script.get("language_used") or "english").casefold()
    audio_language = _clean(approved_audio.get("language") or "english").casefold()
    if script_language != audio_language:
        raise ValueError("Script and audio languages do not match.")

    cues: list[dict[str, Any]] = []
    scene_offset = 0.0

    for number, (script_scene, audio_scene) in enumerate(
        zip(script_scenes, audio_scenes),
        1,
    ):
        duration = float(audio_scene.get("duration") or 0.0)
        timings = audio_scene.get("timings")
        if duration <= 0 or not isinstance(timings, list) or not timings:
            raise ValueError(f"Scene {number} has no usable audio timings.")

        display_words = _display_words(script_scene.get("voiceover", ""), timings)
        timed_words: list[dict[str, Any]] = []

        for index, timing in enumerate(timings):
            try:
                start = float(timing["start"])
                end = float(timing["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Scene {number} contains invalid word timing.") from exc

            if start < 0 or end <= start:
                raise ValueError(f"Scene {number} contains invalid word timing.")
            if start > duration + 0.10 or end > duration + 0.10:
                raise ValueError(f"Scene {number} timing exceeds its audio duration.")

            start = min(duration, start)
            end = min(duration, end)
            if end <= start:
                continue

            timed_words.append(
                {
                    "text": (
                        display_words[index]
                        if index < len(display_words) and display_words[index]
                        else _clean(timing["word"])
                    ),
                    "start": round(scene_offset + start, 3),
                    "end": round(scene_offset + end, 3),
                }
            )

        for group in _group(timed_words):
            cues.append(
                {
                    "start": group[0]["start"],
                    "end": group[-1]["end"],
                    "words": group,
                }
            )

        scene_offset = round(scene_offset + duration, 3)

    result = {
        "schema": SCHEMA,
        "language": audio_language,
        "cues": cues,
    }
    if not cues:
        raise ValueError("No subtitle cues were generated.")
    return result
