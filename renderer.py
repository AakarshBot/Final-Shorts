"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import shutil
import subprocess
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 24

HEADLINE_SECONDS = 1.35
HEADLINE_TEXT = "THE GAME JUST CHANGED"
SOURCE_LABEL = "SPORTS DESK"

HEADLINE_SAFE_MARGIN = 60
HEADLINE_MAX_WIDTH = WIDTH - (HEADLINE_SAFE_MARGIN * 2)
HEADLINE_MAX_SIZE = 260
HEADLINE_MIN_SIZE = 120
HEADLINE_STROKE_WIDTH = 6
HEADLINE_MAX_LINES = 3
HEADLINE_MARKER_WIDTH = 56
HEADLINE_MARKER_HEIGHT = 8
HEADLINE_MARKER_GAP = 16
HEADLINE_LINE_GAP = 8

SUBTITLE_SAFE_MARGIN = 64
SUBTITLE_MAX_WIDTH = WIDTH - (SUBTITLE_SAFE_MARGIN * 2)
SUBTITLE_MAX_SIZE = 70
SUBTITLE_MIN_SIZE = 54
SUBTITLE_STROKE_WIDTH = 5
SUBTITLE_WORD_SPACING = 10
SUBTITLE_LINE_GAP = 14
SUBTITLE_Y = 1390

DASH_TRANSLATION = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "﹘": "-", "﹣": "-", "－": "-",
})

ACCENT = (255, 205, 66)
BRAND_BLUE = (35, 105, 255)
WHITE = (249, 250, 252)
DARK = (5, 7, 10)


TOP5_EDITORIAL_MARGIN_X = 72
TOP5_EDITORIAL_MAX_WIDTH = 860
TOP5_EDITORIAL_HEADLINE_MAX_SIZE = 148
TOP5_EDITORIAL_HEADLINE_MIN_SIZE = 38
TOP5_EDITORIAL_HEADLINE_LINE_GAP = 0
TOP5_EDITORIAL_BODY_SIZE = 42
TOP5_EDITORIAL_BODY_LINE_GAP = 10
TOP5_EDITORIAL_HEADLINE_BODY_GAP = 24
TOP5_EDITORIAL_STROKE_WIDTH = 2
TOP5_EDITORIAL_TEXT_FADE_BLUR = 5
TOP5_EDITORIAL_TEXT_FADE_ALPHA = 60
TOP5_EDITORIAL_SAFE_BOTTOM = 90
TOP5_EDITORIAL_STORY_Y = 880
TOP5_EDITORIAL_OPENER_Y = 760


