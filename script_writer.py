"""Unified Scriptwriter for Final-Shorts.

Serves all production streams and desks:
- Deep-Dive Cricket (3–5 spoken slides + 3 angles + publish metadata)
- YouTube Search Trends & Niche Sports (universal sports Shorts engine)
- Top-5 (6 slides: 1 hook + 5 distinct spoken headlines with visual body copy)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import unescape
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse

from ddgs import DDGS
from dotenv import load_dotenv
import requests
import trafilatura

load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
TIMEOUT = 30
RESEARCH_TIMEOUT = 10
MIN_ARTICLE_CHARS = 500
MAX_SOURCE_CHARS = 28000
MAX_RELATED_ARTICLES = 2
MAX_SLIDE_ONE_WORDS = 13

# Top-5 specific constants
MAX_ARTICLE_CHARS = 4500
MAX_EVIDENCE_CHARS = 6500
MAX_PACKAGE_STORY_CHARS = 1200
SLIDE_1_MAX_WORDS = 8
SPEECH_WORDS_PER_MINUTE = 150.0
MAX_TOP5_TOTAL_SPEECH_SECONDS = 30.0
MIN_HASHTAGS = 3
MAX_HASHTAGS = 5

# Shared non-Top-5 spoken-script constants
MIN_WORDS = 50
MAX_WORDS = 74
MIN_SCENES = 3
MAX_SCENES = 5


class GroqAPIError(RuntimeError):
    """A Groq HTTP error with provider detail and retry metadata."""

    def __init__(self, status_code: int, message: str, retry_after: str | None = None):
        self.status_code = int(status_code)
        self.retry_after = str(retry_after or "").strip() or None
        detail = f"Groq API HTTP {self.status_code}: {message}"
        if self.retry_after:
            detail += f" (Retry-After: {self.retry_after})"
        super().__init__(detail)


def _groq_http_error(response: requests.Response) -> GroqAPIError:
    status = int(response.status_code)
    retry_after = response.headers.get("Retry-After")
    detail = ""
    code = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = _clean(error.get("message"))
            code = _clean(error.get("code") or error.get("type"))
        elif isinstance(error, str):
            detail = _clean(error)
        if not detail:
            detail = _clean(payload.get("message"))
    if not detail:
        detail = _clean(getattr(response, "text", ""))[:700]
    if not detail:
        detail = "The provider returned no error detail."
    if code:
        detail = f"{code}: {detail}"
    if status == 429:
        detail = "Rate limit reached. " + detail
    elif status == 400:
        detail = "The provider rejected the request. " + detail
    return GroqAPIError(status, detail, retry_after)

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
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
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

UNIVERSAL_SCHEMA = {
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

ANGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "angles": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence_basis": {"type": "string"},
                },
                "required": ["title", "description", "evidence_basis"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["angles"],
    "additionalProperties": False,
}

TOP5_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "minItems": 6,
            "maxItems": 6,
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

SCHEMA = TOP5_SCHEMA  # Backward-compatible alias for Top-5 schema tests

SYSTEM_PROMPT = """You are the senior cricket editor and viral showrunner for a human-reviewed YouTube Shorts channel.

JOB
Turn the supplied researched cricket story into one complete, high-retention 3–5-slide spoken Short, targeting the same 20–30 second duration.

SOURCE USE & FACTUAL GROUNDING VS EDITORIAL LIBERTY
- Read the entire research packet before writing.
- HARD GROUNDING (STRICT TRUTH): Real names, scores, match state, venue, dates, and confirmed events must be 100% accurate and grounded in the research packet. Never invent match scores, fake statistics, dates, records, injuries, or fake quotes.
- EDITORIAL LIBERTY (VIRAL COMMENTARY): You are a sharp, energetic broadcast commentator—NOT a robotic scorecard reader. You are explicitly encouraged to use rhetorical questions, tactical comparisons (e.g. comparing a 33-ball duck to a golden duck), psychological drama, and high-stakes debate framing. Let the facts anchor the story, but let your narrative voice drive the intrigue and debate.
- Treat the selected article as the primary source and use related reports to fill factual gaps. Preserve reported claims as reported claims.

EDITORIAL ANGLE & PROMPT (AUTHORITATIVE)
- If a user-selected or custom editorial angle is supplied, BUILD THE ENTIRE SHORT AROUND THIS SPECIFIC LENS.
- Frame the hook, causality, and concluding kicker through this angle. Do not ignore it or default to a generic match summary.
- The underlying match event provides the factual context, but the selected angle determines what the Short is actually about.

INFORMATION & RETENTION
Compress all material factual information into 3–5 slides, letting the story determine the natural number of cuts.
Keep the facts a viewer actually needs: who it is about, what happened, when and where relevant, important scores/numbers/records, material background, and the latest confirmed consequence or status.
Remove only repetition, boilerplate and low-value wording.
Do not replace facts with generic empty hype.

NAMING THE SUBJECT
- Identify the exact main player/person/team in `subject_name`.
- The exact `subject_name` must appear in the spoken narration.
- Never describe the main player only as "the 35-year-old", "the player", "the batter", "the bowler", "the captain", or with a pronoun when the exact name is available.
- For a story about a specific player, name that player in the first two slides whenever the evidence supports the name.

3–5 SLIDES — 20–30s BROADCAST NEWS ARTICLE
- Return 3–5 spoken slides. Prefer four when that best serves the story, but do not force a fixed slide count.
- Slide 1 is the hook: the strongest specific fact from the story.
- For English narration, Slide 1 MUST contain 13 words or fewer. For Hindi and Telugu, write a concise lead designed to fit within 5.2 seconds of natural narration; the Audio stage validates its measured first-scene duration instead of counting whitespace-separated words.
- Later slides must add new information and carry the important remaining facts.
- The complete narration MUST fit within 30 seconds at the channel's normal spoken delivery pace. Treat this as a generation requirement; keep wording tight and do not pad.
- As a generation target, keep the complete narration between 50 and 70 spoken words (~20 to 28 seconds).
- Do not pad the script to hit a word count.

ANTI-REPETITION & EDITORIAL AUTHENTICITY (CRITICAL):
YouTube strictly flags repetitive template scripts as inauthentic content. To ensure authentic, original journalism:
- NEVER use generic AI transition clichés (e.g. "The move follows", "Officials confirmed that", "With the series on the line", "Now, all eyes turn to", "The stage is set", "Only time will tell", "In a shocking turn of events").
- Vary narrative momentum dynamically using one of these authentic editorial approaches:
  1. The Forensic Tactical Breakdown: Focus directly on the strategic flaw, masterstroke, or pitch condition that decided the event.
  2. The Untold Precedent / Contrast: Compare today's occurrence with a historic parallel or past controversy that completely reframes the narrative.
  3. The High-Stakes Debate: Foreground the selection dispute, dressing room tension, or polarizing tactical decision.
  4. The Statistical Anomaly: Highlight the rarity of the metric and what standard scorecards hide.
- Write with varied, human conversational cadence: use sharp contrasts, active verbs, and natural pauses. Never sound like a robotic news wire summary.

VIRAL PACKAGING SUITE
- `headline`: a crisp, story-specific display field for the dashboard only. It is metadata, not on-screen text, narration, or part of the rendered Short. Keep it concise and useful, but do not enforce a word or character limit.
- `titles`: exactly 3 distinct viral YouTube Shorts title candidates across these 3 archetypes:
  1. SEO / Search — lead with the main player, team, event or key search term and make the story immediately discoverable in search.
  2. High-Stakes Debate & Consequence / Why It Matters — ask a polarizing question or foreground the concrete impact that forces viewers to debate in the comments.
  3. Curiosity Gap & Intrigue — create an irresistible information loop from confirmed facts without misleading.
