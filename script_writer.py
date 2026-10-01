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

COVERAGE_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "coverage_pct": {"type": "number"},
        "complete": {"type": "boolean"},
        "covered_facts": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 12},
        "missing_facts": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 12},
    },
    "required": ["coverage_pct", "complete", "covered_facts", "missing_facts"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the senior human cricket editor for a human-reviewed YouTube Shorts channel.

The selected headline is the assignment. The supplied evidence packet is the story.

NON-NEGOTIABLE EDITORIAL RULES
- Produce exactly four spoken slides.
- Slide 1 must contain fewer than 14 words.
- The finished Short must be designed for less than 30 seconds. The existing Audio stage can speed up a slightly long draft, so do not pad or distort the story just to hit a timing target.
- Every slide must contain important information.
- Across the four slides, cover roughly 90% of the materially important information in the entire researched story.
- Do not invent a story, prolong the headline, repeat the headline as narration, or add filler.
- Use the entire evidence packet, including related current reporting, not just the first article.
- A source count does not matter. One source is fine when it contains the necessary facts.
- Related current facts are useful when they are genuinely part of the same story.
- Do not invent missing information when research does not support it.
- Write complete, natural spoken sentences.

FACT COVERAGE
Read the complete evidence packet before drafting.
Prioritise facts that explain:
- what actually happened;
- who is involved;
- the important background;
- relevant numbers, dates, records, statistics, career information or other concrete evidence;
- what changed;
- the latest confirmed status or consequence.
Do not spend four slides rephrasing the selected headline.

SLIDE DESIGN
- Slide 1: strongest factual entry point, fewer than 14 words.
- Slides 2–4: each must add meaningful new information.
- Compress related facts into efficient sentences when that increases coverage without making the narration unnatural.
- Do not force every possible detail into the Short; cover the material story, not article boilerplate.

STYLE
- Energetic cricket desk voice. Facts create the energy.
- Write for the ear.
- Prefer specific names, teams, competitions, dates and numbers when supported.
- No generic hype, clickbait, retention bait or audience commands.

PUBLISH METADATA
Produce the existing three title candidates, a story-specific SEO description, relevant hashtags and the existing upload comment. Keep them grounded in the researched story.

VISUAL HANDOFF
Every slide needs useful visual metadata that matches the fact being narrated.

Return only JSON matching the supplied schema.
"""

FORCEFUL_INSTRUCTION = """MANUAL-QC FORCEFUL RETRY

Rewrite the entire four-slide script from scratch.

The previous draft did not satisfy the required story coverage strongly enough. Re-read the entire evidence packet and the coverage audit. Make the missing facts explicit in the new narration wherever they are materially important.

The objective is not to make the script longer. The objective is to make the four slides cover roughly 90% of the materially important story information without inventing anything.

Every slide must carry substantive information. Remove any sentence that merely repeats the headline, adds atmosphere, or delays a factual point.

Slide 1 must contain fewer than 14 words.
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
                "json_schema": {"name": "sports_shorts_script", "strict": True, "schema": SCHEMA},
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


def _request_coverage_audit(source: str, result: dict) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {
                    "role": "system",
                    "content": """You are a strict fact-coverage editor.

Compare the complete source evidence against the generated four-slide cricket Short.

Judge coverage by materially important story information, not by matching article wording. A four-slide Short covers the story adequately only when it captures roughly 90% of the important factual substance: the key development, people involved, important background, relevant statistics/numbers/dates/records, major context and confirmed current status.

Do not require minor repetition, boilerplate, quotes that add no information, or every sentence from the article.

Return a coverage percentage between 0 and 1, whether the draft is complete enough, the important facts covered, and the important facts still missing.""",
                },
                {
                    "role": "user",
                    "content": "SOURCE EVIDENCE:\n" + source + "\n\nGENERATED SCRIPT:\n" + json.dumps(result, ensure_ascii=False),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sports_script_coverage_audit", "strict": True, "schema": COVERAGE_AUDIT_SCHEMA},
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.1,
            "max_completion_tokens": 800,
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
    if not isinstance(scenes, list) or not scenes:
        return False, "The provider did not return a script."
    if _words(scenes[0].get("voiceover")) >= 14:
        return False, "Slide 1 must contain fewer than 14 words."
    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not _clean(scene.get("voiceover")):
            return False, f"Slide {number} is empty or malformed."
        if not all(_clean(scene.get(key)) for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category")):
            return False, f"Slide {number} is missing visual metadata."
    if not isinstance(result.get("titles"), list) or not all(_clean(item) for item in result["titles"]):
        return False, "The Scriptwriter must produce titles."
    if not _clean(result.get("seo_description")):
        return False, "The Scriptwriter must produce a description."
    if not isinstance(result.get("hashtags"), list) or not any(_clean(item) for item in result["hashtags"]):
        return False, "The Scriptwriter must produce hashtags."
    return True, ""


def _finish_result(result: dict, story, source: str, model: str, audit: dict | None, language_key: str) -> dict:
    result["provider_used"] = model
    result["delivery_profile"] = "HYPE COMMENTATOR"
    result["language_used"] = language_key
    result["word_count"] = _words(" ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or []))
    result["source_title"] = _story_value(story, "title")
    result["source_evidence"] = source
    if audit is not None:
        result["coverage_audit"] = audit
    return result


def write_script(story, language: str = "english", forceful: bool = False, previous_script: dict | None = None) -> dict:
    source = _research_story(story, profile="cricket") or _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    base_instruction = (
        SYSTEM_PROMPT
        + "\n\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )
    if forceful:
        base_instruction += "\n" + FORCEFUL_INSTRUCTION
        if previous_script:
            base_instruction += "\nPREVIOUS DRAFT TO IMPROVE:\n" + json.dumps(previous_script, ensure_ascii=False)

    errors = []
    for model in MODELS:
        try:
            result = _request(model, base_instruction, source)
            valid, reason = validate_script(result, source)
            if not valid:
                errors.append(f"{model}: {reason}")
                continue
            if len(result.get("script") or []) != 4:
                errors.append(f"{model}: Cricket Scriptwriter must return exactly 4 slides.")
                continue

            try:
                audit = _request_coverage_audit(source, result)
            except Exception as exc:
                audit = None
                errors.append(f"Coverage audit unavailable: {type(exc).__name__}: {exc}")

            if isinstance(audit, dict) and (audit.get("complete") is False or float(audit.get("coverage_pct", 0)) < 0.9):
                force = base_instruction + "\n\nCOVERAGE AUDIT FINDINGS:\n" + json.dumps(audit, ensure_ascii=False) + "\n" + FORCEFUL_INSTRUCTION
                revised = _request(model, force, source)
                valid, reason = validate_script(revised, source)
                if not valid:
                    errors.append(f"{model}: forceful rewrite failed: {reason}")
                    continue
                if len(revised.get("script") or []) != 4:
                    errors.append(f"{model}: forceful rewrite returned more than 4 slides.")
                    continue
                try:
                    revised_audit = _request_coverage_audit(source, revised)
                except Exception:
                    revised_audit = audit
                if isinstance(revised_audit, dict):
                    audit = revised_audit
                result = revised

            return _finish_result(result, story, source, model, audit, language_key)
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
