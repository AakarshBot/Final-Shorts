"""Function 04: direct web image retrieval for the selected sports story."""
from __future__ import annotations

import asyncio
import hashlib
import html
import io
import json
import os
import re
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from PIL import Image, UnidentifiedImageError


TARGET = 15
SUCCESS = 10
MAX_RELATED_PAGES = 10
PROFILE_PAGES = 4
PROFILE_IMAGES = 5
IMAGES_PER_PAGE = 6
MIN_SIDE = 500
MAX_IMAGE_BYTES = 8_000_000
SEARCH_RESULTS = 15
SEARCH_TIMEOUT = 8
PAGE_TIMEOUT_MS = 10_000
MAX_AGE_HOURS = 72
QUERY_COUNT = 3

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "from", "by", "with", "after", "before", "during", "over", "into",
    "about", "this", "that", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "has", "have", "had", "will", "would", "could",
    "should", "says", "said", "report", "reports", "latest", "news", "story",
    "update", "today", "ahead", "versus", "vs", "v", "video", "photos",
    "photo", "images", "image", "pictures", "picture",
    "survive", "survives", "suffer", "suffers", "faces", "face", "gets", "get",
    "appears", "announce", "announces", "likely", "may",
}

BLOCKED_HOSTS = {
    "facebook.com", "instagram.com", "x.com", "twitter.com",
    "youtube.com", "tiktok.com",
}

BAD_PATH_PARTS = {
    "/search", "/tag/", "/tags/", "/category/", "/categories/",
    "/author/", "/authors/", "/topic/", "/topics/", "/feed", "/rss", "/sitemap",
}

BAD_IMAGE_TERMS = {
    "logo", "icon", "favicon", "sprite", "tracking", "pixel", "avatar",
    "placeholder", "advert", "banner", "social-share", "share-image",
    "default-image",
}
ACTION_TERMS = {
    "action", "match", "game", "playing", "batting", "bowling", "fielding",
    "wicket", "goal", "scored", "tackle", "dribble", "serve", "race",
    "running", "sprint", "training", "celebrate", "celebration", "shoot",
    "shot", "save", "podium", "finish", "catch", "caught", "throw",
    "lifting",
}
HEADERS = {"User-Agent": "Final-Shorts/1.0 (web image retrieval)"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MANUAL_QUERY_MODEL = "openai/gpt-oss-20b"
MANUAL_QUERY_TIMEOUT = 20
MANUAL_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "historical": {"type": "boolean"},
        "queries": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 3,
        },
    },
    "required": ["historical", "queries"],
    "additionalProperties": False,
}


def _clean(value, limit=5000):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def _tokens(value):
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", _clean(value))
        if len(token) > 2 and token.casefold() not in STOPWORDS
    }


def _topic_value(story, key, fallback=""):
    if isinstance(story, dict):
        return _clean(story.get(key), 5000)
    return _clean(getattr(story, key, fallback), 5000)


def _parse_date(value):
    value = _clean(value, 200)
    if not value:
        return None
    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _usable_url(value):
    url = _clean(value, 3000)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _manual_query_plan(query):
    key = _clean(os.getenv("GROQ_API_KEY"), 300)
    if not key:
        return {"historical": False, "queries": [query]}

    prompt = """You are a sports web-image search planner.
Decide whether the query is name_only or contextual.

name_only means the user supplied only an entity/person/team name.
contextual means they added a specific event, object, action, milestone or occasion.

Rules:
- name_only: return exactly the original query and historical=false.
- contextual: return the original query plus up to two concise search variants using useful synonyms.
- Preserve every named entity and the user's intent.
- Do not invent dates, opponents, scores, events or other facts.
- Set historical=true for contextual searches so older publisher pages can be found.
- Queries should help find photographs on publisher/news pages.
- Return JSON only.
"""
    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MANUAL_QUERY_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": query},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "manual_visual_query_plan",
                        "strict": True,
                        "schema": MANUAL_QUERY_SCHEMA,
                    },
                },
                "include_reasoning": False,
                "reasoning_effort": "low",
                "temperature": 0.2,
                "max_completion_tokens": 220,
            },
            timeout=MANUAL_QUERY_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        plan = content if isinstance(content, dict) else json.loads(content)

        queries = []
        seen = set()
        for value in [query] + list(plan.get("queries") or []):
            value = _clean(value, 260)
            key = value.casefold()
            if value and key not in seen:
                queries.append(value)
                seen.add(key)
            if len(queries) >= 3:
                break

        return {
            "historical": bool(plan.get("historical")) and len(queries) > 1,
            "queries": queries or [query],
        }
    except Exception:
        return {"historical": False, "queries": [query]}


def build_queries(title, description="", entity=""):
    """Build the working crawler's exact-headline and entity/context lanes."""
    title = _clean(title, 260)
    entity = _clean(entity, 180)
    entity_tokens = _tokens(entity)

    distinctive = []
    seen = set()
    for token in re.findall(
        r"[A-Za-z0-9][A-Za-z0-9'’.-]*",
        _clean(f"{title} {description}", 1500),
    ):
        key = token.casefold()
        if len(token) <= 2 or key in STOPWORDS or key in entity_tokens or key in seen:
            continue
        seen.add(key)
        distinctive.append(token)
        if len(distinctive) >= 5:
            break

    queries = [title] if title else []
    if entity and distinctive:
        queries.extend((
            f"{entity} {' '.join(distinctive[:4])}",
            f"{entity} {' '.join(distinctive[:2])}",
        ))
    elif distinctive:
        queries.extend((
            " ".join(distinctive[:4]),
            " ".join(distinctive[:2]),
        ))
    elif entity:
        queries.append(entity)

    output = []
    seen_queries = set()
    for query in queries:
        query = _clean(query, 260)
        key = query.casefold()
        if query and key not in seen_queries:
            output.append(query)
            seen_queries.add(key)
        if len(output) >= QUERY_COUNT:
            break
    return output


