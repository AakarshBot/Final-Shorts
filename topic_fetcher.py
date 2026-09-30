from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
import html
import math
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests
import trendflow

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 12
LOOKBACK_HOURS = 48
MORE_LOOKBACK_HOURS = 72
TREND_LIMIT = 20
TREND_QUERY_LIMIT = 10
TARGET = 20
MAX_QUERY_RESULTS = 100

BASE_QUERIES = {
    "cricket_india_asia": [
        'cricket India Pakistan "Sri Lanka" when:3d',
        '(WPL OR IPL OR BCCI OR PCB OR "Sri Lanka Cricket" OR Bangladesh cricket) when:3d',
        'women cricket when:3d',
        'international cricket when:3d',
        'cricket (law OR laws OR rule OR rules OR coach OR appointed OR retained OR released OR signed OR transfer OR pitch OR venue OR innovation) when:3d',
        'cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR controversy OR upset) when:3d',
        '(franchise OR league OR tournament) cricket when:3d',
    ],
    "cricket_global": [
        'cricket when:3d',
        'international cricket when:3d',
        'women cricket when:3d',
        'cricket (law OR laws OR rule OR rules OR coach OR appointed OR retained OR released OR signed OR transfer OR pitch OR venue OR innovation) when:3d',
        'cricket (record OR milestone OR debut OR comeback OR retirement OR injury OR controversy OR upset) when:3d',
        '(franchise OR league OR tournament) cricket when:3d',
        'cricket board announcement when:3d',
    ],
    "niche_sports": [
        '(tennis OR badminton OR squash OR "table tennis") when:3d',
        '(F1 OR "Formula 1" OR MotoGP OR motorsport) when:3d',
        '(athletics OR swimming OR cycling OR golf) when:3d',
        '(boxing OR wrestling OR hockey OR kabaddi) when:3d',
        '(volleyball OR basketball OR chess) when:3d',
        '(tennis OR badminton OR F1 OR athletics OR boxing OR hockey) (record OR upset OR debut OR comeback OR injury OR controversy OR coach) when:3d',
    ],
}

MORE_QUERIES = {
    "cricket_india_asia": [
        'cricket (retention OR release OR appointment OR ownership OR sponsor OR venue OR pitch OR law OR technology) when:3d',
        '(Australia OR England OR South Africa OR New Zealand OR West Indies) cricket when:3d',
        '(WPL OR PSL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) cricket when:3d',
        'cricket (women OR domestic OR franchise OR associate) when:3d',
        'cricket (statement OR interview OR reaction OR row OR ban OR fine OR suspension) when:3d',
    ],
    "cricket_global": [
        'cricket (retention OR release OR appointment OR ownership OR sponsor OR venue OR pitch OR law OR technology) when:3d',
        '(Australia OR England OR South Africa OR New Zealand OR West Indies) cricket when:3d',
        '(WPL OR PSL OR BBL OR CPL OR SA20 OR ILT20 OR MLC) cricket when:3d',
        'cricket (women OR domestic OR franchise OR associate) when:3d',
        'cricket (statement OR interview OR reaction OR row OR ban OR fine OR suspension) when:3d',
        'cricket (future schedule OR calendar OR format OR rules) when:3d',
    ],
    "niche_sports": [
        'tennis (coach OR injury OR contract OR statement OR reaction OR controversy) when:3d',
        '(F1 OR MotoGP OR motorsport) (contract OR penalty OR crash OR statement OR reaction) when:3d',
        '(badminton OR athletics OR swimming OR cycling OR golf) (coach OR injury OR record OR statement) when:3d',
        '(boxing OR wrestling OR hockey OR kabaddi OR basketball OR chess) (coach OR injury OR title OR statement) when:3d',
    ],
}

