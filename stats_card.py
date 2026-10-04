"""Cricket stats-card data queries and 9:16 card rendering."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
import time
import unicodedata
from typing import Any

from rapidfuzz import fuzz, process

import requests
from PIL import Image, ImageDraw, ImageFont


API_URL = "https://db-mcp.tigzig.com/v1/query/duckdb"
SOURCE_NAME = "TigZig / Cricsheet"
SOURCE_LICENSE = "ODC-BY 1.0"
WIDTH = 1080
HEIGHT = 1920
IMAGE_HEIGHT = 860
MARGIN = 64
PANEL_TOP = IMAGE_HEIGHT
PANEL_BOTTOM = HEIGHT
WHITE = (249, 250, 252)
INK = (14, 16, 20)
MUTED = (86, 91, 100)
LINE = (218, 220, 224)
ACCENT = (255, 205, 66)
BRAND_BLUE = (35, 105, 255)
REQUEST_TIMEOUT = 28
CRICSHEET_PEOPLE_URL = "https://cricsheet.org/register/people.csv"
CRICSHEET_NAMES_URL = "https://cricsheet.org/register/names.csv"
REGISTRY_TIMEOUT = 8
REGISTRY_CACHE_SECONDS = 6 * 60 * 60
PLAYER_SEARCH_LIMIT = 50


class StatsCardError(ValueError):
    """Raised when a stats-card request cannot be answered safely."""


@dataclass(frozen=True)
class StatsIntent:
    kind: str
    format_name: str
    gender: str
    player: str = ""
    team1: str = ""
    team2: str = ""
    count: int = 0


FORMAT_TABLES = {
    ("odi", "men"): "ball_by_ball_odi_men",
    ("odi", "women"): "ball_by_ball_odi_women",
    ("t20", "men"): "ball_by_ball_t20_men",
    ("t20", "women"): "ball_by_ball_t20_women",
    ("test", "men"): "ball_by_ball_test_men",
    ("test", "women"): "ball_by_ball_test_women",
    ("ipl", "men"): "ball_by_ball_ipl",
}
FORMAT_LABELS = {
    "odi": "ODI",
    "t20": "T20",
    "test": "TEST",
    "ipl": "IPL",
}
TEAM_ALIASES = {
    "ind": "India",
    "india": "India",
    "pak": "Pakistan",
    "pakistan": "Pakistan",
    "aus": "Australia",
    "australia": "Australia",
    "eng": "England",
    "england": "England",
    "sa": "South Africa",
    "rsa": "South Africa",
    "south africa": "South Africa",
    "nz": "New Zealand",
    "new zealand": "New Zealand",
    "sl": "Sri Lanka",
    "sri lanka": "Sri Lanka",
    "ban": "Bangladesh",
    "bangladesh": "Bangladesh",
    "wi": "West Indies",
    "west indies": "West Indies",
    "afg": "Afghanistan",
    "afghanistan": "Afghanistan",
    "ire": "Ireland",
    "ireland": "Ireland",
    "zim": "Zimbabwe",
    "zimbabwe": "Zimbabwe",
    "ps": "Pakistan Super League",
    "mi": "Mumbai Indians",
    "mumbai indians": "Mumbai Indians",
    "csk": "Chennai Super Kings",
    "chennai super kings": "Chennai Super Kings",
    "rcb": "Royal Challengers Bengaluru",
    "royal challengers bangalore": "Royal Challengers Bengaluru",
    "royal challengers bengaluru": "Royal Challengers Bengaluru",
    "kkr": "Kolkata Knight Riders",
    "kolkata knight riders": "Kolkata Knight Riders",
    "dc": "Delhi Capitals",
    "delhi capitals": "Delhi Capitals",
    "dd": "Delhi Capitals",
    "srh": "Sunrisers Hyderabad",
    "sunrisers hyderabad": "Sunrisers Hyderabad",
    "rr": "Rajasthan Royals",
    "rajasthan royals": "Rajasthan Royals",
    "pbks": "Punjab Kings",
    "kings xi punjab": "Punjab Kings",
    "punjab kings": "Punjab Kings",
    "gt": "Gujarat Titans",
    "lsg": "Lucknow Super Giants",
    "lucknow super giants": "Lucknow Super Giants",
}


def _normalise(value: str) -> str:
    return " ".join(str(value or "").replace("’", "'").split()).strip()


def _sql_text(value: str) -> str:
    return _normalise(value).replace("'", "''")


def _format_from_text(value: str) -> str | None:
    text = _normalise(value).casefold().replace("-", " ")
    if re.search(r"\b(?:one day|one-day|odi)\b", text):
        return "odi"
    if re.search(r"\b(?:t20i?|twenty20|twenty 20)\b", text):
        return "t20"
    if re.search(r"\b(?:test|tests)\b", text):
        return "test"
    if re.search(r"\bipl\b", text):
        return "ipl"
    return None


def _gender_from_text(value: str) -> str:
    text = _normalise(value).casefold()
    return "women" if re.search(r"\b(?:women|woman|female|womens)\b", text) else "men"


def _strip_format_words(value: str) -> str:
    text = _normalise(value)
    text = re.sub(
        r"\b(?:one[- ]day|odi|t20i?|twenty[- ]20|twenty20|test|tests|ipl)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:women|woman|female|womens)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:stats?|statistics|score|scores|runs?)\b", " ", text, flags=re.IGNORECASE)
    return _normalise(text)


def _canonical_team(value: str) -> str:
    clean = _normalise(value).strip(" '")
    return TEAM_ALIASES.get(clean.casefold(), clean.title())



DYNAMIC_GROQ_MODEL = "openai/gpt-oss-20b"

DYNAMIC_PLAYER_METRICS = (
    "matches", "innings", "runs", "average", "strike_rate", "high_score",
    "hundreds", "fifties", "not_outs", "balls_faced", "fours", "sixes",
    "ducks", "runs_per_innings", "boundary_runs",
)
DYNAMIC_H2H_METRICS = (
    "matches", "wins_team1", "wins_team2", "no_result",
    "team1_win_pct", "team2_win_pct", "first_meeting", "last_meeting",
)
DYNAMIC_DEFAULT_METRICS = {
    "player": (
        "matches", "innings", "runs", "average", "strike_rate", "high_score",
        "hundreds", "fifties", "not_outs", "fours", "sixes", "balls_faced",
    ),
    "player_last_n": (
        "innings", "runs", "average", "strike_rate", "high_score",
        "hundreds", "fifties", "not_outs", "fours", "sixes",
    ),
    "player_vs_team": (
        "matches", "innings", "runs", "average", "strike_rate", "high_score",
        "hundreds", "fifties", "not_outs", "fours", "sixes", "balls_faced",
    ),
    "h2h": (
        "matches", "wins_team1", "wins_team2", "no_result",
        "team1_win_pct", "team2_win_pct", "last_meeting",
    ),
}
DYNAMIC_METRIC_INFO = {
    "matches": ("Matches", "number of matches"),
    "innings": ("Innings", "batting innings"),
    "runs": ("Runs", "total runs"),
    "average": ("Average", "batting average"),
    "strike_rate": ("Strike rate", "runs per 100 balls"),
    "high_score": ("High score", "highest score, including not-out marker"),
    "hundreds": ("100s", "innings of 100 or more"),
    "fifties": ("50s", "innings from 50 to 99"),
    "not_outs": ("Not outs", "innings not dismissed"),
    "balls_faced": ("Balls faced", "legal balls faced using the existing database rule"),
    "fours": ("4s", "fours hit"),
    "sixes": ("6s", "sixes hit"),
    "ducks": ("Ducks", "completed innings scoring zero"),
    "runs_per_innings": ("Runs / innings", "average runs per batting innings"),
    "boundary_runs": ("Boundary runs", "runs from fours and sixes"),
    "wins_team1": ("Team 1 wins", "wins by the first named team"),
    "wins_team2": ("Team 2 wins", "wins by the second named team"),
    "no_result": ("Other / no result", "matches not won by either named team"),
    "team1_win_pct": ("Team 1 win %", "first team's share of H2H matches"),
    "team2_win_pct": ("Team 2 win %", "second team's share of H2H matches"),
    "first_meeting": ("First meeting", "date of the earliest H2H meeting"),
    "last_meeting": ("Last meeting", "date of the latest H2H meeting"),
}
DYNAMIC_SCHEMA = {
    "type": "object",
    "properties": {
        "ready": {"type": "boolean"},
        "message": {"type": "string"},
        "scope": {"type": "string", "enum": ["player", "player_last_n", "player_vs_team", "h2h"]},
        "format": {"type": "string", "enum": ["odi", "t20", "test", "ipl"]},
        "gender": {"type": "string", "enum": ["men", "women"]},
        "player": {"type": "string"},
        "opponent_team": {"type": "string"},
        "team1": {"type": "string"},
        "team2": {"type": "string"},
        "count": {"type": "integer", "minimum": 0, "maximum": 20},
        "metrics": {
            "type": "array", "minItems": 1, "maxItems": 12,
            "items": {"type": "string", "enum": list(DYNAMIC_PLAYER_METRICS)},
        },
        "detail_table": {"type": "string", "enum": ["none", "innings", "meetings"]},
        "detail_limit": {"type": "integer", "minimum": 0, "maximum": 20},
    },
    "required": [
        "ready", "message", "scope", "format", "gender", "player", "opponent_team",
        "team1", "team2", "count", "metrics", "detail_table", "detail_limit",
    ],
    "additionalProperties": False,
}

def _dynamic_planner_prompt() -> str:
    metric_lines = "\n".join(
        f"- {metric_id}: {label} — {description}"
        for metric_id, (label, description) in DYNAMIC_METRIC_INFO.items()
    )
    return """You are the stats-query planner for a human-reviewed cricket YouTube Shorts factory.

