from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 12
LOOKBACK_HOURS = 72
TARGET = 20

QUERIES = {
    "cricket_india_asia": [
        'cricket (India OR BCCI OR Pakistan OR Sri Lanka OR Bangladesh OR Afghanistan OR "women cricket") (injury OR selection OR win OR record OR retirement OR comeback OR breakthrough OR upset OR controversy) when:3d',
        'India cricket OR BCCI OR "women cricket" India when:3d',
    ],
    "cricket_global": [
        'cricket (Australia OR England OR "South Africa" OR "New Zealand" OR "West Indies") (injury OR selection OR win OR record OR retirement OR comeback OR breakthrough OR upset OR controversy) when:3d',
        'international cricket OR "women cricket" (record OR upset OR breakthrough OR controversy) when:3d',
    ],
    "niche_sports": [
        '(tennis OR badminton OR squash OR "table tennis" OR "Formula 1" OR F1 OR MotoGP OR motorsport OR athletics OR swimming OR golf OR cycling OR boxing OR hockey OR kabaddi OR volleyball OR basketball OR wrestling OR chess) (win OR upset OR record OR final OR champion OR medal OR pole OR breakthrough) when:3d',
        '"niche sports" OR badminton OR tennis OR F1 OR MotoGP OR athletics OR hockey OR kabaddi when:3d',
    ],
}

MORE_QUERIES = {
    "cricket_india_asia": [
        'Indian cricket (milestone OR debut OR captain OR statement OR clash OR comeback) when:3d',
        'cricket Asia (milestone OR upset OR statement OR debut OR injury) when:3d',
    ],
    "cricket_global": [
        'international cricket (milestone OR debut OR captain OR clash OR comeback) when:3d',
        'women cricket global (milestone OR debut OR upset OR statement) when:3d',
    ],
    "niche_sports": [
        '(tennis OR badminton OR F1 OR MotoGP OR athletics OR boxing OR wrestling OR hockey OR chess) (milestone OR debut OR upset OR comeback OR statement) when:3d',
        '(golf OR swimming OR cycling OR squash OR volleyball OR kabaddi OR basketball) (record OR upset OR champion OR debut) when:3d',
    ],
}

SPORT_WORDS = {
    "cricket", "bcci", "ipl", "wicket", "innings", "batting", "bowling", "odi", "t20", "test cricket",
    "tennis", "badminton", "squash", "table tennis", "formula 1", "f1", "motogp", "motorsport",
    "athletics", "swimming", "golf", "cycling", "boxing", "hockey", "kabaddi", "volleyball", "basketball",
    "wrestling", "chess", "race", "grand prix", "olympics", "para sport",
}
UTILITY_WORDS = {
    "schedule", "fixtures", "fixture", "standings", "table", "scorecard", "squad", "squads", "points table",
    "live score", "full scorecard", "result today", "match today", "medal tally", "rankings",
}
EVENT_GROUPS = {
    "injury": {"injury", "injured", "scare", "hit", "pain", "blow", "hurt"},
    "selection": {"selection", "selected", "squad", "dropped"},
    "retirement": {"retirement", "retire", "farewell"},
    "debut": {"debut", "first"},
    "comeback": {"comeback", "return"},
    "record": {"record", "milestone"},
    "result": {"wins", "win", "won", "champion", "championship", "final", "upset", "title", "medal", "podium"},
    "controversy": {"controversy", "statement", "clash"},
    "crash": {"crash"},
    "race": {"pole"},
    "wicket": {"dismissed"},
    "contract": {"contract"},
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "by", "with", "from", "ahead",
    "after", "before", "as", "is", "are", "was", "were", "has", "have", "had", "vs", "v", "into", "over",
}


@dataclass(frozen=True)
class Topic:
    title: str
    source: str
    published_at: datetime
    url: str
    description: str = ""
    score: float = 0.0


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:['-][a-z0-9]+)?", title.lower())
    return {word for word in words if word not in STOPWORDS and len(word) > 2}


def _parse_date(value: str) -> datetime:
    value = _clean(value)
    try:
        if re.fullmatch(r"\d{14}", value):
            return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)
    return dt.astimezone(timezone.utc)


def _sports_relevant(title: str, description: str = "") -> bool:
    text = f"{title} {description}".lower()
    return any(word in text for word in SPORT_WORDS)


