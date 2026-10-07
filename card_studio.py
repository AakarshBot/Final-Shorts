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
MUTED = (195, 201, 209)
DARK = (5, 7, 10)
DIVIDER = (255, 255, 255, 42)


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
    x1 = max(0, min(WIDTH, x1))
    y1 = max(0, min(HEIGHT, y1))
    x2 = max(x1 + 1, min(WIDTH, x2))
    y2 = max(y1 + 1, min(HEIGHT, y2))
    crop = mask.crop((x1, y1, x2, y2))
    histogram = crop.histogram()
    return sum(histogram[96:]) / max(1, (x2 - x1) * (y2 - y1) * 255)


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


def _background(source: bytes | bytearray | Image.Image) -> Image.Image:
    base = _cover(source).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 48))
    for top in range(HEIGHT):
        if top < 680:
            alpha = 0
        elif top >= 1500:
            alpha = 220
        else:
            alpha = int((top - 680) / 820 * 220)
        draw.line((0, top, WIDTH, top), fill=(0, 0, 0, alpha))
    draw.rectangle(
        (SAFE_LEFT - 18, SAFE_TOP - 18, SAFE_RIGHT + 16, SAFE_BOTTOM + 18),
        fill=(0, 0, 0, 22),
    )
    draw.rectangle(
        (SAFE_LEFT - 18, SAFE_TOP - 18, SAFE_LEFT - 10, SAFE_BOTTOM + 18),
        fill=ACCENT,
    )
    return Image.alpha_composite(base, overlay)


def _kicker(canvas: Image.Image, text: str) -> int:
    draw = ImageDraw.Draw(canvas)
    clean = " ".join(str(text or "").split()).upper() or "STORY"
    draw.text(
        (SAFE_LEFT, SAFE_TOP - 2),
        clean,
        font=_font(32),
        fill=MUTED,
    )
    draw.line(
        (SAFE_LEFT, SAFE_TOP + 46, SAFE_LEFT + 74, SAFE_TOP + 46),
        fill=ACCENT,
        width=6,
    )
    return SAFE_TOP + 86


def _draw_metric_row(
    canvas: Image.Image,
    y: int,
    label: str,
    value: str,
    x1: int = SAFE_LEFT,
    x2: int = SAFE_RIGHT,
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.line((x1, y, x2, y), fill=DIVIDER, width=2)
    draw.text(
        (x1 + 6, y + 18),
        " ".join(label.split()).upper(),
        font=_font(27, False),
        fill=MUTED,
    )
    draw.text(
        (x2 - 6, y + 8),
        " ".join(value.split()),
        font=_font(58),
        fill=WHITE,
        anchor="ra",
        stroke_width=1,
        stroke_fill=DARK,
    )


def _render_stat_highlight(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
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

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 58)
    headline_w, headline_h = _measure(draw, " ".join(headline_lines), headline_font)
    headline_x, headline_y = _best_text_position(
        subject_mask,
        headline_w,
        headline_h * len(headline_lines) + 8 * max(0, len(headline_lines) - 1),
        (SAFE_LEFT, y, SAFE_RIGHT, 720),
        SAFE_LEFT,
        y,
    )
    y = _draw_lines(canvas, headline_lines, headline_x, headline_y, headline_font, 8) + 48

    value_font = _font(292)
    value_w, value_h = _measure(draw, value, value_font)
    if value_w > SAFE_RIGHT - SAFE_LEFT:
        value_font, _ = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 1, 240, 120)
        value_w, value_h = _measure(draw, value, value_font)

    value_x, value_y = _best_text_position(
        subject_mask,
        value_w + (_measure(draw, unit, _font(44))[0] + 18 if unit else 0),
        value_h,
        (SAFE_LEFT, 650, SAFE_RIGHT, 1080),
        SAFE_LEFT,
        max(700, y),
    )
    draw.text(
        (value_x, value_y),
        value,
        font=value_font,
        fill=WHITE,
        stroke_width=3,
        stroke_fill=DARK,
    )
    if unit:
        draw.text(
            (value_x + value_w + 18, value_y + max(8, value_h - 55)),
            unit.upper(),
            font=_font(44),
            fill=ACCENT,
        )

    metric_y = max(1120, value_y + value_h + 44)
    if metrics:
        for metric in metrics:
            label = " ".join(str(metric.get("label") or "").split())
            metric_value = " ".join(str(metric.get("value") or "").split())
            if not label or not metric_value:
                raise CardStudioError("Every supporting metric needs a label and value.")
            _draw_metric_row(canvas, metric_y, label, metric_value)
            metric_y += 112

    return canvas


