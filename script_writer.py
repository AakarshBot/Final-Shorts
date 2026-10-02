"""Function 02: Cricket Scriptwriter."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
import trafilatura
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
TIMEOUT = 30
RESEARCH_TIMEOUT = 10
MIN_ARTICLE_CHARS = 500
MAX_SOURCE_CHARS = 28000
MAX_RELATED_ARTICLES = 2
MAX_SLIDE_ONE_WORDS = 13
MAX_SCRIPT_SECONDS = 32.0
WORDS_PER_SECOND = 2.5
HOOK_MAX_SECONDS = 3.0  # Shared by the separately implemented Niche Sports writer.

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and publish metadata in punchy, natural spoken English.",
    "hindi": "Write all narration and publish metadata in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and publish metadata in natural spoken Telugu using Telugu script.",
}

CRICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "subject_name": {"type": "string"},
        "headline": {"type": "string"},
        "titles": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "seo_description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
        "comment": {"type": "string"},
        "script": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "voiceover": {"type": "string"},
                    "narrative_role": {"type": "string"},
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
        "subject_name",
        "headline",
        "titles",
        "seo_description",
        "hashtags",
        "comment",
        "script",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the senior cricket editor for a human-reviewed YouTube Shorts channel.

JOB
Turn the supplied researched cricket story into one complete four-slide spoken Short.

SOURCE USE
- Read the entire research packet before writing.
- Treat the selected article as the primary source and use the related reports to fill factual gaps, add current context, or confirm important details.
- When the selected article is thin, use the related reports to recover the missing factual information.
- Use only facts supported by the research packet.
- Do not invent quotes, scores, statistics, dates, records, injuries, motives, predictions, career facts or consequences.
- Preserve reported claims as reported claims.

INFORMATION
Compress the article's material factual information into four slides.
Keep the facts a viewer actually needs: who it is about, what happened, when and where relevant, important scores/numbers/records, material background, and the latest confirmed consequence or status.
Remove only repetition, boilerplate and low-value wording.
Do not replace facts with generic hype.

NAMING THE SUBJECT
- Identify the exact main player/person/team in `subject_name`.
- The exact `subject_name` must appear in the spoken narration.
- Never describe the main player only as "the 35-year-old", "the player", "the batter", "the bowler", "the captain", or with a pronoun when the exact name is available.
- For a story about a specific player, name that player in the first two slides whenever the evidence supports the name.

FOUR SLIDES
- Return exactly four spoken slides.
- Slide 1 is the hook: the strongest specific fact from the story.
- Slide 1 MUST contain 13 words or fewer. This is a generation rule, not a post-generation target.
- The complete four-slide narration MUST be 32 seconds or less at roughly 150 spoken words per minute. This is a generation rule, not a post-generation target.
- Draft, count and rewrite internally before returning JSON if either limit is exceeded.
- Slides 2–4 must add new information and should carry the important remaining facts.
- Do not pad the script to hit a word count.

STYLE
- Sharp, energetic cricket desk voice.
- Write for the ear: short clean sentences, active voice, concrete wording.
- Let the facts create the momentum.
- No generic introductions, CTA, viewer commands, fake suspense or empty hype.
- No article-reading tone.

METADATA
- `headline`: exactly 3 or 4 words.
- `titles`: exactly 3 concise title candidates.
- `seo_description`: concise and story-specific.
- `hashtags`: 3–5 relevant hashtags.
- `comment`: one concise discussion-oriented comment grounded in the story.

VISUAL HANDOFF
Every slide must include useful metadata matching the narrated fact:
- primary_entity
- visual_intent
- specific_search_prompt
- sport_or_topic_category

FINAL SELF-CHECK
Before returning JSON, silently verify:
1. Exactly four slides.
2. Slide 1 is 13 words or fewer.
3. Total narration is 32 seconds or less at 150 wpm.
4. The main subject is named in the narration.
5. All important factual information is compressed into the four slides.
6. No unsupported claim has been added.
7. The metadata is complete.

Return only JSON matching the supplied schema.
"""


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _story_value(story, key: str) -> str:
    if hasattr(story, "__dataclass_fields__") or hasattr(story, key):
        return _clean(getattr(story, key, ""))
    return _clean(dict(story or {}).get(key))


def _source_text(story) -> str:
    if hasattr(story, "__dataclass_fields__"):
        story = {name: getattr(story, name) for name in story.__dataclass_fields__}
    story = dict(story or {})
    parts = []
    for key in ("title", "research_evidence_text", "text", "summary", "description", "topic"):
        value = _clean(story.get(key))
        if value and value not in parts:
            parts.append(value)
    return "\n\n".join(parts)[:MAX_SOURCE_CHARS]


