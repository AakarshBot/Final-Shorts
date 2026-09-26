"""Function 04: direct web image retrieval for the selected sports story."""
from __future__ import annotations

import asyncio
import hashlib
import html
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from PIL import Image, UnidentifiedImageError


TARGET = 15
SUCCESS = 10
MAX_RELATED_PAGES = 6
IMAGES_PER_PAGE = 5
MIN_SIDE = 500
MAX_IMAGE_BYTES = 8_000_000
SEARCH_RESULTS = 8
SEARCH_TIMEOUT = 8
PAGE_TIMEOUT_MS = 10_000

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "from", "by", "with", "after", "before", "during", "over", "into",
    "about", "this", "that", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "has", "have", "had", "will", "would", "could",
    "should", "says", "said", "report", "reports", "latest", "news", "story",
    "update", "today", "ahead", "versus", "vs", "v",
    "survive", "survives", "suffer", "suffers", "faces", "face", "gets", "get",
    "appears", "announce", "announces", "likely", "may",
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


def build_queries(title, description="", entity=""):
    """Build two compact visual-search queries; the original URL is separate."""
    entity = _clean(entity, 180)
    entity_tokens = _tokens(entity)
    source = f"{title} {description}"
    terms = []
    seen = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", _clean(source, 1200)):
        key = token.casefold()
        if len(token) <= 2 or key in STOPWORDS or key in entity_tokens or key in seen:
            continue
        seen.add(key)
        terms.append(token)
        if len(terms) >= 5:
            break

    if entity and terms:
        queries = [
            f"{entity} {' '.join(terms[:4])}",
            f"{entity} {' '.join(terms[:2])}",
        ]
    elif terms:
        queries = [" ".join(terms[:4]), " ".join(terms[:2])]
    else:
        queries = [entity or _clean(title, 220)] if (entity or title) else []

    output = []
    seen = set()
    for query in queries:
        query = _clean(query, 260)
        if query and query.casefold() not in seen:
            output.append(query)
            seen.add(query.casefold())
    return output[:2]


def _news_search(query):
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

    results = []
    for item in root.findall(".//item")[:SEARCH_RESULTS]:
        title = _clean(item.findtext("title"), 600)
        link = _usable_url(item.findtext("link"))
        published = _parse_date(item.findtext("pubDate"))
        source = _clean(item.findtext("source"), 160)
        if title and link:
            results.append({
                "title": title,
                "url": link,
                "published_at": published.isoformat() if published else "",
                "source": source,
                "query": query,
            })
    return results


def _collect_related_pages(queries, original_url):
    if not queries:
        return []

    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        groups = list(executor.map(_news_search, queries))

    now = datetime.now(timezone.utc)
    candidates = [item for group in groups for item in group]

    def sort_key(item):
        published = _parse_date(item.get("published_at"))
        age = (now - published).total_seconds() if published else 0
        return (
            1 if published is None else 0,
            age,
            -len(_tokens(item.get("title", ""))),
        )

    candidates.sort(key=sort_key)

    pages = []
    seen_urls = {_clean(original_url).casefold().rstrip("/")}
    seen_hosts = {}
    for item in candidates:
        url = _clean(item.get("url"), 3000)
        key = url.casefold().rstrip("/")
        host = urlparse(url).netloc.casefold().removeprefix("www.")
        if not url or key in seen_urls or not host:
            continue

        published = _parse_date(item.get("published_at"))
        if published is not None:
            age_hours = (now - published).total_seconds() / 3600.0
            if age_hours < -1 or age_hours > 96:
                continue

        if seen_hosts.get(host, 0) >= 2:
            continue
        if any(part in urlparse(url).path.casefold() for part in (
            "/search", "/tag/", "/category/", "/topic/", "/feed", "/rss"
        )):
            continue

        seen_urls.add(key)
        seen_hosts[host] = seen_hosts.get(host, 0) + 1
        pages.append(item)
        if len(pages) >= MAX_RELATED_PAGES:
            break
    return pages


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
      return {
        title: document.querySelector('meta[property="og:title"]')?.content || document.title || '',
        meta,
        images,
        linkImages,
        backgrounds,
        noscripts,
        jsonLd,
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
                if len(network_responses) < 60:
                    network_responses.setdefault(response.url, response)
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
                r'<(?:img|source)\b[^>]*(?:src|data-src|data-lazy-src|data-original|data-image|data-srcset)\s*=\s*[\'"']([^\'"']+)[\'"']',
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
            for url in _extract_srcset(image.get("srcset")) + _extract_srcset(image.get("dataSrcset")):
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
        network_fallback_hits = 0
        for candidate in unique[: IMAGES_PER_PAGE * 4]:
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

            if not data_bytes:
                network_response = network_responses.get(candidate["url"])
                if network_response is not None:
                    try:
                        data_bytes = await network_response.body()
                        if data_bytes:
                            network_fallback_hits += 1
                    except Exception:
                        data_bytes = b""

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
            if len(assets) >= IMAGES_PER_PAGE:
                break

        return {
            "assets": assets,
            "title": page_title,
            "url": base_url,
            "candidate_count": len(unique),
            "dom_image_count": len(data.get("images") or []),
            "network_image_count": len(network_responses),
            "direct_download_failures": direct_download_failures,
            "network_fallback_hits": network_fallback_hits,
            "error": "",
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _static_page(request):
    try:
        response = requests.get(
            request["url"],
            timeout=SEARCH_TIMEOUT,
            headers=HEADERS,
        )
        response.raise_for_status()
        markup = response.text
        base_url = response.url or request["url"]
    except requests.RequestException:
        return {"assets": []}

    urls = []
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)',
    ):
        urls.extend(re.findall(pattern, markup, re.IGNORECASE))

    assets = []
    seen = set()
    for raw_url in urls[: IMAGES_PER_PAGE * 4]:
        url = _absolute(raw_url, base_url)
        if not url or _bad_image_url(url) or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        try:
            image_response = requests.get(
                url,
                timeout=SEARCH_TIMEOUT,
                headers={**HEADERS, "Referer": base_url},
            )
            image_response.raise_for_status()
            data = image_response.content
        except requests.RequestException:
            continue
        if not _image_bytes_ok(data):
            continue

        width, height = _image_dimensions(data)
        assets.append({
            "bytes": data,
            "hash": _visual_hash(data),
            "source_page_url": base_url,
            "source_image_url": url,
            "publisher": urlparse(base_url).netloc.removeprefix("www."),
            "article_title": request.get("title", ""),
            "published_at": request.get("published_at", ""),
            "query": request.get("query", ""),
            "method": "static",
            "width": width,
            "height": height,
            "score": 10.0,
            "action_score": 0,
        })
        if len(assets) >= IMAGES_PER_PAGE:
            break
    return {"assets": assets}


