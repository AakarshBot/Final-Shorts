"""Manual Card Studio layouts for Final-Shorts.

Card Studio produces static 1080x1920 editorial frames for manual QC.
Each non-cutout card type features a distinct 2026 vertical broadcast / editorial
visual identity designed for high-engagement mobile sports formats.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920

SAFE_LEFT = 88
SAFE_TOP = 220
SAFE_RIGHT = 864
SAFE_BOTTOM = 1460

# Palette
GOLD_ACCENT = (255, 210, 30)         # Athletic vibrant gold
PRESTIGE_GOLD = (255, 218, 98)       # Luxury milestone / champagne gold
ELECTRIC_CYAN = (64, 196, 255)       # H2H Player 1 / cool rivalry tone
CRIMSON_ACCENT = (255, 102, 68)      # H2H Player 2 / warm rivalry tone
WHITE = (248, 250, 252)              # Crisp primary text
IVORY = (255, 252, 246)              # Editorial warm text for quotes
MUTED = (195, 201, 209)              # Secondary labels and metadata
SUBTLE = (140, 150, 166)             # Tertiary annotations
DARK = (6, 8, 12)                    # Deep obsidian shadow / stroke
CARD_BG = (14, 18, 28, 220)          # Glassmorphic dark container
DIVIDER = (255, 255, 255, 36)

ACCENT = GOLD_ACCENT                 # Backward compatibility alias


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


def _cover(source: bytes | bytearray | Image.Image, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    image = _open_image(source)
    target_ratio = width / height
    ratio = image.width / image.height
    if ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _font_file(name: str) -> Path:
    return Path(__file__).resolve().parent / "fonts" / name


@lru_cache(maxsize=128)
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


@lru_cache(maxsize=128)
def _font_display(size: int) -> ImageFont.FreeTypeFont:
    """Super-bold athletic display font for hero numerals and big impact titles."""
    for name in ("Anton-Regular.ttf", "BarlowCondensed-Black.ttf", "Oswald-Bold.ttf"):
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_headline(size: int) -> ImageFont.FreeTypeFont:
    """Punchy condensed bold font for headlines, player names, and bold titles."""
    for name in ("BarlowCondensed-Black.ttf", "Oswald-Bold.ttf", "Anton-Regular.ttf"):
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_label(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Crisp typography for kickers, category badges, scorecard labels."""
    names = ("Oswald-Bold.ttf", "BarlowCondensed-Black.ttf") if bold else ("Barlow-Regular.ttf", "Oswald-Bold.ttf")
    for name in names:
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_body(size: int) -> ImageFont.FreeTypeFont:
    """Clean editorial font for quotes, context, and secondary descriptions."""
    for name in ("Barlow-Regular.ttf", "Oswald-Bold.ttf"):
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
    font_fn=None,
) -> tuple[ImageFont.ImageFont, list[str]]:
    getter = font_fn or (lambda s: _font(s, bold=bold))
    for size in range(start_size, min_size - 1, -2):
        font = getter(size)
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
    stroke_width: int = 2,
    stroke_fill: tuple[int, int, int] = DARK,
    shadow_offset: tuple[int, int] = (3, 5),
) -> int:
    draw = ImageDraw.Draw(canvas)
    _, height = _measure(draw, "Ag", font)
    sx, sy = shadow_offset
    for line in lines:
        if sx > 0 or sy > 0:
            draw.text(
                (x + sx, y + sy),
                line,
                font=font,
                fill=DARK,
                stroke_width=stroke_width,
                stroke_fill=DARK,
            )
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        y += height + gap
    return y


def _subject_occupancy(mask: Image.Image | None, box: tuple[int, int, int, int]) -> float:
    if not isinstance(mask, Image.Image):
        return 0.0
    mask = mask.convert("L")
    if mask.size != (WIDTH, HEIGHT):
        mask = mask.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    x1, y1, x2, y2 = box
    x1 = max(0, min(WIDTH, x1))
    y1 = max(0, min(HEIGHT, y1))
    x2 = max(x1 + 1, min(WIDTH, x2))
    y2 = max(y1 + 1, min(HEIGHT, y2))
    crop = mask.crop((x1, y1, x2, y2))
    histogram = crop.histogram()
    total = sum(index * count for index, count in enumerate(histogram[96:], 96))
    return total / max(1, (x2 - x1) * (y2 - y1) * 255)


