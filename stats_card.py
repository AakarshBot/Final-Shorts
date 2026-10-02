"""Cricket stats-card data queries and 9:16 card rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter


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

    if isinstance(payload, dict):
        for key in ("rows", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                payload = value
                break
        else:
            columns = payload.get("columns")
            rows = payload.get("values")
            if isinstance(columns, list) and isinstance(rows, list):
                return [dict(zip(columns, row)) for row in rows]
            raise StatsCardError("Stats database returned an unexpected response.")

    if not isinstance(payload, list):
        raise StatsCardError("Stats database returned an unexpected response.")

    if not payload:
        return []
    if isinstance(payload[0], dict):
        return [dict(item) for item in payload]
    raise StatsCardError("Stats database returned rows without column names.")


def _resolve_player(intent: StatsIntent) -> dict[str, str]:
    needle = _sql_text(intent.player)
    rows = _query(
        "SELECT identifier, name, unique_name "
        "FROM people "
        f"WHERE lower(name) = lower('{needle}') "
        f"OR lower(unique_name) = lower('{needle}') "
        f"OR lower(name) LIKE lower('%{needle}%') "
        f"OR lower(unique_name) LIKE lower('%{needle}%') "
        "ORDER BY CASE "
        f"WHEN lower(name) = lower('{needle}') THEN 0 "
        f"WHEN lower(unique_name) = lower('{needle}') THEN 1 ELSE 2 END, "
        "name "
        "LIMIT 10"
    )
    if not rows:
        raise StatsCardError(f"Could not find player '{intent.player}' in the cricket database.")

    exact = [
        row for row in rows
        if _normalise(row.get("name", "")).casefold() == intent.player.casefold()
        or _normalise(row.get("unique_name", "")).casefold() == intent.player.casefold()
    ]
    if len(exact) == 1:
        row = exact[0]
    elif len(rows) == 1:
        row = rows[0]
    else:
        names = list(dict.fromkeys(
            _normalise(row.get("name") or row.get("unique_name") or "")
            for row in rows
        ))
        names = [name for name in names if name]
        raise StatsCardError(
            "Player query is ambiguous. Use the full player name."
            + (f" Matches: {', '.join(names[:5])}." if names else "")
        )

    unique_name = _normalise(row.get("unique_name") or row.get("name") or "")
    display_name = _normalise(row.get("name") or unique_name)
    if not unique_name:
        raise StatsCardError("The matched player has no usable database identifier.")
    return {"name": display_name, "unique_name": unique_name}


def _innings_limit(format_name: str) -> int:
    return 4 if format_name == "test" else 2


def _player_rows(intent: StatsIntent, player: dict[str, str]) -> list[dict[str, Any]]:
    table = FORMAT_TABLES.get((intent.format_name, intent.gender))
    if not table:
        raise StatsCardError("That format/gender combination is not available in the stats database.")

    unique_name = _sql_text(player["unique_name"])
    innings_limit = _innings_limit(intent.format_name)
    sql = (
        "SELECT b.match_id, b.start_date, b.innings, b.batting_team, b.bowling_team, "
        "b.striker, SUM(b.runs_off_bat) AS runs, "
        "COUNT(*) FILTER (WHERE b.wides IS NULL) AS balls_faced, "
        "MAX(CASE WHEN lower(b.player_dismissed) = lower(b.striker) THEN 1 ELSE 0 END) AS dismissed "
        f"FROM {table} b "
        "WHERE lower(b.striker) = lower('"
        + unique_name
        + "') "
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


def _career_stats(intent: StatsIntent, player: dict[str, str]) -> dict[str, Any]:
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


def _last_n_stats(intent: StatsIntent, player: dict[str, str]) -> dict[str, Any]:
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
    tile_height: int = 142,
) -> int:
    gap = 18
    available = WIDTH - (MARGIN * 2)
    tile_width = (available - gap * (columns - 1)) // columns
    y = top
    rows = (len(metrics) + columns - 1) // columns
    for row_index in range(rows):
        row = metrics[row_index * columns:(row_index + 1) * columns]
        for col_index, (label, value) in enumerate(row):
            x = MARGIN + col_index * (tile_width + gap)
            draw.rounded_rectangle(
                (x, y, x + tile_width, y + tile_height),
                radius=18,
                fill=(255, 255, 255),
                outline=LINE,
                width=2,
            )
            label_font = _font(24)
            value_font = _font(54)
            draw.text((x + 22, y + 18), label.upper(), font=label_font, fill=MUTED)
            value_box = draw.textbbox((0, 0), str(value), font=value_font)
            value_width = value_box[2] - value_box[0]
            draw.text(
                (x + tile_width - value_width - 22, y + 58),
                str(value),
                font=value_font,
                fill=INK,
            )
        y += tile_height + gap
    return y


def _draw_header(
    image: Image.Image,
    title: str,
    context: list[str],
) -> int:
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, PANEL_TOP, WIDTH, PANEL_BOTTOM), fill=(246, 247, 249))
    title_font, lines = _fit_text(
        draw,
        title.upper(),
        WIDTH - (MARGIN * 2),
        82,
        min_size=52,
        max_lines=2,
    )
    y = PANEL_TOP + 48
    y = _draw_centered_lines(draw, lines, title_font, WIDTH // 2, y, INK, gap=6)
    y += 8
    for line in context:
        context_font = _font(27, bold=False)
        wrapped = _wrap_words(draw, line, context_font, WIDTH - (MARGIN * 2))
        y = _draw_centered_lines(draw, wrapped, context_font, WIDTH // 2, y, MUTED, gap=2)
        y += 2
    return y


def _draw_attribution(draw: ImageDraw.ImageDraw) -> None:
    text = f"Source: {SOURCE_NAME} · {SOURCE_LICENSE}"
    font = _font(20, bold=False)
    draw.text((MARGIN, HEIGHT - 44), text, font=font, fill=MUTED)


def _draw_image_header(base: Image.Image, source_image: bytes | bytearray | Image.Image, title: str) -> None:
    image = _fit_cover(
        _asset_image(source_image),
        (WIDTH, IMAGE_HEIGHT),
    )
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, IMAGE_HEIGHT - 280, WIDTH, IMAGE_HEIGHT), fill=(0, 0, 0, 145))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.2))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    base.paste(image, (0, 0))
    draw = ImageDraw.Draw(base)
    kicker_font = _font(24)
    draw.text((MARGIN, 34), "STATS CARD", font=kicker_font, fill=WHITE)
    title_font, lines = _fit_text(
        draw,
        title,
        WIDTH - (MARGIN * 2),
        76,
        min_size=46,
        max_lines=2,
    )
    _draw_centered_lines(
        draw,
        lines,
        title_font,
        WIDTH // 2,
        IMAGE_HEIGHT - 220,
        WHITE,
        gap=4,
    )


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
    _draw_image_header(base, source_image, stats["player"])
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
    _draw_image_header(base, source_image, f"{stats['team1']} vs {stats['team2']}")
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
    _draw_image_header(base, source_image, stats["player"])
    count_text = f"{stats['count_available']} completed batting innings shown"
    if stats["count_available"] < stats["count_requested"]:
        count_text += f" · only {stats['count_available']} available in the dataset"
    context = [
        f"{stats['format']} · LAST {stats['count_requested']} COMPLETED INNINGS",
        count_text,
        f"Stats through {_date_label(stats['last_date'])}",
    ]
    y = _draw_header(
        base,
        f"{stats['player']} · last {stats['count_requested']} innings",
        context,
    )
    draw = ImageDraw.Draw(base)
    table_top = y + 10
    row_h = 63
    x_date = MARGIN
    x_opp = MARGIN + 220
    x_score = WIDTH - MARGIN - 120
    header_font = _font(22)
    body_font = _font(31)
    draw.text((x_date, table_top), "DATE", font=header_font, fill=MUTED)
    draw.text((x_opp, table_top), "OPPONENT", font=header_font, fill=MUTED)
    draw.text((x_score, table_top), "SCORE", font=header_font, fill=MUTED)
    y = table_top + 38
    for row in stats["innings"]:
        draw.line((MARGIN, y - 7, WIDTH - MARGIN, y - 7), fill=LINE, width=2)
        draw.text((x_date, y), _date_label(row["date"]), font=body_font, fill=INK)
        opponent = row["opponent"] or "—"
        draw.text((x_opp, y), opponent[:22], font=body_font, fill=INK)
        score_box = draw.textbbox((0, 0), row["score"], font=body_font)
        draw.text(
            (x_score + 120 - (score_box[2] - score_box[0]), y),
            row["score"],
            font=body_font,
            fill=INK,
        )
        y += row_h
    y += 8
    metrics = [
        ("Runs", f"{stats['runs']:,}"),
        ("Average", f"{stats['average']:.2f}" if stats["average"] is not None else "—"),
        ("100s", str(stats["hundreds"])),
        ("50s", str(stats["fifties"])),
    ]
    _draw_metric_tiles(draw, metrics, y, columns=4, tile_height=118)
    note = (
        "Completed batting innings only. DNB innings are not listed; not-out scores use *."
    )
    note_font = _font(20, bold=False)
    draw.text((MARGIN, HEIGHT - 72), note, font=note_font, fill=MUTED)
    _draw_attribution(draw)
    return base


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
    _asset_image(image_bytes)

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
    card.save(path, format="PNG", optimize=True)

    buffer = BytesIO()
    card.save(buffer, format="PNG", optimize=True)
    return {
        "bytes": buffer.getvalue(),
        "path": str(path),
        "width": WIDTH,
        "height": HEIGHT,
        "label": label,
        "source": SOURCE_NAME,
        "query": _normalise(query),
        "stats": stats,
        "intent": {
            "kind": intent.kind,
            "format": intent.format_name,
            "gender": intent.gender,
        },
    }
