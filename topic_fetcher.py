from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Final-Shorts/1.0"}
TIMEOUT = 12
LOOKBACK_HOURS = 72
TARGET = 20
QUERY_WINDOW = 6


QUERIES = {
    "cricket_india_asia": [
        'cricket India when:3d',
        '"Virat Kohli" cricket when:3d',
        '"Rohit Sharma" cricket when:3d',
        '"Shubman Gill" cricket when:3d',
        '"Indian cricket" (injury OR comeback OR return OR selection) when:3d',
        '"Indian cricket" (record OR milestone OR debut OR retirement) when:3d',
        '"Indian cricket" (reacts OR responds OR statement OR controversy OR clash) when:3d',
        '"Indian women cricket" when:3d',
    ],
    "cricket_global": [
        'international cricket when:3d',
        'Australia cricket when:3d',
        'England cricket when:3d',
        '"South Africa" cricket when:3d',
        '"New Zealand" cricket when:3d',
        '"West Indies" cricket when:3d',
        '"Pakistan cricket" when:3d',
        '"Afghanistan cricket" when:3d',
    ],
    "niche_sports": [
        'tennis when:3d',
        'badminton when:3d',
        'Formula 1 OR F1 when:3d',
        'MotoGP motorsport when:3d',
        'athletics when:3d',
        'boxing wrestling hockey when:3d',
        'basketball volleyball kabaddi when:3d',
        'golf cycling swimming squash chess when:3d',
    ],
}


MORE_QUERIES = {
    "cricket_india_asia": [
        'Pakistan cricket when:3d',
        'Sri Lanka cricket when:3d',
        'Bangladesh cricket when:3d',
        'Nepal cricket when:3d',
        '"Asian Games" cricket when:3d',
        '"women cricket" Asia when:3d',
        'cricket India (upset OR historic OR breakthrough OR surprise) when:3d',
        'cricket India (injury OR fit OR ruled OR withdrawn) when:3d',
        'cricket India (selection OR named OR squad OR XI) when:3d',
        'cricket India (record OR milestone OR debut OR century) when:3d',
        'cricket India (reveals OR admits OR confirms OR says) when:3d',
        'cricket India (fans OR viral OR reacts OR responds) when:3d',
        'BCCI cricket when:3d',
        'ICC cricket Asia when:3d',
        '"Indian women cricket" (record OR upset OR statement OR selection) when:3d',
        'cricket Asia (upset OR historic OR breakthrough OR controversy) when:3d',
    ],
    "cricket_global": [
        '"Pakistan cricket" (injury OR selection OR return OR comeback) when:3d',
        '"Australia cricket" (injury OR selection OR comeback OR retirement) when:3d',
        '"England cricket" (injury OR selection OR comeback OR retirement) when:3d',
        '"South Africa cricket" (injury OR selection OR record OR upset) when:3d',
        '"New Zealand cricket" (injury OR selection OR record OR upset) when:3d',
        '"West Indies cricket" (injury OR selection OR record OR upset) when:3d',
        '"women cricket" (record OR upset OR breakthrough OR statement) when:3d',
        'cricket (reacts OR responds OR reveals OR admits OR controversy) when:3d',
        'cricket (record OR milestone OR debut OR retirement) when:3d',
        'cricket (upset OR historic OR breakthrough OR shock) when:3d',
        'cricket (fans OR viral OR unusual OR bizarre) when:3d',
        'cricket (county OR franchise OR league) (statement OR controversy OR record) when:3d',
        'ICC cricket (decision OR statement OR change OR rule) when:3d',
        'cricket (captain OR coach) (resigns OR appointed OR dropped OR backs) when:3d',
        'cricket (ban OR fined OR suspended OR ruled out) when:3d',
        'cricket (contract OR sponsor OR deal) when:3d',
    ],
    "niche_sports": [
        'tennis (upset OR breakthrough OR comeback OR record) when:3d',
        'tennis (injury OR retirement OR statement OR controversy) when:3d',
        'badminton (upset OR title OR medal OR record) when:3d',
        'badminton (injury OR comeback OR statement OR controversy) when:3d',
        'Formula 1 OR F1 (pole OR crash OR win OR controversy) when:3d',
        'MotoGP (win OR crash OR pole OR controversy) when:3d',
        'athletics (record OR medal OR breakthrough OR upset) when:3d',
        'boxing wrestling (upset OR title OR comeback OR controversy) when:3d',
        'hockey kabaddi (upset OR title OR medal OR statement) when:3d',
        'basketball volleyball (record OR upset OR comeback OR controversy) when:3d',
        'golf cycling swimming (record OR title OR medal OR breakthrough) when:3d',
        'squash chess (upset OR title OR record OR breakthrough) when:3d',
        'women sports (record OR upset OR breakthrough OR statement) when:3d',
        'sports (reacts OR responds OR reveals OR controversy) when:3d',
        'sports (historic OR bizarre OR unusual OR shocking) when:3d',
        'sports (fans OR viral OR social media reaction) when:3d',
    ],
}


