"""Function 02: sports Shorts script writing."""

import json
import os
import re
from html import unescape
from pathlib import Path
from difflib import SequenceMatcher

import requests
import trafilatura
from ddgs import DDGS
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
TIMEOUT = 30
RESEARCH_TIMEOUT = 10
MAX_SOURCE_CHARS = 12000
MIN_ARTICLE_CHARS = 600
SCENE_1_MAX_WORDS = 14
HOOK_MAX_SECONDS = 3.0
SPEECH_WORDS_PER_MINUTE = 170.0
MAX_WORDS = 75

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all narration and publish metadata in punchy, natural spoken English.",
    "hindi": "Write all narration and publish metadata in natural spoken Hindi using Devanagari script.",
    "telugu": "Write all narration and publish metadata in natural spoken Telugu using Telugu script.",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "titles": {"type": "array", "items": {"type": "string"}},
        "seo_description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "comment": {"type": "string"},
        "script": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "voiceover": {"type": "string"},
                    "narrative_role": {
                        "type": "string",
                        "enum": ["hook", "development", "context", "consequence"],
                    },
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
        "headline",
        "titles",
        "seo_description",
        "hashtags",
        "comment",
        "script",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the original editorial writer for a human-reviewed cricket and sports YouTube Shorts channel.

Your job is NOT to summarize the article. Your job is to turn the strongest supported development in the selected story into a fast, vivid, spoken Short that earns the next sentence.

Use only the supplied story evidence. Prefer the primary article evidence when available; use corroborating evidence only when it supports the same event. Never invent facts, quotes, motives, numbers, predictions, outcomes or causal claims. Never copy a complete source sentence.

EDITORIAL SPINE
Before writing the JSON, silently identify:
1. THE STORY ENGINE — the single most interesting confirmed development in the evidence.
2. THE STAKES — what changed, what is now at risk, or why the timing matters.
3. THE ESCALATION — the strongest new fact that makes the situation more interesting.
4. THE PAYOFF — the concrete latest status, consequence or answer supported by the evidence.

Build the narration around that spine. Do not narrate the source article mechanically from first event to last unless that chronology is itself the interesting part.

SHORTS STYLE
- This is a regular sports Short. Do not write Top-5, Deep-Dive or list content.
- One persona: HYPE COMMENTATOR — energetic, sharp and confident, but credible. Sound like a strong cricket/sports desk update, not an article being read aloud.
- Write for the ear. Prefer active voice, concrete verbs, specific names and crisp sentence rhythm.
- Vary sentence length. A longer factual sentence can be followed by a short punch.
- Use natural spoken pivots such as "But", "And", "That matters because", or a clean contrast when the evidence supports the shift.
- Specificity is the source of energy: prefer the actual player, team, venue, score, date, opponent, number, record or consequence from the evidence over vague wording.
- Never add drama words that are not earned by the facts.
- Do not use generic sports narration such as "this is a big update", "fans will be watching", "this is a major development", "the cricket world", "things could change", or "a huge moment" unless the evidence itself establishes something similar.
- Do not use filler transitions such as "meanwhile", "in other news", "as we know", "of course", "needless to say", or "here is what happened".
- Do not open with a generic subject introduction. Open on the most interesting supported fact, tension point, reversal, result, record, decision or consequence.

HOOK
- Scene 1 is the Short's cold open, not an article lead.
- Target 6–8 spoken words and keep the hook at or below 3 seconds of estimated natural speech.
- Hard maximum 14 words remains a structural ceiling, but the 3-second time limit is the real hook constraint.
- Choose the strongest truthful hook type for the story:
  - result-first: lead with the result or decision;
  - consequence-first: lead with what the development affects;
  - unexpected-detail: lead with the unusual or surprising supported detail;
  - tension-first: lead with the concrete problem and its timing.
- State enough of the fact to be understandable immediately, but do not dump the whole story into Scene 1.
- The hook may create a natural information gap, but it must not use fake suspense, withheld essentials, audience commands or clickbait.
- Do not ask a generic question just to create curiosity.
- Do not start with "Shubman Gill is...", "India are...", "Today...", or similar boilerplate when a sharper fact is available.

