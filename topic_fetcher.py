from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests


GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 12
LOOKBACK_HOURS = 72
TARGET = 20
MAX_QUERY_RESULTS = 100

QUERIES = {
    "cricket_india_asia": [
        'Indian cricket (reacts OR reveals OR confirms OR says OR denies OR admits OR injury OR selection OR record OR retirement OR comeback OR controversy) when:3d',
        '"Virat Kohli" cricket when:3d',
        '"Rohit Sharma" cricket when:3d',
        '"Shubman Gill" cricket when:3d',
        '"BCCI" cricket (decision OR announcement OR sponsor OR selection OR injury OR statement) when:3d',
        '(India OR Pakistan OR Sri Lanka OR Bangladesh OR Afghanistan) cricket (upset OR record OR debut OR comeback OR controversy OR statement) when:3d',
        'women cricket India (record OR selection OR statement OR upset OR comeback OR controversy) when:3d',
        '(Asian Games OR Asia) cricket (India OR Pakistan OR Nepal OR Afghanistan OR Japan OR Oman) when:3d',
        'India cricket (fans OR reaction OR statement OR interview OR milestone) when:3d',
    ],
    "cricket_global": [
        'international cricket (reacts OR reveals OR confirms OR says OR denies OR admits OR injury OR selection OR record OR retirement OR comeback OR controversy) when:3d',
        '"Australia" cricket (injury OR selection OR record OR retirement OR comeback OR statement OR upset) when:3d',
        '"England" cricket (injury OR selection OR record OR retirement OR comeback OR statement OR upset) when:3d',
        '"South Africa" cricket (injury OR selection OR record OR retirement OR comeback OR statement OR upset) when:3d',
        '"New Zealand" cricket (injury OR selection OR record OR retirement OR comeback OR statement OR upset) when:3d',
        '"West Indies" cricket (injury OR selection OR record OR retirement OR comeback OR statement OR upset) when:3d',
        'women cricket international (record OR selection OR statement OR upset OR comeback OR controversy) when:3d',
        'cricket (fans OR reaction OR interview OR statement OR milestone) international when:3d',
        'cricket (upset OR breakthrough OR debut OR comeback OR controversy) international when:3d',
    ],
    "niche_sports": [
        '(tennis OR badminton OR squash OR "table tennis") (reacts OR reveals OR injury OR upset OR record OR debut OR comeback OR statement) when:3d',
        '("Formula 1" OR F1 OR MotoGP OR motorsport) (crash OR pole OR upset OR record OR debut OR statement OR comeback) when:3d',
        '(athletics OR swimming OR cycling OR golf) (record OR medal OR upset OR debut OR breakthrough OR statement) when:3d',
        '(boxing OR wrestling OR hockey OR kabaddi) (upset OR medal OR title OR debut OR comeback OR statement OR controversy) when:3d',
        '(volleyball OR basketball OR chess) (upset OR title OR record OR debut OR breakthrough OR statement) when:3d',
        'tennis (fans OR reaction OR interview OR controversy OR milestone) when:3d',
        'badminton (fans OR reaction OR interview OR controversy OR milestone) when:3d',
        'motorsport (fans OR reaction OR interview OR controversy OR milestone) when:3d',
        'athletics (fans OR reaction OR interview OR controversy OR milestone) when:3d',
    ],
}

