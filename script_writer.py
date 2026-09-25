"""Function 02: sports Shorts script writing."""

import json
import os
import re
from pathlib import Path
from difflib import SequenceMatcher

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
TIMEOUT = 30
MAX_SOURCE_CHARS = 12000
SCENE_1_MAX_WORDS = 14
MAX_WORDS = 75

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and titles in punchy, natural spoken English.",
    "hindi": "Write all narration and titles in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and titles in natural spoken Telugu using Telugu script.",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}},
        "seo_description": {"type": "string"},
        "pinned_comment": {"type": "string"},
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
            "seo_description",
        "pinned_comment",
        "script",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the original editorial writer for a human-reviewed sports Shorts channel.

Use only the supplied story evidence. Tell the complete important story in fresh wording.
Never invent facts, quotes, motives, numbers, predictions, outcomes or causal claims.
Never copy a complete source sentence.

RULES:
- This is a regular sports Short. Do not write Top-5 or Deep-Dive.
- Write exactly 4 or 5 narration scenes.
- Story arc: factual hook → development/context → consequence or useful closing fact.
- Include the essential event, key people or teams, important supported facts, necessary context and immediate consequence when supported.
- Every scene must add useful new information.
- No filler, generic setup, CTA, retention bait or production instructions.
- Scene 1 is a crisp factual hook: target 10–12 words, hard maximum 14.
- Curiosity must come from a real supported fact, never withheld information.
- Target about 22–27 seconds of natural narration and never exceed 30 seconds.
- Do not pad the script.
- Use natural spoken sentences and spell out numbers, acronyms and symbols where practical for TTS.
- Generate exactly 3 title candidates. They are stored for later title selection.
- Every scene must include a supported primary visual entity, visual intent, specific search prompt and sports category.
- Return only JSON matching the supplied schema.
"""

FORBIDDEN = (
    r"\bwait (?:until|till|for) (?:the )?end\b",
    r"\bwait for it\b",
    r"\bstay tuned\b",
    r"\bdon['’]?t go anywhere\b",
    r"\byou (?:won['’]?t|will not) believe\b",
    r"\byou['’]?ll never guess\b",
    r"\bfind out later\b",
)

GENERIC_OPENERS = (
    "welcome to",
    "hey everyone",
    "hey guys",
    "in this video",
    "today we are going to",
    "let's talk about",
    "here is the latest",
)


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w ]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _source_text(story) -> str:
    if hasattr(story, "__dataclass_fields__"):
        story = {name: getattr(story, name) for name in story.__dataclass_fields__}
    story = dict(story or {})
    for key in ("research_evidence_text", "text", "summary", "description", "title", "topic"):
        value = _clean(story.get(key))
        if value:
            return value[:MAX_SOURCE_CHARS]
    return ""


def _copied(source, narration) -> bool:
    source_sentences = [
        _normalise(x)
        for x in re.split(r"(?<=[.!?])\s+|\n+", source)
        if _words(x) >= 8
    ]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", narration):
        candidate = _normalise(sentence)
        if _words(candidate) < 8:
            continue
        for original in source_sentences:
            if candidate == original or SequenceMatcher(None, candidate, original).ratio() >= 0.92:
                return True
    return False


def validate_script(result: dict, source: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or any(not _clean(x) for x in titles):
        return False, "Exactly three non-empty titles are required."


    scenes = result.get("script")
    if not isinstance(scenes, list) or len(scenes) not in (4, 5):
        return False, "A regular sports Short must contain 4 or 5 scenes."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            return False, f"Scene {number} is malformed."
        voiceover = _clean(scene.get("voiceover"))
        if not voiceover:
            return False, f"Scene {number} is empty."
        if not _clean(scene.get("primary_entity")):
            return False, f"Scene {number} is missing its primary visual entity."
        if not all(_clean(scene.get(key)) for key in (
            "visual_intent",
            "specific_search_prompt",
            "sport_or_topic_category",
        )):
            return False, f"Scene {number} is missing visual metadata."
        if any(re.search(pattern, voiceover, re.IGNORECASE) for pattern in FORBIDDEN):
            return False, f"Scene {number} contains retention bait."
        if number == 1 and voiceover.casefold().startswith(GENERIC_OPENERS):
            return False, "Scene 1 starts with a generic opener."

    roles = [str(scene.get("narrative_role") or "").strip().lower() for scene in scenes]
    if roles[0] != "hook" or roles[-1] != "consequence":
        return False, "The script must begin with a hook and end with a consequence."
    if not any(role in {"development", "context"} for role in roles[1:-1]):
        return False, "The middle needs a development or context scene."

    first_words = _words(scenes[0]["voiceover"])
    if first_words > SCENE_1_MAX_WORDS:
        return False, f"Scene 1 exceeds {SCENE_1_MAX_WORDS} words."

    narration = " ".join(_clean(scene["voiceover"]) for scene in scenes)
    if _words(narration) > MAX_WORDS:
        return False, "The narration is likely longer than 30 seconds."
    if _copied(source, narration):
        return False, "The narration is too close to source wording."

    if _words(result.get("seo_description")) < 10:
        return False, "The SEO description is too short."

    return True, ""


def _request(model: str, prompt: str, story: str) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "SELECTED SPORTS STORY:\n" + story},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "sports_shorts_script",
                    "strict": True,
                    "schema": SCHEMA,
                },
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.5,
            "max_completion_tokens": 900,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def write_script(story, language: str = "english") -> dict:
    """Generate one sports Shorts script and return its later-stage metadata too."""
    source = _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    instruction = (
        SYSTEM_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(
            str(language or "english").strip().lower(),
            LANGUAGE_INSTRUCTIONS["english"],
        )
    )

    errors = []
    for model in MODELS:
        try:
            result = _request(model, instruction, source)
            valid, reason = validate_script(result, source)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "HYPE COMMENTATOR"
                result["language_used"] = str(language or "english").strip().lower()
                result["source_title"] = _clean(
                    getattr(story, "title", "")
                    if hasattr(story, "__dataclass_fields__")
                    else dict(story or {}).get("title")
                )
                result["source_evidence"] = source
                return result
            errors.append(f"{model}: {reason}")
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")

    raise RuntimeError("Script generation failed: " + " | ".join(errors))


def apply_script_edits(script: dict, voiceovers: list[str]) -> dict:
    """Apply optional human narration edits and re-run local script checks."""
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited scenes does not match the script.")

    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = _clean(voiceover)

    valid, reason = validate_script(result, _clean(result.get("source_evidence")))
    if not valid:
        raise ValueError(f"Edited script failed local validation: {reason}")

    result["human_script_edited"] = any(
        _clean(scene["voiceover"]) != _clean(original["voiceover"])
        for scene, original in zip(scenes, script.get("script", []))
    )
    result["approved_for_audio"] = True
    return result
