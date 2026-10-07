"""Standalone card layouts for Final-Shorts visual QC.

This module renders 1080x1920 sports/news cards with Pillow only.
All card content is manually supplied and remains subject to visual QC.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageFilter


WIDTH = 1080
HEIGHT = 1920

SAFE_LEFT = 72
SAFE_TOP = 300
SAFE_RIGHT = 864
SAFE_BOTTOM = 1240

ACCENT = (255, 205, 66)
WHITE = (248, 249, 251)
MUTED = (193, 198, 204)
PANEL = (7, 10, 14, 224)
PANEL_SOFT = (7, 10, 14, 198)
BLACK = (0, 0, 0)

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
    """Raised when a card cannot be rendered cleanly."""


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
    ratio = WIDTH / HEIGHT
    current = image.width / image.height
    if current > ratio:
        crop_width = max(1, int(image.height * ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif current < ratio:
        crop_height = max(1, int(image.width / ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _font_file(name: str) -> Path:
    root = Path(__file__).resolve().parent / "fonts"
    return root / name


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


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_lines(
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
        if len(lines) <= max_lines and lines and all(
            _text_width(draw, line, font) <= max_width for line in lines
        ):
            return font, lines
    raise CardStudioError("The card text is too long for this layout. Shorten the copy.")


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, gap: int) -> int:
    box = draw.textbbox((0, 0), "Ag", font=font)
    return box[3] - box[1] + gap


def _draw_text(
    canvas: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = WHITE,
    anchor: str | None = None,
    stroke: int = 0,
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=BLACK)


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
    step = _line_height(draw, font, gap)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _background(source: bytes | bytearray | Image.Image) -> Image.Image:
    base = _cover(source).convert("RGBA")
    veil = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(veil)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 74))
    draw.rectangle(
        (SAFE_LEFT - 28, SAFE_TOP - 30, SAFE_RIGHT + 20, SAFE_BOTTOM + 34),
        fill=PANEL,
    )
    base = Image.alpha_composite(base, veil)
    return base


def _frame_header(canvas: Image.Image, eyebrow: str) -> int:
    draw = ImageDraw.Draw(canvas)
    x = SAFE_LEFT
    y = SAFE_TOP
    draw.rectangle((x, y + 4, x + 70, y + 12), fill=ACCENT)
    draw.text(
        (x + 92, y - 2),
        " ".join(str(eyebrow or "").split()).upper(),
        font=_font(34),
        fill=MUTED,
    )
    return y + 72


def _render_stat_highlight(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _frame_header(canvas, data.get("eyebrow") or "STAT")
    headline = str(data.get("headline") or "").strip()
    value = str(data.get("value") or "").strip()
    unit = str(data.get("unit") or "").strip()
    if not headline or not value:
        raise CardStudioError("Stat Highlight needs a headline and a hero value.")

    headline_font, headline_lines = _fit_lines(
        draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 104, 64
    )
    y = _draw_lines(canvas, headline_lines, SAFE_LEFT, y, headline_font, 8, WHITE) + 26

    value_font = _font(236)
    draw.text((SAFE_LEFT, y), value, font=value_font, fill=WHITE)
    box = draw.textbbox((SAFE_LEFT, y), value, font=value_font)
    value_bottom = box[3]
    if unit:
        draw.text(
            (box[2] + 18, value_bottom - 64),
            unit.upper(),
            font=_font(50),
            fill=ACCENT,
        )
    y = value_bottom + 50

    metrics = data.get("metrics") or []
    if len(metrics) > 3:
        raise CardStudioError("Stat Highlight supports at most three supporting metrics.")
    if metrics:
        width = SAFE_RIGHT - SAFE_LEFT
        row_h = 128
        for metric in metrics:
            label = " ".join(str(metric.get("label") or "").split())
            metric_value = " ".join(str(metric.get("value") or "").split())
            if not label or not metric_value:
                raise CardStudioError("Every supporting metric needs a label and value.")
            draw.rounded_rectangle(
                (SAFE_LEFT, y, SAFE_RIGHT, y + row_h - 12),
                radius=16,
                fill=PANEL_SOFT,
            )
            draw.text((SAFE_LEFT + 24, y + 20), label.upper(), font=_font(31, False), fill=MUTED)
            metric_font, metric_lines = _fit_lines(
                draw, metric_value, width - 300, 1, 62, 42
            )
            draw.text(
                (SAFE_RIGHT - 24, y + 19),
                metric_lines[0],
                font=metric_font,
                fill=WHITE,
                anchor="ra",
            )
            y += row_h

    return canvas


def _render_quote_reaction(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _frame_header(canvas, data.get("eyebrow") or "REACTION")
    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())
    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    draw.text((SAFE_LEFT, y), "“", font=_font(128), fill=ACCENT)
    y += 66
    quote_font, quote_lines = _fit_lines(
        draw, quote, SAFE_RIGHT - SAFE_LEFT, 7, 92, 56
    )
    y = _draw_lines(canvas, quote_lines, SAFE_LEFT, y, quote_font, 13, WHITE) + 28
    draw.rectangle((SAFE_LEFT, y, SAFE_LEFT + 110, y + 6), fill=ACCENT)
    y += 28
    attribution_font, attribution_lines = _fit_lines(
        draw, attribution, SAFE_RIGHT - SAFE_LEFT, 2, 48, 34, bold=False
    )
    y = _draw_lines(canvas, attribution_lines, SAFE_LEFT, y, attribution_font, 8, WHITE)
    if context:
        y += 22
        context_font, context_lines = _fit_lines(
            draw, context, SAFE_RIGHT - SAFE_LEFT, 3, 38, 30, bold=False
        )
        _draw_lines(canvas, context_lines, SAFE_LEFT, y, context_font, 8, MUTED)
    return canvas


def _render_head_to_head(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _frame_header(canvas, data.get("eyebrow") or "COMPARISON")
    headline = " ".join(str(data.get("headline") or "").split())
    left = data.get("left") or {}
    right = data.get("right") or {}
    metrics = list(data.get("metrics") or [])
    if not headline or not left.get("name") or not right.get("name"):
        raise CardStudioError("Head-to-Head needs a headline and both names.")
    if not 1 <= len(metrics) <= 3:
        raise CardStudioError("Head-to-Head needs one to three comparison metrics.")

    headline_font, headline_lines = _fit_lines(
        draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 58
    )
    y = _draw_lines(canvas, headline_lines, SAFE_LEFT, y, headline_font, 8, WHITE) + 34

    split_x = (SAFE_LEFT + SAFE_RIGHT) // 2
    draw.line((split_x, y, split_x, SAFE_BOTTOM), fill=(255, 255, 255, 48), width=2)

    for base_x, side, anchor in (
        (SAFE_LEFT, left, "la"),
        (split_x + 28, right, "la"),
    ):
        name_font, name_lines = _fit_lines(
            draw, str(side["name"]), split_x - SAFE_LEFT - 48, 2, 62, 42
        )
        draw.multiline_text(
            (base_x, y),
            "\n".join(name_lines),
            font=name_font,
            fill=WHITE,
            spacing=4,
        )

    y += 150
    row_h = 130
    for label in metrics:
        metric_label = " ".join(str(label).split())
        lval = " ".join(str((left.get("values") or {}).get(metric_label, "")).split())
        rval = " ".join(str((right.get("values") or {}).get(metric_label, "")).split())
        if not lval or not rval:
            raise CardStudioError(f"Both sides need a value for {metric_label}.")
        draw.text((SAFE_LEFT, y), metric_label.upper(), font=_font(27, False), fill=MUTED)
        lfont, _ = _fit_lines(draw, lval, split_x - SAFE_LEFT - 48, 1, 62, 42)
        rfont, _ = _fit_lines(draw, rval, SAFE_RIGHT - split_x - 52, 1, 62, 42)
        draw.text((SAFE_LEFT, y + 36), lval, font=lfont, fill=WHITE)
        draw.text((split_x + 28, y + 36), rval, font=rfont, fill=WHITE)
        y += row_h
    return canvas


def _render_fact_milestone(source, data: dict) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _frame_header(canvas, data.get("eyebrow") or "MILESTONE")
    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())
    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    value_font, value_lines = _fit_lines(
        draw, value, SAFE_RIGHT - SAFE_LEFT, 2, 220, 112
    )
    y = _draw_lines(canvas, value_lines, SAFE_LEFT, y, value_font, 6, ACCENT) + 18

    label_font, label_lines = _fit_lines(
        draw, label, SAFE_RIGHT - SAFE_LEFT, 2, 74, 46
    )
    y = _draw_lines(canvas, label_lines, SAFE_LEFT, y, label_font, 8, WHITE) + 28

    if context:
        context_font, context_lines = _fit_lines(
            draw, context, SAFE_RIGHT - SAFE_LEFT, 4, 42, 30, bold=False
        )
        _draw_lines(canvas, context_lines, SAFE_LEFT, y, context_font, 9, MUTED)
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


def render_card(
    card_type: str,
    source: bytes | bytearray | Image.Image,
    data: dict,
) -> bytes:
    """Render one non-subject-cutout card to a PNG byte string."""
    if card_type == "Text Subject Cutout":
        raise CardStudioError("Text Subject Cutout uses the approved shared subject-cutout editor.")
    frame = _render(card_type, source, data).convert("RGB")
    buffer = BytesIO()
    frame.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def card_data_for_type(card_type: str) -> dict:
    """Return an empty data schema used by the Streamlit Card Studio editor."""
    if card_type == "Stat Highlight":
        return {"eyebrow": "STAT", "headline": "", "value": "", "unit": "", "metrics": [{"label": "", "value": ""}]}
    if card_type == "Quote / Reaction":
        return {"eyebrow": "REACTION", "quote": "", "attribution": "", "context": ""}
    if card_type == "Head-to-Head":
        return {"eyebrow": "COMPARISON", "headline": "", "left": {"name": "", "values": {}}, "right": {"name": "", "values": {}}, "metrics": [""]}
    if card_type == "Key Fact / Milestone":
        return {"eyebrow": "MILESTONE", "value": "", "label": "", "context": ""}
    return {}
