"""Top-5 cricket Scriptwriter for Function 02.

This module is intentionally independent from script_writer.py. It writes one
six-slide Top-5 package from five approved Topic Fetcher stories.
"""

from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json
import os
from pathlib import Path
from functools import lru_cache
import re
from urllib.parse import urlparse

import requests
import trafilatura
from ddgs import DDGS
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
TIMEOUT = 30
RESEARCH_TIMEOUT = 8
MAX_ARTICLE_CHARS = 4500
MAX_STORY_EVIDENCE_CHARS = 5000
MAX_EVIDENCE_CHARS = 6500
MAX_PACKAGE_STORY_CHARS = 1200
MIN_ARTICLE_CHARS = 500
SLIDE_1_MAX_WORDS = 14
SPEECH_WORDS_PER_MINUTE = 150.0
MIN_HASHTAGS = 3
MAX_HASHTAGS = 5
BODY_SENTENCE_COUNT = 2

AI_EDITORIAL_PATTERNS = (
    r"\bchanging the conversation\b",
    r"\bchange(?:d|s)? the way .* see\b",
    r"\beveryone is talking about\b",
    r"\bthe cricket world is buzzing\b",
    r"\bsending shockwaves\b",
    r"\bshocking the cricket world\b",
    r"\bgame[- ]changer\b",
    r"\bbig talking point\b",
    r"\bwhat you need to know\b",
    r"\bhere(?:'|’)?s what happened\b",
    r"\bin a major update\b",
    r"\bthis could change everything\b",
    r"\bset to change cricket\b",
)

SLIDE_1_FILLER_PATTERNS = (
    r"\bneed to (?:see|watch|know)\b",
    r"\b(?:you|viewers|fans) (?:need to|have to|got to) (?:see|watch|know)\b",
    r"\bright now\b",
    r"\bdon['’]?t miss\b",
    r"\bcan['’]?t miss\b",
    r"\bmust[- ](?:see|watch|know)\b",
    r"\bworth (?:seeing|watching)\b",
    r"\b(?:make|makes|making) you see (?:the )?(?:game|cricket) differently\b",
    r"\bchange(?:s|d)? the way you see (?:the )?(?:game|cricket)\b",
    r"\b(?:will|could|can) change (?:the )?(?:game|world|cricket)\b",
    r"\b(?:changing|change(?:s|d)?) (?:the )?world\b",
    r"\b(?:changing|change(?:s|d)?) (?:the )?game\b",
    r"\bsee (?:the )?(?:game|cricket) differently\b",
    r"\bhere(?:'|’)?s why\b",
    r"\bfind out\b",
)

GENERIC_PATTERNS = (
    r"^\s*top five cricket stories(?: of the day)?\s*$",
    r"^\s*five cricket stories(?: of the day)?\s*$",
    r"^\s*cricket news today\s*$",
    r"^\s*latest cricket news\s*$",
    r"^\s*today(?:'|’)?s cricket roundup\s*$",
    r"^\s*the biggest cricket stories(?: today)?\s*$",
)