CRICKET_INDIA_ASIA_TERMS = {
    "india", "indian", "pakistan", "pakistani", "sri lanka", "sri lankan", "bangladesh",
    "bcci", "pcb", "icc", "wpl", "ipl", "mumbai indians", "rcb", "royal challengers",
    "babar azam", "virat kohli", "rohit sharma", "shubman gill", "jasprit bumrah",
}
CRICKET_TERMS = {
    "cricket", "bcci", "pcb", "icc", "wpl", "ipl", "odi", "t20", "test", "wicket", "innings",
    "batting", "bowling", "retention", "retained", "release", "released", "franchise", "pitch",
    "mcc", "laws", "law", "cricket south africa", "mi emirates", "sa20", "psl", "bbl", "cpl",
    "ilt20", "mlc", "womens premier league", "women's cricket", "head coach", "coach", "curator",
}
STRONG_CRICKET_TERMS = {
    "cricket", "bcci", "pcb", "icc", "wpl", "ipl", "odi", "t20", "test", "wicket", "innings",
    "batting", "bowling", "mcc", "cricket south africa", "mi emirates", "sa20", "psl", "bbl", "cpl",
    "ilt20", "mlc", "womens premier league", "women's cricket",
}
NON_CRICKET_TERMS = {
    "football", "soccer", "tennis", "badminton", "squash", "athletics", "marathon", "swimming",
    "cycling", "boxing", "wrestling", "hockey", "kabaddi", "volleyball", "basketball", "chess",
    "motorsport", "motogp", "formula", "f1",
}
SPORT_WORDS = {
    "cricket", "bcci", "ipl", "wicket", "innings", "batting", "bowling", "odi", "t20", "test",
    "tennis", "badminton", "squash", "table", "formula", "f1", "motogp", "motorsport",
    "athletics", "swimming", "golf", "cycling", "boxing", "hockey", "kabaddi", "volleyball",
    "basketball", "wrestling", "chess", "race", "grand", "prix", "olympics", "para",
}
CRICKET_ENTITY_NAMES = {
    "virat kohli", "rohit sharma", "shubman gill", "jasprit bumrah", "hardik pandya",
    "ravindra jadeja", "rishabh pant", "kl rahul", "kuldeep yadav", "mohammed siraj",
    "arshdeep singh", "yashasvi jaiswal", "sanju samson", "suryakumar yadav", "shreyas iyer",
    "axar patel", "washington sundar", "rinku singh", "prasidh krishna", "smriti mandhana",
    "harmanpreet kaur", "jemimah rodrigues", "babar azam", "mohammad rizwan", "shaheen afridi",
    "naseem shah", "haris rauf", "mark boucher", "fraser stewart",
}
CRICKET_COMPETITIONS = {
    "world cup", "champions trophy", "wpl", "ipl", "psl", "bbl", "cpl", "sa20", "ilt20", "mlc",
    "test championship", "ashes", "county championship", "big bash", "mi emirates",
}
EVENT_GROUPS = {
    "injury": {"injury", "injured", "scare", "pain", "blow", "hurt", "ruled", "layoff"},
    "selection": {"selection", "selected", "dropped", "recalled", "squad", "picked", "omitted"},
    "retirement": {"retirement", "retire", "retired", "farewell", "farewells", "goodbye"},
    "debut": {"debut", "debuted"},
    "comeback": {"comeback", "return", "returns", "returned", "recall", "recalled"},
    "record": {"record", "records", "milestone", "historic", "history", "first-ever", "fastest", "youngest"},
    "result": {"win", "wins", "won", "beat", "beaten", "defeat", "lost", "loss", "draw", "champion", "championship", "upset", "title", "medal", "podium"},
    "controversy": {"controversy", "controversial", "statement", "criticises", "criticizes", "slams", "blasts", "row", "backlash"},
    "contract": {"contract", "signed", "signs", "sponsor", "sponsorship", "deal", "ownership"},
    "discipline": {"banned", "ban", "fined", "fine", "suspended", "sanctioned"},
    "appointment": {"appointed", "appointment", "named", "names", "coach", "manager", "reins"},
    "rules": {"law", "laws", "rule", "rules", "regulation", "regulations", "change", "changes"},
    "franchise": {"franchise", "retention", "retained", "release", "released", "auction", "league"},
    "innovation": {"innovation", "innovative", "technology", "technological", "exchangeable", "trialing", "trial"},
}
EVENT_CONTEXT = {"odi", "t20", "test", "series", "tour", "season", "world", "cup", "final", "match", "championship", "league"}
TITLE_NOISE = {
    "story", "stories", "event", "events", "update", "updates", "player", "players", "star", "stars",
    "team", "teams", "news", "report", "reports", "latest", "says", "said", "today", "official",
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "by", "with", "from",
    "ahead", "after", "before", "as", "is", "are", "was", "were", "has", "have", "had", "vs", "v",
    "into", "over", "says", "said", "will", "its", "their", "his", "her", "how", "what", "which",
    "this", "that", "these", "those", "also", "more", "than", "against", "amid", "through", "after",
}
AUDIENCE_PULL_TERMS = {
    "reacts", "reacted", "responds", "responded", "slams", "blasts", "criticises", "criticizes", "reveals",
    "admits", "confirms", "snubs", "snubbed", "dropped", "ruled", "withdraws", "withdrawn", "suspended", "banned",
    "fined", "shocking", "shock", "surprise", "surprising", "historic", "first", "only", "never", "breakthrough",
    "comeback", "retirement", "debut", "controversy", "clash", "upset", "record", "milestone", "injury", "viral",
}
PUBLISHER_PENALTIES = {"cricketwebs", "cricketnmore", "socialnews.xyz", "northdesk.in"}
LOW_SIGNAL_PATTERNS = (
    r"\bcalled on\b", r"\barrives? in\b", r"\bset to face\b", r"\broad ?map\b", r"\bpreview\b",
)
UTILITY_PATTERNS = (
    r"\bhow to watch\b", r"\bwhere to watch\b", r"\blive streaming\b", r"\blive stream\b", r"\blive telecast\b",
    r"\bplaying xi\b", r"\bpredicted xi\b", r"\bpredicted lineups?\b", r"\bpitch report\b", r"\bscorecard\b",
    r"\blive score\b", r"\bmatch updates?\b", r"\bfixtures?\b", r"\bschedule\b", r"\bstandings?\b",
)
GENERIC_PATTERNS = (r"^\s*sports news\s*$", r"^\s*latest sports news\s*$", r"\btop \d+ .*news\b", r"\bphoto gallery\b", r"\bquiz\b", r"\bnews roundup\b")


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