MORE_QUERIES = {
    "cricket_india_asia": [
        '(India OR Pakistan OR Sri Lanka OR Bangladesh OR Afghanistan OR Nepal) cricket (change OR dropped OR recalled OR ruled out OR signed OR fined OR banned OR suspended OR targeted) when:3d',
        'Indian cricket (captain OR coach OR player) (statement OR interview OR reaction OR criticism OR praise) when:3d',
        'India women cricket (captain OR player OR coach) (statement OR record OR selection OR reaction) when:3d',
        '"Asian Games" cricket (upset OR record OR debut OR controversy OR reaction) when:3d',
        'India cricket (sponsor OR board OR contract OR venue OR rule OR announcement) when:3d',
        '(Virat Kohli OR Rohit Sharma OR Shubman Gill OR Jasprit Bumrah OR Hardik Pandya) cricket (statement OR reaction OR injury OR record) when:3d',
        '(Nepal OR Japan OR Oman OR Malaysia OR Hong Kong) cricket (upset OR record OR reaction OR statement) when:3d',
        'women cricket India (fans OR reaction OR interview OR controversy) when:3d',
        'India cricket (off-field OR controversy OR viral OR fans) when:3d',
    ],
    "cricket_global": [
        'international cricket (change OR dropped OR recalled OR ruled out OR signed OR fined OR banned OR suspended) when:3d',
        'Australia cricket (captain OR coach OR player) (statement OR interview OR reaction OR criticism OR praise) when:3d',
        'England cricket (captain OR coach OR player) (statement OR interview OR reaction OR criticism OR praise) when:3d',
        'South Africa cricket (captain OR coach OR player) (statement OR interview OR reaction OR criticism OR praise) when:3d',
        'West Indies cricket (captain OR coach OR player) (statement OR interview OR reaction OR criticism OR praise) when:3d',
        'women cricket global (fans OR reaction OR interview OR controversy OR record) when:3d',
        'cricket (off-field OR controversy OR viral OR fans OR reaction) when:3d',
        'cricket (contract OR sponsor OR venue OR rule OR board) international when:3d',
        'cricket (breakthrough OR debut OR comeback OR upset) international when:3d',
    ],
    "niche_sports": [
        '(tennis OR badminton OR squash OR "table tennis") (change OR coach OR injury OR suspended OR fined OR contract OR statement) when:3d',
        '(F1 OR "Formula 1" OR MotoGP OR motorsport) (change OR contract OR crash OR penalty OR statement OR reaction) when:3d',
        '(athletics OR swimming OR cycling OR golf) (coach OR injury OR contract OR statement OR reaction OR controversy) when:3d',
        '(boxing OR wrestling OR hockey OR kabaddi) (coach OR injury OR contract OR statement OR reaction OR controversy) when:3d',
        '(volleyball OR basketball OR chess) (coach OR injury OR contract OR statement OR reaction OR controversy) when:3d',
        'tennis (viral OR fans OR controversy OR reaction OR interview) when:3d',
        'badminton (viral OR fans OR controversy OR reaction OR interview) when:3d',
        'motorsport (viral OR fans OR controversy OR reaction OR interview) when:3d',
        'athletics (viral OR fans OR controversy OR reaction OR interview) when:3d',
    ],
}

SPORT_WORDS = {
    "cricket", "bcci", "ipl", "wicket", "innings", "batting", "bowling", "odi", "t20", "test",
    "tennis", "badminton", "squash", "table", "formula", "f1", "motogp", "motorsport",
    "athletics", "swimming", "golf", "cycling", "boxing", "hockey", "kabaddi", "volleyball",
    "basketball", "wrestling", "chess", "race", "grand", "prix", "olympics", "para",
}

CRICKET_TERMS = {"cricket", "bcci", "wicket", "innings", "batting", "bowling", "odi", "t20", "test"}
NON_CRICKET_TERMS = {
    "football", "soccer", "tennis", "badminton", "squash", "athletics", "marathon", "swimming",
    "cycling", "boxing", "wrestling", "hockey", "kabaddi", "volleyball", "basketball", "chess",
    "motorsport", "motogp", "formula", "f1",
}
UTILITY_PATTERNS = (
    r"how to watch",
    r"where to watch",
    r"live streaming",
    r"live stream",
    r"live telecast",
    r"free telecast",
    r"tv channels?",
    r"streaming details?",
    r"playing xi",
    r"predicted xi",
    r"predicted lineups?",
    r"lineups? and pitch report",
    r"pitch report",
    r"scorecard",
    r"full scorecard",
    r"live score",
    r"match updates?",
    r"as it happened",
    r"as-it-happened",
    r"fixtures?",
    r"schedule",
    r"standings?",
    r"points table",
    r"medal tally",
    r"when .* plays",
)

