"""Function 02B: niche-sports Shorts script writing."""

import json
import os

import requests

from script_writer import (
    GROQ_URL,
    LANGUAGE_INSTRUCTIONS,
    MODELS,
    TIMEOUT,
    _research_story,
    _source_text,
    _story_value,
)

NICHE_SCHEMA = {
    "type": "object",
    "properties": {
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


def _validate_script(result: dict) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    headline = " ".join(str(result.get("headline") or "").split())
    if not 3 <= len(headline.split()) <= 4:
        return False, "The opening headline must contain 3 or 4 words."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or not all(str(item or "").strip() for item in titles):
        return False, "The Niche Sports Scriptwriter must produce exactly 3 titles."

    description = " ".join(str(result.get("seo_description") or "").split())
    if not 15 <= len(description.split()) <= 30:
        return False, "The Niche Sports SEO description must contain 15–30 words."

    hashtags = result.get("hashtags")
    if (
        not isinstance(hashtags, list)
        or not 3 <= len(hashtags) <= 5
        or any(
            not str(tag or "").strip().startswith("#")
            or " " in str(tag or "").strip()
            for tag in hashtags
        )
    ):
        return False, "The Niche Sports Scriptwriter must produce 3–5 valid hashtags."

    if not str(result.get("comment") or "").strip():
        return False, "The Niche Sports Scriptwriter must produce a public comment."

    scenes = result.get("script")
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 5:
        return False, "Niche Sports Scriptwriter must return 4 or 5 scenes."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not str(scene.get("voiceover") or "").strip():
            return False, f"Scene {number} is empty or malformed."
        for key in (
            "primary_entity",
            "visual_intent",
            "specific_search_prompt",
            "sport_or_topic_category",
        ):
            if not str(scene.get(key) or "").strip():
                return False, f"Scene {number} is missing {key}."

    total_words = sum(len(str(scene.get("voiceover") or "").split()) for scene in scenes)
    if total_words > 75:
        return False, "Niche Sports narration exceeds the 75-word hard cap."

    first = " ".join(str((scenes[0] or {}).get("voiceover") or "").split()).casefold()
    if len(first.split()) > 14:
        return False, "Scene 1 exceeds 14 words."
    if any(first.startswith(opener) for opener in GENERIC_OPENERS):
        return False, "Scene 1 starts with a generic opener."

    narration = " ".join(
        " ".join(str(scene.get("voiceover") or "").split()).casefold()
        for scene in scenes
        if isinstance(scene, dict)
    )
    if any(phrase in narration for phrase in RETENTION_BAIT):
        return False, "The narration contains retention bait."

    return True, ""


def _request(model: str, prompt: str, source: str) -> dict:
    key = str(os.getenv("GROQ_API_KEY") or "").strip()
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
                    "name": "niche_sports_shorts_script",
                    "strict": True,
                    "schema": NICHE_SCHEMA,
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


def apply_niche_script_edits(
    script: dict,
    voiceovers: list[str],
    headline: str | None = None,
) -> dict:
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited slides does not match the generated Niche Sports script.")
    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = " ".join(str(voiceover or "").split())
    if headline is not None:
        result["headline"] = " ".join(str(headline or "").split())

    valid, reason = _validate_script(result)
    if not valid:
        raise ValueError(f"Edited Niche Sports script failed local validation: {reason}")

    result["human_script_edited"] = any(
        " ".join(str(scene.get("voiceover") or "").split())
        != " ".join(str(original.get("voiceover") or "").split())
        for scene, original in zip(scenes, script.get("script") or [])
    )
    result["approved_for_audio"] = True
    return result


NICHE_SYSTEM_PROMPT = """You are the original editorial writer for a human-reviewed niche-sports YouTube Shorts channel.

Your job is to turn the strongest supported development in the selected niche-sports story into a fast, vivid, spoken Short. Do not summarize the article mechanically.

SOURCE DISCIPLINE
- Use only facts supported by the supplied story evidence.
- Never invent scores, rankings, records, quotes, motives, injuries, penalties, results, schedules, statistics or consequences.
- Treat the selected article as the primary evidence. Do not silently fill gaps from general sports knowledge.
- If the article reports someone's claim, reaction or statement, attribute it naturally.
- Never turn an allegation, prediction or expectation into a confirmed fact.
- Never copy a complete source sentence.

FIRST SILENTLY CLASSIFY THE STORY
Choose the dominant event type before writing:
- RESULT / UPSET
- RECORD / BREAKTHROUGH
- INJURY / WITHDRAWAL
- SELECTION / OMISSION
- DEBUT / COMEBACK / RETIREMENT
- PENALTY / CONTROVERSY
- CONTRACT / TEAM / COACHING CHANGE
- QUALIFICATION / ELIMINATION
- ANNOUNCEMENT / STATEMENT
- OTHER CONCRETE DEVELOPMENT

Then build the Short around:
1. WHAT HAPPENED — the strongest confirmed development.
2. WHY IT MATTERS — the immediate sporting significance.
3. PROOF — the score, margin, time, position, record, opponent, round, event, penalty, ranking or other concrete fact that makes the story specific.
4. WHAT NEXT — the latest confirmed status or consequence.

NICHE-SPORTS EDITORIAL STYLE
- One persona: HYPE COMMENTATOR — energetic, sharp and confident, but credible.
- Sound like a strong digital sports desk update, not an article being read aloud.
- Write for the ear: active voice, short clean sentences, concrete verbs and natural spoken rhythm.
- Energy must come from the sporting fact, not generic hype.
- Never use cricket-specific framing or vocabulary unless the selected story is actually about cricket.
- Do not assume that every sport is a match. Respect the sport's actual event structure.
- Do not force a winner, turning point or comeback into a story that does not contain one.
- Do not force statistics. Use a number when it materially explains the story.
- Avoid generic filler such as "the sports world", "fans will be watching", "this is a huge moment", "a major update", "things could change", or "what happens next remains to be seen" unless the evidence itself makes that wording necessary.
- Avoid article-style chronology when the chronology is not the story.
- Every sentence should either deliver the news, sharpen its significance, prove the claim, or close the loop.

SPORT-SPECIFIC FACT PRIORITIES
Use these only when the source supplies them. Never invent missing fields.

RACKET SPORTS — tennis, badminton, squash, table tennis:
- Prefer opponent + round/stage + result/score + decisive fact.
- For rankings, seeds or qualification, state the exact supported ranking/seed and why it matters.
- For injury or withdrawal stories, make the status and affected event clear.

MOTORSPORT — Formula 1, MotoGP and other racing:
- Prefer finishing position, qualifying/pole position, race/stage, incident, penalty, retirement/DNF, points or championship consequence when supported.
- Distinguish qualifying, sprint, race and championship standings.
- Never describe a driver as "winning" if the source only reports a pole, podium or provisional result.

ATHLETICS / SWIMMING / CYCLING:
- Prefer event + place + mark/time/distance + record or personal-best status when supported.
- For cycling, distinguish stage result from overall/general-classification status.
- For track or field events, do not confuse heat/qualifying/final with the final result.

COMBAT SPORTS — boxing, wrestling and related:
- Prefer opponent + bout/event + result + method/decision/round when supported.
- Distinguish title fights from non-title bouts and confirmed results from scheduled fights.
- Never infer a knockout, stoppage or judging detail that the source does not state.

TEAM SPORTS — hockey, basketball, volleyball, kabaddi:
- Prefer teams + score/result + competition/stage + decisive performer or sequence when supported.
- For volleyball, preserve set-score information when it is central.
- For tournaments, distinguish a single match result from qualification or title status.

GOLF:
- Prefer tournament + round + position + score relative to par/leader when supported.
- Distinguish a round lead from winning the tournament.

CHESS:
- Prefer opponent + event/round + result + concrete turning point only if the source provides it.
- Do not invent moves, openings or tactical explanations.

HOOK
- Scene 1 is a cold open, not an article lead.
- Target 6–8 spoken words and keep the hook at or below 3 seconds of estimated natural speech.
- Hard maximum 14 words remains a structural ceiling, but the 3-second time limit is the real hook constraint.
- Choose the strongest truthful form for this particular event:
  - result or upset;
  - record or breakthrough;
  - consequence;
  - unexpected supported detail;
  - concrete problem or withdrawal;
  - penalty or decision.
- Make the sport/event understandable immediately when needed.
- Create curiosity through a real information gap, not fake suspense.
- Never start with "Today...", "Here is the latest...", "X is...", or a generic sport introduction when a sharper fact exists.
- Do not ask a generic question merely to create curiosity.

STORY FLOW
- Use exactly 4 or 5 narration scenes.
- Scene 1 = HOOK: strongest concrete fact.
- Scene 2 = DEVELOPMENT: immediately add a new, specific fact that changes or sharpens the story.
- Middle scene(s) = CONTEXT / ESCALATION: give only the sporting context needed to understand the significance.
- Final scene = CONSEQUENCE: state the latest confirmed status, qualification effect, ranking consequence, next event, recovery status, or other concrete outcome when supported.
- Every scene must add new information. No scene may simply restate the previous one.
- Prefer 4 strong scenes when a fifth would only pad the story.

PACING
- Target roughly 22–27 seconds.
- Never exceed 30 seconds.
- Aim for roughly 55–68 spoken words, with the existing 75-word hard cap.
- Do not pad a short source to reach a target word count.

RETENTION WITHOUT BAIT
- No CTA, "keep watching", "stay tuned", "wait for it", "don't scroll", "don't skip", "watch till the end", "you won't believe", "find out later" or similar viewer-directed bait.
- The next sentence should feel necessary because the facts create a real unresolved point.

VISUAL HANDOFF
- Every scene needs a supported primary visual entity, visual intent, specific search prompt and sport/topic category.
- Match the visual entity to the scene's actual subject: athlete, opponent, team, venue, event, car, track, trophy, coach or other identifiable subject.
- Make search prompts concrete and sport-aware.
- Never use vague prompts such as "dramatic sports moment".
- Do not invent a visual moment that the article does not support.

PUBLISH METADATA
- Generate exactly one factual 3- or 4-word opening headline.
- Generate exactly 3 concise Shorts title candidates:
  1. direct event/result angle;
  2. consequence/context angle;
  3. curiosity angle grounded in a specific supported fact.
- Each title must contain a key person, team, competition, event or distinctive term from the selected story.
- Avoid generic phrases such as "latest update", "breaking news", "big update", "sports update" or "what you need to know".
- Generate a concise 15–30 word SEO description naming the key subject/event and what happened or why it matters.
- Generate 3–5 relevant hashtags.
- Generate one story-specific public-upload comment question tied to a concrete fact.

FINAL EDITOR CHECK
- Is the story understandable without the article?
- Is Scene 1 specific rather than generic?
- Does Scene 2 introduce genuinely new information?
- Does every middle scene earn its place?
- Are sport-specific facts used correctly and only when supported?
- Does the final scene close the central question with a confirmed status or consequence?
- Does it sound natural aloud?
- Could any sentence be deleted without losing the story?
- Is every claim grounded in the supplied evidence?
- Return only JSON matching the existing schema.

LANGUAGE
Follow the requested language exactly. Preserve the same factual, compact editorial principles in English, Hindi or Telugu.
"""

def write_niche_sports_script(story, language: str = "english") -> dict:
    """Generate one niche-sports Shorts script without changing the Cricket writer."""
    source = _research_story(story)
    has_story_url = bool(_story_value(story, "url"))
    if not source and not has_story_url:
        source = _source_text(story)
    if not source:
        if has_story_url:
            raise RuntimeError(
                "Story research failed: the selected article could not be extracted "
                "and no corroborating full article was reachable."
            )
        raise ValueError("The selected story contains no usable evidence.")

    language_key = str(language or "english").strip().lower()
    instruction = (
        NICHE_SYSTEM_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(language_key, LANGUAGE_INSTRUCTIONS["english"])
    )

    errors = []
    recovery_reason = ""
    for model in MODELS:
        try:
            model_instruction = instruction
            if recovery_reason:
                model_instruction += (
                    "\nRECOVERY:\n"
                    "The previous draft failed local validation. Regenerate the complete JSON "
                    "while fixing this exact failure and preserving every other hard rule. "
                    f"Validation failure: {recovery_reason}"
                )

            result = _request(model, model_instruction, source)
            valid, reason = _validate_script(result)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "NICHE SPORTS"
                result["language_used"] = language_key
                result["source_title"] = _story_value(story, "title")
                result["source_evidence"] = source
                return result
            recovery_reason = reason
            errors.append(f"{model}: {reason}")
        except Exception as exc:
            recovery_reason = f"{type(exc).__name__}: {exc}"
            errors.append(f"{model}: {recovery_reason}")

    raise RuntimeError("Niche sports script generation failed: " + " | ".join(errors))
