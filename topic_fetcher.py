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
        '(India OR Pakistan OR "Sri Lanka") cricket (breaking OR result OR upset OR record OR milestone OR comeback OR debut OR retirement OR injury) when:3d',
        'India cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'Pakistan cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        '"Sri Lanka" cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        '(BCCI OR PCB OR "Sri Lanka Cricket") cricket (decision OR announcement OR selection OR contract OR ban OR suspension OR statement) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (reacts OR responds OR reveals OR confirms OR admits OR slams OR criticizes OR controversy) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (viral OR "social media" OR "fans react" OR bizarre OR unusual OR stunning OR shocking) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket ("last ball" OR "last over" OR turnaround OR comeback OR upset OR "record-breaking") when:3d',
        '(India OR Pakistan OR "Sri Lanka") women cricket (record OR upset OR medal OR selection OR reaction OR breakthrough OR controversy) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (youngster OR debutant OR breakthrough OR uncapped OR emerging) when:3d',
    ],
    "cricket_global": [
        'international cricket (breaking OR result OR upset OR record OR milestone OR comeback OR debut OR retirement OR injury) when:3d',
        'Australia cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'England cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'South Africa cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'New Zealand cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'West Indies cricket (record OR upset OR comeback OR debut OR retirement OR injury OR selection OR controversy) when:3d',
        'women international cricket (record OR upset OR medal OR selection OR reaction OR breakthrough OR controversy) when:3d',
        'international cricket (reacts OR responds OR reveals OR confirms OR admits OR slams OR criticizes OR controversy) when:3d',
        'international cricket (viral OR "social media" OR "fans react" OR bizarre OR unusual OR stunning OR shocking) when:3d',
        'international cricket ("last ball" OR "last over" OR turnaround OR comeback OR upset OR "record-breaking") when:3d',
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
        '(India OR Pakistan OR "Sri Lanka") cricket (dropped OR recalled OR ruled out OR signed OR fined OR banned OR suspended OR contract) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (statement OR interview OR reaction OR criticism OR praise OR apology OR row) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (viral OR fans OR "social media" OR unusual OR bizarre OR heated OR clash) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (records OR milestones OR first-ever OR youngest OR fastest OR highest) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (dramatic OR thriller OR "last ball" OR comeback OR upset) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (youngster OR debutant OR uncapped OR breakout OR emerging star) when:3d',
        'India women cricket (record OR upset OR breakthrough OR controversy OR reaction OR selection) when:3d',
        'Pakistan women cricket (record OR upset OR breakthrough OR controversy OR reaction OR selection) when:3d',
        '"Sri Lanka" women cricket (record OR upset OR breakthrough OR controversy OR reaction OR selection) when:3d',
        '(BCCI OR PCB OR "Sri Lanka Cricket") (contract OR sponsor OR coach OR captain OR disciplinary OR board) cricket when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (off-field OR feud OR dispute OR apology OR criticism) when:3d',
    ],
    "cricket_global": [
        'international cricket (dropped OR recalled OR ruled out OR signed OR fined OR banned OR suspended OR contract) when:3d',
        'international cricket (statement OR interview OR reaction OR criticism OR praise OR apology OR row) when:3d',
        'international cricket (viral OR fans OR "social media" OR unusual OR bizarre OR heated OR clash) when:3d',
        'international cricket (records OR milestones OR first-ever OR youngest OR fastest OR highest) when:3d',
        'international cricket (dramatic OR thriller OR "last ball" OR comeback OR upset) when:3d',
        'international cricket (youngster OR debutant OR breakout OR emerging star) when:3d',
        'women international cricket (record OR upset OR breakthrough OR controversy OR reaction OR selection) when:3d',
        'international cricket (off-field OR feud OR dispute OR apology OR criticism) when:3d',
        'international cricket (contract OR sponsor OR venue OR rule OR board) when:3d',
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

DISCOVERY_QUERIES = {
    "cricket_india_asia": [
        '(India OR Pakistan OR "Sri Lanka") cricket (unexpected OR surprising OR stunning OR bizarre OR bizarrely OR extraordinary) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (viral OR trending OR "social media" OR fans) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (clash OR row OR feud OR apology OR backlash OR slammed) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (upset OR shock OR "record crowd" OR "record viewership" OR historic) when:3d',
        '(India OR Pakistan OR "Sri Lanka") cricket (newcomer OR debutant OR youngster OR breakout OR uncapped) when:3d',
    ],
    "cricket_global": [
        'international cricket (unexpected OR surprising OR stunning OR bizarre OR extraordinary) when:3d',
        'international cricket (viral OR trending OR "social media" OR fans) when:3d',
        'international cricket (clash OR row OR feud OR apology OR backlash OR slammed) when:3d',
        'international cricket (upset OR shock OR "record crowd" OR "record viewership" OR historic) when:3d',
        'international cricket (newcomer OR debutant OR youngster OR breakout OR uncapped) when:3d',
    ],
    "niche_sports": [],
}

PROFILE_LOOKBACK_HOURS = {
    "cricket_india_asia": 48,
    "cricket_global": 48,
    "niche_sports": 72,
}

CRICKET_INDIA_ASIA_SCOPE = (
    "india",
    "indian",
    "pakistan",
    "pakistani",
    "sri lanka",
    "sri lankan",
    "bcci",
    "pcb",
    "sri lanka cricket",
)

CRICKET_INDIA_ASIA_ENTITIES = {
    "virat kohli", "rohit sharma", "shubman gill", "jasprit bumrah", "hardik pandya",
    "ravindra jadeja", "rishabh pant", "kl rahul", "kuldeep yadav", "mohammed siraj",
    "arshdeep singh", "yashasvi jaiswal", "sanju samson", "suryakumar yadav",
    "shreyas iyer", "axar patel", "washington sundar", "rinku singh", "prasidh krishna",
    "smriti mandhana", "harmapreet kaur", "jemimah rodrigues",
    "babar azam", "mohammad rizwan", "shaheen afridi", "naseem shah", "haris rauf",
    "fakhar zaman", "imam-ul-haq", "shadab khan", "mohammad nawaz", "salman ali agha",
    "abdullah shafique", "saim ayub", "mohammad amir",
    "wanindu hasaranga", "kusal mendis", "pathum nissanka", "charith asalanka",
    "maheesh theekshana", "dhananjaya de silva", "matheesha pathirana", "kusal perera",
    "angelo mathews", "dushmantha chameera", "kamindu mendis",
}

SPORT_WORDS = {
    "cricket", "bcci", "ipl", "wicket", "innings", "batting", "bowling", "odi", "t20", "test",
    "tennis", "badminton", "squash", "table", "formula", "f1", "motogp", "motorsport",
    "athletics", "swimming", "golf", "cycling", "boxing", "hockey", "kabaddi", "volleyball",
    "basketball", "wrestling", "chess", "race", "grand", "prix", "olympics", "para",
}

CRICKET_TERMS = {"cricket", "bcci", "wicket", "innings", "batting", "bowling", "odi", "t20", "test"}
CRICKET_ENTITY_NAMES = {
    "virat kohli", "rohit sharma", "shubman gill", "jasprit bumrah", "hardik pandya",
    "ravindra jadeja", "rishabh pant", "kl rahul", "kuldeep yadav", "mohammed siraj",
    "arshdeep singh", "yashasvi jaiswal", "sanju samson", "suryakumar yadav",
    "shreyas iyer", "axar patel", "washington sundar", "rinku singh", "prasidh krishna",
    "smriti mandhana", "harmapreet kaur", "jemimah rodrigues",
}
NON_CRICKET_TERMS = {
    "football", "soccer", "tennis", "badminton", "squash", "athletics", "marathon", "swimming",
    "cycling", "boxing", "wrestling", "hockey", "kabaddi", "volleyball", "basketball", "chess",
    "motorsport", "motogp", "formula", "f1",
}
UTILITY_PATTERNS = (
    r"\bhow to watch\b",
    r"\bwhere to watch\b",
    r"\blive streaming\b",
    r"\blive stream\b",
    r"\blive telecast\b",
    r"\bfree telecast\b",
    r"\btv channels?\b",
    r"\bstreaming details?\b",
    r"\bplaying xi\b",
    r"\bpredicted xi\b",
    r"\bpredicted lineups?\b",
    r"\blineups? and pitch report\b",
    r"\bpitch report\b",
    r"\bscorecard\b",
    r"\bfull scorecard\b",
    r"\blive score\b",
    r"\bmatch updates?\b",
    r"\bas it happened\b",
    r"\bas-it-happened\b",
    r"\bfixtures?\b",
    r"\bschedule\b",
    r"\bstandings?\b",
    r"\bpoints table\b",
    r"\bmedal tally\b",
    r"\bwhen .* plays\b",
)

GENERIC_PATTERNS = (
    r"^\s*sports news\s*$",
    r"^\s*latest sports news\s*$",
    r"^\s*today'?s top \d+",
    r"\btop \d+ .*news\b",
    r"\bphoto gallery\b",
    r"^\s*gallery\b",
    r"\bquiz\b",
    r"\bnews roundup\b",
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
TITLE_NOISE = {
    "story", "stories", "event", "events", "update", "updates", "player",
    "players", "star", "stars", "team", "teams", "news", "report", "reports",
}

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
    if profile in {"cricket_india_asia", "cricket_global"}:
        if title_tokens & NON_CRICKET_TERMS:
            return False

        title_text = _clean(title).casefold()
        description_text = _clean(description).casefold()
        evidence_text = f"{title_text} {description_text}".strip()

        if profile == "cricket_india_asia":
            return (
                any(scope in evidence_text for scope in CRICKET_INDIA_ASIA_SCOPE)
                or any(entity in evidence_text for entity in CRICKET_INDIA_ASIA_ENTITIES)
            )

        return bool(title_tokens & CRICKET_TERMS) or any(
            name in title_text for name in CRICKET_ENTITY_NAMES
        )

    niche_terms = SPORT_WORDS - CRICKET_TERMS
    return bool(title_tokens & niche_terms) and not bool(title_tokens & CRICKET_TERMS)

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
    excluded = SPORT_WORDS | TITLE_NOISE | set().union(*EVENT_GROUPS.values())
    shared = (ta & tb) - excluded
    if len(shared) >= 2 and _event_groups(a.title) & _event_groups(b.title):
        return True

    shared_context = (ta & tb) & EVENT_CONTEXT
    shared_entities = (ta & tb) - excluded - EVENT_CONTEXT
    if len(shared_entities) >= 3 and shared_context:
        similarity = SequenceMatcher(None, _clean(a.title).casefold(), _clean(b.title).casefold()).ratio()
        if similarity >= 0.42:
            return True

    if len(shared_entities) >= 2 and len(shared_context) >= 2:
        return True
    return False


def _score(
    topic: Topic,
    profile: str | None = None,
    coverage_count: int = 1,
) -> float:
    age_hours = max(
        0.0,
        (datetime.now(timezone.utc) - topic.published_at).total_seconds() / 3600,
    )

    if profile in {None, "niche_sports"}:
        freshness = max(0.0, LOOKBACK_HOURS - age_hours) / LOOKBACK_HOURS * 5
        event_bonus = min(2.8, len(_event_groups(topic.title)) * 0.8)
        pull_bonus = min(4.0, len(_tokens(topic.title) & AUDIENCE_PULL_TERMS) * 1.0)
        distinctive = (
            _tokens(topic.title)
            - SPORT_WORDS
            - set().union(*EVENT_GROUPS.values())
            - EVENT_CONTEXT
        )
        specificity = min(2.0, max(0, len(distinctive) - 2) * 0.35)
        source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
        low_signal_penalty = (
            1.5
            if any(
                re.search(pattern, topic.title, re.IGNORECASE)
                for pattern in LOW_SIGNAL_PATTERNS
            )
            else 0.0
        )
        generic_penalty = 3.0 if _utility(topic.title) else 0.0
        return (
            freshness
            + event_bonus
            + pull_bonus
            + specificity
            - source_penalty
            - low_signal_penalty
            - generic_penalty
        )

    lookback_hours = PROFILE_LOOKBACK_HOURS.get(profile, LOOKBACK_HOURS)
    freshness_ratio = max(0.0, lookback_hours - age_hours) / lookback_hours
    freshness = 6.5 * (freshness_ratio ** 1.7)
    event_bonus = min(2.8, len(_event_groups(topic.title)) * 0.8)
    pull_bonus = min(4.5, len(_tokens(topic.title) & AUDIENCE_PULL_TERMS) * 1.0)

    viral_terms = {
        "viral", "trending", "social", "fans", "reaction", "reacts", "responds",
        "backlash", "bizarre", "unusual", "stunning", "shocking", "clash", "feud",
    }
    novelty_bonus = min(2.8, len(_tokens(topic.title) & viral_terms) * 0.7)

    distinctive = (
        _tokens(topic.title)
        - SPORT_WORDS
        - set().union(*EVENT_GROUPS.values())
        - EVENT_CONTEXT
    )
    specificity = min(2.0, max(0, len(distinctive) - 2) * 0.35)
    coverage_bonus = min(2.4, max(0, coverage_count - 1) * 0.6)
    source_penalty = 1.0 if _source_key(topic.source) in PUBLISHER_PENALTIES else 0.0
    low_signal_penalty = (
        1.5
        if any(re.search(pattern, topic.title, re.IGNORECASE) for pattern in LOW_SIGNAL_PATTERNS)
        else 0.0
    )
    generic_penalty = 3.0 if _utility(topic.title) else 0.0
    stale_penalty = (
        min(2.5, (age_hours - 36) * 0.2)
        if age_hours > 36
        else 0.0
    )

    return (
        freshness
        + event_bonus
        + pull_bonus
        + novelty_bonus
        + specificity
        + coverage_bonus
        - source_penalty
        - low_signal_penalty
        - generic_penalty
        - stale_penalty
    )

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
    lookback_hours = PROFILE_LOOKBACK_HOURS.get(profile, LOOKBACK_HOURS)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[Topic] = []
    seen_urls = {_canonical_url(url) for url in seen_urls}
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

def _entity_hits(topic: Topic) -> set[str]:
    text = _clean(topic.title).casefold()
    known = (
        CRICKET_ENTITY_NAMES
        | CRICKET_INDIA_ASIA_ENTITIES
    )
    return {entity for entity in known if entity in text}


def _select(
    rows: list[Topic],
    limit: int,
    seen_urls: set[str],
    existing: list[Topic] | None = None,
    profile: str | None = None,
) -> list[Topic]:
    if limit <= 0:
        return []

    if profile in {None, "niche_sports"}:
        ranked = sorted(
            (
                Topic(
                    r.title,
                    r.source,
                    r.published_at,
                    r.url,
                    r.description,
                    _score(r, profile=profile),
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

    blocked = list(existing or [])
    seen_canonical = {_canonical_url(url) for url in seen_urls}

    base_ranked = sorted(
        rows,
        key=lambda r: _score(r, profile=profile),
        reverse=True,
    )

    coverage_rows = base_ranked[: min(len(base_ranked), 350)]
    coverage_cache: dict[str, int] = {}
    for topic in coverage_rows:
        key = _canonical_url(topic.url)
        coverage_cache[key] = 1 + sum(
            1
            for other in coverage_rows
            if key != _canonical_url(other.url) and _same_event(topic, other)
        )

    ranked = sorted(
        (
            Topic(
                r.title,
                r.source,
                r.published_at,
                r.url,
                r.description,
                _score(
                    r,
                    profile=profile,
                    coverage_count=coverage_cache.get(_canonical_url(r.url), 1),
                ),
            )
            for r in rows
        ),
        key=lambda topic: topic.score,
        reverse=True,
    )

    chosen: list[Topic] = []
    source_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {}
    deferred: list[Topic] = []

    for topic in ranked:
        if _canonical_url(topic.url) in seen_canonical:
            continue
        if any(_same_event(topic, other) for other in blocked + chosen):
            continue

        source = _source_key(topic.source)
        if (
            source
            and source_counts.get(source, 0) >= 2
            and len(chosen) < max(1, limit // 2)
        ):
            deferred.append(topic)
            continue

        entity_hits = _entity_hits(topic)
        repeat_penalty = sum(
            0.9 * min(2, entity_counts.get(entity, 0))
            for entity in entity_hits
        )

        country_boost = 0.0
        if profile == "cricket_india_asia":
            evidence = f"{topic.title} {topic.description}".casefold()
            countries = {
                country
                for country in ("india", "pakistan", "sri lanka")
                if country in evidence
            }
            for country in countries:
                if not any(
                    country in f"{other.title} {other.description}".casefold()
                    for other in chosen
                ):
                    country_boost += 0.35

        adjusted = topic.score - min(2.7, repeat_penalty) + min(0.7, country_boost)
        adjusted_topic = Topic(
            topic.title,
            topic.source,
            topic.published_at,
            topic.url,
            topic.description,
            adjusted,
        )
        chosen.append(adjusted_topic)

        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
        for entity in entity_hits:
            entity_counts[entity] = entity_counts.get(entity, 0) + 1

        if len(chosen) >= limit:
            break

    if len(chosen) < limit:
        for topic in deferred:
            if _canonical_url(topic.url) in seen_canonical:
                continue
            if any(_same_event(topic, other) for other in blocked + chosen):
                continue
            chosen.append(topic)
            if len(chosen) >= limit:
                break

    return chosen

def _keyword_queries(profile: str, keyword: str) -> list[str]:
    keyword = _clean(keyword).replace('"', " ")
    if not keyword:
        return []

    phrase = f'"{keyword}"' if " " in keyword else keyword
    scope = '(India OR Pakistan OR "Sri Lanka") ' if profile == "cricket_india_asia" else ""

    return [
        f"{phrase} cricket {scope}(breaking OR result OR upset OR record OR milestone OR comeback OR debut OR injury) when:3d",
        f"{phrase} cricket {scope}(reacts OR responds OR reveals OR confirms OR admits OR controversy OR backlash) when:3d",
        f'{phrase} cricket {scope}(viral OR trending OR fans OR "social media" OR unusual OR bizarre OR stunning) when:3d',
        f"{phrase} cricket {scope}(selection OR retirement OR contract OR banned OR suspended OR statement) when:3d",
    ]


def _gdelt_query(profile: str, keyword: str | None = None) -> str:
    if keyword:
        scope = '(India Pakistan "Sri Lanka") ' if profile == "cricket_india_asia" else ""
        return f'"{_clean(keyword)}" cricket {scope}'
    return {
        "cricket_india_asia": '(cricket India Pakistan "Sri Lanka")',
        "cricket_global": "(cricket Australia England South Africa New Zealand West Indies international)",
        "niche_sports": "(tennis badminton F1 MotoGP athletics swimming golf boxing hockey kabaddi basketball chess)",
    }[profile]


def fetch_topics(
    profile: str = "cricket_india_asia",
    more: bool = False,
    exclude_topics: list[Topic] | None = None,
    limit: int = TARGET,
    keyword: str | None = None,
) -> list[Topic]:
    if profile not in QUERIES:
        raise ValueError(f"Unknown profile: {profile}")
    if limit <= 0:
        return []

    keyword = _clean(keyword or "")
    if keyword:
        queries = _keyword_queries(profile, keyword)
    else:
        queries = list(QUERIES[profile] if not more else MORE_QUERIES[profile])
        queries.extend(DISCOVERY_QUERIES.get(profile, []))

    existing = list(exclude_topics or [])
    seen_urls = {_canonical_url(topic.url) for topic in existing}

    rows: list[Topic] = []
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(queries)))) as pool:
        futures = [pool.submit(_fetch_google, query) for query in queries]
        for future in futures:
            try:
                rows.extend(future.result())
            except (requests.RequestException, ValueError):
                continue

    prepared = _prepare(rows, seen_urls, profile=profile)
    chosen = _select(
        prepared,
        limit,
        seen_urls,
        existing,
        profile=profile,
    )

    if len(chosen) < limit or len(prepared) < limit * 3:
        try:
            gdelt_rows = _prepare(
                _fetch_gdelt(_gdelt_query(profile, keyword)),
                seen_urls | {_canonical_url(topic.url) for topic in chosen},
                profile=profile,
            )
            chosen.extend(
                _select(
                    gdelt_rows,
                    limit - len(chosen),
                    seen_urls | {_canonical_url(topic.url) for topic in chosen},
                    existing + chosen,
                    profile=profile,
                )
            )
        except (requests.RequestException, ValueError):
            pass

    return chosen[:limit]
