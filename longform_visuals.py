"""Automated Visual Matching and Collection Engine for Long-form Cricket Documentaries.

Executes end-to-end visual sourcing, entity verification, card composition,
and asset assignment without requiring manual visual QC.
Integrates with visual_search.py, visual_generator.py, and longform_cards.py.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import re
from typing import Any, Callable

from PIL import Image, UnidentifiedImageError

from longform_cards import (
    render_longform_stat_card,
    render_longform_quote_card,
    render_longform_h2h_card,
    render_longform_milestone_card,
    render_longform_chapter_card,
    render_longform_timeline_card,
)
from visual_search import search_images
from visual_generator import generate_images


MIN_WIDTH = 1200
MIN_HEIGHT = 650
MAX_CONCURRENT_SEARCHES = 6


def _clean(val: object) -> str:
    return re.sub(r"\s+", " ", str(val or "")).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z]{3,}\b", str(text or "").casefold()))


def _image_valid_and_hires(data: bytes) -> tuple[bool, int, int]:
    if not data or len(data) < 15_000:
        return False, 0, 0
    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            if w >= MIN_WIDTH and h >= MIN_HEIGHT:
                return True, w, h
            # Accept if high resolution portrait (e.g. 1080x1920) that can cover 16:9
            if w * h >= 850_000:
                return True, w, h
            return False, w, h
    except (UnidentifiedImageError, OSError, ValueError):
        return False, 0, 0


def _entity_matches(asset_title: str, asset_url: str, required_entity: str) -> bool:
    """Verifies that the image metadata actually contains the required person/team."""
    if not required_entity or len(required_entity.strip()) < 3:
        return True
    req_tokens = _tokens(required_entity)
    text_tokens = _tokens(asset_title) | _tokens(asset_url)

    # If full name provided, at least one distinctive token must match (e.g. "Bumrah")
    common_words = {"cricket", "india", "test", "match", "team", "bcci"}
    distinct_req = req_tokens - common_words
    if distinct_req:
        return bool(distinct_req & text_tokens)
    return bool(req_tokens & text_tokens)


def _score_asset(asset: dict, required_entity: str, intent: str) -> float:
    score = 5.0
    title = str(asset.get("title") or "").casefold()
    source = str(asset.get("source") or "").casefold()

    # Priority source boost
    if source in ("commons", "wikipedia"):
        score += 3.0
    elif source == "flickr":
        score += 1.5

    # Entity presence
    if _entity_matches(title, asset.get("source_page_url", ""), required_entity):
        score += 6.0
    else:
        score -= 4.0

    # Intent boost
    intent_terms = {
        "press_conference": ("press", "conference", "interview", "speaking", "mic", "announces"),
        "match_action": ("bowling", "batting", "action", "wicket", "delivery", "shot", "catch"),
        "player_portrait": ("portrait", "headshot", "profile", "close", "player"),
        "stadium_atmosphere": ("stadium", "pitch", "ground", "crowd", "wankhede", "lords", "melbourne", "floodlights"),
        "trophy_celebration": ("trophy", "cup", "celebration", "champions", "victory"),
    }
    if intent in intent_terms:
        if any(term in title for term in intent_terms[intent]):
            score += 3.5

    return score


def _fetch_pollinations_ai_image(prompt: str) -> bytes | None:
    """Legacy helper name; use the shared free-first generator for a landscape image.

    The previous implementation called an undefined _pollinations symbol,
    swallowed the NameError, and silently fell back to generic chapter cards.
    The shared generator uses AI Horde by default and never calls metered services
    unless the user explicitly enables them.
    """
    try:
        result = generate_images(
            f"Cinematic 16:9 documentary broadcast photo: {prompt}, natural stadium lighting",
            orientation="landscape",
            timeout_seconds=120,
        )
        assets = result.get("assets") or []
        if assets:
            return assets[0].get("bytes")
    except Exception:
        pass
    return None


class LongformVisualMatcher:
    """Automated visual collector and card assembler for Long-form documentaries."""

    @classmethod
    def match_and_collect(
        cls,
        script_data: dict,
        story: dict,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        scenes = list(script_data.get("scenes") or [])
        if not scenes:
            raise ValueError("No scenes found in script data for visual collection.")

        def log(msg: str):
            if status_callback:
                status_callback(msg)

        log("Formulating targeted visual search queries across documentary scenes...")

        # 1. Gather all unique queries
        queries_to_run = set()
        for sc in scenes:
            if sc.get("search_query"):
                queries_to_run.add(_clean(sc["search_query"]))
            if sc.get("card_required_subject"):
                queries_to_run.add(f"{_clean(sc['card_required_subject'])} cricket portrait")
        queries_to_run.add(f"{_clean(story.get('title'))} cricket")
        queries_to_run.add("cricket stadium floodlights night 16:9 pitch")

        # 2. Parallel Search
        log(f"Searching open repositories across {len(queries_to_run)} targeted queries...")
        all_assets: list[dict] = []
        seen_hashes: set[str] = set()

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SEARCHES) as executor:
            futures = {executor.submit(search_images, q): q for q in queries_to_run}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    for asset in res.get("assets", []):
                        h = str(asset.get("hash") or "")
                        data = asset.get("bytes")
                        if h and h not in seen_hashes and data:
                            valid, _, _ = _image_valid_and_hires(data)
                            if valid:
                                seen_hashes.add(h)
                                all_assets.append(asset)
                except Exception:
                    continue

        log(f"Verified {len(all_assets)} high-resolution images from open sources.")

        # 3. Match and Assign Assets Scene-by-Scene
        assigned_scenes = []
        used_hashes: set[str] = set()
        ai_fallback_cache: dict[str, bytes | None] = {}

        for sc in scenes:
            sc_num = sc["scene_number"]
            v_type = sc.get("visual_type", "photo_kenburns")
            c_type = sc.get("card_type", "none")
            entity = sc.get("card_required_subject") or sc.get("primary_entity") or ""
            intent = sc.get("visual_intent", "match_action")

            # Score all available unused assets for this scene
            candidates = [a for a in all_assets if a["hash"] not in used_hashes]
            candidates.sort(key=lambda a: _score_asset(a, entity, intent), reverse=True)

            chosen_asset = candidates[0] if candidates else None
            chosen_bytes = chosen_asset.get("bytes") if chosen_asset else None
            if chosen_asset:
                used_hashes.add(chosen_asset["hash"])

            # Render only evidence-backed card payloads. If a requested card lacks
            # its factual inputs, show a chapter card instead of invented values,
            # an invented quotation, or a generic controversy narrative.
            rendered_frame_bytes = None
            if v_type == "card" or c_type != "none":
                card_data = sc.get("card_payload") or {}
                if not isinstance(card_data, dict):
                    card_data = {}
                card_img = None
                card_error = None
                try:
                    if c_type == "Stat Highlight":
                        card_img = render_longform_stat_card(chosen_bytes, {
                            "player_name": entity,
                            "eyebrow": card_data.get("eyebrow") or "MATCH DATA",
                            "hero_stat": card_data.get("hero_stat") if card_data.get("hero_stat") is not None else card_data.get("stat"),
                            "stat_label": card_data.get("stat_label") or card_data.get("metric"),
                            "context_note": card_data.get("context_note") or card_data.get("note") or "",
                            "tiles": card_data.get("tiles") or card_data.get("metrics") or [],
                        })
                    elif c_type == "Quote / Reaction":
                        card_img = render_longform_quote_card(chosen_bytes, {
                            "quote": card_data.get("quote_text") or card_data.get("quote") or "",
                            "speaker": card_data.get("speaker") or card_data.get("attribution") or "",
                            "role": card_data.get("speaker_role") or card_data.get("role") or "",
                            "eyebrow": card_data.get("eyebrow") or "QUOTED STATEMENT",
                        })
                    elif c_type == "Head-to-Head":
                        card_img = render_longform_h2h_card(chosen_bytes, {
                            "headline": card_data.get("headline") or "HEAD-TO-HEAD COMPARISON",
                            "left_name": card_data.get("h2h_left_name") or card_data.get("left_name") or "",
                            "right_name": card_data.get("h2h_right_name") or card_data.get("right_name") or "",
                            "metrics": card_data.get("metrics") or card_data.get("comparisons") or [],
                        })
                    elif c_type == "Key Fact / Milestone":
                        card_img = render_longform_milestone_card(chosen_bytes, {
                            "title": card_data.get("milestone_title") or card_data.get("title") or "",
                            "milestone": card_data.get("milestone_badge") or card_data.get("milestone") or "",
                            "subtitle": card_data.get("subtitle") or "",
                            "bullets": card_data.get("bullets") or ([card_data["bullet_1"]] if card_data.get("bullet_1") else []),
                        })
                    elif c_type == "Timeline / Chronology":
                        card_img = render_longform_timeline_card(chosen_bytes, {
                            "headline": card_data.get("headline") or "CHRONOLOGY OF EVENTS",
                            "nodes": card_data.get("nodes") or card_data.get("events") or [],
                        })
                    elif c_type == "Chapter / Act":
                        card_img = render_longform_chapter_card(chosen_bytes, {
                            "act": f"ACT {sc.get('act_number', 1):02d}",
                            "title": sc.get("chapter_title") or entity or story.get("title") or "CHAPTER",
                            "premise": sc.get("voiceover", "")[:120],
                        })
                except Exception as exc:
                    card_error = exc

                if card_img is None:
                    if card_error is not None:
                        log(
                            f"Scene {sc_num}: {type(card_error).__name__} while preparing "
                            f"{c_type or 'visual'}; using an evidence-safe chapter card."
                        )
                    card_img = render_longform_chapter_card(chosen_bytes, {
                        "act": f"ACT {sc.get('act_number', 1):02d}",
                        "title": sc.get("chapter_title") or entity or story.get("title") or "CHAPTER",
                        "premise": sc.get("voiceover", "")[:120],
                    })

                buf = io.BytesIO()
                card_img.save(buf, format="JPEG", quality=95)
                rendered_frame_bytes = buf.getvalue()

            # Fallback if no real photo found and not a card: generate AI photo or default card
            if not chosen_bytes and not rendered_frame_bytes:
                # Repeated entity/intent pairs share one generated fallback within
                # this run; do not call the image service repeatedly for the same prompt.
                ai_prompt = f"{entity} {intent} cricket"
                if ai_prompt not in ai_fallback_cache:
                    ai_fallback_cache[ai_prompt] = _fetch_pollinations_ai_image(ai_prompt)
                ai_data = ai_fallback_cache[ai_prompt]
                if ai_data:
                    chosen_bytes = ai_data
                else:
                    # Render chapter card as clean broadcast graphic
                    c_card = render_longform_chapter_card(None, {
                        "act": f"ACT {sc.get('act_number', 1):02d}",
                        "title": entity.upper(),
                        "premise": sc.get("voiceover", "")[:120],
                    })
                    buf = io.BytesIO()
                    c_card.save(buf, format="JPEG", quality=95)
                    rendered_frame_bytes = buf.getvalue()

            assigned_scenes.append({
                "scene_number": sc_num,
                "act_number": sc.get("act_number", 1),
                "voiceover": sc.get("voiceover", ""),
                "primary_entity": entity,
                "visual_type": "card" if rendered_frame_bytes else "photo_kenburns",
                "card_type": c_type,
                "image_bytes": rendered_frame_bytes or chosen_bytes,
                "image_source": "Long-form card renderer" if rendered_frame_bytes else (chosen_asset.get("source") if chosen_asset else "AI-generated (free-first provider)"),
                "image_title": chosen_asset.get("title") if chosen_asset else f"Scene {sc_num} visual",
            })

        log(f"Successfully matched and verified all {len(assigned_scenes)} documentary scenes.")
        return {
            "scenes_visuals": assigned_scenes,
            "total_scenes": len(assigned_scenes),
            "pool_size": len(all_assets),
            "cards_count": sum(1 for s in assigned_scenes if s["visual_type"] == "card"),
            "photos_count": sum(1 for s in assigned_scenes if s["visual_type"] == "photo_kenburns"),
        }


__all__ = ["LongformVisualMatcher"]
