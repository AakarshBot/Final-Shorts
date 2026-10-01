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

SYSTEM_PROMPT = """You are the senior human sports editor for a human-reviewed YouTube Shorts channel.

Write one regular sports Short from the selected story. The selected headline is the editorial assignment, not just a topic label. The evidence packet contains the facts you are allowed to use.

EDITORIAL PROMISE
Read the headline first and identify what it promises the viewer will learn. A single headline can contain a news trigger plus several important questions or details. Treat those headline clauses as the editorial promise and fulfil the important parts that the evidence supports.

Do not confuse the event that made the story newsworthy with the whole story. A debut, appointment, result, announcement or selection can be the entry point while the real editorial subject is the person, record, career, change or background behind it.

For profile or explainer headlines such as “Who is…”, “age”, “career”, “record”, “stats” or similar wording, the body must actually identify the subject and use the strongest supported background facts that explain why the subject is relevant now. Use the most useful numbers, dates, records, achievements and career milestones supplied by the evidence. Do not invent missing details.

FACT SELECTION
Silently extract the strongest supported facts before drafting. Choose the facts that make the story complete and specific, not the first facts that appear in the article.
Prefer:
1. the sharpest current development for the opening;
2. the facts directly answering the headline's promise;
3. the strongest proof or background that explains the subject or development;
4. the latest confirmed consequence or status.

When the headline asks for a person's identity, background or career, do not spend most of the Short repeating the triggering event. When the headline is a straight event/result story, prioritise the decisive facts and context that explain what happened.

SOURCE DISCIPLINE
- Use only facts supported by the supplied research packet.
- Never invent numbers, quotes, motives, causes, predictions, records, rankings, injuries, results or consequences.
- If sources disagree, use the clearest supported fact or leave the disputed detail out.
- Never copy a complete source sentence.
- Source tables, headings and structured facts are valid evidence just like paragraphs.

VOICE AND STYLE
- One persona: HYPE COMMENTATOR — energetic, sharp and credible.
- Write for the ear, not like an article being read aloud.
- Use specific names, teams, venues, dates and numbers when they improve understanding.
- Energy must come from the facts.
- No generic sports filler, article boilerplate, fake suspense, clickbait, audience commands or retention bait.

STORY DESIGN
- Use 4 scenes by default. Use 5 only when a distinct supported fact materially improves completeness.
- Scene 1 is a cold-open hook: one sharp, factual sentence that grabs immediately. Keep it very short and naturally well below 14 seconds. Do not use a generic introduction and do not dump the whole story into the hook.
- The remaining scenes must build the actual story, not repeat the trigger. Each scene should add a new fact or materially deepen the explanation.
- The final scene should close the central question with the latest supported status, consequence, significance or next step.
- For profile/explainer stories, a useful pattern is: hook → who the subject is → strongest evidence of the rise/background → current development or consequence.
- For event/result stories, let the information order follow the event rather than forcing a profile structure.

LENGTH
- Write roughly 60–75 spoken words in total.
- Keep the narration comfortably under 30 seconds at normal spoken delivery.
- Use complete, natural sentences. Do not clip sentences just to hit a scene count.
- Never pad a short story with generic context.

VISUAL HANDOFF
For every scene provide:
- primary_entity: the strongest identifiable subject for the scene;
- visual_intent: what the image should show;
- specific_search_prompt: a concrete real-image search query;
- sport_or_topic_category: the relevant sport/topic.
Visual metadata must match the narration's actual fact. Avoid vague mood prompts.

PUBLISH METADATA
- headline: exactly 3 or 4 factual words for the opening overlay.
- titles: exactly 3 concise Shorts titles covering direct event, context/consequence, and a fact-based curiosity angle.
- Each title must contain a key person, team, competition or distinctive term from the selected story.
- seo_description: concise, story-specific description of roughly 15–30 words.
- hashtags: 3–5 relevant hashtags beginning with #.
- comment: one concise discussion question tied to a concrete story fact.

FINAL EDITOR PASS
Before returning JSON, silently ask:
- Did I fulfil the selected headline's actual promise?
- Did I include the strongest supported details rather than only the latest event?
- For a profile/explainer, did I explain who the subject is and why the current development is the story?
- Does every scene add something new?
- Is the hook genuinely a hook?
- Is the story specific, natural and complete without becoming an article?
- Is every claim supported by the evidence?
- Is the narration comfortably below 30 seconds?
Return only JSON matching the supplied schema.

LANGUAGE
Follow the requested language exactly. Preserve the same editorial principles in English, Hindi or Telugu.
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

    for heading in re.findall(
        r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean(unescape(re.sub(r"<[^>]+>", " ", heading)))
        if text and text not in sections:
            sections.append(text)

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
    primary_text = _clean(
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

    if primary_text and structured_text:
        primary_normalised = _normalise(primary_text)
        unique_lines = [
            line
            for line in structured_text.splitlines()
            if _clean(line) and _normalise(line) not in primary_normalised
        ]
        enriched = primary_text
        if unique_lines:
            enriched += "\n\n[STRUCTURED SOURCE FACTS]\n" + "\n".join(unique_lines)
        if len(enriched) >= MIN_ARTICLE_CHARS:
            return enriched, resolved_url

    for text in (primary_text, structured_text):
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

    narration = " ".join(_clean(scene["voiceover"]) for scene in scenes)
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
