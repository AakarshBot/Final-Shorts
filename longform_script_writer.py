"""Long-form Documentary Scriptwriter for Final-Shorts.

Engineered specifically for ~8-minute cricket video essays (~1,150 words).
Uses a structured 6-Act documentary narrative arc grounded in multi-source factual evidence.
Produces scene-by-scene voiceovers with explicit visual intent, primary entity tags,
card specifications, and YouTube chapter timestamps.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
TIMEOUT = 45
RESEARCH_TIMEOUT = 10
MAX_SOURCE_CHARS = 32000
WORDS_PER_MINUTE = 145.0
TARGET_DURATION_SECONDS = 480.0  # 8 minutes

LONGFORM_SYSTEM_PROMPT = """You are the lead cricket documentary director and investigative sports journalist for an authoritative, monetized YouTube channel.

YOUR MANDATE:
Write a complete, compelling ~8-minute cricket documentary script (~1,100 to 1,200 words) from the researched evidence.
The final video will be monetized on YouTube. It must NEVER sound robotic, templated, or mass-produced.
It must feel like an authored video essay (ESPN 30 for 30, The Athletic, Vox Sports) with authentic human storytelling, nuanced analysis, dramatic tension, and deep tactical understanding.

CRITICAL FACTUAL GROUNDING (ZERO HALLUCINATION):
- Real player names, match scores, series standings, venues, dates, and confirmed board decisions must be 100% grounded in the research packet.
- Never invent match scores, fake statistics, fabricated quotes, or imaginary injuries.
- If an allegation or rumor is reported, frame it accurately as reported controversy or debate.

DOCUMENTARY STRUCTURE (6 ACTS, ~22 TOTAL SCENES):
You must divide the story into exactly six narrative acts, each advancing the story:

1. ACT 01: THE INCITING HOOK (~140 words, 3 scenes)
   - Drop the viewer straight into the high-stakes dilemma, shocking development, or breaking conflict.
   - Establish what is on the line right now.

2. ACT 02: THE BACKSTORY & CONTEXT (~210 words, 4 scenes)
   - How did cricket reach this point? The preceding series, career trajectories, or systemic pressure.
   - Provide historical depth that casual fans do not know.

3. ACT 03: THE CATALYST & TURNING POINT (~210 words, 4 scenes)
   - Identify the best-documented turning point in the research packet. Never imply a private meeting, locker-room clash, injury, or selector dispute unless the packet contains evidence for it.
   - Explain what is confirmed, what is a reported allegation, and what is analysis.

4. ACT 04: STATISTICAL & TACTICAL DEEP-DIVE (~210 words, 4 scenes)
   - Use only statistics, comparisons, and financial details present in the research packet.
   - Use a Stat Highlight or Head-to-Head card only when its displayed values and labels are supported by that evidence. If the data is missing, use a chapter card or photo instead; never invent numbers to fill a layout.

5. ACT 05: THE CLIMAX & IMMEDIATE FALLOUT (~210 words, 4 scenes)
   - Include only reactions, decisions, match consequences, or fan response documented in the research packet.
   - Use a Quote / Reaction card only when the packet contains the exact quote and identifies the speaker. Never put a paraphrase in quotation marks or invent an official statement; if no verified quote exists, use a non-quote card or photo.

6. ACT 06: LEGACY & THE ROAD AHEAD (~140 words, 3 scenes)
   - Long-term implications for the team, player legacy, or world cricket governance.
   - Conclude with a thought-provoking perspective or open question for the viewer.

VISUAL METADATA REQUIREMENTS FOR EVERY SCENE:
For every scene, specify:
- `primary_entity`: The EXACT person/team that MUST appear in the visual (e.g., "Jasprit Bumrah", "Ajit Agarkar", "Wankhede Stadium").
- `secondary_entity`: Any secondary person/context.
- `visual_intent`: One of "match_action", "press_conference", "player_portrait", "stadium_atmosphere", "training_nets", "trophy_celebration", "controversy_walkoff".
- `visual_type`: "card" (for Stat/Quote/H2H/Milestone/Chapter cards), "photo_kenburns" (for high-res photos), or "ncr_broll" (for action footage).
- `card_type`: "none" if not a card, or one of "Stat Highlight", "Quote / Reaction", "Head-to-Head", "Key Fact / Milestone", "Chapter / Act", "Timeline / Chronology".
- `card_required_subject`: Exact person whose portrait is needed on the card.
- `card_payload`: Evidence-backed content only. Stat cards need a real metric and value; comparison cards need two named subjects and sourced comparable metrics; quote cards need exact quoted words plus a named speaker; timelines need at least two supported event nodes; milestones need a supported title and label. Leave unsupported payload fields empty and use `Chapter / Act` or `none` when the evidence is insufficient. Never fill these fields with plausible-looking defaults.
- `search_query`: High-precision search query for the visual engine (e.g., "Jasprit Bumrah bowling action Test match high resolution").