def _render_quote_reaction(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)

    y = _kicker(canvas, data.get("eyebrow") or "REACTION")
    quote = " ".join(str(data.get("quote") or "").split())
    attribution = " ".join(str(data.get("attribution") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not quote or not attribution:
        raise CardStudioError("Quote / Reaction needs a quote and attribution.")

    quote_font, quote_lines = _fit(draw, quote, SAFE_RIGHT - SAFE_LEFT - 8, 5, 112, 64)
    quote_height = _measure(draw, "Ag", quote_font)[1] * len(quote_lines)
    quote_height += 15 * max(0, len(quote_lines) - 1)
    quote_width = max(_measure(draw, line, quote_font)[0] for line in quote_lines)
    quote_x, quote_y = _best_text_position(
        subject_mask,
        quote_width + 32,
        quote_height + 26,
        (SAFE_LEFT, y, SAFE_RIGHT, 1090),
        SAFE_LEFT,
        420,
    )

    draw.text(
        (quote_x - 4, quote_y - 28),
        "“",
        font=_font(104),
        fill=ACCENT,
    )
    _draw_lines(canvas, quote_lines, quote_x + 24, quote_y, quote_font, 15)

    rule_y = quote_y + quote_height + 46
    draw.line((quote_x + 24, rule_y, SAFE_RIGHT, rule_y), fill=ACCENT, width=4)

    attribution_font, attribution_lines = _fit(
        draw,
        attribution,
        SAFE_RIGHT - SAFE_LEFT - 24,
        2,
        52,
        36,
        bold=True,
    )
    attribution_y = rule_y + 28
    _draw_lines(canvas, attribution_lines, quote_x + 24, attribution_y, attribution_font, 8)

    if context:
        context_font, context_lines = _fit(
            draw,
            context,
            SAFE_RIGHT - SAFE_LEFT - 24,
            3,
            38,
            30,
            bold=False,
        )
        _draw_lines(
            canvas,
            context_lines,
            quote_x + 24,
            attribution_y + len(attribution_lines) * 54 + 18,
            context_font,
            8,
            MUTED,
        )

    return canvas


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
        canvas = _split_image_source(source, direction).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 34))
        if direction == "Horizontal":
            split = HEIGHT // 2
            draw.line((0, split, WIDTH, split), fill=(255, 255, 255, 150), width=5)
            left_region = (48, 90, 1032, split - 90)
            right_region = (48, split + 40, 1032, HEIGHT - 70)
            divider_x = 48
            divider_y = split + 10
        else:
            split = WIDTH // 2
            draw.line((split, 0, split, HEIGHT), fill=(255, 255, 255, 150), width=5)
            left_region = (48, 90, split - 34, HEIGHT - 90)
            right_region = (split + 34, 90, WIDTH - 48, HEIGHT - 90)

        headline_font, headline_lines = _fit(draw, headline, WIDTH - 96, 2, 88, 54)
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

        for region, side in ((left_region, left), (right_region, right)):
            x1, y1, x2, y2 = region
            name_font, name_lines = _fit(draw, str(side["name"]), max(160, x2 - x1 - 36), 2, 62, 40)
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
            _draw_lines(canvas, name_lines, name_x, name_y, name_font, 5)
            metric_y = name_y + name_height + 42
            side_values = side.get("values") or {}
            for label in metrics:
                metric_label = " ".join(str(label).split())
                value = " ".join(str(side_values.get(metric_label) or "").split())
                if not value:
                    raise CardStudioError(f"Both sides need a value for {metric_label}.")
                draw.text((x1, metric_y), metric_label.upper(), font=_font(24, False), fill=MUTED)
                value_font, _ = _fit(draw, value, max(120, x2 - x1), 1, 64, 38)
                draw.text((x1, metric_y + 34), value, font=value_font, fill=WHITE, stroke_width=2, stroke_fill=DARK)
                metric_y += 108
        return canvas.convert("RGB")

    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "HEAD TO HEAD")

    headline_font, headline_lines = _fit(draw, headline, SAFE_RIGHT - SAFE_LEFT, 2, 94, 58)
    headline_width = max(_measure(draw, line, headline_font)[0] for line in headline_lines)
    headline_height = _measure(draw, "Ag", headline_font)[1] * len(headline_lines) + 7 * (len(headline_lines) - 1)
    headline_x, headline_y = _best_text_position(
        subject_mask,
        headline_width,
        headline_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 700),
        SAFE_LEFT,
        y,
    )
    y = _draw_lines(canvas, headline_lines, headline_x, headline_y, headline_font, 7) + 42

    split_x = (SAFE_LEFT + SAFE_RIGHT) // 2
    draw.line((split_x, y, split_x, SAFE_BOTTOM), fill=DIVIDER, width=2)

    name_top = y
    for x, side in ((SAFE_LEFT, left), (split_x + 28, right)):
        name_font, name_lines = _fit(
            draw,
            str(side["name"]),
            split_x - SAFE_LEFT - 48,
            2,
            58,
            40,
        )
        _draw_lines(canvas, name_lines, x, name_top, name_font, 5)

    y = name_top + 140
    left_values = left.get("values") or {}
    right_values = right.get("values") or {}
    for label in metrics:
        metric_label = " ".join(str(label).split())
        lval = " ".join(str(left_values.get(metric_label) or "").split())
        rval = " ".join(str(right_values.get(metric_label) or "").split())
        if not lval or not rval:
            raise CardStudioError(f"Both sides need a value for {metric_label}.")
        draw.text((SAFE_LEFT, y), metric_label.upper(), font=_font(25, False), fill=MUTED)
        draw.text((split_x + 28, y), metric_label.upper(), font=_font(25, False), fill=MUTED)
        lfont, _ = _fit(draw, lval, split_x - SAFE_LEFT - 48, 1, 62, 40)
        rfont, _ = _fit(draw, rval, SAFE_RIGHT - split_x - 48, 1, 62, 40)
        draw.text((SAFE_LEFT, y + 34), lval, font=lfont, fill=WHITE, stroke_width=2, stroke_fill=DARK)
        draw.text((split_x + 28, y + 34), rval, font=rfont, fill=WHITE, stroke_width=2, stroke_fill=DARK)
        draw.line((SAFE_LEFT, y + 104, SAFE_RIGHT, y + 104), fill=DIVIDER, width=2)
        y += 126

    return canvas