def _parse_date(value) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    value = _clean(value)
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        return datetime.now(timezone.utc) - timedelta(hours=MORE_LOOKBACK_HOURS + 1)
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
    return _clean(source).casefold().replace("www.", "").split("/")[0].strip()


def _clean_title(title: str, source: str = "") -> str:
    title = _clean(title)
    source_key = _source_key(source)
    if source_key:
        for separator in (" | ", " - ", " – ", " — "):
            parts = title.split(separator)
            if len(parts) > 1 and _source_key(parts[-1]) == source_key:
                title = separator.join(parts[:-1]).strip()
                break
    return _clean(re.sub(r"\s*(?:\||-)\s*(?:cricket|sports?|news)\s*$", "", title, flags=re.IGNORECASE))


def _utility(title: str) -> bool:
    text = _clean(title).casefold()
    return any(re.search(pattern, text) for pattern in UTILITY_PATTERNS + GENERIC_PATTERNS)


def _event_groups(title: str) -> set[str]:
    words = _tokens(title)
    return {group for group, terms in EVENT_GROUPS.items() if words & terms}


def _profile_relevant(title: str, description: str, profile: str | None, source: str = "") -> bool:
    if not profile:
        return True
    text = f"{_clean(title)} {_clean(description)}".casefold()
    title_tokens = _tokens(title)
    if profile == "niche_sports":
        if title_tokens & {"cricket", "bcci", "wpl", "ipl", "wicket", "innings"}:
            return False
        niche_terms = SPORT_WORDS - {"cricket", "bcci", "ipl", "wicket", "innings", "batting", "bowling", "odi", "t20", "test"}
        return bool(title_tokens & niche_terms)
    strong_cricket = any(term in text for term in STRONG_CRICKET_TERMS) or any(name in text for name in CRICKET_ENTITY_NAMES) or any(comp in text for comp in CRICKET_COMPETITIONS)
    if title_tokens & NON_CRICKET_TERMS and not strong_cricket:
        return False
    if strong_cricket or any(term in text for term in {"retention", "franchise", "coach", "appointment", "pitch", "law", "rules"}):
        return True
    source_key = _source_key(source)
    return any(token in source_key for token in ("cric", "espn", "icc", "wisden", "bcci", "pcb", "cricket"))