def _utility(title: str) -> bool:
    text = title.lower()
    return any(term in text for term in UTILITY_WORDS)


def _event_groups(title: str) -> set[str]:
    words = _tokens(title)
    return {group for group, terms in EVENT_GROUPS.items() if words & terms}


def _same_event(a: Topic, b: Topic) -> bool:
    ta, tb = _tokens(a.title), _tokens(b.title)
    event_terms = set().union(*EVENT_GROUPS.values())
    generic = SPORT_WORDS | event_terms
    shared_entities = (ta & tb) - generic
    return len(shared_entities) >= 2 and bool(_event_groups(a.title) & _event_groups(b.title))


def _score(topic: Topic) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)
    freshness = max(0.0, 72.0 - age_hours) / 72.0 * 4
    event_bonus = min(3.0, len(_event_groups(topic.title)) * 0.7)
    source_bonus = 1.0 if topic.source else 0.0
    return freshness + event_bonus + source_bonus


def _parse_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    rows: list[Topic] = []
    for item in root.findall(".//item"):
        title = _clean(item.findtext("title"))
        url = _clean(item.findtext("link"))
        published = _parse_date(item.findtext("pubDate") or "")
        description = _clean(item.findtext("description"))
        source_el = item.find("source")
        source = _clean(source_el.text if source_el is not None else "")
        if not title or not url:
            continue
        rows.append(Topic(title, source, published, url, description))
    return rows


def _fetch_google(query: str) -> list[Topic]:
    response = requests.get(
        GOOGLE_NEWS_URL,
        params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return _parse_rss(response.text)


def _fetch_gdelt(query: str) -> list[Topic]:
    response = requests.get(
        GDELT_URL,
        params={"query": query, "mode": "artlist", "format": "json", "maxrecords": 75, "timespan": "3d"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    rows = []
    for item in response.json().get("articles", []):
        title = _clean(item.get("title", ""))
        url = _clean(item.get("url", ""))
        if not title or not url:
            continue
        published = _parse_date(item.get("seendate", ""))
        source = _clean(item.get("domain", ""))
        rows.append(Topic(title, source, published, url, _clean(item.get("snippet", ""))))
    return rows


def _prepare(rows: list[Topic], seen_urls: set[str]) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    out = []
    seen_titles: set[str] = set()
    for topic in rows:
        if topic.url in seen_urls or topic.published_at < cutoff:
            continue
        if _utility(topic.title) or not _sports_relevant(topic.title, topic.description):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", topic.title.lower()).strip()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(topic)
    return out


def _select(rows: list[Topic], limit: int, seen_urls: set[str], existing: list[Topic] | None = None) -> list[Topic]:
    ranked = sorted(
        (Topic(r.title, r.source, r.published_at, r.url, r.description, _score(r)) for r in rows),
        key=lambda x: x.score,
        reverse=True,
    )
    chosen: list[Topic] = []
    blocked = list(existing or [])
    for topic in ranked:
        if topic.url in seen_urls or any(_same_event(topic, other) for other in blocked + chosen):
            continue
        chosen.append(topic)
        if len(chosen) >= limit:
            break
    return chosen


def fetch_topics(
    profile: str = "cricket_india_asia",
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
) -> list[Topic]:
    if profile not in QUERIES:
        raise ValueError(f"Unknown profile: {profile}")

    queries = (MORE_QUERIES if more else QUERIES)[profile]
    existing = list(exclude_topics or [])
    seen_urls = {topic.url for topic in existing}

    rows = []
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = [pool.submit(_fetch_google, query) for query in queries]
        for future in futures:
            try:
                rows.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError):
                continue

    rows = _prepare(rows, seen_urls)
    chosen = _select(rows, limit, seen_urls, existing)

    if len(chosen) < limit:
        recovery_query = {
            "cricket_india_asia": "cricket India Asia",
            "cricket_global": "international cricket",
            "niche_sports": "tennis badminton motorsport athletics hockey chess",
        }[profile]
        try:
            recovery = _prepare(_fetch_gdelt(recovery_query), seen_urls | {t.url for t in chosen})
            chosen.extend(
                _select(
                    recovery,
                    limit - len(chosen),
                    seen_urls | {t.url for t in chosen},
                    existing + chosen,
                )
            )
        except requests.RequestException:
            pass

    return chosen[:limit]