def _best_text_position(
    mask: Image.Image | None,
    width: int,
    height: int,
    region: tuple[int, int, int, int],
    preferred_x: int,
    preferred_y: int,
) -> tuple[int, int]:
    rx1, ry1, rx2, ry2 = region
    candidates = []
    x_values = [rx1, (rx1 + rx2 - width) // 2, rx2 - width]
    y_values = [
        ry1,
        ry1 + max(0, (ry2 - ry1 - height) // 3),
        ry1 + max(0, (ry2 - ry1 - height) * 2 // 3),
        ry2 - height,
    ]
    for x in x_values:
        for y in y_values:
            x = max(rx1, min(rx2 - width, x))
            y = max(ry1, min(ry2 - height, y))
            occupancy = _subject_occupancy(mask, (x, y, x + width, y + height))
            distance = (abs(x - preferred_x) / 240) + (abs(y - preferred_y) / 240)
            candidates.append((occupancy * 6 + distance, x, y))
    _, x, y = min(candidates, key=lambda item: item[0])
    return int(x), int(y)


# ---------------------------------------------------------------------------
# Distinct Background Generators (No cookie-cutter templates)
# ---------------------------------------------------------------------------

def _stat_background(source: bytes | bytearray | Image.Image) -> Image.Image:
    """Atmospheric dark athletic stadium backdrop with clear subject spotlight and deep carbon shelf."""
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Vignette gradients: Top darkening for kicker/headline, bottom deep dark for metrics shelf
    for y in range(HEIGHT):
        if y < 340:
            alpha = int((1.0 - y / 340) * 160)
        elif y < 1000:
            alpha = 15
        elif y >= 1520:
            alpha = 238
        else:
            alpha = int((y - 1000) / 520 * 223) + 15
        draw.line((0, y, WIDTH, y), fill=(8, 10, 16, alpha))

    # Top dynamic athletic accent tick (replaces generic full-height yellow bar)
    draw.rounded_rectangle(
        (SAFE_LEFT, SAFE_TOP - 22, SAFE_LEFT + 68, SAFE_TOP - 17),
        radius=3,
        fill=GOLD_ACCENT,
    )
    return Image.alpha_composite(base, overlay)


def _quote_background(source: bytes | bytearray | Image.Image) -> Image.Image:
    """High-end journalistic editorial backdrop with cinematic vignette and deep slate quote bed."""
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Magazine editorial gradient: subtle top fade, deep atmospheric fade from mid-canvas down
    for y in range(HEIGHT):
        if y < 280:
            alpha = int((1.0 - y / 280) * 120)
        elif y < 720:
            alpha = 10
        elif y >= 1480:
            alpha = 242
        else:
            alpha = int((y - 720) / 760 * 232) + 10
        draw.line((0, y, WIDTH, y), fill=(7, 9, 14, alpha))

    # Outer perimeter vignette for editorial focus
    draw.rectangle((0, 0, 36, HEIGHT), fill=(5, 7, 10, 80))
    draw.rectangle((WIDTH - 36, 0, WIDTH, HEIGHT), fill=(5, 7, 10, 80))
    return Image.alpha_composite(base, overlay)


def _h2h_one_image_background(source: bytes | bytearray | Image.Image) -> Image.Image:
    """Broadcast clash atmosphere: Dual-tone split ambient glow (Cyan Left vs Gold Right)."""
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Darkening for text contrast
    for y in range(HEIGHT):
        if y < 340:
            alpha = int((1.0 - y / 340) * 170)
        elif y < 900:
            alpha = 30
        elif y >= 1460:
            alpha = 235
        else:
            alpha = int((y - 900) / 560 * 205) + 30
        draw.line((0, y, WIDTH, y), fill=(6, 8, 14, alpha))

    # Subtle dual-tone edge accents
    draw.rectangle((0, 0, 8, HEIGHT), fill=ELECTRIC_CYAN)
    draw.rectangle((WIDTH - 8, 0, WIDTH, HEIGHT), fill=GOLD_ACCENT)
    return Image.alpha_composite(base, overlay)


def _milestone_background(source: bytes | bytearray | Image.Image) -> Image.Image:
    """Prestige landmark / Hall of Fame atmosphere with gold landmark corner brackets."""
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Deep royal navy/dark charcoal gradient
    for y in range(HEIGHT):
        if y < 320:
            alpha = int((1.0 - y / 320) * 140)
        elif y < 920:
            alpha = 20
        elif y >= 1480:
            alpha = 240
        else:
            alpha = int((y - 920) / 560 * 220) + 20
        draw.line((0, y, WIDTH, y), fill=(8, 10, 18, alpha))

    # Heritage L-shaped brass/gold corner brackets
    c_len = 28
    c_thick = 3
    g_fill = (255, 218, 98, 140)
    # Top-Left
    draw.rectangle((SAFE_LEFT, SAFE_TOP - 20, SAFE_LEFT + c_len, SAFE_TOP - 20 + c_thick), fill=g_fill)
    draw.rectangle((SAFE_LEFT, SAFE_TOP - 20, SAFE_LEFT + c_thick, SAFE_TOP - 20 + c_len), fill=g_fill)
    # Top-Right
    draw.rectangle((SAFE_RIGHT - c_len, SAFE_TOP - 20, SAFE_RIGHT, SAFE_TOP - 20 + c_thick), fill=g_fill)
    draw.rectangle((SAFE_RIGHT - c_thick, SAFE_TOP - 20, SAFE_RIGHT, SAFE_TOP - 20 + c_len), fill=g_fill)
    # Bottom-Left
    draw.rectangle((SAFE_LEFT, SAFE_BOTTOM + 20 - c_thick, SAFE_LEFT + c_len, SAFE_BOTTOM + 20), fill=g_fill)
    draw.rectangle((SAFE_LEFT, SAFE_BOTTOM + 20 - c_len, SAFE_LEFT + c_thick, SAFE_BOTTOM + 20), fill=g_fill)
    # Bottom-Right
    draw.rectangle((SAFE_RIGHT - c_len, SAFE_BOTTOM + 20 - c_thick, SAFE_RIGHT, SAFE_BOTTOM + 20), fill=g_fill)
    draw.rectangle((SAFE_RIGHT - c_thick, SAFE_BOTTOM + 20 - c_len, SAFE_RIGHT, SAFE_BOTTOM + 20), fill=g_fill)
    return Image.alpha_composite(base, overlay)


# ---------------------------------------------------------------------------
# Distinct Header / Kicker Badges
# ---------------------------------------------------------------------------

def _stat_kicker(canvas: Image.Image, text: str) -> int:
    """Athletic badge pill with glowing neon amber telemetry indicator."""
    clean = " ".join(str(text or "").split()).upper() or "CAREER STAT"
    font = _font_label(27)
    draw_temp = ImageDraw.Draw(canvas)
    w, h = _measure(draw_temp, clean, font)
    pill_w = w + 54
    pill_h = h + 16
    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill)
    pdraw.rounded_rectangle(
        (0, 0, pill_w - 1, pill_h - 1),
        radius=8,
        fill=(14, 18, 28, 220),
        outline=(255, 210, 30, 90),
        width=1,
    )
    # Glowing amber indicator dot
    dot_y = pill_h // 2
    pdraw.ellipse((12, dot_y - 4, 20, dot_y + 4), fill=GOLD_ACCENT)
    pdraw.text((28, 7), clean, font=font, fill=WHITE)
    canvas.alpha_composite(pill, (SAFE_LEFT, SAFE_TOP - 8))
    return SAFE_TOP + 74


def _quote_kicker(canvas: Image.Image, text: str) -> int:
    """High-end journalistic editorial kicker with champagne fine-rule."""
    clean = " ".join(str(text or "").split()).upper() or "EXCLUSIVE REACTION"
    font = _font_label(26)
    draw = ImageDraw.Draw(canvas)
    w, h = _measure(draw, clean, font)

    # Gold diamond marker
    cy = SAFE_TOP + 8
    draw.polygon(
        [(SAFE_LEFT + 6, cy - 6), (SAFE_LEFT + 12, cy), (SAFE_LEFT + 6, cy + 6), (SAFE_LEFT, cy)],
        fill=PRESTIGE_GOLD,
    )
    draw.text((SAFE_LEFT + 22, SAFE_TOP - 4), clean, font=font, fill=PRESTIGE_GOLD)
    # Fine-line horizontal rule
    rule_x1 = SAFE_LEFT + 26 + w + 16
    if rule_x1 < SAFE_RIGHT:
        draw.line((rule_x1, cy, SAFE_RIGHT, cy), fill=(255, 255, 255, 38), width=1)
    return SAFE_TOP + 66


def _h2h_kicker(canvas: Image.Image, text: str) -> int:
    """Broadcast matchday clash header with dual-split accent underline."""
    clean = " ".join(str(text or "").split()).upper() or "HEAD TO HEAD"
    font = _font_label(28)
    draw = ImageDraw.Draw(canvas)
    w, h = _measure(draw, clean, font)

    pill_w = w + 44
    pill_h = h + 16
    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill)
    pdraw.rounded_rectangle(
        (0, 0, pill_w - 1, pill_h - 1),
        radius=8,
        fill=(14, 18, 28, 225),
        outline=(255, 255, 255, 36),
        width=1,
    )
    pdraw.text((22, 7), clean, font=font, fill=WHITE)
    canvas.alpha_composite(pill, (SAFE_LEFT, SAFE_TOP - 8))

    # Dual-color split underline (Cyan left, Gold right)
    line_y = SAFE_TOP + h + 18
    mid_x = SAFE_LEFT + 90
    draw.line((SAFE_LEFT, line_y, mid_x, line_y), fill=ELECTRIC_CYAN, width=4)
    draw.line((mid_x, line_y, mid_x + 90, line_y), fill=GOLD_ACCENT, width=4)
    return SAFE_TOP + 80


def _milestone_kicker(canvas: Image.Image, text: str) -> int:
    """Heritage landmark crest ribbon with star glyphs."""
    raw = " ".join(str(text or "").split()).upper() or "HISTORIC MILESTONE"
    clean = f"★ {raw} ★"
    font = _font_label(25)
    draw = ImageDraw.Draw(canvas)
    w, h = _measure(draw, clean, font)

    pill_w = w + 44
    pill_h = h + 16
    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill)
    pdraw.rounded_rectangle(
        (0, 0, pill_w - 1, pill_h - 1),
        radius=8,
        fill=(16, 20, 32, 230),
        outline=(255, 218, 98, 110),
        width=1,
    )
    pdraw.text((22, 6), clean, font=font, fill=PRESTIGE_GOLD)
    canvas.alpha_composite(pill, (SAFE_LEFT, SAFE_TOP - 8))
    return SAFE_TOP + 74


