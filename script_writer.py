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
CRICKET_RESEARCH_MAX_ARTICLES = 2
CRICKET_RESEARCH_CANDIDATE_LIMIT = 6
CRICKET_RESEARCH_PRIMARY_CHARS = 9000
CRICKET_RESEARCH_REPORT_CHARS = 5500
CRICKET_RESEARCH_MAX_PACKET_CHARS = 22000
MIN_ARTICLE_CHARS = 600
SCENE_1_MAX_WORDS = 14
HOOK_MAX_SECONDS = 3.0
SPEECH_WORDS_PER_MINUTE = 170.0
MAX_ESTIMATED_NARRATION_SECONDS = 30.0
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

Your job is NOT to summarize one article mechanically. Your job is to identify what this story is actually about, decide what a viewer needs to understand, and turn the most important supported information into a fast, vivid, spoken Short. The Short must feel complete, not merely current.

Use only the supplied research evidence. The packet may contain the selected story, a primary article, and up to two independent reports. Treat the primary article as the main source; use independent reports to confirm facts, resolve missing details, establish what changed, and add outside context only when that context materially improves the Short.

Never invent facts, quotes, motives, numbers, predictions, outcomes or causal claims. Never use outside knowledge that is not supported by the supplied evidence. If sources disagree, do not silently merge them: use the clearest supported version, attribute the disagreement when it matters, or omit the disputed detail. Never copy a complete source sentence.

RESEARCH-TO-STORY CHECK
Before writing, silently build the story map from the evidence:
1. What is the actual editorial promise of the selected story or headline?
2. What important questions would a viewer reasonably expect this Short to answer?
3. What are the 4–7 most useful supported facts needed to answer those questions?
4. Which facts are essential, which are supporting detail, and which are safe to leave out?
5. What is the latest confirmed development, status or consequence?
6. What single fact makes the story worth covering now?

Do not confuse the latest event with the whole story. A recent debut, appointment, result or announcement may be the trigger for the story without being the complete subject of it.

EDITORIAL STORY MAP
Silently classify the story by its information shape, based on the evidence rather than by a fixed template. Examples include:
- event/result: what happened → decisive detail → context/significance → current consequence
- profile/breakout: who the subject is → why they are relevant now → evidence of the rise/record → current development
- record/milestone: what was achieved → the exact proof → comparison or context → current significance
- appointment/transfer: what changed → who/what is involved → relevant background → why it matters → next status
- rule/policy change: what changed → what it replaces/affects → who is affected → when/how it applies
- injury/availability: what happened → confirmed status → relevant context → practical consequence
- other: derive the clearest information order from the source itself

The examples are guidance, not mandatory buckets. Choose the structure that best answers the story's actual editorial promise.

COMPLETENESS RULE
Treat the selected headline, subheadline and article structure as an editorial contract. If the source asks or strongly signals “who”, “what”, “how”, “why”, “age”, “record”, “career”, background, or another specific question, the narration must answer the important part of that question when the research evidence supports it.

For profile or explainer stories, do not spend most of the Short repeating the triggering event. The triggering event explains why the story is newsworthy; the body should explain the person, achievement, change or background that makes the story meaningful.

Do not include every fact in the article. Select the facts that materially improve understanding. The goal is a complete Short, not a compressed article dump.
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
- Do not open with a generic subject introduction when a sharper fact exists. But when the story itself is a profile, explainer or “who is this person?” piece, the subject’s identity and relevant background are core story information, not filler.

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
- Use 4 narration scenes by default. Use a 5th scene only when a distinct, verified fact materially improves the story; never create a fifth scene just to add structure.
- Scene 1 = HOOK: strongest concrete fact, tension point or sharply framed answer.
- Scene 2 = the first major piece of explanation that the viewer needs in order to understand the story. It must add a new fact, not restate Scene 1.
- Middle scenes = the strongest supporting evidence, context, background, record, comparison, reaction or explanation required by the story's editorial promise.
- Final scene = CONSEQUENCE / PAYOFF: close the central question with the latest confirmed status, significance, consequence or next step supported by the evidence.
- Do not force the same HOOK → DEVELOPMENT → CONTEXT → CONSEQUENCE shape onto every story. The information order must follow the story map.
- Every scene must add a meaningful new piece of information or materially sharpen the viewer's understanding. A scene that only repeats the debut/result/announcement is filler and should be rewritten.
- For profile/breakout stories, the body should normally contain the subject's relevant background or proven achievement before returning to the current development.
- For records, transfers, appointments, rule changes and similar stories, include the specific evidence that explains why the headline matters.
- Use useful numbers, dates, scores, records, fees, milestones, rankings, venues, roles or other precise facts whenever they materially improve understanding and are supported by the evidence.
- Do not force a twist or artificial stakes.
PACING AND LENGTH
- The finished narration must remain under 30 seconds. The existing hard ceiling and time estimator are authoritative.
- Aim for roughly 62–72 spoken words so the Short has enough room to tell the actual story. Do not deliberately compress every scene into a fragment.
- A 5-scene script still has to fit the same overall time budget as a 4-scene script.
- Each scene should carry substantive information in natural spoken sentences. Do not make a scene artificially tiny just to hit a scene count.
- Never pad with generic context just to hit a word count.
- Never rely on audio speed correction to rescue an overlong draft.
DO NOT USE RETENTION BAIT
- No CTA, "keep watching", "stay tuned", "wait for it", "don't scroll", "don't skip", "watch till the end", "you won't believe", "find out later", "we'll reveal", "here's why" or similar viewer-directed bait.
- Curiosity must come from the facts and the way they are sequenced, not from promises to the viewer.