STORY FLOW
- Use exactly 4 or 5 narration scenes.
- Scene 1 = HOOK: strongest concrete fact/tension.
- Scene 2 = DEVELOPMENT / RE-HOOK: immediately add a new specific detail. It should make the story more consequential, clearer or more surprising than Scene 1. Never merely restate the hook.
- Middle scene(s) = CONTEXT / ESCALATION: explain the relevant circumstance, timing, result, record, opposition, selection consequence, reaction, or other fact that actually matters. Cut generic background.
- Final scene = CONSEQUENCE / PAYOFF: close the central question created by the story with the latest confirmed status or concrete consequence. Do not end on empty "key question" language when the evidence gives the answer.
- Every scene must add new information or materially sharpen the meaning of the previous scene.
- Keep the story moving. Each scene should make the next sentence feel necessary.
- When the evidence contains a useful number, time, margin, record or sequence, use it. Precision creates punch.
- When the story contains a clear contrast, use it naturally: expected vs actual, before vs after, selected vs ruled out, return vs setback, result vs consequence.
- Do not force a twist. Do not manufacture stakes when the story does not contain them.
- For very simple stories, prefer 4 strong scenes over padding to reach 5.

PACING AND LENGTH
- Target roughly 22–27 seconds of natural narration and never exceed 30 seconds.
- Aim for compact, information-dense narration rather than a mini article.
- As a guide, most successful drafts should land around 55–68 spoken words while remaining within the existing 75-word hard cap.
- Do not pad a short story with generic context just to hit a word count.
- Write sentences that sound natural at the current HYPE COMMENTATOR audio profile.

DO NOT USE RETENTION BAIT
- No CTA, "keep watching", "stay tuned", "wait for it", "don't scroll", "don't skip", "watch till the end", "you won't believe", "find out later", "we'll reveal", "here's why" or similar viewer-directed bait.
- Curiosity must come from the facts and the way they are sequenced, not from promises to the viewer.

VISUAL HANDOFF
- Every scene must include a supported primary visual entity, visual intent, specific search prompt and sports category.
- The visual entity should be the strongest identifiable subject for that scene, usually a player, team, coach, venue or event.
- The search prompt must describe a concrete thing a real-image search can plausibly find. Avoid vague mood prompts such as "dramatic cricket moment".
- Keep visual metadata subordinate to the narration: first make the spoken story strong, then make the visual fields useful.

PUBLISH METADATA
- Generate exactly one opening headline of strictly 3 or 4 words. It must be a concise, factual summary of the story and work as the renderer overlay.
- Generate exactly 3 YouTube Shorts title candidates tailored to this exact story. Make them meaningfully different:
  1. direct event/result angle;
  2. consequence/context angle;
  3. curiosity angle grounded in a specific supported fact.
- Each title must contain at least one key name, team, competition or distinctive term from the selected story title.
- Keep titles concise and natural. Avoid generic phrases such as "latest update", "big update", "breaking news", "sports update", or "what you need to know".
- Generate one concise, story-specific SEO description of roughly 15–30 words that names the key subject/event and explains what happened or why it matters.
- Generate 3–5 relevant hashtags, each beginning with #, with no spaces inside a hashtag.
- Generate one concise, story-specific public-upload comment that asks a natural discussion question tied to a concrete person, team, event or fact from the story.

FINAL EDITOR CHECK — apply silently before returning JSON
- Can a viewer understand the story from the narration alone?
- Does Scene 1 make me want the next sentence because of a real fact, not a gimmick?
- Does Scene 2 add a genuinely new detail?
- Is every middle scene earning its place?
- Does the final scene deliver a concrete status or consequence?
- Would this sound natural spoken aloud?
- Is there any sentence that sounds like a news article instead of a person talking?
- Is there any generic filler that can simply be deleted?
- Does the script stay strictly inside the supplied evidence?
- Return only JSON matching the supplied schema.