# ---------------------------------------------------------------------------
# Card 1: Stat Highlight
# ---------------------------------------------------------------------------

def _draw_stat_tile(
    canvas: Image.Image,
    y: int,
    index: int,
    label: str,
    value: str,
    x1: int = SAFE_LEFT,
    x2: int = SAFE_RIGHT,
) -> None:
    """Sleek horizontal athletic scorecard tile with left index notch and large bold value."""
    tile_w = x2 - x1
    tile_h = 88
    tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tile)

    # Glassmorphic rounded tile
    tdraw.rounded_rectangle(
        (0, 0, tile_w - 1, tile_h - 1),
        radius=10,
        fill=(14, 18, 28, 205),
        outline=(255, 255, 255, 28),
        width=1,
    )
    # Left athletic accent bar
    tdraw.rounded_rectangle((0, 0, 5, tile_h - 1), radius=2, fill=GOLD_ACCENT)

    # Index number
    idx_str = f"0{index}" if index < 10 else str(index)
    tdraw.text((18, 14), idx_str, font=_font_label(20), fill=(255, 210, 30, 160))

    # Metric label
    clean_label = " ".join(label.split()).upper()
    tdraw.text((48, 28), clean_label, font=_font_label(25, False), fill=MUTED)

    # Large bold metric value on right
    clean_val = " ".join(value.split())
    v_font = _font_headline(54)
    tdraw.text(
        (tile_w - 16, 16),
        clean_val,
        font=v_font,
        fill=WHITE,
        anchor="ra",
        stroke_width=2,
        stroke_fill=DARK,
    )
    canvas.alpha_composite(tile, (x1, y))


