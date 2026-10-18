"""Editorial Card Studio for Final-Shorts.

Builds 1080x1920 sports-magazine frames with photo-led, subject-aware layouts.
Text Subject Cutout intentionally remains on its existing shared editor path.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


WIDTH = 1080
HEIGHT = 1920

# Respect the right-side Shorts controls and lower interface overlays.
SAFE_LEFT = 76
SAFE_TOP = 190
SAFE_RIGHT = 864
SAFE_BOTTOM = 1460
CONTENT_WIDTH = 520

# Editorial palette: photography, ink, white, and one restrained signal accent.
INK = (12, 15, 19)
ACCENT = (244, 202, 61)
WHITE = (250, 249, 245)
MUTED = (199, 201, 199)
DARK = INK
CARD_BG = (12, 15, 19, 232)

CARD_TYPES = (
    "Text Subject Cutout",
    "Stat Highlight",
    "Quote / Reaction",
    "Head-to-Head",
    "Key Fact / Milestone",
)
TEST_CARD_TYPES = CARD_TYPES
LIVE_CARD_TYPES = CARD_TYPES


class CardStudioError(ValueError):
    """Raised when a Card Studio frame cannot be rendered cleanly."""



def invalidate_card_studio_results_for_source(session_state, asset_key: str) -> int:
    """Discard rendered card previews that used a source image whose crop changed."""
    invalidated = 0
    for state_key in list(session_state.keys()):
        if not state_key.endswith("-result"):
            continue
        result = session_state.get(state_key)
        if not isinstance(result, dict) or result.get("bytes") is None:
            continue
        source_keys = result.get("source_keys")
        if not isinstance(source_keys, (list, tuple, set)):
            source_keys = (result.get("source_key"),)
        if asset_key in source_keys:
            session_state[state_key] = None
            invalidated += 1
    return invalidated


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


def _cover_crop_box(source_size: tuple[int, int], width: int, height: int) -> tuple[int, int, int, int]:
    """Return the exact centre-crop box used for both the photograph and its mask."""
    source_width, source_height = source_size
    target_ratio = width / height
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        crop_width = max(1, int(source_height * target_ratio))
        left = (source_width - crop_width) // 2
        return left, 0, left + crop_width, source_height
    if source_ratio < target_ratio:
        crop_height = max(1, int(source_width / target_ratio))
        top = (source_height - crop_height) // 2
        return 0, top, source_width, top + crop_height
    return 0, 0, source_width, source_height


def _cover_with_mask(
    source: bytes | bytearray | Image.Image,
    subject_mask: Image.Image | None,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> tuple[Image.Image, Image.Image | None]:
    """Fit the image and mask through the same crop/resize transform."""
    image = _open_image(source)
    mask = subject_mask.convert("L") if isinstance(subject_mask, Image.Image) else None
    if mask is not None and mask.size != image.size:
        mask = mask.resize(image.size, Image.Resampling.BILINEAR)

    crop_box = _cover_crop_box(image.size, width, height)
    image = image.crop(crop_box).resize((width, height), Image.Resampling.LANCZOS)
    if mask is not None:
        mask = mask.crop(crop_box).resize((width, height), Image.Resampling.BILINEAR)
    return image, mask


def _cover(
    source: bytes | bytearray | Image.Image,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> Image.Image:
    return _cover_with_mask(source, None, width, height)[0]


def _font_file(name: str) -> Path:
    return Path(__file__).resolve().parent / "fonts" / name


@lru_cache(maxsize=128)
def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ("Oswald-Bold.ttf", "BarlowCondensed-Black.ttf", "Anton-Regular.ttf") if bold else (
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
    for name in ("Anton-Regular.ttf", "BarlowCondensed-Black.ttf", "Oswald-Bold.ttf"):
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_headline(size: int) -> ImageFont.FreeTypeFont:
    for name in ("BarlowCondensed-Black.ttf", "Oswald-Bold.ttf", "Anton-Regular.ttf"):
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_label(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ("Oswald-Bold.ttf", "BarlowCondensed-Black.ttf") if bold else (
        "Barlow-Regular.ttf",
        "Oswald-Bold.ttf",
    )
    for name in names:
        path = _font_file(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@lru_cache(maxsize=128)
def _font_body(size: int) -> ImageFont.FreeTypeFont:
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
    getter = font_fn or (lambda size: _font(size, bold=bold))
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
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int] = DARK,
    shadow_offset: tuple[int, int] = (0, 0),
) -> int:
    draw = ImageDraw.Draw(canvas)
    _, line_height = _measure(draw, "Ag", font)
    shadow_x, shadow_y = shadow_offset
    for line in lines:
        if shadow_x or shadow_y:
            draw.text(
                (x + shadow_x, y + shadow_y),
                line,
                font=font,
                fill=DARK,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        y += line_height + gap
    return y


def _subject_occupancy(mask: Image.Image | None, box: tuple[int, int, int, int]) -> float:
    if not isinstance(mask, Image.Image):
        return 0.0
    mask = mask.convert("L")
    if mask.size != (WIDTH, HEIGHT):
        mask = mask.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    x1, y1, x2, y2 = box
    x1 = max(0, min(WIDTH, int(x1)))
    y1 = max(0, min(HEIGHT, int(y1)))
    x2 = max(x1 + 1, min(WIDTH, int(x2)))
    y2 = max(y1 + 1, min(HEIGHT, int(y2)))
    crop = mask.crop((x1, y1, x2, y2))
    histogram = crop.histogram()
    return sum(histogram[96:]) / max(1, (x2 - x1) * (y2 - y1))


def _region_complexity(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = box
    crop = image.crop((max(0, x1), max(0, y1), min(WIDTH, x2), min(HEIGHT, y2))).convert("L")
    crop.thumbnail((40, 64))
    if crop.width <= 1 or crop.height <= 1:
        return 1.0
    stddev = ImageStat.Stat(crop).stddev
    return sum(stddev) / (255 * len(stddev))


def _content_region(side: str) -> tuple[int, int]:
    return (SAFE_LEFT, CONTENT_WIDTH) if side == "left" else (SAFE_RIGHT - CONTENT_WIDTH, CONTENT_WIDTH)


def _choose_text_side(image: Image.Image, mask: Image.Image | None) -> str:
    """Choose the less obstructed side from the aligned subject mask and image texture."""
    left_box = (SAFE_LEFT, SAFE_TOP, SAFE_LEFT + CONTENT_WIDTH, SAFE_BOTTOM)
    right_box = (SAFE_RIGHT - CONTENT_WIDTH, SAFE_TOP, SAFE_RIGHT, SAFE_BOTTOM)

    def score(box):
        occupancy = _subject_occupancy(mask, box) if mask is not None else 0.0
        return occupancy * 8 + _region_complexity(image, box) * 1.1

    left_score = score(left_box)
    right_score = score(right_box)
    return "left" if left_score <= right_score else "right"


def _side_gradient(image: Image.Image, side: str) -> Image.Image:
    """Protect the selected text column and fade the contrast bed into the image."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    full_distance = (
        SAFE_LEFT + CONTENT_WIDTH
        if side == "left"
        else WIDTH - SAFE_RIGHT + CONTENT_WIDTH
    )
    fade_end = min(WIDTH, full_distance + 300)
    fade_span = max(1, fade_end - full_distance)
    for x in range(WIDTH):
        distance = x if side == "left" else WIDTH - 1 - x
        if distance <= full_distance:
            alpha = 224
        elif distance < fade_end:
            alpha = int(224 * (fade_end - distance) / fade_span)
        else:
            alpha = 0
        if alpha:
            draw.line((x, 0, x, HEIGHT), fill=INK + (alpha,))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def _draw_kicker(canvas: Image.Image, x: int, y: int, text: str) -> int:
    draw = ImageDraw.Draw(canvas)
    clean = " ".join(str(text or "").split()).upper() or "SPORTS DESK"
    draw.rounded_rectangle((x, y + 8, x + 42, y + 13), radius=2, fill=ACCENT)
    font = _font_label(25)
    available_width = max(100, SAFE_RIGHT - x)
    if _measure(draw, clean, font)[0] > available_width:
        font, lines = _fit(draw, clean, available_width, 1, 25, 18, font_fn=_font_label)
        clean = lines[0]
    draw.text((x + 58, y - 2), clean, font=font, fill=ACCENT)
    return y + 56


