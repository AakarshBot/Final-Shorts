"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import shutil
import subprocess

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


TOP5_IMAGE_HEIGHT = 860
TOP5_PANEL_TOP = TOP5_IMAGE_HEIGHT
TOP5_PANEL_WHITE = (249, 250, 252)
TOP5_MARGIN_X = 64
TOP5_SAFE_RIGHT = 250
TOP5_SAFE_BOTTOM = 430
TOP5_HEADLINE_MAX_WIDTH = WIDTH - TOP5_MARGIN_X - TOP5_SAFE_RIGHT
TOP5_HEADLINE_MAX_SIZE = 84
TOP5_HEADLINE_MIN_SIZE = 42
TOP5_HEADLINE_MAX_LINES = 2
TOP5_HEADLINE_LINE_GAP = 6
TOP5_BODY_MAX_WIDTH = WIDTH - TOP5_MARGIN_X - TOP5_SAFE_RIGHT
TOP5_BODY_MAX_SIZE = 42
TOP5_BODY_MIN_SIZE = 25
TOP5_BODY_MAX_LINES = 8
TOP5_BODY_LINE_GAP = 12
TOP5_HEADLINE_BODY_GAP = 42
TOP5_PANEL_BOTTOM_GAP = 56
TOP5_IMAGE_FADE_HEIGHT = 230
TOP5_SOURCE_COLOR = (86, 91, 100)

PREVIEW_SUBTITLE_DATA = {
    "schema": "final-shorts.subtitles.v1",
    "language": "english",
    "cues": [
        {
            "start": 0.30,
            "end": 1.28,
            "words": [
                {"text": "India", "start": 0.30, "end": 0.52},
                {"text": "started", "start": 0.52, "end": 0.75},
                {"text": "strongly,", "start": 0.75, "end": 0.98},
                {"text": "but", "start": 0.98, "end": 1.28},
            ],
        },
        {
            "start": 1.28,
            "end": 2.27,
            "words": [
                {"text": "the", "start": 1.28, "end": 1.44},
                {"text": "momentum", "start": 1.44, "end": 1.70},
                {"text": "shifted", "start": 1.70, "end": 1.96},
                {"text": "when", "start": 1.96, "end": 2.27},
            ],
        },
        {
            "start": 2.27,
            "end": 2.85,
            "words": [
                {"text": "pressure", "start": 2.27, "end": 2.51},
                {"text": "finally", "start": 2.51, "end": 2.68},
                {"text": "arrived.", "start": 2.68, "end": 2.85},
            ],
        },
    ],
}

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


def _top5_body_font(size: int, language: str = "english"):
    root = Path(__file__).resolve().parent / "fonts"
    language = str(language or "english").casefold()
    candidates = []
    if language == "hindi":
        candidates.extend([
            root / "NotoSansDevanagariUI-Regular.ttf",
            root / "NotoSansDevanagari-Regular.ttf",
        ])
    elif language == "telugu":
        candidates.extend([
            root / "NotoSansTelugu-Regular.ttf",
        ])
    candidates.extend([
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ])
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _top5_headline_font(size: int):
    root = Path(__file__).resolve().parent / "fonts"
    for path in (
        root / "Oswald-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
    ):
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _top5_wrap_words(draw, text: str, font, max_width: int):
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []
    lines = []
    current = []
    current_width = 0
    for word in words:
        box = draw.textbbox((0, 0), word, font=font)
        width = box[2] - box[0]
        candidate = current_width + width + (10 if current else 0)
        if current and candidate > max_width:
            lines.append(current)
            current = [word]
            current_width = width
        else:
            current.append(word)
            current_width = candidate
    if current:
        lines.append(current)
    return lines


def _top5_sentences(text: str) -> list[str]:
    clean = " ".join(str(text or "").split())
    if not clean:
        return []

    sentences = []
    current = []
    for word in clean.split():
        current.append(word)
        if word.endswith((".", "?", "!")) and len(sentences) < 2:
            sentences.append(" ".join(current))
            current = []

    if current:
        if sentences:
            sentences[-1] = f"{sentences[-1]} {' '.join(current)}"
        else:
            sentences.append(" ".join(current))
    return sentences[:2]