GDELT_QUERIES = {
    "cricket_india_asia": [
        'cricket India',
        'cricket Asia India Pakistan Sri Lanka Bangladesh Afghanistan Nepal',
        '"women cricket" India Asia',
        'BCCI OR ICC cricket',
    ],
    "cricket_global": [
        'international cricket',
        'Australia OR England OR "South Africa" OR "New Zealand" OR "West Indies" cricket',
        '"women cricket"',
        'ICC cricket',
    ],
    "niche_sports": [
        'tennis OR badminton OR "Formula 1" OR F1 OR MotoGP',
        'athletics OR boxing OR wrestling OR hockey OR kabaddi',
        'basketball OR volleyball OR golf OR cycling OR swimming',
        'squash OR chess OR "table tennis"',
    ],
}


CRICKET_TERMS = {
    "cricket", "bcci", "icc", "wicket", "wickets", "innings", "batting", "bowling",
    "batter", "batsman", "batsmen", "bowler", "odi", "t20", "test", "ranji",
    "ipl", "ashes", "world cup", "champions trophy", "asia cup",
}
NICHE_SPORT_TERMS = {
    "tennis", "badminton", "squash", "table tennis", "formula 1", "f1", "motogp",
    "motorsport", "athletics", "marathon", "swimming", "golf", "cycling", "boxing",
    "hockey", "kabaddi", "volleyball", "basketball", "wrestling", "chess", "olympics",
    "para sport", "grand prix",
}
OTHER_SPORT_TERMS = {
    "football", "soccer", "rugby", "baseball", "american football", "mma", "ufc",
}


EVENT_GROUPS = {
    "injury": {"injury", "injured", "injuries", "scare", "blow", "hurt", "pain", "fitness", "fit", "cleared"},
    "selection": {"selection", "selected", "named", "picked", "squad", "xi", "eleven", "dropped", "recalled"},
    "retirement": {"retirement", "retire", "retired", "farewell"},
    "debut": {"debut", "debuted"},
    "comeback": {"comeback", "return", "returns", "returned"},
    "record": {"record", "records", "milestone", "milestones", "landmark"},
    "result": {
        "win", "wins", "won", "beat", "beats", "beaten", "defeat", "defeated",
        "champion", "championship", "final", "upset", "title", "medal", "podium",
        "victory", "victorious", "qualifies", "qualified",
    },
    "controversy": {
        "controversy", "controversial", "clash", "clashes", "row", "blasts", "slams",
        "criticises", "criticizes", "banned", "suspended", "fined", "confrontation",
    },
    "statement": {
        "says", "said", "reveals", "revealed", "confirms", "confirmed", "admits", "admitted",
        "reacts", "reacted", "responds", "responded", "backs", "urges", "warns", "comments",
    },
    "crash": {"crash", "crashed", "collision"},
    "race": {"pole", "qualifying", "qualified", "race"},
    "wicket": {"dismissed", "dismissal", "wicket"},
    "contract": {"contract", "sponsor", "sponsorship", "deal", "agreement"},
}


TOKEN_ALIASES = {
    "injured": "injury",
    "injuries": "injury",
    "retired": "retire",
    "retirement": "retire",
    "returns": "return",
    "returned": "return",
    "reveals": "reveal",
    "revealed": "reveal",
    "confirms": "confirm",
    "confirmed": "confirm",
    "reacts": "react",
    "reacted": "react",
    "responds": "respond",
    "responded": "respond",
    "criticizes": "criticise",
    "criticised": "criticise",
    "criticises": "criticise",
    "wins": "win",
    "won": "win",
    "beats": "beat",
    "beaten": "beat",
    "defeated": "defeat",
    "records": "record",
    "milestones": "milestone",
    "says": "say",
    "said": "say",
}


STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "by", "with",
    "from", "ahead", "after", "before", "as", "is", "are", "was", "were", "has", "have",
    "had", "vs", "v", "into", "over", "under", "than", "that", "this", "his", "her",
    "their", "its", "will", "says", "said", "also", "more", "new", "latest", "today",
    "today's", "now", "about", "who", "what", "how", "why", "when",
}


GENERIC_TITLE_PATTERNS = (
    r"^sports news$",
    r"^latest sports news$",
    r"^sports news[-: ]",
    r"^today'?s top \d+",
    r"^top \d+ .*news",
    r"^live updates?$",
    r"^live blog$",
)


NON_STORY_PATTERNS = (
    r"\bhow to watch\b",
    r"\bwhere to watch\b",
    r"\bwatch live\b",
    r"\blive streaming\b",
    r"\bfree streaming\b",
    r"\bstream(?:ing)? details\b",
    r"\bfixtures?\b",
    r"\bschedule\b",
    r"\bstandings?\b",
    r"\bpoints table\b",
    r"\bscorecard\b",
    r"\bmatch centre\b",
    r"\bmatch center\b",
    r"\bas it happened\b",
    r"\blive updates?\b",
    r"\b(?:photos?|photo gallery|gallery)\b",
    r"\bquiz\b",
    r"\bround[- ]?up\b",
    r"\bpredictions?\b",
    r"\bpredicted\b",
    r"\blineups? and pitch report\b",
    r"\bmedal tally\b",
    r"\brankings?\b",
    r"\bstarting xi prediction\b",
)


AUDIENCE_PULL_TERMS = {
    "react", "respond", "reveal", "confirm", "admit", "slam", "blast", "praise",
    "drop", "ruled", "withdraw", "suspend", "ban", "fine", "shock", "surprise",
    "historic", "first", "only", "never", "breakthrough", "comeback", "retire",
    "debut", "controversy", "clash", "upset", "record", "milestone", "injury",
    "viral", "bizarre", "unusual",
}


SOURCE_WEIGHTS = {
    "espncricinfo.com": 2.0,
    "icc-cricket.com": 2.0,
    "icc": 1.8,
    "reuters.com": 2.0,
    "apnews.com": 2.0,
    "bbc.com": 1.8,
    "bbc.co.uk": 1.8,
    "indianexpress.com": 1.7,
    "sportstar.thehindu.com": 1.7,
    "hindustantimes.com": 1.6,
    "ndtv.com": 1.6,
    "timesofindia.indiatimes.com": 1.5,
    "thehindu.com": 1.7,
    "olympics.com": 1.7,
    "theguardian.com": 1.6,
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


def _canonical_url(url: str) -> str:
    raw = _clean(url)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        if not host:
            return raw
        return f"{parsed.scheme.lower()}://{host}{path}"
    except ValueError:
        return raw


def _tokenise(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+(?:['-][a-z0-9]+)?", _clean(value).lower())
    return [TOKEN_ALIASES.get(word, word) for word in words if word not in STOPWORDS and len(word) > 2]


def _tokens(value: str) -> set[str]:
    return set(_tokenise(value))


def _parse_date(value: str) -> datetime:
    value = _clean(value)
    if not value:
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)

    try:
        if re.fullmatch(r"\d{14}", value):
            return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)

    if dt is None:
        return datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS + 1)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _strip_source_suffix(title: str, source: str) -> str:
    title = _clean(title)
    source = _clean(source)
    if not title or not source:
        return title

    patterns = (
        rf"\s+[-|–—]\s+{re.escape(source)}\s*$",
        rf"\s+[-|–—]\s+{re.escape(source.split('.')[0])}\s*$",
    )
    for pattern in patterns:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()
    return title


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE)
        for term in terms
    )


def _profile_terms(profile: str) -> set[str]:
    if profile.startswith("cricket_"):
        return CRICKET_TERMS
    return NICHE_SPORT_TERMS