def _source_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def _extract_article(url: str) -> tuple[str, str]:
    target = _clean(url)
    if not target:
        return "", ""

    response = requests.get(
        target,
        headers={
            "User-Agent": "Mozilla/5.0 Final-Shorts/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        },
        timeout=RESEARCH_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    resolved_url = str(response.url or target)
    article = _clean(
        trafilatura.extract(
            response.text,
            url=resolved_url,
            favor_recall=True,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
    )
    if len(article) >= MIN_ARTICLE_CHARS:
        return article, resolved_url

    try:
        fallback = DDGS(timeout=5).extract(resolved_url, fmt="text_plain")
        content = _clean(fallback.get("content") if isinstance(fallback, dict) else "")
        if len(content) >= MIN_ARTICLE_CHARS:
            return content, str(fallback.get("url") or resolved_url)
    except Exception:
        pass

    return "", resolved_url


def _related_article_urls(title: str, original_url: str) -> list[tuple[str, str]]:
    if not title:
        return []

    try:
        results = DDGS(timeout=5).news(
            query=title,
            region="in-en",
            safesearch="off",
            timelimit="w",
            max_results=8,
        ) or []
    except Exception:
        return []

    original = _normalise(original_url.rstrip("/"))
    title_words = set(re.findall(r"\b[\w]+\b", title.casefold()))
    scored = []
    seen = {original}
    for result in results:
        url = _clean(result.get("url") or result.get("href"))
        result_title = _clean(result.get("title"))
        if not url or not result_title:
            continue
        canonical = _normalise(url.rstrip("/"))
        if not canonical or canonical in seen:
            continue
        domain = _source_domain(url)
        if not domain or any(blocked in domain for blocked in ("twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google.")):
            continue
        result_words = set(re.findall(r"\b[\w]+\b", result_title.casefold()))
        overlap = len(title_words & result_words)
        if overlap < 2:
            continue
        score = overlap + (0.5 if domain == _source_domain(original_url) else 0)
        scored.append((score, result_title, url))
        seen.add(canonical)

    scored.sort(reverse=True)
    return [(item[1], item[2]) for item in scored[:MAX_RELATED_ARTICLES]]


def _research_story(story) -> str:
    title = _story_value(story, "title")
    description = _story_value(story, "description")
    original_url = _story_value(story, "url")
    sections = []

    if title:
        sections.append(f"[SELECTED STORY]\n{title}")
    if description:
        sections.append(f"[TOPIC SUMMARY]\n{description}")

    primary = ""
    resolved = original_url
    if original_url:
        try:
            primary, resolved = _extract_article(original_url)
        except (requests.RequestException, OSError, ValueError):
            primary = ""
        if primary:
            sections.append(f"[PRIMARY ARTICLE — {resolved or original_url}]\n{primary[:10000]}")

    for number, (related_title, related_url) in enumerate(_related_article_urls(title, original_url), 1):
        try:
            article, resolved_url = _extract_article(related_url)
        except (requests.RequestException, OSError, ValueError):
            continue
        if article:
            sections.append(
                f"[RELATED REPORT {number} — {related_title} — {resolved_url or related_url}]\n"
                + article[:7000]
            )

    return "\n\n".join(sections)[:MAX_SOURCE_CHARS]


def _request(model: str, prompt: str, story: str, schema: dict | None = None) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "RESEARCH PACKET:\n" + story},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cricket_shorts_script",
                    "strict": True,
                    "schema": schema or CRICKET_SCHEMA,
                },
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.35,
            "max_completion_tokens": 1800,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def _estimated_seconds(result: dict) -> float:
    narration = " ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or [])
    return _words(narration) / WORDS_PER_SECOND


def validate_script(result: dict, source: str) -> tuple[bool, str]:
    """Minimal shared validator used by the separately implemented Niche Sports writer."""
    if not isinstance(result, dict):
        return False, "The provider returned no script object."
    scenes = result.get("script")
    if not isinstance(scenes, list) or not scenes:
        return False, "The provider did not return a script."
    for scene in scenes:
        if not isinstance(scene, dict) or not _clean(scene.get("voiceover")):
            return False, "The provider returned an empty scene."
    return True, ""


def validate_cricket_script(result: dict, source: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list) or len(scenes) != 4:
        return False, "Cricket Scriptwriter must return exactly 4 slides."

    subject = _clean(result.get("subject_name"))
    if not subject:
        return False, "The Scriptwriter must identify the main subject."

    first_words = _words((scenes[0] or {}).get("voiceover")) if isinstance(scenes[0], dict) else 0
    if first_words > MAX_SLIDE_ONE_WORDS:
        return False, "Slide 1 must contain fewer than 14 words."

    total_seconds = _estimated_seconds(result)
    if total_seconds > MAX_SCRIPT_SECONDS:
        return False, f"The script exceeds 32 seconds ({total_seconds:.1f}s estimated)."

    narration = _normalise(" ".join(_clean(scene.get("voiceover")) for scene in scenes))
    subject_normalised = _normalise(subject)
    if subject_normalised and subject_normalised not in narration:
        return False, "The main subject is not named in the spoken narration."

    headline_words = _words(result.get("headline"))
    if headline_words < 3 or headline_words > 4:
        return False, "The opening headline must contain 3 or 4 words."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or not all(_clean(item) for item in titles):
        return False, "The Scriptwriter must produce exactly 3 titles."

    if not _clean(result.get("seo_description")):
        return False, "The Scriptwriter must produce a description."

    hashtags = result.get("hashtags")
    if not isinstance(hashtags, list) or not 3 <= len(hashtags) <= 5 or not all(_clean(item).startswith("#") for item in hashtags):
        return False, "The Scriptwriter must produce 3–5 hashtags."

    if not _clean(result.get("comment")):
        return False, "The Scriptwriter must produce the upload comment."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not _clean(scene.get("voiceover")):
            return False, f"Slide {number} is empty or malformed."
        for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category"):
            if not _clean(scene.get(key)):
                return False, f"Slide {number} is missing {key}."

    return True, ""


def _finish_result(result: dict, story, source: str, model: str, language_key: str) -> dict:
    result["provider_used"] = model
    result["language_used"] = language_key
    result["word_count"] = _words(" ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or []))
    result["estimated_seconds"] = round(_estimated_seconds(result), 2)
    result["source_title"] = _story_value(story, "title")
    result["source_evidence"] = source
    return result


def write_script(story, language: str = "english") -> dict:
    source = _research_story(story) or _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    instruction = SYSTEM_PROMPT + "\nLANGUAGE:\n" + LANGUAGE_INSTRUCTIONS.get(
        language_key, LANGUAGE_INSTRUCTIONS["english"]
    )

    try:
        result = _request(MODELS[0], instruction, source, schema=CRICKET_SCHEMA)
    except Exception as first_error:
        result = None
        first_reason = f"{type(first_error).__name__}: {first_error}"
    else:
        valid, reason = validate_cricket_script(result, source)
        if valid:
            return _finish_result(result, story, source, MODELS[0], language_key)
        first_reason = reason

    rewrite_instruction = (
        instruction
        + "\n\nHIDDEN REWRITE\n"
        "The first draft is NOT being shown to the human reviewer. Rewrite the complete four-slide script now. "
        "Keep every important factual detail from the research packet, but fix the exact failure below. "
        "Do not explain the rewrite. Return only the complete JSON package.\n"
        f"Failure to fix: {first_reason}\n"
    )

    try:
        rewritten = _request(MODELS[1], rewrite_instruction, source, schema=CRICKET_SCHEMA)
    except Exception as second_error:
        raise RuntimeError(
            "Script generation failed after one hidden rewrite: "
            + f"{first_reason} | {type(second_error).__name__}: {second_error}"
        ) from second_error

    valid, reason = validate_cricket_script(rewritten, source)
    if not valid:
        raise RuntimeError("Script generation failed after one hidden rewrite: " + reason)

    return _finish_result(rewritten, story, source, MODELS[1], language_key)


def apply_script_edits(script: dict, voiceovers: list[str], headline: str | None = None, *, validate: bool = True) -> dict:
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited slides does not match the generated script.")
    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = _clean(voiceover)
    if headline is not None:
        result["headline"] = _clean(headline)
    if validate:
        valid, reason = validate_cricket_script(result, _clean(result.get("source_evidence")))
        if not valid:
            raise ValueError(f"Edited script failed local validation: {reason}")
    result["human_script_edited"] = any(
        _clean(scene.get("voiceover")) != _clean(original.get("voiceover"))
        for scene, original in zip(scenes, script.get("script", []))
    )
    result["approved_for_audio"] = True
    return result
