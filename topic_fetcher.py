"""Cricket Topic Fetcher.

The fetcher builds a large current pool, removes duplicate events, and fills the
requested number of story/entity groups without changing the Topic handoff.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

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


def _cricket_core_tokens(title: str) -> set[str]:
    generic = CRICKET_TERMS | set().union(*EVENT_GROUPS.values()) | TITLE_STOPWORDS
    return _tokens(title) - generic


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
    return f"player:{player}" if player else f"story:{_canonical_url(topic.url)}


def _profile_relevant(title: str, description: str, profile: str | None) -> bool:
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
        _entity_group_key(topic)
        for topic in blocked
    } if cricket else set()

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
        if _canonical_url(row.url) not in seen
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

    if not cricket:
        return event_representatives[:limit]

    groups: dict[str, list[Topic]] = {}
    for row in event_representatives:
        groups.setdefault(_entity_group_key(row), []).append(row)

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
    chosen = _select(prepared, limit, seen_urls, existing=existing, profile=profile)

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
                    existing=existing + chosen,
                    profile=profile,
                )
            )
        except (requests.RequestException, ET.ParseError, ValueError):
            pass

    return chosen[:limit]