def _fit_top5_headline(text: str):
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    clean = " ".join(str(text or "").split())
    if not clean:
        raise ValueError("Top-5 headline requires text.")

    for size in range(TOP5_HEADLINE_MAX_SIZE, TOP5_HEADLINE_MIN_SIZE - 1, -1):
        font = _top5_headline_font(size)
        lines = _top5_wrap_words(
            probe,
            clean,
            font,
            TOP5_HEADLINE_MAX_WIDTH,
        )
        if len(lines) <= TOP5_HEADLINE_MAX_LINES:
            return font, lines
    raise ValueError("Top-5 headline is too long to fit cleanly.")


def _fit_top5_body(
    text: str,
    language: str,
    max_height: int | None = None,
):
    clean = " ".join(str(text or "").split())
    if not clean:
        return None, []

    sentences = _top5_sentences(clean)
    if not sentences:
        return None, []

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    available_height = max_height or (
        HEIGHT - TOP5_SAFE_BOTTOM - TOP5_HEADLINE_BODY_GAP - 120
    )

    for size in range(TOP5_BODY_MAX_SIZE, TOP5_BODY_MIN_SIZE - 1, -1):
        font = _top5_body_font(size, language)
        paragraphs = [
            _top5_wrap_words(probe, sentence, font, TOP5_BODY_MAX_WIDTH)
            for sentence in sentences
        ]
        total_lines = sum(len(lines) for lines in paragraphs)
        if total_lines > TOP5_BODY_MAX_LINES:
            continue
        line_box = probe.textbbox((0, 0), "Ag", font=font)
        line_height = line_box[3] - line_box[1]
        total_height = (
            line_height * total_lines
            + TOP5_BODY_LINE_GAP * max(0, total_lines - len(paragraphs))
            + 24 * max(0, len(paragraphs) - 1)
        )
        if total_height <= available_height:
            return font, paragraphs

    raise ValueError("Top-5 body copy is too long to fit cleanly.")


def _top5_text_metrics(
    headline_font,
    headline_lines: list[list[str]],
    body_font,
    body_paragraphs: list[list[list[str]]],
) -> tuple[int, int]:
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    headline_box = probe.textbbox((0, 0), "Ag", font=headline_font)
    headline_line_height = headline_box[3] - headline_box[1]
    headline_height = (
        headline_line_height * len(headline_lines)
        + TOP5_HEADLINE_LINE_GAP * max(0, len(headline_lines) - 1)
    )

    body_lines = [line for paragraph in body_paragraphs for line in paragraph]
    if not body_lines or body_font is None:
        return headline_height, 0

    body_box = probe.textbbox((0, 0), "Ag", font=body_font)
    body_line_height = body_box[3] - body_box[1]
    body_height = (
        body_line_height * len(body_lines)
        + TOP5_BODY_LINE_GAP * max(0, len(body_lines) - 1)
        + 24 * max(0, len(body_paragraphs) - 1)
    )
    return headline_height, body_height