def _age_hours(published_at, now):
    if published_at is None:
        return None
    return (now - published_at).total_seconds() / 3600.0


def _title_match(query, title, entity=""):
    q_tokens = _tokens(query)
    title_tokens = _tokens(title)
    if not q_tokens or not title_tokens:
        return 0.0
    overlap = len(q_tokens & title_tokens) / max(1, len(q_tokens))
    entity_tokens = _tokens(entity)
    entity_overlap = (
        len(entity_tokens & title_tokens) / max(1, len(entity_tokens))
        if entity_tokens else 1.0
    )
    if entity_tokens and entity_overlap < 0.75:
        return 0.0
    threshold = 0.82 if len(q_tokens) <= 4 else 0.58
    if overlap < threshold:
        return 0.0
    return min(1.0, overlap * 0.75 + entity_overlap * 0.25)


def _context_match(query, context, entity=""):
    query_tokens = _tokens(query)
    context_tokens = _tokens(context)
    entity_tokens = _tokens(entity)
    if not query_tokens or not context_tokens:
        return 0.0

    query_overlap = len(query_tokens & context_tokens) / len(query_tokens)
    if entity_tokens:
        entity_overlap = len(entity_tokens & context_tokens) / len(entity_tokens)
        if entity_overlap < 0.75 and not (
            len(entity_tokens & context_tokens) >= 1 and len(entity_tokens) >= 2
        ):
            return 0.0
    else:
        entity_overlap = 0.0

    threshold = 0.75 if len(query_tokens) <= 4 else 0.50
    if query_overlap < threshold:
        return 0.0
    return min(1.0, query_overlap * 0.80 + entity_overlap * 0.20)


def _related_article_score(query, article_title, story_title, entity=""):
    title_tokens = _tokens(article_title)
    query_tokens = _tokens(query)
    story_tokens = _tokens(story_title)
    entity_tokens = _tokens(entity)
    if not title_tokens:
        return 0.0

    if entity_tokens:
        entity_hits = len(entity_tokens & title_tokens)
        entity_overlap = entity_hits / max(1, len(entity_tokens))
        if entity_overlap < 0.75 and not (
            entity_hits >= 1 and len(entity_tokens) >= 2
        ):
            return 0.0
    else:
        entity_overlap = 0.0

    topic_tokens = (story_tokens | query_tokens) - entity_tokens
    topic_hits = len(topic_tokens & title_tokens)
    if not entity_tokens and topic_hits < 2:
        return 0.0
    if entity_tokens and topic_hits < 1:
        return 0.0

    query_overlap = len(query_tokens & title_tokens) / max(1, len(query_tokens))
    return min(
        1.0,
        entity_overlap * 0.45
        + min(1.0, topic_hits / 3.0) * 0.35
        + query_overlap * 0.20,
    )


def _ddgs_news(query, timelimit="d"):
    try:
        from ddgs import DDGS
        search = DDGS(timeout=SEARCH_TIMEOUT)
    except Exception:
        return []

    for backend in ("bing", "yahoo"):
        try:
            results = search.news(
                query=query,
                region="us-en",
                safesearch="moderate",
                timelimit=timelimit,
                max_results=SEARCH_RESULTS,
                backend=backend,
            )
            if results:
                return [dict(item) for item in results if isinstance(item, dict)]
        except Exception:
            continue
    return []


def _google_news_rss(query):
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        response = requests.get(url, timeout=SEARCH_TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError):
        return []

    output = []
    for item in root.findall(".//item")[:SEARCH_RESULTS]:
        title = _clean(item.findtext("title"), 600)
        link = _usable_url(item.findtext("link"))
        published = _parse_date(item.findtext("pubDate"))
        source = _clean(item.findtext("source"), 160)
        if title and link:
            output.append({
                "title": title,
                "url": link,
                "published_at": published.isoformat() if published else "",
                "source": source,
                "query": query,
            })
    return output


def _news_search(query, historical=False):
    def text_search():
        try:
            from ddgs import DDGS
            search = DDGS(timeout=SEARCH_TIMEOUT)
            results = search.text(
                query=query,
                region="us-en",
                safesearch="moderate",
                max_results=SEARCH_RESULTS,
                backend="auto",
            )
            return [dict(item) for item in results if isinstance(item, dict)]
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=3 if historical else 2) as executor:
        news_future = executor.submit(
            _ddgs_news,
            query,
            None if historical else "d",
        )
        google_future = executor.submit(_google_news_rss, query)
        text_future = executor.submit(text_search) if historical else None
        ddgs = news_future.result()
        google = google_future.result()
        text = text_future.result() if text_future else []

    combined = []
    seen = set()
    for item in list(ddgs or []) + list(google or []) + list(text or []):
        url = _clean(item.get("url") or item.get("href"), 3000)
        title = _clean(item.get("title"), 600)
        identity = url.casefold() or title.casefold()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        combined.append({**item, "url": url, "title": title, "query": query})

    if not historical and len(combined) < min(SEARCH_RESULTS, 8):
        for item in _ddgs_news(query, timelimit="w"):
            url = _clean(item.get("url") or item.get("href"), 3000)
            title = _clean(item.get("title"), 600)
            identity = url.casefold() or title.casefold()
            if not identity or identity in seen:
                continue
            seen.add(identity)
            combined.append({**item, "url": url, "title": title, "query": query})
            if len(combined) >= SEARCH_RESULTS:
                break

    return combined[:SEARCH_RESULTS]


