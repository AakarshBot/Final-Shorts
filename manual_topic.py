"""Manual story intake shared by Final-Shorts topic desks.

The helper deliberately returns the same Topic contract used by discovered stories,
so downstream Scriptwriter, Visuals and metadata stages do not need special cases.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import ipaddress
import re
from urllib.parse import unquote, urlparse

import requests

from topic_fetcher import Topic

HEADERS = {"User-Agent": "Final-Shorts/1.0 (manual story intake)"}
TIMEOUT_SECONDS = 5


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key or "").casefold(): str(value or "").strip() for key, value in attrs}
        if tag.casefold() == "title":
            self.in_title = True
        if tag.casefold() == "meta":
            key = values.get("property") or values.get("name") or values.get("itemprop")
            value = values.get("content")
            if key and value:
                self.metadata.setdefault(key.casefold(), value)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title and data.strip():
            self.title_parts.append(data.strip())


def _clean(value: object, limit: int = 4000) -> str:
    return re.sub(r"\\s+", " ", str(value or "")).strip()[:limit]


def _validated_http_url(value: object) -> str:
    url = _clean(value, 3000)
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError("Enter a valid news URL beginning with https:// or http://.") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Enter a valid public news URL beginning with https:// or http://.")
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local network URLs are not supported; enter a public news article URL.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified):
        raise ValueError("Private or local network addresses are not supported as news URLs.")
    return url


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = unquote(parsed.path.rstrip("/").split("/")[-1])
    slug = re.sub(r"(?i)\\.(?:html?|amp|php)$", "", slug)
    title = re.sub(r"[-_]+", " ", slug)
    title = re.sub(r"\\s+", " ", title).strip(" ._-/")
    return title[:260] or parsed.hostname or "Manually supplied news story"


def _page_metadata(url: str) -> tuple[str, str, str]:
    """Best-effort page metadata lookup; the downstream Scriptwriter extracts article text."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        response.raise_for_status()
        final_url = _validated_http_url(getattr(response, "url", "") or url)
        parser = _MetadataParser()
        parser.feed(str(getattr(response, "text", "") or ""))
        metadata = parser.metadata
        title = (
            metadata.get("og:title")
            or metadata.get("twitter:title")
            or metadata.get("headline")
            or " ".join(parser.title_parts)
        )
        description = (
            metadata.get("og:description")
            or metadata.get("description")
            or metadata.get("twitter:description")
        )
        title = re.sub(r"\\s+", " ", title).strip()
        description = re.sub(r"\\s+", " ", description).strip()
        return title[:260], description[:1500], final_url
    except (requests.RequestException, ValueError, OSError):
        # Some publishers block automated metadata requests. Keep the URL usable:
        # Scriptwriter will make its own article-extraction and corroboration attempt.
        return "", "", url


def create_manual_topic(
    headline: object = "",
    url: object = "",
    description: object = "",
) -> Topic:
    """Create a normal Topic from a headline, public article URL, or both.

    A supplied headline wins over page metadata. When only a URL is provided,
    metadata is fetched best-effort and a readable URL slug is the fallback.
    """
    title = _clean(headline, 260)
    source_url = _validated_http_url(url)
    summary = _clean(description, 1500)
    source = "Manual headline"
    if source_url:
        parsed = urlparse(source_url)
        source = (parsed.hostname or "News source").casefold().removeprefix("www.")
        if not title:
            extracted_title, extracted_description, resolved_url = _page_metadata(source_url)
            source_url = resolved_url
            title = extracted_title or _title_from_url(source_url)
            summary = summary or extracted_description
            if not extracted_title:
                summary = summary or "Headline metadata could not be read automatically. Verify the source and facts during Scriptwriter review."
    if not title:
        raise ValueError("Enter a manual headline, or paste a news URL so the factory can identify the story.")
    if len(title) < 4:
        raise ValueError("The headline is too short. Enter a more specific story headline.")
    now = datetime.now(timezone.utc)
    identity = hashlib.sha1(f"{title.casefold()}|{source_url}".encode("utf-8")).hexdigest()[:16]
    return Topic(
        title=title,
        source=source,
        published_at=now,
        url=source_url,
        description=summary,
        score=0.0,
        group_key=f"manual:{identity}",
    )


def topic_to_longform_candidate(topic: Topic) -> dict:
    """Adapt the shared Topic contract to the existing Long-form topic handoff."""
    from urllib.parse import urlparse

    published = topic.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    source_url = str(topic.url or "").strip()
    story_id = hashlib.sha1(f"{topic.title}|{source_url}".encode("utf-8")).hexdigest()[:16]
    reports = (
        [{"title": topic.title, "url": source_url, "publisher": topic.source or urlparse(source_url).hostname or "Manual source"}]
        if source_url
        else []
    )
    return {
        "story_id": f"manual-{story_id}",
        "title": topic.title,
        "url": source_url,
        "publisher": topic.source or "Manual headline",
        "published_at": published.isoformat(),
        "summary": topic.description or "Manually supplied story. Verify source coverage and depth before approving.",
        "reports": reports,
        "ranking_reason": "Manually supplied source; editorially verify its accuracy and suitability.",
        "manual_source": True,
    }