def _same_event(a: Topic, b: Topic) -> bool:
    ta, tb = _tokens(a.title), _tokens(b.title)
    groups_a, groups_b = _event_groups(a.title), _event_groups(b.title)
    title_a, title_b = _clean(a.title).casefold(), _clean(b.title).casefold()
    shared = (ta & tb) - TITLE_NOISE
    if groups_a and groups_b and groups_a.isdisjoint(groups_b):
        shared_names = {name for name in CRICKET_ENTITY_NAMES if name in title_a and name in title_b}
        if not shared_names:
            return False
    ratio = SequenceMatcher(None, title_a, title_b).ratio()
    if ratio >= 0.58 or len(shared) >= 3:
        return True
    shared_names = {name for name in CRICKET_ENTITY_NAMES if name in title_a and name in title_b}
    return bool(shared_names and groups_a and groups_a & groups_b)


def _trend_value(value) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"[0-9][0-9,.]*", str(value))
        return float(match.group(0).replace(",", "")) if match else 0.0
    except (TypeError, ValueError):
        return 0.0


def _trend_signals(profile: str, more: bool = False) -> list[dict]:
    try:
        client = trendflow.Client(language="en", timeout=10)
        result = client.trending_now(region="IN", window=4)
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1 if not more else 12)
    signals = []
    for item in getattr(result, "results", [])[:TREND_LIMIT]:
        title = _clean(getattr(item, "title", ""))
        if not title:
            continue
        started = _parse_date(getattr(item, "started_at", ""))
        if started < cutoff and not getattr(item, "active", True):
            continue
        text = title.casefold()
        tokens = _tokens(title)
        sports = bool(tokens & SPORT_WORDS) or any(term in text for term in CRICKET_TERMS | CRICKET_COMPETITIONS)
        if not sports:
            continue
        if profile == "niche_sports" and ("cricket" in text or tokens & {"bcci", "wpl", "ipl"}):
            continue
        growth = _trend_value(getattr(item, "growth", 0))
        volume = _trend_value(getattr(item, "volume", 0))
        score = min(10.0, math.log1p(max(volume, 0)) * 1.2 + math.log1p(max(growth, 0)) * 1.3)
        signals.append({"title": title, "tokens": tokens, "score": score, "started_at": started})
    signals.sort(key=lambda item: item["score"], reverse=True)
    return signals[:TREND_QUERY_LIMIT]


def _trend_bonus(topic: Topic, signals: list[dict]) -> float:
    if not signals:
        return 0.0
    title = _clean(topic.title).casefold()
    tokens = _tokens(topic.title)
    best = 0.0
    for signal in signals:
        if signal["title"].casefold() in title or title in signal["title"].casefold():
            overlap = 1.0
        else:
            overlap = len(tokens & signal["tokens"]) / max(1, len(signal["tokens"]))
        best = max(best, signal["score"] * min(1.0, overlap * 1.8))
    return min(8.0, best)


