"""Free, resilient discovery from curated cricket news and official video feeds.

All providers normalize to small dictionaries compatible with Topic and long-form
story records. A provider failure is isolated; no API key or paid service is needed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

TIMEOUT = 3.5
CACHE_TTL_SECONDS = 90
MAX_FEED_WORKERS = 10
DEFAULT_LOOKBACK_DAYS = 14
HEADERS = {
    "User-Agent": "Final-Shorts-Cricket-TopicFetcher/2.0 (+https://github.com/AakarshBot/Final-Shorts)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}

# Publisher feeds provide stories that broad query search can miss, particularly
# interviews, opinion, analysis, official announcements, and domestic/women's cricket.
# YouTube feeds are deliberately included as interview/press-conference discovery leads.
CRICKET_FEEDS: tuple[tuple[str, str, str], ...] = (
    ("ESPNcricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", "publisher"),
    ("BBC Sport Cricket", "https://feeds.bbci.co.uk/sport/cricket/rss.xml", "publisher"),
    ("The Guardian Cricket", "https://www.theguardian.com/sport/cricket/rss", "publisher"),
    ("The Indian Express Cricket", "https://indianexpress.com/section/sports/cricket/feed/", "publisher"),
    ("NDTV Cricket", "http://feeds.feedburner.com/ndtvsports-cricket", "publisher"),
    ("Times of India Cricket", "https://timesofindia.indiatimes.com/rssfeeds/54829575.cms", "publisher"),
    ("The Hindu Cricket", "https://www.thehindu.com/sport/cricket/feeder/default.rss", "publisher"),
    ("CricTracker", "https://www.crictracker.com/feed/", "publisher"),
    ("Cricket Times", "https://crickettimes.com/feed/", "publisher"),
    ("CricketWeb", "https://www.cricketweb.net/feed/", "publisher"),
    ("The Roar Cricket", "https://www.theroar.com.au/cricket/feed/", "publisher"),
    ("Cricbuzz YouTube", "https://www.youtube.com/feeds/videos.xml?channel_id=UCSRQXk5yErn4e14vN76upOw", "video"),
    ("Cricket Australia YouTube", "https://www.youtube.com/feeds/videos.xml?user=cricketaustraliatv", "video"),
    ("ECB Cricket YouTube", "https://www.youtube.com/feeds/videos.xml?user=ecbcricket", "video"),
    ("Pakistan Cricket YouTube", "https://www.youtube.com/feeds/videos.xml?channel_id=UCiWrjBhlICf_L_RK5y6Vrxw", "video"),
    ("Sri Lanka Cricket YouTube", "https://www.youtube.com/feeds/videos.xml?user=TheOfficialSLC", "video"),
    ("Cricket Unfiltered Podcast", "https://rss.acast.com/cricket-unfiltered", "podcast"),
    ("Sky Sports Cricket Podcast", "https://www.spreaker.com/show/3387348/episodes/feed", "podcast"),
    ("BBC Stumped Podcast", "https://podcasts.files.bbci.co.uk/p02gsrmh.rss", "podcast"),
    ("ESPN Switch Hit Podcast", "https://feeds.megaphone.fm/ESP9247246951", "podcast"),
)

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()
_TRACKING_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ocid", "cmpid",
}


def _clean(value: object, limit: int = 4000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _local_name(tag: object) -> str:
    return str(tag or "").rsplit("}", 1)[-1].split(":")[-1].casefold()


def _canonical_url(value: object) -> str:
    try:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
            return ""
        query = [
            (key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in _TRACKING_KEYS
        ]
        return urlunparse((
            parsed.scheme.casefold(),
            parsed.netloc.casefold().removeprefix("www."),
            parsed.path.rstrip("/") or "/",
            "",
            urlencode(sorted(query)),
            "",
        ))
    except (TypeError, ValueError):
        return ""


def _parse_date(value: object) -> datetime | None:
    text = _clean(value, 200)
    if not text:
        return None
    parsed = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _child_values(element: ET.Element) -> dict[str, list[ET.Element]]:
    values: dict[str, list[ET.Element]] = {}
    for child in list(element):
        values.setdefault(_local_name(child.tag), []).append(child)
    return values


def _text_from(values: dict[str, list[ET.Element]], *names: str) -> str:
    for name in names:
        for node in values.get(name.casefold(), []):
            text = _clean(" ".join(node.itertext()), 4000)
            if text:
                return text
    return ""


def _link_from(values: dict[str, list[ET.Element]]) -> str:
    for node in values.get("link", []):
        href = node.attrib.get("href")
        rel = node.attrib.get("rel", "alternate").casefold()
        if href and rel in {"alternate", ""}:
            return str(href).strip()
        if href and not rel:
            return str(href).strip()
        text = _clean(" ".join(node.itertext()), 3000)
        if text.startswith(("https://", "http://")):
            return text
    return ""


def _parse_feed(xml_text: str, fallback_source: str, now: datetime | None = None) -> list[dict]:
    """Parse RSS 2.x, RSS with namespaces, Atom, and YouTube Atom feeds."""
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(xml_text)
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    rows: list[dict] = []
    seen: set[str] = set()
    cutoff = now - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    for entry in entries:
        values = _child_values(entry)
        title = _text_from(values, "title")
        url = _canonical_url(_link_from(values) or _text_from(values, "guid", "id"))
        summary = _text_from(values, "description", "summary", "subtitle", "content", "encoded")
        published = _parse_date(_text_from(values, "pubdate", "published", "updated", "date", "issued"))
        if not title or not url or not published or published > now + timedelta(hours=12):
            continue
        if published < cutoff or url in seen:
            continue

        publisher = _text_from(values, "source") or fallback_source
        # Remove the common RSS publisher suffix without destroying legitimate titles.
        clean_title = title
        for separator in (" | ", " - ", " – ", " — "):
            suffix = separator + publisher
            if publisher and clean_title.casefold().endswith(suffix.casefold()):
                clean_title = clean_title[:-len(suffix)].strip()
                break
        rows.append({
            "title": clean_title,
            "source": publisher,
            "published_at": published,
            "url": url,
            "description": summary,
            "feed_source": fallback_source,
        })
        seen.add(url)
    return rows


def _fetch_feed(source: str, url: str, kind: str, now_ts: float) -> list[dict]:
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and now_ts - cached[0] < CACHE_TTL_SECONDS:
            return [dict(row) for row in cached[1]]

    rows: list[dict] = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        rows = _parse_feed(response.text, source)
        for row in rows:
            row["source_kind"] = kind
    except (requests.RequestException, ET.ParseError, ValueError, TypeError, OSError):
        # Empty results are cached too: a dead feed must not slow every Streamlit rerun.
        rows = []

    with _CACHE_LOCK:
        _CACHE[url] = (now_ts, [dict(row) for row in rows])
    return rows


def fetch_cricket_feed_items(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """Fetch and normalize curated feeds. Failures are isolated and short-lived cached.

    Returns dictionaries with title/source/published_at/url/description. This remains
    usable without credentials and deliberately does not require an LLM.
    """
    if lookback_days <= 0:
        return []
    now = datetime.now(timezone.utc)
    now_ts = time.time()
    gathered: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(MAX_FEED_WORKERS, len(CRICKET_FEEDS))) as pool:
        futures = {
            pool.submit(_fetch_feed, source, url, kind, now_ts): (source, url)
            for source, url, kind in CRICKET_FEEDS
        }
        for future in as_completed(futures):
            try:
                gathered.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError, OSError):
                continue

    cutoff = now - timedelta(days=lookback_days)
    chosen: dict[str, dict] = {}
    for row in gathered:
        published = row.get("published_at")
        if not isinstance(published, datetime) or published < cutoff or published > now + timedelta(hours=12):
            continue
        key = row["url"]
        previous = chosen.get(key)
        if previous is None or len(row.get("description", "")) > len(previous.get("description", "")):
            chosen[key] = row
    return sorted(
        chosen.values(),
        key=lambda row: row["published_at"],
        reverse=True,
    )


def clear_cricket_feed_cache() -> None:
    """Clear cached feed responses; intended for deterministic tests."""
    with _CACHE_LOCK:
        _CACHE.clear()


__all__ = ["CRICKET_FEEDS", "fetch_cricket_feed_items", "clear_cricket_feed_cache", "_parse_feed"]
