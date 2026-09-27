"""Top-5 visual retrieval: one source URL at a time with a small manual-review pool."""

from __future__ import annotations

import asyncio
import hashlib
import html
import io
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, UnidentifiedImageError


STORY_MIN_IMAGES = 4
STORY_MAX_IMAGES = 6
IMAGE_MIN_SIDE = 500
MAX_IMAGE_BYTES = 8_000_000
PAGE_TIMEOUT_MS = 10_000
SEARCH_TIMEOUT = 8
RELATED_RESULTS = 8
BLOCKED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "youtube.com",
}
BAD_PATH_PARTS = {
    "/search",
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/topic/",
    "/feed",
    "/rss",
    "/sitemap",
}
BAD_IMAGE_TERMS = {
    "logo",
    "icon",
    "favicon",
    "sprite",
    "tracking",
    "pixel",
    "avatar",
    "placeholder",
    "advert",
    "banner",
    "social-share",
    "share-image",
    "default-image",
}
HEADERS = {
    "User-Agent": "Final-Shorts/1.0 (top5 visual retrieval)",
    "Accept": "text/html,application/xhtml+xml",
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "from", "by", "with", "after", "before", "during", "over", "into",
    "about", "this", "that", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "has", "have", "had", "will", "would", "could",
    "should", "says", "said", "report", "reports", "latest", "news", "story",
    "update", "today", "ahead", "versus", "vs", "v", "video", "photos",
    "photo", "images", "image", "pictures", "picture", "team", "match",
    "game", "sport", "sports", "cricket",
}


def _clean(value: Any, limit: int = 5000) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def _url(value: Any) -> str:
    value = _clean(value, 3000)
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _tokens(value: Any) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", _clean(value))
        if len(token) > 2 and token.casefold() not in STOPWORDS
    }


def _domain(url: str) -> str:
    return urlparse(url).netloc.casefold().split(":")[0].removeprefix("www.")


def _article_url_ok(url: str) -> bool:
    target = _url(url)
    if not target:
        return False
    domain = _domain(target)
    if domain in BLOCKED_HOSTS:
        return False
    path = urlparse(target).path.casefold()
    return not any(part in path for part in BAD_PATH_PARTS)


def _related_score(title: str, result_title: str) -> int:
    wanted = _tokens(title)
    found = _tokens(result_title)
    if not wanted or not found:
        return 0
    return len(wanted & found)


def _find_related_url(title: str, original_url: str, seen_urls: set[str]) -> str:
    try:
        from ddgs import DDGS

        results = DDGS(timeout=SEARCH_TIMEOUT).news(
            query=_clean(title, 260),
            region="in-en",
            safesearch="off",
            timelimit="w",
            max_results=RELATED_RESULTS,
        )
    except Exception:
        return ""

    original_key = original_url.casefold().rstrip("/")
    original_domain = _domain(original_url)
    candidates = []
    minimum_overlap = 2 if len(_tokens(title)) >= 2 else 1

    for result in results or []:
        if not isinstance(result, dict):
            continue
        target = _url(result.get("url") or result.get("href"))
        result_title = _clean(result.get("title"), 600)
        key = target.casefold().rstrip("/")
        if (
            not target
            or key == original_key
            or key in seen_urls
            or not result_title
            or not _article_url_ok(target)
        ):
            continue
        if _domain(target) == original_domain:
            continue
        score = _related_score(title, result_title)
        if score < minimum_overlap:
            continue
        candidates.append((score, target))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _absolute(value: Any, base_url: str) -> str:
    value = _clean(value, 3000).replace("\\/", "/")
    if not value or value.startswith(("data:", "blob:", "javascript:")):
        return ""
    target = _url(urljoin(base_url, value))
    if not target:
        return ""
    return target


def _bad_image_url(url: str) -> bool:
    value = _clean(url, 3000).casefold()
    return any(term in value for term in BAD_IMAGE_TERMS)


def _image_ok(data: bytes) -> bool:
    if not data or len(data) > MAX_IMAGE_BYTES:
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return (
                min(image.size) >= IMAGE_MIN_SIDE
                and image.size[0] * image.size[1] >= 300_000
            )
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _image_info(data: bytes) -> tuple[str, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            digest_image = image.convert("RGB").resize(
                (64, 64),
                Image.Resampling.LANCZOS,
            )
            return (
                hashlib.sha256(digest_image.tobytes()).hexdigest(),
                image.width,
                image.height,
            )
    except Exception:
        return hashlib.sha256(data).hexdigest(), 0, 0


def _image_key(url: str) -> str:
    parsed = urlparse(_clean(url, 3000))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}{parsed.path}"