@lru_cache(maxsize=256)
def _font(candidates: tuple[Path, ...], size: int):
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)

    for path in (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/ARLRDBD.TTF"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)

    return ImageFont.load_default()


@lru_cache(maxsize=64)
def _font_candidates(role: str, language: str) -> tuple[Path, ...]:
    root = Path(__file__).resolve().parent / "fonts"
    language = str(language or "english").casefold()

    if role == "headline":
        if language == "hindi":
            return (
                root / "NotoSansDevanagari-CondensedBlack.ttf",
                root / "NotoSansDevanagari-Black.ttf",
            )
        if language == "telugu":
            return (
                root / "NotoSansTelugu-CondensedBlack.ttf",
                root / "NotoSansTelugu-Black.ttf",
            )
        return (root / "Oswald-Bold.ttf",)

    if language == "hindi":
        return (
            root / "NotoSansDevanagariUI-ExtraBold.ttf",
            root / "NotoSansDevanagari-ExtraBold.ttf",
            root / "NotoSansDevanagari-Bold.ttf",
        )
    if language == "telugu":
        return (
            root / "NotoSansTelugu-ExtraBold.ttf",
            root / "NotoSansTelugu-Bold.ttf",
        )
    return (
        root / "Oswald-Bold.ttf",
    )


@lru_cache(maxsize=64)
def _headline_font_stack(size: int, language: str) -> tuple[object, ...]:
    candidates = list(_font_candidates("headline", language))
    candidates.extend(
        [
            Path("C:/Windows/Fonts/seguiemj.ttf"),
            Path("C:/Windows/Fonts/seguisym.ttf"),
            Path("C:/Windows/Fonts/Nirmala.ttf"),
            Path("C:/Windows/Fonts/NirmalaUI.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/msgothic.ttc"),
            Path("C:/Windows/Fonts/malgun.ttf"),
            Path("C:/Windows/Fonts/arialuni.ttf"),
            Path("C:/Windows/Fonts/seguisb.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansSymbols2-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
    )
    fonts = []
    seen = set()
    for path in candidates:
        key = str(path).casefold()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        try:
            fonts.append(ImageFont.truetype(str(path), size))
        except OSError:
            continue
    if not fonts:
        fonts.append(ImageFont.load_default())
    return tuple(fonts)


def _headline_font_supports(font, char: str) -> bool:
    if not char or char in "\n\r\t":
        return True
    try:
        actual = font.getmask(char)
        missing = font.getmask("\U0010ffff")
        return actual.size != missing.size or bytes(actual) != bytes(missing)
    except (AttributeError, OSError, ValueError):
        return False


def _headline_runs(text: str, fonts: tuple[object, ...]) -> list[tuple[str, object]]:
    if not text:
        return []
    runs = []
    current_font = None
    current_text = []
    for char in text:
        font = next((candidate for candidate in fonts if _headline_font_supports(candidate, char)), fonts[-1])
        if current_font is not None and font is not current_font:
            runs.append(("".join(current_text), current_font))
            current_text = []
        if current_font is None or font is not current_font:
            current_font = font
        current_text.append(char)
    if current_text:
        runs.append(("".join(current_text), current_font))
    return runs


def _measure_headline_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    fonts: tuple[object, ...],
) -> tuple[int, int]:
    runs = _headline_runs(text, fonts)
    if not runs:
        return 0, 0
    widths = []
    heights = []
    for run, font in runs:
        box = draw.textbbox(
            (0, 0),
            run,
            font=font,
            stroke_width=HEADLINE_STROKE_WIDTH,
        )
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    return sum(widths), max(heights)


def _measure(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    stroke_width: int = 0,
) -> tuple[int, int]:
    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width,
    )
    return box[2] - box[0], box[3] - box[1]


def _headline_lines(
    text: str,
    draw: ImageDraw.ImageDraw,
    fonts: tuple[object, ...],
) -> list[list[str]]:
    words = text.split()
    if not words:
        return []

    measurements = [
        _measure_headline_text(draw, word, fonts)[0]
        for word in words
    ]
    max_line_width = HEADLINE_MAX_WIDTH - HEADLINE_MARKER_WIDTH - HEADLINE_MARKER_GAP

    lines: list[list[str]] = []
    current: list[str] = []
    current_width = 0

    for word, word_width in zip(words, measurements):
        if word_width > max_line_width:
            raise ValueError("Headline contains a word that is too wide to fit.")
        next_width = (
            current_width
            + word_width
            + (HEADLINE_MARKER_GAP if current else 0)
        )
        if current and next_width > max_line_width:
            lines.append(current)
            current = [word]
            current_width = word_width
        else:
            current.append(word)
            current_width = next_width

    if current:
        lines.append(current)

    if len(lines) > HEADLINE_MAX_LINES:
        raise ValueError("Headline is too long to fit on screen.")

    return lines


@lru_cache(maxsize=256)
def _fit_headline_font(
    text: str,
    language: str = "english",
):
    clean = " ".join(str(text or "").upper().split()) or HEADLINE_TEXT
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    for size in range(HEADLINE_MAX_SIZE, HEADLINE_MIN_SIZE - 1, -1):
        fonts = _headline_font_stack(size, language)
        try:
            lines = _headline_lines(clean, probe, fonts)
        except ValueError:
            continue
        return fonts[0], clean, lines

    raise ValueError("Headline is too long to fit on screen.")
@lru_cache(maxsize=1)
def _load_logo():
    path = Path(__file__).resolve().parent / "logo.png"
    if not path.exists():
        return None

    with Image.open(path) as source:
        logo = source.convert("RGBA")
    logo.thumbnail((150, 150), Image.Resampling.LANCZOS)
    return logo


def _paste_logo(base: Image.Image) -> None:
    logo = _load_logo()
    if logo is None:
        return

    base.paste(
        logo,
        (WIDTH - logo.width - 42, 36),
        logo,
    )


def _paste_source(base: Image.Image, source_label: str | None = None) -> None:
    draw = ImageDraw.Draw(base)
    font = _font((), 24)
    label = str(source_label or SOURCE_LABEL).strip() or SOURCE_LABEL
    width, _ = _measure(draw, label, font)
    draw.text(
        (WIDTH - width - 42, HEIGHT - 86),
        label,
        font=font,
        fill=(210, 216, 224),
    )




@lru_cache(maxsize=64)
def _top5_body_font(size: int, language: str = "english"):
    root = Path(__file__).resolve().parent / "fonts"
    language = str(language or "english").casefold()

    if language == "hindi":
        candidates = (
            root / "NotoSansDevanagari-Regular.ttf",
            root / "NotoSansDevanagariUI-Regular.ttf",
        )
    elif language == "telugu":
        candidates = (root / "NotoSansTelugu-Regular.ttf",)
    else:
        candidates = (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )

    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue

    return ImageFont.load_default()

def _top5_full_frame_image(value: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(value, Image.Image):
        image = value.convert("RGB")
    elif isinstance(value, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(value))) as source:
                image = source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("A Top-5 visual could not be decoded.") from exc
    else:
        raise ValueError("A Top-5 visual is missing.")

    if image.size == (WIDTH, HEIGHT):
        return image

    source_width, source_height = image.size
    if source_height <= 0 or source_width <= 0:
        raise ValueError("A Top-5 visual has invalid dimensions.")

    source_ratio = source_width / source_height
    target_ratio = WIDTH / HEIGHT
    if abs(source_ratio - target_ratio) <= 0.01:
        return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    return _fit_visual_to_frame(image)


def _top5_editorial_font(size: int, language: str):
    root = Path(__file__).resolve().parent / "fonts"
    language = str(language or "english").casefold()

    if language == "hindi":
        candidates = (
            root / "NotoSansDevanagari-ExtraBold.ttf",
            root / "NotoSansDevanagari-CondensedBlack.ttf",
            root / "NotoSansDevanagari-Black.ttf",
        )
    elif language == "telugu":
        candidates = (
            root / "NotoSansTelugu-ExtraBold.ttf",
            root / "NotoSansTelugu-CondensedBlack.ttf",
            root / "NotoSansTelugu-Black.ttf",
        )
    else:
        candidates = (root / "Oswald-Bold.ttf",)

    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue

    return ImageFont.load_default()

def _top5_wrap_editorial_words(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []

    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        box = draw.textbbox(
            (0, 0),
            candidate,
            font=font,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = word
            continue
        if box[2] - box[0] > max_width:
            raise ValueError("Top-5 text contains a word that is too wide to fit.")
        current = candidate

    if current:
        lines.append(current)
    return lines


def _top5_editorial_layout(
    headline: str,
    body: str,
    language: str,
    story_number: int,
    max_headline_lines: int = 2,
) -> dict:
    clean_headline = " ".join(str(headline or "").split())
    clean_body = " ".join(str(body or "").split())
    if not clean_headline:
        raise ValueError("Top-5 card requires a headline.")

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    headline_font = None
    headline_lines = []

    for size in range(
        TOP5_EDITORIAL_HEADLINE_MAX_SIZE,
        TOP5_EDITORIAL_HEADLINE_MIN_SIZE - 1,
        -1,
    ):
        candidate = _top5_editorial_font(size, language)
        lines = _top5_wrap_editorial_words(
            probe,
            clean_headline.upper(),
            candidate,
            TOP5_EDITORIAL_MAX_WIDTH,
        )
        if len(lines) <= max_headline_lines:
            headline_font = candidate
            headline_lines = lines
            break

    if headline_font is None:
        raise ValueError("Top-5 headline cannot fit inside the available frame.")

    headline_box = probe.textbbox(
        (0, 0),
        "Ag",
        font=headline_font,
        stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
    )
    headline_line_height = headline_box[3] - headline_box[1]
    headline_height = (
        headline_line_height * len(headline_lines)
        + TOP5_EDITORIAL_HEADLINE_LINE_GAP * max(0, len(headline_lines) - 1)
    )

    body_font = _top5_body_font(TOP5_EDITORIAL_BODY_SIZE, language)
    body_lines = (
        _top5_wrap_editorial_words(
            probe,
            clean_body,
            body_font,
            TOP5_EDITORIAL_MAX_WIDTH,
        )
        if clean_body
        else []
    )

    if body_lines:
        body_box = probe.textbbox(
            (0, 0),
            "Ag",
            font=body_font,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        body_height = (
            (body_box[3] - body_box[1]) * len(body_lines)
            + TOP5_EDITORIAL_BODY_LINE_GAP * max(0, len(body_lines) - 1)
        )
    else:
        body_height = 0

    total_height = headline_height + (
        TOP5_EDITORIAL_HEADLINE_BODY_GAP + body_height
        if body_lines
        else 0
    )
    preferred_top = (
        TOP5_EDITORIAL_OPENER_Y
        if story_number == 0
        else TOP5_EDITORIAL_STORY_Y
    )

    return {
        "x": TOP5_EDITORIAL_MARGIN_X,
        "y": HEIGHT - TOP5_EDITORIAL_SAFE_BOTTOM - total_height,
        "width": TOP5_EDITORIAL_MAX_WIDTH,
        "headline_font": headline_font,
        "headline_lines": headline_lines,
        "body_font": body_font,
        "body_lines": body_lines,
        "headline_height": headline_height,
        "body_height": body_height,
        "body_gap": TOP5_EDITORIAL_HEADLINE_BODY_GAP if body_lines else 0,
    }
def _draw_top5_editorial_card(base: Image.Image, card: dict) -> Image.Image:
    language = str(card.get("language") or "english")
    source = _top5_full_frame_image(base)
    layout = _top5_editorial_layout(
        card.get("headline"),
        card.get("body"),
        language,
        int(card.get("story_number") or 0),
        int(card.get("max_headline_lines") or 2),
    )

    canvas = source.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    x = layout["x"]
    cursor_y = layout["y"]
    commands = []

    for line in layout["headline_lines"]:
        commands.append((line, layout["headline_font"], x, cursor_y))
        box = draw.textbbox(
            (0, 0),
            line,
            font=layout["headline_font"],
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        cursor_y += box[3] - box[1] + TOP5_EDITORIAL_HEADLINE_LINE_GAP

    if layout["body_lines"] and layout["body_font"] is not None:
        cursor_y += layout["body_gap"]
        for line in layout["body_lines"]:
            commands.append((line, layout["body_font"], x, cursor_y))
            box = draw.textbbox(
                (0, 0),
                line,
                font=layout["body_font"],
                stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            )
            cursor_y += box[3] - box[1] + TOP5_EDITORIAL_BODY_LINE_GAP

    text_bottom = min(
        HEIGHT,
        layout["y"]
        + layout["headline_height"]
        + layout["body_gap"]
        + layout["body_height"],
    )
    sample = canvas.crop(
        (
            x,
            layout["y"],
            min(WIDTH, x + layout["width"]),
            max(layout["y"] + 1, text_bottom),
        )
    ).convert("L")
    luminance = sample.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    text_fill = (8, 10, 14, 255) if luminance >= 150 else WHITE
    stroke_fill = (249, 250, 252, 210) if luminance >= 150 else (5, 7, 10, 220)

    shadow_mask = Image.new("L", canvas.size, 0)
    shadow_draw = ImageDraw.Draw(shadow_mask)
    for text, font, x_pos, y_pos in commands:
        box = shadow_draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        shadow_draw.text(
            (x_pos - box[0], y_pos - box[1]),
            text,
            font=font,
            fill=255,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=255,
        )

    shadow_alpha = shadow_mask.filter(
        ImageFilter.GaussianBlur(TOP5_EDITORIAL_TEXT_FADE_BLUR)
    ).point(
        lambda value: value * TOP5_EDITORIAL_TEXT_FADE_ALPHA // 255
    )
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_layer.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow_layer)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for text, font, x_pos, y_pos in commands:
        box = draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        draw.text(
            (x_pos - box[0], y_pos - box[1]),
            text,
            font=font,
            fill=text_fill,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=stroke_fill,
        )

    return canvas
def _draw_quote_card(base: Image.Image, card: dict) -> Image.Image:
    quote = " ".join(str(card.get("quote") or "").split())
    attribution = " ".join(str(card.get("attribution") or "").split())
    if not quote:
        raise ValueError("Quote Card requires quote text.")
    if not attribution:
        raise ValueError("Quote Card requires an attribution.")

    return _draw_top5_editorial_card(
        base,
        {
            "headline": quote,
            "body": f"— {attribution}",
            "language": str(card.get("language") or "english"),
            "max_headline_lines": 4,
        },
    )

def build_quote_card_preview(
    source_image: bytes | bytearray | Image.Image,
    quote: str,
    attribution: str,
    source_label: str | None = None,
) -> bytes:
    """Render a static Quote Card using the direct editorial card renderer."""
    frame = _draw_quote_card(
        _top5_full_frame_image(source_image),
        {
            "quote": quote,
            "attribution": attribution,
        },
    )
    _paste_logo(frame)
    _paste_top5_source(frame, source_label)
    buffer = BytesIO()
    frame.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _paste_top5_source(base: Image.Image, source_label: str | None) -> None:
    label = str(source_label or "Commons").strip() or "Commons"
    draw = ImageDraw.Draw(base)
    font = _font((), 20)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            WIDTH - TOP5_EDITORIAL_MARGIN_X - (box[2] - box[0]),
            HEIGHT - 48,
        ),
        label,
        font=font,
        fill=(86, 91, 100),
    )


def build_top5_card_preview(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    body: str = "",
    story_number: int = 0,
    total_stories: int = 5,
    source_label: str | None = None,
) -> bytes:
    "Render one static Top-5 slide with full-bleed photography and lower editorial typography."
    frame = _draw_top5_editorial_card(source_image, {
        "headline": headline,
        "body": body,
        "story_number": story_number,
        "total_stories": total_stories,
    })
    _paste_logo(frame)
    _paste_top5_source(frame, source_label)
    buffer = BytesIO()
    frame.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_headline(base: Image.Image, text: str, t: float, language: str) -> None:
    primary_font, clean, lines = _fit_headline_font(text, language)
    fonts = _headline_font_stack(primary_font.size, language)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    line_boxes = [
        (
            0,
            0,
            *_measure_headline_text(
                draw,
                " ".join(line),
                fonts,
            ),
        )
        for line in lines
    ]
    line_widths = [box[2] for box in line_boxes]
    line_heights = [box[3] for box in line_boxes]

    text_block_width = max(line_widths)
    text_block_height = (
        sum(line_heights) + HEADLINE_LINE_GAP * max(0, len(lines) - 1)
    )
    group_width = HEADLINE_MARKER_WIDTH + HEADLINE_MARKER_GAP + text_block_width

    progress = min(1.0, max(0.0, t / 0.45))
    eased = 1 - (1 - progress) ** 3
    start_group_x = -group_width - 80
    final_group_x = (WIDTH - group_width) // 2
    group_x = int(
        start_group_x + (final_group_x - start_group_x) * eased
    )

    marker_x = group_x
    text_x = group_x + HEADLINE_MARKER_WIDTH + HEADLINE_MARKER_GAP
    y = 560

    first_height = line_heights[0]
    line_y = y + max(8, (first_height - HEADLINE_MARKER_HEIGHT) // 2)
    split = int(HEADLINE_MARKER_WIDTH * 0.58)
    draw.rectangle(
        (
            marker_x,
            line_y,
            marker_x + split,
            line_y + HEADLINE_MARKER_HEIGHT,
        ),
        fill=BRAND_BLUE,
    )
    draw.rectangle(
        (
            marker_x + split,
            line_y,
            marker_x + HEADLINE_MARKER_WIDTH,
            line_y + HEADLINE_MARKER_HEIGHT,
        ),
        fill=ACCENT,
    )

    cursor_y = y
    for row, line in enumerate(lines):
        line_text = " ".join(line)
        line_width = line_widths[row]
        line_x = text_x + (text_block_width - line_width) // 2
        runs = _headline_runs(line_text, fonts)
        cursor_x = line_x
        for run, font in runs:
            box = draw.textbbox(
                (0, 0),
                run,
                font=font,
                stroke_width=HEADLINE_STROKE_WIDTH,
            )
            run_height = box[3] - box[1]
            run_y = cursor_y + (line_heights[row] - run_height) // 2
            draw.text(
                (cursor_x - box[0], run_y - box[1]),
                run,
                font=font,
                fill=WHITE,
                stroke_width=HEADLINE_STROKE_WIDTH,
                stroke_fill=DARK,
            )
            cursor_x += box[2] - box[0]
        cursor_y += line_heights[row] + HEADLINE_LINE_GAP

    if t < 0.68 and progress < 1.0:
        layer = layer.filter(
            ImageFilter.GaussianBlur(radius=max(0.0, 2.5 * (1 - progress)))
        )

    base.paste(layer, (0, 0), layer)
def _cue_at_time(subtitle_data: dict, t: float):
    for cue in subtitle_data.get("cues") or []:
        try:
            if float(cue["start"]) <= t < float(cue["end"]):
                return cue
        except (KeyError, TypeError, ValueError):
            continue
    return None


def validate_subtitle_handoff(subtitle_data: dict) -> bool:
    if not isinstance(subtitle_data, dict):
        return False
    if subtitle_data.get("schema") != "final-shorts.subtitles.v1":
        return False
    if not str(subtitle_data.get("language") or "").strip():
        return False

    previous_end = -1.0
    for cue in subtitle_data.get("cues") or []:
        try:
            start = float(cue["start"])
            end = float(cue["end"])
        except (KeyError, TypeError, ValueError):
            return False

        if start < 0 or end <= start or start < previous_end:
            return False

        words = cue.get("words")
        if not isinstance(words, list) or not words:
            return False

        word_end = start
        for word in words:
            try:
                word_start = float(word["start"])
                current_end = float(word["end"])
            except (KeyError, TypeError, ValueError):
                return False

            if (
                not str(word.get("text") or "").strip()
                or word_start < start
                or current_end <= word_start
                or current_end > end
                or word_start < word_end
            ):
                return False
            word_end = current_end

        previous_end = end

    return bool(subtitle_data.get("cues"))


def _subtitle_lines(
    words: list[dict],
    draw: ImageDraw.ImageDraw,
    font,
) -> list[list[dict]]:
    if not words:
        return []

    measurements = [
        _measure(
            draw,
            str(word.get("text") or ""),
            font,
            SUBTITLE_STROKE_WIDTH,
        )[0]
        for word in words
    ]

    def line_width(start: int, end: int) -> int:
        return (
            sum(measurements[start:end])
            + SUBTITLE_WORD_SPACING * max(0, end - start - 1)
        )

    if line_width(0, len(words)) <= SUBTITLE_MAX_WIDTH:
        return [words]

    candidates = []
    for split in range(1, len(words)):
        top = line_width(0, split)
        bottom = line_width(split, len(words))
        if (
            top <= SUBTITLE_MAX_WIDTH
            and bottom <= SUBTITLE_MAX_WIDTH
        ):
            candidates.append((max(top, bottom), abs(top - bottom), split))

    if not candidates:
        raise ValueError("Subtitle cue is too wide to fit in two lines.")

    _, _, split = min(candidates)
    return [words[:split], words[split:]]


@lru_cache(maxsize=256)
def _fit_subtitle_layout_cached(
    word_texts: tuple[str, ...],
    language: str,
):
    words = [{"text": text} for text in word_texts]
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(SUBTITLE_MAX_SIZE, SUBTITLE_MIN_SIZE - 1, -1):
        font = _font(_font_candidates("subtitle", language), size)
        try:
            lines = _subtitle_lines(words, probe, font)
        except ValueError:
            continue
        return font, tuple(len(line) for line in lines)

    raise ValueError("Subtitle cue is too wide to fit in two lines.")

@lru_cache(maxsize=512)
def _subtitle_render_geometry_cached(
    word_texts: tuple[str, ...],
    language: str,
):
    words = [{"text": text} for text in word_texts]
    font, line_lengths = _fit_subtitle_layout_cached(word_texts, language)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    measurements = tuple(
        probe.textbbox(
            (0, 0),
            str(word.get("text") or ""),
            font=font,
            stroke_width=SUBTITLE_STROKE_WIDTH,
        )
        for word in words
    )
    line_heights = []
    offset = 0
    for length in line_lengths:
        indices = range(offset, offset + length)
        line_heights.append(
            max(
                measurements[index][3] - measurements[index][1]
                for index in indices
            )
        )
        offset += length
    total_height = sum(line_heights) + SUBTITLE_LINE_GAP * max(
        0, len(line_heights) - 1
    )
    return font, line_lengths, measurements, tuple(line_heights), total_height


def _draw_subtitles(
    base: Image.Image,
    subtitle_data: dict,
    t: float,
    y_position: int | None = None,
) -> None:
    cue = _cue_at_time(subtitle_data, t)
    if cue is None:
        return

    words = cue["words"]
    language = subtitle_data.get("language") or "english"
    draw = ImageDraw.Draw(base)
    font, line_lengths, measurements, line_heights, total_height = _subtitle_render_geometry_cached(
        tuple(str(word.get("text") or "") for word in words),
        language,
    )
    lines = []
    offset = 0
    for length in line_lengths:
        lines.append(words[offset:offset + length])
        offset += length

    y = (int(y_position) if y_position is not None else SUBTITLE_Y) - total_height // 2

    word_index = 0
    for row, line in enumerate(lines):
        widths = [
            measurements[word_index + offset][2] - measurements[word_index + offset][0]
            for offset in range(len(line))
        ]
        line_width = sum(widths) + SUBTITLE_WORD_SPACING * max(0, len(line) - 1)
        cursor = (WIDTH - line_width) // 2

        for offset, word in enumerate(line):
            index = word_index + offset
            text = str(word["text"]).translate(DASH_TRANSLATION)
            box = measurements[index]
            width = box[2] - box[0]
            start = float(word["start"])
            end = float(word["end"])
            active = start <= t < end

            text_fill = ACCENT if active else WHITE

            draw.text(
                (cursor - box[0], y - box[1]),
                text,
                font=font,
                fill=text_fill,
                stroke_width=SUBTITLE_STROKE_WIDTH,
                stroke_fill=DARK,
            )
            cursor += width + SUBTITLE_WORD_SPACING

        y += line_heights[row] + SUBTITLE_LINE_GAP
        word_index += len(line)


def render_frame(
    base_image: Image.Image,
    t: float,
    subtitle_data: dict | None = None,
    headline_text: str = HEADLINE_TEXT,
    headline_enabled: bool = True,
    source_label: str | None = None,
    subtitle_y: int | None = None,
    top5_card: dict | None = None,
    validate_handoff: bool = True,
    quote_card: dict | None = None,
) -> Image.Image:
    if subtitle_data is None:
        subtitle_data = {"language": "english", "cues": []}
    elif validate_handoff and not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Invalid subtitle handoff.")

    if base_image.size == (WIDTH, HEIGHT) and base_image.mode == "RGBA":
        frame = base_image.copy()
    else:
        frame = base_image.convert("RGBA")
        if frame.size != (WIDTH, HEIGHT):
            frame = frame.resize(
                (WIDTH, HEIGHT),
                Image.Resampling.LANCZOS,
            )

    if top5_card is not None:
        _draw_top5_editorial_card(frame, top5_card)
    elif quote_card is not None:
        _draw_quote_card(frame, quote_card)
    else:
        if headline_enabled and t < HEADLINE_SECONDS:
            _draw_headline(
                frame,
                headline_text,
                t,
                str(subtitle_data.get("language") or "english"),
            )
        if subtitle_y is None:
            _draw_subtitles(frame, subtitle_data, t)
        else:
            _draw_subtitles(frame, subtitle_data, t, subtitle_y)

    _paste_logo(frame)
    if source_label is None:
        _paste_source(frame)
    else:
        _paste_source(frame, source_label)
    return frame.convert("RGB")


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def write_preview_video(frames, path: Path) -> Path:
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg is required to create renderer previews.")

    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{WIDTH}x{HEIGHT}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-profile:v",
            "high",
            "-level:v",
            "4.2",
            "-bf",
            "2",
            "-g",
            str(FPS * 2),
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-movflags",
            "+faststart",
            str(path),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None

    try:
        wrote_frame = False
        for frame in frames:
            wrote_frame = True
            process.stdin.write(frame.tobytes())
        if not wrote_frame:
            process.stdin.close()
            process.kill()
            raise ValueError("No preview frames were provided.")
        process.stdin.close()
    except BrokenPipeError as exc:
        process.kill()
        raise RuntimeError("ffmpeg stopped while creating the preview.") from exc

    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise RuntimeError(stderr.strip() or "ffmpeg failed to create the preview.")
    return path


def _fit_visual_to_frame(value: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(value, Image.Image):
        image = value.convert("RGB")
    elif isinstance(value, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(value))) as source:
                image = source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("A visual asset could not be decoded.") from exc
    else:
        raise ValueError("Each visual must contain image bytes.")

    target_ratio = WIDTH / HEIGHT
    current_ratio = image.width / image.height
    if current_ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif current_ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _mux_audio(
    silent_video: Path,
    audio_scenes: list[dict],
    output_path: Path,
) -> Path:
    inputs = ["-i", str(silent_video)]
    filter_inputs = []

    for index, scene in enumerate(audio_scenes, 1):
        audio_path = Path(str(scene.get("path") or ""))
        if not audio_path.is_file() or audio_path.stat().st_size <= 0:
            raise ValueError(
                f"Audio file for scene {scene.get('scene') or index} is missing."
            )
        inputs.extend(["-i", str(audio_path)])
        filter_inputs.append(f"[{index}:a]")

    filter_complex = (
        "".join(filter_inputs)
        + f"concat=n={len(audio_scenes)}:v=0:a=1[a]"
    )

    process = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-shortest",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            process.stderr.strip() or "ffmpeg failed to attach the audio."
        )
    return output_path


def render_production_video(
    approved_script: dict,
    approved_audio: dict,
    subtitle_data: dict | None,
    visuals: list[dict],
    output_path: str | Path,
    headline_text: str | None = None,
    headline_enabled: bool = True,
    source_label: str | None = None,
) -> Path:
    """Render an approved Cricket or Top-5 production handoff."""
    if (
        not isinstance(approved_script, dict)
        or approved_script.get("approved_for_audio") is not True
    ):
        raise ValueError("Renderer requires the approved Scriptwriter handoff.")

    if (
        not isinstance(approved_audio, dict)
        or approved_audio.get("approved_for_visuals") is not True
    ):
        raise ValueError("Renderer requires the approved Audio handoff.")

    is_top5 = approved_script.get("schema") == "final-shorts.top5-script.v1"
    if not is_top5 and not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Renderer requires a valid subtitle handoff.")

    script_scenes = (
        approved_script.get("slides")
        if is_top5
        else approved_script.get("script")
    )
    audio_scenes = approved_audio.get("scenes")
    if (
        not isinstance(script_scenes, list)
        or not isinstance(audio_scenes, list)
        or len(script_scenes) != len(audio_scenes)
        or len(visuals) != len(script_scenes)
        or not script_scenes
    ):
        raise ValueError("Script, audio and visual scene counts must match.")

    prepared_visuals = []
    for index, visual in enumerate(visuals, 1):
        if not isinstance(visual, dict):
            raise ValueError(f"Visual {index} is malformed.")
        result_key = str(visual.get("result_key") or "").strip().casefold()
        layout = visual.get("card_layout") if isinstance(visual.get("card_layout"), dict) else {}
        top5_card = visual.get("top5_card")
        if top5_card is not None and not isinstance(top5_card, dict):
            raise ValueError(f"Visual {index} has malformed Top-5 card data.")
        quote_card = visual.get("quote_card")
        if quote_card is not None:
            if not isinstance(quote_card, dict):
                raise ValueError(f"Visual {index} has malformed Quote Card data.")
            if not str(quote_card.get("quote") or "").strip() or not str(
                quote_card.get("attribution") or ""
            ).strip():
                raise ValueError(f"Visual {index} has incomplete Quote Card data.")
        image = _fit_visual_to_frame(visual.get("bytes")).convert("RGBA")
        static_frame = None
        if isinstance(top5_card, dict):
            static_frame = _draw_top5_editorial_card(image, top5_card)
            _paste_logo(static_frame)
            _paste_source(
                static_frame,
                str(visual.get("source") or source_label or "Commons").strip() or "Commons",
            )
            static_frame = static_frame.convert("RGB")
        elif isinstance(quote_card, dict):
            static_frame = _draw_quote_card(image, quote_card)
            _paste_logo(static_frame)
            quote_source_label = str(
                quote_card.get("source_label")
                or visual.get("source")
                or source_label
                or "Commons"
            ).strip() or "Commons"
            _paste_source(static_frame, quote_source_label)
            static_frame = static_frame.convert("RGB")

        prepared_visuals.append({
            "image": image,
            "static_frame": static_frame,
            "is_stats_card": result_key == "stats-card",
            "is_top5_card": isinstance(top5_card, dict),
            "top5_card": top5_card,
            "is_quote_card": isinstance(quote_card, dict),
            "quote_card": quote_card,
            "image_height": int(layout.get("image_height") or 0),
        })

    durations = []
    for index, scene in enumerate(audio_scenes, 1):
        try:
            duration = float(scene["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Audio scene {index} has no usable duration.") from exc
        if duration <= 0:
            raise ValueError(f"Audio scene {index} has an invalid duration.")
        durations.append(duration)

    total_duration = sum(durations)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    silent_video = output.with_name(f"{output.stem}.silent.mp4")

    def frames():
        frame_count = max(1, int(math.ceil(total_duration * FPS)))
        elapsed = 0.0
        scene_index = 0
        for frame_index in range(frame_count):
            t = frame_index / FPS
            while (
                scene_index < len(durations) - 1
                and t >= elapsed + durations[scene_index]
            ):
                elapsed += durations[scene_index]
                scene_index += 1
            visual = prepared_visuals[scene_index]
            subtitle_y = None
            if visual["is_stats_card"]:
                image_height = visual["image_height"] or 860
                subtitle_y = max(64, image_height - 96)
            if visual.get("static_frame") is not None:
                yield visual["static_frame"]
            else:
                yield render_frame(
                    visual["image"],
                    t,
                    subtitle_data,
                    headline_text or HEADLINE_TEXT,
                    headline_enabled,
                    source_label,
                    subtitle_y,
                    None,
                    False,
                )

    try:
        write_preview_video(frames(), silent_video)
        return _mux_audio(silent_video, audio_scenes, output)
    finally:
        try:
            silent_video.unlink()
        except FileNotFoundError:
            pass