def _article_url_is_usable(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.casefold().split(":")[0]
    if host in BLOCKED_HOSTS:
        return False
    if host != "news.google.com" and any(
        part in parsed.path.casefold() for part in BAD_PATH_PARTS
    ):
        return False
    return True


def _collect_related_pages(queries, original_url, story_title="", entity="", historical=False):
    if not queries:
        return []

    with ThreadPoolExecutor(max_workers=min(3, len(queries))) as executor:
        groups = list(executor.map(lambda query: _news_search(query, historical), queries))

    now = datetime.now(timezone.utc)
    ranked = []
    seen_urls = {_clean(original_url).casefold().rstrip("/")}

    for group in groups:
        for item in group:
            url = _clean(item.get("url") or item.get("href"), 3000)
            title = _clean(item.get("title"), 600)
            if not url or not title or not _article_url_is_usable(url):
                continue

            key = url.casefold().rstrip("/")
            if key in seen_urls:
                continue

            published = _parse_date(
                item.get("published_at")
                or item.get("published")
                or item.get("date")
            )
            age = _age_hours(published, now)
            if not historical and age is not None and (age < -0.5 or age > MAX_AGE_HOURS):
                continue

            query = _clean(item.get("query"), 260)
            match = max(
                _title_match(query, title, entity),
                _related_article_score(query, title, story_title, entity),
                _context_match(
                    query,
                    _clean(
                        " ".join(
                            str(item.get(key) or "")
                            for key in ("body", "description", "snippet")
                        ),
                        3500,
                    ),
                    entity,
                ),
            )
            if not query or match <= 0:
                continue

            ranked.append({
                **item,
                "url": url,
                "title": title,
                "query": query,
                "published_at": published.isoformat() if published else "",
                "match": match,
                "age": age,
                "_host": urlparse(url).netloc.casefold().removeprefix("www."),
            })
            seen_urls.add(key)

    if historical:
        ranked.sort(
            key=lambda item: (
                -float(item.get("match") or 0),
                float(item.get("age") or 999999),
            )
        )
    else:
        ranked.sort(
            key=lambda item: (
                1 if item.get("age") is None else 0,
                float(item.get("age") or 0),
                -float(item.get("match") or 0),
            )
        )

    pages = []
    host_counts = {}
    for item in ranked:
        host = item.get("_host") or ""
        if host and host_counts.get(host, 0) >= 2:
            continue
        pages.append(item)
        if host:
            host_counts[host] = host_counts.get(host, 0) + 1
        if len(pages) >= MAX_RELATED_PAGES:
            break

    if len(pages) < MAX_RELATED_PAGES:
        selected = {item["url"].casefold() for item in pages}
        for item in ranked:
            if item["url"].casefold() in selected:
                continue
            pages.append(item)
            selected.add(item["url"].casefold())
            if len(pages) >= MAX_RELATED_PAGES:
                break

    return pages


def _collect_profile_pages(entity):
    if not entity:
        return []

    try:
        from ddgs import DDGS
        search = DDGS(timeout=SEARCH_TIMEOUT)
    except Exception:
        return []

    ranked = []
    seen = set()
    for query in (
        f"{entity} player profile",
        f"{entity} profile",
        f"{entity} official",
    ):
        for backend in ("bing", "yahoo"):
            try:
                results = search.text(
                    query=query,
                    region="us-en",
                    safesearch="moderate",
                    max_results=8,
                    backend=backend,
                )
            except Exception:
                continue
            if not results:
                continue

            for item in results:
                if not isinstance(item, dict):
                    continue
                url = _clean(item.get("href") or item.get("url"), 3000)
                title = _clean(item.get("title"), 600)
                key = url.casefold()
                if (
                    not url
                    or not title
                    or key in seen
                    or not _article_url_is_usable(url)
                ):
                    continue
                if _title_match(entity, title, entity) <= 0:
                    continue

                seen.add(key)
                ranked.append({
                    "url": url,
                    "title": title,
                    "source": _clean(item.get("source"), 160),
                    "published_at": "",
                    "query": query,
                    "profile": True,
                })

            if ranked:
                break

    return ranked[:PROFILE_PAGES]


def _extract_srcset(value):
    return [
        _clean(part, 1600).split(" ", 1)[0]
        for part in str(value or "").split(",")
        if _clean(part, 1600)
    ]


def _absolute(value, base_url):
    value = _clean(value, 3000).replace("\\/", "/")
    if not value or value.startswith(("data:", "blob:", "javascript:")):
        return ""
    return _usable_url(urljoin(base_url, value))


def _network_image_key(url):
    parsed = urlparse(_clean(url, 3000))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}{parsed.path}"


def _bad_image_url(url):
    blob = _clean(url, 3000).casefold()
    return any(term in blob for term in BAD_IMAGE_TERMS)


