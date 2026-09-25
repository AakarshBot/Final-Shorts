"""Function 02: sports Shorts script writing."""

from __future__ import annotations

import json
import os
import re
import time
from difflib import SequenceMatcher

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"
TIMEOUT = 30
MAX_SOURCE_CHARS = 12000
MAX_SCENES = 5
MIN_SCENES = 4
SCENE_1_MAX_WORDS = 14
TARGET_MIN_SECONDS = 22
TARGET_MAX_SECONDS = 27
HARD_MAX_SECONDS = 30

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and titles in punchy, natural spoken English.",
    "hindi": "Write all narration and titles in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and titles in natural spoken Telugu using Telugu script.",
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_title_index": {
            "type": "integer",
        },
        "seo_description": {
            "type": "string",
        },
        "pinned_comment": {
            "type": "string",
        },
        "script": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "voiceover": {"type": "string"},
                    "narrative_role": {
                        "type": "string",
                        "enum": ["hook", "development", "context", "consequence"],
                    },
                    "primary_entity": {"type": "string"},
                    "visual_intent": {"type": "string"},
                    "specific_search_prompt": {"type": "string"},
                    "sport_or_topic_category": {"type": "string"},
                },
                "required": [
                    "voiceover",
                    "narrative_role",
                    "primary_entity",
                    "visual_intent",
                    "specific_search_prompt",
                    "sport_or_topic_category",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "titles",
        "recommended_title_index",
        "seo_description",
        "pinned_comment",
        "script",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You are the original editorial writer for a human-reviewed sports Shorts channel.

Use only the supplied story evidence. Tell the complete important story in fresh wording.
Never invent facts, quotes, motives, numbers, predictions, outcomes or causal claims.
Never copy a complete source sentence.

WRITING CONTRACT:
- This is a regular sports Short, not a Top-5 or Deep-Dive format.
- Write exactly 4 or 5 narration scenes.
- Use a clear arc: factual hook → development/context → consequence or useful closing fact.
- Include the essential event, the key people/teams involved, important supported facts, necessary context and the immediate consequence when supported.
- Do not skip a crucial supported fact just to save words.
- Target about 22–27 seconds of natural narration; never exceed 30 seconds.
- Do not pad the script to reach a duration.
- Every scene must add useful new information.
- No filler, generic setup, CTA, retention bait or production instructions.
- Scene 1 is a crisp factual hook: target 10–12 words, hard maximum 14 words.
- Do not stack background context into Scene 1.
- Curiosity must come from a real supported fact, never withheld information.
- Use natural spoken sentences. Spell out numbers, acronyms and symbols where practical for TTS.
- Generate exactly 3 title candidates.
- The titles are stored for later title selection; do not explain or rank them in the narration.
- For every scene, provide the primary visual entity, a useful visual intent, a specific search prompt and the sport/topic category for the later visual stage.
- Return only JSON matching the supplied schema.

Before returning JSON, silently check:
1. Scene 1 is 14 words or fewer.
2. The script has 4–5 scenes.
3. The narration is roughly 22–27 seconds and no more than 30 seconds.
4. Every factual claim is supported by the supplied evidence.
5. No scene is repetitive, generic or filler.
6. Exactly three titles are present.
"""

_REPAIR_PROMPT = """Rewrite the supplied draft once.

Preserve every supported crucial fact, entity, number and attribution.
Do not add facts.
Do not remove important facts.
Remove repetition or unnecessary wording only.
Keep 4–5 scenes.
Keep Scene 1 at 10–12 words, hard maximum 14.
Target about 22–27 seconds and never exceed 30 seconds.
Return only JSON matching the supplied schema.
"""


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _story_text(story) -> str:
    if hasattr(story, "__dataclass_fields__"):
        story = {
            name: getattr(story, name)
            for name in story.__dataclass_fields__
        }

    story = dict(story or {})
    values = []
    for key in (
        "research_evidence_text",
        "text",
        "summary",
        "description",
        "title",
        "topic",
    ):
        value = _clean(story.get(key))
        if value:
            values.append(value)

    text = "\n\n".join(dict.fromkeys(values))
    return text[:MAX_SOURCE_CHARS]


def _words(text: str) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(text or ""), flags=re.UNICODE))


def _normalise(text: str) -> str:
    return re.sub(r"[^\w ]+", " ", str(text or "").casefold(), flags=re.UNICODE).strip()


def _copied_sentence(script_text: str, source_text: str) -> bool:
    source_sentences = [
        _normalise(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", source_text)
        if _words(part) >= 8
    ]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", script_text):
        candidate = _normalise(sentence)
        if _words(candidate) < 8:
            continue
        for source in source_sentences:
            if candidate == source:
                return True
            if SequenceMatcher(None, candidate, source).ratio() >= 0.92:
                return True
    return False


def _validate(result: dict, source_text: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider did not return an object."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3:
        return False, "Exactly three titles are required."
    if any(not _clean(title) for title in titles):
        return False, "All title candidates must contain text."

    try:
        index = int(result.get("recommended_title_index"))
    except (TypeError, ValueError):
        return False, "The recommended title index is invalid."
    if index not in (1, 2, 3):
        return False, "The recommended title index is invalid."

    scenes = result.get("script")
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        return False, "A regular sports Short must contain 4 or 5 scenes."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            return False, f"Scene {number} is malformed."

        voiceover = _clean(scene.get("voiceover"))
        entity = _clean(scene.get("primary_entity"))
        intent = _clean(scene.get("visual_intent"))
        search_prompt = _clean(scene.get("specific_search_prompt"))
        category = _clean(scene.get("sport_or_topic_category"))

        if not voiceover:
            return False, f"Scene {number} is empty."
        if not entity:
            return False, f"Scene {number} is missing its primary visual entity."
        if not intent or not search_prompt or not category:
            return False, f"Scene {number} is missing visual metadata."

        forbidden = (
            r"\bwait (?:until|till|for) (?:the )?end\b",
            r"\bwait for it\b",
            r"\bwatch(?:ing)? until the end\b",
            r"\bstay tuned\b",
            r"\bdon['’]?t go anywhere\b",
            r"\byou (?:won['’]?t|will not) believe\b",
            r"\byou['’]?ll never guess\b",
            r"\bfind out later\b",
        )
        if any(re.search(pattern, voiceover, re.IGNORECASE) for pattern in forbidden):
            return False, f"Scene {number} contains retention bait."

        generic = (
            "welcome to",
            "hey everyone",
            "hey guys",
            "in this video",
            "today we are going to",
            "let's talk about",
            "here is the latest",
        )
        if number == 1 and voiceover.casefold().startswith(generic):
            return False, "Scene 1 starts with a generic opener."

    first = scenes[0]
    if _words(first.get("voiceover")) > SCENE_1_MAX_WORDS:
        return False, f"Scene 1 exceeds {SCENE_1_MAX_WORDS} words."

    roles = [str(scene.get("narrative_role") or "").strip().lower() for scene in scenes]
    if roles[0] != "hook":
        return False, "Scene 1 must be the hook."
    if roles[-1] != "consequence":
        return False, "The final scene must be the consequence or payoff."
    if not any(role in {"development", "context"} for role in roles[1:-1]):
        return False, "The middle needs a development or context scene."

    narration = " ".join(_clean(scene.get("voiceover")) for scene in scenes)
    if _copied_sentence(narration, source_text):
        return False, "The narration is too close to source wording."

    # A useful practical guard: 75 spoken words is roughly 30 seconds at 150 WPM.
    if _words(narration) > 75:
        return False, "The narration is likely longer than the 30-second limit."

    description = _clean(result.get("seo_description"))
    if _words(description) < 10:
        return False, "SEO description is too short."

    return True, ""


def _request(model: str, system_prompt: str, story_text: str, timeout: int = TIMEOUT) -> dict:
    api_key = _clean(os.getenv("GROQ_API_KEY"))
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "SELECTED SPORTS STORY:\n" + story_text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sports_shorts_script",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            },
        },
        "include_reasoning": False,
        "reasoning_effort": "low",
        "temperature": 0.5,
        "max_completion_tokens": 900,
    }

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    if isinstance(content, dict):
        return content
    return json.loads(content)


def write_script(story, language: str = "english") -> dict:
    """Generate, validate and return one sports Shorts script."""
    story_text = _story_text(story)
    if not story_text:
        raise ValueError("The selected story contains no usable evidence.")

    language_instruction = LANGUAGE_INSTRUCTIONS.get(
        str(language or "english").strip().lower(),
        LANGUAGE_INSTRUCTIONS["english"],
    )
    system_prompt = _SYSTEM_PROMPT + "\nLANGUAGE:\n" + language_instruction

    last_error = None
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            result = _request(model, system_prompt, story_text)
            valid, reason = _validate(result, story_text)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "HYPE COMMENTATOR"
                result["sport_or_topic_category"] = "Sports"
                result["source_title"] = _clean(
                    getattr(story, "title", "")
                    if hasattr(story, "__dataclass_fields__")
                    else dict(story or {}).get("title")
                )
                result["source_evidence"] = story_text
                return result

            # One repair call on the same model only when the generated draft needs
            # a bounded structural/content correction.
            repair_prompt = (
                _REPAIR_PROMPT
                + "\nLANGUAGE:\n"
                + language_instruction
            )
            repair_input = (
                "SELECTED SPORTS STORY:\n"
                + story_text
                + "\n\nDRAFT TO REPAIR:\n"
                + json.dumps(result, ensure_ascii=False)
            )
            repaired = _request(model, repair_prompt, repair_input)
            repaired_valid, repaired_reason = _validate(repaired, story_text)
            if repaired_valid:
                repaired["provider_used"] = model
                repaired["delivery_profile"] = "HYPE COMMENTATOR"
                repaired["sport_or_topic_category"] = "Sports"
                repaired["repair_applied"] = True
                repaired["source_title"] = _clean(
                    getattr(story, "title", "")
                    if hasattr(story, "__dataclass_fields__")
                    else dict(story or {}).get("title")
                )
                repaired["source_evidence"] = story_text
                return repaired

            last_error = repaired_reason or reason
        except (requests.RequestException, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if model == PRIMARY_MODEL:
                time.sleep(1)
                continue
            raise RuntimeError(f"Script generation failed: {last_error}") from exc

    raise RuntimeError(f"Script generation failed: {last_error or 'no usable response'}")


def apply_script_edits(script: dict, voiceovers: list[str]) -> dict:
    """Return a copy of a generated script with human voiceover edits applied."""
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited scenes does not match the script.")

    original_voiceovers = [
        _clean(scene.get("voiceover"))
        for scene in scenes
        if isinstance(scene, dict)
    ]
    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = _clean(voiceover)

    valid, reason = _validate(result, _clean(result.get("source_evidence")))
    if not valid:
        raise ValueError(f"Edited script failed local validation: {reason}")

    result["human_script_edited"] = original_voiceovers != [
        _clean(scene.get("voiceover"))
        for scene in scenes
        if isinstance(scene, dict)
    ]
    return result