Your job is ONLY to interpret the user's natural-language request into the supplied JSON schema.
The database is the source of truth. Never invent numbers and never write SQL.

INTERPRETATION
- The user may be vague. Infer the intended cricket stats when the request is reasonably clear.
- Default to ODI and men when the user does not specify another format or gender.
- Use player scope for general career/format stats.
- Use player_last_n for last/latest N innings, recent scores, or recent form.
- Use player_vs_team for a player against/vs a named team.
- Use h2h for two teams against each other, including record, wins, head-to-head, or meetings.
- Resolve common team abbreviations when obvious.
- Count is the requested innings/meeting count, 1-20 when present.
- For a broad stats request, choose the richest useful metric set that fits one 1080x1920 card, rather than returning only one or two stats.
- For explicit metrics, include them and add only closely relevant context metrics if there is room.
- For player_last_n, prefer detail_table=innings.
- For h2h, use detail_table=meetings when recent/last meetings are requested.
- Bowling, fielding, unsupported team score totals, and any metric not listed below are unsupported.

WHEN UNCLEAR OR UNSUPPORTED
- Set ready=false.
- Put the exact user-facing re-query instruction in message.
- Do not guess a missing player/team, incompatible scope, or unsupported metric.
- Keep message concise and immediately actionable.

METRICS
""" + metric_lines + """

Return only JSON matching the supplied schema.
"""

def _plan_dynamic_stats(query: str) -> dict[str, Any]:
    clean = _normalise(query)
    if not clean:
        raise StatsCardError("Enter a stats query.")

    key = _normalise(os.getenv("GROQ_API_KEY"))
    if not key:
        raise StatsCardError("GROQ_API_KEY is not configured.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": DYNAMIC_GROQ_MODEL,
            "messages": [
                {"role": "system", "content": _dynamic_planner_prompt()},
                {"role": "user", "content": clean},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "dynamic_stats_query", "strict": True, "schema": DYNAMIC_SCHEMA},
            },
            "include_reasoning": False,
            "reasoning_effort": "low",
            "temperature": 0.1,
            "max_completion_tokens": 700,
        },
        timeout=REQUEST_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise StatsCardError("Stats query research failed. Try a different query.") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
        plan = content if isinstance(content, dict) else json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise StatsCardError("Stats query research returned an unreadable plan. Try a different query.") from exc

    if not isinstance(plan, dict):
        raise StatsCardError("Stats query research returned an unreadable plan. Try a different query.")

    if not bool(plan.get("ready")):
        message = str(plan.get("message") or "").strip()
        raise StatsCardError(message or "The stats query needs more detail. Try a different query.")

    scope = str(plan.get("scope") or "").strip()
    format_name = str(plan.get("format") or "").strip().lower()
    gender = str(plan.get("gender") or "").strip().lower()
    if scope not in DYNAMIC_DEFAULT_METRICS or format_name not in FORMAT_LABELS or gender not in {"men", "women"}:
        raise StatsCardError("The stats planner returned an invalid request. Try a different query.")

    metrics = []
    allowed = set(DYNAMIC_H2H_METRICS if scope == "h2h" else DYNAMIC_PLAYER_METRICS)
    for metric in plan.get("metrics") or ():
        metric_id = str(metric or "").strip()
        if metric_id in allowed and metric_id not in metrics:
            metrics.append(metric_id)
    if not metrics:
        metrics = list(DYNAMIC_DEFAULT_METRICS[scope])

    detail_table = str(plan.get("detail_table") or "none").strip()
    detail_limit = max(0, min(20, int(plan.get("detail_limit") or 0)))
    count = max(0, min(20, int(plan.get("count") or 0)))

    if scope == "player_last_n":
        count = count or 10
        detail_table = "innings" if detail_table == "none" else detail_table
        if detail_table != "innings":
            raise StatsCardError("Last-innings requests need an innings detail table. Try a different query.")
        detail_limit = detail_limit or count
        plan["player"] = _normalise(plan.get("player") or "")
        if not plan["player"]:
            raise StatsCardError("Please include the player name and try again.")
        plan["opponent_team"] = ""
    elif scope == "player":
        plan["player"] = _normalise(plan.get("player") or "")
        if not plan["player"]:
            raise StatsCardError("Please include the player name and try again.")
        plan["opponent_team"] = ""
    elif scope == "player_vs_team":
        plan["player"] = _normalise(plan.get("player") or "")
        plan["opponent_team"] = _canonical_team(plan.get("opponent_team") or "")
        if not plan["player"] or not plan["opponent_team"]:
            raise StatsCardError("Please include both the player and opponent team and try again.")
    else:
        plan["player"] = ""
        plan["team1"] = _canonical_team(plan.get("team1") or "")
        plan["team2"] = _canonical_team(plan.get("team2") or "")
        if not plan["team1"] or not plan["team2"] or plan["team1"].casefold() == plan["team2"].casefold():
            raise StatsCardError("Please include two different teams for head-to-head stats and try again.")
        plan["opponent_team"] = ""

    plan["metrics"] = metrics[:12]
    plan["count"] = count
    plan["detail_table"] = detail_table
    plan["detail_limit"] = min(20, detail_limit)
    return plan

def _parse_query(query: str) -> StatsIntent:
    clean = _normalise(query)
    if not clean:
        raise StatsCardError("Enter a stats query.")

    format_name = _format_from_text(clean) or "odi"
    gender = _gender_from_text(clean)

    h2h = re.match(
        r"^(.+?)\s+(?:vs\.?|v\.?|versus)\s+(.+?)\s+"
        r"(?:h2h|head[- ]to[- ]head)(?:\s+stats?)?\s*$",
        clean,
        flags=re.IGNORECASE,
    )
    if h2h:
        team1 = _strip_format_words(h2h.group(1))
        team2 = _strip_format_words(h2h.group(2))
        if not team1 or not team2:
            raise StatsCardError("H2H queries need two teams, for example: India vs Pakistan H2H stats.")
        return StatsIntent(
            kind="h2h",
            format_name=format_name,
            gender=gender,
            team1=_canonical_team(team1),
            team2=_canonical_team(team2),
        )

    last_n = re.search(
        r"^(.+?)(?:['’]s)?\s+(?:last|latest)\s+(\d{1,2})\s+"
        r"(?:completed\s+)?innings?(?:\s+scores?)?(?:\s+stats?)?\s*$",
        clean,
        flags=re.IGNORECASE,
    )
    if last_n:
        count = max(1, min(20, int(last_n.group(2))))
        player = _strip_format_words(last_n.group(1).rstrip("'"))
        if not player:
            raise StatsCardError("Last-innings queries need a player name.")
        return StatsIntent(
            kind="last_n",
            format_name=format_name,
            gender=gender,
            player=player,
            count=count,
        )

    player = _strip_format_words(clean)
    if player.casefold().endswith("'s"):
        player = player[:-2].rstrip()
    if not player:
        raise StatsCardError(
            "Use a query like 'MS Dhoni ODI stats', 'India vs Pakistan H2H stats', or 'Virat Kohli last 10 innings scores'."
        )
    return StatsIntent(
        kind="career",
        format_name=format_name,
        gender=gender,
        player=player,
    )


def _query(sql: str) -> list[dict[str, Any]]:
    try:
        response = requests.post(
            API_URL,
            json={"sql": sql, "format": "json"},
            headers={"Content-Type": "application/json", "User-Agent": "Final-Shorts/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise StatsCardError("Stats database could not be reached. Try again.") from exc

    if response.status_code != 200:
        detail = response.text.strip()
        raise StatsCardError(
            f"Stats database request failed ({response.status_code})."
            + (f" {detail[:240]}" if detail else "")
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise StatsCardError("Stats database returned invalid JSON.") from exc

    while isinstance(payload, dict):
        columns = payload.get("columns") or payload.get("column_names")
        for key in ("rows", "data", "results", "values"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            if not rows:
                return []
            if isinstance(rows[0], dict):
                return [dict(item) for item in rows]
            if isinstance(columns, list) and all(
                isinstance(row, (list, tuple)) for row in rows
            ):
                return [dict(zip(columns, row)) for row in rows]

        nested = payload.get("result")
        if isinstance(nested, dict):
            payload = nested
            continue
        raise StatsCardError("Stats database returned an unexpected response.")

    if not isinstance(payload, list):
        raise StatsCardError("Stats database returned an unexpected response.")
    if not payload:
        return []
    if isinstance(payload[0], dict):
        return [dict(item) for item in payload]
    raise StatsCardError("Stats database returned rows without column names.")



def _name_key(value: str) -> str:
    """Normalize a user/registry name for safe comparison."""
    text = unicodedata.normalize("NFKD", _normalise(value)).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(
        "".join(char if char.isalnum() else " " for char in text).split()
    )


def _initial_name_keys(value: str) -> set[str]:
    tokens = _name_key(value).split()
    if len(tokens) < 2:
        return set()

    first_initial = tokens[0][0]
    keys = {f"{first_initial} {tokens[-1]}"}
    if len(tokens) >= 3:
        keys.add(f"{first_initial} {' '.join(tokens[-2:])}")
    return keys


def _registry_cache_bucket() -> int:
    return int(time.time() // REGISTRY_CACHE_SECONDS)


@lru_cache(maxsize=4)
def _cricsheet_registry(
    cache_bucket: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    """Load Cricsheet's stable people IDs and published name variants."""
    people: dict[str, dict[str, Any]] = {}
    aliases: dict[str, set[str]] = {}

    people_response = requests.get(
        CRICSHEET_PEOPLE_URL,
        headers={"User-Agent": "Final-Shorts/1.0"},
        timeout=REGISTRY_TIMEOUT,
    )
    people_response.raise_for_status()
    for row in csv.DictReader(
        people_response.text.lstrip("\ufeff").splitlines()
    ):
        identifier = _normalise(row.get("identifier") or "")
        if not identifier:
            continue
        people[identifier] = {
            "identifier": identifier,
            "name": _normalise(row.get("name") or ""),
            "unique_name": _normalise(row.get("unique_name") or ""),
            "aliases": set(),
        }

    names_response = requests.get(
        CRICSHEET_NAMES_URL,
        headers={"User-Agent": "Final-Shorts/1.0"},
        timeout=REGISTRY_TIMEOUT,
    )
    names_response.raise_for_status()
    for row in csv.DictReader(
        names_response.text.lstrip("\ufeff").splitlines()
    ):
        identifier = _normalise(row.get("identifier") or "")
        alias = _normalise(row.get("name") or "")
        if identifier not in people or not alias:
            continue
        people[identifier]["aliases"].add(alias)
        key = _name_key(alias)
        if key:
            aliases.setdefault(key, set()).add(identifier)

    for identifier, person in people.items():
        for name in (person["name"], person["unique_name"]):
            if not name:
                continue
            person["aliases"].add(name)
            key = _name_key(name)
            if key:
                aliases.setdefault(key, set()).add(identifier)

    return people, aliases