def _render_stat_highlight(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _stat_background(source)
    draw = ImageDraw.Draw(canvas)
    y = _stat_kicker(canvas, data.get("eyebrow") or "CAREER STAT")

    headline = " ".join(str(data.get("headline") or "").split())
    value = " ".join(str(data.get("value") or "").split())
    unit = " ".join(str(data.get("unit") or "").split())
    metrics = data.get("metrics") or []

    if not headline or not value:
        raise CardStudioError("Stat Highlight needs a headline and a hero value.")
    if len(metrics) > 3:
        raise CardStudioError("Stat Highlight supports at most three supporting metrics.")

    # Headline typography
    headline_font, headline_lines = _fit(
        draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 56, font_fn=_font_headline
    )
    headline_w, headline_h = _measure(draw, " ".join(headline_lines), headline_font)
    headline_x, headline_y = _best_text_position(
        subject_mask,
        headline_w,
        headline_h * len(headline_lines) + 8 * max(0, len(headline_lines) - 1),
        (SAFE_LEFT, y, SAFE_RIGHT, 720),
        SAFE_LEFT,
        y,
    )
    y = _draw_lines(
        canvas,
        headline_lines,
        headline_x,
        headline_y,
        headline_font,
        8,
        fill=WHITE,
        stroke_width=2,
        stroke_fill=DARK,
    ) + 40

    # Hero Stat Value with 3D Broadcast Depth Shadow
    value_font = _font_display(296)
    value_w, value_h = _measure(draw, value, value_font)
    if value_w > SAFE_RIGHT - SAFE_LEFT:
        value_font, _ = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 1, 240, 110, font_fn=_font_display)
        value_w, value_h = _measure(draw, value, value_font)

    unit_w, unit_h = _measure(draw, unit.upper(), _font_headline(40)) if unit else (0, 0)
    total_w = value_w + (unit_w + 22 if unit else 0)

    value_x, value_y = _best_text_position(
        subject_mask,
        total_w,
        value_h,
        (SAFE_LEFT, 640, SAFE_RIGHT, 1080),
        SAFE_LEFT,
        max(690, y),
    )

    # 3D Depth Shadow
    draw.text(
        (value_x + 6, value_y + 8),
        value,
        font=value_font,
        fill=DARK,
        stroke_width=3,
        stroke_fill=DARK,
    )
    draw.text(
        (value_x, value_y),
        value,
        font=value_font,
        fill=WHITE,
        stroke_width=2,
        stroke_fill=DARK,
    )

    # Floating Athletic Unit Badge
    if unit:
        pill_w = unit_w + 24
        pill_h = unit_h + 14
        unit_pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        updraw = ImageDraw.Draw(unit_pill)
        updraw.rounded_rectangle(
            (0, 0, pill_w - 1, pill_h - 1),
            radius=6,
            fill=GOLD_ACCENT,
            outline=DARK,
            width=1,
        )
        updraw.text((12, 6), unit.upper(), font=_font_headline(40), fill=DARK)
        canvas.alpha_composite(unit_pill, (value_x + value_w + 16, value_y + max(4, value_h - unit_h - 18)))

    # Segmented Scorecard Shelf
    metric_y = max(1120, value_y + value_h + 46)
    if metrics:
        for idx, metric in enumerate(metrics, 1):
            label = " ".join(str(metric.get("label") or "").split())
            metric_value = " ".join(str(metric.get("value") or "").split())
            if not label or not metric_value:
                raise CardStudioError("Every supporting metric needs a label and value.")
            _draw_stat_tile(canvas, metric_y, idx, label, metric_value)
            metric_y += 104

    return canvas


# ---------------------------------------------------------------------------
# Card 2: Quote / Reaction
# ---------------------------------------------------------------------------