def _sports_relevant(profile: str, title: str, description: str = "") -> bool:
    title_text = _clean(title).casefold()
    description_text = _clean(description).casefold()

    wanted = _profile_terms(profile)
    if _contains_any(title_text, wanted):
        return True

    if profile.startswith("cricket_"):
        return (
            len(_tokens(title)) >= 4
            and _contains_any(description_text, wanted)
            and not _contains_any(title_text, OTHER_SPORT_TERMS | NICHE_SPORT_TERMS)
        )

    return (
        _contains_any(description_text, wanted)
        and not _contains_any(title_text, OTHER_SPORT_TERMS)
    )


def _is_story_title(title: str) -> bool:
    normalised = _clean(title).casefold()
    if not normalised or any(re.search(pattern, normalised) for pattern in GENERIC_TITLE_PATTERNS):
        return False
    if any(re.search(pattern, normalised) for pattern in NON_STORY_PATTERNS):
        return False

    words = _tokens(normalised)
    if len(words) < 4:
        return False

    return True


def _event_groups(value: str) -> set[str]:
    words = _tokens(value)
    return {
        group
        for group, terms in EVENT_GROUPS.items()
        if words & {TOKEN_ALIASES.get(term, term) for term in terms}
    }


def _identity_tokens(value: str) -> set[str]:
    generic = {
        "cricket", "tennis", "badminton", "squash", "table", "formula", "f1", "motogp",
        "motorsport", "athletics", "swimming", "golf", "cycling", "boxing", "hockey",
        "kabaddi", "volleyball", "basketball", "wrestling", "chess", "olympics", "sport",
        "sports", "match", "series", "game", "games", "team", "teams", "player", "players",
        "international", "world", "cup", "championship", "final", "event",
    }
    return _tokens(value) - generic - AUDIENCE_PULL_TERMS


def _related_event_groups(a: set[str], b: set[str]) -> bool:
    if a & b:
        return True
    related = {
        frozenset({"injury", "selection"}),
        frozenset({"injury", "comeback"}),
        frozenset({"injury", "statement"}),
        frozenset({"selection", "statement"}),
        frozenset({"result", "wicket"}),
        frozenset({"crash", "race"}),
    }
    return any(group_pair <= (a | b) for group_pair in related)


def _same_event(a: Topic, b: Topic) -> bool:
    shared = _identity_tokens(a.title) & _identity_tokens(b.title)
    if len(shared) < 2:
        return False

    groups_a = _event_groups(a.title)
    groups_b = _event_groups(b.title)

    if _related_event_groups(groups_a, groups_b):
        return len(shared) >= 3 or bool(shared & {"retire", "injury", "record", "debut", "return", "crash"})

    return len(shared) >= 4


def _source_weight(topic: Topic) -> float:
    haystack = f"{topic.source} {topic.url}".casefold()
    return max(
        (weight for domain, weight in SOURCE_WEIGHTS.items() if domain in haystack),
        default=0.4,
    )