def _score(topic: Topic, profile: str | None = None, trend_bonus: float = 0.0) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600)
    lookback = MORE_LOOKBACK_HOURS if profile == "niche_sports" else LOOKBACK_HOURS
    freshness = max(0.0, lookback - age_hours) / lookback * 6.0
    event_bonus = min(2.8, len(_event_groups(topic.title)) * 0.8)
    pull_bonus = min(4.0, len(_tokens(topic.title) & AUDIENCE_PULL_TERMS))
    distinctive = _tokens(topic.title) - SPORT_WORDS - TITLE_NOISE - set().union(*EVENT_GROUPS.values()) - EVENT_CONTEXT
    specificity = min(2.0, max(0, len(distinctive) - 2) * 0.35)
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    low_signal_penalty = 1.5 if any(re.search(pattern, topic.title, re.IGNORECASE) for pattern in LOW_SIGNAL_PATTERNS) else 0.0
    generic_penalty = 3.0 if _utility(topic.title) else 0.0
    local_boost = 0.0
    if profile == "cricket_india_asia":
        evidence = f"{topic.title} {topic.description}".casefold()
        local_boost = min(2.0, 0.5 * sum(term in evidence for term in CRICKET_INDIA_ASIA_TERMS))
    return freshness + event_bonus + pull_bonus + specificity + trend_bonus + local_boost - source_penalty - low_signal_penalty - generic_penalty


def _parse_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    rows = []
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
        if title and url:
            rows.append(Topic(title, _clean(item.get("domain", "")), _parse_date(item.get("seendate", "")), url, _clean(item.get("snippet", ""))))
    return rows


def _prepare(rows: list[Topic], seen_urls: set[str], profile: str | None = None, lookback_hours: int | None = None) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours or (MORE_LOOKBACK_HOURS if profile == "niche_sports" else LOOKBACK_HOURS))
    seen_urls = {_canonical_url(url) for url in seen_urls}
    out, seen_titles = [], set()
    for topic in rows:
        title = _clean_title(topic.title, topic.source)
        url = _canonical_url(topic.url)
        if not title or not url or url in seen_urls or topic.published_at < cutoff or _utility(title):
            continue
        if not _profile_relevant(title, topic.description, profile, topic.source):
            continue
        title_key = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
        if not title_key or title_key in seen_titles:
            continue
        out.append(Topic(title, _clean(topic.source), topic.published_at, url, _clean(topic.description), topic.score))
        seen_titles.add(title_key)
    return out


