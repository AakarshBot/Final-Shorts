"""Phase 2: direct manual image search across real-image sources.

Manual query only. Providers return real image bytes; this module only performs
basic download validation and content deduplication. Licensing and semantic
filters are intentionally not part of this test phase.
"""
from __future__ import annotations

import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from threading import local
from typing import Any
from urllib.parse import quote_plus
import re
import requests
import pillow_avif  # noqa: F401 - register AVIF decoding for search-result image bytes.
from PIL import Image, UnidentifiedImageError

TIMEOUT = 6
MAX_RESULTS_PER_SOURCE = max(4, min(20, int(os.getenv("VISUAL_SEARCH_RESULTS_PER_SOURCE", "12"))))
MIN_IMAGE_SIDE = 720
MIN_IMAGE_PIXELS = 800_000
MAX_IMAGE_BYTES = 12_000_000
MAX_RETURNED_IMAGES = 36
HEADERS = {"User-Agent": "FinalShorts/1.0 (https://github.com/aakarsh/final-shorts; visual-qc@finalshorts.local)"}

_SESSION_LOCAL = local()


def _get_session() -> requests.Session:
    """Use one pooled Session per worker thread; requests.Session is not shared cross-thread."""
    session = getattr(_SESSION_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4,
            pool_maxsize=4,
            max_retries=1,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _SESSION_LOCAL.session = session
    return session


def _clean_query(query: Any) -> str:
    return " ".join(str(query or "").split()).strip()[:300]


def _image_info(data: bytes) -> tuple[int, int] | None:
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image.verify()
        if min(width, height) < MIN_IMAGE_SIDE or width * height < MIN_IMAGE_PIXELS:
            return None
        return width, height
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _valid_image(data: bytes) -> bool:
    return _image_info(data) is not None


def _download(url: str, meta: dict[str, Any]) -> dict[str, Any] | None:
    urls_to_try = [url]
    fallback = meta.get("fallback_url")
    if fallback and fallback != url:
        urls_to_try.append(fallback)

    for candidate_url in urls_to_try:
        try:
            response = _get_session().get(
                str(candidate_url),
                timeout=(4, 9),
                headers={**HEADERS, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"},
                allow_redirects=True,
                stream=True,
            )
            response.raise_for_status()
            content_type = str(response.headers.get("content-type", "")).lower()
            if content_type and "image" not in content_type and not content_type.startswith("application/octet-stream"):
                continue
            declared_size = int(response.headers.get("content-length") or 0)
            if declared_size > MAX_IMAGE_BYTES:
                continue

            # Enforce the byte ceiling while streaming, rather than reading an
            # arbitrarily large response into memory and checking only afterwards.
            if callable(getattr(response, "iter_content", None)):
                chunks = []
                total_size = 0
                oversized = False
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total_size += len(chunk)
                    if total_size > MAX_IMAGE_BYTES:
                        oversized = True
                        break
                    chunks.append(chunk)
                if oversized:
                    continue
                data = b"".join(chunks)
            else:
                # Compatibility for simple response adapters and test doubles.
                data = response.content
                if len(data) > MAX_IMAGE_BYTES:
                    continue

            dimensions = _image_info(data)
            if dimensions is None:
                continue
            width, height = dimensions
            return {
                "bytes": data,
                "hash": hashlib.sha256(data).hexdigest(),
                "source": meta.get("source", "Web"),
                "source_page_url": meta.get("source_page_url") or response.url or str(candidate_url),
                "source_image_url": response.url or str(candidate_url),
                "width": width,
                "height": height,
                "title": str(meta.get("title") or ""),
            }
        except requests.RequestException:
            continue
    return None


def _download_many(items: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(3, len(items)), thread_name_prefix="visual-search-download") as executor:
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
            "iiprop": "url|mime|extmetadata|size",
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
        image_url = info.get("url") or info.get("thumburl")
        page_url = info.get("descriptionurl")
        if image_url:
            items.append((str(image_url), {
                "width": int(info.get("width") or 0),
                "height": int(info.get("height") or 0),
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
        image_url = result.get("image") or result.get("url") or result.get("thumbnail")
        fallback_url = result.get("thumbnail") if result.get("thumbnail") != image_url else None
        if image_url:
            items.append((str(image_url), {
                "fallback_url": fallback_url,
                "width": int(result.get("width") or 0),
                "height": int(result.get("height") or 0),
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
        image_url = src.get("original") or src.get("large2x") or src.get("large")
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
        image_url = urls.get("raw") or urls.get("full") or urls.get("regular")
        links = result.get("links") or {}
        if image_url:
            items.append((str(image_url), {
                "source": "Unsplash",
                "source_page_url": str(links.get("html") or image_url),
                "title": str(result.get("alt_description") or ""),
            }))
    return _download_many(items)


def _flickr(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://www.flickr.com/services/feeds/photos_public.gne",
        params={"text": query, "format": "json", "nojsoncallback": 1},
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    items = []
    for item in response.json().get("items", []):
        media = item.get("media", {})
        thumb_url = str(media.get("m") or "")
        if thumb_url:
            high_res = re.sub(r"_[a-z]\.jpg$", "_b.jpg", thumb_url)
            items.append((
                high_res,
                {
                    "source": "Flickr",
                    "source_page_url": str(item.get("link") or high_res),
                    "title": str(item.get("title") or ""),
                },
            ))
    return _download_many(items)


def _archive_org(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://archive.org/advancedsearch.php",
        params={
            "q": f"{query} mediatype:image",
            "fl[]": ["identifier", "title"],
            "rows": MAX_RESULTS_PER_SOURCE,
            "output": "json",
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    docs = response.json().get("response", {}).get("docs", [])
    items = []
    for doc in docs:
        ident = str(doc.get("identifier") or "")
        if ident:
            img_url = f"https://archive.org/services/img/{ident}"
            items.append((
                img_url,
                {
                    "source": "ArchiveOrg",
                    "source_page_url": f"https://archive.org/details/{ident}",
                    "title": str(doc.get("title") or ident),
                },
            ))
    return _download_many(items)


def _wikidata(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": min(MAX_RESULTS_PER_SOURCE, 4),
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    entities = response.json().get("search", [])
    if not isinstance(entities, list) or not entities:
        return []

    entity_ids = [str(e.get("id")) for e in entities if isinstance(e, dict) and e.get("id")]
    if not entity_ids:
        return []

    claims_resp = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": "|".join(entity_ids),
            "props": "claims",
            "format": "json",
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    claims_resp.raise_for_status()
    ent_data = claims_resp.json().get("entities", {})

    image_files = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        eid = str(ent.get("id") or "")
        label = str(ent.get("label") or query)
        claims = ent_data.get(eid, {}).get("claims", {})
        for prop in ("P18", "P154"):
            for snak in claims.get(prop, []):
                val = snak.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(val, str) and val.strip():
                    image_files.append((val.strip(), label, eid))

    if not image_files:
        return []

    file_titles = [f"File:{fn}" for fn, _, _ in image_files[:MAX_RESULTS_PER_SOURCE]]
    commons_resp = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "titles": "|".join(file_titles),
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1600,
            "format": "json",
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    commons_resp.raise_for_status()
    pages = commons_resp.json().get("query", {}).get("pages", {})

    title_to_info = {}
    for p in pages.values() if isinstance(pages, dict) else []:
        t = str(p.get("title") or "")
        info = (p.get("imageinfo") or [{}])[0]
        if info:
            title_to_info[t.casefold()] = info

    items = []
    for fn, label, eid in image_files[:MAX_RESULTS_PER_SOURCE]:
        info = title_to_info.get(f"File:{fn}".casefold())
        if not info:
            continue
        img_url = info.get("thumburl") or info.get("url")
        desc_url = info.get("descriptionurl") or f"https://www.wikidata.org/wiki/{eid}"
        if img_url:
            items.append((
                str(img_url),
                {
                    "source": "Wikidata",
                    "source_page_url": str(desc_url),
                    "title": f"{label} ({fn})",
                },
            ))
    return _download_many(items)


def _serpapi_bing(query: str) -> list[dict[str, Any]]:
    key = str(os.getenv("SERPAPI_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "q": query,
            "engine": "bing_images",
            "api_key": key,
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("images_results", [])[:MAX_RESULTS_PER_SOURCE]:
        if not isinstance(result, dict):
            continue
        orig = result.get("original")
        thumb = result.get("thumbnail")
        image_url = orig or thumb
        if image_url:
            items.append((
                str(image_url),
                {
                    "source": "Bing",
                    "source_page_url": str(result.get("link") or image_url),
                    "title": str(result.get("title") or ""),
                    "fallback_url": str(thumb or ""),
                },
            ))
    return _download_many(items)


def _serpapi_google(query: str) -> list[dict[str, Any]]:
    key = str(os.getenv("SERPAPI_API_KEY") or "").strip()
    if not key:
        return []
    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "q": query,
            "engine": "google_images",
            "api_key": key,
        },
        timeout=TIMEOUT,
        headers=HEADERS,
    )
    response.raise_for_status()
    items = []
    for result in response.json().get("images_results", [])[:MAX_RESULTS_PER_SOURCE]:
        if not isinstance(result, dict):
            continue
        orig = result.get("original")
        thumb = result.get("thumbnail")
        image_url = orig or thumb
        if image_url:
            items.append((
                str(image_url),
                {
                    "source": "Google Images",
                    "source_page_url": str(result.get("link") or image_url),
                    "title": str(result.get("title") or ""),
                    "fallback_url": str(thumb or ""),
                },
            ))
    return _download_many(items)


PROVIDERS = (
    ("Commons", _commons, True),
    ("DuckDuckGo", _ddg, True),
    ("Wikidata", _wikidata, True),
    ("Wikipedia", _wikipedia, True),
    ("Openverse", _openverse, True),
    ("Flickr", _flickr, True),
    ("ArchiveOrg", _archive_org, True),
    ("Bing", _serpapi_bing, False),
    ("Google Images", _serpapi_google, False),
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
            name in ("Bing", "Google Images") and os.getenv("SERPAPI_API_KEY")
        ) or (
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

    with ThreadPoolExecutor(max_workers=min(4, len(configured)), thread_name_prefix="visual-search-provider") as executor:
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

    query_terms = {
        token.casefold()
        for token in re.findall(r"[\\w]+", q, flags=re.UNICODE)
        if len(token) > 1
    }

    def quality_rank(asset):
        title = " ".join(str(asset.get(key) or "") for key in ("title", "article_title", "alt")).casefold()
        title_terms = set(re.findall(r"[\\w]+", title, flags=re.UNICODE))
        relevance = len(query_terms & title_terms) / max(1, len(query_terms))
        width = int(asset.get("width") or 0)
        height = int(asset.get("height") or 0)
        pixels = width * height
        resolution = min(18.0, pixels / 250_000)
        url = str(asset.get("source_image_url") or "").casefold()
        source_is_thumbnail = any(term in url for term in ("/thumb/", "thumbnail", "tse", "w=320", "w=480"))
        original_penalty = -12.0 if source_is_thumbnail else 0.0
        return (relevance * 80.0 + resolution + original_penalty, pixels)

    assets.sort(key=quality_rank, reverse=True)
    candidate_count = len(assets)
    # Preserve provider breadth and quality ranking while keeping the session
    # payload bounded; users can still browse every returned image in pages.
    assets = assets[:MAX_RETURNED_IMAGES]
    return {
        "query": q,
        "assets": assets,
        "candidate_count": candidate_count,
        "result_limit": MAX_RETURNED_IMAGES,
        "providers": {name: len(results.get(name, [])) for name, _ in configured},
        "errors": errors,
    }