def _image_bytes_ok(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return (
                min(image.size) >= MIN_SIDE
                and image.size[0] * image.size[1] >= 300_000
            )
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _image_dimensions(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return 0, 0


def _visual_hash(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
            return hashlib.sha256(image.tobytes()).hexdigest()
    except Exception:
        return hashlib.sha256(data).hexdigest()


def _page_score(title, query, entity):
    title_tokens = _tokens(title)
    query_tokens = _tokens(query)
    entity_tokens = _tokens(entity)
    if entity_tokens and not (entity_tokens & title_tokens):
        return 0.0
    query_overlap = len(query_tokens & title_tokens) / max(1, len(query_tokens))
    entity_overlap = len(entity_tokens & title_tokens) / max(1, len(entity_tokens))
    return min(1.0, query_overlap * 0.65 + entity_overlap * 0.35)


def _candidate_score(candidate, page_title, query, entity):
    context = _clean(
        " ".join(str(candidate.get(key) or "") for key in (
            "alt", "title", "context"
        )),
        4000,
    )
    score = _page_score(page_title, query, entity) * 70.0
    context_tokens = _tokens(context)
    if candidate.get("in_article"):
        score += 30.0
    if candidate.get("in_figure"):
        score += 12.0
    if candidate.get("method") in {"metadata", "json-ld:image"}:
        score += 16.0
    if min(
        int(candidate.get("width") or 0),
        int(candidate.get("height") or 0),
    ) >= 1200:
        score += 12.0
    score += min(20.0, len(context_tokens & ACTION_TERMS) * 6.0)
    return round(score, 2)


def _browser_script():
    return r"""
    () => {
      const meta = {};
      document.querySelectorAll('meta[property], meta[name], meta[itemprop]').forEach(el => {
        const key = (el.getAttribute('property') || el.getAttribute('name') || el.getAttribute('itemprop') || '').toLowerCase();
        const value = el.getAttribute('content') || '';
        if (key && value && !meta[key]) meta[key] = value;
      });
      const images = Array.from(document.querySelectorAll('img')).map(img => {
        const figure = img.closest('figure');
        const article = img.closest('article, main, [itemtype*="Article"], [itemtype*="NewsArticle"]');
        let context = '';
        let node = img.parentElement;
        for (let i = 0; i < 2 && node; i += 1, node = node.parentElement) {
          context += ' ' + (node.innerText || '').slice(0, 700);
        }
        return {
          currentSrc: img.currentSrc || '',
          src: img.getAttribute('src') || '',
          srcset: img.getAttribute('srcset') || '',
          dataSrc: img.getAttribute('data-src') || '',
          dataSrcset: img.getAttribute('data-srcset') || '',
          dataLazySrcset: img.getAttribute('data-lazy-srcset') || '',
          dataLazySrc: img.getAttribute('data-lazy-src') || '',
          dataOriginal: img.getAttribute('data-original') || '',
          alt: img.getAttribute('alt') || '',
          title: img.getAttribute('title') || '',
          width: img.naturalWidth || 0,
          height: img.naturalHeight || 0,
          inArticle: Boolean(article),
          inFigure: Boolean(figure),
          context: context.slice(0, 1600)
        };
      });
      const linkImages = Array.from(document.querySelectorAll('link[rel~="image_src"], link[rel~="preload"][as="image"]'))
        .map(el => el.getAttribute('href') || '').filter(Boolean);
      const backgrounds = Array.from(document.querySelectorAll('article [style], main [style]')).map(el => {
        const match = (getComputedStyle(el).backgroundImage || '').match(/url\(["']?(.*?)["']?\)/);
        return match ? match[1] : '';
      }).filter(Boolean);
      const noscripts = Array.from(document.querySelectorAll('noscript'))
        .map(el => el.textContent || el.innerHTML || '').filter(Boolean).slice(0, 12);
      const jsonLd = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
        .map(el => el.textContent || '').filter(Boolean).slice(0, 12);
      const articleNode = document.querySelector('article') || document.querySelector('main');
      const articleText = (articleNode?.innerText || '').slice(0, 3500);
      return {
        title: document.querySelector('meta[property="og:title"]')?.content || document.title || '',
        meta,
        images,
        linkImages,
        backgrounds,
        noscripts,
        jsonLd,
        articleText,
        finalUrl: location.href
      };
    }
    """


def _walk_images(value):
    found = []
    if isinstance(value, str):
        if value.startswith(("http://", "https://", "/", "./", "../")):
            found.append(value)
    elif isinstance(value, dict):
        for key in ("image", "contentUrl", "thumbnailUrl", "url"):
            child = value.get(key)
            if isinstance(child, (str, dict, list)):
                found.extend(_walk_images(child))
        for child in value.values():
            if isinstance(child, (dict, list)):
                found.extend(_walk_images(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_images(child))
    return found


async def _browser_page(context, request):
    page = await context.new_page()
    network_responses = {}

    def remember_response(response):
        try:
            if response.request.resource_type == "image" and response.ok:
                if len(network_responses) < 120:
                    network_responses.setdefault(response.url, response)
                    key = _network_image_key(response.url)
                    if key:
                        network_responses.setdefault(key, response)
        except Exception:
            pass

    page.on("response", remember_response)
    try:
        try:
            await page.goto(
                request["url"],
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT_MS,
            )
        except Exception as exc:
            return {
                "assets": [],
                "error": f"navigation: {type(exc).__name__}: {exc}",
                "url": request["url"],
            }

        try:
            await page.wait_for_load_state("networkidle", timeout=1800)
        except Exception:
            pass
        await page.wait_for_timeout(500)
        for _ in range(3):
            try:
                await page.evaluate(
                    "window.scrollBy(0, Math.min(window.innerHeight * 1.25, 1400));"
                )
                await page.wait_for_timeout(180)
            except Exception:
                break

        try:
            data = await page.evaluate(_browser_script())
        except Exception as exc:
            return {
                "assets": [],
                "error": f"page-evaluation: {type(exc).__name__}: {exc}",
                "url": page.url or request["url"],
            }

        base_url = data.get("finalUrl") or request["url"]
        page_title = _clean(data.get("title"), 600)
        query = _clean(request.get("query"), 500)
        entity = _clean(request.get("entity"), 180)
        story_title = _clean(request.get("story_title"), 600)
        if query:
            page_context = _clean(
                " ".join(
                    [
                        str((data.get("meta") or {}).get("description") or ""),
                        str((data.get("meta") or {}).get("og:description") or ""),
                        str(data.get("articleText") or ""),
                    ]
                ),
                4500,
            )
            page_match = max(
                _title_match(query, page_title, entity),
                _related_article_score(query, page_title, story_title, entity),
                _context_match(query, page_context, entity),
            )
            if request.get("profile") and entity:
                page_match = max(
                    page_match,
                    _title_match(entity, page_title, entity),
                )
            if page_match <= 0:
                return {
                    "assets": [],
                    "title": page_title,
                    "url": base_url,
                    "candidate_count": 0,
                    "dom_image_count": len(data.get("images") or []),
                    "network_image_count": len(network_responses),
                    "error": "page-relevance-mismatch",
                }
        candidates = []

        def add(url, method, payload=None):
            absolute = _absolute(url, base_url)
            if absolute and not _bad_image_url(absolute):
                candidates.append({
                    **(payload or {}),
                    "url": absolute,
                    "method": method,
                })

        meta = data.get("meta") or {}
        for key in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image"):
            if meta.get(key):
                add(meta[key], "metadata")

        for raw in data.get("jsonLd") or []:
            try:
                value = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            for url in _walk_images(value):
                add(url, "json-ld:image")

        for url in data.get("linkImages") or []:
            add(url, "link:image")

        for url in data.get("backgrounds") or []:
            add(url, "background-image", {"in_article": True})

        for markup in data.get("noscripts") or []:
            for match in re.finditer(
                r"""<(?:img|source)\b[^>]*(?:src|data-src|data-lazy-src|data-original|data-image|data-srcset)\s*=\s*["']([^"']+)["']""",
                markup,
                re.IGNORECASE,
            ):
                for url in _extract_srcset(match.group(1)):
                    add(url, "noscript:image", {"in_article": True})

        for image in data.get("images") or []:
            payload = {
                "alt": image.get("alt"),
                "title": image.get("title"),
                "context": image.get("context"),
                "width": image.get("width"),
                "height": image.get("height"),
                "in_article": image.get("inArticle"),
                "in_figure": image.get("inFigure"),
            }
            for key, method in (
                ("currentSrc", "currentSrc"),
                ("src", "article-img" if image.get("inArticle") else "img"),
                ("dataSrc", "lazy-src"),
                ("dataLazySrc", "lazy-lazy-src"),
                ("dataOriginal", "lazy-original"),
            ):
                if image.get(key):
                    add(image[key], method, payload)
            for url in (
                _extract_srcset(image.get("srcset"))
                + _extract_srcset(image.get("dataSrcset"))
                + _extract_srcset(image.get("dataLazySrcset"))
            ):
                add(url, "srcset", payload)

        unique = []
        seen_urls = set()
        for candidate in candidates:
            key = candidate["url"].casefold()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            candidate["score"] = _candidate_score(
                candidate,
                page_title,
                request.get("query", ""),
                request.get("entity", ""),
            )
            unique.append(candidate)

        unique.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                -int(item.get("height") or 0),
            )
        )

        assets = []
        seen_hashes = set()
        direct_download_failures = 0
        direct_invalid_images = 0
        network_fallback_hits = 0
        max_images = int(request.get("max_images") or IMAGES_PER_PAGE)
        for candidate in unique[: max_images * 4]:
            try:
                response = await page.request.get(
                    candidate["url"],
                    timeout=min(7500, PAGE_TIMEOUT_MS),
                    headers={
                        "Referer": base_url,
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                )
                data_bytes = await response.body() if response.ok else b""
            except Exception:
                direct_download_failures += 1
                data_bytes = b""

            if not _image_bytes_ok(data_bytes):
                direct_invalid_images += 1
                for key in (candidate["url"], _network_image_key(candidate["url"])):
                    network_response = network_responses.get(key)
                    if network_response is None:
                        continue
                    try:
                        fallback_bytes = await network_response.body()
                    except Exception:
                        fallback_bytes = b""
                    if _image_bytes_ok(fallback_bytes):
                        data_bytes = fallback_bytes
                        network_fallback_hits += 1
                        break

            if not _image_bytes_ok(data_bytes):
                continue

            digest = _visual_hash(data_bytes)
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            width, height = _image_dimensions(data_bytes)
            assets.append({
                "bytes": data_bytes,
                "hash": digest,
                "source_page_url": base_url,
                "source_image_url": candidate["url"],
                "publisher": _clean(
                    meta.get("og:site_name")
                    or request.get("publisher")
                    or urlparse(base_url).netloc.removeprefix("www."),
                    160,
                ),
                "article_title": page_title,
                "published_at": request.get("published_at", ""),
                "query": request.get("query", ""),
                "method": candidate["method"],
                "width": width,
                "height": height,
                "score": candidate["score"],
                "action_score": len(
                    _tokens(" ".join(
                        str(candidate.get(k) or "")
                        for k in ("alt", "title", "context")
                    )) & ACTION_TERMS
                ),
            })
            if len(assets) >= max_images:
                break

        return {
            "assets": assets,
            "title": page_title,
            "url": base_url,
            "candidate_count": len(unique),
            "dom_image_count": len(data.get("images") or []),
            "network_image_count": len(network_responses),
            "direct_download_failures": direct_download_failures,
            "direct_invalid_images": direct_invalid_images,
            "network_fallback_hits": network_fallback_hits,
            "error": "",
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


class _StaticImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.candidates = []
        self.json_ld = []
        self._in_script = False
        self._script_type = ""
        self._script_parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        data = {
            str(key).casefold(): str(value)
            for key, value in attrs
            if key and value is not None
        }

        if tag == "meta":
            key = _clean(
                data.get("property")
                or data.get("name")
                or data.get("itemprop"),
                120,
            ).casefold()
            value = _clean(data.get("content"), 3000)
            if key and value:
                self.meta.setdefault(key, value)
            return

        if tag == "script":
            self._in_script = True
            self._script_type = _clean(data.get("type"), 120).casefold()
            self._script_parts = []
            return

        if tag == "link":
            rel = _clean(data.get("rel"), 200).casefold()
            href = data.get("href")
            if href and (
                "image_src" in rel
                or ("preload" in rel and data.get("as", "").casefold() == "image")
            ):
                self.candidates.append((href, "link:image", {}))
            return

        if tag not in {"img", "source"}:
            return
        if tag == "source" and "video" in data.get("type", "").casefold():
            return

        payload = {
            "alt": data.get("alt"),
            "title": data.get("title"),
            "class": data.get("class"),
            "itemprop": data.get("itemprop"),
        }
        for key, method in (
            ("src", "static-img"),
            ("data-src", "static-lazy"),
            ("data-lazy-src", "static-lazy"),
            ("data-original", "static-original"),
            ("data-image", "static-image"),
            ("data-image-url", "static-image"),
            ("data-url", "static-image"),
        ):
            if data.get(key):
                self.candidates.append((data[key], method, payload))

        for key in ("srcset", "data-srcset", "data-lazy-srcset"):
            for value in _extract_srcset(data.get(key)):
                self.candidates.append((value, "static-srcset", payload))

    def handle_endtag(self, tag):
        if tag.casefold() != "script" or not self._in_script:
            return
        if "ld+json" in self._script_type:
            raw = "".join(self._script_parts).strip()
            if raw:
                try:
                    self.json_ld.append(json.loads(html.unescape(raw)))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        self._in_script = False
        self._script_type = ""
        self._script_parts = []

    def handle_data(self, data):
        if self._in_script:
            self._script_parts.append(data)


def _static_page(request):
    try:
        response = requests.get(
            request["url"],
            timeout=SEARCH_TIMEOUT,
            headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
        )
        response.raise_for_status()
        raw = response.content[:4_000_000]
        markup = raw.decode(
            response.encoding or response.apparent_encoding or "utf-8",
            errors="replace",
        )
        base_url = response.url or request["url"]
    except (requests.RequestException, UnicodeError):
        return {"assets": [], "error": "static-navigation-failed"}

    parser = _StaticImageParser()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:
        return {
            "assets": [],
            "error": f"static-parse: {type(exc).__name__}: {exc}",
        }

    candidates = []
    for key, method in (
        ("og:image", "metadata"),
        ("og:image:url", "metadata"),
        ("og:image:secure_url", "metadata"),
        ("twitter:image", "metadata"),
        ("twitter:image:src", "metadata"),
    ):
        if parser.meta.get(key):
            candidates.append((parser.meta[key], method, {}))

    for value in parser.json_ld:
        for url in _walk_images(value):
            candidates.append((url, "json-ld:image", {}))

    candidates.extend(parser.candidates)

    max_images = int(request.get("max_images") or IMAGES_PER_PAGE)
    assets = []
    seen_urls = set()
    seen_hashes = set()

    for raw_url, method, payload in candidates[: max_images * 8]:
        url = _absolute(raw_url, base_url)
        if not url or _bad_image_url(url):
            continue
        key = url.casefold()
        if key in seen_urls:
            continue
        seen_urls.add(key)

        try:
            response = requests.get(
                url,
                timeout=SEARCH_TIMEOUT,
                headers={
                    **HEADERS,
                    "Referer": base_url,
                    "Accept": (
                        "image/avif,image/webp,image/apng,image/svg+xml,"
                        "image/*,*/*;q=0.8"
                    ),
                },
            )
            response.raise_for_status()
            data = response.content
        except requests.RequestException:
            continue

        if not _image_bytes_ok(data):
            continue
        digest = _visual_hash(data)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)

        width, height = _image_dimensions(data)
        context = " ".join(
            str(payload.get(key) or "")
            for key in ("alt", "title", "class", "itemprop")
        )
        assets.append({
            "bytes": data,
            "hash": digest,
            "source_page_url": base_url,
            "source_image_url": url,
            "publisher": _clean(
                parser.meta.get("og:site_name")
                or request.get("publisher")
                or urlparse(base_url).netloc.removeprefix("www."),
                160,
            ),
            "article_title": _clean(
                parser.meta.get("og:title")
                or request.get("title")
                or "",
                600,
            ),
            "published_at": request.get("published_at", ""),
            "query": request.get("query", ""),
            "method": method,
            "width": width,
            "height": height,
            "score": 10.0,
            "action_score": len(_tokens(context) & ACTION_TERMS),
            "profile_page": bool(request.get("profile")),
        })
        if len(assets) >= max_images:
            break

    return {
        "assets": assets,
        "title": _clean(parser.meta.get("og:title") or request.get("title"), 600),
        "url": base_url,
        "static_candidates": len(candidates),
        "error": "",
    }


def _crawl_pages(page_requests, images_per_page=IMAGES_PER_PAGE):
    async def run_browser():
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required for the Visual Fetcher. Install requirements and Chromium."
            ) from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 1200},
                    locale="en-IN",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/151 Safari/537.36"
                    ),
                )
                results = await asyncio.gather(
                    *(
                        _browser_page(
                            context,
                            {
                                **request,
                                "max_images": int(
                                    request.get("max_images") or images_per_page
                                ),
                            },
                        )
                        for request in page_requests
                    ),
                    return_exceptions=True,
                )
                output = [
                    {
                        "assets": [],
                        "error": f"{type(result).__name__}: {result}",
                    }
                    if isinstance(result, Exception)
                    else result
                    for result in results
                ]
                await context.close()
                return output
            finally:
                await browser.close()

    browser_results = asyncio.run(run_browser())

    missing = [
        (index, request)
        for index, (request, result) in enumerate(zip(page_requests, browser_results))
        if not result.get("assets")
    ]
    if not missing:
        return browser_results

    with ThreadPoolExecutor(max_workers=min(4, len(missing))) as executor:
        fallback_results = list(executor.map(
            lambda pair: _static_page(pair[1]), missing
        ))

    for (index, _), fallback in zip(missing, fallback_results):
        merged = {
            **browser_results[index],
            "static_fallback_attempted": True,
            "static_candidates": int(fallback.get("static_candidates") or 0),
            "static_assets": len(fallback.get("assets") or []),
            "static_error": str(fallback.get("error") or ""),
        }
        if fallback.get("assets"):
            browser_results[index] = {
                **fallback,
                "static_fallback_attempted": True,
                "static_candidates": int(fallback.get("static_candidates") or 0),
                "static_assets": len(fallback.get("assets") or []),
                "static_error": str(fallback.get("error") or ""),
                "browser_candidate_count": int(browser_results[index].get("candidate_count") or 0),
                "browser_dom_image_count": int(browser_results[index].get("dom_image_count") or 0),
                "browser_network_image_count": int(browser_results[index].get("network_image_count") or 0),
            }
        else:
            browser_results[index] = merged
    return browser_results


