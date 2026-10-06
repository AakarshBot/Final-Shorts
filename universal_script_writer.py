"""Function 02B: universal sports Shorts scriptwriter for Niche Sports and YouTube Trends."""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
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
MIN_WORDS = 45
MAX_WORDS = 74
MAX_SLIDE_ONE_WORDS = 13
MIN_SCENES = 3
MAX_SCENES = 5

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and publish metadata in punchy, natural spoken English.",
    "hindi": "Write all narration and publish metadata in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and publish metadata in natural spoken Telugu using Telugu script.",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "subject_name": {"type": "string"},
        "headline": {"type": "string"},
        "titles": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "seo_description": {"type": "string"},
        "hashtags": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "comment": {"type": "string"},
        "quote": {"type": "string"},
        "quote_attribution": {"type": "string"},
        "quote_slide": {"type": "integer", "minimum": 0, "maximum": MAX_SCENES},
        "script": {
            "type": "array",
            "minItems": MIN_SCENES,
            "maxItems": MAX_SCENES,
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
        "quote",
        "quote_attribution",
        "quote_slide",
        "script",
    ],
    "additionalProperties": False,
}

FILLER_PHRASES = (
    "wait till the end",
    "wait until the end",
    "watch till the end",
    "watch until the end",
    "keep watching",
    "stay tuned",
    "don't scroll",
    "dont scroll",
    "don't skip",
    "dont skip",
    "you won't believe",
    "you wont believe",
    "find out later",
    "here is the latest",
    "here's the latest",
    "here’s the latest",
    "welcome to",
    "hey everyone",
    "hey guys",
    "in this video",
    "today we are going to",
    "let's talk about",
    "lets talk about",
    "sports world is buzzing",
    "the sports world is buzzing",
    "what happens next remains to be seen",
)


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
            include_tables=False,
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
        if not domain or any(
            blocked in domain
            for blocked in ("twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google.")
        ):
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

    if original_url:
        try:
            primary, resolved = _extract_article(original_url)
        except (requests.RequestException, OSError, ValueError):
            primary, resolved = "", original_url
        if primary:
            sections.append(
                f"[PRIMARY ARTICLE — {resolved or original_url}]\n{primary[:16000]}"
            )

    related = _related_article_urls(title, original_url)
    if related:
        with ThreadPoolExecutor(max_workers=min(2, len(related))) as pool:
            futures = [
                pool.submit(_extract_article, related_url)
                for _, related_url in related
            ]
            for number, ((related_title, related_url), future) in enumerate(
                zip(related, futures),
                1,
            ):
                try:
                    article, resolved_url = future.result()
                except (requests.RequestException, OSError, ValueError):
                    continue
                if article:
                    sections.append(
                        f"[RELATED REPORT {number} — {related_title} — "
                        f"{resolved_url or related_url}]\n{article[:6000]}"
                    )

    return "\n\n".join(sections)[:MAX_SOURCE_CHARS]


def _request(model: str, prompt: str, source: str) -> dict:
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
                {"role": "user", "content": "RESEARCH PACKET:\n" + source},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "universal_sports_shorts_script",
                    "strict": True,
                    "schema": SCHEMA,
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