def _render_quote_reaction(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _quote_background(source)
    draw = ImageDraw.Draw(canvas)
    y = _quote_kicker(canvas, data.get("eyebrow") or "POST-MATCH REACTION")

    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    # High-impact editorial quote block
    quote_font, quote_lines = _fit(draw, quote, SAFE_RIGHT - SAFE_LEFT - 32, 5, 108, 62, font_fn=_font_headline)
    line_h = _measure(draw, "Ag", quote_font)[1]
    quote_height = line_h * len(quote_lines) + 16 * max(0, len(quote_lines) - 1)
    quote_width = max(_measure(draw, line, quote_font)[0] for line in quote_lines)

    quote_x, quote_y = _best_text_position(
        subject_mask,
        quote_width + 48,
        quote_height + 40,
        (SAFE_LEFT, y, SAFE_RIGHT, 1080),
        SAFE_LEFT,
        410,
    )

    # Oversized decorative champagne quote glyph
    draw.text(
        (quote_x + 14, quote_y - 44),
        "“",
        font=_font_headline(118),
        fill=(245, 204, 82, 175),
    )

    # Vertical luxury gold accent quote rail
    draw.rounded_rectangle(
        (quote_x + 6, quote_y + 4, quote_x + 11, quote_y + quote_height + 4),
        radius=2,
        fill=PRESTIGE_GOLD,
    )

    # Quote lines in warm ivory with generous line spacing
    _draw_lines(
        canvas,
        quote_lines,
        quote_x + 28,
        quote_y,
        quote_font,
        16,
        fill=IVORY,
        stroke_width=2,
        stroke_fill=DARK,
    )

    # Speaker Plaque / Attribution Capsule
    speaker_y = quote_y + quote_height + 46
    card_w = SAFE_RIGHT - quote_x

    attr_font, attr_lines = _fit(draw, attribution, card_w - 36, 2, 50, 36, font_fn=_font_headline)
    context_font, context_lines = (
        _fit(draw, context, card_w - 36, 3, 34, 26, font_fn=_font_body)
        if context
        else (None, [])
    )

    attr_block_h = len(attr_lines) * 44 + 14
    context_block_h = (len(context_lines) * 36 + 18) if context_lines else 0
    plaque_h = attr_block_h + context_block_h + 16

    # Frosted Speaker Plaque Container
    plaque = Image.new("RGBA", (card_w, plaque_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plaque)
    pdraw.rounded_rectangle(
        (0, 0, card_w - 1, plaque_h - 1),
        radius=12,
        fill=(14, 18, 28, 225),
        outline=(245, 204, 82, 55),
        width=1,
    )
    # Gold top accent line on speaker plaque
    pdraw.rounded_rectangle((0, 0, card_w - 1, 3), radius=1, fill=PRESTIGE_GOLD)

    # Speaker Attribution
    py = 14
    for line in attr_lines:
        pdraw.text((18, py), line, font=attr_font, fill=WHITE)
        py += 44

    # Muted context copy
    if context_lines:
        pdraw.line((18, py + 4, card_w - 18, py + 4), fill=(255, 255, 255, 30), width=1)
        py += 14
        for line in context_lines:
            pdraw.text((18, py), line, font=context_font, fill=MUTED)
            py += 36

    canvas.alpha_composite(plaque, (quote_x, speaker_y))
    return canvas


# ---------------------------------------------------------------------------
# Card 3: Head-to-Head
# ---------------------------------------------------------------------------

def _split_image_source(source_pair, direction: str) -> Image.Image:
    if not isinstance(source_pair, (tuple, list)) or len(source_pair) != 2:
        raise CardStudioError("Two-image Head-to-Head needs two source images.")
    if direction == "Horizontal":
        height = HEIGHT // 2
        top = _cover(source_pair[0], WIDTH, height)
        bottom = _cover(source_pair[1], WIDTH, HEIGHT - height)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), DARK)
        canvas.paste(top, (0, 0))
        canvas.paste(bottom, (0, height))
        return canvas
    width = WIDTH // 2
    left = _cover(source_pair[0], width, HEIGHT)
    right = _cover(source_pair[1], WIDTH - width, HEIGHT)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), DARK)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (width, 0))
    return canvas


def _draw_vs_badge(canvas: Image.Image, cx: int, cy: int, radius: int = 42) -> None:
    """Broadcast metallic 3D 'VS' medallion with dual-tone ring."""
    d = radius * 2
    badge = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge)
    # Metallic dark core
    bdraw.ellipse((2, 2, d - 2, d - 2), fill=(12, 16, 24, 250), outline=GOLD_ACCENT, width=3)
    bdraw.ellipse((6, 6, d - 6, d - 6), outline=(255, 255, 255, 45), width=1)
    # Cyan accent arc on left, Gold arc on right
    bdraw.arc((3, 3, d - 3, d - 3), start=90, end=270, fill=ELECTRIC_CYAN, width=3)
    # Bold "VS" lettering
    vs_font = _font_headline(36)
    bdraw.text((radius, radius - 2), "VS", font=vs_font, fill=GOLD_ACCENT, anchor="mm")
    canvas.alpha_composite(badge, (cx - radius, cy - radius))