def _candidate_from_registry(
    people: dict[str, dict[str, Any]],
    identifier: str,
) -> dict[str, Any] | None:
    person = people.get(identifier)
    if not person:
        return None

    unique_name = _normalise(person.get("unique_name") or "")
    if not unique_name:
        return None

    return {
        "identifier": identifier,
        "name": _normalise(person.get("name") or unique_name),
        "unique_name": unique_name,
        "aliases": {
            _normalise(alias)
            for alias in (person.get("aliases") or ())
            if _normalise(alias)
        },
    }


def _fallback_people_candidates(intent: StatsIntent) -> list[dict[str, Any]]:
    """Use TigZig's player registry if Cricsheet's registry is unavailable."""
    needle = _sql_text(intent.player)
    tokens = _name_key(intent.player).split()
    conditions = [
        f"lower(name) = lower('{needle}')",
        f"lower(unique_name) = lower('{needle}')",
    ]

    if len(tokens) == 1:
        conditions.extend(
            [
                f"lower(name) LIKE lower('%{needle}%')",
                f"lower(unique_name) LIKE lower('%{needle}%')",
            ]
        )
    elif len(tokens) >= 2:
        initial = _sql_text(tokens[0][0])
        surname = _sql_text(tokens[-1])
        conditions.extend(
            [
                f"lower(name) LIKE lower('{initial}% {surname}')",
                f"lower(unique_name) LIKE lower('{initial}% {surname}')",
                f"lower(name) LIKE lower('% {surname}')",
                f"lower(unique_name) LIKE lower('% {surname}')",
            ]
        )

    rows = _query(
        "SELECT identifier, name, unique_name "
        "FROM people WHERE "
        + " OR ".join(conditions)
        + f" ORDER BY name LIMIT {PLAYER_SEARCH_LIMIT}"
    )

    candidates: list[dict[str, Any]] = []
    for row in rows:
        name = _normalise(row.get("name") or "")
        unique_name = _normalise(row.get("unique_name") or "")
        identifier = _normalise(row.get("identifier") or "")
        if not identifier or not unique_name:
            continue
        candidates.append(
            {
                "identifier": identifier,
                "name": name or unique_name,
                "unique_name": unique_name,
                "aliases": {value for value in (name, unique_name) if value},
            }
        )
    return candidates


def _filter_candidates_by_format(
    candidates: list[dict[str, Any]],
    intent: StatsIntent,
) -> list[dict[str, Any]]:
    table = FORMAT_TABLES.get((intent.format_name, intent.gender))
    if not table:
        return []

    names = list(
        dict.fromkeys(
            _normalise(candidate.get("unique_name") or "")
            for candidate in candidates
            if _normalise(candidate.get("unique_name") or "")
        )
    )
    if not names:
        return []

    literals = ", ".join(f"lower('{_sql_text(name)}')" for name in names)
    rows = _query(
        f"SELECT lower(striker) AS striker FROM {table} "
        f"WHERE lower(striker) IN ({literals}) "
        "GROUP BY lower(striker)"
    )
    present = {
        _normalise(row.get("striker") or "").casefold()
        for row in rows
    }
    return [
        candidate
        for candidate in candidates
        if _normalise(candidate.get("unique_name") or "").casefold() in present
    ]


def _fuzzy_registry_candidates(intent: StatsIntent) -> list[dict[str, Any]]:
    try:
        people, aliases = _cricsheet_registry(_registry_cache_bucket())
    except (requests.RequestException, OSError, ValueError):
        return []

    query_key = _name_key(intent.player)
    if not query_key:
        return []

    matches = process.extract(
        query_key,
        list(aliases),
        scorer=fuzz.WRatio,
        limit=8,
        score_cutoff=90,
    )
    if not matches:
        return []

    best_score = float(matches[0][1])
    identifiers = {
        identifier
        for alias_key, score, _ in matches
        if best_score - float(score) < 4
        for identifier in aliases.get(alias_key, set())
    }
    if len(identifiers) != 1:
        return []

    candidate = _candidate_from_registry(people, next(iter(identifiers)))
    return [candidate] if candidate else []