def _top5_panel_geometry(
    headline_height: int,
    body_height: int,
    has_body: bool,
) -> tuple[int, int, int]:
    content_height = headline_height + (
        TOP5_HEADLINE_BODY_GAP + body_height if has_body else 0
    )
    panel_top = max(
        720,
        HEIGHT - TOP5_SAFE_BOTTOM - TOP5_PANEL_BOTTOM_GAP - content_height - 120,
    )
    panel_bottom = min(
        HEIGHT - TOP5_SAFE_BOTTOM,
        panel_top + content_height + 120,
    )
    content_top = panel_top + 56
    return panel_top, panel_bottom, content_top


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
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _draw_top5_image_fade(
    base: Image.Image,
    fade_end: int,
    panel_bottom: int,
) -> Image.Image:
    canvas = _top5_full_frame_image(base).convert("RGBA")
    fade_top = max(0, fade_end - TOP5_IMAGE_FADE_HEIGHT)
    fade_height = max(1, fade_end - fade_top)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    for index in range(fade_height):
        progress = index / max(1, fade_height - 1)
        eased = progress * progress * (3 - 2 * progress)
        alpha = int(255 * eased)
        draw.line(
            (0, fade_top + index, WIDTH, fade_top + index),
            fill=(*TOP5_PANEL_WHITE, alpha),
        )

    draw.rectangle(
        (0, fade_end, WIDTH, panel_bottom),
        fill=(*TOP5_PANEL_WHITE, 255),
    )
    canvas.alpha_composite(overlay)
    return canvas


def _draw_top5_card(base: Image.Image, card: dict) -> Image.Image:
    headline = " ".join(str(card.get("headline") or "").split())
    body = " ".join(str(card.get("body") or "").split())
    if not headline:
        raise ValueError("Top-5 card requires a headline.")

    language = str(card.get("language") or "english")
    headline_font, headline_lines = _fit_top5_headline(headline)

    body_font = None
    body_paragraphs = []
    if body:
        body_font, body_paragraphs = _fit_top5_body(body, language)

    headline_height, body_height = _top5_text_metrics(
        headline_font,
        headline_lines,
        body_font,
        body_paragraphs,
    )
    panel_top, panel_bottom, content_top = _top5_panel_geometry(
        headline_height,
        body_height,
        bool(body_paragraphs),
    )

    canvas = _draw_top5_image_fade(
        base,
        content_top,
        panel_bottom,
    )
    draw = ImageDraw.Draw(canvas, "RGBA")

    headline_y = content_top
    for row, line_words in enumerate(headline_lines):
        line = " ".join(line_words)
        box = draw.textbbox((0, 0), line, font=headline_font)
        x = TOP5_MARGIN_X
        y = headline_y + row * (
            (box[3] - box[1]) + TOP5_HEADLINE_LINE_GAP
        )
        draw.text(
            (x - box[0], y - box[1]),
            line,
            font=headline_font,
            fill=(14, 16, 20, 255),
        )

    if body_paragraphs and body_font:
        body_y = headline_y + headline_height + TOP5_HEADLINE_BODY_GAP
        line_box = draw.textbbox((0, 0), "Ag", font=body_font)
        line_height = line_box[3] - line_box[1]

        for paragraph_index, paragraph in enumerate(body_paragraphs):
            for line_words in paragraph:
                line = " ".join(line_words)
                box = draw.textbbox((0, 0), line, font=body_font)
                draw.text(
                    (
                        TOP5_MARGIN_X + 8 - box[0],
                        body_y - box[1],
                    ),
                    line,
                    font=body_font,
                    fill=(86, 91, 100, 255),
                )
                body_y += line_height + TOP5_BODY_LINE_GAP
            if paragraph_index < len(body_paragraphs) - 1:
                body_y += 24

    return canvas


def _paste_top5_source(base: Image.Image, source_label: str | None) -> None:
    label = str(source_label or "Commons").strip() or "Commons"
    draw = ImageDraw.Draw(base)
    font = _font((), 20)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            WIDTH - TOP5_MARGIN_X - (box[2] - box[0]),
            HEIGHT - 48,
        ),
        label,
        font=font,
        fill=TOP5_SOURCE_COLOR,
    )