def _dedupe(assets):
    output = []
    seen_hashes = set()
    seen_urls = set()
    for asset in sorted(
        assets,
        key=lambda item: (
            0 if item.get("original_story") else 1,
            -float(item.get("score") or 0),
            -int(item.get("action_score") or 0),
        ),
    ):
        digest = _clean(asset.get("hash"), 120)
        image_url = _clean(asset.get("source_image_url"), 3000).casefold().rstrip("/")
        if digest and digest in seen_hashes:
            continue
        if image_url and image_url in seen_urls:
            continue
        if digest:
            seen_hashes.add(digest)
        if image_url:
            seen_urls.add(image_url)
        asset["qc_status"] = "usable"
        output.append(asset)
        if len(output) >= TARGET:
            break
    return output



def crawl_visuals(story, manual_query=""):
    """Fetch the 10–15 image web pool for one selected sports story."""
    title = _topic_value(story, "title")
    description = _topic_value(story, "description")
    entity = (
        _topic_value(story, "primary_entity")
        or _topic_value(story, "subject")
    )
    original_url = _usable_url(_topic_value(story, "url"))

    if not title or not original_url:
        raise ValueError(
            "Visual Fetcher requires the selected story title and original URL."
        )

    automatic_queries = build_queries(title, description, entity)
    manual_query = _clean(manual_query, 260)
    search_queries = [manual_query] if manual_query else list(automatic_queries)

    page_requests = [{
        "url": original_url,
        "title": title,
        "publisher": _topic_value(story, "source"),
        "published_at": _topic_value(story, "published_at"),
        "query": "",
        "entity": entity,
        "story_title": title,
    }]

    related_pages = _collect_related_pages(
        search_queries,
        original_url,
        title,
        "" if manual_query else entity,
    ) if search_queries else []

    for page in related_pages:
        page_requests.append({
            "url": page["url"],
            "title": page.get("title", ""),
            "publisher": page.get("source", ""),
            "published_at": page.get("published_at", ""),
            "query": page.get("query", ""),
            "entity": entity,
            "story_title": title,
        })

    results = _crawl_pages(page_requests)
    assets = []
    diagnostics = []

    def add_diagnostic(request, result):
        diagnostics.append({
            "url": result.get("url") or request["url"],
            "title": result.get("title") or request.get("title", ""),
            "assets": len(result.get("assets") or []),
            "candidates": int(result.get("candidate_count") or 0),
            "dom_images": int(result.get("dom_image_count") or 0),
            "network_images": int(result.get("network_image_count") or 0),
            "direct_download_failures": int(
                result.get("direct_download_failures") or 0
            ),
            "direct_invalid_images": int(
                result.get("direct_invalid_images") or 0
            ),
            "network_fallback_hits": int(
                result.get("network_fallback_hits") or 0
            ),
            "static_fallback_attempted": bool(
                result.get("static_fallback_attempted")
            ),
            "static_candidates": int(result.get("static_candidates") or 0),
            "static_assets": int(result.get("static_assets") or 0),
            "static_error": str(result.get("static_error") or ""),
            "error": str(result.get("error") or ""),
            "query": request.get("query") or "original story URL",
            "profile": bool(request.get("profile")),
        })

    for index, result in enumerate(results):
        request = page_requests[index]
        add_diagnostic(request, result)

        for asset in result.get("assets") or []:
            asset["article_title"] = (
                asset.get("article_title") or request.get("title", "")
            )
            asset["source_page_url"] = (
                asset.get("source_page_url") or request["url"]
            )
            asset["publisher"] = (
                asset.get("publisher") or request.get("publisher", "")
            )
            asset["query"] = (
                asset.get("query") or request.get("query", "")
            )

            if index == 0:
                asset["query"] = "original story URL"
                asset["original_story"] = True
                asset["published_at"] = (
                    asset.get("published_at")
                    or _topic_value(story, "published_at")
                )

            assets.append(asset)

    selected = _dedupe(assets)

    if len(selected) < SUCCESS and entity and not manual_query:
        profile_pages = _collect_profile_pages(entity)
        profile_requests = [
            {
                "url": page["url"],
                "title": page.get("title", ""),
                "publisher": page.get("source", ""),
                "published_at": "",
                "query": page.get("query", ""),
                "entity": entity,
                "story_title": title,
                "profile": True,
                "max_images": PROFILE_IMAGES,
            }
            for page in profile_pages
        ]

        if profile_requests:
            profile_results = _crawl_pages(
                profile_requests,
                images_per_page=PROFILE_IMAGES,
            )
            for request, result in zip(profile_requests, profile_results):
                add_diagnostic(request, result)
                for asset in result.get("assets") or []:
                    asset["article_title"] = (
                        asset.get("article_title") or request["title"]
                    )
                    asset["source_page_url"] = (
                        asset.get("source_page_url") or request["url"]
                    )
                    asset["publisher"] = (
                        asset.get("publisher") or request["publisher"]
                    )
                    asset["query"] = (
                        asset.get("query") or request["query"]
                    )
                    asset["profile_page"] = True
                    assets.append(asset)
            selected = _dedupe(assets)

    publishers = sorted({
        _clean(item.get("publisher"), 160)
        for item in selected
        if _clean(item.get("publisher"), 160)
    })
    domains = sorted({
        urlparse(str(item.get("source_page_url") or "")).netloc.removeprefix("www.").lower()
        for item in selected
        if urlparse(str(item.get("source_page_url") or "")).netloc
    })

    failure_state = (
        "ready"
        if len(selected) >= SUCCESS
        else "underfilled"
        if selected
        else "no_images"
    )

    print(
        f"   [Visual Fetcher] related={len(related_pages)} "
        f"profiles={sum(1 for p in page_requests if p.get('profile'))} "
        f"final_pool={len(selected)}/{TARGET} state={failure_state}",
        flush=True,
    )

    return {
        "assets": selected,
        "target": TARGET,
        "success_threshold": SUCCESS,
        "original_story_url": original_url,
        "automatic_queries": automatic_queries,
        "queries_used": search_queries,
        "manual_query": manual_query,
        "pages_scraped": len(page_requests),
        "related_pages": len(related_pages),
        "profile_pages": sum(1 for page in page_requests if page.get("profile")),
        "publishers": publishers,
        "domains": domains,
        "failure_state": failure_state,
        "diagnostics": diagnostics,
    }


