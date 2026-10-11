"""Long-form cricket story discovery for the Test workspace.

This is deliberately separate from the approved Shorts Topic Fetcher.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import xml.etree.ElementTree as ET

import requests


GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
TIMEOUT = 8
LOOKBACK_DAYS = 14
TARGET = 20
MAX_WORKERS = 8
HEADERS = {"User-Agent": "Final-Shorts-Longform/1.0"}

QUERIES = (
    'cricket (selection OR dropped OR recalled OR captaincy OR squad) when:14d',
    'cricket (controversy OR dispute OR backlash OR allegation OR suspension OR investigation) when:14d',
    'cricket (comeback OR retirement OR farewell OR career OR legacy OR injury) when:14d',
    'cricket (decision OR rule OR governance OR BCCI OR PCB OR ICC OR finances) when:14d',
    'cricket (rivalry OR feud OR debate OR criticism OR reaction) when:14d',
    'cricket (record OR milestone OR breakthrough OR youngest OR historic) when:14d',
    'cricket (IPL OR WPL OR PSL OR franchise OR auction OR ownership OR signing) when:14d',
    'cricket (women OR domestic OR associate OR emerging OR U19) when:14d',
    'cricket (coach OR captain OR strategy OR tactics OR role OR team balance) when:14d',
    'cricket (series OR tournament OR World Cup OR Ashes) (decision OR impact OR future OR controversy) when:14d',
)

MORE_QUERIES = (
    'cricket (selection row OR captaincy debate OR dropped player OR squad decision) when:14d',
    'cricket (career turning point OR comeback story OR retirement decision OR injury return) when:14d',
    'cricket (board dispute OR rule change OR governance OR finances OR franchise ownership) when:14d',
    'cricket (rivalry history OR tactical decision OR team strategy OR dressing room) when:14d',
    'cricket (record chase OR historic defeat OR unexpected result OR tournament consequence) when:14d',
    'cricket (women cricket OR domestic cricket OR associate nation OR young player) when:14d',
    'cricket (coach change OR captain removed OR contract OR transfer OR auction) when:14d',
    'cricket (investigation OR allegation OR disciplinary hearing OR appeal OR ban) when:14d',
    'cricket (player statement OR board statement OR reaction OR criticism OR fallout) when:14d',
    'cricket analysis (why OR how OR consequence OR future OR decision) when:14d',
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "has", "have", "he", "her", "his", "in", "into", "is", "it", "its", "of",
    "on", "or", "said", "says", "she", "that", "the", "their", "this", "to",
    "was", "were", "will", "with", "after", "before", "over", "under", "new",
    "news", "latest", "today", "report", "reports", "update", "updates",
    "according", "reveals", "revealed", "confirms", "confirmed", "claims",
}

UTILITY_TERMS = (
    "live score", "live scores", "scorecard", "points table", "standings",
    "full schedule", "match schedule", "fixtures list", "today's fixtures",
    "where to watch", "live streaming", "ticket booking", "fantasy tips",
    "dream11 prediction", "match prediction", "betting odds", "weather report",
)

DEPTH_SIGNALS = {
    "selection": ("selection", "selected", "dropped", "recalled", "squad", "captaincy", "captain"),
    "dispute": ("controversy", "dispute", "backlash", "allegation", "investigation", "row", "ban", "suspension", "appeal"),
    "career": ("comeback", "retirement", "farewell", "career", "legacy", "injury", "return", "comeback"),
    "decision": ("decision", "rule", "governance", "board", "policy", "contract", "appointed", "resigned"),
    "rivalry": ("rivalry", "feud", "debate", "criticism", "reaction", "fallout"),
    "milestone": ("record", "milestone", "breakthrough", "youngest", "historic", "first-ever"),
    "business": ("franchise", "auction", "ownership", "finances", "signing", "deal", "contract"),
    "competition": ("world cup", "champions trophy", "ashes", "series", "tournament", "final"),
    "performance": ("tactics", "strategy", "team balance", "coach", "role", "form"),
}

CRICKET_TERMS = (
    "cricket", "cricketer", "cricketers", "batter", "bowler", "wicket",
    "innings", "bcci", "pcb", "icc", "ipl", "wpl", "psl", "ashes", "odi",
    "t20", "test match", "test cricket", "ranji", "bbl", "sa20", "cpl",
    "virat kohli", "rohit sharma", "jasprit bumrah", "ms dhoni", "rishabh pant",
    "shubman gill", "hardik pandya", "ravindra jadeja", "babar azam",
    "shaheen afridi", "pat cummins", "steve smith", "joe root", "ben stokes",
    "james anderson", "kane williamson", "travis head", "smriti mandhana",
    "harmana", "suryakumar yadav", "yashasvi jaiswal",
)

TRUSTED_NEWS_TERMS = (
    "reuters", "associated press", "bbc", "espncricinfo", "cricbuzz",
    "the guardian", "sportstar", "the hindu", "indian express", "icc",
)


def _clean(value: object, limit: int = 4000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _parse_date(value: object) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(str(value or "").strip())
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_url(value: object) -> str:
    try:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        query = [
            (key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
        ]
        return urlunparse((
            parsed.scheme.casefold(),
            parsed.netloc.casefold().removeprefix("www."),
            parsed.path.rstrip("/"),
            "",
            urlencode(sorted(query)),
            "",
        ))
    except ValueError:
        return ""


def _tokens(value: object) -> set[str]:
    return {
        token.casefold() for token in re.findall(r"[a-zA-Z0-9]+", _clean(value, 1000))
        if len(token) > 2 and token.casefold() not in STOPWORDS
    }


def _action_family(title: str) -> str:
    lower = title.casefold()
    families = (
        ("selection", ("selected", "selection", "dropped", "recalled", "squad", "captaincy", "captain")),
        ("dispute", ("controversy", "dispute", "backlash", "allegation", "investigation", "suspension", "banned", "ban", "row", "appeal")),
        ("career", ("retirement", "retire", "farewell", "comeback", "returns", "returned", "injury", "injured")),
        ("governance", ("rule change", "governance", "board decision", "appointed", "resigned", "contract")),
        ("business", ("auction", "ownership", "franchise", "finances", "signing", "deal")),
        ("record", ("record", "milestone", "youngest", "fastest", "first-ever")),
        ("result", ("defeated", "defeat", "beat", "beats", "won", "wins", "victory", "final result")),
    )
    for family, terms in families:
        if any(term in lower for term in terms):
            return family
    return ""


def _same_event(first: dict, second: dict) -> bool:
    first_url = _canonical_url(first.get("url"))
    second_url = _canonical_url(second.get("url"))
    if first_url and first_url == second_url:
        return True

    a = _tokens(first.get("title"))
    b = _tokens(second.get("title"))
    if not a or not b:
        return False
    action_a = _action_family(str(first.get("title") or ""))
    action_b = _action_family(str(second.get("title") or ""))
    if action_a and action_b and action_a != action_b:
        return False

    common = len(a & b)
    smaller = min(len(a), len(b))
    union = len(a | b)
    return smaller >= 4 and common / smaller >= 0.78 and common / union >= 0.52


def _is_cricket_story(title: str, description: str) -> bool:
    text = f"{title} {description}".casefold()
    return any(term in text for term in CRICKET_TERMS)


def _is_utility(title: str, url: str) -> bool:
    lower_title = title.casefold()
    lower_url = url.casefold()
    if any(term in lower_title for term in UTILITY_TERMS):
        return True
    return any(path in lower_url for path in ("/scorecard", "/points-table", "/standings", "/fixtures", "/schedule/"))


def _depth_labels(title: str, description: str) -> list[str]:
    text = f"{title} {description}".casefold()
    return [
        label for label, terms in DEPTH_SIGNALS.items()
        if any(term in text for term in terms)
    ]


def _score(story: dict, now: datetime) -> float:
    published = _parse_date(story.get("published_at"))
    age_days = max(0.0, (now - published).total_seconds() / 86400) if published else LOOKBACK_DAYS
    freshness = max(0.0, 10.0 - age_days * 0.65)
    depth = min(12.0, len(story["depth_signals"]) * 2.5)
    description = min(3.0, len(story.get("summary", "")) / 240)
    publisher = str(story.get("publisher") or "").casefold()
    source_quality = 2.0 if any(term in publisher for term in TRUSTED_NEWS_TERMS) else 0.0
    specificity = min(2.0, len(_tokens(story.get("title"))) / 6)
    return round(freshness + depth + description + source_quality + specificity, 2)


def _parse_feed(xml_text: str, query: str, now: datetime) -> list[dict]:
    root = ET.fromstring(xml_text)
    rows = []
    for item in root.findall(".//item"):
        source_node = item.find("source")
        publisher = _clean(source_node.text if source_node is not None else "", 160)
        title = _clean(item.findtext("title") or "", 500)
        if publisher and title.casefold().endswith(f" - {publisher}".casefold()):
            title = title[:-(len(publisher) + 3)].strip()
        url = _clean(item.findtext("link") or "", 3000)
        summary = _clean(item.findtext("description") or "", 1200)
        published = _parse_date(item.findtext("pubDate") or "")
        if not title or not url or not published:
            continue
        if published > now + timedelta(hours=12) or published < now - timedelta(days=LOOKBACK_DAYS):
            continue
        if not _is_cricket_story(title, summary) or _is_utility(title, url):
            continue

        row = {
            "title": title,
            "url": url,
            "publisher": publisher or urlparse(url).netloc.removeprefix("www."),
            "published_at": published.isoformat(),
            "summary": summary,
            "desk": "Cricket",
            "profile": "Long-form",
            "query": query,
            "depth_signals": _depth_labels(title, summary),
        }
        row["ranking_score"] = _score(row, now)
        rows.append(row)
    return rows


def _fetch_query(query: str, now: datetime) -> list[dict]:
    response = requests.get(
        GOOGLE_NEWS_URL,
        params={"q": query, "hl": "en"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return _parse_feed(response.text, query, now)


def _query_plan(more: bool, keyword: str) -> list[str]:
    queries = list(MORE_QUERIES if more else QUERIES)
    clean_keyword = _clean(keyword, 120)
    if clean_keyword:
        queries.extend((
            f'"{clean_keyword}" cricket when:14d',
            f'"{clean_keyword}" cricket (decision OR controversy OR selection OR career OR impact) when:14d',
        ))
    return queries


def fetch_longform_topics(
    limit: int = TARGET,
    already_seen: list[dict] | None = None,
    more: bool = False,
    keyword: str = "",
) -> list[dict]:
    """Return a ranked, deduplicated pool of current cricket stories with depth signals."""
    limit = max(1, min(40, int(limit)))
    now = datetime.now(timezone.utc)
    queries = _query_plan(more, keyword)
    fetched: list[dict] = []
    failures = 0

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(queries))) as executor:
        futures = {executor.submit(_fetch_query, query, now): query for query in queries}
        for future in as_completed(futures):
            try:
                fetched.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError, OSError):
                failures += 1

    if failures == len(queries):
        raise RuntimeError("Google News could not be reached for Long-form topic discovery. Try again.")

    # Cluster source variants of the same event, retaining all distinct reports as evidence leads.
    fetched.sort(key=lambda item: (item["ranking_score"], item["published_at"]), reverse=True)
    grouped: list[dict] = []
    for row in fetched:
        if any(_same_event(row, old) for old in (already_seen or [])):
            continue
        match = next((group for group in grouped if _same_event(row, group)), None)
        report_url = _canonical_url(row["url"])
        if match is None:
            row["reports"] = [{
                "title": row["title"],
                "url": row["url"],
                "publisher": row["publisher"],
                "published_at": row["published_at"],
            }]
            row["publishers"] = [row["publisher"]]
            grouped.append(row)
        elif not any(_canonical_url(report.get("url")) == report_url for report in match["reports"]):
            match["reports"].append({
                "title": row["title"],
                "url": row["url"],
                "publisher": row["publisher"],
                "published_at": row["published_at"],
            })
            if row["publisher"] and row["publisher"] not in match["publishers"]:
                match["publishers"].append(row["publisher"])
            match["ranking_score"] = round(max(match["ranking_score"], row["ranking_score"]) + min(4.0, (len(match["reports"]) - 1) * 1.3), 2)

    seen_rows = list(already_seen or [])
    results = []
    grouped.sort(key=lambda item: (item["ranking_score"], item["published_at"]), reverse=True)
    for story in grouped:
        if any(_same_event(story, old) for old in seen_rows) or any(_same_event(story, old) for old in results):
            continue
        normalised_title = " ".join(sorted(_tokens(story["title"])))
        story["story_id"] = hashlib.sha1(_canonical_url(story["url"]).encode("utf-8") or normalised_title.encode("utf-8")).hexdigest()[:16]
        story["event_id"] = hashlib.sha1(normalised_title.encode("utf-8")).hexdigest()[:16]
        story["report_count"] = len(story["reports"])
        if story["depth_signals"]:
            story["ranking_reason"] = "Recent cricket coverage with " + ", ".join(story["depth_signals"][:3]) + " potential."
        else:
            story["ranking_reason"] = "Recent cricket development; editorial depth needs confirmation during research."
        if story["report_count"] > 1:
            story["ranking_reason"] += f" Found {story['report_count']} distinct report URLs."
        results.append(story)
        seen_rows.append(story)
        if len(results) >= limit:
            break
    return results


__all__ = ["fetch_longform_topics"]