def build_top5_card_preview(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    body: str = "",
    story_number: int = 0,
    total_stories: int = 5,
    source_label: str | None = None,
) -> bytes:
    "Render one static Top-5 slide using the full manually-cropped 9:16 image and a content-sized light panel."
    frame = _draw_top5_card(_fit_visual_to_frame(source_image), {
        "headline": headline,
        "body": body if story_number else "",
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


def _fit_subtitle_layout(
    words: list[dict],
    language: str,
):
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(SUBTITLE_MAX_SIZE, SUBTITLE_MIN_SIZE - 1, -1):
        font = _font(_font_candidates("subtitle", language), size)
        try:
            lines = _subtitle_lines(words, probe, font)
        except ValueError:
            continue
        return font, lines

    raise ValueError("Subtitle cue is too wide to fit in two lines.")


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
    font, lines = _fit_subtitle_layout(words, language)

    measurements = {
        index: draw.textbbox(
            (0, 0),
            str(word["text"]),
            font=font,
            stroke_width=SUBTITLE_STROKE_WIDTH,
        )
        for index, word in enumerate(words)
    }

    line_heights = []
    line_start = 0
    for line in lines:
        line_end = line_start + len(line)
        line_heights.append(
            max(
                measurements[index][3] - measurements[index][1]
                for index in range(line_start, line_end)
            )
        )
        line_start = line_end
    total_height = sum(line_heights) + SUBTITLE_LINE_GAP * max(0, len(lines) - 1)
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
    subtitle_data: dict = PREVIEW_SUBTITLE_DATA,
    headline_text: str = HEADLINE_TEXT,
    headline_enabled: bool = True,
    source_label: str | None = None,
    subtitle_y: int | None = None,
    top5_card: dict | None = None,
) -> Image.Image:
    if not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Invalid subtitle handoff.")

    frame = base_image.convert("RGBA").resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS,
    )

    if top5_card is not None:
        _draw_top5_card(frame, top5_card)
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


def build_preview_bundle(
    output_dir: str | Path | None = None,
    headline_enabled: bool = True,
    headline_text: str = HEADLINE_TEXT,
) -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    output = Path(output_dir) if output_dir else root / "output" / "renderer_previews"
    output.mkdir(parents=True, exist_ok=True)

    base = make_sample_background()

    opening_count = max(1, int(HEADLINE_SECONDS * FPS))
    videos = {
        "opening": write_preview_video(
            (
                render_frame(
                    base,
                    index / FPS,
                    PREVIEW_SUBTITLE_DATA,
                    headline_text,
                    headline_enabled,
                )
                for index in range(opening_count)
            ),
            output / "opening_headline.mp4",
        )
    }

    frame_count = max(1, int(2.85 * FPS))
    videos["final"] = write_preview_video(
        (
            render_frame(
                base,
                index / FPS,
                PREVIEW_SUBTITLE_DATA,
                headline_text,
                headline_enabled,
            )
            for index in range(frame_count)
        ),
        output / "final_editorial_highlight.mp4",
    )

    return videos




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
    subtitle_data: dict,
    visuals: list[dict],
    output_path: str | Path,
    headline_text: str | None = None,
    headline_enabled: bool = True,
    source_label: str | None = None,
) -> Path:
    """Render the approved production handoff with supplied slide visuals and audio."""
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

    if not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Renderer requires a valid subtitle handoff.")

    script_scenes = approved_script.get("script")
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
        prepared_visuals.append({
            "image": _fit_visual_to_frame(visual.get("bytes")),
            "is_stats_card": result_key == "stats-card",
            "is_top5_card": isinstance(top5_card, dict),
            "top5_card": top5_card,
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
            if visual.get("is_top5_card"):
                yield render_frame(
                    visual["image"],
                    t,
                    subtitle_data,
                    headline_text or HEADLINE_TEXT,
                    headline_enabled,
                    source_label,
                    subtitle_y,
                    top5_card=visual["top5_card"],
                )
            else:
                yield render_frame(
                    visual["image"],
                    t,
                    subtitle_data,
                    headline_text or HEADLINE_TEXT,
                    headline_enabled,
                    source_label,
                    subtitle_y,
                )

    try:
        write_preview_video(frames(), silent_video)
        return _mux_audio(silent_video, audio_scenes, output)
    finally:
        try:
            silent_video.unlink()
        except FileNotFoundError:
            pass