def _crawl_pages(page_requests):
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
                    *(_browser_page(context, request) for request in page_requests),
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
        if fallback.get("assets"):
            browser_results[index] = fallback
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
    """Fetch a 10–15 image web pool for one selected sports story."""
    title = _topic_value(story, "title")
    description = _topic_value(story, "description")
    entity = (
        _topic_value(story, "primary_entity")
        or _topic_value(story, "subject")
        or ""
    )
    original_url = _usable_url(_topic_value(story, "url"))
    if not title or not original_url:
        raise ValueError("Visual Fetcher requires the selected story title and original URL.")

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
    }]

    for page in _collect_related_pages(search_queries, original_url):
        page_requests.append({
            "url": page["url"],
            "title": page.get("title", ""),
            "publisher": page.get("source", ""),
            "published_at": page.get("published_at", ""),
            "query": page.get("query", ""),
            "entity": entity,
        })

    results = _crawl_pages(page_requests)
    assets = []
    for index, result in enumerate(results):
        for asset in result.get("assets") or []:
            request = page_requests[index]
            asset["article_title"] = asset.get("article_title") or request.get("title", "")
            asset["source_page_url"] = asset.get("source_page_url") or request["url"]
            asset["publisher"] = asset.get("publisher") or request.get("publisher", "")
            asset["query"] = asset.get("query") or request.get("query", "")
            if index == 0:
                asset["query"] = "original story URL"
                asset["original_story"] = True
                asset["published_at"] = asset.get("published_at") or _topic_value(
                    story, "published_at"
                )
            assets.append(asset)

    selected = _dedupe(assets)

    if len(selected) < SUCCESS and entity and not manual_query:
        fallback_pages = _collect_related_pages(
            [f"{entity} profile", f"{entity} action"],
            original_url,
        )
        fallback_requests = [
            {
                "url": page["url"],
                "title": page.get("title", ""),
                "publisher": page.get("source", ""),
                "published_at": page.get("published_at", ""),
                "query": page.get("query", ""),
                "entity": entity,
            }
            for page in fallback_pages
        ]
        if fallback_requests:
            fallback_results = _crawl_pages(fallback_requests)
            for request, result in zip(fallback_requests, fallback_results):
                for asset in result.get("assets") or []:
                    asset["article_title"] = asset.get("article_title") or request["title"]
                    asset["source_page_url"] = asset.get("source_page_url") or request["url"]
                    asset["publisher"] = asset.get("publisher") or request["publisher"]
                    asset["query"] = asset.get("query") or request["query"]
                    assets.append(asset)
            selected = _dedupe(assets)

    return {
        "assets": selected,
        "target": TARGET,
        "success_threshold": SUCCESS,
        "original_story_url": original_url,
        "automatic_queries": automatic_queries,
        "queries_used": search_queries,
        "manual_query": manual_query,
        "pages_scraped": len(page_requests),
        "related_pages": max(0, len(page_requests) - 1),
        "failure_state": (
            "ready" if len(selected) >= SUCCESS
            else "underfilled" if selected
            else "no_images"
        ),
    }


def same_query(query, used_queries):
    value = _clean(query, 260).casefold()
    return bool(value) and any(
        value == _clean(item, 260).casefold()
        for item in (used_queries or [])
    )


__all__ = ["TARGET", "SUCCESS", "build_queries", "crawl_visuals", "same_query"]