def _render_fact_milestone(source, data: dict, subject_mask: Image.Image | None) -> Image.Image:
    canvas = _background(source)
    draw = ImageDraw.Draw(canvas)
    y = _kicker(canvas, data.get("eyebrow") or "MILESTONE")

    value = " ".join(str(data.get("value") or "").split())
    label = " ".join(str(data.get("label") or "").split())
    context = " ".join(str(data.get("context") or "").split())

    if not value or not label:
        raise CardStudioError("Key Fact / Milestone needs a value and label.")

    value_font, value_lines = _fit(draw, value, SAFE_RIGHT - SAFE_LEFT, 2, 230, 104)
    value_width = max(_measure(draw, line, value_font)[0] for line in value_lines)
    value_height = _measure(draw, "Ag", value_font)[1] * len(value_lines) + 5 * (len(value_lines) - 1)
    value_x, value_y = _best_text_position(
        subject_mask,
        value_width,
        value_height,
        (SAFE_LEFT, y, SAFE_RIGHT, 900),
        SAFE_LEFT,
        380,
    )
    y = _draw_lines(canvas, value_lines, value_x, value_y, value_font, 5) + 36

    label_font, label_lines = _fit(draw, label, SAFE_RIGHT - SAFE_LEFT, 3, 76, 44)
    label_width = max(_measure(draw, line, label_font)[0] for line in label_lines)
    label_height = _measure(draw, "Ag", label_font)[1] * len(label_lines) + 7 * (len(label_lines) - 1)
    label_x, label_y = _best_text_position(
        subject_mask,
        label_width,
        label_height,
        (SAFE_LEFT, 860, SAFE_RIGHT, 1220),
        SAFE_LEFT,
        max(900, y),
    )
    y = _draw_lines(canvas, label_lines, label_x, label_y, label_font, 7) + 24

    if context:
        context_font, context_lines = _fit(
            draw,
            context,
            SAFE_RIGHT - SAFE_LEFT,
            4,
            40,
            30,
            bold=False,
        )
        _draw_lines(canvas, context_lines, SAFE_LEFT, max(1260, y), context_font, 8, MUTED)

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