LANGUAGE
Follow the requested language exactly. Preserve the same editorial principles in English, Hindi, or Telugu.
"""
FORBIDDEN = (
    r"\bwait (?:until|till|for) (?:the )?end\b",
    r"\bwait for it\b",
    r"\bwatch (?:to|until|till) (?:the )?end\b",
    r"\bkeep watching\b",
    r"\bstay tuned\b",
    r"\bstick around\b",
    r"\bstay with (?:us|me)\b",
    r"\bdon['’]?t (?:go anywhere|scroll|skip)\b",
    r"\byou (?:won['’]?t|will not) believe\b",
    r"\byou['’]?ll never guess\b",
    r"\bfind out later\b",
    r"\bmore (?:on|about) (?:this|that) later\b",
    r"\blater in (?:the|this) (?:video|short)\b",
    r"\bwe(?:['’]?ll| will) (?:reveal|show|find out|get to)\b",
    r"\byou need to (?:see|watch) this\b",
    r"\bdon['’]?t blink\b",
    r"\bwatch what happens\b",
    r"\bsee what happens\b",
    r"\bbut that['’]?s not all\b",
    r"\bthat['’]?s not all\b",
    r"\bmore is coming\b",
    r"\bthe best part is still to come\b",
)

GENERIC_OPENERS = (
    "welcome to",
    "hey everyone",
    "hey guys",
    "in this video",
    "today we are going to",
    "let's talk about",
    "here is the latest",
)

GENERIC_METADATA_PHRASES = (
    "latest update",
    "latest news",
    "big update",
    "major update",
    "breaking update",
    "breaking news",
    "big news",
    "sports update",
    "what you need to know",
    "here's the latest",
    "here is the latest",
)

METADATA_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "before", "after",
    "about", "into", "over", "under", "when", "where", "will", "has", "have",
    "had", "its", "his", "her", "their", "they", "them", "your", "our",
    "new", "latest", "update", "news", "team", "match", "game", "sport",
    "sports", "vs", "versus",
}



def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value) -> int:
    return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", str(value or ""), flags=re.UNICODE))


def _normalise(value) -> str:
    return re.sub(r"[^\w ]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def estimate_spoken_seconds(text: str) -> float:
    clean = _clean(text)
    if not clean:
        return 0.0
    seconds = _words(clean) / (SPEECH_WORDS_PER_MINUTE / 60.0)
    seconds += 0.05 * len(re.findall(r"[,;:]", clean))
    seconds += 0.15 * len(re.findall(r"[.!?]", clean))
    seconds += 0.04 * len(re.findall(r"\b\w{10,}\b", clean, flags=re.UNICODE))
    return round(seconds, 3)


def _story_value(story, key: str) -> str:
    if hasattr(story, "__dataclass_fields__"):
        return _clean(getattr(story, key, ""))
    return _clean(dict(story or {}).get(key))


def _source_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def _limit_source_text(text: str) -> str:
    lines = [
        _clean(line)
        for line in str(text or "").splitlines()
        if _clean(line)
    ]
    clean = "\n".join(lines)
    if len(clean) <= MAX_SOURCE_CHARS:
        return clean
    head = int(MAX_SOURCE_CHARS * 0.72)
    tail = MAX_SOURCE_CHARS - head
    return clean[:head].rstrip() + "\n\n[ARTICLE CONTINUES]\n\n" + clean[-tail:].lstrip()


def _article_body_from_html(html_text: str) -> str:
    raw = str(html_text or "")

    for match in re.finditer(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
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
                if body:
                    return body
                stack.extend(
                    value
                    for value in item.values()
                    if isinstance(value, (dict, list))
                )
            elif isinstance(item, list):
                stack.extend(item)

    paragraphs = []
    for paragraph in re.findall(r"<p\b[^>]*>(.*?)</p>", raw, flags=re.IGNORECASE | re.DOTALL):
        text = _clean(unescape(re.sub(r"<[^>]+>", " ", paragraph)))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_article(url: str) -> tuple[str, str]:
    target = _clean(url)
    if not target:
        return "", ""

    response = requests.get(
        target,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0 Safari/537.36 Final-Shorts/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
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
            return text, resolved_url

    try:
        extracted = DDGS(timeout=5).extract(
            resolved_url,
            fmt="text_plain",
        )
        text = _clean(extracted.get("content") if isinstance(extracted, dict) else "")
        if len(text) >= MIN_ARTICLE_CHARS:
            return text, str(extracted.get("url") or resolved_url)
    except Exception:
        pass

    return "", resolved_url


def _fallback_article(story_title: str, original_url: str) -> tuple[str, str]:
    query = _clean(story_title)
    original_domain = _source_domain(original_url)
    if not query:
        return "", ""

    keywords = _story_title_keywords(query)
    minimum_overlap = 2 if len(keywords) >= 2 else 1
    blocked_domains = (
        "twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google."
    )

    def candidate_urls(results):
        candidates = []
        for result in results or []:
            url = _clean(result.get("url") or result.get("href"))
            title = _clean(result.get("title"))
            if not url or url == original_url:
                continue
            domain = _source_domain(url)
            if not domain or domain == original_domain:
                continue
            if any(blocked in domain for blocked in blocked_domains):
                continue
            candidate_keywords = _story_title_keywords(title)
            overlap = len(keywords & candidate_keywords)
            similarity = SequenceMatcher(
                None,
                _normalise(query),
                _normalise(title),
            ).ratio()
            if keywords and overlap < minimum_overlap and similarity < 0.35:
                continue
            candidates.append((overlap + similarity, url))
        return sorted(candidates, key=lambda item: item[0], reverse=True)

    try:
        search = DDGS(timeout=5)
        results = search.news(
            query=query,
            region="in-en",
            safesearch="off",
            timelimit="w",
            max_results=8,
        )
        candidates = candidate_urls(results)
    except Exception:
        candidates = []

    for _, url in candidates:
        try:
            extracted, resolved_url = _extract_article(url)
            if extracted:
                return extracted, resolved_url
        except (requests.RequestException, OSError, ValueError):
            continue

    try:
        results = DDGS(timeout=5).text(
            query=query,
            region="in-en",
            safesearch="off",
            timelimit="w",
            max_results=8,
        )
    except Exception:
        return "", ""

    for _, url in candidate_urls(results):
        try:
            extracted, resolved_url = _extract_article(url)
            if extracted:
                return extracted, resolved_url
        except (requests.RequestException, OSError, ValueError):
            continue

    return "", ""


def _research_story(story) -> str:
    title = _story_value(story, "title")
    description = _story_value(story, "description")
    original_url = _story_value(story, "url")

    if original_url:
        extracted, resolved_url = "", ""
        try:
            extracted, resolved_url = _extract_article(original_url)
        except (requests.RequestException, OSError, ValueError):
            extracted = ""

        if extracted:
            return _limit_source_text(
                f"[SELECTED STORY]\n{title}\n\n"
                f"[PRIMARY ARTICLE — {resolved_url or original_url}]\n{extracted}\n\n"
                f"[TOPIC FETCHER SUMMARY]\n{description}"
            )

        fallback, fallback_url = _fallback_article(title, original_url)
        if fallback:
            return _limit_source_text(
                f"[SELECTED STORY]\n{title}\n\n"
                f"[CORROBORATING ARTICLE — {fallback_url}]\n{fallback}\n\n"
                f"[TOPIC FETCHER SUMMARY]\n{description}"
            )

        return ""

    sections = []
    if title:
        sections.append(f"[SELECTED STORY]\n{title}")
    if description:
        sections.append(f"[TOPIC FETCHER SUMMARY]\n{description}")
    return _limit_source_text("\n\n".join(sections))


def _source_text(story) -> str:
    if hasattr(story, "__dataclass_fields__"):
        story = {name: getattr(story, name) for name in story.__dataclass_fields__}
    story = dict(story or {})

    parts = []
    seen = set()
    for key in (
        "title",
        "research_evidence_text",
        "text",
        "summary",
        "description",
        "topic",
    ):
        value = _clean(story.get(key))
        if not value:
            continue
        identity = _normalise(value)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        parts.append(value)

    return "\n\n".join(parts)[:MAX_SOURCE_CHARS]


def _copied(source, narration) -> bool:
    source_sentences = [
        _normalise(x)
        for x in re.split(r"(?<=[.!?])\s+|\n+", source)
        if _words(x) >= 8
    ]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", narration):
        candidate = _normalise(sentence)
        if _words(candidate) < 8:
            continue
        for original in source_sentences:
            if candidate == original or SequenceMatcher(None, candidate, original).ratio() >= 0.92:
                return True
    return False


def _story_title_keywords(source: str) -> set[str]:
    first_block = str(source or "").strip().split("\n\n", 1)[0]
    if first_block.startswith("[SELECTED STORY]"):
        title_part = first_block.split("\n", 1)[1] if "\n" in first_block else ""
    else:
        title_part = first_block
    words = re.findall(r"\b[\w]+\b", title_part.casefold(), flags=re.UNICODE)
    return {
        word
        for word in words
        if len(word) >= 3 and word not in METADATA_STOPWORDS
    }


def _metadata_mentions_story(text: str, source: str) -> bool:
    keywords = _story_title_keywords(source)
    if not keywords:
        return True
    normalised = _normalise(text)
    return any(keyword in normalised.split() for keyword in keywords)


def _metadata_is_generic_title(title: str) -> bool:
    normalised = _normalise(title)
    return any(phrase in normalised for phrase in GENERIC_METADATA_PHRASES)


def validate_script(result: dict, source: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "The provider returned no script object."

    headline = _clean(result.get("headline"))
    if not headline or _words(headline) not in (3, 4):
        return False, "The headline must contain exactly 3 or 4 words."

    titles = result.get("titles")
    if not isinstance(titles, list) or len(titles) != 3 or any(not _clean(x) for x in titles):
        return False, "Exactly three non-empty titles are required."
    normalised_titles = [_normalise(title) for title in titles]
    if len(set(normalised_titles)) != 3:
        return False, "The three Shorts titles must be different."

    story_relevant_titles = 0
    for title in titles:
        clean_title = _clean(title)
        if not 12 <= len(clean_title) <= 80:
            return False, "Each Shorts title must be between 12 and 80 characters."
        if _metadata_is_generic_title(clean_title):
            return False, "The Shorts title uses a generic metadata phrase."
        if _metadata_mentions_story(clean_title, source):
            story_relevant_titles += 1

    if story_relevant_titles < 2:
        return False, "At least two Shorts titles must reference the selected story."

    hashtags = result.get("hashtags")
    if (
        not isinstance(hashtags, list)
        or not hashtags
        or any(not _clean(x).startswith("#") for x in hashtags)
    ):
        return False, "At least one valid hashtag is required."

    comment = _clean(result.get("comment"))
    if not comment:
        return False, "A non-empty comment is required."
    if not _metadata_mentions_story(comment, source):
        return False, "The upload comment must reference the selected story."

    description = _clean(result.get("seo_description"))
    if _words(description) < 10:
        return False, "The SEO description is too short."
    if not _metadata_mentions_story(description, source):
        return False, "The SEO description must reference the selected story."

    scenes = result.get("script")
    if not isinstance(scenes, list) or len(scenes) not in (4, 5):
        return False, "A regular sports Short must contain 4 or 5 scenes."

    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            return False, f"Scene {number} is malformed."
        voiceover = _clean(scene.get("voiceover"))
        if not voiceover:
            return False, f"Scene {number} is empty."
        if not _clean(scene.get("primary_entity")):
            return False, f"Scene {number} is missing its primary visual entity."
        if not all(_clean(scene.get(key)) for key in (
            "visual_intent",
            "specific_search_prompt",
            "sport_or_topic_category",
        )):
            return False, f"Scene {number} is missing visual metadata."
        if any(re.search(pattern, voiceover, re.IGNORECASE) for pattern in FORBIDDEN):
            return False, f"Scene {number} contains retention bait."
        if number == 1 and voiceover.casefold().startswith(GENERIC_OPENERS):
            return False, "Scene 1 starts with a generic opener."

    roles = [str(scene.get("narrative_role") or "").strip().lower() for scene in scenes]
    if roles[0] != "hook" or roles[-1] != "consequence":
        return False, "The script must begin with a hook and end with a consequence."
    if not any(role in {"development", "context"} for role in roles[1:-1]):
        return False, "The middle needs a development or context scene."

    first_words = _words(scenes[0]["voiceover"])
    if first_words > SCENE_1_MAX_WORDS:
        return False, f"Scene 1 exceeds {SCENE_1_MAX_WORDS} words."
    hook_seconds = estimate_spoken_seconds(scenes[0]["voiceover"])
    if hook_seconds > HOOK_MAX_SECONDS:
        return False, (
            f"Scene 1 exceeds the 3-second hook limit "
            f"({hook_seconds:.2f}s estimated)."
        )

    narration = " ".join(_clean(scene["voiceover"]) for scene in scenes)
    if _words(narration) > MAX_WORDS:
        return False, "The narration is likely longer than 30 seconds."
    if _copied(source, narration):
        return False, "The narration is too close to source wording."

    return True, ""


def _request(model: str, prompt: str, story: str) -> dict:
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
            "temperature": 0.5,
            "max_completion_tokens": 900,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def write_script(story, language: str = "english") -> dict:
    """Generate one sports Shorts script and return its later-stage metadata too."""
    source = _research_story(story)
    if not source:
        fallback = _source_text(story)
        if _story_value(story, "title") and _story_value(story, "description"):
            source = fallback
    if not source:
        raise ValueError("The selected story contains no usable evidence.")

    instruction = (
        SYSTEM_PROMPT
        + "\nLANGUAGE:\n"
        + LANGUAGE_INSTRUCTIONS.get(
            str(language or "english").strip().lower(),
            LANGUAGE_INSTRUCTIONS["english"],
        )
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
            valid, reason = validate_script(result, source)
            if valid:
                result["provider_used"] = model
                result["delivery_profile"] = "HYPE COMMENTATOR"
                result["language_used"] = str(language or "english").strip().lower()
                result["source_title"] = _clean(
                    getattr(story, "title", "")
                    if hasattr(story, "__dataclass_fields__")
                    else dict(story or {}).get("title")
                )
                result["source_evidence"] = source
                return result
            recovery_reason = reason
            errors.append(f"{model}: {reason}")
        except Exception as exc:
            recovery_reason = f"{type(exc).__name__}: {exc}"
            errors.append(f"{model}: {recovery_reason}")

    raise RuntimeError("Script generation failed: " + " | ".join(errors))


def apply_script_edits(
    script: dict,
    voiceovers: list[str],
    headline: str | None = None,
    *,
    validate: bool = True,
) -> dict:
    """Apply optional human edits and re-run local script checks."""
    result = json.loads(json.dumps(script, ensure_ascii=False))
    scenes = result.get("script") or []
    if len(voiceovers) != len(scenes):
        raise ValueError("The number of edited scenes does not match the script.")

    for scene, voiceover in zip(scenes, voiceovers):
        scene["voiceover"] = _clean(voiceover)

    original_headline = _clean(script.get("headline"))
    if headline is not None:
        result["headline"] = _clean(headline)

    if validate:
        valid, reason = validate_script(result, _clean(result.get("source_evidence")))
        if not valid:
            raise ValueError(f"Edited script failed local validation: {reason}")

    result["human_script_edited"] = any(
        _clean(scene["voiceover"]) != _clean(original["voiceover"])
        for scene, original in zip(scenes, script.get("script", []))
    ) or (
        headline is not None
        and _clean(result.get("headline")) != original_headline
    )
    result["approved_for_audio"] = True
    return result