LANGUAGE_PROMPT = (
    "Write in natural spoken English. Use normal sports-desk vocabulary, "
    "clean sentence rhythm and no artificial promotional language."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
                        "items": {
                "type": "object",
                "properties": {
                    "slide_number": {"type": "integer", "minimum": 1, "maximum": 6},
                    "story_index": {"type": "integer", "minimum": 0, "maximum": 5},
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                    "primary_entity": {"type": "string"},
                    "visual_intent": {"type": "string"},
                    "specific_search_prompt": {"type": "string"},
                    "sport_or_topic_category": {"type": "string"},
                },
                "required": [
                    "slide_number",
                    "story_index",
                    "headline",
                    "body",
                    "primary_entity",
                    "visual_intent",
                    "specific_search_prompt",
                    "sport_or_topic_category",
                ],
                "additionalProperties": False,
            },
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "seo_description": {"type": "string"},
        "comment": {"type": "string"},
    },
    "required": ["slides", "hashtags", "seo_description", "comment"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the senior sports desk editor for a human-reviewed YouTube Shorts channel.

You are writing ONE Top-5 cricket Short from exactly five selected stories.
Treat the five supplied stories as five separate editorial assignments. Do not merge
their facts, do not invent a common theme, and do not make the package sound like an
AI-generated roundup.

EDITORIAL STANDARD
- Use only facts explicitly supported by the supplied evidence.
- Research evidence is provided for each selected story. Stay inside that story's evidence.
- A headline must tell the important development, not simply rephrase the source headline.
- The body is visual-only supporting copy. Write exactly two concise factual sentences.
  Together they should add useful facts, context, timing, consequence or supporting detail
  from the same story. Never make them a restatement of the headline.
- Never invent quotes, numbers, motives, reactions, implications, predictions or outcomes.
- Do not imply public reaction, global importance or a wider trend unless the evidence
  explicitly establishes it.
- Write like a sharp human cricket editor: specific, economical and natural.
- Avoid promotional, dramatic, clickbait or generic AI language.
- Never address the viewer directly in Slide 1. It is an editorial package headline, not a
  call to action or teaser.
- Never pad Slide 1 with phrases such as "you need to see", "you need to know", "right now",
  "don't miss", "can't miss", "must-see", "worth watching", "find out", "here's why",
  "make you see the game differently", "change the way you see the game", "change the world",
  or similar audience-facing filler.
- Do not use phrases such as "changing the conversation", "everyone is talking",
  "the cricket world is buzzing", "sending shockwaves", "game changer",
  "what you need to know", "here's what happened", or similar synthetic framing.
- Slide 1 is the package opener for the Top-5 Short. It should smartly communicate
  “today's top five cricket news/headlines” while incorporating concrete details from a few
  of the five selected stories.
- Make Slide 1 feel like a smart human-written front-page or scoreboard headline: concise,
  informative and varied. It can weave together two or three notable names, teams, events,
  results or headline developments from the selected stories.
- The wording may use a natural roundup frame such as “Gill returns, India reshuffle and
  three more cricket headlines today”, but it should never be a bare label such as
  “Top 5 Cricket Stories” or “Cricket News Today”.
- Write Slide 1 yourself rather than copying any source headline verbatim. Do not invent
  a common theme or connect unrelated stories as though they are one event.

SLIDE STRUCTURE
- Return exactly six slides.
- Slide 1 is the Top-5 package opener. It has ONE spoken headline, a maximum of 14 words, and no body copy.
- Slides 2–6 correspond exactly, in order, to selected stories 1–5.
- Set story_index exactly as follows: Slide 1 = 0, Slide 2 = 1, Slide 3 = 2, Slide 4 = 3, Slide 5 = 4, Slide 6 = 5.
- For Slides 2–6, the headline IS the spoken narration for that slide.
- Each story headline must tell the complete important development in ONE clean sentence.
- Each story headline must remain under 15 seconds of estimated natural speech.
- Do not merely repeat the source title. Add the key development, context or consequence
  that makes the story understandable on its own.
- The body is visual-only supporting copy. Write exactly two concise factual sentences.
  Together they should add useful detail or context from the same story that is not already
  fully stated in the headline. Do not pad them with filler.
- For every slide, provide a concrete visual entity, visual intent and a specific search prompt.
  Slide 1 should describe a factual cricket-package visual, not an invented mood or theme.
- `seo_description`: concise and story-specific, covering the Top-5 package without inventing a common theme.
- `hashtags`: generate 3–5 relevant story/package-specific hashtags. Include the main teams, players, events, competitions or developments when suitable. Avoid generic growth tags such as #viral, #fyp or #trending unless directly relevant.
- `comment`: one concise discussion-oriented public comment grounded in the selected stories. Do not invent facts or ask a generic engagement question disconnected from the package.
- Return JSON only.
"""

def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w ]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _story_value(story, key: str) -> str:
    if hasattr(story, "__dataclass_fields__"):
        return _clean(getattr(story, key, ""))
    return _clean(dict(story or {}).get(key))


@lru_cache(maxsize=2048)
def _source_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def _limit_text(text: str, limit: int = MAX_ARTICLE_CHARS) -> str:
    clean = _clean(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip() + "…"


def _article_body_from_html(html_text: str) -> str:
    raw = str(html_text or "")
    paragraphs = []
    for paragraph in re.findall(
        r"<p\b[^>]*>(.*?)</p>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        value = _clean(unescape(re.sub(r"<[^>]+>", " ", paragraph)))
        if value:
            paragraphs.append(value)
    return "\n".join(paragraphs)


def _extract_article(url: str) -> tuple[str, str]:
    target = _clean(url)
    if not target:
        return "", ""

    response = requests.get(
        target,
        headers={
            "User-Agent": "Final-Shorts/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=RESEARCH_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    resolved_url = str(response.url or target)

    candidates = [
        trafilatura.extract(
            response.text,
            url=resolved_url,
            favor_recall=True,
            include_comments=False,
            include_tables=False,
            output_format="txt",
        ),
        _article_body_from_html(response.text),
    ]
    for candidate in candidates:
        text = _clean(candidate)
        if len(text) >= MIN_ARTICLE_CHARS:
            return _limit_text(text), resolved_url

    return "", resolved_url


@lru_cache(maxsize=2048)
def _title_keywords(title: str) -> set[str]:
    words = re.findall(r"\b[\w]+\b", title.casefold(), flags=re.UNICODE)
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "before", "after",
        "about", "into", "over", "under", "when", "where", "will", "has", "have",
        "had", "its", "his", "her", "their", "they", "them", "your", "our",
        "new", "latest", "update", "news", "team", "match", "game", "sport",
        "sports", "vs", "versus", "cricket",
    }
    return {word for word in words if len(word) >= 3 and word not in stop}


def _search_corroborating_article(title: str, original_url: str) -> tuple[str, str]:
    query = _clean(title)
    original_domain = _source_domain(original_url)
    keywords = _title_keywords(query)
    minimum_overlap = 2 if len(keywords) >= 2 else 1
    blocked = ("twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google.")

    try:
        results = DDGS(timeout=5).news(
            query=query,
            region="in-en",
            safesearch="off",
            timelimit="w",
            max_results=5,
        )
    except Exception:
        results = []

    candidates = []
    for result in results or []:
        url = _clean(result.get("url") or result.get("href"))
        result_title = _clean(result.get("title"))
        if not url or url == original_url:
            continue
        domain = _source_domain(url)
        if not domain or domain == original_domain or any(x in domain for x in blocked):
            continue
        overlap = len(keywords & _title_keywords(result_title))
        if keywords and overlap < minimum_overlap:
            continue
        candidates.append((overlap, url))

    for _, url in sorted(candidates, key=lambda item: item[0], reverse=True):
        try:
            article, resolved = _extract_article(url)
            if article:
                return article, resolved
        except (OSError, ValueError, requests.RequestException):
            continue
    return "", ""


def _research_story(story: dict) -> str:
    title = _story_value(story, "title")
    url = _story_value(story, "url")
    description = _story_value(story, "article") or _story_value(story, "description")
    sections = [f"[SELECTED STORY]\n{title}"]

    if url:
        try:
            article, resolved = _extract_article(url)
        except (OSError, ValueError, requests.RequestException):
            article, resolved = "", url

        if article:
            sections.append(f"[PRIMARY ARTICLE — {resolved or url}]\n{article}")
        else:
            fallback, fallback_url = _search_corroborating_article(title, url)
            if fallback:
                sections.append(f"[CORROBORATING ARTICLE — {fallback_url}]\n{fallback}")

    if description:
        sections.append(f"[TOPIC FETCHER SUMMARY]\n{_limit_text(description, 1800)}")

    evidence = "\n\n".join(sections)
    return _limit_text(evidence, MAX_STORY_EVIDENCE_CHARS)


def research_top5_stories(stories: list[dict]) -> list[str]:
    if len(stories) != 5:
        raise ValueError("Top-5 Scriptwriter requires exactly five selected stories.")
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(_research_story, stories))
    if not any(results):
        raise RuntimeError("Top-5 story research returned no usable evidence.")
    return results


def _evidence_packet(stories: list[dict], research: list[str]) -> str:
    packets = []
    for index, (story, evidence) in enumerate(zip(stories, research), 1):
        title = _story_value(story, "title")
        packets.append(
            f"===== STORY {index} =====\n"
            f"TITLE: {title}\n"
            f"TEXT: {_limit_text(evidence, MAX_PACKAGE_STORY_CHARS)}"
        )
    packet = "\n\n".join(packets)
    return _limit_text(packet, MAX_EVIDENCE_CHARS)


def estimate_speech_seconds(text: str) -> float:
    return _words(text) / (SPEECH_WORDS_PER_MINUTE / 60.0)


def _contains_forbidden_editorial_language(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in AI_EDITORIAL_PATTERNS)


def _is_generic_package_headline(headline: str) -> bool:
    clean = _clean(headline)
    return any(re.search(pattern, clean, re.IGNORECASE) for pattern in GENERIC_PATTERNS)


def _contains_slide_1_filler(headline: str) -> bool:
    clean = _clean(headline)
    return any(re.search(pattern, clean, re.IGNORECASE) for pattern in SLIDE_1_FILLER_PATTERNS)


def _references_any_selected_story(headline: str, stories: list[dict]) -> bool:
    headline_words = set(_normalise(headline).split())
    selected_keywords = set()
    for story in stories:
        selected_keywords.update(_title_keywords(_story_value(story, "title")))
    return bool(headline_words & selected_keywords)


def _sentence_count(text: str) -> int:
    clean = _clean(text)
    if not clean:
        return 0
    return len(re.findall(r"[^.!?]+[.!?](?=\s|$)", clean))


def validate_top5_script(result: dict, stories: list[dict]) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no Top-5 script object."
    if len(stories) != 5:
        return False, "Top-5 Scriptwriter requires exactly five selected stories."

    slides = result.get("slides")
    if not isinstance(slides, list) or len(slides) != 6:
        return False, "Top-5 Scriptwriter must return exactly six slides."

    for expected_number, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            return False, f"Slide {expected_number} is malformed."
        if slide.get("slide_number") != expected_number:
            return False, f"Slide {expected_number} has the wrong slide number."
        if int(slide.get("story_index", -1)) != (expected_number - 1):
            return False, f"Slide {expected_number} is mapped to the wrong story."

        headline = _clean(slide.get("headline"))
        if not headline:
            return False, f"Slide {expected_number} has no headline."
        if _contains_forbidden_editorial_language(headline) or _contains_slide_1_filler(headline):
            return False, f"Slide {expected_number} contains audience-facing or synthetic filler language."

        for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category"):
            if not _clean(slide.get(key)):
                return False, f"Slide {expected_number} is missing {key}."

        if expected_number == 1:
            if _words(headline) > SLIDE_1_MAX_WORDS:
                return False, f"Slide 1 exceeds {SLIDE_1_MAX_WORDS} words."
            if _is_generic_package_headline(headline):
                return False, "Slide 1 is a generic Top-5 headline."
            if not _references_any_selected_story(headline, stories):
                return False, "Slide 1 must incorporate a concrete detail from the selected stories."
            if any(
                _clean(other.get("headline")).casefold() == headline.casefold()
                for other in slides[1:]
            ):
                return False, "Slide 1 cannot duplicate a story headline."
            body = _clean(slide.get("body"))
        else:
            story = stories[expected_number - 2]
            if estimate_speech_seconds(headline) >= 15.0:
                return False, f"Slide {expected_number} is not below 15 seconds at the speech-rate estimate."
            body = _clean(slide.get("body"))
            if not body:
                return False, f"Slide {expected_number} is missing body copy."
            if _sentence_count(body) != BODY_SENTENCE_COUNT:
                return False, f"Slide {expected_number} body must contain exactly two sentences."

    description = _clean(result.get("seo_description"))
    if not description:
        return False, "Top-5 Scriptwriter must return a non-empty description."

    hashtags = result.get("hashtags")
    if (
        not isinstance(hashtags, list)
        or not MIN_HASHTAGS <= len(hashtags) <= MAX_HASHTAGS
        or any(not _clean(tag).startswith("#") or " " in _clean(tag) for tag in hashtags)
    ):
        return False, "Top-5 Scriptwriter must return 3–5 valid hashtags."

    if not _clean(result.get("comment")):
        return False, "Top-5 Scriptwriter must return a non-empty public comment."

    return True, ""


def _request(model: str, prompt: str, evidence: str) -> dict:
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
                {"role": "user", "content": "TOP-5 STORY EVIDENCE:\n" + evidence},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "top5_cricket_script",
                    "strict": True,
                    "schema": SCHEMA,
                },
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.35,
            "max_completion_tokens": 2200,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def generate_top5_script(stories: list[dict]) -> dict:
    if len(stories) != 5:
        raise ValueError("Top-5 Scriptwriter requires exactly five selected stories.")

    research = research_top5_stories(stories)
    if not any(_clean(text) for text in research):
        raise RuntimeError("Top-5 story research returned no usable evidence.")

    evidence = _evidence_packet(stories, research)
    errors = []
    recovery_reason = ""

    for model in MODELS:
        instruction = SYSTEM_PROMPT + "\n\n" + LANGUAGE_PROMPT
        if recovery_reason:
            instruction += (
                "\n\nRECOVERY:\n"
                "The previous draft failed local validation. Regenerate the complete "
                "six-slide JSON and fix this exact validation failure without relaxing "
                "any other rule.\n"
                f"Validation failure: {recovery_reason}"
            )
        try:
            result = _request(model, instruction, evidence)
            valid, reason = validate_top5_script(result, stories)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "TOP-5 CRICKET EDITOR"
                result["stories"] = [
                    {
                        "title": _story_value(story, "title"),
                        "url": _story_value(story, "url"),
                        "source": _story_value(story, "source"),
                        "published_at": _story_value(story, "published_at"),
                    }
                    for story in stories
                ]
                return result
            recovery_reason = reason
            errors.append(f"{model}: {reason}")
        except Exception as exc:
            recovery_reason = f"{type(exc).__name__}: {exc}"
            errors.append(f"{model}: {recovery_reason}")

    raise RuntimeError("Top-5 script generation failed: " + " | ".join(errors))