GENERIC_PATTERNS = (
    r"^s*sports newss*$",
    r"^s*latest sports newss*$",
    r"^s*today'?s top d+",
    r"top d+ .*news",
    r"photo gallery",
    r"^s*gallery",
    r"quiz",
    r"news roundup",
)

EVENT_GROUPS = {
    "injury": {"injury", "injured", "scare", "pain", "blow", "hurt", "ruled", "layoff"},
    "selection": {"selection", "selected", "dropped", "recalled", "squad", "picked", "omitted"},
    "retirement": {"retirement", "retire", "retired", "farewell", "farewells", "last", "goodbye"},
    "debut": {"debut", "debuted"},
    "comeback": {"comeback", "return", "returns", "returned", "recall", "recalled"},
    "record": {"record", "records", "milestone", "historic", "history"},
    "result": {"win", "wins", "won", "champion", "championship", "upset", "title", "medal", "podium"},
    "controversy": {"controversy", "controversial", "statement", "criticises", "criticizes", "slams", "blasts"},
    "contract": {"contract", "signed", "signs", "sponsor", "sponsorship", "deal"},
    "discipline": {"banned", "ban", "fined", "fine", "suspended", "sanctioned"},
}
EVENT_CONTEXT = {"odi", "t20", "test", "series", "tour", "season", "world", "cup", "final", "match", "championship"}
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "by", "with", "from",
    "ahead", "after", "before", "as", "is", "are", "was", "were", "has", "have", "had", "vs",
    "v", "into", "over", "says", "said", "will", "its", "their", "his", "her", "how", "what",
    "which", "this", "that", "these", "those", "also", "more", "than", "after", "against",
}
AUDIENCE_PULL_TERMS = {
    "reacts", "reacted", "responds", "responded", "slams", "blasts", "criticises", "criticizes",
    "praises", "reveals", "admits", "confirms", "snubs", "snubbed", "dropped", "ruled", "withdraws",
    "withdrawn", "suspended", "banned", "fined", "shocking", "shock", "surprise", "surprising",
    "historic", "first", "only", "never", "breakthrough", "comeback", "retirement", "debut",
    "controversy", "clash", "upset", "record", "milestone", "injury", "targeted", "viral",
}
PUBLISHER_PENALTIES = {"cricketwebs", "cricketnmore", "socialnews.xyz", "northdesk.in"}
LOW_SIGNAL_PATTERNS = (
    r"\bcalled on\b",
    r"\barrives? in\b",
    r"\bset to face\b",
    r"\broad map\b",
    r"\broadmap\b",
)


@dataclass(frozen=True)
class Topic:
    title: str
    source: str
    published_at: datetime
    url: str
    description: str = ""
    score: float = 0.0


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:['-][a-z0-9]+)?", _clean(value).casefold())
    return {word for word in words if word not in STOPWORDS and len(word) > 2}


def _parse_date(value: str) -> datetime:
    value = _clean(value)
    formats = ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)
    return dt.astimezone(timezone.utc)


def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(_clean(url))
    except ValueError:
        return _clean(url).casefold().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return _clean(url).casefold().rstrip("/")
    return parsed._replace(query="", fragment="").geturl().rstrip("/").casefold()


def _source_key(source: str) -> str:
    source = _clean(source).casefold().replace("www.", "")
    return source.split("/")[0].strip()