SYSTEM_PROMPT = """You are the senior editorial sports writer for a human-reviewed YouTube Shorts channel.

JOB
Turn the supplied research packet into one original, factual, high-energy sports Short.
This writer serves Niche Sports stories and YouTube Search Trends stories. The selected story may be about any sport, including cricket. Do not assume cricket.

SOURCE USE
- Read the entire research packet before writing.
- Treat the selected article as the primary source. Use related reports to confirm facts, fill factual gaps, add current context, or clarify the latest status.
- Build your own version of the story. Do not mechanically summarize the article and do not copy complete source sentences.
- Use only facts supported by the research packet.
- Never invent names, scores, rankings, records, quotes, dates, injuries, penalties, motives, schedules, statistics or consequences.
- Preserve allegations, predictions, expectations and reported claims as such.
- When the source contains conflicting reports, do not silently choose one. Use the supported latest position or state the uncertainty clearly.

UNDERSTAND THE STORY FIRST
Silently determine:
- the actual sport or topic;
- the dominant news development;
- the exact main person/team/event/entity;
- the most important consequence or significance;
- the concrete fact that proves or sharpens the story;
- the latest confirmed status or next development.

Do not force a fixed event template. A transfer, injury, retirement, qualifying result, race penalty, disciplinary decision, record, statement, selection, tournament result and other developments need different story structures.

NAMING PEOPLE AND ENTITIES
- Identify the exact main subject in subject_name.
- The exact subject_name must appear naturally in the spoken narration.
- If the source or headline uses a descriptor such as "legend", "champion", "star", "former champion", "defending champion" or "world number one", resolve that descriptor to the actual named person or team from the story before writing.
- Never make the viewer guess who a descriptor refers to when the research identifies the person.
- Prefer the exact name early when the identity is central to the story.
- Do not manufacture a subject name from unrelated context.

NARRATION CONTRACT
- Return 3, 4 or 5 spoken slides.
- Never return only 1 or 2 slides.
- Four slides are the preferred structure when they fit naturally.
- Use 3 slides when the story is genuinely tight.
- Use 5 slides when five distinct factual beats are needed.
- Slide 1 MUST contain fewer than 14 words. This is a generation rule.
- The complete spoken narration MUST be at least 18 seconds and strictly under 30 seconds at normal channel delivery.
- As a generation proxy, keep the complete narration between 45 and 74 spoken words. This protects the 18-second minimum and the under-30-second ceiling without padding.
- Target roughly 50–68 words when the story permits.
- Never add words merely to reach the minimum.
- The minimum duration must come from useful story information, context, evidence or consequence.
- Every slide must add genuinely new information.

EDITORIAL STYLE
- One persona: HYPE COMMENTATOR — sharp, energetic, confident and credible.
- Write for the ear: short clean sentences, active voice, concrete verbs and natural spoken rhythm.
- The editorial touch comes from selecting and explaining why the reported development matters, not from inventing an opinion.
- Compress the source into the strongest version a viewer can understand without reading the article.
- Prefer specific facts over generic excitement.
- Respect each sport's actual rules and event structure.
- Do not call a qualifying result a race win, a round win a tournament title, a ranking movement a championship win, or a scheduled event a completed event.
- Use sport-specific terminology only when supported and used correctly.
- If the story is about cricket, write proper cricket language; if it is tennis, motorsport, badminton, chess or another sport, write the vocabulary appropriate to that story.

NO FILLER OR RETENTION BAIT
The narration must never contain viewer-directed bait or disposable filler such as:
- "wait till the end", "wait until the end", "watch till the end", "watch until the end";
- "keep watching", "stay tuned", "don't scroll", "don't skip";
- "you won't believe this", "find out later";
- generic openings such as "welcome to", "hey everyone", "hey guys", "in this video", "today we are going to", "let's talk about", "here is the latest";
- empty phrases such as "the sports world is buzzing", "this is huge", "major update", "big news", "things could change", or similar hype without story-specific meaning.
Do not ask the viewer a generic question merely to force curiosity.
Curiosity must come from a real information gap created by the facts.

STORY FLOW
Use the structure that best fits the evidence, while normally following:
1. HOOK — the strongest specific fact or development.
2. DEVELOPMENT — a new fact that materially advances the story.
3. CONTEXT / SIGNIFICANCE — the minimum context needed to understand why the event matters.
4. CONSEQUENCE / STATUS — the latest confirmed outcome, effect or next development.
For five slides, split context or consequence only when each extra slide carries a separate useful fact.
For three slides, combine context and consequence when that produces a cleaner story.
Never repeat the headline as narration. Never repeat the same fact across slides.

PUBLISH METADATA
- headline: exactly 3 or 4 words. It should identify the actual story, not use empty phrases.
- titles: exactly 3 concise YouTube Shorts title candidates:
  1. SEO / Search — lead with the strongest identifiable person, team, event or distinctive search term.
  2. Consequence / Why It Matters — foreground the concrete impact or significance.
  3. Curiosity — create an information gap from a confirmed fact without misleading the viewer.
- Every title must be clearly about the selected story and materially different in angle.
- Do not use generic titles such as "latest update", "breaking news", "big update" or "sports update".
- seo_description: concise and story-specific.
- hashtags: 3–5 relevant story-specific hashtags.
- comment: one concise, story-specific discussion question grounded in a concrete fact.

QUOTE
- quote: the strongest meaningful direct quote from the research when one materially adds to the story; otherwise empty string.
- quote_attribution: exact speaker/source of quote, or empty string when there is no quote.
- quote_slide: the existing slide number where the quote naturally supports the story, or 0 when there is no quote.
- Never invent, reconstruct or alter a quote.
- A quote is a visual treatment for an existing story beat, never an additional narration beat.

VISUAL HANDOFF
Every slide must include:
- primary_entity
- visual_intent
- specific_search_prompt
- sport_or_topic_category
Make each visual handoff match the fact narrated on that slide.
Prefer identifiable people, teams, venues, cars, events, trophies, equipment or other concrete subjects.
Search prompts must be specific and usable by the Visual Fetcher.
Never use vague prompts such as "dramatic sports moment".
Do not invent a visual moment unsupported by the research.

FINAL SELF-CHECK
Before returning JSON, silently verify:
1. The story is understandable without the article.
2. There are 3–5 slides, preferably 4.
3. Slide 1 has fewer than 14 words.
4. Total narration is 45–74 words.
5. The exact main subject name appears in the narration.
6. No filler or retention-bait phrase appears.
7. Every slide adds new factual information.
8. Every factual claim is grounded in the research packet.
9. The headline is 3–4 words.
10. Exactly 3 titles are present.
11. Description, hashtags and comment are useful and story-specific.
12. Any quote is faithful and attached to an existing slide.
13. Every visual handoff field is complete and concrete.

Return only JSON matching the supplied schema.

LANGUAGE
Follow the requested language exactly while preserving the same factual, compact editorial principles.
"""

