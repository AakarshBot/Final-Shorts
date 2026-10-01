"""Function 02: Cricket Scriptwriter."""
import json
import os
import re
from html import unescape
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
MAX_SOURCE_CHARS = 24000
CRICKET_RESEARCH_MAX_ARTICLES = 5
CRICKET_RESEARCH_CANDIDATE_LIMIT = 12
CRICKET_RESEARCH_ARTICLE_CHARS = 4200
MIN_ARTICLE_CHARS = 500
HOOK_MAX_SECONDS = 3.0

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and publish metadata in punchy, natural spoken English.",
    "hindi": "Write all narration and publish metadata in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and publish metadata in natural spoken Telugu using Telugu script.",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "titles": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "seo_description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "comment": {"type": "string"},
        "script": {
            "type": "array",
            "minItems": 4,
            "maxItems": 5,
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
    "required": ["headline", "titles", "seo_description", "hashtags", "comment", "script"],
    "additionalProperties": False,
}

CRICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "titles": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "seo_description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
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
    "required": ["headline", "titles", "seo_description", "hashtags", "comment", "script"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the senior cricket editor for a human-reviewed YouTube Shorts channel.

INPUT
The selected headline identifies the story. The evidence packet contains the available reporting, including the selected article and relevant current reporting when research was successful.

PRIMARY OBJECTIVE
Create a four-slide Short that maximizes these two outcomes at the same time:

1. RETENTION
Keep the viewer moving from slide to slide because each sentence creates a useful reason to hear the next sentence.
- Start with the strongest truthful factual entry point immediately.
- Prefer a real tension, contrast, consequence, rivalry, debate, comeback, record, unusual development, human stake or unanswered factual point when the evidence supports it.
- Build forward momentum: each slide should naturally lead into the next piece of information.
- Reward attention with information; never use empty suspense.
- Write for the ear: clean spoken rhythm, concrete verbs, active voice and economical wording.

2. INFORMATIVE
Preserve roughly 90% of the materially important information in the researched story.
- Cover the central development and who/what is involved.
- Preserve material background and context needed to understand the story.
- Preserve important dates, statistics, records, numbers, career facts, decisions and consequences when supported.
- For a profile or explainer, cover the actual person/story promised by the headline rather than repeatedly describing the trigger event.
- Compress information; do not replace important facts with generic excitement.
- Ignore article boilerplate, repetition and low-value wording.

RETENTION + INFORMATION BALANCE
The goal is not to choose between entertainment and information.
Make the factual information itself create the momentum.
When several facts are available, sequence them so the first fact opens the story, the next fact sharpens or changes what the viewer understands, the next adds the most useful context, and the final fact closes the story with its latest confirmed status or consequence.
For a pure news announcement, look for the enduring sporting or human narrative contained in the evidence when one exists. Do not invent a narrative that the source does not support.

FOUR-SLIDE DESIGN
- Exactly four spoken slides.
- Slide 1: strongest factual entry point, with fewer than 14 words.
- Slides 2–4: each must add meaningful new information.
- Use the four slides to compress the complete story, not to restate the headline.
- Every sentence must earn its space by delivering a fact, context, consequence or necessary transition.
- Do not pad a small story to make it sound larger.
- The whole Short must be less than 30 seconds.
- Do not deliberately target a word count. Keep the narration concise enough for a natural sub-30-second Short; the Audio stage is the final timing authority.

SOURCE DISCIPLINE
- Read the complete evidence packet before writing.
- Use only facts supported by the evidence.
- Never invent quotes, motives, predictions, statistics, records, injuries, consequences or background.
- Distinguish confirmed facts from reported claims, expectations and opinions.
- Related current reporting can strengthen context, but only when it is genuinely about the same story.
- One strong source is sufficient when it contains the necessary information.

EDITORIAL VOICE
Sound like a sharp cricket desk editor, not an article being read aloud.
Energy should come from the facts and their sequence, not from generic hype.
Do not use viewer-directed bait such as "wait until the end", "stay tuned", "don't scroll" or "you won't believe".
Do not begin with a generic introduction.
Do not manufacture outrage, rivalry or suspense.

INTERNAL SELF-QC BEFORE RETURNING JSON
Silently draft the story, then inspect it before returning the answer:
- Can a viewer understand what happened without seeing the article?
- Does Slide 1 immediately provide a strong, specific reason to listen?
- Does every slide add new information?
- Are the four slides carrying the materially important facts rather than filler?
- Is roughly 90% of the important story substance represented?
- Did any sentence repeat the headline or another slide without adding information?
- Is every factual claim supported by the evidence?
- Does the final slide close the story with the latest confirmed status or consequence when one exists?
Revise the draft internally until it is the strongest compact version you can make.

PUBLISH METADATA
Return:
- one factual 3–4 word opening headline;
- exactly three concise title candidates;
- one concise story-specific SEO description;
- relevant hashtags;
- one story-specific public-upload comment.

VISUAL HANDOFF
Each slide must include accurate visual metadata for the narrated fact:
- primary_entity;
- visual_intent;
- specific_search_prompt;
- sport_or_topic_category.
Do not invent a visual moment that the evidence does not support.

LANGUAGE
Write the narration and publish metadata in the requested language.

Return only JSON matching the supplied schema.
"""

def _clean(value) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w ]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _story_value(story, key: str) -> str:
    if hasattr(story, "__dataclass_fields__"):
        return _clean(getattr(story, key, ""))
    return _clean(dict(story or {}).get(key))


def _source_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def _limit_source_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> str:
    clean = "\n".join(_clean(line) for line in str(text or "").splitlines() if _clean(line))
    if len(clean) <= max_chars:
        return clean
    head = int(max_chars * 0.55)
    middle = int(max_chars * 0.2)
    tail = max_chars - head - middle
    start = max(0, (len(clean) - middle) // 2)
    return clean[:head].rstrip() + "\n\n[ARTICLE MIDDLE]\n\n" + clean[start:start + middle].strip() + "\n\n[ARTICLE END]\n\n" + clean[-tail:].lstrip()


def _article_body_from_html(html_text: str) -> str:
    raw = str(html_text or "")
    sections = []

    for match in re.finditer(
        r"<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(unescape(match.group(1).strip()))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                body = _clean(item.get("articleBody"))
                if body and body not in sections:
                    sections.append(body)
                stack.extend(value for value in item.values() if isinstance(value, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)

    for tag in ("h1", "h2", "h3", "p"):
        for value in re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", raw, flags=re.IGNORECASE | re.DOTALL):
            cleaned = _clean(re.sub(r"<[^>]+>", " ", unescape(value)))
            if cleaned and cleaned not in sections:
                sections.append(cleaned)

    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, flags=re.IGNORECASE | re.DOTALL):
            cells = [
                _clean(re.sub(r"<[^>]+>", " ", unescape(cell)))
                for cell in re.findall(r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", row, flags=re.IGNORECASE | re.DOTALL)
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                row_text = " | ".join(cells)
                if row_text not in sections:
                    sections.append(row_text)

    return "\n".join(sections)


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

    extracted = _clean(
        trafilatura.extract(
            response.text,
            url=resolved_url,
            favor_recall=True,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
    )
    structured = _clean(_article_body_from_html(response.text))
    if extracted and structured:
        base = _normalise(extracted)
        extra = [line for line in structured.splitlines() if _clean(line) and _normalise(line) not in base]
        enriched = extracted + ("\n\n[STRUCTURED SOURCE FACTS]\n" + "\n".join(extra) if extra else "")
        if len(enriched) >= MIN_ARTICLE_CHARS:
            return enriched, resolved_url

    for candidate in (extracted, structured):
        if len(candidate) >= MIN_ARTICLE_CHARS:
            return candidate, resolved_url

    try:
        fallback = DDGS(timeout=5).extract(resolved_url, fmt="text_plain")
        content = _clean(fallback.get("content") if isinstance(fallback, dict) else "")
        if len(content) >= MIN_ARTICLE_CHARS:
            return content, str(fallback.get("url") or resolved_url)
    except Exception:
        pass
    return "", resolved_url


def _related_article_urls(title: str, description: str, original_url: str) -> list[tuple[str, str]]:
    queries = [
        title,
        f"{title} latest",
        f"{title} background statistics career record",
        f"{title} reaction statement",
        f"{title} latest cricket news",
    ]
    original = _normalise(original_url.rstrip("/"))
    seen = {original}
    candidates = []

    for query in queries:
        try:
            results = DDGS(timeout=5).news(
                query=_clean(query),
                region="in-en",
                safesearch="off",
                timelimit="w",
                max_results=8,
            ) or []
        except Exception:
            continue

        for result in results:
            url = _clean(result.get("url") or result.get("href"))
            result_title = _clean(result.get("title"))
            if not url or not result_title:
                continue
            canonical = _normalise(url.rstrip("/"))
            if canonical in seen:
                continue
            domain = _source_domain(url)
            if not domain or any(blocked in domain for blocked in ("twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google.")):
                continue
            query_tokens = set(re.findall(r"\b[\w]+\b", _clean(title).casefold()))
            result_tokens = set(re.findall(r"\b[\w]+\b", result_title.casefold()))
            score = len(query_tokens & result_tokens)
            if domain == _source_domain(original_url):
                score += 0.25
            candidates.append((score, result_title, url))
            seen.add(canonical)

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [(result_title, url) for _, result_title, url in candidates[:CRICKET_RESEARCH_CANDIDATE_LIMIT]]


def _research_story(story, profile: str | None = None) -> str:
    title = _story_value(story, "title")
    description = _story_value(story, "description")
    original_url = _story_value(story, "url")
    sections = []
    if title:
        sections.append(f"[SELECTED STORY]\n{title}")
    if description:
        sections.append(f"[TOPIC FETCHER SUMMARY]\n{description}")

    if original_url:
        try:
            primary, resolved = _extract_article(original_url)
        except (requests.RequestException, OSError, ValueError):
            primary, resolved = "", original_url
        if primary:
            sections.append("[PRIMARY ARTICLE — " + (resolved or original_url) + "]\n" + _limit_source_text(primary, 9000))

        for number, (related_title, related_url) in enumerate(
            _related_article_urls(title, description, original_url)[:CRICKET_RESEARCH_MAX_ARTICLES], 1
        ):
            try:
                article, resolved_url = _extract_article(related_url)
            except (requests.RequestException, OSError, ValueError):
                continue
            if article:
                sections.append(
                    f"[RELATED CURRENT REPORT {number} — {related_title} — {resolved_url or related_url}]\n"
                    + _limit_source_text(article, CRICKET_RESEARCH_ARTICLE_CHARS)
                )

    return _limit_source_text("\n\n".join(sections), MAX_SOURCE_CHARS)


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
                {"role": "user", "content": "SELECTED SPORTS STORY:\n" + story},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sports_shorts_script", "strict": True, "schema": schema or SCHEMA},
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.45,
            "max_completion_tokens": 1000,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


REWRITE_INSTRUCTION = """MANUAL-QC REWRITE

The human reviewer asked for a full rewrite of the selected story.

Rewrite from scratch. Start again from the complete evidence packet. Do not preserve the previous draft's wording or structure. Rebuild all four slides around the strongest truthful narrative while maximizing retention and informative value together.

Make sure every slide carries materially useful information, the story remains faithful to the evidence, and the result is concise enough for a sub-30-second Short.

PREVIOUS DRAFT
Use this only to identify what the human rejected or what can be improved. It is not the source of truth.
"""


GENERIC_OPENERS = (
    "welcome to",
    "hey everyone",
    "hey guys",
    "in this video",
    "today we are going to",
    "let's talk about",
    "here is the latest",
)
RETENTION_BAIT = (
    "wait until the end",
    "wait till the end",
    "watch till the end",
    "keep watching",
    "stay tuned",
    "don't skip",
    "don't scroll",
    "find out later",
)


def validate_script(result: dict, source: str) -> tuple[bool, str]:
    # Compatibility validator retained for the separately implemented Niche writer.
    if not isinstance(result, dict):
        return False, "The provider returned no script object."
    scenes = result.get("script")
    if not isinstance(scenes, list) or not scenes:
        return False, "The provider did not return a script."
    first = _clean(scenes[0].get("voiceover")).casefold()
    if any(first.startswith(opener) for opener in GENERIC_OPENERS):
        return False, "Scene 1 starts with a generic opener."
    if any(phrase in " ".join(_clean(scene.get("voiceover")).casefold() for scene in scenes) for phrase in RETENTION_BAIT):
        return False, "The narration contains retention bait."
    return True, ""


def validate_cricket_script(result: dict, source: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list) or len(scenes) != 4:
        return False, "Cricket Scriptwriter must return exactly 4 slides."

    first = scenes[0] if scenes else {}
    if _words(first.get("voiceover")) >= 14:
        return False, "Slide 1 must contain fewer than 14 words."

    headline_words = _words(result.get("headline"))
    if headline_words < 3 or headline_words > 4:
        return False, "The opening headline must contain 3 or 4 words."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or not all(_clean(item) for item in titles):
        return False, "The Scriptwriter must produce exactly 3 titles."

    if not _clean(result.get("seo_description")):
        return False, "The Scriptwriter must produce a description."

    hashtags = result.get("hashtags")
    if not isinstance(hashtags, list) or not hashtags or not all(_clean(item) for item in hashtags):
        return False, "The Scriptwriter must produce hashtags."

    if not _clean(result.get("comment")):
        return False, "The Scriptwriter must produce the upload comment."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not _clean(scene.get("voiceover")):
            return False, f"Slide {number} is empty or malformed."
        if not all(
            _clean(scene.get(key))
            for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category")
        ):
            return False, f"Slide {number} is missing visual metadata."

    return True, ""


def _finish_result(result: dict, story, source: str, model: str, language_key: str) -> dict:
    result["provider_used"] = model
    result["language_used"] = language_key
    result["word_count"] = _words(
        " ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or [])
    )
    result["source_title"] = _story_value(story, "title")
    result["source_evidence"] = source
    return result


def write_script(
    story,
    language: str = "english",
    forceful: bool = False,
    previous_script: dict | None = None,
) -> dict:
    source = _research_story(story, profile="cricket") or _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    instruction = (
        SYSTEM_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )

    if forceful:
        instruction += "\n\n" + REWRITE_INSTRUCTION
        if previous_script:
            instruction += "\n" + json.dumps(previous_script, ensure_ascii=False)

    errors = []
    for model in MODELS:
        try:
            result = _request(
                model,
                instruction,
                source,
                schema=CRICKET_SCHEMA,
            )
            valid, reason = validate_cricket_script(result, source)
            if valid:
                return _finish_result(
                    result,
                    story,
                    source,
                    model,
                    language_key,
                )

            errors.append(f"{model}: {reason}")
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")

    raise RuntimeError("Script generation failed: " + " | ".join(errors))


def apply_script_edits(
    script: dict,
    voiceovers: list[str],
    headline: str | None = None,
    *,
    validate: bool = True,
) -> dict:
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
        _clean(scene["voiceover"]) != _clean(original.get("voiceover"))
        for scene, original in zip(scenes, script.get("script", []))
    )
    result["approved_for_audio"] = True
    return result
