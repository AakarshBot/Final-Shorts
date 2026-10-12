"""Long-form Documentary Subtitles & Cinematic Act Title Engine.

Produces broadcast-standard 16:9 lower-third subtitle phrases (5-8 words per cue)
and cinematic Act chapter billboards from approved script and audio timings.
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA = "final-shorts.longform-subtitles.v1"
MAX_WORDS_PER_LOWER_THIRD = 7
MAX_CUE_SECONDS = 3.2
MIN_CUE_SECONDS = 1.0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hrs = millis // 3600000
    millis %= 3600000
    mins = millis // 60000
    millis %= 60000
    secs = millis // 1000
    millis %= 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


class LongformSubtitleEngine:
    """Generates broadcast documentary lower-third subtitles and Act title cards."""

    @classmethod
    def generate(
        cls,
        approved_script: dict[str, Any],
        approved_audio: dict[str, Any],
    ) -> dict[str, Any]:
        if not approved_script or not isinstance(approved_script, dict):
            raise ValueError("Long-form Subtitles require approved Scriptwriter data.")
        if not isinstance(approved_audio, dict) or not approved_audio.get("scenes"):
            raise ValueError("Long-form Subtitles require approved Audio scenes.")

        audio_scenes = approved_audio.get("scenes", [])
        script_scenes = approved_script.get("scenes", [])
        acts = approved_script.get("acts", [])

        # Map scene number to act details
        scene_to_act = {}
        for sc in script_scenes:
            s_num = sc.get("scene_number")
            a_num = sc.get("act_number", 1)
            if s_num is not None:
                scene_to_act[s_num] = a_num

        cues: list[dict[str, Any]] = []
        act_billboards: list[dict[str, Any]] = []
        seen_acts: set[int] = set()

        for a_scene in audio_scenes:
            sc_num = a_scene.get("scene", 1)
            act_num = a_scene.get("act") or scene_to_act.get(sc_num, 1)
            sc_start = float(a_scene.get("start_seconds", 0.0))
            timings = a_scene.get("timings") or []

            # Check if this is the first scene of an Act to register a billboard
            if act_num not in seen_acts:
                seen_acts.add(act_num)
                # Find chapter title
                ch_title = f"Act {act_num}"
                for a in acts:
                    if a.get("act_number") == act_num:
                        ch_title = a.get("chapter_title", ch_title)
                        break
                act_billboards.append({
                    "act_number": act_num,
                    "title": ch_title.upper(),
                    "start_time": sc_start,
                    "duration": 3.5,
                })

            if not timings:
                continue

            # Group timings into natural lower-third reading phrases
            current_words: list[str] = []
            cue_start = sc_start + float(timings[0].get("start", 0.0))
            cue_end = cue_start

            for idx, item in enumerate(timings):
                w = _clean(item.get("word"))
                if not w:
                    continue
                w_start = sc_start + float(item.get("start", 0.0))
                w_end = sc_start + float(item.get("end", 0.0))

                current_words.append(w)
                cue_end = w_end

                is_sentence_end = bool(re.search(r"[.!?]$", w))
                is_phrase_end = len(current_words) >= 4 and bool(re.search(r"[,;:]$", w))
                is_length_limit = len(current_words) >= MAX_WORDS_PER_LOWER_THIRD
                is_time_limit = (cue_end - cue_start) >= MAX_CUE_SECONDS

                if is_sentence_end or is_phrase_end or is_length_limit or is_time_limit:
                    text_phrase = " ".join(current_words)
                    cues.append({
                        "cue_index": len(cues) + 1,
                        "act": act_num,
                        "scene": sc_num,
                        "start": round(cue_start, 3),
                        "end": round(cue_end, 3),
                        "duration": round(cue_end - cue_start, 3),
                        "text": text_phrase,
                    })
                    current_words = []
                    if idx + 1 < len(timings):
                        cue_start = sc_start + float(timings[idx + 1].get("start", 0.0))

            if current_words:
                text_phrase = " ".join(current_words)
                cues.append({
                    "cue_index": len(cues) + 1,
                    "act": act_num,
                    "scene": sc_num,
                    "start": round(cue_start, 3),
                    "end": round(cue_end, 3),
                    "duration": round(cue_end - cue_start, 3),
                    "text": text_phrase,
                })

        # Generate standard SRT formatting
        srt_lines = []
        for i, c in enumerate(cues, 1):
            srt_lines.append(str(i))
            srt_lines.append(f"{_format_srt_time(c['start'])} --> {_format_srt_time(c['end'])}")
            srt_lines.append(c["text"])
            srt_lines.append("")
        srt_text = "\n".join(srt_lines)

        total_dur = float(approved_audio.get("total_duration") or (cues[-1]["end"] if cues else 0.0))

        return {
            "schema": SCHEMA,
            "cues": cues,
            "cue_count": len(cues),
            "act_billboards": act_billboards,
            "srt_content": srt_text,
            "total_duration": round(total_dur, 2),
            "acts_count": len(act_billboards),
        }

    @classmethod
    def approve(cls, subtitle_data: dict[str, Any]) -> dict[str, Any]:
        """Validates and marks Long-form subtitles as approved for video rendering."""
        if not isinstance(subtitle_data, dict) or subtitle_data.get("schema") != SCHEMA:
            raise ValueError("Invalid Long-form subtitle data.")
        if not subtitle_data.get("cues"):
            raise ValueError("Long-form subtitles contain no cues.")
        approved = dict(subtitle_data)
        approved["approved_for_render"] = True
        return approved


__all__ = ["LongformSubtitleEngine", "SCHEMA"]