def validate_universal_script(
    result: dict,
    *,
    headline_required: bool = True,
) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        return False, "Universal Scriptwriter must return 3–5 slides."

    subject = _clean(result.get("subject_name"))
    if not subject:
        return False, "The Scriptwriter must identify the main subject."

    first_words = _words(
        scenes[0].get("voiceover")
        if isinstance(scenes[0], dict)
        else ""
    )
    if first_words > MAX_SLIDE_ONE_WORDS:
        return False, "Slide 1 must contain fewer than 14 words."

    narration_parts = []
    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not _clean(scene.get("voiceover")):
            return False, f"Slide {number} is empty or malformed."
        for key in (
            "primary_entity",
            "visual_intent",
            "specific_search_prompt",
            "sport_or_topic_category",
        ):
            if not _clean(scene.get(key)):
                return False, f"Slide {number} is missing {key}."
        narration_parts.append(_clean(scene.get("voiceover")))

    narration = " ".join(narration_parts)
    total_words = _words(narration)
    if total_words < MIN_WORDS:
        return False, "Narration is too short to reach the 18-second minimum without padding."
    if total_words > MAX_WORDS:
        return False, "Narration must stay under 30 seconds."

    narration_normalised = _normalise(narration)
    subject_normalised = _normalise(subject)
    if subject_normalised and subject_normalised not in narration_normalised:
        return False, "The main subject is not named in the spoken narration."

    for phrase in FILLER_PHRASES:
        if _normalise(phrase) in narration_normalised:
            return False, "The narration contains filler or retention bait."

    headline = _clean(result.get("headline"))
    if headline_required and not headline:
        return False, "The opening headline is required."
    if headline and not 3 <= _words(headline) <= 4:
        return False, "The opening headline must contain 3 or 4 words."

    titles = result.get("titles")
    if (
        not isinstance(titles, list)
        or len(titles) != 3
        or not all(_clean(item) for item in titles)
    ):
        return False, "The Scriptwriter must produce exactly 3 titles."

    if not _clean(result.get("seo_description")):
        return False, "The Scriptwriter must produce a description."

    hashtags = result.get("hashtags")
    if (
        not isinstance(hashtags, list)
        or not 3 <= len(hashtags) <= 5
        or any(
            not _clean(tag).startswith("#") or " " in _clean(tag)
            for tag in hashtags
        )
    ):
        return False, "The Scriptwriter must produce 3–5 valid hashtags."

    if not _clean(result.get("comment")):
        return False, "The Scriptwriter must produce a public comment."

    quote = _clean(result.get("quote"))
    attribution = _clean(result.get("quote_attribution"))
    try:
        quote_slide = int(result.get("quote_slide") or 0)
    except (TypeError, ValueError):
        return False, "The quote slide is invalid."

    if quote:
        if not attribution:
            return False, "A quote requires an attribution."
        if not 1 <= quote_slide <= len(scenes):
            return False, "A quote must point to an existing slide."
    elif attribution or quote_slide:
        return False, "Quote attribution and slide must be empty when no quote is provided."

    return True, ""


def _finish_result(result: dict, story, source: str, model: str, language_key: str) -> dict:
    result["provider_used"] = model
    result["delivery_profile"] = "UNIVERSAL SPORTS"
    result["language_used"] = language_key
    result["word_count"] = _words(
        " ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or [])
    )
    result["source_title"] = _story_value(story, "title")
    result["source_evidence"] = source
    return result


def write_universal_script(story, language: str = "english") -> dict:
    source = _research_story(story)
    if not source:
        source = _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    instruction = (
        SYSTEM_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )

    errors = []
    for attempt, model in enumerate(MODELS):
        try:
            model_instruction = instruction
            if attempt:
                model_instruction += (
                    "\nRECOVERY:\n"
                    "The previous draft was rejected by local validation. "
                    "Rewrite the complete package now. Fix the exact failure below "
                    "while preserving every other hard rule and all supported facts. "
                    "Return only the complete JSON package.\n"
                    f"Validation failure: {errors[-1]}"
                )
            result = _request(model, model_instruction, source)
            valid, reason = validate_universal_script(result)
            if valid:
                return _finish_result(result, story, source, model, language_key)
            errors.append(reason)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    raise RuntimeError(
        "Universal sports script generation failed after one hidden rewrite: "
        + " | ".join(errors)
    )


def apply_universal_script_edits(
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
        valid, reason = validate_universal_script(
            result,
            headline_required=False,
        )
        if not valid:
            raise ValueError(f"Edited script failed local validation: {reason}")

    result["human_script_edited"] = any(
        _clean(scene.get("voiceover")) != _clean(original.get("voiceover"))
        for scene, original in zip(scenes, script.get("script") or [])
    )
    result["approved_for_audio"] = True
    return result