def _draw_h2h_duel_row(
    canvas: Image.Image,
    y: int,
    label: str,
    left_val: str,
    right_val: str,
    split_x: int,
) -> None:
    """Broadcast duel comparison scorecard row with central metric pill."""
    row_w = SAFE_RIGHT - SAFE_LEFT
    row_h = 88
    row = Image.new("RGBA", (row_w, row_h), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(row)

    # Base container
    rdraw.rounded_rectangle(
        (0, 0, row_w - 1, row_h - 1),
        radius=10,
        fill=(14, 18, 28, 210),
        outline=(255, 255, 255, 28),
        width=1,
    )

    rel_split = split_x - SAFE_LEFT

    # Center metric pill
    clean_lbl = " ".join(label.split()).upper()
    lbl_font = _font_label(22)
    lw, lh = _measure(rdraw, clean_lbl, lbl_font)
    pill_w = lw + 24
    pill_h = lh + 10
    rdraw.rounded_rectangle(
        (rel_split - pill_w // 2, (row_h - pill_h) // 2, rel_split + pill_w // 2, (row_h + pill_h) // 2),
        radius=6,
        fill=(22, 28, 42, 240),
        outline=(255, 255, 255, 32),
        width=1,
    )
    rdraw.text((rel_split, row_h // 2), clean_lbl, font=lbl_font, fill=MUTED, anchor="mm")

    # Left player value
    l_font = _font_headline(52)
    rdraw.text(
        (rel_split - pill_w // 2 - 16, row_h // 2),
        left_val,
        font=l_font,
        fill=WHITE,
        anchor="rm",
        stroke_width=2,
        stroke_fill=DARK,
    )

    # Right player value
    rdraw.text(
        (rel_split + pill_w // 2 + 16, row_h // 2),
        right_val,
        font=l_font,
        fill=WHITE,
        anchor="lm",
        stroke_width=2,
        stroke_fill=DARK,
    )

    canvas.alpha_composite(row, (SAFE_LEFT, y))


def _render_head_to_head(source, data: dict, subject_mask=None) -> Image.Image:
    headline = " ".join(str(data.get("headline") or "").split())
    left = data.get("left") or {}
    right = data.get("right") or {}
    metrics = list(data.get("metrics") or [])
    image_mode = str(data.get("image_mode") or "One image")
    direction = str(data.get("split_direction") or "Vertical")

    if not headline or not left.get("name") or not right.get("name"):
        raise CardStudioError("Head-to-Head needs a headline and both names.")
    if not 1 <= len(metrics) <= 3:
        raise CardStudioError("Head-to-Head needs one to three comparison metrics.")

    # Two Images Mode
    if image_mode == "Two images":
        canvas = _split_image_source(source, direction).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 36))

        if direction == "Horizontal":
            split = HEIGHT // 2
            draw.line((0, split, WIDTH, split), fill=(255, 255, 255, 140), width=4)
            _draw_vs_badge(canvas, WIDTH // 2, split, radius=42)
            left_region = (48, 90, 1032, split - 90)
            right_region = (48, split + 40, 1032, HEIGHT - 70)
        else:
            split = WIDTH // 2
            draw.line((split, 0, split, HEIGHT), fill=(255, 255, 255, 140), width=4)
            _draw_vs_badge(canvas, split, 740, radius=42)
            left_region = (48, 90, split - 34, HEIGHT - 90)
            right_region = (split + 34, 90, WIDTH - 48, HEIGHT - 90)

        headline_font, headline_lines = _fit(draw, headline, WIDTH - 96, 2, 88, 54, font_fn=_font_headline)
        headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
        headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 6 * (len(headline_lines) - 1)
        headline_x, headline_y = _best_text_position(
            subject_mask[0] if isinstance(subject_mask, (tuple, list)) else None,
            headline_width,
            headline_height,
            (48, 80, WIDTH - 48, min(620, HEIGHT - 120)),
            (WIDTH - headline_width) // 2,
            160,
        )
        _draw_lines(canvas, headline_lines, headline_x, headline_y, headline_font, 6)

        for region, side, side_accent in ((left_region, left, ELECTRIC_CYAN), (right_region, right, GOLD_ACCENT)):
            x1, y1, x2, y2 = region
            name_font, name_lines = _fit(draw, str(side["name"]), max(160, x2 - x1 - 36), 2, 62, 40, font_fn=_font_headline)
            name_width = max(_measure(draw, line, name_font)[0] for line in name_lines)
            name_height = _measure(draw, "Ag", name_font)[1] * len(name_lines) + 5 * (len(name_lines) - 1)
            side_mask = None
            if isinstance(subject_mask, (tuple, list)) and len(subject_mask) == 2:
                side_mask = subject_mask[0] if region is left_region else subject_mask[1]
            name_x, name_y = _best_text_position(
                side_mask,
                name_width + 12,
                name_height,
                region,
                x1,
                max(y1 + 80, y2 - 540),
            )
            draw.rectangle((name_x - 10, name_y + 4, name_x - 6, name_y + name_height - 4), fill=side_accent)
            _draw_lines(canvas, name_lines, name_x, name_y, name_font, 5)

            metric_y = name_y + name_height + 42
            side_values = side.get("values") or {}
            for label in metrics:
                metric_label = " ".join(str(label).split())
                value = " ".join(str(side_values.get(metric_label) or "").split())
                if not value:
                    raise CardStudioError(f"Both sides need a value for {metric_label}.")
                draw.text((x1, metric_y), metric_label.upper(), font=_font_label(24, False), fill=MUTED)
                value_font, _ = _fit(draw, value, max(120, x2 - x1), 1, 64, 38, font_fn=_font_headline)
                draw.text((x1, metric_y + 34), value, font=value_font, fill=WHITE, stroke_width=2, stroke_fill=DARK)
                metric_y += 108
        return canvas.convert("RGB")

    # One Image Mode
    canvas = _h2h_one_image_background(source)
    draw = ImageDraw.Draw(canvas)
    y = _h2h_kicker(canvas, data.get("eyebrow") or "HEAD TO HEAD")

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 56, font_fn=_font_headline)
    headline_w = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
    headline_h = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 7 * (len(headline_lines) - 1)
    headline_x, headline_y = _best_text_position(
        subject_mask,
        headline_w,
        headline_h,
        (SAFE_LEFT, y, SAFE_RIGHT, 700),
        SAFE_LEFT,
        y,
    )
    y = _draw_lines(canvas, headline_lines, headline_x, headline_y, headline_font, 7) + 38

    split_x = (SAFE_LEFT + SAFE_RIGHT) // 2

    # Player Names Row
    name_top = y
    # Left Player Badge
    draw.rounded_rectangle((SAFE_LEFT, name_top, split_x - 18, name_top + 92), radius=8, fill=(14, 20, 32, 210), outline=(64, 196, 255, 60), width=1)
    draw.rounded_rectangle((SAFE_LEFT, name_top, SAFE_LEFT + 4, name_top + 92), radius=2, fill=ELECTRIC_CYAN)
    l_name_font, l_name_lines = _fit(draw, str(left["name"]), split_x - SAFE_LEFT - 36, 2, 54, 36, font_fn=_font_headline)
    _draw_lines(canvas, l_name_lines, SAFE_LEFT + 18, name_top + 16, l_name_font, 4)

    # Right Player Badge
    draw.rounded_rectangle((split_x + 18, name_top, SAFE_RIGHT, name_top + 92), radius=8, fill=(14, 20, 32, 210), outline=(255, 190, 48, 60), width=1)
    draw.rounded_rectangle((SAFE_RIGHT - 4, name_top, SAFE_RIGHT, name_top + 92), radius=2, fill=GOLD_ACCENT)
    r_name_font, r_name_lines = _fit(draw, str(right["name"]), SAFE_RIGHT - split_x - 36, 2, 54, 36, font_fn=_font_headline)
    _draw_lines(canvas, r_name_lines, split_x + 28, name_top + 16, r_name_font, 4)

    # Central Dividing Seam & VS Medallion
    duel_y = name_top + 120
    duel_bottom = duel_y + len(metrics) * 102
    draw.line((split_x, duel_y - 20, split_x, duel_bottom + 10), fill=DIVIDER, width=2)
    _draw_vs_badge(canvas, split_x, name_top + 46, radius=32)

    # Comparison Duel Scorecard Rows
    left_values = left.get("values") or {}
    right_values = right.get("values") or {}
    for label in metrics:
        metric_label = " ".join(str(label).split())
        lval = " ".join(str(left_values.get(metric_label) or "").split())
        rval = " ".join(str(right_values.get(metric_label) or "").split())
        if not lval or not rval:
            raise CardStudioError(f"Both sides need a value for {metric_label}.")
        _draw_h2h_duel_row(canvas, duel_y, metric_label, lval, rval, split_x)
        duel_y += 102

    return canvas


# ---------------------------------------------------------------------------
# Card 4: Key Fact / Milestone
# ---------------------------------------------------------------------------

def _render_fact_milestone(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _milestone_background(source)
    draw = ImageDraw.Draw(canvas)
    y = _milestone_kicker(canvas, data.get("eyebrow") or "MILESTONE")

    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    # Monumental Milestone Number with Prestige Gold Fill and 3D Depth
    value_font, value_lines = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 2, 280, 104, font_fn=_font_display)
    value_width = max(_measure(draw, line, value_font)[0] for line in value_lines)
    value_height = _measure(draw, "Ag", value_font)[1] * len(value_lines) + 6 * (len(value_lines) - 1)
    value_x, value_y = _best_text_position(
        subject_mask,
        value_width,
        value_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 900),
        SAFE_LEFT,
        370,
    )

    # 3D Depth Shadow
    for line in value_lines:
        draw.text((value_x + 6, value_y + 8), line, font=value_font, fill=DARK, stroke_width=3, stroke_fill=DARK)
        draw.text((value_x, value_y), line, font=value_font, fill=PRESTIGE_GOLD, stroke_width=2, stroke_fill=DARK)
    y = value_y + value_height + 24

    # Prestige decorative divider below monumental number
    draw.line((SAFE_LEFT, y, SAFE_LEFT + 80, y), fill=PRESTIGE_GOLD, width=3)
    # Diamond accent at center of divider
    draw.polygon([(SAFE_LEFT + 80, y - 4), (SAFE_LEFT + 88, y), (SAFE_LEFT + 80, y + 4), (SAFE_LEFT + 72, y)], fill=PRESTIGE_GOLD)
    y += 28

    # Landmark Achievement Title
    label_font, label_lines = _fit(draw, label, SAFE_RIGHT - SAFE_LEFT - 24, 3, 76, 44, font_fn=_font_headline)
    label_width = max(_measure(draw, line, label_font)[0] for line in label_lines)
    label_height = _measure(draw, "Ag", label_font)[1] * len(label_lines) + 8 * (len(label_lines) - 1)
    label_x, label_y = _best_text_position(
        subject_mask,
        label_width + 24,
        label_height,
        (SAFE_LEFT, 850, SAFE_RIGHT, 1220),
        SAFE_LEFT,
        max(880, y),
    )

    # Left prestige gold accent notch
    draw.rounded_rectangle((label_x, label_y + 4, label_x + 5, label_y + label_height - 4), radius=2, fill=PRESTIGE_GOLD)
    y = _draw_lines(canvas, label_lines, label_x + 18, label_y, label_font, 8, fill=WHITE) + 30

    # Commemorative Hall-of-Fame Plaque Container for Context
    if context:
        context_font, context_lines = _fit(
            draw,
            context,
            SAFE_RIGHT - SAFE_LEFT - 40,
            4,
            38,
            26,
            font_fn=_font_body,
        )
        context_box_y = max(1240, y)
        context_h = len(context_lines) * 44 + 28
        plaque_w = SAFE_RIGHT - SAFE_LEFT
        cbox = Image.new("RGBA", (plaque_w, context_h), (0, 0, 0, 0))
        cbdraw = ImageDraw.Draw(cbox)

        # Commemorative Plaque Plate
        cbdraw.rounded_rectangle(
            (0, 0, plaque_w - 1, context_h - 1),
            radius=14,
            fill=(14, 18, 28, 220),
            outline=(255, 218, 98, 75),
            width=1,
        )
        # 4 Corner Brass Rivets
        for rx, ry in ((10, 10), (plaque_w - 10, 10), (10, context_h - 10), (plaque_w - 10, context_h - 10)):
            cbdraw.ellipse((rx - 3, ry - 3, rx + 3, ry + 3), fill=(255, 218, 98, 180))

        canvas.alpha_composite(cbox, (SAFE_LEFT, context_box_y))
        _draw_lines(canvas, context_lines, SAFE_LEFT + 20, context_box_y + 14, context_font, 8, fill=MUTED, stroke_width=1)

    return canvas


# ---------------------------------------------------------------------------
# Card Studio Dispatcher & Public API
# ---------------------------------------------------------------------------

def _render(card_type: str, source, data: dict, subject_mask=None) -> Image.Image:
    normalized = " ".join(str(card_type or "").split())
    if normalized == "Stat Highlight":
        return _render_stat_highlight(source, data, subject_mask)
    if normalized == "Quote / Reaction":
        return _render_quote_reaction(source, data, subject_mask)
    if normalized == "Head-to-Head":
        return _render_head_to_head(source, data, subject_mask)
    if normalized == "Key Fact / Milestone":
        return _render_fact_milestone(source, data, subject_mask)
    raise CardStudioError(f"Unknown card type: {normalized or 'None'}")


def render_card(card_type: str, source, data: dict, subject_mask=None) -> bytes:
    if card_type == "Text Subject Cutout":
        raise CardStudioError("Text Subject Cutout uses the approved shared subject-cutout editor.")
    frame = _render(card_type, source, data, subject_mask).convert("RGB")
    buffer = BytesIO()
    frame.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def card_data_for_type(card_type: str) -> dict:
    if card_type == "Stat Highlight":
        return {
            "eyebrow": "CAREER STAT",
            "headline": "A huge scoring run",
            "value": "1,203",
            "unit": "RUNS",
            "metrics": [
                {"label": "Matches", "value": "38"},
                {"label": "Average", "value": "46.27"},
                {"label": "Strike rate", "value": "132.4"},
            ],
        }
    if card_type == "Quote / Reaction":
        return {
            "eyebrow": "POST-MATCH REACTION",
            "quote": "We believed from the first ball.",
            "attribution": "Player Name · after the final",
            "context": "The reaction came after the latest match.",
        }
    if card_type == "Head-to-Head":
        return {
            "eyebrow": "HEAD TO HEAD",
            "headline": "Who has the edge?",
            "image_mode": "One image",
            "split_direction": "Vertical",
            "left": {
                "name": "Player A",
                "values": {"Runs": "1,020", "Average": "48.4", "Strike Rate": "132.4"},
            },
            "right": {
                "name": "Player B",
                "values": {"Runs": "934", "Average": "42.1", "Strike Rate": "121.8"},
            },
            "metrics": ["Runs", "Average", "Strike Rate"],
        }
    if card_type == "Key Fact / Milestone":
        return {
            "eyebrow": "MILESTONE",
            "value": "100",
            "label": "International appearances",
            "context": "A landmark reached in the latest match.",
        }
    return {}