def manual_crawl_visuals(query):
    """Scrape current publisher pages returned for one manual news query."""
    query = _clean(query, 260)
    if not query:
        raise ValueError("Manual scraper requires a search query.")

    related_pages = _collect_related_pages([query], "", "", "")
    page_requests = [
        {
            "url": page["url"],
            "title": page.get("title", ""),
            "publisher": page.get("source", ""),
            "published_at": page.get("published_at", ""),
            "query": query,
            "entity": "",
            "story_title": "",
        }
        for page in related_pages
    ]

    results = _crawl_pages(page_requests)
    assets = []
    diagnostics = []

    for request, result in zip(page_requests, results):
        diagnostics.append({
            "url": result.get("url") or request["url"],
            "title": result.get("title") or request.get("title", ""),
            "assets": len(result.get("assets") or []),
            "candidates": int(result.get("candidate_count") or 0),
            "dom_images": int(result.get("dom_image_count") or 0),
            "network_images": int(result.get("network_image_count") or 0),
            "direct_download_failures": int(result.get("direct_download_failures") or 0),
            "direct_invalid_images": int(result.get("direct_invalid_images") or 0),
            "network_fallback_hits": int(result.get("network_fallback_hits") or 0),
            "static_fallback_attempted": bool(result.get("static_fallback_attempted")),
            "static_candidates": int(result.get("static_candidates") or 0),
            "static_assets": int(result.get("static_assets") or 0),
            "static_error": str(result.get("static_error") or ""),
            "error": str(result.get("error") or ""),
            "query": query,
        })
        for asset in result.get("assets") or []:
            asset["query"] = query
            asset["article_title"] = asset.get("article_title") or request.get("title", "")
            asset["source_page_url"] = asset.get("source_page_url") or request["url"]
            asset["publisher"] = asset.get("publisher") or request.get("publisher", "")
            assets.append(asset)

    selected = _dedupe(assets)
    failure_state = (
        "ready" if len(selected) >= SUCCESS
        else "underfilled" if selected
        else "no_images"
    )

    print(
        f"   [Visual Fetcher] manual_query={query!r} "
        f"pages={len(related_pages)} final_pool={len(selected)}/{TARGET} state={failure_state}",
        flush=True,
    )

    return {
        "assets": selected,
        "target": TARGET,
        "success_threshold": SUCCESS,
        "manual_query": query,
        "queries_used": [query],
        "pages_scraped": len(page_requests),
        "related_pages": len(related_pages),
        "failure_state": failure_state,
        "diagnostics": diagnostics,
    }


def same_query(query, used_queries):
    value = _clean(query, 260).casefold()
    return bool(value) and any(
        value == _clean(item, 260).casefold()
        for item in (used_queries or [])
    )


__all__ = ["TARGET", "SUCCESS", "build_queries", "crawl_visuals", "manual_crawl_visuals", "same_query"]