TONE & STYLE:
- Authoritative, intelligent, journalistic, and cinematic.
- Varied sentence structures: mix short punchy sentences with rhythmic analytical prose.
- Zero generic YouTube fluff: NEVER say "Hey guys welcome back", "Don't forget to like and subscribe", "In this video we will discuss", or "Let's dive right in".
- Write for the ear: spoken documentary cadence.
"""


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value: object) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _extract_article_text(url: str) -> str:
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            timeout=RESEARCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FinalShorts/1.0"},
        )
        if response.status_code == 200:
            text = trafilatura.extract(response.text, include_comments=False, include_tables=True)
            return _clean(text)
    except Exception:
        pass
    return ""


def _research_longform_story(story: dict) -> str:
    """Gathers comprehensive multi-source factual evidence for the long-form story."""
    sections: list[str] = []
    main_title = _clean(story.get("title"))
    main_url = _clean(story.get("url"))
    summary = _clean(story.get("summary"))

    sections.append(f"STORY TITLE: {main_title}")
    if summary:
        sections.append(f"DISCOVERY SUMMARY: {summary}")

    # 1. Primary article extraction
    if main_url:
        main_text = _extract_article_text(main_url)
        if main_text:
            sections.append(f"[PRIMARY SOURCE — {main_url}]\n{main_text[:12000]}")

    # 2. Clustered reports extraction (up to 3 alternate reports)
    reports = list(story.get("reports") or [])
    alt_urls = [r.get("url") for r in reports if r.get("url") and r.get("url") != main_url][:3]
    for idx, r_url in enumerate(alt_urls, 1):
        r_text = _extract_article_text(r_url)
        if r_text:
            sections.append(f"[RELATED REPORT {idx} — {r_url}]\n{r_text[:6000]}")

    # 3. Targeted DuckDuckGo News & Context Queries
    try:
        ddg_results = DDGS(timeout=5).text(f"{main_title} cricket details quotes", max_results=4) or []
        ddg_snippets = "\n".join(f"- {r.get('title')}: {r.get('body')}" for r in ddg_results if r.get("body"))
        if ddg_snippets:
            sections.append(f"[BACKGROUND CONTEXT & QUOTES]\n{ddg_snippets}")
    except Exception:
        pass

    return "\n\n".join(sections)[:MAX_SOURCE_CHARS]


def _request_groq(prompt: str, user_payload: str, model: str = MODELS[0]) -> dict:
    key = _clean(os.getenv("GROQ_API_KEY"))
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_payload},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.35,
        "max_completion_tokens": 6000,
    }

    for attempt in range(3):
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as exc:
            if attempt == 2:
                # Try fallback model if first model failed
                if model != MODELS[1]:
                    return _request_groq(prompt, user_payload, model=MODELS[1])
                raise RuntimeError(f"Groq API call failed for Long-form Scriptwriter: {exc}") from exc
            time.sleep(2 ** attempt)

    raise RuntimeError("Groq API failed to respond.")


class LongformScriptWriter:
    """Generates complete, monetizable 8-minute cricket video essays."""

    @staticmethod
    def write(story: dict, language: str = "english") -> dict:
        research_packet = _research_longform_story(story)
        user_prompt = (
            f"STORY HEADLINE: {story.get('title')}\n"
            f"KEY DEPTH SIGNALS: {', '.join(story.get('depth_signals', []))}\n\n"
            f"RESEARCH EVIDENCE PACKET:\n{research_packet}\n\n"
            f"INSTRUCTION: Write the complete 6-Act ~8-minute documentary script in {language.upper()} "
            f"as a valid JSON object matching the requested documentary structure."
        )

        raw_script = _request_groq(LONGFORM_SYSTEM_PROMPT, user_prompt)
        return LongformScriptWriter.validate_and_format(raw_script, story)

    @staticmethod
    def validate_and_format(data: dict, story: dict) -> dict:
        """Validates schema, calculates word pacing, and computes chapter timestamps."""
        acts = list(data.get("acts") or [])
        if not acts:
            raise ValueError("Script generation failed to produce acts.")

        total_words = 0
        all_scenes = []
        chapters = []
        cumulative_seconds = 0.0

        normalized_acts = []
        for act_index, act in enumerate(acts, 1):
            # Scene/act IDs are structural ordering, not model-authored content.
            # Reassign them from the actual list order to prevent duplicate or
            # contradictory IDs from misaligning visuals, audio and chapters.
            act_num = act_index
            ch_title = _clean(act.get("chapter_title")) or f"Chapter {act_num}"
            normalized_act = dict(act)
            normalized_act["act_number"] = act_num
            normalized_act["chapter_title"] = ch_title
            normalized_act["scenes"] = []
            normalized_acts.append(normalized_act)
            mins = int(cumulative_seconds // 60)
            secs = int(cumulative_seconds % 60)
            timestamp_str = f"{mins:02d}:{secs:02d}"

            chapters.append({
                "act_number": act_num,
                "title": ch_title,
                "timestamp": timestamp_str,
                "seconds": round(cumulative_seconds, 1),
            })

            scenes = list(act.get("scenes") or [])
            for scene in scenes:
                vo = _clean(scene.get("voiceover"))
                w_count = _words(vo)
                total_words += w_count
                scene_duration = round((w_count / WORDS_PER_MINUTE) * 60.0, 1)

                primary_entity = _clean(
                    scene.get("primary_entity")
                    or story.get("primary_entity")
                    or story.get("subject_name")
                    or story.get("title")
                )
                scene_formatted = {
                    "scene_number": len(all_scenes) + 1,
                    "act_number": act_num,
                    "chapter_title": ch_title,
                    "voiceover": vo,
                    "word_count": w_count,
                    "estimated_seconds": scene_duration,
                    "start_seconds": round(cumulative_seconds, 1),
                    "primary_entity": primary_entity,
                    "secondary_entity": _clean(scene.get("secondary_entity")),
                    "visual_intent": _clean(scene.get("visual_intent") or "match_action"),
                    "visual_type": _clean(scene.get("visual_type") or "photo_kenburns"),
                    "card_type": _clean(scene.get("card_type") or "none"),
                    "card_required_subject": _clean(scene.get("card_required_subject") or primary_entity),
                    "card_payload": scene.get("card_payload") if isinstance(scene.get("card_payload"), dict) else {},
                    "search_query": _clean(scene.get("search_query") or f"{primary_entity} cricket"),
                }
                all_scenes.append(scene_formatted)
                normalized_act["scenes"].append(scene_formatted)
                cumulative_seconds += scene_duration

        # Generate a description from verified metadata only. Do not claim wire
        # reporting unless publishers are actually present in the handoff.
        timestamp_lines = "\n".join(f"{ch['timestamp']} - {ch['title']}" for ch in chapters)
        source_names = []
        publisher = _clean(story.get("publisher"))
        if publisher:
            source_names.append(publisher)
        for report in story.get("reports") or []:
            if not isinstance(report, dict):
                continue
            report_source = _clean(report.get("publisher") or report.get("source"))
            if report_source and report_source.casefold() not in {name.casefold() for name in source_names}:
                source_names.append(report_source)
        sources_line = f"Sources: {', '.join(source_names)}\n" if source_names else ""
        seo_subject = _clean(data.get("subject_name") or story.get("primary_entity") or story.get("title") or "Cricket")
        seo_tag = re.sub(r"[^A-Za-z0-9]+", "", seo_subject) or "Cricket"
        desc = (
            f"{_clean(data.get('seo_description') or story.get('title'))}\n\n"
            f"CHAPTERS:\n{timestamp_lines}\n\n"
            f"{sources_line}"
            f"#Cricket #{seo_tag} #VideoEssay"
        )

        return {
            "title": _clean(data.get("title") or story.get("title")),
            "titles": list(data.get("titles") or [story.get("title")]),
            "subject_name": _clean(data.get("subject_name") or story.get("primary_entity") or story.get("title")),
            "core_conflict": _clean(data.get("core_conflict")),
            "seo_description": desc,
            "hashtags": list(data.get("hashtags") or ["#Cricket", "#CricketDocumentary", "#VideoEssay"]),
            "pinned_comment": _clean(data.get("pinned_comment") or "Which detail from this story matters most to you? Share your view below."),
            "total_words": total_words,
            "estimated_duration_seconds": round(cumulative_seconds, 1),
            "acts": normalized_acts,
            "chapters": chapters,
            "scenes": all_scenes,
            "scene_count": len(all_scenes),
        }


__all__ = ["LongformScriptWriter"]