VISUAL HANDOFF
- Every scene must include a supported primary visual entity, visual intent, specific search prompt and sports category.
- The visual entity should be the strongest identifiable subject for that scene, usually a player, team, coach, venue or event.
- The search prompt must describe a concrete thing a real-image search can plausibly find. Avoid vague mood prompts such as "dramatic cricket moment".
- Keep visual metadata subordinate to the narration: first make the spoken story strong, then make the visual fields useful.
- Visual prompts must reflect the exact scene fact whenever possible: for example, a training incident, match result, trophy, lineup, venue or player action—not generic player portraits when the scene is about a specific event.

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
- Does the narration fulfil the selected story's actual editorial promise?
- Can a viewer understand not only what happened, but the important information that explains what it is, who is involved, why it matters or what changed?
- If the headline or article is a profile/explainer, have you answered the important subject/background question instead of spending the Short on the triggering event alone?
- Does every scene contribute a new, useful fact?
- Are the strongest supported details from the research represented, rather than only the first and most recent facts?
- Is the latest status or consequence clear when one exists?
- Is every claim supported by the supplied research packet?
- Has any detail been included merely because it was available, rather than because it improves understanding?
- Would removing any sentence make the story meaningfully less complete?
- Is the narration comfortably within 30 seconds without making the scenes feel like clipped fragments?
- Would this sound natural spoken aloud?
- Is there any sentence that sounds like a news article instead of a person talking?
- Is there any generic filler that can simply be deleted?
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


