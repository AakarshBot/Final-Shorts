"""Cricket Topic Fetcher.

The fetcher builds a large current pool, removes duplicate articles and repeats,
and returns distinct cricket events. The downstream Topic contract is stable.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 8
LOOKBACK_HOURS = 72
TARGET = 20
MAX_QUERY_RESULTS = 100
MAX_GOOGLE_WORKERS = 12

CRICKET_QUERIES = {
    "cricket_india_asia": [
        'cricket India Pakistan "Sri Lanka" Bangladesh when:3d',
        '(BCCI OR PCB OR ICC OR "Sri Lanka Cricket" OR Bangladesh cricket) when:3d',
        'India cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR selection OR controversy) when:3d',
        'Pakistan cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR selection OR controversy) when:3d',
        '"Sri Lanka" cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR selection OR controversy) when:3d',
        'women cricket India Pakistan Sri Lanka WPL when:3d',
        'cricket (law OR rules OR coach OR appointed OR retained OR released OR signed OR transfer OR venue OR pitch OR technology OR innovation) when:3d',
        'cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR controversy OR upset OR statement) when:3d',
        '(franchise OR league OR tournament) cricket when:3d',
        'international cricket latest when:3d',
        'cricket (youngster OR debutant OR uncapped OR breakout OR emerging) when:3d',
        'cricket (reaction OR interview OR responds OR reveals OR confirms OR ban OR fine OR suspension) when:3d',
    ],
    "cricket_global": [
        'international cricket latest when:3d',
        'Australia cricket when:3d',
        'England cricket when:3d',
        'South Africa cricket when:3d',
        'New Zealand cricket when:3d',
        'West Indies cricket when:3d',
        'Pakistan cricket when:3d',
        '"Sri Lanka" cricket when:3d',
        'women international cricket when:3d',
        'cricket (law OR rules OR coach OR appointed OR retained OR released OR signed OR transfer OR venue OR pitch OR technology OR innovation) when:3d',
        'cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR controversy OR upset OR statement) when:3d',
        '(franchise OR league OR tournament) cricket when:3d',
    ],
}

MORE_QUERIES = {
    "cricket_india_asia": [
        'cricket (retention OR release OR appointment OR ownership OR sponsor OR venue OR pitch OR law OR technology) when:3d',
        'cricket (statement OR interview OR reaction OR row OR ban OR fine OR suspension) when:3d',
        'cricket (women OR domestic OR franchise OR associate) when:3d',
        '(Australia OR England OR South Africa OR New Zealand OR West Indies) cricket when:3d',
        '(WPL OR PSL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) cricket when:3d',
        'cricket (schedule OR calendar OR format OR rules OR policy) when:3d',
        'cricket (off-field OR dispute OR apology OR criticism OR backlash) when:3d',
        'cricket (youngster OR uncapped OR breakout OR emerging OR comeback) when:3d',
    ],
    "cricket_global": [
        'cricket (retention OR release OR appointment OR ownership OR sponsor OR venue OR pitch OR law OR technology) when:3d',
        'cricket (statement OR interview OR reaction OR row OR ban OR fine OR suspension) when:3d',
        'cricket (women OR domestic OR franchise OR associate) when:3d',
        '(Australia OR England OR South Africa OR New Zealand OR West Indies) cricket when:3d',
        '(WPL OR PSL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) cricket when:3d',
        'cricket (schedule OR calendar OR format OR rules OR policy) when:3d',
        'cricket (off-field OR dispute OR apology OR criticism OR backlash) when:3d',
        'cricket (youngster OR uncapped OR breakout OR emerging OR comeback) when:3d',
    ],
}

KEYWORD_QUERIES = [
    '"{keyword}" cricket when:3d',
    '"{keyword}" cricket (record OR milestone OR debut OR comeback OR injury OR appointment OR controversy) when:3d',
    '"{keyword}" cricket (reaction OR interview OR statement OR confirms OR reveals) when:3d',
    '"{keyword}" cricket (women OR franchise OR league OR board OR rules OR pitch) when:3d',
]

CRICKET_TERMS = {
    "cricket", "bcci", "pcb", "icc", "wpl", "ipl", "odi", "t20", "test",
    "wicket", "innings", "batting", "bowling", "mcc", "laws", "sa20", "psl",
    "bbl", "cpl", "ilt20", "mlc", "cricket south africa", "women's cricket",
    "womens cricket", "head coach", "cricketer",
}
CRICKET_COMPETITIONS = {
    "world cup", "champions trophy", "wpl", "ipl", "psl", "bbl", "cpl",
    "sa20", "ilt20", "mlc", "ashes", "test championship", "county championship",
}
NON_CRICKET_TERMS = {
    "football", "soccer", "tennis", "badminton", "squash", "athletics",
    "marathon", "swimming", "cycling", "boxing", "wrestling", "hockey",
    "kabaddi", "volleyball", "basketball", "chess", "motorsport", "motogp",
    "formula", "f1",
}
INDIA_ASIA_TERMS = {
    "india", "indian", "bcci", "pakistan", "pakistani", "pcb", "sri lanka",
    "sri lankan", "bangladesh", "bangladeshi", "wpl", "ipl", "psl",
    "mumbai indians", "rcb", "royal challengers", "virat kohli", "rohit sharma",
    "shubman gill", "jasprit bumrah", "hardik pandya", "ravindra jadeja",
    "rishabh pant", "kl rahul", "kuldeep yadav", "mohammed siraj", "arshdeep singh",
    "yashasvi jaiswal", "smriti mandhana", "babar azam", "shaheen afridi",
    "mohammad rizwan", "wanindu hasaranga", "kusal mendis", "pathum nissanka",
    "matheesha pathirana", "shreyas iyer", "axar patel",
}
EVENT_GROUPS = {
    "result": {"win", "wins", "won", "beat", "beaten", "defeat", "lost", "loss", "draw", "champion", "title", "medal", "upset"},
    "injury": {"injury", "injured", "scare", "pain", "blow", "hurt", "layoff", "ruled"},
    "selection": {"selection", "selected", "dropped", "recalled", "squad", "picked", "omitted", "included"},
    "debut": {"debut", "debuted"},
    "retirement": {"retirement", "retire", "retired", "farewell"},
    "comeback": {"comeback", "return", "returned", "returns"},
    "record": {"record", "records", "milestone", "historic", "fastest", "youngest", "highest", "first"},
    "appointment": {"appointed", "appointment", "named", "names", "coach", "manager", "reins"},
    "contract": {"contract", "signed", "signs", "sponsor", "deal", "ownership"},
    "discipline": {"banned", "ban", "fined", "fine", "suspended", "sanctioned"},
    "rules": {"law", "laws", "rule", "rules", "regulation", "change", "changes", "policy"},
    "franchise": {"franchise", "retention", "retained", "release", "released", "auction", "league"},
    "innovation": {"innovation", "technology", "technological", "exchangeable", "trial", "trialing", "pitch"},
    "controversy": {"controversy", "statement", "slams", "blasts", "criticises", "criticizes", "row", "backlash"},
}
TITLE_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "by",
    "with", "from", "ahead", "after", "before", "as", "is", "are", "was", "were",
    "has", "have", "had", "its", "their", "his", "her", "will", "this", "that",
    "these", "those", "more", "than", "against", "amid", "latest", "news",
    "update", "updates", "report", "reports", "says", "said", "today", "official",
    "story", "stories",
}
UTILITY_PATTERNS = (
    r"\bhow to watch\b", r"\bwhere to watch\b", r"\blive streaming\b",
    r"\blive stream\b", r"\blive telecast\b", r"\bplaying xi\b",
    r"\bpredicted xi\b", r"\bpredicted lineups?\b", r"\bpitch report\b",
    r"\bscorecard\b", r"\blive score\b", r"\bmatch updates?\b",
    r"\bfixtures?\b", r"\bschedule\b", r"\bstandings?\b",
    r"\bphoto gallery\b", r"\bquiz\b", r"\btop \d+ .*news\b",
)
PUBLISHER_PENALTIES = {"cricketwebs", "cricketnmore", "socialnews.xyz", "northdesk.in"}

@dataclass(frozen=True)
class Topic:
    title: str
    source: str
    published_at: datetime
    url: str
    description: str = ""
    score: float = 0.0

def _clean(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()

def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+(?:['-][a-z0-9]+)?", _clean(value).casefold())
        if len(token) > 2 and token not in TITLE_STOPWORDS
    }

def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(_clean(url))
    except ValueError:
        return _clean(url).casefold().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return _clean(url).casefold().rstrip("/")
    return parsed._replace(query="", fragment="").geturl().rstrip("/").casefold()

def _source_key(source: str) -> str:
    return _clean(source).casefold().removeprefix("www.").split("/")[0]

def _clean_title(title: str, source: str = "") -> str:
    title = _clean(title)
    source_key = _source_key(source)
    if source_key:
        for separator in (" | ", " - ", " – ", " — "):
            parts = title.split(separator)
            if len(parts) > 1 and _source_key(parts[-1]) == source_key:
                title = separator.join(parts[:-1])
                break
    return _clean(title)

def _utility(title: str) -> bool:
    return any(re.search(pattern, _clean(title).casefold()) for pattern in UTILITY_PATTERNS)

def _event_groups(title: str) -> set[str]:
    tokens = _tokens(title)
    return {group for group, terms in EVENT_GROUPS.items() if tokens & terms}

TEAM_ENTITIES = {
    "india", "pakistan", "sri lanka", "bangladesh", "australia", "england",
    "south africa", "new zealand", "west indies", "afghanistan", "ireland",
}


def _known_entities(text: str) -> set[str]:
    value = _clean(text).casefold()
    known = INDIA_ASIA_TERMS | CRICKET_COMPETITIONS | TEAM_ENTITIES
    return {entity for entity in known if len(entity) > 3 and entity in value}


def _named_phrases(title: str) -> set[str]:
    return {
        _clean(match)
        for match in re.findall(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+\b", title)
        if len(_clean(match).split()) >= 2
    }


def _same_event(a: Topic, b: Topic) -> bool:
    shared = _tokens(a.title) & _tokens(b.title)
    if len(shared) < 2:
        return False
    groups = _event_groups(a.title) & _event_groups(b.title)
    if not groups:
        return False
    entities = _known_entities(f"{a.title} {a.description}") & _known_entities(f"{b.title} {b.description}")
    specific_entities = entities - TEAM_ENTITIES
    if specific_entities:
        return True
    if _named_phrases(a.title) & _named_phrases(b.title):
        return True
    return len(entities) >= 2 and len(shared) >= 3

def _profile_relevant(title: str, description: str, profile: str | None, source: str) -> bool:
    if profile == "niche_sports":
        text = f"{title} {description}".casefold()
        return any(term in text for term in (
            "tennis", "badminton", "squash", "athletics", "swimming", "cycling",
            "golf", "boxing", "wrestling", "hockey", "kabaddi", "volleyball",
            "basketball", "chess", "motorsport", "motogp", "formula 1",
        )) and not any(term in text for term in CRICKET_TERMS)
    if profile not in {"cricket_india_asia", "cricket_global"}:
        return False
    text = f"{title} {description}".casefold()
    if any(term in _tokens(title) for term in NON_CRICKET_TERMS):
        return False
    strong = any(term in text for term in CRICKET_TERMS) or any(term in text for term in CRICKET_COMPETITIONS)
    if strong:
        return True
    return any(token in _source_key(source) for token in ("cric", "espn", "icc", "wisden", "bcci", "pcb", "cricket"))

def _parse_date(value) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    value = _clean(value)
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)

def _parse_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    rows = []
    for item in root.findall(".//item"):
        source_el = item.find("source")
        source = _clean(source_el.text if source_el is not None else "")
        title = _clean_title(item.findtext("title") or "", source)
        url = _clean(item.findtext("link") or "")
        if title and url:
            rows.append(Topic(title, source, _parse_date(item.findtext("pubDate") or ""), url, _clean(item.findtext("description") or "")))
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
        params={"query": query, "mode": "artlist", "format": "json", "maxrecords": MAX_QUERY_RESULTS, "timespan": "3d"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return [
        Topic(
            _clean_title(item.get("title", ""), item.get("domain", "")),
            _clean(item.get("domain", "")),
            _parse_date(item.get("seendate", "")),
            _clean(item.get("url", "")),
            _clean(item.get("snippet", "")),
        )
        for item in payload.get("articles", [])
        if isinstance(item, dict)
        and _clean(item.get("title", ""))
        and _clean(item.get("url", ""))
    ]

def _score(topic: Topic, profile: str) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)
    freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 6.0
    event_signal = min(2.4, len(_event_groups(topic.title)) * 0.6)
    meaningful = _tokens(topic.title) - CRICKET_TERMS - set().union(*EVENT_GROUPS.values())
    specificity = min(2.0, max(0, len(meaningful) - 1) * 0.4)
    local = 1.5 if profile == "cricket_india_asia" and any(
        term in f"{topic.title} {topic.description}".casefold() for term in INDIA_ASIA_TERMS
    ) else 0.0
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    return freshness + event_signal + specificity + local - source_penalty

def _prepare(
    rows: list[Topic],
    seen_urls: set[str],
    profile: str | None = None,
    lookback_hours: int | None = None,
) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours or LOOKBACK_HOURS)
    seen = {_canonical_url(url) for url in seen_urls}
    prepared = []
    seen_titles = set()
    seen_row_urls = set()
    for row in rows:
        title = _clean_title(row.title, row.source)
        url = _canonical_url(row.url)
        if not title or not url or url in seen or url in seen_row_urls:
            continue
        if row.published_at < cutoff or _utility(title):
            continue
        if not _profile_relevant(title, row.description, profile, row.source):
            continue
        title_key = " ".join(sorted(_tokens(title)))
        if not title_key or title_key in seen_titles:
            continue
        prepared.append(Topic(title, _clean(row.source), row.published_at, url, _clean(row.description), row.score))
        seen_titles.add(title_key)
        seen_row_urls.add(url)
    return prepared

def _select(
    rows: list[Topic],
    limit: int,
    seen_urls: set[str],
    existing: list[Topic] | None = None,
    profile: str | None = None,
) -> list[Topic]:
    if limit <= 0:
        return []
    profile = profile or "cricket_india_asia"
    blocked = list(existing or [])
    seen = {_canonical_url(url) for url in seen_urls}
    ranked = sorted(
        (Topic(r.title, r.source, r.published_at, r.url, r.description, _score(r, profile)) for r in rows),
        key=lambda r: r.score,
        reverse=True,
    )
    candidates = [
        row for row in ranked
        if _canonical_url(row.url) not in seen and not any(_same_event(row, old) for old in blocked)
    ]
    cluster_window = candidates[: max(250, limit * 12)]
    clusters = []
    for row in cluster_window:
        for cluster in clusters:
            if _same_event(row, cluster[0]):
                cluster.append(row)
                break
        else:
            clusters.append([row])

    chosen = []
    source_counts = {}
    for cluster in clusters:
        if len(chosen) >= limit:
            break
        ordered = sorted(cluster, key=lambda row: row.score, reverse=True)
        candidate = next(
            (
                row for row in ordered
                if _source_key(row.source) and source_counts.get(_source_key(row.source), 0) < 2
            ),
            ordered[0],
        )
        if any(_same_event(candidate, old) for old in blocked + chosen):
            continue
        chosen.append(candidate)
        source = _source_key(candidate.source)
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1

    if len(chosen) < limit:
        for row in candidates:
            if len(chosen) >= limit:
                break
            if row.url in {item.url for item in chosen}:
                continue
            if any(_same_event(row, old) for old in blocked + chosen):
                continue
            chosen.append(row)
    return chosen[:limit]

def _keyword_queries(keyword: str) -> list[str]:
    clean = _clean(keyword).replace('"', " ")
    if not clean:
        return []
    return [query.format(keyword=clean) for query in KEYWORD_QUERIES]

def _gdelt_query(profile: str, keyword: str | None = None) -> str:
    if keyword:
        return f'"{_clean(keyword)}" cricket'
    if profile == "cricket_global":
        return '(cricket India Pakistan "Sri Lanka" Bangladesh Australia England South Africa "New Zealand" "West Indies")'
    return '(cricket India Pakistan "Sri Lanka" Bangladesh WPL IPL BCCI ICC)'

def fetch_topics(
    profile: str = "cricket_india_asia",
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
    keyword: str | None = None,
) -> list[Topic]:
    if profile not in {"cricket_india_asia", "cricket_global", "niche_sports"}:
        raise ValueError(f"Unknown profile: {profile}")
    if limit <= 0:
        return []
    existing = list(exclude_topics or [])
    seen_urls = {_canonical_url(topic.url) for topic in existing}

    if keyword:
        queries = _keyword_queries(keyword)
    elif profile == "niche_sports":
        queries = [
            '(tennis OR badminton OR squash OR "table tennis") when:3d',
            '(F1 OR "Formula 1" OR MotoGP OR motorsport) when:3d',
            '(athletics OR swimming OR cycling OR golf) when:3d',
            '(boxing OR wrestling OR hockey OR kabaddi OR basketball OR chess) when:3d',
        ]
    else:
        queries = list(MORE_QUERIES[profile] if more else CRICKET_QUERIES[profile])

    rows = []
    with ThreadPoolExecutor(max_workers=min(MAX_GOOGLE_WORKERS, max(1, len(queries)))) as pool:
        futures = [pool.submit(_fetch_google, query) for query in queries]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError):
                continue

    prepared = _prepare(rows, seen_urls, profile=profile)
    chosen = _select(prepared, limit, seen_urls, existing=existing, profile=profile)

    if len(chosen) < limit and profile != "niche_sports":
        try:
            fallback_rows = _prepare(
                _fetch_gdelt(_gdelt_query(profile, keyword)),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                profile=profile,
            )
            chosen.extend(
                _select(
                    fallback_rows,
                    limit - len(chosen),
                    seen_urls | {_canonical_url(topic.url) for topic in chosen},
                    existing=existing + chosen,
                    profile=profile,
                )
            )
        except (requests.RequestException, ET.ParseError, ValueError):
            pass

    return chosen[:limit]
