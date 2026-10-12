"""16:9 Widescreen Card Studio for Long-form Cricket Productions.

Produces broadcast-grade 1920x1080 editorial visual frames for 8-minute documentaries.
Shares the signature obsidian/gold/cyan palette of the Shorts Card Studio while
featuring widescreen asymmetric split-screen compositions, multi-metric telemetry,
horizontal timeline tracks, and cinematic chapter cards.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1920
HEIGHT = 1080

SAFE_LEFT = 120
SAFE_RIGHT = 1800
SAFE_TOP = 90
SAFE_BOTTOM = 990

# Shared Signature Palette (Elevated for 16:9 Broadcast)
GOLD_ACCENT = (255, 210, 30)         # Athletic vibrant gold
PRESTIGE_GOLD = (255, 218, 98)       # Luxury milestone / champagne gold
ELECTRIC_CYAN = (64, 196, 255)       # H2H Player 1 / cool telemetry tone
CRIMSON_ACCENT = (255, 102, 68)      # H2H Player 2 / warm rivalry tone
WHITE = (248, 250, 252)              # Crisp primary text
IVORY = (255, 252, 246)              # Editorial warm quote text
MUTED = (195, 201, 209)              # Secondary labels and metrics
SUBTLE = (140, 150, 166)             # Tertiary annotations
DARK = (6, 8, 12)                    # Deep obsidian shadow / stroke
CARD_BG = (14, 18, 28, 230)          # Glassmorphic dark telemetry panel
CARD_BORDER = (255, 255, 255, 32)
DIVIDER = (255, 255, 255, 36)

CARD_TYPES = (
    "Stat Highlight",
    "Quote / Reaction",
    "Head-to-Head",
    "Key Fact / Milestone",
    "Chapter / Act",
    "Timeline / Chronology",
)


class LongformCardError(ValueError):
    """Raised when a Long-form card cannot be rendered cleanly."""


def _open_image(source: bytes | bytearray | Image.Image | None) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(source))) as image:
                return image.convert("RGB")
        except (OSError, ValueError) as exc:
            raise LongformCardError("The selected source image could not be opened.") from exc
    # If None, create a deep cinematic dark canvas with subtle gradient
    base = Image.new("RGB", (WIDTH, HEIGHT), (10, 14, 22))
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        alpha = int(12 + (y / HEIGHT) * 18)
        draw.line((0, y, WIDTH, y), fill=(18 + alpha, 24 + alpha, 38 + alpha))
    return base


def _cover(source: bytes | bytearray | Image.Image | None, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
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
    names = ("Oswald-Bold.ttf", "BarlowCondensed-Black.ttf", "Anton-Regular.ttf") if bold else ("Barlow-Regular.ttf", "Oswald-Bold.ttf")
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
    raise LongformCardError("The card text is too long for this layout. Shorten the copy.")


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
    shadow_offset: tuple[int, int] = (3, 4),
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


# ---------------------------------------------------------------------------
# Background Treatments for 16:9 Widescreen
# ---------------------------------------------------------------------------

def _widescreen_backdrop(source: bytes | bytearray | Image.Image | None, side: str = "right") -> Image.Image:
    """Creates a 16:9 broadcast backdrop with subject focus and gradient protection.
    
    If side='right', the photo subject sits on the right, protected by an obsidian
    gradient on the left for text and telemetry.
    """
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Horizontal asymmetric gradient
    for x in range(WIDTH):
        if side == "right":
            # Dark telemetry panel on left, photo revealed on right
            if x < 720:
                alpha = 245
            elif x > 1440:
                alpha = 60
            else:
                progress = (x - 720) / 720
                alpha = int(245 - progress * 185)
        elif side == "left":
            # Photo on left, dark telemetry panel on right
            if x < 480:
                alpha = 60
            elif x > 1200:
                alpha = 245
            else:
                progress = (x - 480) / 720
                alpha = int(60 + progress * 185)
        else:
            # Full center atmospheric vignette
            alpha = 180
        draw.line((x, 0, x, HEIGHT), fill=(10, 14, 24, alpha))

    # Top and bottom broadcast letterbox fade
    for y in range(HEIGHT):
        if y < 140:
            a = int((1.0 - y / 140) * 160)
            draw.line((0, y, WIDTH, y), fill=(6, 8, 14, a))
        elif y > HEIGHT - 140:
            a = int(((y - (HEIGHT - 140)) / 140) * 200)
            draw.line((0, y, WIDTH, y), fill=(6, 8, 14, a))

    return Image.alpha_composite(base, overlay)


# ---------------------------------------------------------------------------
# 1. Long-form Stat Highlight Card (1920x1080)
# ---------------------------------------------------------------------------

def render_longform_stat_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a 16:9 Stat Highlight Card with hero metric and telemetry grid."""
    player_name = " ".join(str(data.get("player_name") or data.get("headline") or "PLAYER STAT").split()).upper()
    eyebrow = " ".join(str(data.get("eyebrow") or "DEEP-DIVE TELEMETRY").split()).upper()
    hero_stat = " ".join(str(data.get("hero_stat") or data.get("stat") or "0.0").split())
    stat_label = " ".join(str(data.get("stat_label") or data.get("metric") or "METRIC RECORD").split()).upper()
    context_note = " ".join(str(data.get("context_note") or data.get("note") or "").split())
    tiles = list(data.get("tiles") or data.get("metrics") or [])

    canvas = _widescreen_backdrop(source, side="right")
    draw = ImageDraw.Draw(canvas)

    # Left Telemetry Panel
    panel_x1 = SAFE_LEFT
    panel_y1 = SAFE_TOP + 20
    panel_w = 980
    panel_h = SAFE_BOTTOM - panel_y1

    panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle(
        (0, 0, panel_w - 1, panel_h - 1),
        radius=16,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=1,
    )
    # Subtle top edge gold highlight
    pdraw.line((32, 0, 240, 0), fill=GOLD_ACCENT, width=3)
    canvas.alpha_composite(panel, (panel_x1, panel_y1))

    # Eyebrow / Kicker Pill
    pill_font = _font_label(22)
    pw, ph = _measure(draw, eyebrow, pill_font)
    pill = Image.new("RGBA", (pw + 46, ph + 14), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill)
    pill_draw.rounded_rectangle((0, 0, pw + 45, ph + 13), radius=6, fill=(22, 28, 42, 240), outline=(255, 210, 30, 90), width=1)
    pill_draw.ellipse((10, (ph + 14) // 2 - 4, 18, (ph + 14) // 2 + 4), fill=GOLD_ACCENT)
    pill_draw.text((26, 6), eyebrow, font=pill_font, fill=WHITE)
    canvas.alpha_composite(pill, (panel_x1 + 36, panel_y1 + 36))

    # Player / Subject Name Headline
    cur_y = panel_y1 + 86
    name_font, name_lines = _fit(draw, player_name, panel_w - 72, 2, 74, 46, font_fn=_font_headline)
    cur_y = _draw_lines(canvas, name_lines, panel_x1 + 36, cur_y, name_font, gap=4, fill=WHITE)

    # Hero Stat Row (Giant Numerals + Label Block)
    cur_y += 18
    hero_font = _font_display(136)
    hw, hh = _measure(draw, hero_stat, hero_font)
    draw.text(
        (panel_x1 + 36, cur_y),
        hero_stat,
        font=hero_font,
        fill=GOLD_ACCENT,
        stroke_width=3,
        stroke_fill=DARK,
    )

    # Metric Label next to or below hero stat
    lbl_font, lbl_lines = _fit(draw, stat_label, panel_w - hw - 90, 3, 36, 24, font_fn=_font_headline)
    _draw_lines(canvas, lbl_lines, panel_x1 + 54 + hw, cur_y + 14, lbl_font, gap=4, fill=WHITE)
    cur_y += max(hh, 120) + 24

    # Secondary Metric Tiles Grid (2 or 3 modular tiles)
    if tiles:
        tile_w = (panel_w - 72 - (len(tiles[:3]) - 1) * 16) // len(tiles[:3])
        tile_h = 110
        tx = panel_x1 + 36
        for item in tiles[:3]:
            t_label = " ".join(str(item.get("label") or "").split()).upper()
            t_val = " ".join(str(item.get("value") or "").split())
            t_tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(t_tile)
            tdraw.rounded_rectangle((0, 0, tile_w - 1, tile_h - 1), radius=8, fill=(20, 26, 38, 220), outline=(255, 255, 255, 24), width=1)
            # Label
            tdraw.text((16, 12), t_label, font=_font_label(20, False), fill=MUTED)
            # Value
            v_font, _ = _fit(tdraw, t_val, tile_w - 32, 1, 46, 28, font_fn=_font_headline)
            tdraw.text((16, 42), t_val, font=v_font, fill=WHITE)
            canvas.alpha_composite(t_tile, (tx, cur_y))
            tx += tile_w + 16
        cur_y += tile_h + 24

    # Contextual Editorial Note
    if context_note:
        note_font, note_lines = _fit(draw, context_note, panel_w - 72, 2, 26, 20, bold=False, font_fn=_font_body)
        draw.line((panel_x1 + 36, cur_y, panel_x1 + panel_w - 36, cur_y), fill=DIVIDER, width=1)
        cur_y += 14
        _draw_lines(canvas, note_lines, panel_x1 + 36, cur_y, note_font, gap=4, fill=SUBTLE, shadow_offset=(1, 2))

    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# 2. Long-form Quote / Reaction Card (1920x1080)
# ---------------------------------------------------------------------------

def render_longform_quote_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a 16:9 Quote / Reaction Card with editorial quotation layout."""
    quote_text = " ".join(str(data.get("quote") or data.get("text") or "").split())
    speaker_name = " ".join(str(data.get("speaker") or data.get("attribution") or "CRICKET INSIDER").split()).upper()
    speaker_role = " ".join(str(data.get("role") or data.get("context") or "STATEMENT").split()).upper()
    eyebrow = " ".join(str(data.get("eyebrow") or "EXCLUSIVE STATEMENT").split()).upper()

    if not quote_text:
        raise LongformCardError("Quote Card requires quote text.")

    canvas = _widescreen_backdrop(source, side="right")
    draw = ImageDraw.Draw(canvas)

    panel_x1 = SAFE_LEFT
    panel_y1 = SAFE_TOP + 30
    panel_w = 1040
    panel_h = SAFE_BOTTOM - panel_y1 - 20

    panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle((0, 0, panel_w - 1, panel_h - 1), radius=16, fill=CARD_BG, outline=CARD_BORDER, width=1)
    # Prestige gold vertical accent bar
    pdraw.rounded_rectangle((0, 24, 6, panel_h - 24), radius=3, fill=PRESTIGE_GOLD)
    canvas.alpha_composite(panel, (panel_x1, panel_y1))

    # Kicker with champagne diamond marker
    cy = panel_y1 + 44
    draw.polygon([(panel_x1 + 38, cy - 5), (panel_x1 + 44, cy), (panel_x1 + 38, cy + 5), (panel_x1 + 32, cy)], fill=PRESTIGE_GOLD)
    draw.text((panel_x1 + 54, panel_y1 + 34), eyebrow, font=_font_label(22), fill=PRESTIGE_GOLD)

    # Big quotation mark glyph
    q_font = _font_display(108)
    draw.text((panel_x1 + 36, panel_y1 + 72), "“", font=q_font, fill=GOLD_ACCENT)

    # Authoritative Quote Text
    quote_x = panel_x1 + 36
    quote_y = panel_y1 + 140
    quote_font, quote_lines = _fit(draw, f'"{quote_text}"', panel_w - 72, 5, 52, 30, bold=False, font_fn=_font_body)
    quote_y = _draw_lines(canvas, quote_lines, quote_x, quote_y, quote_font, gap=8, fill=IVORY, shadow_offset=(2, 3))

    # Speaker Attribution Plaque at Bottom of Panel
    attr_y = max(quote_y + 24, panel_y1 + panel_h - 120)
    draw.line((quote_x, attr_y - 12, panel_x1 + panel_w - 36, attr_y - 12), fill=DIVIDER, width=1)

    draw.text((quote_x, attr_y), speaker_name, font=_font_headline(38), fill=WHITE)
    if speaker_role:
        draw.text((quote_x, attr_y + 42), speaker_role, font=_font_label(22, False), fill=MUTED)

    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# 3. Long-form Head-to-Head Split Card (1920x1080)
# ---------------------------------------------------------------------------

def render_longform_h2h_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a 16:9 Head-to-Head Split Card with dual player comparisons."""
    headline = " ".join(str(data.get("headline") or "TACTICAL SHOWDOWN").split()).upper()
    left_name = " ".join(str(data.get("left_name") or data.get("left", {}).get("name") or "PLAYER 1").split()).upper()
    right_name = " ".join(str(data.get("right_name") or data.get("right", {}).get("name") or "PLAYER 2").split()).upper()
    metrics = list(data.get("metrics") or [])

    if not metrics:
        metrics = [
            {"label": "TEST AVERAGE", "left": "52.4", "right": "48.2"},
            {"label": "STRIKE RATE", "left": "78.9", "right": "84.1"},
            {"label": "MATCH WINS", "left": "44", "right": "39"},
        ]

    canvas = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Asymmetrical dual-color split atmosphere (Cyan left, Crimson/Gold right)
    for x in range(WIDTH):
        if x < WIDTH // 2:
            progress = x / (WIDTH // 2)
            alpha = int(180 + (1.0 - progress) * 50)
            odraw.line((x, 0, x, HEIGHT), fill=(10, 20, 36, alpha))
        else:
            progress = (x - WIDTH // 2) / (WIDTH // 2)
            alpha = int(180 + progress * 50)
            odraw.line((x, 0, x, HEIGHT), fill=(36, 16, 14, alpha))

    # Top/Bottom dark vignette
    for y in range(HEIGHT):
        if y < 140:
            odraw.line((0, y, WIDTH, y), fill=(6, 8, 14, int((1.0 - y / 140) * 160)))
        elif y > HEIGHT - 140:
            odraw.line((0, y, WIDTH, y), fill=(6, 8, 14, int(((y - (HEIGHT - 140)) / 140) * 180)))

    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # Top Center Title
    head_font, head_lines = _fit(draw, headline, 1200, 1, 56, 38, font_fn=_font_headline)
    hw, hh = _measure(draw, head_lines[0], head_font)
    draw.text(((WIDTH - hw) // 2, SAFE_TOP), head_lines[0], font=head_font, fill=WHITE)

    # Player Names
    p1_font, p1_lines = _fit(draw, left_name, 560, 1, 62, 40, font_fn=_font_headline)
    draw.text((SAFE_LEFT + 40, SAFE_TOP + 70), p1_lines[0], font=p1_font, fill=ELECTRIC_CYAN)

    p2_font, p2_lines = _fit(draw, right_name, 560, 1, 62, 40, font_fn=_font_headline)
    p2_w, _ = _measure(draw, p2_lines[0], p2_font)
    draw.text((SAFE_RIGHT - 40 - p2_w, SAFE_TOP + 70), p2_lines[0], font=p2_font, fill=CRIMSON_ACCENT)

    # Center Metallic VS Medallion
    vs_cx, vs_cy = WIDTH // 2, SAFE_TOP + 95
    vs_rad = 38
    vs_badge = Image.new("RGBA", (vs_rad * 2, vs_rad * 2), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(vs_badge)
    bdraw.ellipse((2, 2, vs_rad * 2 - 2, vs_rad * 2 - 2), fill=(14, 18, 28, 245), outline=GOLD_ACCENT, width=2)
    bdraw.arc((3, 3, vs_rad * 2 - 3, vs_rad * 2 - 3), start=90, end=270, fill=ELECTRIC_CYAN, width=3)
    bdraw.text((vs_rad, vs_rad - 2), "VS", font=_font_headline(32), fill=GOLD_ACCENT, anchor="mm")
    canvas.alpha_composite(vs_badge, (vs_cx - vs_rad, vs_cy - vs_rad))

    # Center Comparison Card Container
    comp_w = 1100
    comp_h = len(metrics[:4]) * 105 + 40
    comp_x = (WIDTH - comp_w) // 2
    comp_y = SAFE_TOP + 170

    comp_panel = Image.new("RGBA", (comp_w, comp_h), (0, 0, 0, 0))
    cp_draw = ImageDraw.Draw(comp_panel)
    cp_draw.rounded_rectangle((0, 0, comp_w - 1, comp_h - 1), radius=16, fill=CARD_BG, outline=CARD_BORDER, width=1)
    canvas.alpha_composite(comp_panel, (comp_x, comp_y))

    # Metric Rows
    row_y = comp_y + 20
    for row in metrics[:4]:
        lbl = " ".join(str(row.get("label") or "").split()).upper()
        l_val = " ".join(str(row.get("left") or "").split())
        r_val = " ".join(str(row.get("right") or "").split())

        # Central metric pill
        lbl_font = _font_label(22)
        lw, lh = _measure(draw, lbl, lbl_font)
        pill_w = lw + 28
        pill_h = lh + 10
        mid_x = WIDTH // 2
        pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(pill)
        pdraw.rounded_rectangle((0, 0, pill_w - 1, pill_h - 1), radius=6, fill=(24, 30, 44, 240), outline=(255, 255, 255, 30), width=1)
        pdraw.text((pill_w // 2, pill_h // 2), lbl, font=lbl_font, fill=MUTED, anchor="mm")
        canvas.alpha_composite(pill, (mid_x - pill_w // 2, row_y + 26))

        # Left Player Stat
        v_font = _font_headline(54)
        draw.text((mid_x - pill_w // 2 - 24, row_y + 36), l_val, font=v_font, fill=WHITE, anchor="rm", stroke_width=2, stroke_fill=DARK)

        # Right Player Stat
        draw.text((mid_x + pill_w // 2 + 24, row_y + 36), r_val, font=v_font, fill=WHITE, anchor="lm", stroke_width=2, stroke_fill=DARK)

        row_y += 105

    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# 4. Long-form Key Fact / Milestone Card (1920x1080)
# ---------------------------------------------------------------------------

def render_longform_milestone_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a 16:9 Landmark Milestone Card with prestige heritage styling."""
    title = " ".join(str(data.get("title") or data.get("headline") or "HISTORIC MILESTONE").split()).upper()
    milestone_badge = " ".join(str(data.get("milestone") or data.get("badge") or "RECORD").split()).upper()
    subtitle = " ".join(str(data.get("subtitle") or "").split())
    bullet_points = list(data.get("bullets") or data.get("facts") or [])

    canvas = _widescreen_backdrop(source, side="right")
    draw = ImageDraw.Draw(canvas)

    panel_x1 = SAFE_LEFT
    panel_y1 = SAFE_TOP + 30
    panel_w = 1000
    panel_h = SAFE_BOTTOM - panel_y1 - 20

    panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle((0, 0, panel_w - 1, panel_h - 1), radius=16, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # Heritage brass corner brackets
    c_len = 24
    c_thick = 3
    g_fill = (255, 218, 98, 140)
    pdraw.rectangle((16, 16, 16 + c_len, 16 + c_thick), fill=g_fill)
    pdraw.rectangle((16, 16, 16 + c_thick, 16 + c_len), fill=g_fill)
    pdraw.rectangle((panel_w - 16 - c_len, 16, panel_w - 16, 16 + c_thick), fill=g_fill)
    pdraw.rectangle((panel_w - 16 - c_thick, 16, panel_w - 16, 16 + c_len), fill=g_fill)
    canvas.alpha_composite(panel, (panel_x1, panel_y1))

    # Milestone Badge Ribbon
    kicker_font = _font_label(22)
    ribbon_text = f"★ {milestone_badge} ★"
    rw, rh = _measure(draw, ribbon_text, kicker_font)
    ribbon = Image.new("RGBA", (rw + 36, rh + 12), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(ribbon)
    rdraw.rounded_rectangle((0, 0, rw + 35, rh + 11), radius=6, fill=(24, 30, 48, 240), outline=PRESTIGE_GOLD, width=1)
    rdraw.text((rw // 2 + 18, rh // 2 + 6), ribbon_text, font=kicker_font, fill=PRESTIGE_GOLD, anchor="mm")
    canvas.alpha_composite(ribbon, (panel_x1 + 44, panel_y1 + 40))

    # Big Milestone Headline
    cur_y = panel_y1 + 96
    title_font, title_lines = _fit(draw, title, panel_w - 88, 2, 64, 42, font_fn=_font_headline)
    cur_y = _draw_lines(canvas, title_lines, panel_x1 + 44, cur_y, title_font, gap=6, fill=WHITE)

    if subtitle:
        sub_font, sub_lines = _fit(draw, subtitle, panel_w - 88, 2, 28, 20, bold=False, font_fn=_font_body)
        cur_y += 8
        cur_y = _draw_lines(canvas, sub_lines, panel_x1 + 44, cur_y, sub_font, gap=4, fill=SUBTLE)

    # Bullet Points / Key Impacts
    if bullet_points:
        cur_y += 24
        draw.line((panel_x1 + 44, cur_y, panel_x1 + panel_w - 44, cur_y), fill=DIVIDER, width=1)
        cur_y += 20
        for bp in bullet_points[:3]:
            bp_clean = " ".join(str(bp).split())
            bp_font, bp_lines = _fit(draw, bp_clean, panel_w - 120, 2, 28, 20, bold=False, font_fn=_font_body)
            # Gold diamond bullet
            draw.polygon([(panel_x1 + 48, cur_y + 12), (panel_x1 + 54, cur_y + 18), (panel_x1 + 48, cur_y + 24), (panel_x1 + 42, cur_y + 18)], fill=PRESTIGE_GOLD)
            cur_y = _draw_lines(canvas, bp_lines, panel_x1 + 68, cur_y, bp_font, gap=4, fill=WHITE, shadow_offset=(1, 2))
            cur_y += 12

    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# 5. Long-form Chapter / Act Title Card (1920x1080) [New for Long-form]
# ---------------------------------------------------------------------------

def render_longform_chapter_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a cinematic Chapter Title Card signaling an act transition in an 8-min video."""
    act_num = " ".join(str(data.get("act") or data.get("chapter_number") or "ACT 01").split()).upper()
    act_title = " ".join(str(data.get("title") or data.get("chapter_title") or "THE CATALYST").split()).upper()
    premise = " ".join(str(data.get("premise") or data.get("summary") or "").split())
    runtime = " ".join(str(data.get("timestamp") or data.get("runtime") or "").split())

    canvas = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Deep obsidian cinematic vignette
    for y in range(HEIGHT):
        progress = abs(y - HEIGHT // 2) / (HEIGHT // 2)
        alpha = int(210 + progress * 40)
        odraw.line((0, y, WIDTH, y), fill=(8, 10, 16, alpha))

    # Center spotlight illumination
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # Act Badge Pill
    pill_font = _font_label(26)
    pw, ph = _measure(draw, act_num, pill_font)
    pill = Image.new("RGBA", (pw + 48, ph + 16), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill)
    pdraw.rounded_rectangle((0, 0, pw + 47, ph + 15), radius=8, fill=(20, 26, 40, 240), outline=GOLD_ACCENT, width=1)
    pdraw.text((pw // 2 + 24, ph // 2 + 8), act_num, font=pill_font, fill=GOLD_ACCENT, anchor="mm")
    canvas.alpha_composite(pill, ((WIDTH - (pw + 48)) // 2, HEIGHT // 2 - 160))

    # Big Cinematic Chapter Headline
    head_font, head_lines = _fit(draw, act_title, 1400, 2, 92, 54, font_fn=_font_headline)
    cur_y = HEIGHT // 2 - 80
    for line in head_lines:
        lw, lh = _measure(draw, line, head_font)
        draw.text(((WIDTH - lw) // 2, cur_y), line, font=head_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
        cur_y += lh + 10

    # Premise / Core Conflict Subtitle
    if premise:
        cur_y += 18
        p_font, p_lines = _fit(draw, premise, 1100, 2, 34, 22, bold=False, font_fn=_font_body)
        for line in p_lines:
            pw, ph = _measure(draw, line, p_font)
            draw.text(((WIDTH - pw) // 2, cur_y), line, font=p_font, fill=MUTED)
            cur_y += ph + 6

    # Timestamp badge at bottom center
    if runtime:
        draw.text((WIDTH // 2, HEIGHT - 120), runtime, font=_font_label(22, False), fill=SUBTLE, anchor="mm")

    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# 6. Long-form Timeline / Chronology Card (1920x1080) [New for Long-form]
# ---------------------------------------------------------------------------

def render_longform_timeline_card(source: bytes | bytearray | Image.Image | None, data: dict) -> Image.Image:
    """Renders a 16:9 Horizontal Chronological Track showing how events unfolded."""
    headline = " ".join(str(data.get("headline") or "CHRONOLOGY OF EVENTS").split()).upper()
    nodes = list(data.get("nodes") or data.get("events") or [])

    if not nodes:
        nodes = [
            {"date": "STAGE 1", "title": "The Incident", "desc": "Initial reports emerge during morning practice."},
            {"date": "STAGE 2", "title": "Medical Scan", "desc": "Swelling confirmed; hospital scans advise mandatory rest."},
            {"date": "STAGE 3", "title": "BCCI Statement", "desc": "Selectors officially name Bumrah as stand-in captain."},
        ]

    canvas = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Atmospheric dark background
    odraw.rectangle((0, 0, WIDTH, HEIGHT), fill=(10, 14, 24, 235))
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # Top Header
    head_font = _font_headline(54)
    hw, hh = _measure(draw, headline, head_font)
    draw.text((SAFE_LEFT, SAFE_TOP + 20), headline, font=head_font, fill=WHITE)
    draw.line((SAFE_LEFT, SAFE_TOP + 86, SAFE_LEFT + hw, SAFE_TOP + 86), fill=GOLD_ACCENT, width=3)

    # Horizontal Timeline Track Coordinates
    count = min(4, max(2, len(nodes)))
    track_y = HEIGHT // 2 - 40
    start_x = SAFE_LEFT + 80
    end_x = SAFE_RIGHT - 80
    spacing = (end_x - start_x) // (count - 1)

    # Draw Connecting Horizontal Track Line
    draw.line((start_x, track_y, end_x, track_y), fill=(255, 255, 255, 60), width=4)

    # Draw Event Nodes
    for idx, node in enumerate(nodes[:count]):
        nx = start_x + idx * spacing
        date_lbl = " ".join(str(node.get("date") or f"STEP {idx+1}").split()).upper()
        node_title = " ".join(str(node.get("title") or "").split())
        node_desc = " ".join(str(node.get("desc") or "").split())

        # Glowing Node Circle
        node_badge = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        nb_draw = ImageDraw.Draw(node_badge)
        nb_draw.ellipse((0, 0, 47, 47), fill=(18, 24, 38, 250), outline=GOLD_ACCENT, width=3)
        nb_draw.ellipse((14, 14, 33, 33), fill=GOLD_ACCENT)
        canvas.alpha_composite(node_badge, (nx - 24, track_y - 24))

        # Date Label Above Node
        d_font = _font_label(24)
        dw, dh = _measure(draw, date_lbl, d_font)
        draw.text((nx, track_y - 48), date_lbl, font=d_font, fill=PRESTIGE_GOLD, anchor="mm")

        # Event Description Card Below Node
        card_w = min(360, spacing - 30)
        card_h = 240
        card_x = nx - card_w // 2
        card_y = track_y + 48

        c_panel = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        cp_draw = ImageDraw.Draw(c_panel)
        cp_draw.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=12, fill=CARD_BG, outline=CARD_BORDER, width=1)
        canvas.alpha_composite(c_panel, (card_x, card_y))

        # Title
        t_font, t_lines = _fit(draw, node_title, card_w - 36, 2, 34, 22, font_fn=_font_headline)
        ty = _draw_lines(canvas, t_lines, card_x + 18, card_y + 18, t_font, gap=4, fill=WHITE)

        # Description
        if node_desc:
            desc_font, desc_lines = _fit(draw, node_desc, card_w - 36, 4, 22, 16, bold=False, font_fn=_font_body)
            _draw_lines(canvas, desc_lines, card_x + 18, ty + 10, desc_font, gap=3, fill=MUTED)

    return canvas.convert("RGB")
