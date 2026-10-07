"""Manual Card Studio layouts for Final-Shorts.

Card Studio produces static 1080x1920 editorial frames for manual QC.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920

SAFE_LEFT = 88
SAFE_TOP = 220
SAFE_RIGHT = 864
SAFE_BOTTOM = 1460

ACCENT = (255, 205, 66)
WHITE = (248, 249, 251)
MUTED = (199, 204, 210)
DARK = (0, 0, 0)

CARD_TYPES = (
    "Text Subject Cutout",
    "Stat Highlight",
    "Quote / Reaction",
    "Head-to-Head",
    "Key Fact / Milestone",
)

TEST_CARD_TYPES = CARD_TYPES
LIVE_CARD_TYPES = ("Text Subject Cutout",)


class CardStudioError(ValueError):
    """Raised when a Card Studio frame cannot be rendered cleanly."""


def _open_image(source: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(source))) as image:
                return image.convert("RGB")
        except (OSError, ValueError) as exc:
            raise CardStudioError("The selected source image could not be opened.") from exc
    raise CardStudioError("A source image is required.")


def _cover(source: bytes | bytearray | Image.Image) -> Image.Image:
    image = _open_image(source)
    target_ratio = WIDTH / HEIGHT
    ratio = image.width / image.height
    if ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _font_file(name: str) -> Path:
    return Path(__file__).resolve().parent / "fonts" / name


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = (
        "Oswald-Bold.ttf",
        "BarlowCondensed-Black.ttf",
        "Anton-Regular.ttf",
    ) if bold else (
        "Barlow-Regular.ttf",
        "Oswald-Bold.ttf",
    )
    for name in names:
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _measure(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_lines: int,
    start_size: int,
    min_size: int,
    bold: bool = True,
) -> tuple[ImageFont.ImageFont, list[str]]:
    for size in range(start_size, min_size - 1, -4):
        font = _font(size, bold=bold)
        lines = _wrap(draw, text, font, max_width)
        if lines and len(lines) <= max_lines:
            return font, lines
    raise CardStudioError("The card text is too long for this layout. Shorten the copy.")


def _draw_lines(
    canvas: Image.Image,
    lines: list[str],
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    gap: int,
    fill: tuple[int, int, int] = WHITE,
) -> int:
    draw = ImageDraw.Draw(canvas)
    _, height = _measure(draw, "Ag", font)
    for line in lines:
        draw.text(
            (x + 3, y + 5),
            line,
            font=font,
            fill=DARK,
            stroke_width=2,
            stroke_fill=DARK,
        )
        draw.text((x, y), line, font=font, fill=fill)
        y += height + gap
    return y


def _background(source: bytes | bytearray | Image.Image) -> Image.Image:
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 58))

    for top in range(HEIGHT):
        if top < 760:
            alpha = 0
        elif top >= 1510:
            alpha = 205
        else:
            alpha = int((top - 760) / 750 * 205)
        draw.line((0, top, WIDTH, top), fill=(0, 0, 0, alpha))

    draw.rectangle(
        (SAFE_LEFT - 22, SAFE_TOP - 22, SAFE_RIGHT + 24, SAFE_BOTTOM + 14),
        fill=(0, 0, 0, 34),
    )
    draw.rectangle(
        (SAFE_LEFT - 22, SAFE_TOP - 22, SAFE_LEFT - 14, SAFE_BOTTOM + 14),
        fill=ACCENT,
    )
    return Image.alpha_composite(base, overlay)


def _kicker(canvas: Image.Image, text: str) -> int:
    draw = ImageDraw.Draw(canvas)
    clean = " ".join(str(text or "").split()).upper() or "STORY"
    draw.text(
        (SAFE_LEFT, SAFE_TOP - 2),
        clean,
        font=_font(34),
        fill=MUTED,
    )
    return SAFE_TOP + 62


def _draw_metric_row(
    canvas: Image.Image,
    y: int,
    label: str,
    value: str,
    value_size: int = 58,
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.line(
        (SAFE_LEFT, y, SAFE_RIGHT, y),
        fill=(255, 255, 255, 55),
        width=2,
    )
    draw.text(
        (SAFE_LEFT + 6, y + 20),
        " ".join(label.split()).upper(),
        font=_font(29, False),
        fill=MUTED,
    )
    draw.text(
        (SAFE_RIGHT - 8, y + 13),
        " ".join(value.split()),
        font=_font(value_size),
        fill=WHITE,
        anchor="ra",
        stroke_width=1,
        stroke_fill=DARK,
    )


def _render_stat_highlight(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "STAT")

    headline = " ".join(str(data.get("headline") or "").split())
    value = " ".join(str(data.get("value") or "").split())
    unit = " ".join(str(data.get("unit") or "").split())
    metrics = data.get("metrics") or []

    if not headline or not value:
        raise CardStudioError("Stat Highlight needs a headline and a hero value.")
    if len(metrics) > 3:
        raise CardStudioError("Stat Highlight supports at most three supporting metrics.")

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT - 8, 2, 92, 60)
    y = _draw_lines(canvas, headline_lines, SAFE_LEFT, y, headline_font, 7) + 54

    value_font = _font(286)
    value_w, value_h = _measure(draw, value, value_font)
    if value_w > SAFE_RIGHT - SAFE_LEFT:
        value_font, _ = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 1, 240, 120)
        value_w, value_h = _measure(draw, value, value_font)

    draw.text(
        (SAFE_LEFT, y),
        value,
        font=value_font,
        fill=WHITE,
        stroke_width=2,
        stroke_fill=DARK,
    )
    if unit:
        unit_y = y + max(12, value_h - 62)
        draw.text(
            (SAFE_LEFT + value_w + 18, unit_y),
            unit.upper(),
            font=_font(46),
            fill=ACCENT,
        )
    y += value_h + 72

    if metrics:
        for metric in metrics:
            label = " ".join(str(metric.get("label") or "").split())
            metric_value = " ".join(str(metric.get("value") or "").split())
            if not label or not metric_value:
                raise CardStudioError("Every supporting metric needs a label and value.")
            _draw_metric_row(canvas, y, label, metric_value)
            y += 112

    return canvas


def _render_quote_reaction(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "REACTION")

    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    quote_font, quote_lines = _fit(draw, quote, SAFE_RIGHT - SAFE_LEFT - 4, 6, 82, 50)
    draw.text((SAFE_LEFT - 3, y - 12), "“", font=_font(120), fill=ACCENT)
    y = _draw_lines(canvas, quote_lines, SAFE_LEFT, y + 70, quote_font, 12) + 42

    attribution_font, attribution_lines = _fit(
        draw,
        attribution,
        SAFE_RIGHT - SAFE_LEFT,
        2,
        50,
        34,
        bold=False,
    )
    y = _draw_lines(canvas, attribution_lines, SAFE_LEFT, y, attribution_font, 8)
    if context:
        context_font, context_lines = _fit(
            draw,
            context,
            SAFE_RIGHT - SAFE_LEFT,
            3,
            38,
            30,
            bold=False,
        )
        _draw_lines(canvas, context_lines, SAFE_LEFT, y + 20, context_font, 8, MUTED)

    return canvas


def _render_head_to_head(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "HEAD TO HEAD")

    headline = " ".join(str(data.get("headline") or "").split())
    left = data.get("left") or {}
    right = data.get("right") or {}
    metrics = list(data.get("metrics") or [])

    if not headline or not left.get("name") or not right.get("name"):
        raise CardStudioError("Head-to-Head needs a headline and both names.")
    if not 1 <= len(metrics) <= 3:
        raise CardStudioError("Head-to-Head needs one to three comparison metrics.")

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 82, 54)
    y = _draw_lines(canvas, headline_lines, SAFE_LEFT, y, headline_font, 7) + 42

    split_x = (SAFE_LEFT + SAFE_RIGHT) // 2
    draw.line((split_x, y, split_x, SAFE_BOTTOM), fill=(255, 255, 255, 70), width=2)

    for x, side in ((SAFE_LEFT, left), (split_x + 28, right)):
        name_font, name_lines = _fit(
            draw,
            str(side["name"]),
            split_x - SAFE_LEFT - 48,
            2,
            54,
            38,
        )
        _draw_lines(canvas, name_lines, x, y, name_font, 5)

    y += 138
    left_values = left.get("values") or {}
    right_values = right.get("values") or {}
    for label in metrics:
        metric_label = " ".join(str(label).split())
        lval = " ".join(str(left_values.get(metric_label) or "").split())
        rval = " ".join(str(right_values.get(metric_label) or "").split())
        if not lval or not rval:
            raise CardStudioError(f"Both sides need a value for {metric_label}.")
        draw.text((SAFE_LEFT, y), metric_label.upper(), font=_font(27, False), fill=MUTED)
        lfont, _ = _fit(draw, lval, split_x - SAFE_LEFT - 48, 1, 60, 40)
        rfont, _ = _fit(draw, rval, SAFE_RIGHT - split_x - 48, 1, 60, 40)
        draw.text((SAFE_LEFT, y + 38), lval, font=lfont, fill=WHITE)
        draw.text((split_x + 28, y + 38), rval, font=rfont, fill=WHITE)
        draw.line((SAFE_LEFT, y + 108, SAFE_RIGHT, y + 108), fill=(255, 255, 255, 42), width=2)
        y += 132

    return canvas


def _render_fact_milestone(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "MILESTONE")

    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    value_font, value_lines = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 2, 210, 104)
    y = _draw_lines(canvas, value_lines, SAFE_LEFT, y + 24, value_font, 5) + 30

    label_font, label_lines = _fit(draw, label, SAFE_RIGHT - SAFE_LEFT, 3, 68, 42)
    y = _draw_lines(canvas, label_lines, SAFE_LEFT, y, label_font, 7) + 26

    if context:
        context_font, context_lines = _fit(
            draw,
            context,
            SAFE_RIGHT - SAFE_LEFT,
            5,
            40,
            30,
            bold=False,
        )
        _draw_lines(canvas, context_lines, SAFE_LEFT, y, context_font, 8, MUTED)

    return canvas


def _render(card_type: str, source, data: dict) -> Image.Image:
    normalized = " ".join(str(card_type or "").split())
    if normalized == "Stat Highlight":
        return _render_stat_highlight(source, data)
    if normalized == "Quote / Reaction":
        return _render_quote_reaction(source, data)
    if normalized == "Head-to-Head":
        return _render_head_to_head(source, data)
    if normalized == "Key Fact / Milestone":
        return _render_fact_milestone(source, data)
    raise CardStudioError(f"Unknown card type: {normalized or 'None'}")


def render_card(card_type: str, source, data: dict) -> bytes:
    if card_type == "Text Subject Cutout":
        raise CardStudioError("Text Subject Cutout uses the approved shared subject-cutout editor.")
    frame = _render(card_type, source, data).convert("RGB")
    buffer = BytesIO()
    frame.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def card_data_for_type(card_type: str) -> dict:
    if card_type == "Stat Highlight":
        return {
            "eyebrow": "STAT",
            "headline": "",
            "value": "",
            "unit": "",
            "metrics": [],
        }
    if card_type == "Quote / Reaction":
        return {"eyebrow": "REACTION", "quote": "", "attribution": "", "context": ""}
    if card_type == "Head-to-Head":
        return {
            "eyebrow": "HEAD TO HEAD",
            "headline": "",
            "left": {"name": "", "values": {}},
            "right": {"name": "", "values": {}},
            "metrics": [],
        }
    if card_type == "Key Fact / Milestone":
        return {"eyebrow": "MILESTONE", "value": "", "label": "", "context": ""}
    return {}