def _clean_title(title: str, source: str = "") -> str:
    title = _clean(title)
    source_key = _source_key(source)
    if source_key:
        for separator in (" | ", " - ", " – ", " — "):
            parts = title.split(separator)
            if len(parts) > 1 and _source_key(parts[-1]) == source_key:
                title = separator.join(parts[:-1]).strip()
                break
    title = re.sub(r"\s*\|\s*(?:cricket|sports?|news)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+-\s+(?:cricket|sports?|news)\s*$", "", title, flags=re.IGNORECASE)
    return _clean(title)


def _profile_relevant(title: str, description: str, profile: str | None) -> bool:
    title_tokens = _tokens(title)
    description_tokens = _tokens(description[:500])
    if profile in {"cricket_india_asia", "cricket_global"}:
        if title_tokens & NON_CRICKET_TERMS:
            return False
        return bool(title_tokens & CRICKET_TERMS) or (
            bool(description_tokens & CRICKET_TERMS)
            and bool(_event_groups(title))
        )
    return bool(title_tokens & (SPORT_WORDS - CRICKET_TERMS)) and not (
        "cricket" in title_tokens
        and not title_tokens & (SPORT_WORDS - CRICKET_TERMS)
    )


def _utility(title: str) -> bool:
    text = _clean(title).casefold()
    return any(re.search(pattern, text) for pattern in UTILITY_PATTERNS) or any(
        re.search(pattern, text) for pattern in GENERIC_PATTERNS
    )


def _event_groups(title: str) -> set[str]:
    words = _tokens(title)
    return {group for group, terms in EVENT_GROUPS.items() if words & terms}


def _same_event(a: Topic, b: Topic) -> bool:
    ta, tb = _tokens(a.title), _tokens(b.title)
    shared = (ta & tb) - SPORT_WORDS - set().union(*EVENT_GROUPS.values())
    if len(shared) >= 2 and _event_groups(a.title) & _event_groups(b.title):
        return True

    shared_context = (ta & tb) & EVENT_CONTEXT
    shared_entities = (ta & tb) - SPORT_WORDS - set().union(*EVENT_GROUPS.values()) - EVENT_CONTEXT
    if len(shared_entities) >= 3 and shared_context:
        similarity = SequenceMatcher(None, _clean(a.title).casefold(), _clean(b.title).casefold()).ratio()
        if similarity >= 0.42:
            return True

    if len(shared_entities) >= 2 and len(shared_context) >= 2:
        return True
    return False


def _score(topic: Topic) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)
    freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 5
    event_bonus = min(2.8, len(_event_groups(topic.title)) * 0.8)
    pull_bonus = min(4.0, len(_tokens(topic.title) & AUDIENCE_PULL_TERMS) * 1.0)
    distinctive = _tokens(topic.title) - SPORT_WORDS - set().union(*EVENT_GROUPS.values()) - EVENT_CONTEXT
    specificity = min(2.0, max(0, len(distinctive) - 2) * 0.35)
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    low_signal_penalty = 1.5 if any(re.search(pattern, topic.title, re.IGNORECASE) for pattern in LOW_SIGNAL_PATTERNS) else 0.0
    generic_penalty = 3.0 if _utility(topic.title) else 0.0
    return freshness + event_bonus + pull_bonus + specificity - source_penalty - low_signal_penalty - generic_penalty


