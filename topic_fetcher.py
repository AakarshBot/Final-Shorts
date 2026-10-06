"""Cricket Topic Fetcher.

The fetcher builds a large current pool, removes duplicate events, and fills the
requested number of story/entity groups without changing the Topic handoff.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from email.utils import parsedate_to_datetime
import html
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from rapidfuzz import fuzz

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 8
LOOKBACK_HOURS = 72
TARGET = 20
MAX_QUERY_RESULTS = 100
MAX_GOOGLE_WORKERS = 12
YOUTUBE_TRENDS_EXPLORE_URL = "https://trends.google.com/trends/api/explore"
YOUTUBE_TRENDS_RELATED_URL = "https://trends.google.com/trends/api/widgetdata/relatedsearches"
YOUTUBE_AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"
YOUTUBE_TREND_SEEDS = (
    ("cricket", "cricket_india_asia"),
    ("cricket news", "cricket_india_asia"),
    ("international cricket", "cricket_global"),
    ("football", "niche_sports"),
    ("football news", "niche_sports"),
    ("tennis", "niche_sports"),
    ("formula 1", "niche_sports"),
    ("badminton", "niche_sports"),
    ("basketball", "niche_sports"),
    ("sports news", "niche_sports"),
)
YOUTUBE_TREND_NOISE_TERMS = {
    "aaj", "tak", "live", "today", "news", "latest", "update", "updates",
    "match", "matches", "watch", "watching", "stream", "streaming", "telecast",
    "score", "scores", "result", "results", "highlights", "highlight", "online",
    "full", "video", "videos", "channel", "channels", "official", "time",
    "schedule", "schedules", "fixture", "fixtures", "prediction", "predicted",
    "lineup", "lineups",
}
YOUTUBE_TREND_GENERIC_TERMS = {
    "cricket", "football", "soccer", "tennis", "badminton", "basketball",
    "hockey", "formula", "f1", "motogp", "motorsport", "athletics", "boxing",
    "wrestling", "volleyball", "kabaddi", "squash", "golf", "chess", "swimming",
    "cycling", "t20", "odi", "test", "sport", "sports",
}
LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


CRICKET_QUERIES = {
    "cricket_india_asia": [
        '(India OR Pakistan OR "Sri Lanka" OR Bangladesh) cricket when:3d',
        'cricket (India OR Pakistan OR "Sri Lanka" OR Bangladesh) (record OR milestone OR first OR fastest OR historic) when:3d',
        'cricket (India OR Pakistan OR "Sri Lanka" OR Bangladesh) (injury OR comeback OR retirement OR debut OR dropped OR recalled) when:3d',
        'cricket (India OR Pakistan OR "Sri Lanka" OR Bangladesh) (rivalry OR debate OR feud OR clash OR showdown OR revenge) when:3d',
        'cricket (India OR Pakistan OR "Sri Lanka" OR Bangladesh) (controversy OR row OR ban OR fine OR suspension OR statement OR reaction) when:3d',
        'cricket (women OR WPL OR domestic OR Ranji OR U19 OR emerging OR uncapped OR associate) when:3d',
        'cricket (upset OR underdog OR breakout OR breakthrough OR teenager OR youngster) when:3d',
        'cricket (BCCI OR PCB OR ICC OR board) (decision OR rule OR law OR appointment OR venue OR pitch OR technology) when:3d',
        'cricket (IPL OR PSL OR WPL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) (retention OR release OR auction OR transfer OR signing OR controversy) when:3d',
        'cricket (career OR legacy OR comeback OR rise OR fall OR landmark) when:3d',
    ],
    "cricket_global": [
        'international cricket latest when:3d',
        'cricket (Australia OR England OR "South Africa" OR "New Zealand" OR "West Indies" OR Afghanistan OR Ireland) when:3d',
        'cricket (record OR milestone OR first OR fastest OR historic) when:3d',
        'cricket (injury OR comeback OR retirement OR debut OR dropped OR recalled) when:3d',
        'cricket (rivalry OR debate OR feud OR clash OR showdown OR revenge) when:3d',
        'cricket (controversy OR row OR ban OR fine OR suspension OR statement OR reaction) when:3d',
        'cricket (women OR domestic OR county OR U19 OR emerging OR uncapped OR associate) when:3d',
        'cricket (upset OR underdog OR breakout OR breakthrough OR teenager OR youngster) when:3d',
        'cricket (board OR ICC) (decision OR rule OR law OR appointment OR venue OR pitch OR technology) when:3d',
        'cricket (IPL OR PSL OR WPL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) (retention OR release OR auction OR transfer OR signing) when:3d',
    ],
}

MORE_QUERIES = {
    "cricket_india_asia": [
        'cricket (women OR Ranji OR Duleep OR Irani OR U19 OR domestic OR associate) when:3d',
        'cricket (Nepal OR Oman OR UAE OR Scotland OR Zimbabwe OR Namibia OR Uganda OR USA) when:3d',
        'cricket (rivalry OR feud OR debate OR clash OR showdown OR revenge OR rematch) when:3d',
        'cricket (record OR milestone OR first-ever OR fastest OR youngest OR oldest OR unbeaten) when:3d',
        'cricket (comeback OR breakthrough OR breakout OR uncapped OR debut OR teenager OR youngster) when:3d',
        'cricket (retirement OR legacy OR career OR farewell OR landmark) when:3d',
        'cricket (ban OR fine OR suspension OR row OR backlash OR statement OR apology) when:3d',
        'cricket (law OR rule OR technology OR pitch OR venue OR board decision) when:3d',
    ],
    "cricket_global": [
        'cricket (women OR domestic OR county OR U19 OR emerging OR associate) when:3d',
        'cricket (Nepal OR Oman OR UAE OR Scotland OR Zimbabwe OR Namibia OR Uganda OR USA OR Ireland) when:3d',
        'cricket (rivalry OR feud OR debate OR clash OR showdown OR revenge OR rematch) when:3d',
        'cricket (record OR milestone OR first-ever OR fastest OR youngest OR oldest OR unbeaten) when:3d',
        'cricket (comeback OR breakthrough OR breakout OR uncapped OR debut OR teenager OR youngster) when:3d',
        'cricket (retirement OR legacy OR career OR farewell OR landmark) when:3d',
        'cricket (ban OR fine OR suspension OR row OR backlash OR statement OR apology) when:3d',
        'cricket (law OR rule OR technology OR pitch OR venue OR board decision) when:3d',
    ],
}


TOP5_QUERIES = [
    '(India OR Pakistan OR "Sri Lanka" OR Bangladesh) cricket when:3d',
    'cricket (record OR milestone OR first OR fastest OR historic OR upset OR breakout) when:3d',
    'cricket (injury OR comeback OR retirement OR debut OR dropped OR recalled) when:3d',
    'cricket (controversy OR ban OR suspension OR statement OR reaction OR feud OR clash) when:3d',
    'cricket (women OR WPL OR domestic OR Ranji OR U19 OR associate) when:3d',
    'cricket (BCCI OR PCB OR ICC OR board OR IPL OR PSL OR WPL) (decision OR rule OR signing OR retention OR appointment) when:3d',
]

TOP5_TIMEOUT = 4.0
TOP5_QUERY_BATCH_SIZE = 2

TOP5_MORE_QUERIES = [
    'cricket (Nepal OR Oman OR UAE OR Scotland OR Zimbabwe OR Namibia OR Uganda OR USA) when:3d',
    'cricket (youngest OR oldest OR first-ever OR unbeaten OR milestone OR record) when:3d',
    'cricket (comeback OR breakthrough OR breakout OR uncapped OR teenager OR youngster) when:3d',
    'cricket (retirement OR farewell OR legacy OR career OR landmark) when:3d',
    'cricket (law OR technology OR pitch OR venue OR board decision) when:3d',
    'cricket (transfer OR release OR auction OR signing OR retention OR franchise) when:3d',
]

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

CRICKET_NARRATIVE_TERMS = {
    "rivalry", "feud", "debate", "clash", "showdown", "revenge", "rematch",
    "upset", "underdog", "breakout", "breakthrough", "comeback", "redemption",
    "retirement", "farewell", "legacy", "rise", "fall", "record", "milestone",
    "historic", "first", "fastest", "youngest", "oldest", "stuns", "shock",
    "controversy", "row", "ban", "banned", "suspended", "backlash", "reveals",
    "responds", "admits", "refuses", "returns", "debut", "teenager", "youngster",
}
CRICKET_UNDERCOVERED_TERMS = {
    "women", "wpl", "ranji", "county", "domestic", "u19", "u-19", "under-19",
    "associate", "uncapped", "emerging", "nepal", "oman", "uae", "scotland",
    "zimbabwe", "namibia", "uganda", "usa", "ireland", "afghanistan",
}
CRICKET_CONSEQUENCE_TERMS = {
    "ruled out", "dropped", "recalled", "selected", "retired", "banned",
    "suspended", "released", "retained", "appointed", "signed", "miss",
    "availability", "qualify", "qualification", "title", "record",
}

@dataclass(frozen=True)
class Topic:
    title: str
    source: str
    published_at: datetime
    url: str
    description: str = ""
    score: float = 0.0
    group_key: str = ""
    group_members: tuple["Topic", ...] = ()

def _clean(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()

@lru_cache(maxsize=4096)
def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+(?:['-][a-z0-9]+)?", _clean(value).casefold())
        if len(token) > 2 and token not in TITLE_STOPWORDS
    }

@lru_cache(maxsize=4096)
def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(_clean(url))
    except ValueError:
        return _clean(url).casefold().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return _clean(url).casefold().rstrip("/")
    return parsed._replace(query="", fragment="").geturl().rstrip("/").casefold()

@lru_cache(maxsize=4096)
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

@lru_cache(maxsize=4096)
def _event_groups(title: str) -> set[str]:
    tokens = _tokens(title)
    return {group for group, terms in EVENT_GROUPS.items() if tokens & terms}

TEAM_ENTITIES = {
    "india", "pakistan", "sri lanka", "bangladesh", "australia", "england",
    "south africa", "new zealand", "west indies", "afghanistan", "ireland",
}


@lru_cache(maxsize=4096)
def _known_entities(text: str) -> set[str]:
    value = _clean(text).casefold()
    known = INDIA_ASIA_TERMS | CRICKET_COMPETITIONS | TEAM_ENTITIES
    return {entity for entity in known if len(entity) > 3 and entity in value}


@lru_cache(maxsize=4096)
def _named_phrases(title: str) -> set[str]:
    return {
        _clean(match)
        for match in re.findall(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+\b", title)
        if len(_clean(match).split()) >= 2
    }


@lru_cache(maxsize=8192)
def _same_event_general(a: Topic, b: Topic) -> bool:
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


@lru_cache(maxsize=4096)
def _cricket_core_tokens(title: str) -> set[str]:
    generic = CRICKET_TERMS | set().union(*EVENT_GROUPS.values()) | TITLE_STOPWORDS
    return _tokens(title) - generic


@lru_cache(maxsize=8192)
def _cricket_same_event(a: Topic, b: Topic) -> bool:
    if _canonical_url(a.url) == _canonical_url(b.url):
        return True

    similarity = max(
        fuzz.token_set_ratio(a.title, b.title),
        fuzz.token_sort_ratio(a.title, b.title),
    )
    shared_core = _cricket_core_tokens(a.title) & _cricket_core_tokens(b.title)
    groups = _event_groups(a.title) & _event_groups(b.title)
    entities = _known_entities(f"{a.title} {a.description}") & _known_entities(f"{b.title} {b.description}")
    specific_entities = entities - TEAM_ENTITIES
    named = _named_phrases(a.title) & _named_phrases(b.title)

    if groups and shared_core and (specific_entities or named):
        return True
    if similarity >= 86 and len(shared_core) >= 2 and (specific_entities or named):
        return True
    if similarity >= 97 and len(shared_core) >= 3:
        return True
    return False


NON_PLAYER_ENTITIES = (
    TEAM_ENTITIES
    | CRICKET_COMPETITIONS
    | {"bcci", "pcb", "icc", "mcc", "mumbai indians", "rcb", "royal challengers"}
)
KNOWN_PLAYER_NAMES = {
    term
    for term in INDIA_ASIA_TERMS
    if term not in NON_PLAYER_ENTITIES
}
KNOWN_PLAYER_ALIASES = KNOWN_PLAYER_NAMES | {
    term.split()[-1]
    for term in KNOWN_PLAYER_NAMES
    if len(term.split()) > 1
}


NICHE_TILE_STOPWORDS = {
    *TITLE_STOPWORDS,
    "sport", "sports", "player", "players", "team", "teams", "coach", "coaches",
    "manager", "managers", "star", "stars", "championship", "championships",
    "champion", "champions", "final", "finals", "match", "matches", "game", "games",
    "series", "round", "rounds", "season", "seasons", "title", "titles", "win", "wins",
    "won", "beat", "beats", "defeat", "defeats", "victory", "victories", "event",
    "events", "world", "international", "open", "cup", "league", "leagues",
}

@lru_cache(maxsize=4096)
def _niche_entity(title: str) -> str:
    clean = _clean(title)
    for phrase in sorted(
        _named_phrases(clean),
        key=lambda value: (-len(value.split()), clean.index(value)),
    ):
        parts = phrase.casefold().split()
        if parts and not all(part in NICHE_TILE_STOPWORDS for part in parts):
            return phrase.casefold()

    candidates = [
        token.casefold()
        for token in re.findall(r"\b[A-Z][A-Za-z0-9'-]{2,}\b", clean)
        if token.casefold() not in NICHE_TILE_STOPWORDS
    ]
    if candidates:
        return candidates[0]

    meaningful = _tokens(clean) - NICHE_TILE_STOPWORDS
    return max(meaningful, key=lambda value: (len(value), value), default="")



@lru_cache(maxsize=4096)
def _player_entity(title: str) -> str:
    text = _clean(title).casefold()
    known = [
        name
        for name in KNOWN_PLAYER_ALIASES
        if re.search(rf"\b{re.escape(name)}\b", text)
    ]
    if known:
        return max(known, key=lambda name: (len(name), -text.index(name)))

    for phrase in sorted(
        _named_phrases(title),
        key=lambda value: (-len(value), title.index(value)),
    ):
        candidate = _clean(phrase).casefold()
        if candidate and not any(
            entity in candidate for entity in NON_PLAYER_ENTITIES
        ):
            return candidate
    return ""


def _entity_group_key(topic: Topic) -> str:
    player = _player_entity(topic.title)
    return f"player:{player}" if player else f"story:{_canonical_url(topic.url)}"


def _tile_group_key(topic: Topic, profile: str) -> str:
    if profile == "niche_sports":
        keyword = _niche_entity(topic.title)
        return f"keyword:{keyword}" if keyword else f"story:{_canonical_url(topic.url)}"
    return _entity_group_key(topic)


def _profile_relevant(title: str, description: str, profile: str | None) -> bool:
    if profile == "niche_sports":
        text = f"{title} {description}".casefold()
        return any(term in text for term in (
            "tennis", "badminton", "squash", "athletics", "swimming", "cycling",
            "golf", "boxing", "wrestling", "hockey", "kabaddi", "volleyball",
            "basketball", "chess", "motorsport", "motogp", "formula 1",
        )) and not any(
            re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)
            for term in CRICKET_TERMS
        )
    if profile not in {"cricket_india_asia", "cricket_global"}:
        return False
    text = f"{title} {description}".casefold()
    return not any(term in text for term in NON_CRICKET_TERMS)

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

def _fetch_google(
    query: str,
    timeout: float = TIMEOUT,
    *,
    geo: str | None = "IN",
) -> list[Topic]:
    params = {"q": query}
    if geo == "IN":
        params.update({"hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    elif geo:
        code = str(geo).upper()
        params.update({"hl": "en-US", "gl": code, "ceid": f"{code}:en"})
    else:
        params.update({"hl": "en"})
    response = requests.get(
        GOOGLE_NEWS_URL,
        params=params,
        headers=HEADERS,
        timeout=timeout,
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


def _decode_google_json(response_text: str) -> dict:
    content = str(response_text or "").lstrip()
    if content.startswith(")]}',"):
        content = content[5:]
    elif content.startswith(")]}'"):
        content = content[4:]
    return json.loads(content)


def _youtube_autocomplete(keyword: str) -> list[str]:
    response = requests.get(
        YOUTUBE_AUTOCOMPLETE_URL,
        params={"client": "youtube", "ds": "yt", "hl": "en", "q": _clean(keyword)},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    payload = response.json()
    return [
        _clean(item[0])
        for item in (payload[1] if isinstance(payload, list) and len(payload) > 1 else [])
        if isinstance(item, list) and item and _clean(item[0])
    ]


def _youtube_trend_queries(keyword: str) -> list[dict]:
    language = "en-US"
    request = {
        "comparisonItem": [{
            "keyword": _clean(keyword),
            "geo": "",
            "time": "now 1-d",
        }],
        "category": 0,
        "property": "youtube",
    }
    explore = requests.get(
        YOUTUBE_TRENDS_EXPLORE_URL,
        params={"hl": language, "tz": "330", "req": json.dumps(request)},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    widgets = _decode_google_json(explore.text).get("widgets") or []
    widget = next(
        (item for item in widgets if "RELATED_QUERIES" in str(item.get("id") or "")),
        None,
    )
    if not widget:
        return []

    related = requests.get(
        YOUTUBE_TRENDS_RELATED_URL,
        params={
            "hl": language,
            "tz": "330",
            "req": json.dumps(widget["request"]),
            "token": widget["token"],
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    ranked = _decode_google_json(related.text).get("default", {}).get("rankedList") or []
    rows = []
    for index, signal in enumerate(("Top", "Rising")):
        items = ranked[index].get("rankedKeyword", []) if index < len(ranked) else []
        for rank, item in enumerate(items, 1):
            query = _clean(item.get("query"))
            if not query:
                continue
            raw_value = item.get("value")
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = 100.0 if str(raw_value).casefold() == "breakout" else 0.0
            rows.append({
                "keyword": query,
                "signal": signal,
                "value": value,
                "rank": rank,
                "breakout": str(raw_value).casefold() == "breakout",
                "seed": _clean(keyword),
            })

    try:
        suggestions = set(_youtube_autocomplete(keyword))
    except (requests.RequestException, ValueError, TypeError):
        suggestions = set()
    for row in rows:
        row["autocomplete"] = row["keyword"] in suggestions
    return rows


def fetch_youtube_search_trends(
    limit: int = 20,
) -> list[dict]:
    if limit <= 0:
        return []

    grouped: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(YOUTUBE_TREND_SEEDS)) as pool:
        futures = {
            pool.submit(_youtube_trend_queries, seed): (seed, profile)
            for seed, profile in YOUTUBE_TREND_SEEDS
        }
        for future in as_completed(futures):
            seed, profile = futures[future]
            try:
                rows = future.result()
            except (requests.RequestException, ValueError, TypeError, KeyError):
                continue

            for row in rows:
                raw_keyword = _clean(row.get("keyword"))
                key = raw_keyword.casefold()
                if not raw_keyword or _utility(raw_keyword):
                    continue
                item = grouped.setdefault(
                    key,
                    {
                        "keyword": raw_keyword,
                        "evidence": 0.0,
                        "rising": False,
                        "breakout": False,
                        "autocomplete": False,
                        "seeds": set(),
                        "profiles": set(),
                    },
                )
                rank = max(1, int(row.get("rank") or 1))
                weight = 1.5 if row.get("signal") == "Rising" else 1.0
                item["evidence"] = max(
                    item["evidence"],
                    weight / rank + (0.35 if row.get("breakout") else 0.0),
                )
                if row.get("signal") == "Rising":
                    item["rising"] = True
                if row.get("breakout"):
                    item["breakout"] = True
                item["autocomplete"] = item["autocomplete"] or bool(row.get("autocomplete"))
                item["seeds"].add(seed.casefold())
                item["profiles"].add(profile)

    candidates = []
    for item in grouped.values():
        raw_keyword = item["keyword"]
        normalized = re.sub(
            r"\bt(\d+)(?:st|nd|rd|th)\b",
            r"t\1",
            raw_keyword.casefold(),
        )
        tokens = re.findall(r"[a-z0-9]+", normalized)
        meaningful = [
            token
            for token in tokens
            if token not in YOUTUBE_TREND_NOISE_TERMS
            and (not token.isdigit() or len(token) == 4)
        ]
        subject_tokens = [
            token
            for token in meaningful
            if token not in YOUTUBE_TREND_GENERIC_TERMS and not token.isdigit()
        ]
        if not subject_tokens or not meaningful:
            continue

        story_keyword = " ".join(meaningful).strip()
        if len(story_keyword) < 4:
            continue

        profile = (
            "cricket_india_asia"
            if "cricket_india_asia" in item["profiles"]
            else "cricket_global"
            if "cricket_global" in item["profiles"]
            else "niche_sports"
        )
        candidates.append({
            **item,
            "keyword": story_keyword,
            "trend_query": raw_keyword,
            "profile": profile,
        })

    if not candidates:
        raise RuntimeError("YouTube search trends did not produce any story-worthy signals.")

    candidates.sort(
        key=lambda item: (item["evidence"], item["keyword"].casefold()),
        reverse=True,
    )
    target_date = _today_local_date()
    date_filter = f"after:{target_date.isoformat()} before:{(target_date + timedelta(days=1)).isoformat()}"
    validated = []

    with ThreadPoolExecutor(max_workers=min(12, len(candidates))) as pool:
        futures = {}
        for item in candidates[: max(limit * 3, 40)]:
            context = "cricket" if item["profile"] != "niche_sports" else "sports"
            query = (
                f'({item["trend_query"]}) OR ({item["keyword"]}) '
                f'{context} {date_filter}'
            )
            futures[pool.submit(_fetch_google, query, TIMEOUT, geo=None)] = item

        for future in as_completed(futures):
            item = futures[future]
            try:
                rows = future.result()
            except (requests.RequestException, ET.ParseError, ValueError):
                continue

            prepared = _prepare(rows, set(), profile=item["profile"])
            prepared = [
                row
                for row in prepared
                if row.published_at.astimezone(LOCAL_TIMEZONE).date() == target_date
            ]
            stories = _select(prepared, 3, set(), profile=item["profile"])
            if not stories:
                continue

            score = item["evidence"] + min(1.5, 0.5 * len(stories))
            validated.append({
                "keyword": item["keyword"],
                "trend_query": item["trend_query"],
                "hashtag": "#" + re.sub(r"[^A-Za-z0-9]+", "", item["keyword"]),
                "signal": "Rising" if item["rising"] or item["breakout"] else "Top",
                "breakout": item["breakout"],
                "youtube_autocomplete": item["autocomplete"],
                "seed_count": len(item["seeds"]),
                "profile": item["profile"],
                "news_count": len(stories),
                "top_news_title": stories[0].title,
                "topics": stories,
                "score": score,
            })

    if not validated:
        raise RuntimeError("YouTube search trend services returned no news-backed story signals. Retry the trend fetch.")

    maximum = max(item["score"] for item in validated)
    for item in validated:
        item["score"] = round(item["score"] / maximum * 100, 1)

    validated.sort(
        key=lambda item: (item["score"], item["keyword"].casefold()),
        reverse=True,
    )
    return validated[:limit]

def _today_local_date():
    return datetime.now(LOCAL_TIMEZONE).date()


def fetch_youtube_trend_topics(
    keyword: str,
    profile: str,
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
) -> list[Topic]:
    if profile not in {"cricket_india_asia", "cricket_global", "niche_sports"}:
        raise ValueError(f"Unknown YouTube trend profile: {profile}")
    clean_keyword = _clean(keyword)
    if not clean_keyword or limit <= 0:
        return []

    target_date = _today_local_date()
    next_date = target_date + timedelta(days=1)
    date_filter = f"after:{target_date.isoformat()} before:{next_date.isoformat()}"
    context = "cricket" if profile != "niche_sports" else "sports"
    queries = [
        f"{clean_keyword} {context} {date_filter}",
        f"{clean_keyword} {context} (latest OR news OR update OR reaction OR statement) {date_filter}",
        f"{clean_keyword} {context} (record OR injury OR transfer OR appointment OR controversy OR result) {date_filter}",
        f"{clean_keyword} {context} (confirms OR reveals OR announces OR returns OR wins) {date_filter}",
    ]
    if more:
        queries = queries[:3]

    existing = list(exclude_topics or [])
    seen_urls = {
        _canonical_url(member.url)
        for topic in existing
        for member in (topic.group_members or (topic,))
    }
    rows: list[Topic] = []
    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
        futures = [
            pool.submit(_fetch_google, query, TIMEOUT, geo=None)
            for query in queries
        ]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError):
                continue

    prepared = _prepare(rows, seen_urls, profile=profile)
    prepared = [
        row for row in prepared
        if row.published_at.astimezone(LOCAL_TIMEZONE).date() == target_date
    ]
    chosen = _select(
        prepared,
        limit,
        seen_urls,
        existing=existing if more else [],
        profile=profile,
    )
    return chosen[:limit]



def _score_niche(topic: Topic) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)
    freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 6.0
    event_signal = min(2.4, len(_event_groups(topic.title)) * 0.6)
    meaningful = _tokens(topic.title) - CRICKET_TERMS - set().union(*EVENT_GROUPS.values())
    specificity = min(2.0, max(0, len(meaningful) - 1) * 0.4)
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    return freshness + event_signal + specificity - source_penalty


def _score_cricket(topic: Topic, profile: str) -> float:
    text = f"{topic.title} {topic.description}".casefold()
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)

    freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 6.0

    core = _cricket_core_tokens(topic.title)
    specificity = min(2.5, max(0, len(core) - 1) * 0.45)

    narrative_hits = sum(
        1 for term in CRICKET_NARRATIVE_TERMS
        if (term in text if " " in term else term in _tokens(topic.title))
    )
    narrative = min(4.0, narrative_hits * 0.8)

    consequence_hits = sum(term in text for term in CRICKET_CONSEQUENCE_TERMS)
    consequence = min(2.0, consequence_hits * 0.55)

    undercovered_hits = sum(
        1 for term in CRICKET_UNDERCOVERED_TERMS
        if (term in text if " " in term else term in _tokens(topic.title))
    )
    undercovered = min(1.8, undercovered_hits * 0.45)

    unusual = 1.2 if any(
        term in text for term in (
            "first ever", "first-ever", "stuns", "shock", "surprise", "unusual",
            "rare", "record", "historic", "bizarre", "unexpected",
        )
    ) else 0.0

    generic = -1.4 if len(core) <= 2 and narrative_hits == 0 and consequence_hits == 0 else 0.0
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    local = 1.0 if profile == "cricket_india_asia" and any(
        term in text for term in INDIA_ASIA_TERMS
    ) else 0.0

    return freshness + specificity + narrative + consequence + undercovered + unusual + local - generic - source_penalty


def _prepare(
    rows: list[Topic],
    seen_urls: set[str],
    profile: str | None = None,
) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    seen = {_canonical_url(url) for url in seen_urls}
    prepared = []
    seen_row_urls = set()

    for row in rows:
        title = _clean_title(row.title, row.source)
        url = _canonical_url(row.url)
        if not title or not url or url in seen or url in seen_row_urls:
            continue
        if row.published_at < cutoff or _utility(title):
            continue
        if not _profile_relevant(title, row.description, profile):
            continue

        if profile == "niche_sports" and not re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip():
            continue

        prepared.append(
            Topic(title, _clean(row.source), row.published_at, url, _clean(row.description), row.score)
        )
        seen_row_urls.add(url)

    if profile == "niche_sports":
        unique = []
        seen_titles = set()
        for row in prepared:
            key = re.sub(r"[^a-z0-9]+", " ", row.title.casefold()).strip()
            if key and key not in seen_titles:
                unique.append(row)
                seen_titles.add(key)
        return unique

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
    cricket = profile != "niche_sports"
    same_event = _cricket_same_event if cricket else _same_event_general
    blocked = [
        member
        for topic in (existing or [])
        for member in (topic.group_members or (topic,))
    ]
    seen = {_canonical_url(url) for url in seen_urls}
    blocked_groups = {
        _tile_group_key(topic, profile)
        for topic in blocked
    }

    ranked = sorted(
        (
            replace(
                r,
                score=_score_niche(r) if profile == "niche_sports" else _score_cricket(r, profile),
            )
            for r in rows
        ),
        key=lambda r: r.score,
        reverse=True,
    )
    candidates = [
        row
        for row in ranked
        if row.url not in seen
        and not any(same_event(row, old) for old in blocked)
        and (not cricket or _entity_group_key(row) not in blocked_groups)
    ]

    cluster_window = candidates[: min(len(candidates), max(350, limit * 18))]
    clusters: list[list[Topic]] = []
    for row in cluster_window:
        for cluster in clusters:
            if same_event(row, cluster[0]):
                cluster.append(row)
                break
        else:
            clusters.append([row])

    event_representatives: list[Topic] = []
    source_counts: dict[str, int] = {}
    for cluster in clusters:
        ordered = sorted(cluster, key=lambda row: row.score, reverse=True)
        candidate = next(
            (
                row for row in ordered
                if not _source_key(row.source)
                or source_counts.get(_source_key(row.source), 0) < 2
            ),
            ordered[0],
        )
        if any(same_event(candidate, old) for old in blocked + event_representatives):
            continue
        event_representatives.append(candidate)
        source = _source_key(candidate.source)
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1

    group_keys = {
        _tile_group_key(row, profile)
        for row in event_representatives
    }

    for row in candidates:
        if not any(same_event(row, old) for old in blocked + event_representatives):
            event_representatives.append(row)
            group_key = _tile_group_key(row, profile)
            group_keys.add(group_key)
            if len(group_keys) >= limit:
                break

    groups: dict[str, list[Topic]] = {}
    for row in event_representatives:
        groups.setdefault(_tile_group_key(row, profile), []).append(row)

    ordered_groups = sorted(
        groups.items(),
        key=lambda item: max(row.score for row in item[1]),
        reverse=True,
    )
    chosen: list[Topic] = []
    for group_key, members in ordered_groups[:limit]:
        ordered_members = tuple(sorted(members, key=lambda row: row.score, reverse=True))
        chosen.append(
            replace(
                ordered_members[0],
                group_key=group_key,
                group_members=ordered_members,
            )
        )

    return chosen


def fetch_top5_topics(
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
) -> list[Topic]:
    """Build the Top-5 story pool with an adaptive, fast query plan."""
    if limit <= 0:
        return []

    existing = list(exclude_topics or [])
    seen_urls = {
        _canonical_url(member.url)
        for topic in existing
        for member in (topic.group_members or (topic,))
    }
    queries = TOP5_MORE_QUERIES if more else TOP5_QUERIES
    rows = []
    chosen = []
    selection_existing = existing if more else []

    for start in range(0, len(queries), TOP5_QUERY_BATCH_SIZE):
        batch = queries[start:start + TOP5_QUERY_BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = [
                pool.submit(_fetch_google, query, TOP5_TIMEOUT)
                for query in batch
            ]
            for future in as_completed(futures):
                try:
                    rows.extend(future.result())
                except (requests.RequestException, ET.ParseError, ValueError):
                    continue

        prepared = _prepare(rows, seen_urls, profile="cricket_india_asia")
        chosen = _select(
            prepared,
            limit,
            seen_urls,
            existing=selection_existing,
            profile="cricket_india_asia",
        )
        if len(chosen) >= limit:
            return chosen[:limit]

    return chosen[:limit]


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
    seen_urls = {
        _canonical_url(member.url)
        for topic in existing
        for member in (topic.group_members or (topic,))
    }
    selection_existing = existing if more and not keyword else []

    if keyword:
        clean_keyword = _clean(keyword).replace('"', " ")
        queries = [] if not clean_keyword else [
            query.format(keyword=clean_keyword) for query in KEYWORD_QUERIES
        ]
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
    chosen = _select(prepared, limit, seen_urls, existing=selection_existing, profile=profile)

    if len(chosen) < limit and profile != "niche_sports":
        try:
            if keyword:
                gdelt_query = f'"{_clean(keyword)}" cricket'
            elif profile == "cricket_global":
                gdelt_query = (
                    '(cricket record milestone rivalry controversy comeback upset '
                    'breakout women domestic associate board)'
                )
            else:
                gdelt_query = (
                    '(cricket India Pakistan "Sri Lanka" Bangladesh record milestone '
                    'rivalry controversy comeback upset breakout women domestic associate BCCI ICC)'
                )

            fallback_rows = _prepare(
                _fetch_gdelt(gdelt_query),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                profile=profile,
            )
            chosen.extend(
                _select(
                    fallback_rows,
                    limit - len(chosen),
                    seen_urls | {_canonical_url(topic.url) for topic in chosen},
                    existing=selection_existing + chosen,
                    profile=profile,
                )
            )
        except (requests.RequestException, ET.ParseError, ValueError):
            pass

    return chosen[:limit]