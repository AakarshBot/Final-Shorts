"""Phase 2: direct manual image search across real-image sources.

Manual query only. Providers return real image bytes; this module only performs
basic download validation and content deduplication. Licensing and semantic
filters are intentionally not part of this test phase.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote_plus

import requests
from PIL import Image, UnidentifiedImageError

TIMEOUT = 8
MAX_RESULTS_PER_SOURCE = max(4, min(20, int(os.getenv("VISUAL_SEARCH_RESULTS_PER_SOURCE", "12"))))
MAX_IMAGE_BYTES = 12_000_000
HEADERS = {"User-Agent": "Final-Shorts/1.0 (+manual-image-search)"}


def _clean_query(query: Any) -> str:
    return " ".join(str(query or "").split()).strip()[:300]


def _valid_image(data: bytes) -> bool:
    if not data or len(data) > MAX_IMAGE_BYTES:
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _download(url: str, meta: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.get(
            str(url),
            timeout=TIMEOUT,
            headers={**HEADERS, "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"},
            allow_redirects=True,
        )
        response.raise_for_status()
        data = response.content
        content_type = str(response.headers.get("content-type", "")).lower()
        if content_type and "image" not in content_type and not content_type.startswith("application/octet-stream"):
            return None
        if not _valid_image(data):
            return None
        return {
            "bytes": data,
            "hash": hashlib.sha256(data).hexdigest(),
            "source": meta.get("source", "Web"),
            "source_page_url": meta.get("source_page_url") or response.url or str(url),
            "source_image_url": response.url or str(url),
            "title": str(meta.get("title") or ""),
        }
    except requests.RequestException:
        return None


def _download_many(items: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(6, len(items)), thread_name_prefix="visual-search-download") as executor:
        results = executor.map(lambda item: _download(item[0], item[1]), items)
        return [item for item in results if item]


def _commons(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": MAX_RESULTS_PER_SOURCE,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": 1600,
            "format": "json",
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    items = []
    for page in pages.values() if isinstance(pages, dict) else []:
        info = (page.get("imageinfo") or [{}])[0]
        image_url = info.get("thumburl") or info.get("url")
        page_url = info.get("descriptionurl")
        if image_url:
            items.append((str(image_url), {
                "source": "Commons",
                "source_page_url": str(page_url or image_url),
                "title": str(page.get("title") or "").removeprefix("File:"),
            }))
    return _download_many(items)


def _ddg(query: str) -> list[dict[str, Any]]:
    from ddgs import DDGS

    results = DDGS(timeout=TIMEOUT).images(
        query,
        safesearch="moderate",
        max_results=MAX_RESULTS_PER_SOURCE,
    )
    items = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        image_url = result.get("image") or result.get("thumbnail") or result.get("url")
        if image_url:
            items.append((str(image_url), {
                "source": "DuckDuckGo",
                "source_page_url": str(result.get("url") or image_url),
                "title": str(result.get("title") or ""),
            }))
    return _download_many(items)


def _wikipedia(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 0,
            "gsrlimit": MAX_RESULTS_PER_SOURCE,
            "prop": "pageimages",
            "piprop": "original",
            "pithumbsize": 1600,
            "format": "json",
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    items = []
    for page in pages.values() if isinstance(pages, dict) else []:
        original = page.get("original") or {}
        image_url = original.get("source")
        if image_url:
            items.append((str(image_url), {
                "source": "Wikipedia",
                "source_page_url": f"https://en.wikipedia.org/wiki/{quote_plus(str(page.get('title') or '').replace(' ', '_'))}",
                "title": str(page.get("title") or ""),
            }))
    return _download_many(items)


def _openverse(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://api.openverse.org/v1/images/",
        params={"q": query, "page_size": MAX_RESULTS_PER_SOURCE, "mature": "false"},
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("results", []):
        if not isinstance(result, dict):
            continue
        image_url = result.get("url") or result.get("thumbnail")
        if image_url:
            items.append((str(image_url), {
                "source": "Openverse",
                "source_page_url": str(result.get("foreign_landing_url") or result.get("url") or image_url),
                "title": str(result.get("title") or ""),
            }))
    return _download_many(items)


def _pixabay(query: str) -> list[dict[str, Any]]:
    key = str(os.getenv("PIXABAY_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://pixabay.com/api/",
        params={"key": key, "q": query, "image_type": "photo", "safesearch": "true", "per_page": MAX_RESULTS_PER_SOURCE},
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("hits", []):
        image_url = result.get("largeImageURL") or result.get("webformatURL")
        if image_url:
            items.append((str(image_url), {
                "source": "Pixabay",
                "source_page_url": str(result.get("pageURL") or image_url),
                "title": str(result.get("tags") or ""),
            }))
    return _download_many(items)


def _pexels(query: str) -> list[dict[str, Any]]:
    key = str(os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "per_page": MAX_RESULTS_PER_SOURCE},
        headers={"Authorization": key, **HEADERS},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("photos", []):
        src = result.get("src") or {}
        image_url = src.get("large2x") or src.get("large") or src.get("original")
        if image_url:
            items.append((str(image_url), {
                "source": "Pexels",
                "source_page_url": str(result.get("url") or image_url),
                "title": str(result.get("alt") or ""),
            }))
    return _download_many(items)


def _unsplash(query: str) -> list[dict[str, Any]]:
    key = str(os.getenv("UNSPLASH_ACCESS_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": MAX_RESULTS_PER_SOURCE},
        headers={"Authorization": f"Client-ID {key}", **HEADERS},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("results", []):
        urls = result.get("urls") or {}
        image_url = urls.get("regular") or urls.get("full") or urls.get("raw")
        links = result.get("links") or {}
        if image_url:
            items.append((str(image_url), {
                "source": "Unsplash",
                "source_page_url": str(links.get("html") or image_url),
                "title": str(result.get("alt_description") or ""),
            }))
    return _download_many(items)


PROVIDERS = (
    ("Commons", _commons, True),
    ("DuckDuckGo", _ddg, True),
    ("Wikipedia", _wikipedia, True),
    ("Openverse", _openverse, True),
    ("Pixabay", _pixabay, False),
    ("Pexels", _pexels, False),
    ("Unsplash", _unsplash, False),
)


def search_images(query: str) -> dict[str, Any]:
    q = _clean_query(query)
    if not q:
        return {"query": "", "assets": [], "providers": {}, "errors": {}}

    configured = []
    for name, provider, always_on in PROVIDERS:
        if always_on or (
            name == "Pixabay" and os.getenv("PIXABAY_API_KEY")
        ) or (
            name == "Pexels" and os.getenv("PEXELS_API_KEY")
        ) or (
            name == "Unsplash" and os.getenv("UNSPLASH_ACCESS_KEY")
        ):
            configured.append((name, provider))

    results: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}

    def run(item):
        name, provider = item
        try:
            return name, provider(q), ""
        except Exception as exc:
            return name, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=min(7, len(configured)), thread_name_prefix="visual-search-provider") as executor:
        for name, items, error in executor.map(run, configured):
            results[name] = items
            if error:
                errors[name] = error

    assets = []
    seen_hashes: set[str] = set()
    seen_urls: set[str] = set()
    for name, _provider in configured:
        for asset in results.get(name, []):
            digest = str(asset.get("hash") or "")
            image_url = str(asset.get("source_image_url") or "").casefold().rstrip("/")
            if digest and digest in seen_hashes:
                continue
            if image_url and image_url in seen_urls:
                continue
            if digest:
                seen_hashes.add(digest)
            if image_url:
                seen_urls.add(image_url)
            assets.append(asset)

    return {
        "query": q,
        "assets": assets,
        "providers": {name: len(results.get(name, [])) for name, _ in configured},
        "errors": errors,
    }