- Every title must be accurate, concise, punchy, and clearly different in angle.
- Put the most important words first; avoid generic filler such as "latest update", "breaking news", "big update" or "sports update".
- `seo_description`: concise and story-specific summary optimized for YouTube Shorts algorithm.
- `hashtags`: 3–5 relevant story-specific hashtags including player, team, and tournament.
- `comment`: one provocative, high-engagement pinned question designed to ignite debate in the comments. Tailor it specifically to the real tactical or ethical dilemma in the story without using canned bot phrases.
- `quote`: the strongest meaningful direct quote from the research, copied faithfully, when one materially adds to the story. Return an empty string when there is no worthwhile quote.
- `quote_attribution`: the exact speaker/source of `quote`, or an empty string when there is no quote.
- `quote_slide`: the existing slide number (1–5, never greater than the generated slide count) where the quote most naturally supports the narration, or 0 when there is no quote. Do not create an extra slide for a quote.
- Never invent, reconstruct, or shorten a quote in a way that changes its wording.

VISUAL HANDOFF
Every slide must include useful metadata matching the narrated fact:
- primary_entity
- visual_intent
- specific_search_prompt
- sport_or_topic_category

GENERATION CHECKLIST — SATISFY THE EXISTING SCRIPT CHECKS BEFORE RETURNING JSON
- Return 3–5 non-empty spoken slides. Each slide must include non-empty primary_entity, visual_intent, specific_search_prompt, and sport_or_topic_category.
- For English, keep Slide 1 to 13 words or fewer; for Hindi/Telugu, keep the lead concise and let the measured 5.2-second audio check enforce the limit.
- Name the non-empty subject_name exactly in the spoken narration.
- Include a non-empty, crisp dashboard-only headline, exactly three non-empty and distinct title candidates, a non-empty story-specific SEO description, at least one relevant hashtag, and a non-empty public comment.
- Keep the full narration concise enough to fit under 30 seconds without padding; include all important supported facts across the generated slides.
- quote must be copied exactly from source evidence or be empty. Provide an exact quote_attribution and quote_slide from 1–5, never greater than the generated slide count, when quote is present; when quote is empty, return an empty quote_attribution and quote_slide 0.
- Make every field complete in the first JSON returned. Before output, check the actual field values, not only the JSON shape.

FINAL SELF-CHECK
Before returning JSON, silently verify:
1. Return 3–5 slides, preferring four only when it best fits the story.
2. For English, Slide 1 is 13 words or fewer; for Hindi/Telugu, the generated first-scene audio fits within 5.2 seconds.
3. The main subject is named in the narration.
4. All important factual information is compressed across the generated slides.
5. No unsupported claim has been added.
6. The metadata is complete.
7. Any quote is copied faithfully from the research packet and points to an existing slide; never create an extra slide for it.

Return only JSON matching the supplied schema.
"""

CRICKET_ANGLE_PROMPT = """You are the senior editorial planning desk for a viral sports YouTube Shorts channel.

Read the entire research packet and propose exactly three genuinely different, high-retention story angles for the same story.

VIRAL ANGLE ARCHETYPES
Propose exactly three distinct creative angles corresponding to these proven YouTube formats:
1. THE HIGH-STAKES DEBATE / PROVOCATION:
   Frame the event as a polarizing question or tactical debate (e.g., "Is a 33-ball duck better than a golden duck?", "Masterclass or total collapse?", "Did the captain make the right call?").
2. THE ANOMALY / FREAK STAT / HISTORICAL RECORD:
   Focus on the extreme numbers, where this ranks in history, or a statistical contrast that shocks the viewer.
3. THE HIDDEN DRAMA / NARRATIVE INVERSION:
   Reveal the untold story, tactical sacrifice, or behind-the-scenes tension that proves the scorecard doesn't tell the whole truth.

RULES
- Each angle must be grounded in the research packet.
- The angles must be materially different in perspective and tone, not three phrasings of the same summary.
- Each title must be concise (2–5 words) and immediately communicate the viral lens.
- Each description must be one short sentence explaining the Short's central thesis.
- evidence_basis must name the concrete evidence in the research that makes the angle viable.
- Return only JSON matching the supplied schema.
"""

UNIVERSAL_SYSTEM_PROMPT = """You are the senior editorial sports writer for a human-reviewed YouTube Shorts channel.

JOB
Turn the supplied research packet into one original, factual, high-energy sports Short.
This writer serves Niche Sports stories and YouTube Search Trends stories. The selected story may be about any sport, including cricket. Do not assume cricket.

SOURCE USE
- Read the entire research packet before writing.
EDITORIAL ANGLE
- If a user-selected editorial angle is supplied, it is authoritative.
- The entire Short must be built around that angle.
- Do not switch back to the most obvious event/result merely because it is easier to summarize.
- The underlying event may be used as context, but it must not replace the selected angle.
- For a statement, reaction or quote angle, make the person's reported comments the core development when the research supports them.
- For a consequence or significance angle, prioritize the concrete impact and only use event details that explain it.
- For a process or performance angle, prioritize how the development happened rather than repeating the outcome.
- The selected angle may be custom-written by the user; follow it exactly within the facts supported by the research.
- Never invent evidence just to satisfy an angle.
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
- For English, Slide 1 MUST contain fewer than 14 words. For Hindi and Telugu, write a concise lead designed to fit within 5.2 seconds of natural narration; measured first-scene duration is validated after Audio generation.
- The complete spoken narration MUST be at least 18 seconds and strictly under 30 seconds at normal channel delivery.
- As a generation proxy, keep the complete narration between 50 and 74 spoken words. This protects the 18-second minimum and the under-30-second ceiling without padding.
- Target roughly 52–68 words when the story permits.
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

STORY FLOW — ONE CONNECTED 18–30s BROADCAST ARTICLE
- Write one cohesive news article split across spoken cuts, not disconnected bullet points.
- Let the facts determine the transitions and slide structure. Use natural connective wording grounded in actual chronology, cause, context, or consequence; never use a fixed template or any phrase forbidden by NO FILLER OR RETENTION BAIT.
- Slide 1: lead with the strongest specific development and name the subject when supported. For English, stay under 14 words. For Hindi/Telugu, keep the lead concise enough to fit within a measured 5.2 seconds of audio.
- Later slides: add the next useful fact, evidence, background, or consequence. Each slide must contribute new information without repeating a fact or mechanically restating the headline.
- Use 3–5 slides as the story warrants, preferably four when that is the clearest structure. Do not force fixed per-slide word ranges.
- Read the cuts in sequence: they must sound natural, flow into one continuous article, and stay within 50–74 total spoken words and under 30 seconds without padding.

PUBLISH METADATA
- headline: a crisp, story-specific display field for the dashboard only. It is never spoken or rendered onto the Short. It has no word-count limit.
- titles: exactly 3 concise YouTube Shorts title candidates:
  1. SEO / Search — lead with the strongest identifiable person, team, event or distinctive search term.
  2. Consequence / Why It Matters — foreground the concrete impact or significance.
  3. Curiosity — create an information gap from a confirmed fact without misleading the viewer.
- Every title must be clearly about the selected story and materially different in angle.
- When a primary YouTube search query is supplied, make the SEO / Search title a natural, accurate match for that query and use its important terms naturally in the description.
- Never force a search phrase that would make the title inaccurate or misleading.
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