def _walk_json_images(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            key = str(key).casefold()
            if key in {"image", "contenturl", "thumbnailurl"}:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict):
                    for nested in (
                        item.get("url"),
                        item.get("contentUrl"),
                        item.get("contenturl"),
                    ):
                        if nested:
                            yield str(nested)
            yield from _walk_json_images(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json_images(item)


BROWSER_SCRIPT = r"""
() => {
  const meta = {};
  document.querySelectorAll('meta[property], meta[name], meta[itemprop]').forEach(el => {
    const key = (el.getAttribute('property') || el.getAttribute('name') ||
      el.getAttribute('itemprop') || '').toLowerCase();
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
      context: context.slice(0, 1400)
    };
  });

  const linkImages = Array.from(
    document.querySelectorAll('link[rel~="image_src"], link[rel~="preload"][as="image"]')
  ).map(el => el.getAttribute('href') || '').filter(Boolean);

  const backgrounds = Array.from(
    document.querySelectorAll('article [style], main [style]')
  ).map(el => {
    const match = (getComputedStyle(el).backgroundImage || '')
      .match(/url\(["']?(.*?)["']?\)/);
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


def _srcset(value: Any) -> list[str]:
    return [
        _clean(part, 1600).split(" ", 1)[0]
        for part in str(value or "").split(",")
        if _clean(part, 1600)
    ]


async def _browser_page(context, request: dict[str, Any]) -> dict[str, Any]:
    page = await context.new_page()
    network = {}

    def remember(response):
        try:
            if response.request.resource_type == "image" and response.ok:
                if len(network) < 120:
                    network.setdefault(response.url, response)
                    key = _image_key(response.url)
                    if key:
                        network.setdefault(key, response)
        except Exception:
            pass

    page.on("response", remember)
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
                "url": request["url"],
                "error": f"navigation: {type(exc).__name__}: {exc}",
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
            data = await page.evaluate(BROWSER_SCRIPT)
        except Exception as exc:
            return {
                "assets": [],
                "url": page.url or request["url"],
                "error": f"page-evaluation: {type(exc).__name__}: {exc}",
            }

        base_url = data.get("finalUrl") or request["url"]
        page_title = _clean(data.get("title") or request.get("title"), 600)
        candidates = []

        def add(raw_url, method, payload=None):
            target = _absolute(raw_url, base_url)
            if target and not _bad_image_url(target):
                candidates.append({
                    **(payload or {}),
                    "url": target,
                    "method": method,
                })

        meta = data.get("meta") or {}
        for key in (
            "og:image",
            "og:image:url",
            "og:image:secure_url",
            "twitter:image",
        ):
            add(meta.get(key), "metadata")

        for raw in data.get("jsonLd") or []:
            try:
                value = raw if isinstance(raw, (dict, list)) else __import__("json").loads(raw)
            except (TypeError, ValueError):
                continue
            for target in _walk_json_images(value):
                add(target, "json-ld:image")

        for target in data.get("linkImages") or []:
            add(target, "link:image")

        for target in data.get("backgrounds") or []:
            add(target, "background-image", {"in_article": True})

        for markup in data.get("noscripts") or []:
            for match in re.finditer(
                r"""<(?:img|source)\b[^>]*(?:src|data-src|data-lazy-src|data-original|data-image|data-srcset)\s*=\s*["']([^"']+)["']""",
                markup,
                re.IGNORECASE,
            ):
                for target in _srcset(match.group(1)):
                    add(target, "noscript:image", {"in_article": True})

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
                add(image.get(key), method, payload)
            for target in (
                _srcset(image.get("srcset"))
                + _srcset(image.get("dataSrcset"))
                + _srcset(image.get("dataLazySrcset"))
            ):
                add(target, "srcset", payload)

        unique = []
        seen = set()
        for candidate in candidates:
            key = candidate["url"].casefold()
            if key in seen:
                continue
            seen.add(key)
            context = _clean(
                " ".join(
                    str(candidate.get(key) or "")
                    for key in ("alt", "title", "context")
                ),
                1800,
            )
            score = 0
            if candidate.get("in_article"):
                score += 30
            if candidate.get("in_figure"):
                score += 12
            if candidate.get("method") in {"metadata", "json-ld:image"}:
                score += 16
            width = int(candidate.get("width") or 0)
            height = int(candidate.get("height") or 0)
            if min(width, height) >= 1200:
                score += 12
            score += min(20, len(_tokens(context) & {
                "action", "match", "playing", "batting", "bowling", "fielding",
                "wicket", "goal", "race", "running", "training", "celebrate",
                "celebration", "catch", "caught", "throw", "shoot", "shot",
            }) * 6)
            unique.append({**candidate, "score": score})

        unique.sort(
            key=lambda item: (
                -int(item.get("score") or 0),
                -int(item.get("height") or 0),
                -int(item.get("width") or 0),
            )
        )

        assets = []
        hashes = set()
        for candidate in unique[: STORY_MAX_IMAGES * 4]:
            try:
                response = await page.request.get(
                    candidate["url"],
                    timeout=min(7500, PAGE_TIMEOUT_MS),
                    headers={
                        **HEADERS,
                        "Referer": base_url,
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                )
                data_bytes = await response.body() if response.ok else b""
            except Exception:
                data_bytes = b""

            if not _image_ok(data_bytes):
                for key in (candidate["url"], _image_key(candidate["url"])):
                    network_response = network.get(key)
                    if network_response is None:
                        continue
                    try:
                        data_bytes = await network_response.body()
                    except Exception:
                        data_bytes = b""
                    if _image_ok(data_bytes):
                        break

            if not _image_ok(data_bytes):
                continue

            digest, width, height = _image_info(data_bytes)
            if digest in hashes:
                continue
            hashes.add(digest)
            assets.append({
                "bytes": data_bytes,
                "hash": digest,
                "source_page_url": base_url,
                "source_image_url": candidate["url"],
                "publisher": _clean(
                    meta.get("og:site_name")
                    or request.get("source")
                    or _domain(base_url),
                    160,
                ),
                "article_title": page_title,
                "published_at": request.get("published_at", ""),
                "method": candidate["method"],
                "width": width,
                "height": height,
                "score": candidate.get("score", 0),
            })
            if len(assets) >= STORY_MAX_IMAGES:
                break

        return {
            "assets": assets,
            "title": page_title,
            "url": base_url,
            "candidate_count": len(unique),
            "network_image_count": len(network),
            "error": "",
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


class _StaticParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.candidates = []
        self.json_ld = []
        self.in_script = False
        self.script_type = ""
        self.script_parts = []

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
            self.in_script = True
            self.script_type = _clean(data.get("type"), 120).casefold()
            self.script_parts = []
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
            for value in _srcset(data.get(key)):
                self.candidates.append((value, "static-srcset", payload))

    def handle_endtag(self, tag):
        if tag.casefold() != "script" or not self.in_script:
            return
        if "ld+json" in self.script_type:
            raw = "".join(self.script_parts).strip()
            if raw:
                try:
                    import json
                    self.json_ld.append(json.loads(html.unescape(raw)))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        self.in_script = False
        self.script_type = ""
        self.script_parts = []

    def handle_data(self, data):
        if self.in_script:
            self.script_parts.append(data)


def _static_page(request: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(
            request["url"],
            timeout=SEARCH_TIMEOUT,
            headers=HEADERS,
            allow_redirects=True,
        )
        response.raise_for_status()
        markup = response.content[:4_000_000].decode(
            response.encoding or response.apparent_encoding or "utf-8",
            errors="replace",
        )
        base_url = response.url or request["url"]
    except (requests.RequestException, UnicodeError):
        return {"assets": [], "url": request["url"], "error": "static-navigation-failed"}

    parser = _StaticParser()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:
        return {
            "assets": [],
            "url": base_url,
            "error": f"static-parse: {type(exc).__name__}: {exc}",
        }

    candidates = []
    for key in (
        "og:image",
        "og:image:url",
        "og:image:secure_url",
        "twitter:image",
        "twitter:image:src",
    ):
        if parser.meta.get(key):
            candidates.append((parser.meta[key], "metadata", {}))

    for value in parser.json_ld:
        for target in _walk_json_images(value):
            candidates.append((target, "json-ld:image", {}))
    candidates.extend(parser.candidates)

    assets = []
    hashes = set()
    seen_urls = set()
    for raw_url, method, payload in candidates[: STORY_MAX_IMAGES * 8]:
        target = _absolute(raw_url, base_url)
        key = target.casefold()
        if not target or key in seen_urls or _bad_image_url(target):
            continue
        seen_urls.add(key)

        try:
            response = requests.get(
                target,
                timeout=SEARCH_TIMEOUT,
                headers={
                    **HEADERS,
                    "Referer": base_url,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
                allow_redirects=True,
            )
            response.raise_for_status()
            data = response.content
        except requests.RequestException:
            continue

        if not _image_ok(data):
            continue
        digest, width, height = _image_info(data)
        if digest in hashes:
            continue
        hashes.add(digest)
        assets.append({
            "bytes": data,
            "hash": digest,
            "source_page_url": base_url,
            "source_image_url": target,
            "publisher": _clean(
                parser.meta.get("og:site_name")
                or request.get("source")
                or _domain(base_url),
                160,
            ),
            "article_title": _clean(
                parser.meta.get("og:title") or request.get("title"),
                600,
            ),
            "published_at": request.get("published_at", ""),
            "method": method,
            "width": width,
            "height": height,
        })
        if len(assets) >= STORY_MAX_IMAGES:
            break

    return {
        "assets": assets,
        "title": _clean(parser.meta.get("og:title") or request.get("title"), 600),
        "url": base_url,
        "static_candidates": len(candidates),
        "error": "",
    }


def _merge_assets(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    hashes = set()
    urls = set()

    for asset in sum((list(group) for group in groups), []):
        digest = _clean(asset.get("hash"), 120)
        target = _clean(asset.get("source_image_url"), 3000).casefold().rstrip("/")
        if digest and digest in hashes:
            continue
        if target and target in urls:
            continue
        if digest:
            hashes.add(digest)
        if target:
            urls.add(target)
        output.append(asset)

    output.sort(
        key=lambda item: (
            -int(item.get("score") or 0),
            -int(item.get("height") or 0),
            -int(item.get("width") or 0),
        )
    )
    return output[:STORY_MAX_IMAGES]


async def _scrape_url(context, request: dict[str, Any]) -> dict[str, Any]:
    browser_result = await _browser_page(context, request)
    browser_assets = list(browser_result.get("assets") or [])
    if len(browser_assets) >= STORY_MIN_IMAGES:
        return {
            **browser_result,
            "assets": browser_assets[:STORY_MAX_IMAGES],
            "method": "browser",
        }

    static_result = await asyncio.to_thread(_static_page, request)
    assets = _merge_assets(browser_assets, list(static_result.get("assets") or []))
    return {
        **browser_result,
        "assets": assets,
        "title": browser_result.get("title") or static_result.get("title") or request.get("title", ""),
        "url": browser_result.get("url") or static_result.get("url") or request["url"],
        "static_fallback_attempted": True,
        "static_candidates": int(static_result.get("static_candidates") or 0),
        "static_error": str(static_result.get("error") or ""),
        "method": "browser+static",
    }


async def _scrape_story(context, story: dict[str, Any], story_index: int) -> dict[str, Any]:
    title = _clean(story.get("title"), 600)
    original_url = _url(story.get("url"))
    if not title or not original_url:
        return {
            "story_index": story_index,
            "title": title,
            "url": original_url,
            "assets": [],
            "urls_scraped": [],
            "related_urls": [],
            "failure_state": "invalid_story",
        }

    request = {
        "url": original_url,
        "title": title,
        "source": _clean(story.get("source"), 160),
        "published_at": _clean(story.get("published_at"), 120),
    }
    result = await _scrape_url(context, request)
    assets = list(result.get("assets") or [])
    urls_scraped = [original_url]
    related_urls = []
    seen_urls = {original_url.casefold().rstrip("/")}

    while len(assets) < STORY_MIN_IMAGES:
        related_url = await asyncio.to_thread(
            _find_related_url,
            title,
            original_url,
            seen_urls,
        )
        if not related_url:
            break
        related_key = related_url.casefold().rstrip("/")
        seen_urls.add(related_key)
        related_urls.append(related_url)

        related_request = {
            "url": related_url,
            "title": title,
            "source": "",
            "published_at": "",
        }
        related_result = await _scrape_url(context, related_request)
        urls_scraped.append(related_url)
        assets = _merge_assets(
            assets,
            list(related_result.get("assets") or []),
        )

    failure_state = (
        "ready"
        if len(assets) >= STORY_MIN_IMAGES
        else "underfilled"
        if assets
        else "no_images"
    )
    return {
        "story_index": story_index,
        "title": title,
        "url": original_url,
        "assets": assets,
        "urls_scraped": urls_scraped,
        "related_urls": related_urls,
        "image_count": len(assets),
        "failure_state": failure_state,
    }


def crawl_top5_visuals(stories: list[dict[str, Any]]) -> dict[str, Any]:
    """Scrape each of five selected stories until each has a small usable pool."""
    if len(stories) != 5:
        raise ValueError("Top-5 Visual Fetcher requires exactly five selected stories.")

    async def run():
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required for Top-5 Visuals. Install requirements and Chromium."
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
                        _scrape_story(context, story, index)
                        for index, story in enumerate(stories, 1)
                    )
                )
                await context.close()
                return results
            finally:
                await browser.close()

    story_results = asyncio.run(run())
    return {
        "schema": "final-shorts.top5-visuals.v1",
        "stories": story_results,
        "story_count": 5,
        "ready_count": sum(
            1 for result in story_results if result.get("failure_state") == "ready"
        ),
        "total_assets": sum(
            len(result.get("assets") or []) for result in story_results
        ),
    }
