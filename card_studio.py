"""Editorial Card Studio layouts for Final-Shorts.

Card Studio produces static 1080x1920 frames for manual QC.
WIP cards use multiple content-driven compositions; Text Subject Cutout remains
owned by the shared subject-cutout editor in app.py.
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
MUTED = (195, 201, 209)
DARK = (5, 7, 10)
PANEL = (8, 10, 14, 190)
LINE = (255, 255, 255)

CARD_TYPES = (
    "Text Subject Cutout",
    "Stat Highlight",
    "Quote / Reaction",
    "Head-to-Head",
    "Key Fact / Milestone",
)

TEST_CARD_TYPES = CARD_TYPES
LIVE_CARD_TYPES = ("Text Subject Cutout",)

CARD_COMPOSITIONS = {
    "Stat Highlight": ("Hero Signal", "Data Stack", "Metric Rail"),
    "Quote / Reaction": ("Quote Lead", "Reaction Panel", "Context Lead"),
    "Head-to-Head": ("Duel Columns", "Comparison Board", "Split Face-Off"),
    "Key Fact / Milestone": ("Number Lead", "Record Side", "Story Lead"),
}


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


def _cover(
    source: bytes | bytearray | Image.Image,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> Image.Image:
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


def _measure(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int]:
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
    for size in range(start_size, min_size - 1, -2):
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


def _subject_occupancy(mask: Image.Image | None, box: tuple[int, int, int, int]) -> float:
    if not isinstance(mask, Image.Image):
        return 0.0
    mask = mask.convert("L")
    if mask.size != (WIDTH, HEIGHT):
        mask = mask.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    x1, y1, x2, y2 = box
    x1 = max(0, min(WIDTH - 1, x1))
    y1 = max(0, min(HEIGHT - 1, y1))
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
    max_x = max(rx1, rx2 - width)
    max_y = max(ry1, ry2 - height)
    x_values = sorted({
        rx1,
        max(rx1, (rx1 + max_x) // 2),
        max_x,
    })
    y_values = sorted({
        ry1,
        max(ry1, ry1 + max(0, max_y - ry1) // 3),
        max(ry1, ry1 + max(0, max_y - ry1) * 2 // 3),
        max_y,
    })
    candidates = []
    for x in x_values:
        for y in y_values:
            occupancy = _subject_occupancy(mask, (x, y, x + width, y + height))
            distance = (abs(x - preferred_x) / 240) + (abs(y - preferred_y) / 240)
            candidates.append((occupancy * 6 + distance, x, y))
    _, x, y = min(candidates, key=lambda item: item[0])
    return int(x), int(y)


def card_composition_options(card_type: str) -> tuple[str, ...]:
    options = CARD_COMPOSITIONS.get(card_type)
    if not options:
        return ("Auto",)
    return ("Auto",) + tuple(options)


def _auto_composition(card_type: str, data: dict) -> str:
    if card_type == "Stat Highlight":
        metric_count = len(data.get("metrics") or [])
        if metric_count >= 3:
            return "Data Stack"
        if metric_count == 1:
            return "Hero Signal"
        return "Metric Rail"

    if card_type == "Quote / Reaction":
        quote = " ".join(str(data.get("quote") or "").split())
        context = " ".join(str(data.get("context") or "").split())
        if len(context) >= 55:
            return "Context Lead"
        if len(quote) >= 84:
            return "Reaction Panel"
        return "Quote Lead"

    if card_type == "Head-to-Head":
        if str(data.get("image_mode") or "One image") == "Two images":
            return "Split Face-Off"
        return "Comparison Board" if len(data.get("metrics") or []) >= 3 else "Duel Columns"

    if card_type == "Key Fact / Milestone":
        value = " ".join(str(data.get("value") or "").split())
        label = " ".join(str(data.get("label") or "").split())
        context = " ".join(str(data.get("context") or "").split())
        if len(context) >= 55:
            return "Story Lead"
        if len(value) >= 4 or len(label) < 24:
            return "Number Lead"
        return "Record Side"

    return ""


def _composition(card_type: str, data: dict) -> str:
    requested = " ".join(str(data.get("composition") or "").split())
    options = card_composition_options(card_type)
    if requested in options[1:]:
        return requested
    return _auto_composition(card_type, data)


def _background(source) -> Image.Image:
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 42))
    for top in range(HEIGHT):
        if top < 680:
            alpha = 0
        elif top >= 1500:
            alpha = 222
        else:
            alpha = int((top - 680) / 820 * 222)
        draw.line((0, top, WIDTH, top), fill=(0, 0, 0, alpha))
    draw.rectangle(
        (SAFE_LEFT - 18, SAFE_TOP - 18, SAFE_RIGHT + 16, SAFE_BOTTOM + 18),
        fill=(0, 0, 0, 18),
    )
    draw.rectangle(
        (SAFE_LEFT - 18, SAFE_TOP - 18, SAFE_LEFT - 10, SAFE_BOTTOM + 18),
        fill=ACCENT,
    )
    return Image.alpha_composite(base, overlay)


def _kicker(canvas: Image.Image, text: str, y: int = SAFE_TOP) -> int:
    draw = ImageDraw.Draw(canvas)
    clean = " ".join(str(text or "").split()).upper() or "STORY"
    draw.text((SAFE_LEFT, y - 2), clean, font=_font(32), fill=MUTED)
    draw.line((SAFE_LEFT, y + 46, SAFE_LEFT + 74, y + 46), fill=ACCENT, width=6)
    return y + 86


def _panel(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int] = PANEL,
    radius: int = 24,
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(box, radius=radius, fill=fill)
    canvas.alpha_composite(overlay)


def _metric_row(
    canvas: Image.Image,
    y: int,
    label: str,
    value: str,
    x1: int = SAFE_LEFT,
    x2: int = SAFE_RIGHT,
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.line((x1, y, x2, y), fill=LINE, width=2)
    draw.text(
        (x1 + 6, y + 16),
        " ".join(label.split()).upper(),
        font=_font(25, False),
        fill=MUTED,
    )
    draw.text(
        (x2 - 6, y + 6),
        " ".join(value.split()),
        font=_font(56),
        fill=WHITE,
        anchor="ra",
        stroke_width=1,
        stroke_fill=DARK,
    )


def _render_stat_highlight(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    composition = _composition("Stat Highlight", data)
    headline = " ".join(str(data.get("headline") or "").split())
    value = " ".join(str(data.get("value") or "").split())
    unit = " ".join(str(data.get("unit") or "").split())
    metrics = data.get("metrics") or []

    if not headline or not value:
        raise CardStudioError("Stat Highlight needs a headline and a hero value.")
    if len(metrics) > 3:
        raise CardStudioError("Stat Highlight supports at most three supporting metrics.")

    if composition == "Hero Signal":
        y = _kicker(canvas, data.get("eyebrow") or "STAT")
        headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 58)
        headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
        headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 8 * (len(headline_lines) - 1)
        x, y_text = _best_text_position(
            subject_mask, headline_width, headline_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 690), SAFE_LEFT, y,
        )
        y = _draw_lines(canvas, headline_lines, x, y_text, headline_font, 8) + 34
        value_font = _font(292)
        value_width, value_height = _measure(draw, value, value_font)
        if value_width > SAFE_RIGHT - SAFE_LEFT:
            value_font, _ = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 1, 240, 120)
            value_width, value_height = _measure(draw, value, value_font)
        x, y_value = _best_text_position(
            subject_mask, value_width, value_height,
            (SAFE_LEFT, max(560, y), SAFE_RIGHT, 1080), SAFE_LEFT, 690,
        )
        draw.text((x, y_value), value, font=value_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
        if unit:
            draw.text(
                (x + value_width + 18, y_value + max(8, value_height - 55)),
                unit.upper(), font=_font(44), fill=ACCENT,
            )
        metric_y = 1110
        for metric in metrics:
            _metric_row(canvas, metric_y, metric["label"], metric["value"])
            metric_y += 106
        return canvas

    if composition == "Data Stack":
        y = _kicker(canvas, data.get("eyebrow") or "STAT")
        headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 3, 88, 52)
        headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
        headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 6 * (len(headline_lines) - 1)
        x, y_text = _best_text_position(
            subject_mask, headline_width, headline_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 650), SAFE_LEFT, y,
        )
        _draw_lines(canvas, headline_lines, x, y_text, headline_font, 6)
        _panel(canvas, (SAFE_LEFT, 690, 520, 1115), fill=PANEL, radius=30)
        value_font, _ = _fit(draw, value, 390, 1, 220, 100)
        draw.text((SAFE_LEFT + 30, 735), value, font=value_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
        if unit:
            draw.text((SAFE_LEFT + 34, 1010), unit.upper(), font=_font(40), fill=ACCENT)
        metric_y = 710
        for index, metric in enumerate(metrics):
            y_metric = metric_y + index * 132
            x1 = 560
            draw.text((x1, y_metric), " ".join(metric["label"].split()).upper(), font=_font(25, False), fill=MUTED)
            metric_value_font, _ = _fit(draw, metric["value"], 260, 1, 58, 34)
            draw.text((x1, y_metric + 34), metric["value"], font=metric_value_font, fill=WHITE, stroke_width=2, stroke_fill=DARK)
            if index < len(metrics) - 1:
                draw.line((x1, y_metric + 104, SAFE_RIGHT, y_metric + 104), fill=LINE, width=2)
        return canvas

    y = _kicker(canvas, data.get("eyebrow") or "STAT")
    value_font = _font(264)
    value_width, value_height = _measure(draw, value, value_font)
    if value_width > SAFE_RIGHT - SAFE_LEFT:
        value_font, _ = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 1, 220, 104)
        value_width, value_height = _measure(draw, value, value_font)
    x, y_value = _best_text_position(
        subject_mask, value_width, value_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 920), SAFE_LEFT, 380,
    )
    draw.text((x, y_value), value, font=value_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
    if unit:
        draw.text(
            (x, y_value + value_height + 10),
            unit.upper(),
            font=_font(38, False),
            fill=ACCENT,
        )
    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 72, 48)
    headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
    headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 5 * (len(headline_lines) - 1)
    x, y_head = _best_text_position(
        subject_mask, headline_width, headline_height,
        (SAFE_LEFT, 930, SAFE_RIGHT, 1160), SAFE_LEFT, 980,
    )
    _draw_lines(canvas, headline_lines, x, y_head, headline_font, 5)
    if metrics:
        columns = max(1, len(metrics))
        column_width = (SAFE_RIGHT - SAFE_LEFT) // columns
        for index, metric in enumerate(metrics):
            x1 = SAFE_LEFT + index * column_width
            x2 = SAFE_LEFT + (index + 1) * column_width
            draw.line((x1, 1195, x2 - 12, 1195), fill=LINE, width=2)
            draw.text((x1, 1220), metric["label"].upper(), font=_font(22, False), fill=MUTED)
            metric_font, _ = _fit(draw, metric["value"], max(110, column_width - 18), 1, 46, 30)
            draw.text((x1, 1258), metric["value"], font=metric_font, fill=WHITE, stroke_width=2, stroke_fill=DARK)
    return canvas


def _render_quote_reaction(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    composition = _composition("Quote / Reaction", data)
    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    if composition == "Reaction Panel":
        draw.rectangle((0, 820, WIDTH, HEIGHT), fill=(0, 0, 0, 120))
        y = 880
        quote_font, quote_lines = _fit(draw, quote, SAFE_RIGHT - SAFE_LEFT, 5, 96, 58)
        quote_width = max(_measure(draw, line, quote_font)[0] for line in quote_lines)
        quote_height = _measure(draw, "Ag", quote_font)[1] * len(quote_lines) + 12 * (len(quote_lines) - 1)
        x, y_quote = _best_text_position(
            subject_mask, quote_width, quote_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 1380), SAFE_LEFT, 930,
        )
        _draw_lines(canvas, quote_lines, x, y_quote, quote_font, 12)
        rule_y = y_quote + quote_height + 32
        draw.line((x, rule_y, min(SAFE_RIGHT, x + 560)), fill=ACCENT, width=5)
        attr_font, attr_lines = _fit(draw, attribution, SAFE_RIGHT - SAFE_LEFT, 2, 46, 32)
        _draw_lines(canvas, attr_lines, x, rule_y + 24, attr_font, 6)
        if context:
            ctx_font, ctx_lines = _fit(draw, context, SAFE_RIGHT - SAFE_LEFT, 2, 34, 28, bold=False)
            _draw_lines(canvas, ctx_lines, x, rule_y + 118, ctx_font, 7, MUTED)
        return canvas

    y = _kicker(canvas, data.get("eyebrow") or "REACTION")
    if composition == "Context Lead":
        context_font, context_lines = _fit(draw, context or "THE MOMENT", SAFE_RIGHT - SAFE_LEFT, 3, 56, 36)
        context_width = max(_measure(draw, line, context_font)[0] for line in context_lines)
        context_height = _measure(draw, "Ag", context_font)[1] * len(context_lines) + 7 * (len(context_lines) - 1)
        x, y_context = _best_text_position(
            subject_mask, context_width, context_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 620), SAFE_LEFT, y,
        )
        _draw_lines(canvas, context_lines, x, y_context, context_font, 7, WHITE)
        y = y_context + context_height + 44
        quote_limit = 3
    else:
        quote_limit = 5

    quote_font, quote_lines = _fit(
        draw, quote, SAFE_RIGHT - SAFE_LEFT - 14,
        quote_limit, 118 if composition == "Quote Lead" else 100,
        64 if composition == "Quote Lead" else 56,
    )
    quote_width = max(_measure(draw, line, quote_font)[0] for line in quote_lines)
    quote_height = _measure(draw, "Ag", quote_font)[1] * len(quote_lines) + 12 * (len(quote_lines) - 1)
    x, y_quote = _best_text_position(
        subject_mask, quote_width + 20, quote_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 1080), SAFE_LEFT, 430,
    )
    draw.text((x - 6, y_quote - 36), "“", font=_font(110), fill=ACCENT)
    _draw_lines(canvas, quote_lines, x + 28, y_quote, quote_font, 12)
    rule_y = y_quote + quote_height + 42
    draw.line((x + 28, rule_y, min(SAFE_RIGHT, x + 610)), fill=ACCENT, width=4)
    attr_font, attr_lines = _fit(draw, attribution, SAFE_RIGHT - SAFE_LEFT - 28, 2, 50, 34)
    _draw_lines(canvas, attr_lines, x + 28, rule_y + 26, attr_font, 7)
    if context and composition == "Quote Lead":
        ctx_font, ctx_lines = _fit(draw, context, SAFE_RIGHT - SAFE_LEFT - 28, 3, 34, 28, bold=False)
        _draw_lines(canvas, ctx_lines, x + 28, rule_y + 112, ctx_font, 7, MUTED)
    return canvas


def _combined_split_mask(
    masks: tuple[Image.Image, Image.Image] | list[Image.Image],
    direction: str,
) -> Image.Image | None:
    if not isinstance(masks, (tuple, list)) or len(masks) != 2:
        return None
    first = masks[0].convert("L")
    second = masks[1].convert("L")
    if direction == "Horizontal":
        split = HEIGHT // 2
        combined = Image.new("L", (WIDTH, HEIGHT), 0)
        combined.paste(first.resize((WIDTH, split), Image.Resampling.BILINEAR), (0, 0))
        combined.paste(second.resize((WIDTH, HEIGHT - split), Image.Resampling.BILINEAR), (0, split))
        return combined
    split = WIDTH // 2
    combined = Image.new("L", (WIDTH, HEIGHT), 0)
    combined.paste(first.resize((split, HEIGHT), Image.Resampling.BILINEAR), (0, 0))
    combined.paste(second.resize((WIDTH - split, HEIGHT), Image.Resampling.BILINEAR), (split, 0))
    return combined


def _side_split_mask(
    mask: Image.Image | None,
    direction: str,
    side: int,
) -> Image.Image | None:
    if not isinstance(mask, Image.Image):
        return None
    source = mask.convert("L")
    if direction == "Horizontal":
        split = HEIGHT // 2
        box = (0, 0, WIDTH, split) if side == 0 else (0, split, WIDTH, HEIGHT)
        cropped = source.crop(box)
        return cropped.resize((WIDTH, split if side == 0 else HEIGHT - split), Image.Resampling.BILINEAR)
    split = WIDTH // 2
    box = (0, 0, split, HEIGHT) if side == 0 else (split, 0, WIDTH, HEIGHT)
    cropped = source.crop(box)
    return cropped.resize((split if side == 0 else WIDTH - split, HEIGHT), Image.Resampling.BILINEAR)


def _render_two_image_head_to_head(
    source_pair,
    data: dict,
    masks: tuple[Image.Image, Image.Image] | None,
) -> Image.Image:
    direction = str(data.get("split_direction") or "Vertical")
    canvas = _split_image_source(source_pair, direction).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 36))

    if direction == "Horizontal":
        split = HEIGHT // 2
        draw.line((0, split, WIDTH, split), fill=LINE, width=5)
        top_region = (60, 100, WIDTH - 60, split - 60)
        bottom_region = (60, split + 50, WIDTH - 60, HEIGHT - 70)
        regions = (top_region, bottom_region)
    else:
        split = WIDTH // 2
        draw.line((split, 0, split, HEIGHT), fill=LINE, width=5)
        left_region = (60, 100, split - 34, HEIGHT - 80)
        right_region = (split + 34, 100, WIDTH - 60, HEIGHT - 80)
        regions = (left_region, right_region)

    combined_mask = _combined_split_mask(masks, direction) if masks else None
    headline_font, headline_lines = _fit(draw, data["headline"], WIDTH - 120, 2, 86, 54)
    headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
    headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 5 * (len(headline_lines) - 1)
    hx, hy = _best_text_position(
        combined_mask, headline_width, headline_height,
        (60, 90, WIDTH - 60, 610), (WIDTH - headline_width) // 2, 150,
    )
    _draw_lines(canvas, headline_lines, hx, hy, headline_font, 5)

    for index, (region, side) in enumerate(((regions[0], data["left"]), (regions[1], data["right"]))):
        x1, y1, x2, y2 = region
        side_mask = _side_split_mask(masks[index], direction, 0) if masks else None
        if direction == "Horizontal":
            side_mask = _side_split_mask(masks[index], direction, index) if masks else None
        elif masks:
            side_mask = masks[index].resize(
                (x2 - x1, y2 - y1),
                Image.Resampling.BILINEAR,
            )
        name_font, name_lines = _fit(draw, side["name"], max(180, x2 - x1 - 30), 2, 62, 40)
        name_width = max(_measure(draw, line, name_font)[0] for line in name_lines)
        name_height = _measure(draw, "Ag", name_font)[1] * len(name_lines) + 5 * (len(name_lines) - 1)
        nx, ny = _best_text_position(
            side_mask, name_width, name_height,
            region, x1, max(y1 + 40, y2 - 500),
        )
        _draw_lines(canvas, name_lines, nx, ny, name_font, 5)
        metric_y = ny + name_height + 36
        for label in data["metrics"]:
            metric_label = " ".join(str(label).split())
            value = " ".join(str((side.get("values") or {}).get(metric_label) or "").split())
            if not value:
                raise CardStudioError(f"Both sides need a value for {metric_label}.")
            draw.text((x1, metric_y), metric_label.upper(), font=_font(23, False), fill=MUTED)
            value_font, _ = _fit(draw, value, max(140, x2 - x1 - 10), 1, 58, 34)
            draw.text((x1, metric_y + 32), value, font=value_font, fill=WHITE, stroke_width=2, stroke_fill=DARK)
            metric_y += 104
    return canvas.convert("RGB")


def _render_head_to_head(source, data: dict, subject_mask=None) -> Image.Image:
    headline = " ".join(str(data.get("headline") or "").split())
    left = data.get("left") or {}
    right = data.get("right") or {}
    metrics = list(data.get("metrics") or [])
    image_mode = str(data.get("image_mode") or "One image")

    if not headline or not left.get("name") or not right.get("name"):
        raise CardStudioError("Head-to-Head needs a headline and both names.")
    if not 1 <= len(metrics) <= 3:
        raise CardStudioError("Head-to-Head needs one to three comparison metrics.")

    if image_mode == "Two images":
        return _render_two_image_head_to_head(source, data, subject_mask)

    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    composition = _composition("Head-to-Head", data)
    y = _kicker(canvas, data.get("eyebrow") or "HEAD TO HEAD")

    if composition == "Comparison Board":
        headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 82, 52)
        headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
        headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 5 * (len(headline_lines) - 1)
        hx, hy = _best_text_position(
            subject_mask, headline_width, headline_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 620), SAFE_LEFT, y,
        )
        _draw_lines(canvas, headline_lines, hx, hy, headline_font, 5)
        y = max(650, hy + headline_height + 34)
        _panel(canvas, (SAFE_LEFT, y, SAFE_RIGHT, 1370), fill=(8, 10, 14, 198), radius=30)
        split_x = WIDTH // 2
        draw.line((split_x, y + 30, split_x, 1340), fill=LINE, width=2)
        for x, side in ((SAFE_LEFT + 28, left), (split_x + 28, right)):
            name_font, name_lines = _fit(draw, side["name"], 330, 2, 58, 40)
            _draw_lines(canvas, name_lines, x, y + 38, name_font, 5)
        metric_y = y + 188
        for label in metrics:
            metric_label = " ".join(str(label).split())
            lval = " ".join(str((left.get("values") or {}).get(metric_label) or "").split())
            rval = " ".join(str((right.get("values") or {}).get(metric_label) or "").split())
            if not lval or not rval:
                raise CardStudioError(f"Both sides need a value for {metric_label}.")
            draw.text((SAFE_LEFT + 28, metric_y), metric_label.upper(), font=_font(23, False), fill=MUTED)
            draw.text((split_x + 28, metric_y), metric_label.upper(), font=_font(23, False), fill=MUTED)
            lf, _ = _fit(draw, lval, 320, 1, 58, 34)
            rf, _ = _fit(draw, rval, 320, 1, 58, 34)
            draw.text((SAFE_LEFT + 28, metric_y + 32), lval, font=lf, fill=WHITE, stroke_width=2, stroke_fill=DARK)
            draw.text((split_x + 28, metric_y + 32), rval, font=rf, fill=WHITE, stroke_width=2, stroke_fill=DARK)
            draw.line((SAFE_LEFT + 28, metric_y + 94, SAFE_RIGHT - 28, metric_y + 94), fill=LINE, width=2)
            metric_y += 118
        return canvas

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 92, 56)
    headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
    headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 6 * (len(headline_lines) - 1)
    hx, hy = _best_text_position(
        subject_mask, headline_width, headline_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 690), SAFE_LEFT, y,
    )
    _draw_lines(canvas, headline_lines, hx, hy, headline_font, 6)
    y = hy + headline_height + 46

    split_x = (SAFE_LEFT + SAFE_RIGHT) // 2
    draw.line((split_x, y, split_x, SAFE_BOTTOM), fill=LINE, width=2)

    for x, side in ((SAFE_LEFT, left), (split_x + 28, right)):
        name_font, name_lines = _fit(draw, side["name"], 300, 2, 58, 40)
        _draw_lines(canvas, name_lines, x, y + 16, name_font, 5)

    metric_y = y + 142
    for label in metrics:
        metric_label = " ".join(str(label).split())
        lval = " ".join(str((left.get("values") or {}).get(metric_label) or "").split())
        rval = " ".join(str((right.get("values") or {}).get(metric_label) or "").split())
        if not lval or not rval:
            raise CardStudioError(f"Both sides need a value for {metric_label}.")
        draw.text((SAFE_LEFT, metric_y), metric_label.upper(), font=_font(24, False), fill=MUTED)
        draw.text((split_x + 28, metric_y), metric_label.upper(), font=_font(24, False), fill=MUTED)
        lf, _ = _fit(draw, lval, 300, 1, 60, 36)
        rf, _ = _fit(draw, rval, 300, 1, 60, 36)
        draw.text((SAFE_LEFT, metric_y + 32), lval, font=lf, fill=WHITE, stroke_width=2, stroke_fill=DARK)
        draw.text((split_x + 28, metric_y + 32), rval, font=rf, fill=WHITE, stroke_width=2, stroke_fill=DARK)
        draw.line((SAFE_LEFT, metric_y + 100, SAFE_RIGHT, metric_y + 100), fill=LINE, width=2)
        metric_y += 122

    return canvas


def _render_fact_milestone(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    composition = _composition("Key Fact / Milestone", data)
    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    if composition == "Record Side":
        y = _kicker(canvas, data.get("eyebrow") or "MILESTONE")
        _panel(canvas, (SAFE_LEFT, 350, 500, 1030), fill=PANEL, radius=30)
        label_font, label_lines = _fit(draw, label, 360, 4, 66, 40)
        _draw_lines(canvas, label_lines, SAFE_LEFT + 30, 405, label_font, 7)
        value_font, _ = _fit(draw, value, 300, 1, 180, 92)
        draw.text((570, 420), value, font=value_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
        draw.text((575, 610), "THE MILESTONE", font=_font(25, False), fill=ACCENT)
        if context:
            context_font, context_lines = _fit(draw, context, 350, 5, 38, 28, bold=False)
            _draw_lines(canvas, context_lines, 570, 690, context_font, 8, MUTED)
        return canvas

    if composition == "Story Lead":
        y = _kicker(canvas, data.get("eyebrow") or "MILESTONE")
        label_font, label_lines = _fit(draw, label, SAFE_RIGHT - SAFE_LEFT, 3, 92, 54)
        label_width = max(_measure(draw, line, label_font)[0] for line in label_lines)
        label_height = _measure(draw, "Ag", label_font)[1] * len(label_lines) + 7 * (len(label_lines) - 1)
        x, y_label = _best_text_position(
            subject_mask, label_width, label_height,
            (SAFE_LEFT, y, SAFE_RIGHT, 800), SAFE_LEFT, y,
        )
        _draw_lines(canvas, label_lines, x, y_label, label_font, 7)
        y_number = max(820, y_label + label_height + 26)
        _panel(canvas, (SAFE_LEFT, y_number, 620, 1120), fill=(8, 10, 14, 188), radius=24)
        value_font, _ = _fit(draw, value, 490, 1, 190, 96)
        draw.text((SAFE_LEFT + 32, y_number + 35), value, font=value_font, fill=WHITE, stroke_width=3, stroke_fill=DARK)
        if context:
            context_font, context_lines = _fit(draw, context, SAFE_RIGHT - SAFE_LEFT, 4, 38, 28, bold=False)
            _draw_lines(canvas, context_lines, SAFE_LEFT, 1190, context_font, 8, MUTED)
        return canvas

    y = _kicker(canvas, data.get("eyebrow") or "MILESTONE")
    value_font, value_lines = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 2, 230, 106)
    value_width = max(_measure(draw, line, value_font)[0] for line in value_lines)
    value_height = _measure(draw, "Ag", value_font)[1] * len(value_lines) + 5 * (len(value_lines) - 1)
    x, y_value = _best_text_position(
        subject_mask, value_width, value_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 900), SAFE_LEFT, 360,
    )
    _draw_lines(canvas, value_lines, x, y_value, value_font, 5)
    label_font, label_lines = _fit(draw, label, SAFE_RIGHT - SAFE_LEFT, 3, 76, 44)
    label_width = max(_measure(draw, line, label_font)[0] for line in label_lines)
    label_height = _measure(draw, "Ag", label_font)[1] * len(label_lines) + 7 * (len(label_lines) - 1)
    x, y_label = _best_text_position(
        subject_mask, label_width, label_height,
        (SAFE_LEFT, 830, SAFE_RIGHT, 1230), SAFE_LEFT, max(900, y_value + value_height),
    )
    _draw_lines(canvas, label_lines, x, y_label, label_font, 7)
    if context:
        context_font, context_lines = _fit(draw, context, SAFE_RIGHT - SAFE_LEFT, 4, 38, 28, bold=False)
        _draw_lines(canvas, context_lines, SAFE_LEFT, max(1270, y_label + label_height + 20), context_font, 8, MUTED)
    return canvas


def _split_image_source(source_pair, direction: str) -> Image.Image:
    if not isinstance(source_pair, (tuple, list)) or len(source_pair) != 2:
        raise CardStudioError("Two-image Head-to-Head needs two source images.")
    if direction == "Horizontal":
        split = HEIGHT // 2
        top = _cover(source_pair[0], WIDTH, split)
        bottom = _cover(source_pair[1], WIDTH, HEIGHT - split)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), DARK)
        canvas.paste(top, (0, 0))
        canvas.paste(bottom, (0, split))
        return canvas
    split = WIDTH // 2
    left = _cover(source_pair[0], split, HEIGHT)
    right = _cover(source_pair[1], WIDTH - split, HEIGHT)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), DARK)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (split, 0))
    return canvas


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
            "composition": "Auto",
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
            "composition": "Auto",
            "eyebrow": "POST-MATCH REACTION",
            "quote": "We believed from the first ball.",
            "attribution": "Player Name · after the final",
            "context": "The reaction came after the latest match.",
        }
    if card_type == "Head-to-Head":
        return {
            "composition": "Auto",
            "eyebrow": "HEAD TO HEAD",
            "headline": "Who has the edge?",
            "image_mode": "One image",
            "split_direction": "Vertical",
            "left": {
                "name": "Player A",
                "values": {
                    "Runs": "1,020",
                    "Average": "48.4",
                    "Strike Rate": "132.4",
                },
            },
            "right": {
                "name": "Player B",
                "values": {
                    "Runs": "934",
                    "Average": "42.1",
                    "Strike Rate": "121.8",
                },
            },
            "metrics": ["Runs", "Average", "Strike Rate"],
        }
    if card_type == "Key Fact / Milestone":
        return {
            "composition": "Auto",
            "eyebrow": "MILESTONE",
            "value": "100",
            "label": "International appearances",
            "context": "A landmark reached in the latest match.",
        }
    return {}