GENERATION CHECKLIST — SATISFY THE EXISTING SCRIPT CHECKS BEFORE RETURNING JSON
- Return 3–5 non-empty spoken slides, each with non-empty primary_entity, visual_intent, specific_search_prompt, and sport_or_topic_category.
- For English, keep Slide 1 to 13 words or fewer. For Hindi/Telugu, keep Slide 1 concise for a maximum measured audio duration of 5.2 seconds. Keep total narration between 50 and 74 spoken words; aim for 52–68 words when the evidence supports it, never padding.
- subject_name must be non-empty and the exact name must appear naturally in the spoken narration.
- Do not use any listed filler or retention-bait phrase, including “what happens next remains to be seen”.
- Return a non-empty, crisp dashboard-only headline (no word-count limit), exactly three non-empty title candidates, a non-empty SEO description, 3–5 hashtags each beginning with # and containing no spaces, and a non-empty public comment.
- quote, quote_attribution, and quote_slide must agree: if a quote is present, give its source attribution and a valid existing slide number; otherwise return empty quote and attribution with quote_slide 0. Never invent or alter a quotation.
- Complete every required value in the generated JSON. Do not expect manual QC to repair omitted required fields.

FINAL SELF-CHECK
Before returning JSON, silently verify:
1. The story is understandable without the article.
2. There are 3–5 slides, preferably 4.
3. For English, Slide 1 has fewer than 14 words; for Hindi/Telugu, the generated first-scene audio fits within 5.2 seconds.
4. Total narration is 50–74 words.
5. The exact main subject name appears in the narration.
6. No filler or retention-bait phrase appears.
7. Every slide adds new factual information.
8. Every factual claim is grounded in the research packet.
9. The headline is crisp dashboard-only metadata with no word-count limit.
10. Exactly 3 titles are present.
11. Description, hashtags and comment are useful and story-specific.
12. Any quote is faithful and attached to an existing slide.
13. Every visual handoff field is complete and concrete.

Return only JSON matching the supplied schema.

LANGUAGE
Follow the requested language exactly while preserving the same factual, compact editorial principles.
"""

UNIVERSAL_ANGLE_PROMPT = """You are the senior editorial planning desk for a viral sports YouTube Shorts channel.

Read the entire research packet and propose exactly three genuinely different, high-retention story angles for the same story.

VIRAL ANGLE ARCHETYPES
Propose exactly three distinct creative angles corresponding to these proven YouTube formats:
1. THE HIGH-STAKES DEBATE / PROVOCATION:
   Frame the event as a polarizing question or tactical debate (e.g. "Did they make the right call?", "Masterclass or total collapse?", "Tactical genius or pure luck?").
2. THE ANOMALY / FREAK STAT / HISTORICAL RECORD:
   Focus on the extreme numbers, where this ranks in history, or a statistical contrast that shocks the viewer.
3. THE HIDDEN DRAMA / NARRATIVE INVERSION:
   Reveal the untold story, tactical sacrifice, or behind-the-scenes tension that proves the headline doesn't tell the whole truth.

RULES
- Each angle must be grounded in the research packet.
- The angles must be materially different in perspective and tone, not three phrasings of the same summary.
- When the research contains a meaningful post-match, post-event or public statement, center one of the three angles on that reaction evidence.
- Each title must be concise (2–5 words) and immediately communicate the viral lens.
- Each description must be one short sentence explaining the Short's central thesis.
- evidence_basis must name the concrete evidence in the research that makes the angle viable.
- If a primary YouTube search query is supplied, use it as search-intent context when choosing angles, but never sacrifice factual accuracy.
- Return only JSON matching the supplied schema.
"""

TOP5_SYSTEM_PROMPT = """You are the senior sports desk editor for a human-reviewed YouTube Shorts channel.

You are writing ONE Top-5 cricket Short from exactly five selected stories.
Treat the five supplied stories as five separate editorial assignments. Do not merge
their facts, do not invent a common theme, and do not make the package sound like an
AI-generated roundup.

EDITORIAL STANDARD
- Use only facts explicitly supported by the supplied evidence.
- Research evidence is provided for each selected story. Stay inside that story's evidence.
- A headline must tell the important development, not simply rephrase the source headline.
- The body is visual-only supporting copy: it appears on the editorial card but is not narrated.
  Keep it concise enough to fit comfortably in the 9:16 card. Use a reasonable amount of
  supporting factual detail without forcing a fixed sentence or word count. Never turn it
  into a mini article or restate the headline.
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
- Slide 1 is the package opener. Its headline is a short section label, always a variation of
  “Top-5 Cricket News Of The Day”, “Top 5 Cricket News Today”, “Top-5 Cricket Headlines Today”
  or similar. Keep it at eight words or fewer. Do not put story-specific facts, names or results
  into the Slide 1 headline.
- Slide 1 body is visual-only. It carries the factual roundup script that would otherwise have
  been compressed into the spoken opener: mention the most useful selected developments,
  names, teams or results in concise, natural sports-desk copy. It may use more than one
  sentence when needed, but must stay focused and factual.
- Make Slide 1 feel like a clean sports-news front page: a clear package label above a useful
  factual summary, with no viewer-facing teaser language.
- Write Slide 1 yourself rather than copying any source headline verbatim. Do not invent
  a common theme or connect unrelated stories as though they are one event.

SLIDE STRUCTURE
- Return exactly six slides.
- Slide 1 is the Top-5 package opener. It has one short spoken package label (maximum eight words)
  plus visual-only body copy containing the factual roundup summary.
- Slides 2–6 correspond exactly, in order, to selected stories 1–5.
- Set story_index exactly as follows: Slide 1 = 0, Slide 2 = 1, Slide 3 = 2, Slide 4 = 3, Slide 5 = 4, Slide 6 = 5.
- For Slides 2–6, the headline IS the spoken narration for that slide.
- Each story headline must tell the complete important development in ONE clean sentence.
- The six spoken headlines together must remain at or below 30 seconds of estimated natural speech.
- Do not merely repeat the source title. Add the key development, context or consequence
  that makes the story understandable on its own.
- The body is visual-only supporting copy. Keep it concise enough to fit comfortably in the
  9:16 editorial card, using a reasonable amount of factual supporting detail without a fixed
  sentence or word count. Use body copy when it adds context; keep it empty when the spoken
  headline already carries the necessary information. Never pad it with filler.
- For every slide, provide a concrete visual entity, visual intent and a specific search prompt.
  Slide 1 should describe a factual cricket-package visual, not an invented mood or theme.
