"""Function 02: Cricket Scriptwriter.

The writer researches the selected story, builds an AI coverage brief, then
writes one four-slide Short. Manual QC can force a fresh rewrite using the
same full evidence and coverage brief.
"""

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
MAX_SOURCE_CHARS = 18000
CRICKET_RESEARCH_MAX_ARTICLES = 5
CRICKET_RESEARCH_CANDIDATE_LIMIT = 10
CRICKET_RESEARCH_ARTICLE_CHARS = 4200
CRICKET_RESEARCH_MAX_PACKET_CHARS = 24000
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

COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "story_core": {"type": "string"},
        "must_cover_facts": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 6,
            "maxItems": 12,
        },
        "related_current_facts": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
            "maxItems": 8,
        },
        "four_slide_plan": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "slide": {"type": "integer"},
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 6,
                    },
                },
                "required": ["slide", "facts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["story_core", "must_cover_facts", "related_current_facts", "four_slide_plan"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the senior human cricket editor for a human-reviewed YouTube Shorts channel.

The selected headline is the assignment. Your job is to compress the important substance of the researched story into exactly four spoken slides.

NON-NEGOTIABLE EDITORIAL RULES
- Slide 1 must contain fewer than 14 words.
- The finished Short must be designed for less than 30 seconds. A slightly long draft can be tightened by the existing Audio stage, but do not deliberately write long narration.
- Every slide must contain important information. No filler slide, scene-padding, generic setup or repeated headline.
- The four slides should cover roughly 90% of the materially important information in the researched story, prioritising facts a viewer actually needs rather than trying to repeat article prose.
- Do not invent a story, facts, numbers, quotes, motives, causes, outcomes, records or context.
- Do not merely prolong the headline. The article and related current evidence are the story.
- Use the coverage brief as the factual checklist, then use the full evidence packet to recover any material fact the brief missed.
- Related current reporting may add important facts that are not in the selected article. Use it when supported and clearly part of the same story.
- A single source is acceptable. Source count is irrelevant; factual completeness is what matters.
- Return complete natural spoken sentences. Do not clip sentences solely to hit a slide count.

RESEARCH PRIORITY
1. Cover the strongest current development.
2. Cover the facts explicitly promised by the headline.
3. Cover the important background, numbers, dates, records, career details or context that explain the development.
4. Cover the latest related development or confirmed consequence when it materially belongs to the same story.
5. When facts conflict, use the most clearly supported current fact and avoid inventing a resolution.

SLIDE DESIGN
- Slide 1: the strongest factual entry point, fewer than 14 words.
- Slides 2–4: continue the story with new, important information.
- Across all four slides, use the coverage brief's must-cover facts and slide plan.
- Do not sacrifice important facts merely to make the prose sound dramatic.
- Do not manufacture a conclusion when the evidence does not support one.

STYLE
- Energetic sports-desk voice, but the facts provide the energy.
- Write for the ear, not as an article being read aloud.
- Specific names, teams, competitions, dates and numbers are preferred when supported.
- No clickbait, retention bait, generic hype or audience commands.

PUBLISH METADATA
- Generate the existing three title candidates, a story-specific description, relevant hashtags and the existing upload comment.
- Metadata must be grounded in the researched story.

VISUAL HANDOFF
Every slide must contain useful visual metadata matching the actual fact being narrated.

FINAL SELF-CHECK
Before returning JSON, silently confirm:
- Slide 1 is fewer than 14 words.
- There are exactly four slides.
- Every slide contains important information.
- The four slides collectively cover the coverage brief and roughly 90% of the material story information.
- Nothing has been invented.
- The narration is naturally concise enough for a sub-30-second Short.
Return only JSON matching the supplied schema.
"""

FORCEFUL_INSTRUCTION = """
REWRITE MODE — COVERAGE FIRST

This is a forceful Manual-QC rewrite. Do not preserve the previous wording just because it already exists.

Re-read the entire evidence packet and the coverage brief. Identify anything important that the prior draft left out, especially concrete facts, dates, statistics, records, career background, named people, decisions and current developments.

Rewrite all four slides from scratch so that the four slides cover roughly 90% of the materially important information in the story. Every slide must carry substantial information. Remove any sentence that only restates the headline or creates empty drama.

Still obey the two runtime constraints: Slide 1 has fewer than 14 words, and the whole Short should be naturally concise enough to fit under 30 seconds with the existing Audio speed correction available.
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
    clean = "\n".join(
        _clean(line) for line in str(text or "").splitlines() if _clean(line)
    )
    if len(clean) <= max_chars:
        return clean
    head = int(max_chars * 0.55)
    middle = int(max_chars * 0.2)
    tail = max_chars - head - middle
    middle_start = max(0, (len(clean) - middle) // 2)
    return (
        clean[:head].rstrip()
        + "\n\n[ARTICLE MIDDLE]\n\n"
        + clean[middle_start:middle_start + middle].strip()
        + "\n\n[ARTICLE END]\n\n"
        + clean[-tail:].lstrip()
    )


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
        for match in re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", raw, flags=re.IGNORECASE | re.DOTALL):
            value = _clean(re.sub(r"<[^>]+>", " ", unescape(match)))
            if value and value not in sections:
                sections.append(value)

    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, flags=re.IGNORECASE | re.DOTALL):
            cells = [
                _clean(re.sub(r"<[^>]+>", " ", unescape(cell)))
                for cell in re.findall(r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", row, flags=re.IGNORECASE | re.DOTALL)
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                value = " | ".join(cells)
                if value not in sections:
                    sections.append(value)

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

    trafilatura_text = _clean(
        trafilatura.extract(
            response.text,
            url=resolved_url,
            favor_recall=True,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
    )
    structured_text = _clean(_article_body_from_html(response.text))

    if trafilatura_text and structured_text:
        primary_normalised = _normalise(trafilatura_text)
        extra = [
            line for line in structured_text.splitlines()
            if _clean(line) and _normalise(line) not in primary_normalised
        ]
        enriched = trafilatura_text
        if extra:
            enriched += "\n\n[STRUCTURED SOURCE FACTS]\n" + "\n".join(extra)
        if len(enriched) >= MIN_ARTICLE_CHARS:
            return enriched, resolved_url

    for candidate in (trafilatura_text, structured_text):
        if len(candidate) >= MIN_ARTICLE_CHARS:
            return candidate, resolved_url

    try:
        extracted = DDGS(timeout=5).extract(resolved_url, fmt="text_plain")
        content = _clean(extracted.get("content") if isinstance(extracted, dict) else "")
        if len(content) >= MIN_ARTICLE_CHARS:
            return content, str(extracted.get("url") or resolved_url)
    except Exception:
        pass

    return "", resolved_url


def _related_article_urls(title: str, description: str, original_url: str) -> list[tuple[str, str]]:
    queries = [
        title,
        f"{title} latest",
        f"{title} statistics career record background",
        f"{title} reaction statement",
    ]
    candidates = []
    seen_urls = {_source_domain(original_url) + _normalise(original_url)}
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
            if canonical in seen_urls:
                continue
            domain = _source_domain(url)
            if not domain or any(blocked in domain for blocked in ("twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google.")):
                continue
            score = 0
            title_tokens = set(re.findall(r"\b[\w]+\b", _clean(title).casefold()))
            result_tokens = set(re.findall(r"\b[\w]+\b", result_title.casefold()))
            score += len(title_tokens & result_tokens)
            if domain == _source_domain(original_url):
                score += 0.25
            candidates.append((score, result_title, url))
            seen_urls.add(canonical)

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [(title, url) for _, title, url in candidates[:CRICKET_RESEARCH_CANDIDATE_LIMIT]]


def _research_story(story, profile: str | None = None) -> str:
    title = _story_value(story, "title")
    description = _story_value(story, "description")
    original_url = _story_value(story, "url")
    sections = [f"[SELECTED STORY]\n{title}"] if title else []

    if description:
        sections.append(f"[TOPIC FETCHER SUMMARY]\n{description}")

    if original_url:
        try:
            primary, resolved = _extract_article(original_url)
        except (requests.RequestException, OSError, ValueError):
            primary, resolved = "", original_url
        if primary:
            sections.append(
                f"[PRIMARY ARTICLE — {resolved or original_url}]\n"
                + _limit_source_text(primary, 9000)
            )

        for number, (candidate_title, candidate_url) in enumerate(
            _related_article_urls(title, description, original_url)[:CRICKET_RESEARCH_MAX_ARTICLES],
            1,
        ):
            try:
                text, resolved_url = _extract_article(candidate_url)
            except (requests.RequestException, OSError, ValueError):
                continue
            if text:
                sections.append(
                    f"[RELATED CURRENT REPORT {number} — {candidate_title} — {resolved_url or candidate_url}]\n"
                    + _limit_source_text(text, CRICKET_RESEARCH_ARTICLE_CHARS)
                )

    return _limit_source_text("\n\n".join(sections), CRICKET_RESEARCH_MAX_PACKET_CHARS)


def _source_text(story) -> str:
    if hasattr(story, "__dataclass_fields__"):
        story = {name: getattr(story, name) for name in story.__dataclass_fields__}
    story = dict(story or {})
    values = []
    for key in ("title", "research_evidence_text", "text", "summary", "description", "topic"):
        value = _clean(story.get(key))
        if value and value not in values:
            values.append(value)
    return "\n\n".join(values)[:MAX_SOURCE_CHARS]


def _request(model: str, prompt: str, story: str) -> dict:
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
                "json_schema": {
                    "name": "sports_shorts_script",
                    "strict": True,
                    "schema": SCHEMA,
                },
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


def _request_coverage(model: str, source: str) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are the fact-coverage editor for a human sports newsroom.

Read the ENTIRE supplied evidence packet. Do not write narration. Build a coverage brief for another editor.

Identify the central story and the important facts a four-slide Short must cover. Select 6–12 must-cover facts that together represent roughly 90% of the materially important story information, collapsing repeated reporting into one fact. Include important numbers, dates, records, career details, named people, decisions, current developments and consequences when supported.

Also identify related current facts from the evidence that belong to the same story and map the important facts across exactly four slides.

Never invent facts. Do not optimise for drama. Optimise for factual completeness.""",
                },
                {"role": "user", "content": source},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "sports_story_coverage",
                    "strict": True,
                    "schema": COVERAGE_SCHEMA,
                },
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.2,
            "max_completion_tokens": 1200,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def validate_script(result: dict, source: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list):
        return False, "The provider did not return a script."

    if not scenes:
        return False, "The script is empty."

    first_words = _words(scenes[0].get("voiceover"))
    if first_words >= 14:
        return False, "Slide 1 must contain fewer than 14 words."

    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            return False, f"Slide {index} is malformed."
        if not _clean(scene.get("voiceover")):
            return False, f"Slide {index} is empty."
        if not _clean(scene.get("primary_entity")):
            return False, f"Slide {index} is missing its visual entity."
        if not all(
            _clean(scene.get(key))
            for key in ("visual_intent", "specific_search_prompt", "sport_or_topic_category")
        ):
            return False, f"Slide {index} is missing visual metadata."

    if not isinstance(result.get("titles"), list) or not all(_clean(x) for x in result["titles"]):
        return False, "The Scriptwriter must produce title candidates."
    if not _clean(result.get("seo_description")):
        return False, "The Scriptwriter must produce a description."
    if not isinstance(result.get("hashtags"), list) or not any(_clean(x) for x in result["hashtags"]):
        return False, "The Scriptwriter must produce hashtags."

    return True, ""


def _fallback_coverage(source: str) -> dict:
    sentences = [
        _clean(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", source)
        if _words(part) >= 6
    ]
    facts = sentences[:8]
    return {
        "story_core": facts[0] if facts else "",
        "must_cover_facts": facts,
        "related_current_facts": [],
        "four_slide_plan": [
            {"slide": 1, "facts": facts[:2] or ["Identify the story."]},
            {"slide": 2, "facts": facts[2:4] or facts[:1] or ["State the key facts."]},
            {"slide": 3, "facts": facts[4:6] or facts[1:2] or ["Add the strongest context."]},
            {"slide": 4, "facts": facts[6:8] or facts[2:3] or ["Close with the latest supported status."]},
        ],
    }


def write_script(story, language: str = "english", forceful: bool = False) -> dict:
    """Research and write one complete four-slide Cricket Short."""
    source = _research_story(story, profile="cricket")
    if not source:
        source = _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    coverage = None
    coverage_errors = []
    for model in MODELS:
        try:
            coverage = _request_coverage(model, source)
            break
        except Exception as exc:
            coverage_errors.append(f"{model}: {type(exc).__name__}: {exc}")

    if not isinstance(coverage, dict):
        coverage = _fallback_coverage(source)

    instruction = (
        SYSTEM_PROMPT
        + "\n\nCOVERAGE BRIEF:\n"
        + json.dumps(coverage, ensure_ascii=False)
        + "\n\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(
            str(language or "english").strip().lower(),
            LANGUAGE_INSTRUCTIONS["english"],
        )
    )
    if forceful:
        instruction += FORCEFUL_INSTRUCTION

    errors = []
    for model in MODELS:
        try:
            result = _request(model, instruction, source)
            valid, reason = validate_script(result, source)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "HYPE COMMENTATOR"
                result["language_used"] = str(language or "english").strip().lower()
                result["word_count"] = _words(
                    " ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or [])
                )
                result["source_title"] = _story_value(story, "title")
                result["source_evidence"] = source
                result["coverage_brief"] = coverage
                result["coverage_review_provider"] = (
                    coverage.get("provider_used") if isinstance(coverage, dict) else None
                )
                if coverage_errors:
                    result["coverage_research_warnings"] = coverage_errors
                return result
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
        valid, reason = validate_script(result, _clean(result.get("source_evidence")))
        if not valid:
            raise ValueError(f"Edited script failed local validation: {reason}")

    result["human_script_edited"] = any(
        _clean(scene["voiceover"]) != _clean(original.get("voiceover"))
        for scene, original in zip(scenes, script.get("script", []))
    )
    result["approved_for_audio"] = True
    return result