def _score(topic: Topic) -> float:
    age_hours = max(
        0.0,
        (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600,
    )
    freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 5.0

    title_tokens = _tokens(topic.title)
    pull_bonus = min(4.0, len(title_tokens & AUDIENCE_PULL_TERMS) * 0.9)

    event_bonus = min(2.5, len(_event_groups(topic.title)) * 0.6)

    distinctive = _identity_tokens(topic.title)
    specificity = min(3.0, max(0, len(distinctive) - 2) * 0.5)

    source_bonus = _source_weight(topic)

    length_penalty = 0.0
    if len(topic.title) > 150:
        length_penalty = 0.8

    return freshness + pull_bonus + event_bonus + specificity + source_bonus - length_penalty


def _parse_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    rows: list[Topic] = []

    for item in root.findall(".//item"):
        title = _clean(item.findtext("title") or "")
        url = _canonical_url(item.findtext("link") or "")
        published = _parse_date(item.findtext("pubDate") or "")
        description = _clean(item.findtext("description") or "")

        source_el = item.find("source")
        source = _clean(source_el.text if source_el is not None else "")

        title = _strip_source_suffix(title, source)
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
        params={
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": 75,
            "timespan": "3d",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    articles = response.json().get("articles", [])
    rows: list[Topic] = []

    for item in articles:
        title = _clean(item.get("title", ""))
        url = _canonical_url(item.get("url", ""))
        if not title or not url:
            continue

        rows.append(
            Topic(
                title=title,
                source=_clean(item.get("domain", "")),
                published_at=_parse_date(item.get("seendate", "")),
                url=url,
                description=_clean(item.get("snippet", "")),
            )
        )

    return rows


def _prepare(
    rows: list[Topic],
    seen_urls: set[str],
    profile: str | None = None,
) -> list[Topic]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    prepared: list[Topic] = []
    seen_titles: set[str] = set()

    for topic in rows:
        canonical_url = _canonical_url(topic.url)
        if not canonical_url or canonical_url in seen_urls:
            continue
        if topic.published_at < cutoff:
            continue
        if not _is_story_title(topic.title):
            continue
        if profile and not _sports_relevant(profile, topic.title, topic.description):
            continue

        title_key = " ".join(_tokenise(topic.title))
        if not title_key or title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        prepared.append(
            Topic(
                title=_clean(topic.title),
                source=_clean(topic.source),
                published_at=topic.published_at,
                url=canonical_url,
                description=_clean(topic.description),
            )
        )

    return prepared


def _select(
    rows: list[Topic],
    limit: int,
    seen_urls: set[str],
    existing: list[Topic] | None = None,
) -> list[Topic]:
    if limit <= 0:
        return []

    ranked = sorted(
        (
            Topic(
                row.title,
                row.source,
                row.published_at,
                row.url,
                row.description,
                _score(row),
            )
            for row in rows
        ),
        key=lambda row: (row.score, row.published_at),
        reverse=True,
    )

    chosen: list[Topic] = []
    blocked = list(existing or [])
    seen_title_keys = {
        " ".join(_tokenise(topic.title))
        for topic in blocked
        if topic.title
    }

    for topic in ranked:
        if topic.url in seen_urls:
            continue
        title_key = " ".join(_tokenise(topic.title))
        if title_key in seen_title_keys:
            continue
        if any(_same_event(topic, other) for other in blocked + chosen):
            continue
        chosen.append(topic)
        seen_title_keys.add(title_key)
        if len(chosen) >= limit:
            break

    return chosen


def _query_batches(profile: str, more: bool, existing_count: int) -> list[list[str]]:
    bank = QUERIES[profile] + MORE_QUERIES[profile]
    if not more:
        start = 0
    else:
        start = min(
            (max(existing_count, 0) // TARGET) * QUERY_WINDOW,
            len(bank),
        )

    batches = [
        bank[index:index + QUERY_WINDOW]
        for index in range(start, len(bank), QUERY_WINDOW)
    ]

    return [batch for batch in batches if batch]


def _fetch_query_batch(queries: list[str]) -> list[Topic]:
    rows: list[Topic] = []
    workers = min(QUERY_WINDOW, max(1, len(queries)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_google, query) for query in queries]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except (requests.RequestException, ET.ParseError, ValueError, OSError):
                continue

    return rows


def _fetch_gdelt_recovery(profile: str) -> list[Topic]:
    rows: list[Topic] = []
    queries = GDELT_QUERIES[profile]

    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
        futures = [pool.submit(_fetch_gdelt, query) for query in queries]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except (requests.RequestException, ValueError, OSError):
                continue

    return rows


def fetch_topics(
    profile: str = "cricket_india_asia",
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
) -> list[Topic]:
    if profile not in QUERIES:
        raise ValueError(f"Unknown profile: {profile}")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    existing = list(exclude_topics or [])
    seen_urls = {_canonical_url(topic.url) for topic in existing if topic.url}

    candidates: list[Topic] = []
    chosen: list[Topic] = []

    for batch in _query_batches(profile, more, len(existing)):
        candidates.extend(_prepare(_fetch_query_batch(batch), seen_urls, profile))
        chosen = _select(candidates, limit, seen_urls, existing)
        if len(chosen) >= limit:
            return chosen[:limit]

    if len(chosen) < limit:
        recovery_rows = _prepare(
            _fetch_gdelt_recovery(profile),
            seen_urls | {topic.url for topic in chosen},
            profile,
        )
        candidates.extend(recovery_rows)
        chosen = _select(
            candidates,
            limit,
            seen_urls,
            existing,
        )

    return chosen[:limit]