def _limit_source_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> str:
    lines = [
        _clean(line)
        for line in str(text or "").splitlines()
        if _clean(line)
    ]
    clean = "\n".join(lines)
    max_chars = max(1000, int(max_chars))
    if len(clean) <= max_chars:
        return clean

    head = int(max_chars * 0.55)
    middle = int(max_chars * 0.25)
    tail = max_chars - head - middle
    middle_start = max(0, (len(clean) - middle) // 2)
    middle_end = middle_start + middle
    return (
        clean[:head].rstrip()
        + "\n\n[ARTICLE MIDDLE]\n\n"
        + clean[middle_start:middle_end].strip()
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
                stack.extend(
                    value
                    for value in item.values()
                    if isinstance(value, (dict, list))
                )
            elif isinstance(item, list):
                stack.extend(item)

    for paragraph in re.findall(
        r"<p\b[^>]*>(.*?)</p>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean(unescape(re.sub(r"<[^>]+>", " ", paragraph)))
        if text and text not in sections:
            sections.append(text)

    for table in re.findall(
        r"<table\b[^>]*>(.*?)</table>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, flags=re.IGNORECASE | re.DOTALL):
            cells = [
                _clean(unescape(re.sub(r"<[^>]+>", " ", cell)))
                for cell in re.findall(
                    r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>",
                    row,
                    flags=re.IGNORECASE | re.DOTALL,
                )
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
            include_tables=True,
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


def _cricket_research_candidates(story_title: str, original_url: str) -> list[dict]:
    query = _clean(story_title)
    original_domain = _source_domain(original_url)
    keywords = _story_title_keywords(query)
    minimum_overlap = 2 if len(keywords) >= 2 else 1
    blocked_domains = (
        "twitter.", "x.com", "facebook.", "instagram.", "youtube.", "google."
    )

    raw_results = []
    try:
        raw_results = list(
            DDGS(timeout=5).news(
                query=query,
                region="in-en",
                safesearch="off",
                timelimit="w",
                max_results=8,
            )
            or []
        )
    except Exception:
        raw_results = []

    candidates = []
    seen_urls = set()
    seen_domains = set()
    for result in raw_results:
        url = _clean(result.get("url") or result.get("href"))
        title = _clean(result.get("title"))
        if not url or url == original_url:
            continue

        domain = _source_domain(url)
        if not domain or domain == original_domain:
            continue
        if any(blocked in domain for blocked in blocked_domains):
            continue

        overlap = len(keywords & _story_title_keywords(title))
        similarity = SequenceMatcher(
            None,
            _normalise(query),
            _normalise(title),
        ).ratio()
        if keywords and overlap < minimum_overlap and similarity < 0.38:
            continue

        canonical = url.rstrip("/").casefold()
        if canonical in seen_urls or domain in seen_domains:
            continue

        seen_urls.add(canonical)
        seen_domains.add(domain)
        candidates.append(
            {
                "title": title,
                "url": url,
                "domain": domain,
                "score": overlap * 2.0 + similarity,
            }
        )

    if not candidates:
        try:
            raw_results = list(
                DDGS(timeout=5).text(
                    query=query,
                    region="in-en",
                    safesearch="off",
                    timelimit="w",
                    max_results=8,
                )
                or []
            )
        except Exception:
            raw_results = []

        seen_urls.clear()
        seen_domains.clear()
        candidates = []
        for result in raw_results:
            url = _clean(result.get("url") or result.get("href"))
            title = _clean(result.get("title"))
            if not url or url == original_url:
                continue

            domain = _source_domain(url)
            if not domain or domain == original_domain:
                continue
            if any(blocked in domain for blocked in blocked_domains):
                continue

            overlap = len(keywords & _story_title_keywords(title))
            similarity = SequenceMatcher(
                None,
                _normalise(query),
                _normalise(title),
            ).ratio()
            if keywords and overlap < minimum_overlap and similarity < 0.38:
                continue

            canonical = url.rstrip("/").casefold()
            if canonical in seen_urls or domain in seen_domains:
                continue

            seen_urls.add(canonical)
            seen_domains.add(domain)
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "score": overlap * 2.0 + similarity,
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:CRICKET_RESEARCH_CANDIDATE_LIMIT]


def _research_story(story, profile: str | None = None) -> str:
    title = _story_value(story, "title")
    description = _story_value(story, "description")
    original_url = _story_value(story, "url")

    if profile == "cricket":
        sections = []
        if title:
            sections.append(f"[SELECTED STORY]\n{title}")

        primary = ""
        resolved_primary_url = original_url
        if original_url:
            try:
                primary, resolved_primary_url = _extract_article(original_url)
            except (requests.RequestException, OSError, ValueError):
                primary = ""

        if primary:
            sections.append(
                f"[PRIMARY ARTICLE — {resolved_primary_url or original_url}]\n"
                f"{_limit_source_text(primary, CRICKET_RESEARCH_PRIMARY_CHARS)}"
            )

        independent = []
        if title:
            for candidate in _cricket_research_candidates(title, original_url):
                if len(independent) >= CRICKET_RESEARCH_MAX_ARTICLES:
                    break

                candidate_url = candidate["url"]
                if (
                    resolved_primary_url
                    and _source_domain(candidate_url) == _source_domain(resolved_primary_url)
                ):
                    continue

                try:
                    extracted, resolved_url = _extract_article(candidate_url)
                except (requests.RequestException, OSError, ValueError):
                    continue

                if not extracted:
                    continue

                if any(
                    _source_domain(resolved_url) == _source_domain(item["url"])
                    for item in independent
                ):
                    continue

                independent.append(
                    {
                        "title": candidate["title"],
                        "url": resolved_url or candidate_url,
                        "text": extracted,
                    }
                )

            for number, article in enumerate(independent, 1):
                sections.append(
                    f"[INDEPENDENT REPORT {number} — "
                    f"{article['title']} — {article['url']}]\n"
                    f"{_limit_source_text(article['text'], CRICKET_RESEARCH_REPORT_CHARS)}"
                )

        if description:
            sections.append(f"[TOPIC FETCHER SUMMARY]\n{description}")

        return _limit_source_text(
            "\n\n".join(sections),
            CRICKET_RESEARCH_MAX_PACKET_CHARS,
        )

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

        return _limit_source_text(
            f"[SELECTED STORY]\n{title}\n\n"
            f"[TOPIC FETCHER SUMMARY]\n{description}"
        )

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
    narration = " ".join(_clean(scene["voiceover"]) for scene in scenes)
    word_count = _words(narration)
    if word_count > MAX_WORDS:
        return False, "The narration is likely longer than 30 seconds."
    estimated_seconds = estimate_spoken_seconds(narration)
    if estimated_seconds > MAX_ESTIMATED_NARRATION_SECONDS:
        return False, (
            "The narration exceeds the writer's estimated time ceiling "
            f"({estimated_seconds:.2f}s)."
        )
    for previous, current in zip(scenes, scenes[1:]):
        previous_text = _normalise(previous.get("voiceover"))
        current_text = _normalise(current.get("voiceover"))
        if (
            _words(previous_text) >= 7
            and _words(current_text) >= 7
            and SequenceMatcher(None, previous_text, current_text).ratio() >= 0.90
        ):
            return False, "Adjacent scenes repeat the same narration."
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
    """Generate one regular Cricket Shorts script and return its later-stage metadata too."""
    source = _research_story(story, profile="cricket")
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
                result["word_count"] = _words(
                    " ".join(
                        _clean(scene.get("voiceover"))
                        for scene in result.get("script") or []
                    )
                )
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