def _resolve_player(intent: StatsIntent) -> dict[str, Any]:
    """Resolve a human name to one stable person and its match-data names."""
    query_key = _name_key(intent.player)
    candidates: list[dict[str, Any]] = []

    try:
        people, aliases = _cricsheet_registry(_registry_cache_bucket())
        identifiers = set(aliases.get(query_key, set()))

        if not identifiers:
            identifiers = {
                identifier
                for key in _initial_name_keys(intent.player)
                for identifier in aliases.get(key, set())
            }

        if not identifiers and len(query_key.split()) == 1:
            identifiers = {
                identifier
                for key, key_identifiers in aliases.items()
                if query_key in key.split()
                for identifier in key_identifiers
            }

        for identifier in sorted(identifiers):
            candidate = _candidate_from_registry(people, identifier)
            if candidate:
                candidates.append(candidate)

        if not candidates:
            candidates = _fallback_people_candidates(intent)
    except (requests.RequestException, OSError, ValueError):
        candidates = _fallback_people_candidates(intent)

    if not candidates:
        candidates = _fuzzy_registry_candidates(intent)

    if not candidates:
        raise StatsCardError(
            f"Could not find player '{intent.player}' in the cricket database."
        )

    exact = [
        candidate
        for candidate in candidates
        if query_key
        in {
            _name_key(candidate.get("name") or ""),
            _name_key(candidate.get("unique_name") or ""),
            *{
                _name_key(alias)
                for alias in (candidate.get("aliases") or ())
                if alias
            },
        }
    ]
    if exact:
        candidates = exact

    if len(candidates) > 1:
        format_candidates = _filter_candidates_by_format(candidates, intent)
        if len(format_candidates) == 1:
            candidates = format_candidates

    if len(candidates) > 1:
        names = list(
            dict.fromkeys(
                _normalise(candidate.get("name") or candidate.get("unique_name") or "")
                for candidate in candidates
            )
        )
        names = [name for name in names if name]
        raise StatsCardError(
            "Player query is ambiguous. Use the full player name."
            + (f" Matches: {', '.join(names[:5])}." if names else "")
        )

    candidate = candidates[0]
    unique_name = _normalise(candidate.get("unique_name") or "")
    if not unique_name:
        raise StatsCardError("The matched player has no usable database identifier.")

    display_name = _normalise(candidate.get("name") or unique_name)
    matched_aliases = sorted(
        (
            _normalise(alias)
            for alias in (candidate.get("aliases") or ())
            if _name_key(alias) == query_key
        ),
        key=lambda value: (bool(re.search(r"[^A-Za-z0-9 ]", value)), -len(value), value.casefold()),
    )
    if matched_aliases:
        display_name = matched_aliases[0]
    return {
        "identifier": _normalise(candidate.get("identifier") or ""),
        "name": display_name,
        "unique_name": unique_name,
    }

def _innings_limit(format_name: str) -> int:
    return 4 if format_name == "test" else 2


def _player_rows(intent: StatsIntent, player: dict[str, Any]) -> list[dict[str, Any]]:
    table = FORMAT_TABLES.get((intent.format_name, intent.gender))
    if not table:
        raise StatsCardError(
            "That format/gender combination is not available in the stats database."
        )

    unique_name = _normalise(player.get("unique_name") or "")
    if not unique_name:
        raise StatsCardError("The matched player has no usable database name.")

    innings_limit = _innings_limit(intent.format_name)
    sql = (
        "SELECT b.match_id, b.start_date, b.innings, b.batting_team, b.bowling_team, "
        "b.striker, SUM(b.runs_off_bat) AS runs, "
        "COUNT(*) FILTER (WHERE b.wides IS NULL) AS balls_faced, "
        "MAX(CASE WHEN lower(b.player_dismissed) = lower(b.striker) THEN 1 ELSE 0 END) AS dismissed "
        f"FROM {table} b "
        f"WHERE lower(b.striker) = lower('{_sql_text(unique_name)}') "
        f"AND b.innings <= {innings_limit} "
        "GROUP BY b.match_id, b.start_date, b.innings, b.batting_team, "
        "b.bowling_team, b.striker "
        "ORDER BY b.start_date DESC, b.match_id DESC, b.innings DESC"
    )
    return _query(sql)

