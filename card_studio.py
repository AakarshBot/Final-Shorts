"""Editorial Card Studio for Final-Shorts.

Builds 1080x1920 sports-magazine frames with photo-led, subject-aware layouts.
Text Subject Cutout intentionally remains on its existing shared editor path.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

import indic_bootstrap

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat, features


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

CARD_LAYOUT_POSITIONS = (
    "Auto · Best negative space",
    "Left half",
    "Right half",
    "Bottom half",
)
CARD_CONTRAST_TREATMENTS = (
    "Adaptive gradient",
    "Deep gradient",
    "Editorial panel",
    "Edge-lit wash",
)

_CARD_COPY_LABELS = {
    "english": {
        "sports_desk": "SPORTS DESK",
        "performance": "PERFORMANCE",
        "reaction": "REACTION",
        "head_to_head": "HEAD TO HEAD",
        "milestone": "MILESTONE",
        "versus": "VS",
    },
    "hindi": {
        "sports_desk": "खेल डेस्क",
        "performance": "प्रदर्शन",
        "reaction": "प्रतिक्रिया",
        "head_to_head": "आमने-सामने",
        "milestone": "उपलब्धि",
        "versus": "बनाम",
    },
    "telugu": {
        "sports_desk": "క్రీడా విభాగం",
        "performance": "ప్రదర్శన",
        "reaction": "స్పందన",
        "head_to_head": "ఎదురెదురు పోటీ",
        "milestone": "మైలురాయి",
        "versus": "వర్సెస్",
    },
}


def _normalise_card_language(language: str | None) -> str:
    key = str(language or "english").strip().casefold()
    key = {"en": "english", "hi": "hindi", "te": "telugu"}.get(key, key)
    return key if key in _CARD_COPY_LABELS else "english"


def _card_label(key: str, language: str | None = "english") -> str:
    language_key = _normalise_card_language(language)
    return _CARD_COPY_LABELS[language_key].get(key, _CARD_COPY_LABELS["english"].get(key, ""))



class CardStudioError(ValueError):
    """Raised when a Card Studio frame cannot be rendered cleanly."""



def invalidate_card_studio_result_for_composition(
    session_state,
    result_key: str,
    card_type: str,
    layout_position: str,
    contrast_treatment: str,
    language: str = "english",
) -> bool:
    """Clear a rendered preview when its card type or photo composition has changed."""
    result = session_state.get(result_key)
    if not isinstance(result, dict) or result.get("bytes") is None:
        return False
    previous = result.get("data") or {}
    if (
        result.get("type") != card_type
        or previous.get("layout_position", CARD_LAYOUT_POSITIONS[0]) != layout_position
        or previous.get("contrast_treatment", CARD_CONTRAST_TREATMENTS[0]) != contrast_treatment
        or _normalise_card_language(previous.get("language", "english"))
        != _normalise_card_language(language)
    ):
        session_state[result_key] = None
        return True
    return False


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


@lru_cache(maxsize=256)
def _localized_font(language: str, size: int) -> ImageFont.FreeTypeFont | None:
    language_key = _normalise_card_language(language)
    font_name = {
        "hindi": "NotoSansDevanagari-Bold.ttf",
        "telugu": "NotoSansTelugu-Bold.ttf",
    }.get(language_key)
    if not font_name:
        return None
    try:
        raqm_available = features.check_feature("raqm")
    except (AttributeError, ValueError):
        raqm_available = False
    if not raqm_available:
        raise CardStudioError(
            f"{language_key.title()} card text needs Pillow's RAQM shaping engine. "
            "Rendering has stopped to prevent incorrectly joined letters. On Windows, "
            "ensure the FriBiDi runtime DLL is available and restart the factory."
        )
    path = _font_file(font_name)
    if not path.is_file():
        raise CardStudioError(
            f"The bundled {font_name} font is missing; the card will not use a substitute font."
        )
    try:
        return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
    except (AttributeError, OSError, ValueError) as exc:
        raise CardStudioError(
            f"Could not load {font_name} with correct Indic text shaping."
        ) from exc


def _font_for_text(text: str, size: int, fallback):
    value = str(text or "")
    devanagari = any("\u0900" <= char <= "\u097F" for char in value)
    telugu = any("\u0C00" <= char <= "\u0C7F" for char in value)
    if devanagari and telugu:
        raise CardStudioError("One card text field cannot mix Hindi and Telugu scripts.")
    if devanagari:
        return _localized_font("hindi", size)
    if telugu:
        return _localized_font("telugu", size)
    return fallback(size)


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
        font = _font_for_text(text, size, getter)
        lines = _wrap(draw, text, font, max_width)
        if lines and len(lines) <= max_lines:
            return font, lines
    raise CardStudioError("The card text is too long for this layout. Shorten the copy.")


def _lines_metric_height(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    gap: int,
    stroke_width: int = 0,
) -> tuple[int, int]:
    has_indic = any(
        any(
            0x0900 <= ord(char) <= 0x097F or 0x0C00 <= ord(char) <= 0x0C7F
            for char in line
        )
        for line in lines
    )
    if has_indic and hasattr(font, "getmetrics"):
        ascent, descent = font.getmetrics()
        metric_h = ascent + descent + stroke_width * 2
        line_ink_heights = [_measure(draw, line, font)[1] for line in lines] if lines else [0]
        line_height = max(metric_h, max(line_ink_heights))
        font_size = getattr(font, "size", 40)
        effective_gap = max(gap, int(font_size * 0.18))
    else:
        _, line_height = _measure(draw, "Ag", font)
        effective_gap = gap
    return line_height, effective_gap


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
    line_height, effective_gap = _lines_metric_height(
        draw, lines, font, gap, stroke_width=stroke_width
    )
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
        y += line_height + effective_gap
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
    """Estimate distraction using both tonal variation and edge density."""
    x1, y1, x2, y2 = box
    crop = image.crop((max(0, x1), max(0, y1), min(WIDTH, x2), min(HEIGHT, y2))).convert("L")
    crop.thumbnail((48, 72))
    if crop.width <= 1 or crop.height <= 1:
        return 1.0
    stats = ImageStat.Stat(crop)
    tonal_variation = sum(stats.stddev) / (255 * len(stats.stddev))
    edge_density = ImageStat.Stat(crop.filter(ImageFilter.FIND_EDGES)).mean[0] / 255
    return min(1.0, tonal_variation * 0.45 + edge_density * 0.55)


def _content_region(position: str) -> tuple[int, int]:
    if position == "left":
        return SAFE_LEFT, CONTENT_WIDTH
    if position == "right":
        return SAFE_RIGHT - CONTENT_WIDTH, CONTENT_WIDTH
    return SAFE_LEFT, SAFE_RIGHT - SAFE_LEFT


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


def _resolve_layout_position(image: Image.Image, mask: Image.Image | None, data: dict | None = None) -> str:
    selected = str((data or {}).get("layout_position") or CARD_LAYOUT_POSITIONS[0])
    if selected == "Left half":
        return "left"
    if selected == "Right half":
        return "right"
    if selected == "Bottom half":
        return "bottom"
    return _choose_text_side(image, mask)


def _contrast_bed(
    image: Image.Image,
    position: str,
    treatment: str = "Adaptive gradient",
    content_bounds: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """Build a contrast treatment around measured copy bounds and local image brightness."""
    rgba = image.convert("RGBA")
    selected = str(treatment or "Adaptive gradient")
    if selected == "Soft gradient":
        selected = "Adaptive gradient"

    if content_bounds:
        left, top, right, bottom = (int(value) for value in content_bounds)
    elif position == "bottom":
        left, top, right, bottom = SAFE_LEFT, 1020, SAFE_RIGHT, SAFE_BOTTOM
    else:
        region_x, region_width = _content_region(position)
        left, top, right, bottom = region_x, SAFE_TOP, region_x + region_width, SAFE_BOTTOM

    left = max(12, min(WIDTH - 12, left))
    right = max(left + 1, min(WIDTH - 12, right))
    top = max(40, min(HEIGHT - 80, top))
    bottom = max(top + 1, min(HEIGHT - 80, bottom))
    panel_box = (
        max(20, left - 26),
        max(40, top - 24),
        min(WIDTH - 20, right + 26),
        min(HEIGHT - 80, bottom + 24),
    )
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), INK + (0,))

    if selected == "Editorial panel":
        panel_draw = ImageDraw.Draw(overlay, "RGBA")
        panel_draw.rounded_rectangle(
            panel_box,
            radius=28,
            fill=INK + (218,),
            outline=(255, 255, 255, 58),
            width=2,
        )
        px1, py1, px2, _py2 = panel_box
        if position == "bottom":
            panel_draw.rounded_rectangle(
                (px1 + 28, py1 + 22, min(px2 - 28, px1 + 108), py1 + 28),
                radius=3,
                fill=ACCENT + (245,),
            )
        else:
            panel_draw.rounded_rectangle(
                (px1 + 18, py1 + 28, px1 + 24, max(py1 + 34, panel_box[3] - 28)),
                radius=3,
                fill=ACCENT + (235,),
            )
        return Image.alpha_composite(rgba, overlay)

    fade = 300
    horizontal = Image.new("L", (WIDTH, 1), 0)
    vertical = Image.new("L", (1, HEIGHT), 0)
    if position == "bottom":
        vertical_values = []
        vertical_fade = 150
        for y in range(HEIGHT):
            if y < top - vertical_fade:
                factor = 0.0
            elif y < top:
                factor = (y - (top - vertical_fade)) / max(1, vertical_fade)
            elif y <= bottom:
                factor = 1.0
            elif y < bottom + vertical_fade:
                factor = (bottom + vertical_fade - y) / max(1, vertical_fade)
            else:
                factor = 0.0
            vertical_values.append(int(255 * max(0.0, min(1.0, factor))))
        vertical.putdata(vertical_values)
        spatial = vertical.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    else:
        horizontal_values = []
        for x in range(WIDTH):
            if position == "right":
                if x >= left:
                    factor = 1.0
                elif x > left - fade:
                    factor = (x - (left - fade)) / max(1, fade)
                else:
                    factor = 0.0
            else:
                if x <= right:
                    factor = 1.0
                elif x < right + fade:
                    factor = (right + fade - x) / max(1, fade)
                else:
                    factor = 0.0
            horizontal_values.append(int(255 * max(0.0, min(1.0, factor))))
        horizontal.putdata(horizontal_values)
        vertical_values = []
        for y in range(HEIGHT):
            if y < top - 110:
                factor = 0.0
            elif y < top:
                factor = (y - (top - 110)) / 110
            elif y <= bottom:
                factor = 1.0
            elif y < bottom + 150:
                factor = (bottom + 150 - y) / 150
            else:
                factor = 0.0
            vertical_values.append(int(255 * max(0.0, min(1.0, factor))))
        vertical.putdata(vertical_values)
        spatial = ImageChops.multiply(
            horizontal.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST),
            vertical.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST),
        )

    if selected == "Deep gradient":
        alpha = Image.eval(spatial, lambda value: value * 238 // 255)
    else:
        # Bright photo pixels receive a stronger scrim; darker pixels retain more image detail.
        luminance = ImageOps.grayscale(rgba.convert("RGB"))
        adaptive_strength = Image.eval(luminance, lambda value: min(238, 92 + int(value * 0.57)))
        alpha = ImageChops.multiply(spatial, adaptive_strength)
        if selected == "Edge-lit wash":
            alpha = Image.eval(alpha, lambda value: int(value * 0.88))
    overlay.putalpha(alpha)

    if selected == "Edge-lit wash":
        accent_draw = ImageDraw.Draw(overlay, "RGBA")
        px1, py1, px2, py2 = panel_box
        if position == "bottom":
            accent_draw.rounded_rectangle(
                (px1 + 28, py1 + 20, min(px2 - 28, px1 + 100), py1 + 26),
                radius=3,
                fill=ACCENT + (235,),
            )
        elif position == "right":
            accent_draw.rounded_rectangle(
                (px2 - 7, py1 + 24, px2 - 2, py2 - 24),
                radius=3,
                fill=ACCENT + (235,),
            )
        else:
            accent_draw.rounded_rectangle(
                (px1 + 2, py1 + 24, px1 + 7, py2 - 24),
                radius=3,
                fill=ACCENT + (235,),
            )
    return Image.alpha_composite(rgba, overlay)


def _draw_kicker(
    canvas: Image.Image,
    x: int,
    y: int,
    text: str,
    language: str = "english",
) -> int:
    draw = ImageDraw.Draw(canvas)
    clean = " ".join(str(text or "").split()).upper() or _card_label("sports_desk", language)
    draw.rounded_rectangle((x, y + 8, x + 42, y + 13), radius=2, fill=ACCENT)
    font = _font_for_text(clean, 25, _font_label)
    available_width = max(100, SAFE_RIGHT - x)
    if _measure(draw, clean, font)[0] > available_width:
        font, lines = _fit(draw, clean, available_width, 1, 25, 18, font_fn=_font_label)
        clean = lines[0]
    draw.text((x + 58, y - 2), clean, font=font, fill=ACCENT)
    return y + 56


def _draw_rule(canvas: Image.Image, x: int, y: int, width: int, alpha: int = 112) -> None:
    ImageDraw.Draw(canvas, "RGBA").line((x, y, x + width, y), fill=(255, 255, 255, alpha), width=1)


def _text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    preferred_size: int,
    minimum_size: int,
    max_lines: int,
    font_fn,
    gap: int = 6,
    bold: bool = True,
) -> dict | None:
    clean = " ".join(str(text or "").split())
    if not clean:
        return None
    font, lines = _fit(
        draw, clean, max_width, max_lines, preferred_size, minimum_size,
        bold=bold, font_fn=font_fn,
    )
    line_height, line_gap = _lines_metric_height(draw, lines, font, gap)
    height = line_height * len(lines) + line_gap * max(0, len(lines) - 1)
    return {
        "text": clean,
        "font": font,
        "lines": lines,
        "line_height": line_height,
        "line_gap": line_gap,
        "height": height,
    }


def _supporting_fields(data: dict, card_type: str) -> list[dict]:
    fields = data.get("supporting_fields")
    if fields is None:
        fields = data.get("metrics") or []
        if not fields and data.get("context"):
            fields = [{"label": "Context", "value": data.get("context")}]
    result = []
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        label = " ".join(str(field.get("label") or "").split())
        value = " ".join(str(field.get("value") or "").split())
        if label and value:
            result.append({"label": label, "value": value})
    return result


def _support_rows_block(
    draw: ImageDraw.ImageDraw,
    fields: list[dict],
    width: int,
    *,
    bottom_mode: bool = False,
) -> dict | None:
    rows = []
    label_width = max(120, int(width * 0.52))
    value_width = max(100, width - int(width * 0.61))
    for item in fields:
        label = " ".join(str(item.get("label") or "").split())
        value = " ".join(str(item.get("value") or "").split())
        if not label or not value:
            continue
        label_block = _text_block(
            draw, label, label_width,
            preferred_size=29 if not bottom_mode else 27,
            minimum_size=25 if not bottom_mode else 24,
            max_lines=2, font_fn=lambda size: _font_label(size, False), gap=3, bold=False,
        )
        value_block = _text_block(
            draw, value, value_width,
            preferred_size=42 if not bottom_mode else 36,
            minimum_size=31 if not bottom_mode else 29,
            max_lines=2, font_fn=_font_headline, gap=3,
        )
        if not label_block or not value_block:
            continue
        rows.append({
            "label": label_block,
            "value": value_block,
            "height": max(label_block["height"], value_block["height"]) + 18,
        })
    if not rows:
        return None
    height = sum(row["height"] for row in rows) + max(0, len(rows) - 1) * 12
    return {"kind": "support_rows", "rows": rows, "height": height}


def _block_height(blocks: list[dict]) -> int:
    return sum(block["height"] + block.get("gap_after", 0) for block in blocks)


def _draw_text_block(
    canvas: Image.Image,
    block: dict,
    x: int,
    y: int,
    fill: tuple[int, int, int],
    *,
    width: int | None = None,
    centered: bool = False,
) -> int:
    draw = ImageDraw.Draw(canvas)
    cursor_y = y
    for line in block["lines"]:
        if centered and width is not None:
            draw.text((x + width // 2, cursor_y), line, font=block["font"], fill=fill, anchor="ma")
        else:
            draw.text((x, cursor_y), line, font=block["font"], fill=fill)
        cursor_y += block["line_height"] + block["line_gap"]
    return y + block["height"]


def _draw_support_rows(canvas: Image.Image, block: dict, x: int, y: int, width: int) -> int:
    draw = ImageDraw.Draw(canvas)
    cursor_y = y
    for index, row in enumerate(block["rows"]):
        if index:
            draw.line((x, cursor_y, x + width, cursor_y), fill=(255, 255, 255, 76), width=2)
            cursor_y += 12
        label_block = row["label"]
        value_block = row["value"]
        _draw_text_block(
            canvas, label_block, x,
            cursor_y + max(0, (row["height"] - label_block["height"]) // 2), MUTED,
        )
        value_x = x + int(width * 0.61)
        value_width = width - (value_x - x)
        _draw_text_block(
            canvas, value_block, value_x,
            cursor_y + max(0, (row["height"] - value_block["height"]) // 2),
            WHITE, width=value_width, centered=True,
        )
        cursor_y += row["height"]
    return y + block["height"]


def _draw_editorial_stack(
    image: Image.Image,
    position: str,
    treatment: str,
    x: int,
    width: int,
    top: int,
    blocks: list[dict],
) -> Image.Image:
    blocks = [block for block in blocks if block]
    total_height = _block_height(blocks)
    if top + total_height > SAFE_BOTTOM - 12:
        raise CardStudioError(
            "This card has more copy than the selected position can hold at readable font sizes. "
            "Remove a supporting field or choose Auto / Left half / Right half."
        )
    content_bounds = (
        max(24, x - 20),
        max(40, top - 24),
        min(WIDTH - 24, x + width + 18),
        min(SAFE_BOTTOM, top + total_height + 18),
    )
    canvas = _contrast_bed(image, position, treatment, content_bounds)
    cursor_y = top
    for block in blocks:
        kind = block.get("kind", "text")
        if kind == "kicker":
            cursor_y = _draw_kicker(canvas, x, cursor_y, block["text"], block.get("language", "english"))
        elif kind == "rule":
            ImageDraw.Draw(canvas, "RGBA").rounded_rectangle(
                (x, cursor_y + 2, x + 72, cursor_y + 7),
                radius=2, fill=ACCENT + (245,),
            )
            cursor_y += block["height"]
        elif kind == "quote":
            draw = ImageDraw.Draw(canvas)
            draw.text((x - 2, cursor_y - 17), "“", font=_font_display(112), fill=ACCENT)
            _draw_text_block(canvas, block["copy"], x + 30, cursor_y + 14, WHITE)
            cursor_y += block["height"]
        elif kind == "support_rows":
            cursor_y = _draw_support_rows(canvas, block, x, cursor_y, width)
        else:
            _draw_text_block(canvas, block, x, cursor_y, block.get("fill", WHITE))
            cursor_y += block["height"]
        cursor_y += block.get("gap_after", 0)
    return canvas.convert("RGB")


def _make_support_rows(
    draw: ImageDraw.ImageDraw,
    fields: list[dict],
    width: int,
    *,
    bottom_mode: bool = False,
) -> dict | None:
    block = _support_rows_block(draw, fields, width, bottom_mode=bottom_mode)
    if block:
        block["gap_after"] = 0
    return block


def _render_stat_highlight(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    image, mask = _cover_with_mask(source, subject_mask)
    position = _resolve_layout_position(image, mask, data)
    x, width = _content_region(position)
    bottom_mode = position == "bottom"
    top = 900 if bottom_mode else SAFE_TOP
    language = _normalise_card_language(data.get("language"))
    draw = ImageDraw.Draw(image)
    headline = " ".join(str(data.get("headline") or "").split())
    value = " ".join(str(data.get("value") or "").split())
    unit = " ".join(str(data.get("unit") or "").split())
    if not value:
        raise CardStudioError("Stat Highlight needs one hero value. Fill it from the story or enter a verified value.")

    blocks = [{
        "kind": "kicker",
        "text": str(data.get("eyebrow") or _card_label("performance", language)),
        "language": language, "height": 56,
        "gap_after": 14 if bottom_mode else 20,
    }]
    headline_block = _text_block(
        draw, headline, width,
        preferred_size=64 if not bottom_mode else 52,
        minimum_size=48 if not bottom_mode else 40,
        max_lines=2, font_fn=_font_headline, gap=5,
    )
    if headline_block:
        headline_block.update({"kind": "text", "fill": WHITE, "gap_after": 14 if bottom_mode else 24})
        blocks.append(headline_block)
    value_block = _text_block(
        draw, value, width,
        preferred_size=174 if not bottom_mode else 126,
        minimum_size=82 if not bottom_mode else 72,
        max_lines=2, font_fn=_font_display, gap=2,
    )
    if not value_block:
        raise CardStudioError("Stat Highlight needs one hero value.")
    value_block.update({"kind": "text", "fill": ACCENT, "gap_after": 3 if unit else (18 if bottom_mode else 26)})
    blocks.append(value_block)
    unit_block = _text_block(
        draw, unit, width,
        preferred_size=33 if not bottom_mode else 29,
        minimum_size=27, max_lines=1,
        font_fn=lambda size: _font_label(size, True), gap=2,
    )
    if unit_block:
        unit_block.update({"kind": "text", "fill": WHITE, "gap_after": 14 if bottom_mode else 22})
        blocks.append(unit_block)
    support = _make_support_rows(draw, _supporting_fields(data, "Stat Highlight"), width, bottom_mode=bottom_mode)
    if support:
        blocks.append(support)
    return _draw_editorial_stack(
        image, position, str(data.get("contrast_treatment") or "Adaptive gradient"),
        x, width, top, blocks,
    )


def _render_quote_reaction(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    image, mask = _cover_with_mask(source, subject_mask)
    position = _resolve_layout_position(image, mask, data)
    x, width = _content_region(position)
    bottom_mode = position == "bottom"
    top = 900 if bottom_mode else SAFE_TOP
    language = _normalise_card_language(data.get("language"))
    draw = ImageDraw.Draw(image)
    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    if not quote:
        raise CardStudioError("Quote / Reaction needs a real quotation. Use story fill to avoid inventing quotes.")

    blocks = [{
        "kind": "kicker",
        "text": str(data.get("eyebrow") or _card_label("reaction", language)),
        "language": language, "height": 56,
        "gap_after": 16 if bottom_mode else 22,
    }]
    quote_block = _text_block(
        draw, quote, max(100, width - 34),
        preferred_size=54 if not bottom_mode else 46,
        minimum_size=39 if not bottom_mode else 34,
        max_lines=5, font_fn=_font_body, gap=7, bold=False,
    )
    if not quote_block:
        raise CardStudioError("Quote / Reaction needs a quote.")
    blocks.append({
        "kind": "quote",
        "copy": quote_block,
        "height": quote_block["height"] + 18,
        "gap_after": 18 if attribution or data.get("supporting_fields") or data.get("context") else 0,
    })
    if attribution:
        attr_block = _text_block(
            draw, attribution, width,
            preferred_size=36 if not bottom_mode else 32,
            minimum_size=29, max_lines=2,
            font_fn=_font_headline, gap=3,
        )
        if attr_block:
            blocks.append({"kind": "rule", "height": 22, "gap_after": 14})
            attr_block.update({"kind": "text", "fill": WHITE, "gap_after": 14 if (data.get("supporting_fields") or data.get("context")) else 0})
            blocks.append(attr_block)
    support_fields = _supporting_fields(data, "Quote / Reaction")
    if data.get("context") and not any(item["label"].casefold() == "context" for item in support_fields):
        support_fields.append({"label": "Context", "value": str(data.get("context"))})
    support = _make_support_rows(draw, support_fields, width, bottom_mode=bottom_mode)
    if support:
        blocks.append(support)
    return _draw_editorial_stack(
        image, position, str(data.get("contrast_treatment") or "Adaptive gradient"),
        x, width, top, blocks,
    )


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
    if not left.get("name") or not right.get("name"):
        raise CardStudioError("Head-to-Head needs both names.")

    if image_mode == "Two images":
        if not isinstance(source, (tuple, list)) or len(source) != 2:
            raise CardStudioError("Two-image Head-to-Head needs two source images.")
        first, first_mask, second, second_mask = _split_image_and_mask(source, subject_mask, direction)
        image = Image.new("RGB", (WIDTH, HEIGHT), INK)
        combined_mask = Image.new("L", (WIDTH, HEIGHT), 0) if first_mask is not None or second_mask is not None else None
        if direction == "Horizontal":
            image.paste(first, (0, 0))
            image.paste(second, (0, HEIGHT // 2))
            if combined_mask is not None:
                if first_mask is not None:
                    combined_mask.paste(first_mask, (0, 0))
                if second_mask is not None:
                    combined_mask.paste(second_mask, (0, HEIGHT // 2))
        else:
            image.paste(first, (0, 0))
            image.paste(second, (WIDTH // 2, 0))
            if combined_mask is not None:
                if first_mask is not None:
                    combined_mask.paste(first_mask, (0, 0))
                if second_mask is not None:
                    combined_mask.paste(second_mask, (WIDTH // 2, 0))
    else:
        image, combined_mask = _cover_with_mask(source, subject_mask if isinstance(subject_mask, Image.Image) else None)

    position = _resolve_layout_position(image, combined_mask, data)
    treatment = str(data.get("contrast_treatment") or "Adaptive gradient")
    bottom_mode = position == "bottom"
    header_x, header_width = _content_region(position)
    header_top = 810 if bottom_mode else SAFE_TOP
    draw = ImageDraw.Draw(image)
    header_blocks = [{
        "kind": "kicker",
        "text": str(data.get("eyebrow") or _card_label("head_to_head", data.get("language"))),
        "language": _normalise_card_language(data.get("language")),
        "height": 56, "gap_after": 12 if bottom_mode else 20,
    }]
    headline_block = _text_block(
        draw, headline, header_width,
        preferred_size=55 if bottom_mode else 70,
        minimum_size=42 if bottom_mode else 48,
        max_lines=2, font_fn=_font_headline, gap=4,
    )
    if headline_block:
        headline_block["gap_after"] = 20
        header_blocks.append(headline_block)
    header_height = _block_height(header_blocks)
    panel_top = max(760 if not bottom_mode else 990, header_top + header_height + 28)
    if panel_top >= SAFE_BOTTOM - 180:
        raise CardStudioError("The Head-to-Head heading leaves too little safe space for the comparison.")
    panel_bottom = SAFE_BOTTOM
    panel_height = panel_bottom - panel_top
    side_width = max(170, (SAFE_RIGHT - SAFE_LEFT) // 2 - 24)
    left_name_block = _text_block(draw, str(left.get("name") or ""), side_width, preferred_size=41, minimum_size=30, max_lines=2, font_fn=_font_headline, gap=3)
    right_name_block = _text_block(draw, str(right.get("name") or ""), side_width, preferred_size=41, minimum_size=30, max_lines=2, font_fn=_font_headline, gap=3)
    if not left_name_block or not right_name_block:
        raise CardStudioError("Head-to-Head needs both names.")
    names_height = max(left_name_block["height"], right_name_block["height"])
    if not metrics:
        raise CardStudioError("Add at least one evidence-backed comparison metric.")
    parsed_rows = []
    for metric in metrics:
        if isinstance(metric, dict):
            label = " ".join(str(metric.get("label") or "").split())
            left_value = " ".join(str(metric.get("left_value") or "").split())
            right_value = " ".join(str(metric.get("right_value") or "").split())
        else:
            label = " ".join(str(metric or "").split())
            left_value = " ".join(str((left.get("values") or {}).get(label) or "").split())
            right_value = " ".join(str((right.get("values") or {}).get(label) or "").split())
        if label:
            parsed_rows.append((label, left_value or "—", right_value or "—"))
    if not parsed_rows:
        raise CardStudioError("Add at least one evidence-backed comparison metric.")

    panel_padding = 28
    names_block_height = names_height + 52
    row_area = panel_height - panel_padding * 2 - names_block_height
    row_height = min(94, row_area // len(parsed_rows))
    if row_height < 58:
        raise CardStudioError(
            "Too many comparison rows for this photo position at readable font sizes. "
            "Remove a row or choose Auto / Left half / Right half."
        )

    canvas = _contrast_bed(
        image, position, treatment,
        (header_x - 20, header_top - 20, header_x + header_width + 20, min(panel_top - 20, header_top + header_height + 20)),
    )
    panel_draw = ImageDraw.Draw(canvas, "RGBA")
    panel_draw.rounded_rectangle(
        (28, panel_top, SAFE_RIGHT + 72, panel_bottom),
        radius=28, fill=CARD_BG, outline=(255, 255, 255, 55), width=2,
    )
    panel_draw.rounded_rectangle(
        (48, panel_top + 22, 122, panel_top + 28),
        radius=3, fill=ACCENT + (245,),
    )
    cursor_y = panel_top + panel_padding + 10
    left_x = SAFE_LEFT
    right_x = SAFE_RIGHT - side_width
    left_cx = left_x + side_width // 2
    right_cx = right_x + side_width // 2
    versus = _card_label("versus", data.get("language"))
    ImageDraw.Draw(canvas).text(
        ((SAFE_LEFT + SAFE_RIGHT) // 2, cursor_y + names_height // 2),
        versus, font=_font_label(23), fill=ACCENT, anchor="mm",
    )
    _draw_text_block(canvas, left_name_block, left_x, cursor_y, WHITE, width=side_width, centered=True)
    _draw_text_block(canvas, right_name_block, right_x, cursor_y, WHITE, width=side_width, centered=True)
    cursor_y += names_block_height
    line_x1, line_x2 = 48, SAFE_RIGHT + 48
    centre_x = (SAFE_LEFT + SAFE_RIGHT) // 2
    for index, (label, left_value, right_value) in enumerate(parsed_rows):
        if index:
            ImageDraw.Draw(canvas, "RGBA").line((line_x1, cursor_y, line_x2, cursor_y), fill=(255, 255, 255, 75), width=2)
        value_width = side_width - 4
        label_font, label_lines = _fit(ImageDraw.Draw(canvas), label.upper(), 184, 2, 27, 24, font_fn=lambda size: _font_label(size, False), bold=False)
        left_font, left_lines = _fit(ImageDraw.Draw(canvas), left_value, value_width, 2, 38, 29, font_fn=_font_headline)
        right_font, right_lines = _fit(ImageDraw.Draw(canvas), right_value, value_width, 2, 38, 29, font_fn=_font_headline)
        label_h, label_gap = _lines_metric_height(ImageDraw.Draw(canvas), label_lines, label_font, 2)
        left_h, left_gap = _lines_metric_height(ImageDraw.Draw(canvas), left_lines, left_font, 2)
        right_h, right_gap = _lines_metric_height(ImageDraw.Draw(canvas), right_lines, right_font, 2)
        row_content_height = max(
            label_h * len(label_lines) + label_gap * max(0, len(label_lines) - 1),
            left_h * len(left_lines) + left_gap * max(0, len(left_lines) - 1),
            right_h * len(right_lines) + right_gap * max(0, len(right_lines) - 1),
        )
        if row_content_height + 18 > row_height:
            raise CardStudioError(
                f"Comparison row '{label}' does not fit the available height at readable sizes. "
                "Shorten the label/value or choose a position with more room."
            )
        row_y = cursor_y + max(0, (row_height - row_content_height) // 2)
        _draw_text_block(canvas, {"font": left_font, "lines": left_lines, "line_height": left_h, "line_gap": left_gap, "height": left_h * len(left_lines) + left_gap * max(0, len(left_lines) - 1)}, left_x, row_y, WHITE, width=value_width, centered=True)
        _draw_text_block(canvas, {"font": label_font, "lines": label_lines, "line_height": label_h, "line_gap": label_gap, "height": label_h * len(label_lines) + label_gap * max(0, len(label_lines) - 1)}, centre_x - 92, row_y, MUTED, width=184, centered=True)
        _draw_text_block(canvas, {"font": right_font, "lines": right_lines, "line_height": right_h, "line_gap": right_gap, "height": right_h * len(right_lines) + right_gap * max(0, len(right_lines) - 1)}, right_x, row_y, WHITE, width=value_width, centered=True)
        cursor_y += row_height

    y = header_top
    for block in header_blocks:
        if block.get("kind") == "kicker":
            y = _draw_kicker(canvas, header_x, y, block["text"], block.get("language", "english"))
        else:
            _draw_text_block(canvas, block, header_x, y, WHITE)
            y += block["height"]
        y += block.get("gap_after", 0)
    return canvas.convert("RGB")


def _render_fact_milestone(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    image, mask = _cover_with_mask(source, subject_mask)
    position = _resolve_layout_position(image, mask, data)
    x, width = _content_region(position)
    bottom_mode = position == "bottom"
    top = 900 if bottom_mode else SAFE_TOP
    language = _normalise_card_language(data.get("language"))
    draw = ImageDraw.Draw(image)
    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    blocks = [{
        "kind": "kicker",
        "text": str(data.get("eyebrow") or _card_label("milestone", language)),
        "language": language, "height": 56,
        "gap_after": 14 if bottom_mode else 20,
    }]
    value_block = _text_block(
        draw, value, width,
        preferred_size=164 if not bottom_mode else 122,
        minimum_size=78 if not bottom_mode else 70,
        max_lines=2, font_fn=_font_display, gap=3,
    )
    if value_block:
        value_block.update({"kind": "text", "fill": ACCENT, "gap_after": 12 if bottom_mode else 22})
        blocks.append(value_block)
    label_block = _text_block(
        draw, label, width,
        preferred_size=60 if not bottom_mode else 49,
        minimum_size=43 if not bottom_mode else 38,
        max_lines=3 if not bottom_mode else 2,
        font_fn=_font_headline, gap=5,
    )
    if label_block:
        label_block.update({"kind": "text", "fill": WHITE, "gap_after": 16 if bottom_mode else 22})
        blocks.append(label_block)
    support_fields = _supporting_fields(data, "Key Fact / Milestone")
    if data.get("context") and not any(item["label"].casefold() == "context" for item in support_fields):
        support_fields.append({"label": "Context", "value": str(data.get("context"))})
    support = _make_support_rows(draw, support_fields, width, bottom_mode=bottom_mode)
    if support:
        blocks.append(support)
    return _draw_editorial_stack(
        image, position, str(data.get("contrast_treatment") or "Adaptive gradient"),
        x, width, top, blocks,
    )


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


def card_data_for_type(card_type: str, language: str = "english") -> dict:
    """Return blank editable content; story/prompt generation supplies variable supporting fields."""
    language_key = _normalise_card_language(language)
    data = {
        "layout_position": CARD_LAYOUT_POSITIONS[0],
        "contrast_treatment": CARD_CONTRAST_TREATMENTS[0],
        "language": language_key,
        "eyebrow": "",
    }
    if card_type == "Stat Highlight":
        data.update({"headline": "", "value": "", "unit": "", "supporting_fields": []})
    elif card_type == "Quote / Reaction":
        data.update({"quote": "", "attribution": "", "supporting_fields": []})
    elif card_type == "Head-to-Head":
        data.update({
            "headline": "",
            "image_mode": "One image",
            "split_direction": "Vertical",
            "left": {"name": "", "values": {}},
            "right": {"name": "", "values": {}},
            "metrics": [],
        })
    elif card_type == "Key Fact / Milestone":
        data.update({"value": "", "label": "", "supporting_fields": []})
    else:
        return {}
    if language_key == "hindi":
        data["eyebrow"] = {
            "Stat Highlight": "करियर के आँकड़े",
            "Quote / Reaction": "प्रतिक्रिया",
            "Head-to-Head": "आमने-सामने",
            "Key Fact / Milestone": "उपलब्धि",
        }.get(card_type, "")
    elif language_key == "telugu":
        data["eyebrow"] = {
            "Stat Highlight": "కెరీర్ గణాంకాలు",
            "Quote / Reaction": "స్పందన",
            "Head-to-Head": "ఎదురెదురు పోటీ",
            "Key Fact / Milestone": "మైలురాయి",
        }.get(card_type, "")
    return data