- `seo_description`: concise and story-specific, covering the Top-5 package without inventing a common theme.
- `hashtags`: generate 3–5 relevant story/package-specific hashtags. Include the main teams, players, events, competitions or developments when suitable. Avoid generic growth tags such as #viral, #fyp or #trending unless directly relevant.
- `comment`: one concise discussion-oriented public comment grounded in the selected stories. Do not invent facts or ask a generic engagement question disconnected from the package.
GENERATION CHECKLIST — SATISFY EVERY EXISTING TOP-5 GENERATION CHECK BEFORE RETURNING JSON
- Return exactly six complete slide objects in order. Set slide_number to 1–6 and story_index to 0–5 respectively (story_index equals slide_number minus one).
- Every headline must be non-empty. Every slide must have non-empty primary_entity, visual_intent, specific_search_prompt, and sport_or_topic_category.
- All six spoken headlines together must be under 30 seconds at 150 words per minute; aim for 26–28 seconds, not the limit.
- Do not use any validated synthetic/editorial filler in any headline: “changing the conversation”, “change the way people see”, “everyone is talking about”, “the cricket world is buzzing”, “sending shockwaves”, “shocking the cricket world”, “game changer” or “game-changer”, “big talking point”, “what you need to know”, “here’s what happened”, “in a major update”, “this could change everything”, or “set to change cricket”.
- The validator checks viewer-directed filler in every headline, not only Slide 1. Do not use “need to see/watch/know”; “you”, “viewers” or “fans need to, have to, or got to see/watch/know”; “right now”; “don’t miss” or “can’t miss”; “must-see/watch/know”; “worth seeing/watching”; “make”, “makes” or “making you see the game/cricket differently”; “change”, “changes” or “changed the way you see the game/cricket”; “will”, “could” or “can change the game/world/cricket”; “changing”, “changes” or “changed the world/game”; “see the game/cricket differently”; “here’s why”; or “find out”.
- Slide 1 must be eight words or fewer and clearly include “Top-5” or “Top 5”, “Cricket”, and “News”, “Headline(s)”, “Stories”, or “Roundup”. It is only the package label, must not duplicate a story headline on Slides 2–6, and must have non-empty visual-only roundup body copy.
- Slides 2–6 must report the five selected stories in the supplied order. Return a non-empty SEO description, 3–5 single-token hashtags (each begins with # and has no spaces), and a non-empty public comment. Every title/body fact must be supported by that story’s evidence. Later visual-only body copy may be empty when it adds no useful context.

Return JSON only.
"""

DESK_PROMPTS = {
    "cricket_india_asia": """
EDITORIAL DESK: SUBCONTINENTAL CRICKET DESK
- Target: Passionate Indian and Asian cricket fans expecting high-stakes drama, tactical sharpness, and insider authority.
- Editorial Focus: Team India, IPL franchises, BCCI selection moves, bilateral rivalries, Asia Cup, and ICC trophy pressure.
- Tone & Vocabulary: Urgent, authoritative, tactical, and dramatic. Use authentic cricket terms naturally (powerplay, death overs, match simulation, turning track, selection committee, bilateral showdown).
- Subject Naming: Name the core player (e.g. Virat Kohli, Rohit Sharma, Jasprit Bumrah, Shubman Gill) in Slide 1.
""",
    "cricket_global": """
EDITORIAL DESK: INTERNATIONAL CRICKET CORRESPONDENT
- Target: Global cricket purists and international followers.
- Editorial Focus: World Test Championship, The Ashes, SENA tours, County Championship, BBL, SA20, and ICC governance.
- Tone & Vocabulary: Prestigious, crisp broadcast cadence, analytical and heritage-conscious. Use classic international cricket language (red-ball grit, pace attack, seam movement, declarations, overseas triumph).
- Subject Naming: Identify the exact national team, captain, or player immediately in Slide 1.
""",
    "niche_sports": """
EDITORIAL DESK: HIGH-ENERGY MULTI-SPORT DESK
- Target: Passionate fans of Formula 1, Grand Slam Tennis, Football, Badminton, Boxing, MMA, or Chess.
- Editorial Focus: The decisive competitive breakthrough, title race, or shocking upset.
- Tone & Vocabulary: Kinetic, explosive, modern sports anchor. Use sport-precise terminology flawlessly (pole position, undercut, break point, straight sets, clean sheet, stoppage time, grandmaster). Never misstate the sporting stage.
- Subject Naming: Name the exact athlete or club in Slide 1.
""",
    "youtube_trends": """
EDITORIAL DESK: YOUTUBE SEARCH TRENDS DESK
- Target: Viewers searching for a trending topic or discovering an exploding viral sports story.
- Editorial Focus: The exact search-intent query or trending curiosity corroborated by hard 24-hour news facts.
- Tone & Vocabulary: High-curiosity hook, immediate payoff, fast rhythm, highly conversational yet strictly factual.
- Search Query Integration: If a search query is provided, weave its key entity or search angle naturally into the Slide 1 lead without awkward keyword stuffing.
""",
    "otd": """
EDITORIAL DESK: ON THIS DAY (HISTORICAL SPORTS MILESTONES)
- Target: Sports fans seeking nostalgia, legendary moments, and iconic throwback feats.
- Editorial Focus: The historic calendar anniversary, the incredible milestone, and why it changed sports history.
- Tone & Vocabulary: Epic, monumental, narrative throwback celebrating iconic sports history.
- 4-Beat Historical Arc:
  * Slide 1: THE ANNIVERSARY HOOK: "On this day in [Year], [Subject] achieved one of the most iconic feats in history." Keep it under 14 words in English; in Hindi/Telugu, keep it concise enough to fit within 5.2 seconds of measured narration.
  * Slide 2: THE ADVERSITY / DRAMA: The hostile atmosphere, the impossible odds, or the desperate match situation.
  * Slide 3: THE HISTORIC FEAT: The unforgettable numbers, the record shattered, or the clutch climax.
  * Slide 4: THE ENDURING LEGACY: Why that milestone redefined the sport and echoes decades later.
""",
}

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

PACKAGE_OPENER_PATTERNS = (
    r"\btop\s*[- ]?(?:5|five)\b",
    r"\bcricket\b",
    r"\b(?:news|headlines?|stories|roundup)\b",
)

LANGUAGE_PROMPT = (
    "Write in natural spoken English. Use normal sports-desk vocabulary, "
    "clean sentence rhythm and no artificial promotional language."
)


# ---------------------------------------------------------------------------
# Common Text & Research Helpers
# ---------------------------------------------------------------------------
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


def _angle_text(angle) -> str:
    if isinstance(angle, dict):
        title = _clean(angle.get("title"))
        desc = _clean(angle.get("description"))
        if title and desc:
            return f"{title}: {desc}"
        return title or desc
    return _clean(angle)


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w ]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _normalize_profile(profile: str | None) -> str:
    p = str(profile or "").strip().lower().replace("-", "_")
    if p in {"cricket_india", "india_asia", "cricket_india_asia", "deep_dive"}:
        return "cricket_india_asia"
    if p in {"cricket_global", "global_cricket"}:
        return "cricket_global"
    if p in {"niche", "niche_sports", "other_sports"}:
        return "niche_sports"
    if p in {"yt_trends", "youtube_trends", "trends"}:
        return "youtube_trends"
    if p in {"otd", "on_this_day", "history"}:
        return "otd"
    if p in {"top5", "top_5", "top_five"}:
        return "top_5"
    return "cricket_india_asia"




def evaluate_flow(script: dict) -> dict:
    """Analyze the broadcast narrative flow and speech timing of a script."""
    scenes = script.get("script") or []
    if not isinstance(scenes, list) or not scenes:
        return {
            "flow_score": 0.0,
            "total_words": 0,
            "slide_one_words": 0,
            "estimated_seconds": 0.0,
            "is_within_time": False,
            "is_slide_one_compliant": False,
            "transitions_count": 0,
        }

    voiceovers = [str(s.get("voiceover") or "").strip() for s in scenes if isinstance(s, dict)]
    slide_one_words = _words(voiceovers[0]) if voiceovers else 0
    total_words = _words(" ".join(voiceovers))
    est_seconds = round(total_words / 2.5, 1)

    connective_markers = (
        "after", "with", "now", "following", "as", "the move", "the decision",
        "officials", "forcing", "revealed", "confirmed", "despite", "meanwhile",
        "instead", "that makes", "that performance", "all eyes", "the stage",
        "before", "sparks", "sealed", "clinched", "stands", "heading into",
        "in response", "meanwhile", "crucially", "however", "prompting"
    )
    transitions_found = 0
    for vo in voiceovers[1:]:
        vo_lower = vo.lower()
        if any(marker in vo_lower for marker in connective_markers):
            transitions_found += 1

    score = 7.0
    if slide_one_words <= 13:
        score += 1.0
    if 50 <= total_words <= 72:
        score += 1.0
    elif 40 <= total_words <= 74:
        score += 0.5
    if len(voiceovers) > 1 and transitions_found >= (len(voiceovers) - 2):
        score += 1.0

    return {
        "flow_score": round(min(10.0, score), 1),
        "total_words": total_words,
        "slide_one_words": slide_one_words,
        "estimated_seconds": est_seconds,
        "is_within_time": 18.0 <= est_seconds <= 30.0,
        "is_slide_one_compliant": slide_one_words <= 13,
        "transitions_count": transitions_found,
    }


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
    response.encoding = response.encoding or response.apparent_encoding or "utf-8"
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
        return _limit_text(article), resolved_url

    try:
        fallback = DDGS(timeout=5).extract(resolved_url, fmt="text_plain")
        content = _clean(fallback.get("content") if isinstance(fallback, dict) else "")
        if len(content) >= MIN_ARTICLE_CHARS:
            return _limit_text(content), str(fallback.get("url") or resolved_url)
    except Exception:
        pass

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
        results = []

    if not results:
        try:
            from visual_fetcher import _google_news_rss
            results = _google_news_rss(title)
        except Exception:
            results = []

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
    description = _story_value(story, "description") or _story_value(story, "article")
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
        else:
            fallback, fallback_url = _search_corroborating_article(title, original_url)
            if fallback:
                sections.append(f"[CORROBORATING ARTICLE — {fallback_url}]\n{fallback}")

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
                        f"[RELATED REPORT {number} — {related_title} — {resolved_url or related_url}]\n"
                        + article[:7000]
                    )

    return "\n\n".join(sections)[:MAX_SOURCE_CHARS]


def _groq_strict_schema(schema):
    """Strip array-length keywords not documented in Groq's strict schema subset.

    Exact array lengths remain enforced by the local Scriptwriter validators; this
    only avoids sending undocumented minItems/maxItems keywords to the provider.
    """
    if isinstance(schema, dict):
        return {
            key: _groq_strict_schema(value)
            for key, value in schema.items()
            if key not in {"minItems", "maxItems"}
        }
    if isinstance(schema, list):
        return [_groq_strict_schema(value) for value in schema]
    return schema


def _request(
    model: str,
    prompt: str,
    story: str,
    schema: dict | None = None,
    *,
    schema_name: str | None = None,
    max_completion_tokens: int | None = None,
) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    if schema is not None:
        active_schema = schema
        active_schema_name = schema_name or "shorts_script"
        tokens = max_completion_tokens or 1800
    elif "six-slide" in prompt.lower() or "top-5" in prompt.lower() or "top5" in prompt.lower():
        active_schema = TOP5_SCHEMA
        active_schema_name = "top5_cricket_script"
        tokens = max_completion_tokens or 2200
    elif "3, 4 or 5" in prompt or "niche sports" in prompt.lower() or "universal" in prompt.lower():
        active_schema = UNIVERSAL_SCHEMA
        active_schema_name = "universal_shorts_script"
        tokens = max_completion_tokens or 1400
    elif "three distinct story angles" in prompt.lower() or "editorial planning desk" in prompt.lower():
        active_schema = ANGLE_SCHEMA
        active_schema_name = "story_angles"
        tokens = max_completion_tokens or 900
    else:
        active_schema = CRICKET_SCHEMA
        active_schema_name = "cricket_shorts_script"
        tokens = max_completion_tokens or 1800

    user_payload = ""
    angle_marker = "SELECTED EDITORIAL ANGLE (AUTHORITATIVE):"
    if angle_marker in prompt:
        angle_chunk = prompt.split(angle_marker, 1)[1].strip()
        if "\nRECOVERY:\n" in angle_chunk:
            angle_chunk = angle_chunk.split("\nRECOVERY:\n", 1)[0].strip()
        user_payload += (
            f"MANDATORY EDITORIAL ANGLE (PRIORITY ONE DIRECTIVE):\n"
            f"{angle_chunk}\n\n"
            f"CRITICAL INSTRUCTION: Construct the Short around this exact thesis. Ground all real-world facts "
            f"in the research packet below, but frame the narration, hook, debate, and pacing entirely through this lens.\n\n"
        )
    user_payload += "RESEARCH PACKET:\n" + story
    provider_schema = _groq_strict_schema(active_schema)

    for attempt in range(3):
        try:
            response = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_payload},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": active_schema_name,
                            "strict": True,
                            "schema": provider_schema,
                        },
                    },
                    "include_reasoning": False,
                    "reasoning_effort": "low",
                    "temperature": 0.35,
                    "max_completion_tokens": tokens,
                },
                timeout=TIMEOUT,
            )
            break
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    if response.status_code >= 400:
        raise _groq_http_error(response)
    content = response.json()["choices"][0]["message"]["content"]
    if isinstance(content, dict):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Provider returned invalid JSON: {content}") from exc


def translate_card_copy(card_type: str, data: dict, target_language: str) -> dict:
    """Translate only human-facing card copy; preserve names and all numeric/stat data."""
    from copy import deepcopy

    language = str(target_language or "english").strip().casefold()
    language = {"en": "english", "hi": "hindi", "te": "telugu"}.get(language, language)
    language_names = {
        "english": "English (Latin script)",
        "hindi": "natural Hindi in Devanagari script",
        "telugu": "natural Telugu in Telugu script",
    }
    if language not in language_names:
        raise ValueError(f"Unsupported card-copy language: {target_language}")
    if language == "english":
        result = deepcopy(data)
        result["language"] = language
        return result

    card_type = " ".join(str(card_type or "").split())
    result = deepcopy(data)
    paths: list[tuple[str, str]] = []

    def add(path: str, value) -> None:
        text = str(value or "").strip()
        if text:
            paths.append((path, text))

    def add_if_textual_value(path: str, value) -> None:
        text = str(value or "").strip()
        if text and any(char.isalpha() for char in text):
            add(path, text)

    add("eyebrow", data.get("eyebrow"))
    if card_type == "Stat Highlight":
        add("headline", data.get("headline"))
        add_if_textual_value("value", data.get("value"))
        add("unit", data.get("unit"))
        for index, metric in enumerate(data.get("metrics") or []):
            add(f"metrics.{index}.label", (metric or {}).get("label"))
    elif card_type == "Quote / Reaction":
        add("quote", data.get("quote"))
        add("attribution", data.get("attribution"))
        add("context", data.get("context"))
    elif card_type == "Head-to-Head":
        add("headline", data.get("headline"))
        for index, metric in enumerate(data.get("metrics") or []):
            add(f"metrics.{index}", metric)
    elif card_type == "Key Fact / Milestone":
        add_if_textual_value("value", data.get("value"))
        add("label", data.get("label"))
        add("context", data.get("context"))
    else:
        raise ValueError(f"Card-copy translation is not supported for '{card_type}'.")

    if not paths:
        result["language"] = language
        return result

    field_map = {
        f"copy_{index:02d}": {"path": path, "text": text}
        for index, (path, text) in enumerate(paths, 1)
    }
    payload = {key: item["text"] for key, item in field_map.items()}
    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in field_map},
        "required": list(field_map),
        "additionalProperties": False,
    }
    prompt = (
        "Translate the supplied JSON values into "
        + language_names[language]
        + " for text displayed on a sports editorial card. Return only the required JSON object. "
        "Translate every supplied value naturally and concisely; do not explain your work. "
        "Preserve proper names, player/team/competition names and their spelling. "
        "Do not add or remove facts. This request contains only copy fields: statistics, score values, "
        "dates, numeric values and player/team name fields are intentionally excluded and must remain untouched. "
        "A quoted sentence may be translated for the target-language card, but preserve its exact meaning. "
        "Keep output values suitable for a compact vertical sports card."
    )
    errors = []
    translated = None
    for model in MODELS:
        try:
            candidate = _request(
                model,
                prompt,
                json.dumps(payload, ensure_ascii=False),
                schema=schema,
                schema_name="card_copy_translation",
                max_completion_tokens=1000,
            )
            if not isinstance(candidate, dict) or any(
                not isinstance(candidate.get(key), str) or not candidate[key].strip()
                for key in field_map
            ):
                raise ValueError("The translation provider returned incomplete card copy.")
            translated = candidate
            break
        except GroqAPIError as exc:
            errors.append(f"{model}: {exc}")
            if 400 <= exc.status_code < 500 and exc.status_code != 429:
                raise RuntimeError(
                    "Groq rejected the card-copy translation request: " + str(exc)
                ) from exc
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
    if translated is None:
        raise RuntimeError("Card-copy translation failed: " + " | ".join(errors))

    def set_path(target: dict, path: str, value: str) -> None:
        parts = path.split(".")
        current = target
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        final = parts[-1]
        if isinstance(current, list):
            current[int(final)] = value
        else:
            current[final] = value

    old_metrics = list(data.get("metrics") or []) if card_type == "Head-to-Head" else []
    new_metric_labels = []
    for key, item in field_map.items():
        value = translated[key].strip()
        set_path(result, item["path"], value)
        if card_type == "Head-to-Head" and item["path"].startswith("metrics."):
            new_metric_labels.append(value)

    if card_type == "Head-to-Head" and new_metric_labels:
        for side in ("left", "right"):
            side_data = result.get(side) or {}
            old_values = dict((data.get(side) or {}).get("values") or {})
            remapped = {}
            for old_label, new_label in zip(old_metrics, result.get("metrics") or []):
                if old_label in old_values:
                    remapped[new_label] = old_values[old_label]
            for key, value in old_values.items():
                if key not in old_metrics:
                    remapped[key] = value
            side_data["values"] = remapped
            result[side] = side_data

    result["language"] = language
    return result


def _validate_cricket_story_angles(result: dict) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no angle object."
    angles = result.get("angles")
    if not isinstance(angles, list) or len(angles) != 3:
        return False, "Cricket story angle generator must produce exactly 3 options."
    titles = set()
    for number, angle in enumerate(angles, 1):
        if not isinstance(angle, dict):
            return False, f"Angle {number} is empty or malformed."
        title = _clean(angle.get("title"))
        if not title:
            return False, f"Angle {number} is missing a title."
        if title.casefold() in titles:
            return False, f"Angle {number} is a duplicate."
        titles.add(title.casefold())
        if not _clean(angle.get("description")):
            return False, f"Angle {number} is missing a description."
        if not _clean(angle.get("evidence_basis")):
            return False, f"Angle {number} is missing an evidence basis."
    return True, ""


def suggest_cricket_story_angles(
    story,
    language: str = "english",
    search_query: str = "",
) -> dict:
    source = _research_story(story) or _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    instruction = (
        CRICKET_ANGLE_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )
    if search_query:
        instruction += f"\nPRIMARY YOUTUBE SEARCH QUERY:\n{search_query}\n"

    errors = []
    for model in MODELS:
        try:
            result = _request(
                model,
                instruction,
                source,
                schema=ANGLE_SCHEMA,
                schema_name="cricket_story_angles",
                max_completion_tokens=900,
            )
            valid, reason = _validate_cricket_story_angles(result)
            if valid:
                res = {
                    "angles": result["angles"],
                    "source_evidence": source,
                    "source_title": _story_value(story, "title"),
                    "language_used": language_key,
                    "provider_used": model,
                }
                if search_query:
                    res["search_query"] = search_query
                return res
            errors.append(f"{model}: {reason}")
        except GroqAPIError as exc:
            errors.append(f"{model}: {exc}")
            if 400 <= exc.status_code < 500 and exc.status_code != 429:
                raise RuntimeError(
                    "Groq rejected the cricket story-angle request: " + str(exc)
                ) from exc
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "Cricket story-angle generation failed: " + " | ".join(errors)
    )


def validate_cricket_script(
    result: dict,
    *,
    headline_required: bool = True,
    language: str | None = None,
) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        return False, "Cricket Scriptwriter must return 3–5 slides."

    subject = _clean(result.get("subject_name"))
    if not subject:
        return False, "The Scriptwriter must identify the main subject."

    language_key = str(language or result.get("language_used") or "english").strip().casefold()
    first_words = _words((scenes[0] or {}).get("voiceover")) if isinstance(scenes[0], dict) else 0
    if language_key not in {"hindi", "telugu", "hi", "te"} and first_words > MAX_SLIDE_ONE_WORDS:
        return False, "Slide 1 must contain fewer than 14 words."

    narration = _normalise(" ".join(_clean(scene.get("voiceover")) for scene in scenes))
    subject_normalised = _normalise(subject)
    if subject_normalised and subject_normalised not in narration:
        return False, "The main subject is not named in the spoken narration."

    headline = _clean(result.get("headline"))
    if headline_required and not headline:
        return False, "The opening headline is required."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or not all(_clean(item) for item in titles):
        return False, "The Cricket Scriptwriter must produce exactly 3 titles."

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
        for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category"):
            if not _clean(scene.get(key)):
                return False, f"Slide {number} is missing {key}."

    return True, ""


DESK_PROFILES = {
    "cricket_india_asia": "SUBCONTINENTAL CRICKET DESK",
    "cricket_global": "INTERNATIONAL CRICKET CORRESPONDENT",
    "niche_sports": "HIGH-ENERGY MULTI-SPORT DESK",
    "youtube_trends": "YOUTUBE SEARCH TRENDS DESK",
    "otd": "ON THIS DAY HISTORICAL DESK",
    "top_5": "TOP-5 DAILY ROUNDUP DESK",
}


def _finish_result(
    result: dict,
    story,
    source: str,
    model: str,
    language_key: str,
    angle_text: str = "",
    search_query: str | None = None,
    delivery_profile: str | None = None,
    desk_profile: str | None = None,
) -> dict:
    result.setdefault("story_angle", "")
    if angle_text:
        result["story_angle"] = angle_text
    result["provider_used"] = model
    result["language_used"] = language_key
    result["word_count"] = _words(" ".join(_clean(scene.get("voiceover")) for scene in result.get("script") or []))
    result["source_title"] = _story_value(story, "title")
    if search_query:
        result["search_query"] = search_query
    if delivery_profile:
        result["delivery_profile"] = delivery_profile
    if desk_profile:
        result["desk_profile"] = desk_profile
    result["flow_metrics"] = evaluate_flow(result)
    return result


def _supplement_research_for_angle(story, angle_text: str, source: str) -> str:
    if not angle_text:
        return source
    story_title = _clean(_story_value(story, "title"))
    title_words = set(re.findall(r"\b[\w]+\b", story_title.casefold()))
    angle_words = set(re.findall(r"\b[\w]+\b", angle_text.casefold()))
    stop_words = {"focus", "on", "the", "a", "an", "is", "than", "and", "in", "to", "of", "what", "how", "why", "who", "with"}
    diff_words = angle_words - title_words - stop_words
    if len(diff_words) >= 1:
        queries = [
            f"{angle_text} cricket".strip()[:90],
            f"{story_title} {angle_text}".strip()[:90],
        ]
        snippets = []
        for q in queries:
            try:
                results = DDGS(timeout=4).text(q, max_results=2) or []
                for r in results:
                    body = _clean(r.get("body") or r.get("snippet"))
                    if body and len(body) > 20 and body not in snippets:
                        snippets.append(f"- {body}")
                if len(snippets) >= 3:
                    break
            except Exception:
                pass
        if snippets:
            source += f"\n\n[SUPPLEMENTARY ANGLE CONTEXT & FACTS — '{angle_text}']:\n" + "\n".join(snippets[:4])
    return source[:MAX_SOURCE_CHARS]


def write_script(
    story,
    language: str = "english",
    angle=None,
    research_source: str | None = None,
    profile: str = "cricket_india_asia",
) -> dict:
    source = research_source or _research_story(story) or _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    norm_profile = _normalize_profile(profile)
    language_key = str(language or "english").strip().lower()
    angle_text = _angle_text(angle)
    if angle_text:
        source = _supplement_research_for_angle(story, angle_text, source)
    instruction = (
        SYSTEM_PROMPT
        + "\n\n"
        + DESK_PROMPTS.get(norm_profile, DESK_PROMPTS["cricket_india_asia"])
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )
    if angle_text:
        instruction += (
            "\n\nSELECTED EDITORIAL ANGLE (AUTHORITATIVE):\n"
            + angle_text
            + "\nBuild the whole narration around this lens. Explore the debate, comparison, or insight posed by this angle using the context and cricket knowledge. Do not replace it with the obvious event/result summary."
        )

    def finish(result: dict, model: str) -> dict:
        return _finish_result(
            result,
            story,
            source,
            model,
            language_key,
            angle_text=angle_text,
            delivery_profile=DESK_PROFILES.get(norm_profile, "SUBCONTINENTAL CRICKET DESK"),
            desk_profile=norm_profile,
        )

    def fresh_backup(first_error: Exception) -> dict:
        try:
            backup = _request(MODELS[1], instruction, source)
        except Exception as second_error:
            raise RuntimeError(
                "Script generation failed before a valid draft was available. "
                f"Primary request: {first_error} | Fresh backup request: {second_error}. "
                "No hidden rewrite was attempted because the primary request did not produce a draft."
            ) from second_error
        backup_valid, backup_reason = validate_cricket_script(backup, language=language_key)
        if not backup_valid:
            raise RuntimeError(
                "The backup model returned an invalid script after the primary request failed: "
                + backup_reason
            )
        return finish(backup, MODELS[1])

    try:
        result = _request(MODELS[0], instruction, source)
    except GroqAPIError as first_error:
        if 400 <= first_error.status_code < 500 and first_error.status_code != 429:
            raise RuntimeError(
                "Groq rejected the Scriptwriter request before generating a draft. "
                "This is a provider/request error, not a script-validation failure: "
                + str(first_error)
            ) from first_error
        return fresh_backup(first_error)
    except Exception as first_error:
        return fresh_backup(first_error)
    else:
        valid, reason = validate_cricket_script(result, language=language_key)
        if valid:
            return finish(result, MODELS[0])
        first_reason = reason

    rewrite_instruction = (
        instruction
        + "\n\nHIDDEN REWRITE\n"
        "The first draft is NOT being shown to the human reviewer. Rewrite the complete 3–5-slide script now, using the story's natural structure. "
        "Keep every important factual detail from the research packet, but fix the exact failure below. "
        "Do not explain the rewrite. Return only the complete JSON package.\n"
        f"Failure to fix: {first_reason}\n"
    )

    try:
        rewritten = _request(MODELS[1], rewrite_instruction, source)
    except Exception as second_error:
        raise RuntimeError(
            "Script generation failed after one hidden rewrite: "
            + f"{first_reason} | {type(second_error).__name__}: {second_error}"
        ) from second_error

    valid, reason = validate_cricket_script(rewritten, language=language_key)
    if not valid:
        raise RuntimeError("Script generation failed after one hidden rewrite: " + reason)

    return finish(rewritten, MODELS[1])


def generate_cricket_script(*args, **kwargs) -> dict:
    return write_script(*args, **kwargs)


def _apply_edits_helper(
    script: dict,
    voiceovers: list[str],
    headline: str | None = None,
) -> dict:
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited slides does not match the generated script.")
    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = _clean(voiceover)
    if headline is not None:
        result["headline"] = _clean(headline)
    result["human_script_edited"] = any(
        _clean(scene.get("voiceover")) != _clean(original.get("voiceover"))
        for scene, original in zip(scenes, script.get("script", []))
    )
    result["approved_for_audio"] = True
    return result


def apply_script_edits(script: dict, voiceovers: list[str], headline: str | None = None) -> dict:
    return _apply_edits_helper(script, voiceovers, headline=headline)


# ---------------------------------------------------------------------------
# Universal Scriptwriter Compatibility (YT Trends & Niche)
# ---------------------------------------------------------------------------

def validate_universal_script(
    result: dict,
    *,
    headline_required: bool = True,
    language: str | None = None,
) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    scenes = result.get("script")
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        return False, "Universal Scriptwriter must return 3–5 slides."

    subject = _clean(result.get("subject_name"))
    if not subject:
        return False, "The Scriptwriter must identify the main subject."

    language_key = str(language or result.get("language_used") or "english").strip().casefold()
    first_words = _words(
        scenes[0].get("voiceover")
        if isinstance(scenes[0], dict)
        else ""
    )
    if language_key not in {"hindi", "telugu", "hi", "te"} and first_words > MAX_SLIDE_ONE_WORDS:
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
    narration_normalised = _normalise(narration)

    for phrase in FILLER_PHRASES:
        if _normalise(phrase) in narration_normalised:
            return False, "The narration contains filler or retention bait."

    total_words = _words(narration)
    if total_words < MIN_WORDS:
        return False, "Narration is too short to reach the 18-second minimum without padding."
    if total_words > MAX_WORDS:
        return False, "Narration must stay under 30 seconds."

    subject_normalised = _normalise(subject)
    if subject_normalised and subject_normalised not in narration_normalised:
        return False, "The main subject is not named in the spoken narration."

    headline = _clean(result.get("headline"))
    if headline_required and not headline:
        return False, "The opening headline is required."

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



_validate_story_angles = _validate_cricket_story_angles


def suggest_universal_story_angles(
    story,
    language: str = "english",
    search_query: str | None = None,
    profile: str = "niche_sports",
) -> dict:
    source = _research_story(story)
    if not source:
        source = _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    norm_profile = _normalize_profile(profile)
    language_key = str(language or "english").strip().lower()
    instruction = (
        UNIVERSAL_ANGLE_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )
    if norm_profile == "otd":
        instruction += (
            "\n\nON THIS DAY HISTORICAL ANGLES:\n"
            "Propose retrospective/throwback editorial angles grounded in the anniversary: "
            "1. The Unbelievable Feat (how the record/victory was achieved against the odds), "
            "2. The Turning Point (how this day changed the player's career or team's destiny), "
            "3. The Enduring Legacy (why this milestone is still celebrated decades later)."
        )
    if str(search_query or "").strip():
        instruction += (
            "\n\nPRIMARY YOUTUBE SEARCH QUERY:\n"
            + str(search_query).strip()
            + "\nUse this as search-intent context, not as a factual source."
        )
    errors = []

    for model in MODELS:
        try:
            result = _request(
                model,
                instruction,
                source,
                schema=ANGLE_SCHEMA,
                schema_name="universal_story_angles",
                max_completion_tokens=900,
            )
            valid, reason = _validate_story_angles(result)
            if valid:
                return {
                    "angles": result["angles"],
                    "source_evidence": source,
                    "source_title": _story_value(story, "title"),
                    "search_query": str(search_query or "").strip(),
                    "language_used": language_key,
                    "provider_used": model,
                }
            errors.append(f"{model}: {reason}")
        except GroqAPIError as exc:
            errors.append(f"{model}: {exc}")
            if 400 <= exc.status_code < 500 and exc.status_code != 429:
                raise RuntimeError(
                    "Groq rejected the universal story-angle request: " + str(exc)
                ) from exc
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "Universal story-angle generation failed: " + " | ".join(errors)
    )


def write_universal_script(
    story,
    language: str = "english",
    angle=None,
    research_source: str | None = None,
    search_query: str | None = None,
    profile: str = "niche_sports",
) -> dict:
    source = research_source or _research_story(story)
    if not source:
        source = _source_text(story)
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    norm_profile = _normalize_profile(profile)
    language_key = str(language or "english").strip().lower()
    angle_text = _angle_text(angle)
    if angle_text:
        source = _supplement_research_for_angle(story, angle_text, source)
    instruction = (
        UNIVERSAL_SYSTEM_PROMPT
        + "\n\n"
        + DESK_PROMPTS.get(norm_profile, DESK_PROMPTS["niche_sports"])
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )
    if str(search_query or "").strip():
        instruction += (
            "\n\nPRIMARY YOUTUBE SEARCH QUERY:\n"
            + str(search_query).strip()
            + "\nThis is the search-intent target for packaging. Keep the story factual and do not distort the editorial angle to force the phrase."
        )
    if angle_text:
        instruction += (
            "\n\nSELECTED EDITORIAL ANGLE (AUTHORITATIVE):\n"
            + angle_text
            + "\nBuild the whole narration around this lens. Explore the debate, comparison, or insight posed by this angle using the context and domain knowledge. Do not replace it with the obvious event/result summary."
        )
    else:
        instruction += (
            "\n\nNO USER ANGLE SELECTED:\n"
            "Choose the strongest evidence-backed editorial angle yourself and keep the entire Short centered on it."
        )

    errors = []
    recovery_reason = ""
    for model in MODELS:
        model_instruction = instruction
        if recovery_reason:
            model_instruction += (
                "\nRECOVERY:\n"
                "The previous draft was rejected by local validation. "
                "Rewrite the complete package now. Fix the exact failure below "
                "while preserving every other hard rule and all supported facts. "
                "Return only the complete JSON package.\n"
                f"Validation failure: {recovery_reason}"
            )
        try:
            result = _request(model, model_instruction, source)
        except GroqAPIError as exc:
            errors.append(f"{model}: {exc}")
            if 400 <= exc.status_code < 500 and exc.status_code != 429:
                raise RuntimeError(
                    "Groq rejected the universal Scriptwriter request; no recovery prompt was sent: "
                    + str(exc)
                ) from exc
            continue
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
            continue

        if angle_text:
            result["story_angle"] = angle_text
        valid, reason = validate_universal_script(result, language=language_key)
        if valid:
            return _finish_result(
                result,
                story,
                source,
                model,
                language_key,
                angle_text=angle_text,
                search_query=search_query,
                delivery_profile=(
                    "UNIVERSAL SPORTS"
                    if norm_profile in {"niche_sports", "universal"}
                    else DESK_PROFILES.get(norm_profile, "UNIVERSAL SPORTS")
                ),
                desk_profile=norm_profile,
            )
        recovery_reason = reason
        errors.append(f"{model}: {reason}")

    raise RuntimeError(
        "Universal sports script generation failed: " + " | ".join(errors)
    )



def apply_universal_script_edits(
    script: dict,
    voiceovers: list[str],
    headline: str | None = None,
) -> dict:
    return _apply_edits_helper(script, voiceovers, headline=headline)


# ---------------------------------------------------------------------------
# Top-5 Multi-Story Scriptwriter Functions
# ---------------------------------------------------------------------------

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


def _is_package_opener_headline(headline: str) -> bool:
    clean = _clean(headline)
    return all(
        re.search(pattern, clean, re.IGNORECASE)
        for pattern in PACKAGE_OPENER_PATTERNS
    )


def _contains_slide_1_filler(headline: str) -> bool:
    clean = _clean(headline)
    return any(re.search(pattern, clean, re.IGNORECASE) for pattern in SLIDE_1_FILLER_PATTERNS)


def validate_top5_script(result: dict, stories: list[dict]) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no Top-5 script object."
    if len(stories) != 5:
        return False, "Top-5 Scriptwriter requires exactly five selected stories."

    slides = result.get("slides")
    if not isinstance(slides, list) or len(slides) != 6:
        return False, "Top-5 Scriptwriter must return exactly six slides."

    total_estimated_speech = 0.0
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
        total_estimated_speech += estimate_speech_seconds(headline)
        if _contains_forbidden_editorial_language(headline) or _contains_slide_1_filler(headline):
            return False, f"Slide {expected_number} contains audience-facing or synthetic filler language."

        for key in ("primary_entity", "visual_intent", "specific_search_prompt", "sport_or_topic_category"):
            if not _clean(slide.get(key)):
                return False, f"Slide {expected_number} is missing {key}."

        if expected_number == 1:
            if _words(headline) > SLIDE_1_MAX_WORDS:
                return False, f"Slide 1 exceeds {SLIDE_1_MAX_WORDS} words."
            if not _is_package_opener_headline(headline):
                return False, "Slide 1 must be a Top-5 Cricket News package headline."
            if any(
                _clean(other.get("headline")).casefold() == headline.casefold()
                for other in slides[1:]
            ):
                return False, "Slide 1 cannot duplicate a story headline."
            body = _clean(slide.get("body"))
            if not body:
                return False, "Slide 1 must contain visual-only body copy."
        else:
            body = _clean(slide.get("body"))

    if total_estimated_speech > MAX_TOP5_TOTAL_SPEECH_SECONDS:
        return False, (
            f"Top-5 spoken headlines exceed {MAX_TOP5_TOTAL_SPEECH_SECONDS:.0f} seconds "
            "at the speech-rate estimate."
        )

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
        instruction = TOP5_SYSTEM_PROMPT + "\n\n" + LANGUAGE_PROMPT
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
        except GroqAPIError as exc:
            errors.append(f"{model}: {exc}")
            if 400 <= exc.status_code < 500 and exc.status_code != 429:
                raise RuntimeError("Groq rejected the Top-5 Scriptwriter request: " + str(exc)) from exc
            continue
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
            continue

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

    raise RuntimeError("Top-5 script generation failed: " + " | ".join(errors))


class ScriptWriter:
    """Unified Scriptwriter for Final-Shorts.

    Powers all desks and production lines with broadcast-grade 20-30s news article Shorts:
    - cricket_india_asia (Subcontinental Cricket Desk)
    - cricket_global (International Cricket Correspondent)
    - niche_sports (High-Energy Multi-Sport Desk)
    - youtube_trends (YouTube Search Trends Desk)
    - otd (On This Day Historical Milestone Desk)
    - top_5 (Top-5 6-Slide Daily Roundup Desk)
    """

    DESK_PROFILES = DESK_PROFILES

    @classmethod
    def write(
        cls,
        story,
        profile: str = "cricket_india_asia",
        language: str = "english",
        angle=None,
        research_source: str | None = None,
        search_query: str | None = None,
        **kwargs,
    ) -> dict:
        norm = _normalize_profile(profile)
        if norm == "top_5":
            if isinstance(story, list):
                return generate_top5_script(story)
            raise ValueError("Top-5 scriptwriter requires a list of 5 stories.")

        if norm in {"cricket_india_asia", "cricket_global"}:
            return write_script(
                story=story,
                language=language,
                angle=angle,
                research_source=research_source,
                profile=norm,
            )
        else:
            return write_universal_script(
                story=story,
                language=language,
                angle=angle,
                research_source=research_source,
                search_query=search_query,
                profile=norm,
            )

    @classmethod
    def suggest_angles(
        cls,
        story,
        profile: str = "cricket_india_asia",
        language: str = "english",
        search_query: str = "",
    ) -> dict:
        norm = _normalize_profile(profile)
        if norm in {"cricket_india_asia", "cricket_global"}:
            return suggest_cricket_story_angles(story, language=language, search_query=search_query)
        else:
            return suggest_universal_story_angles(
                story,
                language=language,
                search_query=search_query,
                profile=norm,
            )

    @classmethod
    def apply_edits(
        cls,
        script: dict,
        voiceovers: list[str],
        headline: str | None = None,
        profile: str = "cricket_india_asia",
    ) -> dict:
        norm = _normalize_profile(profile)
        if norm in {"cricket_india_asia", "cricket_global"}:
            return apply_script_edits(script, voiceovers, headline=headline)
        else:
            return apply_universal_script_edits(script, voiceovers, headline=headline)

    @classmethod
    def evaluate_flow(cls, script: dict) -> dict:
        return evaluate_flow(script)