def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _date_value(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _date_label(value: Any) -> str:
    parsed = _date_value(value)
    return parsed.strftime("%d %b %Y") if parsed else _normalise(str(value))[:20]


def _career_stats(intent: StatsIntent, player: dict[str, Any]) -> dict[str, Any]:
    rows = _player_rows(intent, player)
    if not rows:
        raise StatsCardError(
            f"No {FORMAT_LABELS[intent.format_name]} batting data was found for {player['name']}."
        )

    innings = []
    for row in rows:
        runs = _to_int(row.get("runs"))
        dismissed = _to_int(row.get("dismissed")) == 1
        balls = _to_int(row.get("balls_faced"))
        batting_team = _normalise(row.get("batting_team") or "")
        innings.append({
            "date": row.get("start_date"),
            "opponent": _normalise(row.get("bowling_team") or ""),
            "team": batting_team,
            "runs": runs,
            "balls": balls,
            "dismissed": dismissed,
            "score": f"{runs}" + ("" if dismissed else "*"),
        })

    matches = len({str(row.get("match_id")) for row in rows})
    total_runs = sum(item["runs"] for item in innings)
    outs = sum(1 for item in innings if item["dismissed"])
    balls = sum(item["balls"] for item in innings)
    average = total_runs / outs if outs else None
    strike_rate = total_runs * 100 / balls if balls else None
    high_score = max(item["runs"] for item in innings)
    high_rows = [item for item in innings if item["runs"] == high_score]
    high_score_mark = f"{high_score}{'' if all(item['dismissed'] for item in high_rows) else '*'}"
    centuries = sum(1 for item in innings if item["runs"] >= 100)
    fifties = sum(1 for item in innings if 50 <= item["runs"] < 100)
    dates = [parsed for item in innings if (parsed := _date_value(item["date"])) is not None]
    team_counts: dict[str, int] = {}
    for item in innings:
        if item["team"]:
            team_counts[item["team"]] = team_counts.get(item["team"], 0) + 1
    team = max(team_counts, key=team_counts.get) if team_counts else ""

    return {
        "player": player["name"],
        "format": FORMAT_LABELS[intent.format_name],
        "gender": intent.gender,
        "team": team,
        "matches": matches,
        "innings": len(innings),
        "runs": total_runs,
        "average": average,
        "strike_rate": strike_rate,
        "high_score": high_score_mark,
        "hundreds": centuries,
        "fifties": fifties,
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "innings_rows": innings,
    }


def _last_n_stats(intent: StatsIntent, player: dict[str, Any]) -> dict[str, Any]:
    stats = _career_stats(intent, player)
    innings = stats["innings_rows"][: intent.count]
    if not innings:
        raise StatsCardError(
            f"No completed batting innings were found for {player['name']}."
        )

    total_runs = sum(item["runs"] for item in innings)
    outs = sum(1 for item in innings if item["dismissed"])
    average = total_runs / outs if outs else None
    centuries = sum(1 for item in innings if item["runs"] >= 100)
    fifties = sum(1 for item in innings if 50 <= item["runs"] < 100)
    dates = [parsed for item in innings if (parsed := _date_value(item["date"])) is not None]
    return {
        "player": player["name"],
        "format": FORMAT_LABELS[intent.format_name],
        "gender": intent.gender,
        "count_requested": intent.count,
        "count_available": len(innings),
        "runs": total_runs,
        "average": average,
        "hundreds": centuries,
        "fifties": fifties,
        "last_date": max(dates) if dates else None,
        "innings": innings,
    }


def _h2h_stats(intent: StatsIntent) -> dict[str, Any]:
    team1 = _sql_text(intent.team1)
    team2 = _sql_text(intent.team2)
    match_type = {
        "odi": "ODI",
        "t20": "T20",
        "test": "TEST",
        "ipl": "IPL",
    }[intent.format_name]
    gender_value = "female" if intent.gender == "women" else "male"
    sql = (
        "SELECT match_id, start_date, team1, team2, winner "
        "FROM match_info "
        f"WHERE match_type = '{match_type}' "
        f"AND gender = '{gender_value}' "
        f"AND ((lower(team1) = lower('{team1}') AND lower(team2) = lower('{team2}')) "
        f"OR (lower(team1) = lower('{team2}') AND lower(team2) = lower('{team1}'))) "
        "ORDER BY start_date DESC, match_id DESC"
    )
    rows = _query(sql)
    if not rows:
        raise StatsCardError(
            f"No {FORMAT_LABELS[intent.format_name]} H2H matches were found for {intent.team1} vs {intent.team2}."
        )

    wins1 = 0
    wins2 = 0
    other = 0
    for row in rows:
        winner = _normalise(row.get("winner") or "")
        if winner.casefold() == intent.team1.casefold():
            wins1 += 1
        elif winner.casefold() == intent.team2.casefold():
            wins2 += 1
        else:
            other += 1

    dates = [parsed for row in rows if (parsed := _date_value(row.get("start_date"))) is not None]
    return {
        "team1": intent.team1,
        "team2": intent.team2,
        "format": FORMAT_LABELS[intent.format_name],
        "gender": intent.gender,
        "matches": len(rows),
        "wins1": wins1,
        "wins2": wins2,
        "other": other,
        "first_date": min(dates) if dates else None,
        "latest_date": max(dates) if dates else None,
    }


@lru_cache(maxsize=128)
def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    root = Path(__file__).resolve().parent / "fonts"
    candidates = [
        root / "Oswald-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/seguisb.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    if not bold:
        candidates = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ] + candidates
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    source = image.convert("RGB")
    source_ratio = source.width / source.height
    target_ratio = target_w / target_h
    if source_ratio > target_ratio:
        crop_w = max(1, int(source.height * target_ratio))
        left = (source.width - crop_w) // 2
        source = source.crop((left, 0, left + crop_w, source.height))
    else:
        crop_h = max(1, int(source.width / target_ratio))
        top = (source.height - crop_h) // 2
        source = source.crop((0, top, source.width, top + crop_h))
    return source.resize(size, Image.Resampling.LANCZOS)


def build_stats_card_preview(source_image: bytes | bytearray | Image.Image) -> bytes:
    """Render the selected Manual QC image in its final card frame with an empty stats panel."""
    base = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    image = _fit_cover(_asset_image(source_image), (WIDTH, IMAGE_HEIGHT))
    base.paste(image, (0, 0))
    draw = ImageDraw.Draw(base)
    draw.rectangle((0, PANEL_TOP, WIDTH, PANEL_BOTTOM), fill=(246, 247, 249))

    buffer = BytesIO()
    base.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _wrap_words(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = _normalise(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if current and width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_size: int,
    min_size: int = 26,
    max_lines: int = 2,
) -> tuple[ImageFont.ImageFont, list[str]]:
    for size in range(max_size, min_size - 1, -2):
        font = _font(size)
        lines = _wrap_words(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    raise StatsCardError("Stats-card text is too long to fit cleanly.")


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    center_x: int,
    top: int,
    fill: tuple[int, int, int],
    gap: int = 4,
) -> int:
    y = top
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        width = box[2] - box[0]
        height = box[3] - box[1]
        draw.text((center_x - width / 2, y), line, font=font, fill=fill)
        y += height + gap
    return y


def _draw_metric_tiles(
    draw: ImageDraw.ImageDraw,
    metrics: list[tuple[str, str]],
    top: int,
    columns: int = 3,
    tile_height: int = 132,
) -> int:
    gap = 18
    available = WIDTH - (MARGIN * 2)
    tile_width = (available - gap * (columns - 1)) // columns
    label_font = _font(21)
    value_font = _font(50)

    for row_index in range((len(metrics) + columns - 1) // columns):
        row = metrics[row_index * columns:(row_index + 1) * columns]
        y = top + row_index * (tile_height + gap)
        for col_index, (label, value) in enumerate(row):
            x = MARGIN + col_index * (tile_width + gap)
            draw.rounded_rectangle(
                (x, y, x + tile_width, y + tile_height),
                radius=18,
                fill=(255, 255, 255),
                outline=LINE,
                width=2,
            )
            label_lines = _wrap_words(draw, str(label).upper(), label_font, tile_width - 36)
            label_y = y + 16
            for label_line in label_lines[:2]:
                box = draw.textbbox((0, 0), label_line, font=label_font)
                draw.text(
                    (x + (tile_width - (box[2] - box[0])) / 2, label_y),
                    label_line,
                    font=label_font,
                    fill=MUTED,
                )
                label_y += box[3] - box[1] + 2

            value_text = str(value)
            value_font_for_tile = value_font
            while value_font_for_tile.size > 34:
                box = draw.textbbox((0, 0), value_text, font=value_font_for_tile)
                if box[2] - box[0] <= tile_width - 32:
                    break
                value_font_for_tile = _font(value_font_for_tile.size - 2)
            box = draw.textbbox((0, 0), value_text, font=value_font_for_tile)
            value_width = box[2] - box[0]
            value_height = box[3] - box[1]
            draw.text(
                (x + (tile_width - value_width) / 2, y + tile_height - value_height - 16),
                value_text,
                font=value_font_for_tile,
                fill=INK,
            )

    rows = (len(metrics) + columns - 1) // columns
    return top + rows * tile_height + max(0, rows - 1) * gap

def _draw_header(
    image: Image.Image,
    title: str,
    context: list[str],
) -> int:
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, PANEL_TOP, WIDTH, PANEL_BOTTOM), fill=(246, 247, 249))

    eyebrow_text = str(context[0] or "STATS") if context else "STATS"
    eyebrow_font = _font(22)
    draw.text((MARGIN, PANEL_TOP + 38), eyebrow_text.upper(), font=eyebrow_font, fill=BRAND_BLUE)

    title_font, title_lines = _fit_text(
        draw,
        title.upper(),
        WIDTH - (MARGIN * 2),
        70,
        min_size=46,
        max_lines=2,
    )
    y = PANEL_TOP + 80
    y = _draw_centered_lines(draw, title_lines, title_font, WIDTH // 2, y, INK, gap=4)

    body_font = _font(23, bold=False)
    # Keep the metadata deliberately compact: two lines maximum, always above the divider.
    for line in context[1:3]:
        wrapped = _wrap_words(draw, line, body_font, WIDTH - (MARGIN * 2))
        y = _draw_centered_lines(draw, wrapped, body_font, WIDTH // 2, y + 5, MUTED, gap=2)

    draw.line((MARGIN, y + 14, WIDTH - MARGIN, y + 14), fill=LINE, width=2)
    return y + 30

def _draw_attribution(draw: ImageDraw.ImageDraw) -> None:
    text = f"Source: {SOURCE_NAME} · {SOURCE_LICENSE}"
    font = _font(20, bold=False)
    draw.text((MARGIN, HEIGHT - 44), text, font=font, fill=MUTED)


def _draw_image_header(base: Image.Image, source_image: bytes | bytearray | Image.Image) -> None:
    image = _fit_cover(_asset_image(source_image), (WIDTH, IMAGE_HEIGHT))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        (0, IMAGE_HEIGHT - 230, WIDTH, IMAGE_HEIGHT),
        fill=(0, 0, 0, 125),
    )
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    base.paste(image, (0, 0))
    draw = ImageDraw.Draw(base)
    draw.text((MARGIN, 34), "STATS CARD", font=_font(24), fill=WHITE)


def _asset_image(value: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    if isinstance(value, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(value))) as source:
                return source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise StatsCardError("The selected player image could not be opened.") from exc
    raise StatsCardError("The selected player image is missing.")


def _career_card(stats: dict[str, Any], source_image: Any) -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    _draw_image_header(base, source_image)
    context = [
        f"{stats['format']} · {stats['team'] or 'Team not recorded'} · CAREER",
        f"{stats['matches']} matches · {stats['innings']} batting innings",
    ]
    if stats["first_date"] and stats["last_date"]:
        context.append(
            f"{stats['first_date'].strftime('%d %b %Y')} – {stats['last_date'].strftime('%d %b %Y')}"
        )
    y = _draw_header(base, f"{stats['player']} {stats['format']} stats", context)
    metrics = [
        ("Runs", f"{stats['runs']:,}"),
        ("Average", f"{stats['average']:.2f}" if stats["average"] is not None else "—"),
        ("Strike rate", f"{stats['strike_rate']:.2f}" if stats["strike_rate"] is not None else "—"),
        ("High score", stats["high_score"]),
        ("100s", str(stats["hundreds"])),
        ("50s", str(stats["fifties"])),
    ]
    _draw_metric_tiles(ImageDraw.Draw(base), metrics, y + 12)
    _draw_attribution(ImageDraw.Draw(base))
    return base


def _h2h_card(stats: dict[str, Any], source_image: Any) -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    _draw_image_header(base, source_image)
    context = [
        f"{stats['format']} · HEAD-TO-HEAD · {stats['matches']} matches",
        f"Date range: {_date_label(stats['first_date'])} – {_date_label(stats['latest_date'])}",
    ]
    y = _draw_header(
        base,
        f"{stats['team1']} vs {stats['team2']}",
        context,
    )
    metrics = [
        ("Matches", str(stats["matches"])),
        (f"{stats['team1']} wins", str(stats["wins1"])),
        (f"{stats['team2']} wins", str(stats["wins2"])),
        ("Other / no result", str(stats["other"])),
    ]
    _draw_metric_tiles(ImageDraw.Draw(base), metrics, y + 12, columns=2, tile_height=150)
    _draw_attribution(ImageDraw.Draw(base))
    return base


def _last_n_card(stats: dict[str, Any], source_image: Any) -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    _draw_image_header(base, source_image)
    draw = ImageDraw.Draw(base)

    count_available = int(stats["count_available"])
    count_requested = int(stats["count_requested"])
    context = [
        f"{count_available} completed innings shown"
        + (
            f" · {count_requested - count_available} fewer than requested"
            if count_available < count_requested
            else ""
        ),
        f"Stats through {_date_label(stats['last_date'])}",
    ]
    y = _draw_header(
        base,
        f"{stats['player']} · last {count_requested} innings",
        context,
    )

    # Put the compact summary before the table so 20 innings still fit cleanly.
    metrics = [
        ("Runs", f"{stats['runs']:,}"),
        ("Average", f"{stats['average']:.2f}" if stats["average"] is not None else "—"),
        ("100s", str(stats["hundreds"])),
        ("50s", str(stats["fifties"])),
    ]
    metrics_bottom = _draw_metric_tiles(
        draw,
        metrics,
        y + 10,
        columns=4,
        tile_height=104,
    )

    table_top = metrics_bottom + 28
    table_header_font = _font(19)
    draw.text((MARGIN, table_top), "RECENT INNINGS", font=table_header_font, fill=BRAND_BLUE)
    header_y = table_top + 30
    small_font = _font(17, bold=False)
    draw.text((MARGIN, header_y), "DATE · OPPONENT", font=small_font, fill=MUTED)
    score_header = "SCORE"
    score_box = draw.textbbox((0, 0), score_header, font=small_font)
    draw.text(
        (WIDTH - MARGIN - (score_box[2] - score_box[0]), header_y),
        score_header,
        font=small_font,
        fill=MUTED,
    )

    gap = 18
    column_width = (WIDTH - (MARGIN * 2) - gap) // 2
    rows_per_column = max(1, (len(stats["innings"]) + 1) // 2)
    dense = len(stats["innings"]) > 10
    row_height = 43 if dense else 52
    row_gap = 3 if dense else 5
    body_font = _font(22 if dense else 25)
    score_font = _font(27 if dense else 30)
    table_rows_top = header_y + 26

    for column in range(2):
        column_rows = stats["innings"][
            column * rows_per_column:(column + 1) * rows_per_column
        ]
        x = MARGIN + column * (column_width + gap)
        for row_index, row in enumerate(column_rows):
            row_y = table_rows_top + row_index * (row_height + row_gap)
            draw.rounded_rectangle(
                (x, row_y, x + column_width, row_y + row_height),
                radius=12,
                fill=(255, 255, 255),
                outline=LINE,
                width=1,
            )
            score = str(row.get("score") or "—")
            score_box = draw.textbbox((0, 0), score, font=score_font)
            score_width = score_box[2] - score_box[0]
            draw.text(
                (x + column_width - score_width - 16, row_y + 10),
                score,
                font=score_font,
                fill=INK,
            )
            opponent = str(row.get("opponent") or "—")
            left_width = column_width - score_width - 42
            left_text = f"{_date_label(row.get('date'))} · {opponent}"
            left_font = body_font
            while left_font.size > (16 if dense else 17):
                box = draw.textbbox((0, 0), left_text, font=left_font)
                if box[2] - box[0] <= left_width:
                    break
                left_font = _font(left_font.size - 1)
            draw.text((x + 14, row_y + 9), left_text, font=left_font, fill=INK)

    note = "Completed batting innings only · * = not out"
    draw.text((MARGIN, HEIGHT - 76), note, font=_font(18, bold=False), fill=MUTED)
    _draw_attribution(draw)
    return base


def _dynamic_player_rows(
    intent: StatsIntent,
    player: dict[str, Any],
    opponent_team: str = "",
) -> list[dict[str, Any]]:
    table = FORMAT_TABLES.get((intent.format_name, intent.gender))
    if not table:
        raise StatsCardError("That format/gender combination is not available in the stats database.")
    unique_name = _normalise(player.get("unique_name") or "")
    if not unique_name:
        raise StatsCardError("The matched player has no usable database name.")
    conditions = [
        f"lower(b.striker) = lower('{_sql_text(unique_name)}')",
        f"b.innings <= {_innings_limit(intent.format_name)}",
    ]
    if opponent_team:
        conditions.append(f"lower(b.bowling_team) = lower('{_sql_text(opponent_team)}')")
    sql = (
        "SELECT b.match_id, b.start_date, b.innings, b.batting_team, b.bowling_team, "
        "SUM(b.runs_off_bat) AS runs, "
        "COUNT(*) FILTER (WHERE b.wides IS NULL) AS balls_faced, "
        "SUM(CASE WHEN b.runs_off_bat = 4 THEN 1 ELSE 0 END) AS fours, "
        "SUM(CASE WHEN b.runs_off_bat = 6 THEN 1 ELSE 0 END) AS sixes, "
        "MAX(CASE WHEN lower(b.player_dismissed) = lower(b.striker) THEN 1 ELSE 0 END) AS dismissed "
        f"FROM {table} b WHERE {' AND '.join(conditions)} "
        "GROUP BY b.match_id, b.start_date, b.innings, b.batting_team, b.bowling_team, b.striker "
        "ORDER BY b.start_date DESC, b.match_id DESC, b.innings DESC"
    )
    rows = _query(sql)
    return [
        {
            "match_id": row.get("match_id"),
            "date": row.get("start_date"),
            "opponent": _normalise(row.get("bowling_team") or ""),
            "team": _normalise(row.get("batting_team") or ""),
            "runs": _to_int(row.get("runs")),
            "balls": _to_int(row.get("balls_faced")),
            "fours": _to_int(row.get("fours")),
            "sixes": _to_int(row.get("sixes")),
            "dismissed": _to_int(row.get("dismissed")) == 1,
        }
        for row in rows
    ]

def _dynamic_player_summary(
    intent: StatsIntent,
    player: dict[str, Any],
    opponent_team: str = "",
) -> dict[str, Any]:
    all_innings = _dynamic_player_rows(intent, player, opponent_team)
    if not all_innings:
        suffix = f" against {opponent_team}" if opponent_team else ""
        raise StatsCardError(
            f"No {FORMAT_LABELS[intent.format_name]} batting data was found for {player['name']}{suffix}."
        )
    innings = all_innings[:intent.count] if intent.kind == "player_last_n" else all_innings
    total_runs = sum(item["runs"] for item in innings)
    outs = sum(1 for item in innings if item["dismissed"])
    balls = sum(item["balls"] for item in innings)
    fours = sum(item["fours"] for item in innings)
    sixes = sum(item["sixes"] for item in innings)
    dates = [parsed for item in innings if (parsed := _date_value(item["date"])) is not None]
    high_score = max(item["runs"] for item in innings)
    high_rows = [item for item in innings if item["runs"] == high_score]
    team_counts: dict[str, int] = {}
    for item in innings:
        if item["team"]:
            team_counts[item["team"]] = team_counts.get(item["team"], 0) + 1
    return {
        "player": player["name"],
        "format": FORMAT_LABELS[intent.format_name],
        "gender": intent.gender,
        "team": max(team_counts, key=team_counts.get) if team_counts else "",
        "opponent_team": opponent_team,
        "matches": len({str(item["match_id"]) for item in innings}),
        "innings": len(innings),
        "runs": total_runs,
        "average": total_runs / outs if outs else None,
        "strike_rate": total_runs * 100 / balls if balls else None,
        "high_score": f"{high_score}{'' if all(item['dismissed'] for item in high_rows) else '*'}",
        "hundreds": sum(1 for item in innings if item["runs"] >= 100),
        "fifties": sum(1 for item in innings if 50 <= item["runs"] < 100),
        "not_outs": sum(1 for item in innings if not item["dismissed"]),
        "balls_faced": balls,
        "fours": fours,
        "sixes": sixes,
        "ducks": sum(1 for item in innings if item["runs"] == 0),
        "runs_per_innings": total_runs / len(innings) if innings else None,
        "boundary_runs": fours * 4 + sixes * 6,
        "last_date": max(dates) if dates else None,
        "first_date": min(dates) if dates else None,
        "count_requested": intent.count,
        "count_available": len(innings),
        "innings_rows": innings,
    }

def _dynamic_h2h_summary(plan: dict[str, Any]) -> dict[str, Any]:
    team1 = _sql_text(plan["team1"])
    team2 = _sql_text(plan["team2"])
    match_type = FORMAT_LABELS[plan["format"]]
    gender_value = "female" if plan["gender"] == "women" else "male"
    sql = (
        "SELECT match_id, start_date, team1, team2, winner FROM match_info "
        f"WHERE match_type = '{match_type}' AND gender = '{gender_value}' "
        f"AND ((lower(team1) = lower('{team1}') AND lower(team2) = lower('{team2}')) "
        f"OR (lower(team1) = lower('{team2}') AND lower(team2) = lower('{team1}'))) "
        "ORDER BY start_date DESC, match_id DESC"
    )
    rows = _query(sql)
    if not rows:
        raise StatsCardError(f"No {match_type} H2H matches were found for {plan['team1']} vs {plan['team2']}.")
    wins1 = wins2 = other = 0
    meetings = []
    for row in rows:
        winner = _normalise(row.get("winner") or "")
        if winner.casefold() == plan["team1"].casefold():
            wins1 += 1
            result = f"{plan['team1']} won"
        elif winner.casefold() == plan["team2"].casefold():
            wins2 += 1
            result = f"{plan['team2']} won"
        else:
            other += 1
            result = "No result / tied"
        meetings.append({"date": row.get("start_date"), "result": result})
    dates = [parsed for row in rows if (parsed := _date_value(row.get("start_date"))) is not None]
    return {
        "team1": plan["team1"], "team2": plan["team2"], "format": match_type, "gender": plan["gender"],
        "matches": len(rows), "wins_team1": wins1, "wins_team2": wins2, "no_result": other,
        "team1_win_pct": wins1 * 100 / len(rows), "team2_win_pct": wins2 * 100 / len(rows),
        "first_meeting": min(dates) if dates else None, "last_meeting": max(dates) if dates else None,
        "meetings": meetings,
    }

def _dynamic_metric_items(plan: dict[str, Any], stats: dict[str, Any]) -> list[tuple[str, str]]:
    if plan["scope"] == "h2h":
        labels = {
            "wins_team1": f"{stats['team1']} wins",
            "wins_team2": f"{stats['team2']} wins",
        }
        values = {
            "matches": stats["matches"], "wins_team1": stats["wins_team1"], "wins_team2": stats["wins_team2"],
            "no_result": stats["no_result"], "team1_win_pct": stats["team1_win_pct"],
            "team2_win_pct": stats["team2_win_pct"], "first_meeting": _date_label(stats["first_meeting"]),
            "last_meeting": _date_label(stats["last_meeting"]),
        }
        items=[]
        for metric_id in plan["metrics"]:
            value=values[metric_id]
            if metric_id.endswith("_win_pct"):
                text_value=f"{float(value):.1f}%"
            elif isinstance(value,(int,float)):
                text_value=f"{value:,}"
            else:
                text_value=str(value)
            items.append((labels.get(metric_id,DYNAMIC_METRIC_INFO[metric_id][0]),text_value))
        return items

    values = {
        "matches": stats["matches"], "innings": stats["innings"], "runs": stats["runs"],
        "average": stats["average"], "strike_rate": stats["strike_rate"], "high_score": stats["high_score"],
        "hundreds": stats["hundreds"], "fifties": stats["fifties"], "not_outs": stats["not_outs"],
        "balls_faced": stats["balls_faced"], "fours": stats["fours"], "sixes": stats["sixes"],
        "ducks": stats["ducks"], "runs_per_innings": stats["runs_per_innings"],
        "boundary_runs": stats["boundary_runs"],
    }
    items=[]
    for metric_id in plan["metrics"]:
        value=values[metric_id]
        if value is None:
            text_value="—"
        elif metric_id in {"average","strike_rate","runs_per_innings"}:
            text_value=f"{float(value):.2f}"
        elif isinstance(value,(int,float)):
            text_value=f"{value:,}"
        else:
            text_value=str(value)
        items.append((DYNAMIC_METRIC_INFO[metric_id][0],text_value))
    return items

def _fit_single_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    value = _normalise(text)
    if not value:
        return "—"
    if draw.textbbox((0,0),value,font=font)[2] <= max_width:
        return value
    candidate=value
    while candidate and draw.textbbox((0,0),candidate+"…",font=font)[2] > max_width:
        candidate=candidate[:-1]
    return (candidate.rstrip()+"…") if candidate else "…"

def _draw_dynamic_metric_grid(
    draw: ImageDraw.ImageDraw,
    metrics: list[tuple[str, str]],
    top: int,
    *,
    with_detail: bool,
) -> int:
    if not metrics:
        return top
    columns = 4 if with_detail or len(metrics) >= 10 else 3
    gap = 16
    available = WIDTH - MARGIN * 2
    tile_width = (available - gap * (columns - 1)) // columns
    tile_height = (
        96 if with_detail and len(metrics) >= 10
        else 106 if with_detail
        else 150 if len(metrics) >= 10
        else 142
    )
    label_font = _font(18 if columns == 4 else 20)
    value_font = _font(39 if columns == 4 else 46)
    rows = (len(metrics) + columns - 1) // columns
    for row_index in range(rows):
        row = metrics[row_index*columns:(row_index+1)*columns]
        y=top+row_index*(tile_height+gap)
        for col_index,(label,value) in enumerate(row):
            x=MARGIN+col_index*(tile_width+gap)
            draw.rounded_rectangle((x,y,x+tile_width,y+tile_height),radius=16,fill=(255,255,255),outline=LINE,width=2)
            label_lines=_wrap_words(draw,label.upper(),label_font,tile_width-28)
            label_y=y+13
            for line in label_lines[:2]:
                box=draw.textbbox((0,0),line,font=label_font)
                draw.text((x+(tile_width-(box[2]-box[0]))/2,label_y),line,font=label_font,fill=MUTED)
                label_y += box[3]-box[1]+2
            value_text=_fit_single_line(draw,value,value_font,tile_width-28)
            value_for_tile=value_font
            while value_for_tile.size>28 and draw.textbbox((0,0),value_text,font=value_for_tile)[2]>tile_width-28:
                value_for_tile=_font(value_for_tile.size-2)
            box=draw.textbbox((0,0),value_text,font=value_for_tile)
            draw.text((x+(tile_width-(box[2]-box[0]))/2,y+tile_height-(box[3]-box[1])-13),value_text,font=value_for_tile,fill=INK)
    return top+rows*tile_height+max(0,rows-1)*gap

def _draw_dynamic_detail_table(
    draw: ImageDraw.ImageDraw,
    detail_type: str,
    stats: dict[str, Any],
    top: int,
    bottom_limit: int,
) -> int:
    rows=list(stats.get("innings_rows") if detail_type=="innings" else stats.get("meetings") or [])
    if not rows or top>=bottom_limit:
        return top
    rows=rows[:min(20, len(rows))]
    title="RECENT INNINGS" if detail_type=="innings" else "RECENT MEETINGS"
    draw.text((MARGIN,top),title,font=_font(19),fill=BRAND_BLUE)
    header_y=top+30
    small=_font(16,bold=False)
    heading="SCORE" if detail_type=="innings" else "RESULT"
    draw.text((MARGIN,header_y),"DATE · OPPONENT" if detail_type=="innings" else "DATE",font=small,fill=MUTED)
    hb=draw.textbbox((0,0),heading,font=small)
    draw.text((WIDTH-MARGIN-(hb[2]-hb[0]),header_y),heading,font=small,fill=MUTED)
    rows_per_column=max(1,(len(rows)+1)//2)
    gap=14
    row_gap=4
    table_rows_top=header_y+23
    max_row_height=max(32,(bottom_limit-table_rows_top-8-row_gap*(rows_per_column-1))//rows_per_column)
    row_height=min(50 if len(rows)<=10 else 43,max_row_height)
    if row_height<32:
        return top
    col_width=(WIDTH-MARGIN*2-gap)//2
    body_font=_font(20 if len(rows)<=10 else 17,bold=False)
    value_font=_font(25 if len(rows)<=10 else 21)
    right_width=118
    left_width=col_width-right_width-28
    for column in range(2):
        col_rows=rows[column*rows_per_column:(column+1)*rows_per_column]
        x=MARGIN+column*(col_width+gap)
        for row_index,row in enumerate(col_rows):
            row_y=table_rows_top+row_index*(row_height+row_gap)
            draw.rounded_rectangle((x,row_y,x+col_width,row_y+row_height),radius=10,fill=(255,255,255),outline=LINE,width=1)
            if detail_type=="innings":
                left_text=f"{_date_label(row.get('date'))} · {_normalise(row.get('opponent') or '')}"
                right_text=f"{_to_int(row.get('runs'))}{'' if bool(row.get('dismissed')) else '*'}"
            else:
                left_text=_date_label(row.get('date'))
                right_text=_normalise(row.get('result') or "No result / tied")
            left=_fit_single_line(draw,left_text,body_font,left_width)
            right=_fit_single_line(draw,right_text,value_font,right_width)
            lb=draw.textbbox((0,0),left,font=body_font)
            rb=draw.textbbox((0,0),right,font=value_font)
            draw.text((x+12,row_y+(row_height-(lb[3]-lb[1]))/2-1),left,font=body_font,fill=INK)
            draw.text((x+col_width-(rb[2]-rb[0])-12,row_y+(row_height-(rb[3]-rb[1]))/2-1),right,font=value_font,fill=INK)
    return table_rows_top+rows_per_column*(row_height+row_gap)-row_gap

def _dynamic_stats_card(plan: dict[str, Any], stats: dict[str, Any], source_image: Any) -> Image.Image:
    base=Image.new("RGB",(WIDTH,HEIGHT),WHITE)
    _draw_image_header(base,source_image)
    if plan["scope"]=="h2h":
        title=f"{stats['team1']} vs {stats['team2']}"
        context=[f"{stats['format']} · HEAD-TO-HEAD · {stats['matches']} matches",f"{_date_label(stats['first_meeting'])} – {_date_label(stats['last_meeting'])}"]
    elif plan["scope"]=="player_last_n":
        title=f"{stats['player']} · last {stats['count_requested']} innings"
        context=[f"{stats['format']} · {stats['count_available']} innings shown",f"Stats through {_date_label(stats['last_date'])}"]
    elif plan["scope"]=="player_vs_team":
        title=f"{stats['player']} vs {stats['opponent_team']}"
        context=[f"{stats['format']} · AGAINST {stats['opponent_team']}",f"{stats['matches']} matches · {stats['innings']} innings"]
    else:
        title=f"{stats['player']} · {stats['format']} stats"
        context=[f"{stats['format']} · {stats['team'] or 'Team not recorded'} · CAREER",f"{stats['matches']} matches · {stats['innings']} batting innings"]
    y=_draw_header(base,title,context)
    metrics=_dynamic_metric_items(plan,stats)
    metrics_bottom=_draw_dynamic_metric_grid(ImageDraw.Draw(base),metrics,y+14,with_detail=plan["detail_table"]!="none")
    if plan["detail_table"]!="none":
        stats["detail_limit"]=plan["detail_limit"]
        table_top=metrics_bottom+20
        table_bottom=_draw_dynamic_detail_table(ImageDraw.Draw(base),plan["detail_table"],stats,table_top,1830)
        if table_bottom<=table_top:
            raise StatsCardError("The requested stats and detail table do not fit on one card. Try a narrower query.")
    _draw_attribution(ImageDraw.Draw(base))
    return base

def _dynamic_stats_for_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if plan["scope"]=="h2h":
        return _dynamic_h2h_summary(plan), ""
    intent=StatsIntent(kind=plan["scope"],format_name=plan["format"],gender=plan["gender"],player=plan["player"],count=plan["count"])
    player=_resolve_player(intent)
    return _dynamic_player_summary(intent,player,plan.get("opponent_team") or ""), player["name"]

def build_test_stats_card(query: str, image_bytes: bytes | bytearray | Image.Image, output_dir: str | Path = "output/visuals/stats_cards") -> dict[str, Any]:
    plan=_plan_dynamic_stats(query)
    stats,resolved_player=_dynamic_stats_for_plan(plan)
    card=_dynamic_stats_card(plan,stats,image_bytes)
    if plan["scope"]=="h2h":
        label=f"{stats['team1']} vs {stats['team2']} · {stats['format']} H2H"
    elif plan["scope"]=="player_last_n":
        label=f"{resolved_player} · {stats['format']} last {stats['count_requested']} innings"
    elif plan["scope"]=="player_vs_team":
        label=f"{resolved_player} vs {stats['opponent_team']} · {stats['format']}"
    else:
        label=f"{resolved_player} · {stats['format']} stats"
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    slug=re.sub(r"[^a-z0-9]+","-",label.casefold()).strip("-") or "stats-card"
    path=output/f"{slug}.png"
    index=2
    while path.exists():
        path=output/f"{slug}-{index}.png"
        index+=1
    buffer=BytesIO()
    card.save(buffer,format="PNG",optimize=True)
    data=buffer.getvalue()
    path.write_bytes(data)
    return {
        "bytes":data,"path":str(path),"width":WIDTH,"height":HEIGHT,"label":label,
        "source":SOURCE_NAME,"query":_normalise(query),"stats":stats,
        "layout":{"width":WIDTH,"height":HEIGHT,"image_width":WIDTH,"image_height":IMAGE_HEIGHT,"panel_height":HEIGHT-IMAGE_HEIGHT},
        "intent":{"kind":plan["scope"],"format":plan["format"],"gender":plan["gender"]},
        "plan":plan,
    }

def _stats_for_intent(intent: StatsIntent) -> dict[str, Any]:
    if intent.kind == "h2h":
        return _h2h_stats(intent)
    player = _resolve_player(intent)
    if intent.kind == "last_n":
        return _last_n_stats(intent, player)
    return _career_stats(intent, player)


def build_stats_card(
    query: str,
    image_bytes: bytes | bytearray | Image.Image,
    output_dir: str | Path = "output/visuals/stats_cards",
) -> dict[str, Any]:
    intent = _parse_query(query)
    stats = _stats_for_intent(intent)

    if intent.kind == "h2h":
        card = _h2h_card(stats, image_bytes)
        label = f"{stats['team1']} vs {stats['team2']} · {stats['format']} H2H"
    elif intent.kind == "last_n":
        card = _last_n_card(stats, image_bytes)
        label = f"{stats['player']} · {stats['format']} last {stats['count_requested']} innings"
    else:
        card = _career_card(stats, image_bytes)
        label = f"{stats['player']} · {stats['format']} career stats"

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or "stats-card"
    path = output / f"{slug}.png"
    index = 2
    while path.exists():
        path = output / f"{slug}-{index}.png"
        index += 1
    buffer = BytesIO()
    card.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    path.write_bytes(data)
    return {
        "bytes": data,
        "path": str(path),
        "width": WIDTH,
        "height": HEIGHT,
        "label": label,
        "source": SOURCE_NAME,
        "query": _normalise(query),
        "stats": stats,
        "layout": {
            "width": WIDTH,
            "height": HEIGHT,
            "image_width": WIDTH,
            "image_height": IMAGE_HEIGHT,
            "panel_height": HEIGHT - IMAGE_HEIGHT,
        },
        "intent": {
            "kind": intent.kind,
            "format": intent.format_name,
            "gender": intent.gender,
        },
    }
