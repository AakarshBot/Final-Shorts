"""Free, read-only YouTube channel analytics helpers."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

ROOT = Path(__file__).resolve().parent
ANALYTICS_TOKEN_PATH = ROOT / "analytics_token.json"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
REQUIRED_SCOPES = frozenset({ANALYTICS_SCOPE, YOUTUBE_READONLY_SCOPE})

SUMMARY_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
    "subscribersGained,subscribersLost,likes,comments,shares"
)
DAILY_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,"
    "subscribersGained,subscribersLost"
)
VIDEO_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
    "subscribersGained,likes,comments,shares"
)


def missing_required_scopes(scopes: Iterable[str] | None) -> set[str]:
    """Return the required read-only OAuth scopes missing from a token."""
    return set(REQUIRED_SCOPES) - set(scopes or ())


def load_analytics_credentials(
    token_path: str | Path = ANALYTICS_TOKEN_PATH,
) -> Credentials:
    """Load/refresh the read-only analytics token, never the upload token."""
    path = Path(token_path)
    if not path.is_file():
        raise RuntimeError(
            "Analytics is not authorized yet. Run python authorize_youtube_analytics.py "
            "from the factory folder."
        )
    try:
        credentials = Credentials.from_authorized_user_file(str(path))
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            "analytics_token.json is invalid. Run python authorize_youtube_analytics.py again."
        ) from exc

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            path.write_text(credentials.to_json(), encoding="utf-8")
        except RefreshError as exc:
            raise RuntimeError(
                "The analytics authorization was revoked or expired. "
                "Run python authorize_youtube_analytics.py again."
            ) from exc
    if not credentials.valid:
        raise RuntimeError(
            "The analytics token is not valid. Run python authorize_youtube_analytics.py again."
        )

    missing = missing_required_scopes(credentials.scopes)
    if missing:
        raise RuntimeError(
            "The analytics token is missing read-only scope(s): "
            + ", ".join(sorted(missing))
            + ". Run python authorize_youtube_analytics.py again. "
            "The factory upload token is not modified."
        )
    return credentials


def build_analytics_clients(credentials: Credentials) -> tuple[Resource, Resource]:
    """Return YouTube Analytics API v2 and YouTube Data API v3 clients."""
    analytics = build(
        "youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False
    )
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    return analytics, youtube


def reporting_date_range(
    days: int, *, today: date | None = None, lag_days: int = 2
) -> tuple[str, str]:
    """Return inclusive YYYY-MM-DD bounds with a small processing-delay buffer."""
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days must be a positive integer")
    if isinstance(lag_days, bool) or not isinstance(lag_days, int) or lag_days < 0:
        raise ValueError("lag_days must be a non-negative integer")
    end_date = (today or date.today()) - timedelta(days=lag_days)
    start_date = end_date - timedelta(days=days - 1)
    return start_date.isoformat(), end_date.isoformat()


def rows_to_dicts(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert columnHeaders/rows from an Analytics API response to dictionaries."""
    payload = payload if isinstance(payload, dict) else {}
    headers = [
        str(header.get("name") or "")
        for header in (payload.get("columnHeaders") or [])
        if isinstance(header, dict)
    ]
    return [
        {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
        for row in (payload.get("rows") or [])
        if isinstance(row, (list, tuple))
    ]


def _query_rows(
    analytics: Resource,
    start_date: str,
    end_date: str,
    metrics: str,
    *,
    dimensions: str | None = None,
    sort: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if sort:
        params["sort"] = sort
    if dimensions and max_results:
        params["maxResults"] = max_results
    response = analytics.reports().query(**params).execute(num_retries=2)
    return rows_to_dicts(response)


def _optional_report(
    analytics: Resource,
    start_date: str,
    end_date: str,
    metrics: str,
    *,
    dimensions: str,
    sort: str | None = None,
    max_results: int = 10,
) -> tuple[list[dict[str, Any]], str]:
    try:
        return _query_rows(
            analytics, start_date, end_date, metrics,
            dimensions=dimensions, sort=sort, max_results=max_results,
        ), ""
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def fetch_channel_analytics(
    analytics: Resource,
    youtube: Resource,
    *,
    days: int = 28,
    today: date | None = None,
) -> dict[str, Any]:
    """Fetch channel identity, summary KPIs, daily trends, top videos, and discovery sources."""
    start_date, end_date = reporting_date_range(days, today=today)
    response = youtube.channels().list(
        part="snippet,statistics,contentDetails", mine=True, maxResults=1
    ).execute(num_retries=2)
    channels = response.get("items") or []
    if not channels:
        raise RuntimeError(
            "No YouTube channel was returned for this Google account. "
            "Re-authorize using the account that owns the target channel."
        )

    item = channels[0]
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    thumb_set = snippet.get("thumbnails") or {}
    channel_thumb = (thumb_set.get("medium") or thumb_set.get("default") or {}).get("url")

    # Fail visibly if the core summary cannot be fetched.
    summary_rows = _query_rows(
        analytics, start_date, end_date, SUMMARY_METRICS, max_results=1
    )
    summary = summary_rows[0] if summary_rows else {}

    daily, daily_error = _optional_report(
        analytics, start_date, end_date, DAILY_METRICS,
        dimensions="day", sort="day", max_results=max(days, 1),
    )
    videos, videos_error = _optional_report(
        analytics, start_date, end_date, VIDEO_METRICS,
        dimensions="video", sort="-views", max_results=10,
    )
    sources, sources_error = _optional_report(
        analytics, start_date, end_date, "views,estimatedMinutesWatched",
        dimensions="insightTrafficSourceType", sort="-views", max_results=10,
    )

    ids = [str(row.get("video") or "").strip() for row in videos]
    ids = [video_id for video_id in ids if video_id]
    details_by_id: dict[str, dict[str, Any]] = {}
    if ids:
        try:
            result = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(ids[:50]),
                maxResults=min(len(ids), 50),
            ).execute(num_retries=2)
            details_by_id = {
                str(video.get("id")): video
                for video in (result.get("items") or [])
                if video.get("id")
            }
        except Exception as exc:
            videos_error = (videos_error + "; " if videos_error else "") + (
                f"Video metadata unavailable ({type(exc).__name__}: {exc})"
            )

    for video in videos:
        video_id = str(video.get("video") or "").strip()
        metadata = details_by_id.get(video_id) or {}
        video_snippet = metadata.get("snippet") or {}
        video_stats = metadata.get("statistics") or {}
        thumb_set = video_snippet.get("thumbnails") or {}
        thumb = (thumb_set.get("medium") or thumb_set.get("default") or {}).get("url")
        video.update({
            "video_id": video_id,
            "title": video_snippet.get("title") or video_id or "Video title unavailable",
            "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            "thumbnail_url": thumb or "",
            "lifetime_views": _safe_int(video_stats.get("viewCount")),
        })

    errors = {
        key: message
        for key, message in (
            ("daily trends", daily_error),
            ("top videos", videos_error),
            ("traffic sources", sources_error),
        )
        if message
    }
    return {
        "channel": {
            "id": item.get("id", ""),
            "title": snippet.get("title") or "Your YouTube channel",
            "custom_url": snippet.get("customUrl") or "",
            "thumbnail_url": channel_thumb or "",
            "lifetime_views": _safe_int(stats.get("viewCount")),
            "subscribers": (
                None if stats.get("hiddenSubscriberCount") else
                (_safe_int(stats["subscriberCount"]) if stats.get("subscriberCount") not in (None, "") else None)
            ),
            "video_count": _safe_int(stats.get("videoCount")),
            "hidden_subscriber_count": bool(stats.get("hiddenSubscriberCount", False)),
        },
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "summary": summary,
        "daily": daily,
        "top_videos": videos,
        "traffic_sources": sources,
        "optional_errors": errors,
    }


def format_duration(seconds: Any) -> str:
    """Format a duration in seconds as m:ss or h:mm:ss."""
    total = _safe_int(seconds)
    total = max(0, total)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


__all__ = [
    "ANALYTICS_SCOPE", "ANALYTICS_TOKEN_PATH", "REQUIRED_SCOPES",
    "YOUTUBE_READONLY_SCOPE", "build_analytics_clients", "fetch_channel_analytics",
    "format_duration", "load_analytics_credentials", "missing_required_scopes",
    "reporting_date_range", "rows_to_dicts",
]