def _draw_rule(canvas: Image.Image, x: int, y: int, width: int, alpha: int = 112) -> None:
    ImageDraw.Draw(canvas, "RGBA").line((x, y, x + width, y), fill=(255, 255, 255, alpha), width=1)


def _prepare_photo_card(source, subject_mask):
    image, mask = _cover_with_mask(source, subject_mask)
    side = _choose_text_side(image, mask)
    return _side_gradient(image, side), mask, side, _content_region(side)


def _render_stat_highlight(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas, _mask, side, (x, width) = _prepare_photo_card(source, subject_mask)
    draw = ImageDraw.Draw(canvas)
    y = _draw_kicker(canvas, x, 205, data.get("eyebrow") or "PERFORMANCE")
    headline = " ".join(str(data.get("headline") or "").split())
    value = " ".join(str(data.get("value") or "").split())
    unit = " ".join(str(data.get("unit") or "").split())
    metrics = list(data.get("metrics") or [])

    if not headline or not value:
        raise CardStudioError("Stat Highlight needs a headline and a hero value.")
    if len(metrics) > 3:
        raise CardStudioError("Stat Highlight supports at most three supporting metrics.")

    headline_font, headline_lines = _fit(
        draw, headline, width, 2, 94, 58, font_fn=_font_headline
    )
    y = _draw_lines(canvas, headline_lines, x, y + 10, headline_font, 8, fill=WHITE) + 24

    value_font, value_lines = _fit(
        draw, value, width, 1, 250, 112, font_fn=_font_display
    )
    value = value_lines[0]
    draw.text((x - 2, y), value, font=value_font, fill=WHITE)
    y += _measure(draw, value, value_font)[1] + 8

    if unit:
        draw.rounded_rectangle((x, y + 4, x + 34, y + 8), radius=2, fill=ACCENT)
        draw.text((x + 48, y - 6), unit.upper(), font=_font_label(28), fill=ACCENT)
        y += 42

    if metrics:
        y = max(y + 16, 890)
        for metric in metrics:
            label = " ".join(str(metric.get("label") or "").split())
            metric_value = " ".join(str(metric.get("value") or "").split())
            if not label or not metric_value:
                raise CardStudioError("Every supporting metric needs a label and value.")
            _draw_rule(canvas, x, y, width, alpha=104)
            draw.text((x, y + 14), label.upper(), font=_font_label(23, False), fill=MUTED)
            value_font, value_lines = _fit(
                draw, metric_value, width // 2, 1, 43, 27, font_fn=_font_headline
            )
            draw.text((x + width, y + 8), value_lines[0], font=value_font, fill=WHITE, anchor="ra")
            y += 72

    return canvas.convert("RGB")


def _render_quote_reaction(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas, _mask, side, (x, width) = _prepare_photo_card(source, subject_mask)
    draw = ImageDraw.Draw(canvas)
    y = _draw_kicker(canvas, x, 235, data.get("eyebrow") or "REACTION")

    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())
    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    quote_font, quote_lines = _fit(
        draw, quote, width - 30, 5, 78, 48, bold=False, font_fn=_font_body
    )
    line_height = _measure(draw, "Ag", quote_font)[1]
    quote_top = y + 22
    quote_bottom = quote_top + len(quote_lines) * (line_height + 10)
    draw.rounded_rectangle((x, quote_top, x + 5, quote_bottom - 10), radius=2, fill=ACCENT)
    y = _draw_lines(canvas, quote_lines, x + 28, quote_top, quote_font, 10, fill=WHITE) + 28

    _draw_rule(canvas, x + 28, y, width - 28, alpha=150)
    attr_font, attr_lines = _fit(
        draw, attribution, width - 28, 2, 48, 34, font_fn=_font_headline
    )
    y = _draw_lines(canvas, attr_lines, x + 28, y + 22, attr_font, 4, fill=WHITE) + 10

    if context:
        context_font, context_lines = _fit(
            draw, context, width - 28, 3, 31, 23, bold=False, font_fn=_font_body
        )
        _draw_lines(canvas, context_lines, x + 28, y, context_font, 5, fill=MUTED)

    return canvas.convert("RGB")


def _split_image_and_mask(source, mask, direction: str) -> tuple[Image.Image, Image.Image | None, Image.Image, Image.Image | None]:
    first_source, second_source = source
    masks = mask if isinstance(mask, (tuple, list)) and len(mask) == 2 else (None, None)
    if direction == "Horizontal":
        first, first_mask = _cover_with_mask(first_source, masks[0], WIDTH, HEIGHT // 2)
        second, second_mask = _cover_with_mask(second_source, masks[1], WIDTH, HEIGHT - HEIGHT // 2)
    else:
        first, first_mask = _cover_with_mask(first_source, masks[0], WIDTH // 2, HEIGHT)
        second, second_mask = _cover_with_mask(second_source, masks[1], WIDTH - WIDTH // 2, HEIGHT)
    return first, first_mask, second, second_mask


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

    if image_mode == "Two images":
        if not isinstance(source, (tuple, list)) or len(source) != 2:
            raise CardStudioError("Two-image Head-to-Head needs two source images.")
        first, first_mask, second, second_mask = _split_image_and_mask(source, subject_mask, direction)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), INK)
        combined_mask = None
        if first_mask is not None or second_mask is not None:
            combined_mask = Image.new("L", (WIDTH, HEIGHT), 0)
        if direction == "Horizontal":
            canvas.paste(first, (0, 0))
            canvas.paste(second, (0, HEIGHT // 2))
            if combined_mask is not None:
                if first_mask is not None:
                    combined_mask.paste(first_mask, (0, 0))
                if second_mask is not None:
                    combined_mask.paste(second_mask, (0, HEIGHT // 2))
        else:
            canvas.paste(first, (0, 0))
            canvas.paste(second, (WIDTH // 2, 0))
            if combined_mask is not None:
                if first_mask is not None:
                    combined_mask.paste(first_mask, (0, 0))
                if second_mask is not None:
                    combined_mask.paste(second_mask, (WIDTH // 2, 0))
        side = _choose_text_side(canvas, combined_mask)
        canvas = _side_gradient(canvas, side)
        header_x, _ = _content_region(side)
    else:
        canvas, aligned_mask = _cover_with_mask(
            source, subject_mask if isinstance(subject_mask, Image.Image) else None
        )
        side = _choose_text_side(canvas, aligned_mask)
        canvas = _side_gradient(canvas, side)
        header_x, _ = _content_region(side)

    draw = ImageDraw.Draw(canvas)
    kicker_y = _draw_kicker(canvas, header_x, 160, data.get("eyebrow") or "HEAD TO HEAD")
    head_font, head_lines = _fit(
        draw, headline, CONTENT_WIDTH, 2, 88, 56, font_fn=_font_headline
    )
    y = _draw_lines(canvas, head_lines, header_x, kicker_y + 8, head_font, 6, fill=WHITE)

    panel_top = min(820, max(720, y + 42))
    panel = Image.new("RGBA", (WIDTH, HEIGHT - panel_top), CARD_BG)
    canvas.alpha_composite(panel, (0, panel_top))
    draw = ImageDraw.Draw(canvas)

    left_x1 = SAFE_LEFT
    left_x2 = WIDTH // 2 - 48
    right_x1 = WIDTH // 2 + 48
    right_x2 = SAFE_RIGHT
    mid_x = WIDTH // 2

    left_font, left_lines = _fit(
        draw, str(left["name"]), left_x2 - left_x1 - 22, 2, 48, 31,
        font_fn=_font_headline,
    )
    right_font, right_lines = _fit(
        draw, str(right["name"]), right_x2 - right_x1 - 22, 2, 48, 31,
        font_fn=_font_headline,
    )
    left_end = _draw_lines(canvas, left_lines, left_x1, panel_top + 48, left_font, 3, fill=WHITE)
    right_end = _draw_lines(canvas, right_lines, right_x1, panel_top + 48, right_font, 3, fill=WHITE)

    draw = ImageDraw.Draw(canvas)
    draw.text((mid_x, panel_top + 62), "VS", font=_font_label(22), fill=ACCENT, anchor="mm")
    names_bottom = max(left_end, right_end)
    _draw_rule(canvas, SAFE_LEFT, names_bottom + 12, SAFE_RIGHT - SAFE_LEFT, alpha=148)

    left_values = left.get("values") or {}
    right_values = right.get("values") or {}
    row_y = names_bottom + 26
    row_height = min(130, max(96, (SAFE_BOTTOM - row_y) // len(metrics)))
    for metric in metrics:
        label = " ".join(str(metric).split())
        left_value = " ".join(str(left_values.get(label) or "").split())
        right_value = " ".join(str(right_values.get(label) or "").split())
        if not left_value or not right_value:
            raise CardStudioError(f"Both sides need a value for {label}.")
        draw = ImageDraw.Draw(canvas)
        left_value_font, left_value_lines = _fit(
            draw, left_value, 220, 1, 42, 28, font_fn=_font_headline
        )
        label_font, label_lines = _fit(
            draw, label.upper(), SAFE_RIGHT - SAFE_LEFT, 1, 23, 17,
            font_fn=lambda size: _font_label(size, False),
        )
        right_value_font, right_value_lines = _fit(
            draw, right_value, 220, 1, 42, 28, font_fn=_font_headline
        )
        draw.text(
            (mid_x, row_y + 18), label_lines[0],
            font=label_font, fill=MUTED, anchor="mm",
        )
        draw.text(
            (SAFE_LEFT + 150, row_y + 68), left_value_lines[0],
            font=left_value_font, fill=WHITE, anchor="mm",
        )
        draw.text(
            (SAFE_RIGHT - 150, row_y + 68), right_value_lines[0],
            font=right_value_font, fill=WHITE, anchor="mm",
        )
        _draw_rule(canvas, SAFE_LEFT, row_y + row_height - 4, SAFE_RIGHT - SAFE_LEFT, alpha=76)
        row_y += row_height

    return canvas.convert("RGB")


def _render_fact_milestone(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas, _mask, side, (x, width) = _prepare_photo_card(source, subject_mask)
    draw = ImageDraw.Draw(canvas)
    y = _draw_kicker(canvas, x, 220, data.get("eyebrow") or "MILESTONE")

    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())
    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    value_font, value_lines = _fit(draw, value, width, 2, 236, 94, font_fn=_font_display)
    y = _draw_lines(canvas, value_lines, x, y + 30, value_font, 3, fill=ACCENT) + 26
    _draw_rule(canvas, x, y, width, alpha=170)
    label_font, label_lines = _fit(
        draw, label, width, 3, 82, 49, font_fn=_font_headline
    )
    y = _draw_lines(canvas, label_lines, x, y + 28, label_font, 8, fill=WHITE) + 28

    if context:
        context_font, context_lines = _fit(
            draw, context, width, 4, 34, 25, bold=False, font_fn=_font_body
        )
        _draw_lines(canvas, context_lines, x, y, context_font, 7, fill=MUTED)

    return canvas.convert("RGB")


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