def _select(rows: list[Topic], limit: int, seen_urls: set[str], existing: list[Topic] | None = None, profile: str | None = None, signals: list[dict] | None = None) -> list[Topic]:
    if limit <= 0:
        return []
    existing = list(existing or [])
    seen_canonical = {_canonical_url(url) for url in seen_urls}
    candidates = []
    for row in rows:
        if _canonical_url(row.url) in seen_canonical:
            continue
        if any(_same_event(row, old) for old in existing):
            continue
        score = _score(row, profile=profile, trend_bonus=_trend_bonus(row, signals or []))
        candidates.append(Topic(row.title, row.source, row.published_at, row.url, row.description, score))
    candidates.sort(key=lambda topic: topic.score, reverse=True)

    clusters: list[list[Topic]] = []
    for topic in candidates:
        for cluster in clusters:
            if _same_event(topic, cluster[0]):
                cluster.append(topic)
                break
        else:
            clusters.append([topic])

    def cluster_score(cluster: list[Topic]) -> float:
        best = max(cluster, key=lambda t: t.score)
        sources = {_source_key(t.source) for t in cluster if _source_key(t.source)}
        coverage_bonus = min(2.2, math.log2(len(cluster) + 1) * 0.8)
        source_bonus = min(2.0, max(0, len(sources) - 1) * 0.5)
        return best.score + coverage_bonus + source_bonus

    clusters.sort(key=cluster_score, reverse=True)
    chosen: list[Topic] = []
    source_counts: dict[str, int] = {}

    def add(topic: Topic) -> None:
        chosen.append(topic)
        source = _source_key(topic.source)
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1

    for cluster in clusters:
        if len(chosen) >= limit:
            break
        representative = cluster[0]
        source = _source_key(representative.source)
        if source and source_counts.get(source, 0) >= 2 and len(chosen) < max(1, limit // 2):
            alternatives = [item for item in cluster if _source_key(item.source) != source and _source_key(item.source)]
            representative = alternatives[0] if alternatives else representative
        add(representative)

    if len(chosen) < limit:
        for cluster in clusters:
            for topic in cluster[1:]:
                if len(chosen) >= limit:
                    break
                if topic.url in {item.url for item in chosen}:
                    continue
                source = _source_key(topic.source)
                if source and source_counts.get(source, 0) >= 2 and len(chosen) < max(1, limit // 2):
                    continue
                add(topic)
            if len(chosen) >= limit:
                break

    return chosen[:limit]


def _keyword_queries(profile: str, keyword: str) -> list[str]:
    keyword = _clean(keyword).replace('"', " ")
    if not keyword:
        return []
    phrase = f'"{keyword}"' if " " in keyword else keyword
    return [
        f"{phrase} cricket when:3d",
        f"{phrase} cricket (breaking OR result OR record OR milestone OR appointment OR injury OR controversy) when:3d",
        f"{phrase} cricket (reacts OR responds OR reveals OR confirms OR statement OR backlash) when:3d",
        f"{phrase} cricket (women OR franchise OR league OR board OR rules OR pitch) when:3d",
    ]


def _gdelt_query(profile: str, keyword: str | None = None) -> str:
    if keyword:
        return f'"{_clean(keyword)}" cricket'
    if profile == "niche_sports":
        return '(tennis badminton squash "table tennis" F1 MotoGP athletics swimming cycling golf boxing wrestling hockey kabaddi basketball chess)'
    return '(cricket WPL IPL BCCI ICC Pakistan India Australia England South Africa "West Indies" "New Zealand")'


def fetch_topics(profile: str = "cricket_india_asia", more: bool = False, exclude_topics: list[Topic] | None = None, limit: int = TARGET, keyword: str | None = None) -> list[Topic]:
    if profile not in BASE_QUERIES:
        raise ValueError(f"Unknown profile: {profile}")
    if limit <= 0:
        return []

    existing = list(exclude_topics or [])
    seen_urls = {_canonical_url(topic.url) for topic in existing}
    signals = _trend_signals(profile, more=more) if not keyword else []
    queries = _keyword_queries(profile, keyword) if _clean(keyword or "") else list(BASE_QUERIES[profile])
    if more and not keyword:
        queries.extend(MORE_QUERIES[profile])
    for signal in signals:
        phrase = signal["title"].replace('"', " ")
        if profile == "niche_sports" and "cricket" in phrase.casefold():
            continue
        queries.append(f'"{phrase}" {"cricket" if profile != "niche_sports" else "sports"} when:3d')
    queries = list(dict.fromkeys(queries))

    rows: list[Topic] = []
    with ThreadPoolExecutor(max_workers=min(10, len(queries) or 1)) as pool:
        futures = {pool.submit(_fetch_google, query): query for query in queries}
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except (requests.RequestException, ValueError, ET.ParseError):
                continue

    prepared = _prepare(rows, seen_urls, profile=profile, lookback_hours=MORE_LOOKBACK_HOURS if more else None)
    chosen = _select(prepared, limit, seen_urls, existing=existing, profile=profile, signals=signals)

    if len(chosen) < limit:
        try:
            gdelt_rows = _prepare(
                _fetch_gdelt(_gdelt_query(profile, keyword)),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                profile=profile,
                lookback_hours=MORE_LOOKBACK_HOURS if more else None,
            )
            chosen.extend(_select(
                gdelt_rows,
                limit - len(chosen),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                existing=existing + chosen,
                profile=profile,
                signals=signals,
            ))
        except (requests.RequestException, ValueError, ET.ParseError):
            pass

    return chosen[:limit]