def _parse_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    rows: list[Topic] = []
    for item in root.findall(".//item"):
        source_el = item.find("source")
        source = _clean(source_el.text if source_el is not None else "")
        title = _clean_title(item.findtext("title") or "", source)
        url = _clean(item.findtext("link"))
        published = _parse_date(item.findtext("pubDate") or "")
        description = _clean(item.findtext("description"))
        if title and url:
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
        params={
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": MAX_QUERY_RESULTS,
            "timespan": "3d",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    rows = []
    for item in payload.get("articles", []) if isinstance(payload, dict) else []:
        title = _clean_title(item.get("title", ""), item.get("domain", ""))
        url = _clean(item.get("url", ""))
        if not title or not url:
            continue
        rows.append(
            Topic(
                title,
                _clean(item.get("domain", "")),
                _parse_date(item.get("seendate", "")),
                url,
                _clean(item.get("snippet", "")),
            )
        )
    return rows


def _prepare(
    rows: list[Topic],
    seen_urls: set[str],
    profile: str | None = None,
) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    out: list[Topic] = []
    seen_urls: set[str] = {_canonical_url(url) for url in seen_urls}
    seen_titles: set[str] = set()

    for topic in rows:
        title = _clean_title(topic.title, topic.source)
        url = _canonical_url(topic.url)
        if not title or not url or url in seen_urls or topic.published_at < cutoff:
            continue
        if _utility(title):
            continue
        if not _profile_relevant(title, topic.description, profile):
            continue

        title_key = " ".join(sorted(_tokens(title)))
        if title_key in seen_titles:
            continue
        if any(
            SequenceMatcher(None, title.casefold(), other.title.casefold()).ratio() >= 0.94
            for other in out
        ):
            continue

        cleaned = Topic(
            title,
            _clean(topic.source),
            topic.published_at,
            url,
            _clean(topic.description),
            topic.score,
        )
        seen_titles.add(title_key)
        out.append(cleaned)

    return out


def _select(
    rows: list[Topic],
    limit: int,
    seen_urls: set[str],
    existing: list[Topic] | None = None,
) -> list[Topic]:
    ranked = sorted(
        (
            Topic(
                r.title,
                r.source,
                r.published_at,
                r.url,
                r.description,
                _score(r),
            )
            for r in rows
        ),
        key=lambda topic: topic.score,
        reverse=True,
    )

    blocked = list(existing or [])
    chosen: list[Topic] = []
    source_counts: dict[str, int] = {}
    deferred: list[Topic] = []
    seen_canonical = {_canonical_url(url) for url in seen_urls}

    for topic in ranked:
        if _canonical_url(topic.url) in seen_canonical:
            continue
        if any(_same_event(topic, other) for other in blocked + chosen):
            continue
        source = _source_key(topic.source)
        if source and source_counts.get(source, 0) >= 2 and len(chosen) < max(1, limit // 2):
            deferred.append(topic)
            continue
        chosen.append(topic)
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
        if len(chosen) >= limit:
            break

    if len(chosen) < limit:
        for topic in deferred:
            if any(_same_event(topic, other) for other in blocked + chosen):
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
    if limit <= 0:
        return []

    queries = (MORE_QUERIES if more else QUERIES)[profile]
    existing = list(exclude_topics or [])
    seen_urls = {_canonical_url(topic.url) for topic in existing}

    rows: list[Topic] = []
    with ThreadPoolExecutor(max_workers=min(8, len(queries))) as pool:
        futures = [pool.submit(_fetch_google, query) for query in queries]
        for future in futures:
            try:
                rows.extend(future.result())
            except (requests.RequestException, ValueError):
                continue

    prepared = _prepare(rows, seen_urls, profile=profile)
    chosen = _select(prepared, limit, seen_urls, existing)

    if len(chosen) < limit or len(prepared) < limit * 3:
        gdelt_query = {
            "cricket_india_asia": "(cricket India Pakistan Sri Lanka Bangladesh Afghanistan Nepal Asia)",
            "cricket_global": "(cricket Australia England South Africa New Zealand West Indies international)",
            "niche_sports": "(tennis badminton F1 MotoGP athletics swimming golf boxing hockey kabaddi basketball chess)",
        }[profile]
        try:
            gdelt_rows = _prepare(
                _fetch_gdelt(gdelt_query),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                profile=profile,
            )
            chosen.extend(
                _select(
                    gdelt_rows,
                    limit - len(chosen),
                    seen_urls | {_canonical_url(topic.url) for topic in chosen},
                    existing + chosen,
                )
            )
        except (requests.RequestException, ValueError):
            pass

    return chosen[:limit]
