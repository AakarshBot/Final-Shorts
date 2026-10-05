"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import shutil
import subprocess
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


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


TOP5_EDITORIAL_MARGIN_X = 60
TOP5_EDITORIAL_SAFE_TOP = 150
TOP5_EDITORIAL_SAFE_BOTTOM = 1780
TOP5_EDITORIAL_HEADLINE_DEFAULT_SIZE = 118
TOP5_EDITORIAL_HEADLINE_MAX_SIZE = 200
TOP5_EDITORIAL_HEADLINE_MIN_SIZE = 76
TOP5_EDITORIAL_HEADLINE_MAX_LINES = 2
TOP5_EDITORIAL_HEADLINE_LINE_GAP = 8
TOP5_EDITORIAL_BODY_MAX_SIZE = 50
TOP5_EDITORIAL_BODY_MIN_SIZE = 36
TOP5_EDITORIAL_BODY_LINE_GAP = 12
TOP5_EDITORIAL_HEADLINE_BODY_GAP = 28
TOP5_EDITORIAL_STROKE_WIDTH = 2
TOP5_EDITORIAL_SHADOW_BLUR = 7
TOP5_EDITORIAL_SHADOW_ALPHA = 185
TOP5_EDITORIAL_SHADOW_OFFSET = (0, 5)
TOP5_SUBJECT_HEADLINE_MAX_SIZE = 280
TOP5_SUBJECT_HEADLINE_MIN_SIZE = 92
TOP5_SUBJECT_MIN_SPACE = 110
TOP5_SUBJECT_REMOVAL_MODEL = "ZhengPeng7/BiRefNet"


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
    else:
        candidates.append(root / "Barlow-Regular.ttf")
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


def _top5_editorial_measure(
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
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    return sum(widths), max(heights)


def _top5_wrap_editorial_words(
    draw: ImageDraw.ImageDraw,
    text: str,
    fonts: tuple[object, ...],
    max_width: int,
) -> list[list[str]]:
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []
    lines = []
    current = []
    current_width = 0
    for word in words:
        width, _ = _top5_editorial_measure(draw, word, fonts)
        if width > max_width:
            raise ValueError("Top-5 text contains a word that is too wide to fit.")
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


@lru_cache(maxsize=256)
def _top5_headline_font_stack(size: int, language: str) -> tuple[object, ...]:
    language = str(language or "english").casefold()
    root = Path(__file__).resolve().parent / "fonts"
    candidates = []
    if language == "hindi":
        candidates.extend([
            root / "NotoSansDevanagari-CondensedBlack.ttf",
            root / "NotoSansDevanagari-Black.ttf",
        ])
    elif language == "telugu":
        candidates.extend([
            root / "NotoSansTelugu-CondensedBlack.ttf",
            root / "NotoSansTelugu-Black.ttf",
        ])
    else:
        candidates.append(root / "Oswald-Bold.ttf")
    candidates.extend([
        root / "BarlowCondensed-Black.ttf",
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
        Path("/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ])
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


def _top5_headline_layout(
    headline: str,
    language: str,
    probe: ImageDraw.ImageDraw,
    max_width: int,
    headline_size: int,
    max_lines: int = TOP5_EDITORIAL_HEADLINE_MAX_LINES,
) -> dict:
    clean_headline = " ".join(str(headline or "").split())
    if not clean_headline:
        raise ValueError("Top-5 card requires a headline.")
    if headline_size < TOP5_EDITORIAL_HEADLINE_MIN_SIZE:
        raise ValueError("Top-5 headline is below the readable size floor.")

    headline_fonts = _top5_headline_font_stack(headline_size, language)
    headline_lines = _top5_wrap_editorial_words(
        probe,
        clean_headline.upper(),
        headline_fonts,
        max_width,
    )
    if not headline_lines or len(headline_lines) > max_lines:
        raise ValueError("Top-5 headline cannot fit inside the editorial text area.")

    headline_height = sum(
        _top5_editorial_measure(probe, " ".join(line), headline_fonts)[1]
        for line in headline_lines
    ) + TOP5_EDITORIAL_HEADLINE_LINE_GAP * max(0, len(headline_lines) - 1)
    return {
        "headline_fonts": headline_fonts,
        "headline_lines": headline_lines,
        "headline_height": headline_height,
        "headline_size": headline_size,
    }


def _top5_body_fits(
    body: str,
    headline_height: int,
    body_size: int,
    language: str,
    probe: ImageDraw.ImageDraw,
    max_width: int,
) -> tuple[list[list[str]], int]:
    clean_body = " ".join(str(body or "").split())
    if not clean_body:
        return [], 0
    available_height = (
        TOP5_EDITORIAL_SAFE_BOTTOM
        - TOP5_EDITORIAL_SAFE_TOP
        - headline_height
        - TOP5_EDITORIAL_HEADLINE_BODY_GAP
    )
    if available_height <= 0:
        return [], 0
    body_font = _top5_body_font(body_size, language)
    body_lines = _top5_wrap_editorial_words(probe, clean_body, (body_font,), max_width)
    body_box = probe.textbbox(
        (0, 0),
        "Ag",
        font=body_font,
        stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
    )
    line_height = body_box[3] - body_box[1]
    body_height = line_height * len(body_lines) + TOP5_EDITORIAL_BODY_LINE_GAP * max(0, len(body_lines) - 1)
    return body_lines, body_height


def _top5_body_word_cap(
    body: str,
    headline_height: int,
    language: str,
    probe: ImageDraw.ImageDraw,
    max_width: int,
) -> int:
    words = " ".join(str(body or "").split()).split()
    if not words:
        return 0
    available_height = (
        TOP5_EDITORIAL_SAFE_BOTTOM
        - TOP5_EDITORIAL_SAFE_TOP
        - headline_height
        - TOP5_EDITORIAL_HEADLINE_BODY_GAP
    )
    low = 0
    high = len(words)
    while low < high:
        count = (low + high + 1) // 2
        try:
            _, body_height = _top5_body_fits(
                " ".join(words[:count]),
                headline_height,
                TOP5_EDITORIAL_BODY_MIN_SIZE,
                language,
                probe,
                max_width,
            )
        except ValueError:
            body_height = available_height + 1
        if body_height <= available_height:
            low = count
        else:
            high = count - 1
    return low


def _top5_subject_geometry(subject_mask: Image.Image) -> dict | None:
    mask = subject_mask.convert("L")
    frame_area = WIDTH * HEIGHT
    best = None

    for threshold in (96, 128, 160, 192):
        binary = mask.point(
            lambda value, t=threshold: 255 if value >= t else 0
        )
        bbox = binary.getbbox()
        if not bbox:
            continue

        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        coverage = sum(
            value > 128
            for value in binary.resize(
                (90, 160),
                Image.Resampling.BOX,
            ).getdata()
        ) / 14400.0
        bbox_area = width * height

        if width < 100 or height < 140:
            continue
        if coverage < 0.002 or coverage > 0.90:
            continue
        if bbox_area > frame_area * 0.96:
            continue

        compactness = 1.0 - min(1.0, bbox_area / frame_area)
        quality = (
            min(coverage, 0.55) * 2.0
            + min(width / WIDTH, 0.80) * 0.5
            + min(height / HEIGHT, 0.90) * 0.7
            + compactness * 0.8
            + (threshold / 192.0) * 0.2
        )
        candidate = {
            "bbox": bbox,
            "mask": binary,
            "coverage": coverage,
            "width": width,
            "height": height,
            "center_x": (x1 + x2) / 2.0,
            "center_y": (y1 + y2) / 2.0,
            "left_space": x1,
            "right_space": WIDTH - x2,
            "top_space": y1,
            "bottom_space": HEIGHT - y2,
            "quality": quality,
        }
        if best is None or candidate["quality"] > best["quality"]:
            best = candidate

    return best

def _top5_subject_overlap_ratio(
    subject_mask: Image.Image,
    box: tuple[int, int, int, int],
) -> float:
    x1, y1, x2, y2 = box
    left = max(0, x1)
    top = max(0, y1)
    right = min(WIDTH, x2)
    bottom = min(HEIGHT, y2)
    if right <= left or bottom <= top:
        return 0.0
    region = subject_mask.crop((left, top, right, bottom)).resize(
        (64, 32),
        Image.Resampling.BOX,
    )
    return sum(value > 128 for value in region.getdata()) / 2048.0


def _top5_balanced_headline_lines(
    draw: ImageDraw.ImageDraw,
    headline: str,
    fonts: tuple[object, ...],
    max_width: int,
    max_lines: int,
    target_fill: float,
    preferred_lines: int,
) -> list[list[str]]:
    words = " ".join(str(headline or "").split()).upper().split()
    if not words or max_width < 160:
        return []

    widths = [
        _top5_editorial_measure(draw, word, fonts)[0]
        for word in words
    ]
    space = 10
    best = None

    def score_lines(lines):
        fills = []
        for line in lines:
            width = sum(
                _top5_editorial_measure(draw, word, fonts)[0]
                for word in line
            ) + space * max(0, len(line) - 1)
            fills.append(width / max(1, max_width))
        singleton_count = sum(len(line) == 1 for line in lines)
        balance = max(len(line) for line in lines) - min(len(line) for line in lines)
        return (
            -sum((fill - target_fill) ** 2 for fill in fills) * 1400.0
            - abs(len(lines) - preferred_lines) * 95.0
            - singleton_count * 130.0
            - max(0, balance - 2) * 18.0
        )

    def solve(start, count):
        if count == 1:
            line = words[start:]
            width = sum(widths[start:]) + space * max(0, len(line) - 1)
            return [line] if width <= max_width else None

        result = None
        current_width = 0
        for end in range(start, len(words)):
            current_width += widths[end]
            if end > start:
                current_width += space
            if current_width > max_width:
                break
            remaining = len(words) - end - 1
            if remaining < count - 1:
                continue
            tail = solve(end + 1, count - 1)
            if tail is None:
                continue
            candidate = [words[start:end + 1], *tail]
            if result is None or score_lines(candidate) > score_lines(result):
                result = candidate
        return result

    for count in range(1, min(max_lines, len(words)) + 1):
        lines = solve(0, count)
        if lines is None:
            continue
        score = score_lines(lines)
        if best is None or score > best[0]:
            best = (score, lines)

    return best[1] if best else []


def _top5_subject_headline_fits(
    headline: str,
    language: str,
    probe: ImageDraw.ImageDraw,
    region_width: int,
    region_height: int,
    *,
    max_lines: int,
    target_fill_x: float,
    target_fill_y: float,
    preferred_lines: int,
) -> list[dict]:
    clean = " ".join(str(headline or "").split()).upper()
    if not clean or region_width < 180 or region_height < 180:
        return []

    candidates = []
    for size in range(360, 83, -4):
        fonts = _top5_headline_font_stack(size, language)
        lines = _top5_balanced_headline_lines(
            probe,
            clean,
            fonts,
            max(160, int(region_width * 0.96)),
            max_lines,
            target_fill_x,
            preferred_lines,
        )
        if not lines:
            continue

        widths = [
            _top5_editorial_measure(probe, " ".join(line), fonts)[0]
            for line in lines
        ]
        heights = [
            _top5_editorial_measure(probe, " ".join(line), fonts)[1]
            for line in lines
        ]
        text_width = max(widths)
        text_height = sum(heights) + TOP5_EDITORIAL_HEADLINE_LINE_GAP * (len(lines) - 1)
        if text_height > region_height * 0.94:
            continue

        fill_x = text_width / max(1, region_width)
        fill_y = text_height / max(1, region_height)
        singleton_count = sum(len(line) == 1 for line in lines)
        score = (
            size * 4.0
            + (1.0 - min(1.0, abs(fill_x - target_fill_x) / 0.30)) * 250.0
            + (1.0 - min(1.0, abs(fill_y - target_fill_y) / 0.45)) * 170.0
            - singleton_count * 160.0
            - max(0, len(lines) - preferred_lines) * 30.0
        )
        candidates.append({
            "score": score,
            "headline_fonts": fonts,
            "headline_lines": lines,
            "headline_height": int(text_height),
            "headline_size": size,
            "width": int(text_width),
            "fill_x": fill_x,
            "fill_y": fill_y,
        })

    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _top5_editorial_layout(
    headline: str,
    body: str,
    language: str,
    story_number: int,
    max_headline_lines: int = TOP5_EDITORIAL_HEADLINE_MAX_LINES,
    image: bytes | bytearray | Image.Image | None = None,
    subject_mask: Image.Image | None = None,
) -> dict:
    clean_headline = " ".join(str(headline or "").split()).upper()
    clean_body = " ".join(str(body or "").split())
    if not clean_headline:
        raise ValueError("Top-5 card requires a headline.")
    if subject_mask is not None and clean_body:
        raise ValueError("Top-5 Subject Cutout accepts a headline only.")

    frame = _top5_full_frame_image(image) if image is not None else Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (24, 28, 34),
    )
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    safe_left = TOP5_EDITORIAL_MARGIN_X
    safe_right = WIDTH - TOP5_EDITORIAL_MARGIN_X
    safe_top = TOP5_EDITORIAL_SAFE_TOP
    safe_bottom = TOP5_EDITORIAL_SAFE_BOTTOM

    if subject_mask is not None:
        mask = subject_mask.convert("L")
        subject_binary = mask.point(lambda value: 255 if value >= 64 else 0)
        bbox = subject_binary.getbbox()
        if bbox is None:
            raise ValueError("Top-5 Subject Cutout returned an empty foreground mask.")

        x1, y1, x2, y2 = bbox
        if x2 - x1 < 90 or y2 - y1 < 120:
            raise ValueError("Top-5 Subject Cutout returned too little foreground.")

        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        left_space = x1 - safe_left
        right_space = safe_right - x2
        top_space = y1 - safe_top
        bottom_space = safe_bottom - y2
        centered = (
            left_space >= TOP5_SUBJECT_MIN_SPACE
            and right_space >= TOP5_SUBJECT_MIN_SPACE
            and 0.30 <= center_x / WIDTH <= 0.70
        )

        if centered:
            mask_small = subject_binary.resize((90, 160), Image.Resampling.BOX)
            best = None

            for size in range(
                TOP5_SUBJECT_HEADLINE_MAX_SIZE,
                TOP5_SUBJECT_HEADLINE_MIN_SIZE - 1,
                -8,
            ):
                fonts = _top5_headline_font_stack(size, language)
                width, height = _top5_editorial_measure(
                    probe,
                    clean_headline,
                    fonts,
                )
                if width > safe_right - safe_left:
                    continue

                min_x = max(safe_left, x2 + 24 - width)
                max_x = min(safe_right - width, x1 - 24)
                if min_x > max_x:
                    continue

                x = int(round(max(min_x, min(max_x, (WIDTH - width) / 2.0))))
                for offset in (-160, -80, 0, 80, 160):
                    y = int(round(center_y - height / 2.0 + offset))
                    if y < safe_top or y + height > safe_bottom:
                        continue

                    headline_mask = Image.new("L", (WIDTH, HEIGHT), 0)
                    headline_draw = ImageDraw.Draw(headline_mask)
                    cursor_x = x
                    for run, font in _headline_runs(clean_headline, fonts):
                        box = headline_draw.textbbox(
                            (0, 0),
                            run,
                            font=font,
                            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                        )
                        headline_draw.text(
                            (cursor_x - box[0], y - box[1]),
                            run,
                            font=font,
                            fill=255,
                            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                            stroke_fill=255,
                        )
                        cursor_x += box[2] - box[0]

                    text_small = headline_mask.resize((90, 160), Image.Resampling.BOX)
                    intersection = ImageChops.multiply(text_small, mask_small)
                    visible = ImageChops.subtract(text_small, mask_small)
                    text_total = sum(text_small.getdata())
                    hidden_total = sum(intersection.getdata())
                    left_limit = max(1, min(90, int(x1 * 90 / WIDTH)))
                    right_start = min(89, max(0, int(x2 * 90 / WIDTH)))
                    left_total = sum(visible.crop((0, 0, left_limit, 160)).getdata())
                    right_total = sum(visible.crop((right_start, 0, 90, 160)).getdata())
                    if not text_total:
                        continue

                    overlap = hidden_total / text_total
                    left_ratio = left_total / text_total
                    right_ratio = right_total / text_total
                    if overlap < 0.08 or overlap > 0.62:
                        continue
                    if left_ratio < 0.035 or right_ratio < 0.035:
                        continue

                    gap_box = (
                        max(0, int(x1 * 90 / WIDTH)),
                        max(0, int(y1 * 160 / HEIGHT)),
                        min(90, int(x2 * 90 / WIDTH)),
                        min(160, int(y2 * 160 / HEIGHT)),
                    )
                    gap_text = ImageChops.subtract(
                        text_small.crop(gap_box),
                        mask_small.crop(gap_box),
                    )
                    gap_ratio = sum(gap_text.getdata()) / text_total

                    score = (
                        size * 10.0
                        + min(1.0, left_ratio / 0.13) * 180.0
                        + min(1.0, right_ratio / 0.13) * 180.0
                        - abs(overlap - 0.28) * 220.0
                        + min(1.0, gap_ratio / 0.04) * 70.0
                        - abs((y + height / 2.0) - center_y) * 0.06
                    )
                    candidate = {
                        "score": score,
                        "composition_mode": "cross-subject",
                        "x": x,
                        "y": y,
                        "width": width,
                        "headline_fonts": fonts,
                        "headline_lines": [clean_headline.split()],
                        "headline_height": height,
                        "headline_size": size,
                        "body_font": None,
                        "body_lines": [],
                        "body_height": 0,
                        "body_size": None,
                        "body_gap": 0,
                        "total_height": height,
                        "zone_bottom": safe_bottom,
                        "subject_overlap": overlap,
                        "subject_bbox": bbox,
                        "story_number": story_number,
                    }
                    if best is None or candidate["score"] > best["score"]:
                        best = candidate

            if best is None and len(clean_headline.split()) > 2:
                words = clean_headline.split()
                for size in range(
                    TOP5_SUBJECT_HEADLINE_MAX_SIZE,
                    TOP5_SUBJECT_HEADLINE_MIN_SIZE - 1,
                    -8,
                ):
                    fonts = _top5_headline_font_stack(size, language)
                    for split in range(1, len(words)):
                        line_a = " ".join(words[:split])
                        line_b = " ".join(words[split:])
                        width_a, height_a = _top5_editorial_measure(probe, line_a, fonts)
                        width_b, height_b = _top5_editorial_measure(probe, line_b, fonts)
                        width = max(width_a, width_b)
                        total_height = height_a + TOP5_EDITORIAL_HEADLINE_LINE_GAP + height_b
                        if width > safe_right - safe_left or total_height > safe_bottom - safe_top:
                            continue

                        min_x = max(safe_left, x2 + 24 - width)
                        max_x = min(safe_right - width, x1 - 24)
                        if min_x > max_x:
                            continue

                        x = int(round(max(min_x, min(max_x, (WIDTH - width) / 2.0))))
                        y = int(round(center_y - total_height / 2.0))
                        headline_mask = Image.new("L", (WIDTH, HEIGHT), 0)
                        headline_draw = ImageDraw.Draw(headline_mask)
                        cursor_y = y
                        for line in (line_a, line_b):
                            cursor_x = x
                            for run, font in _headline_runs(line, fonts):
                                box = headline_draw.textbbox(
                                    (0, 0),
                                    run,
                                    font=font,
                                    stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                                )
                                headline_draw.text(
                                    (cursor_x - box[0], cursor_y - box[1]),
                                    run,
                                    font=font,
                                    fill=255,
                                    stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                                    stroke_fill=255,
                                )
                                cursor_x += box[2] - box[0]
                            cursor_y += _top5_editorial_measure(probe, line, fonts)[1] + TOP5_EDITORIAL_HEADLINE_LINE_GAP

                        text_small = headline_mask.resize((90, 160), Image.Resampling.BOX)
                        intersection = ImageChops.multiply(text_small, mask_small)
                        visible = ImageChops.subtract(text_small, mask_small)
                        text_total = sum(text_small.getdata())
                        hidden_total = sum(intersection.getdata())
                        left_total = sum(visible.crop((0, 0, max(1, int(x1 * 90 / WIDTH)), 160)).getdata())
                        right_total = sum(visible.crop((min(89, int(x2 * 90 / WIDTH)), 0, 90, 160)).getdata())
                        if not text_total:
                            continue

                        overlap = hidden_total / text_total
                        if overlap < 0.05 or overlap > 0.62:
                            continue
                        if left_total / text_total < 0.025 or right_total / text_total < 0.025:
                            continue

                        candidate = {
                            "score": size * 9.0 + width * 0.35 - abs(overlap - 0.28) * 180.0,
                            "composition_mode": "cross-subject",
                            "x": x,
                            "y": y,
                            "width": width,
                            "headline_fonts": fonts,
                            "headline_lines": [words[:split], words[split:]],
                            "headline_height": total_height,
                            "headline_size": size,
                            "body_font": None,
                            "body_lines": [],
                            "body_height": 0,
                            "body_size": None,
                            "body_gap": 0,
                            "total_height": total_height,
                            "zone_bottom": safe_bottom,
                            "subject_overlap": overlap,
                            "subject_bbox": bbox,
                            "story_number": story_number,
                        }
                        if best is None or candidate["score"] > best["score"]:
                            best = candidate

            if best is not None:
                return best

        regions = []
        if center_x < WIDTH * 0.48 and right_space >= 170:
            regions.append((
                "vertical-right",
                (x2 + 34, safe_top, safe_right, safe_bottom),
            ))
        if center_x > WIDTH * 0.52 and left_space >= 170:
            regions.append((
                "vertical-left",
                (safe_left, safe_top, x1 - 34, safe_bottom),
            ))
        if top_space >= 260:
            regions.append((
                "top-negative-space",
                (safe_left, safe_top, safe_right, y1 - 34),
            ))
        if bottom_space >= 260:
            regions.append((
                "bottom-negative-space",
                (safe_left, y2 + 34, safe_right, safe_bottom),
            ))

        best = None
        words = clean_headline.split()
        for mode, region in regions:
            rx1, ry1, rx2, ry2 = region
            rw = rx2 - rx1
            rh = ry2 - ry1
            if rw < 220 or rh < 260:
                continue

            for size in range(
                TOP5_SUBJECT_HEADLINE_MAX_SIZE,
                TOP5_SUBJECT_HEADLINE_MIN_SIZE - 1,
                -8,
            ):
                fonts = _top5_headline_font_stack(size, language)
                lines = []
                current = []
                for word in words:
                    trial = current + [word]
                    trial_width = _top5_editorial_measure(
                        probe,
                        " ".join(trial),
                        fonts,
                    )[0]
                    if current and (len(current) >= 2 or trial_width > rw):
                        lines.append(current)
                        current = [word]
                    else:
                        current = trial
                if current:
                    lines.append(current)

                heights = [
                    _top5_editorial_measure(probe, " ".join(line), fonts)[1]
                    for line in lines
                ]
                total_height = sum(heights) + TOP5_EDITORIAL_HEADLINE_LINE_GAP * max(0, len(lines) - 1)
                if total_height > rh:
                    continue

                text_width = max(
                    _top5_editorial_measure(probe, " ".join(line), fonts)[0]
                    for line in lines
                )
                if text_width < rw * 0.55:
                    continue

                x = int(rx1 + (rw - text_width) / 2)
                y = int(ry1 + (rh - total_height) / 2)
                score = size * 10.0 + min(1.0, text_width / rw) * 260.0 - len(lines) * 18.0
                if mode.startswith("vertical"):
                    score += 90.0

                candidate = {
                    "score": score,
                    "composition_mode": mode,
                    "x": x,
                    "y": y,
                    "width": text_width,
                    "headline_fonts": fonts,
                    "headline_lines": lines,
                    "headline_height": total_height,
                    "headline_size": size,
                    "body_font": None,
                    "body_lines": [],
                    "body_height": 0,
                    "body_size": None,
                    "body_gap": 0,
                    "total_height": total_height,
                    "zone_bottom": safe_bottom,
                    "subject_overlap": 0.0,
                    "subject_bbox": bbox,
                    "story_number": story_number,
                }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate

        if best is None:
            raise ValueError("Top-5 Subject Cutout could not build a subject-aware headline layout.")
        return best

    analysis = frame.convert("L").resize((90, 160), Image.Resampling.BILINEAR)
    edge_map = analysis.filter(ImageFilter.FIND_EDGES)
    regions = [
        ("top", (safe_left, 150, safe_right, 760)),
        ("upper", (safe_left, 330, safe_right, 1030)),
        ("middle", (safe_left, 620, safe_right, 1330)),
        ("lower", (safe_left, 900, safe_right, 1610)),
        ("bottom", (safe_left, 1120, safe_right, safe_bottom)),
        ("top-left", (safe_left, 180, 620, 830)),
        ("top-right", (460, 180, safe_right, 830)),
        ("bottom-left", (safe_left, 1030, 620, safe_bottom)),
        ("bottom-right", (460, 1030, safe_right, safe_bottom)),
        ("center-left", (safe_left, 560, 720, 1420)),
        ("center-right", (360, 560, safe_right, 1420)),
    ]

    candidates = []
    for mode, region in regions:
        rx1, ry1, rx2, ry2 = region
        rw = rx2 - rx1
        rh = ry2 - ry1
        if rw < 300 or rh < 280:
            continue

        qbox = (
            max(0, int(rx1 * 90 / WIDTH)),
            max(0, int(ry1 * 160 / HEIGHT)),
            min(90, int(rx2 * 90 / WIDTH)),
            min(160, int(ry2 * 160 / HEIGHT)),
        )
        patch = edge_map.crop(qbox).resize((48, 48), Image.Resampling.BILINEAR)
        values = list(patch.getdata())
        if not values:
            continue
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        quiet = max(
            0.0,
            1.0
            - min(1.0, mean / 54.0) * 0.78
            - min(1.0, math.sqrt(variance) / 68.0) * 0.22,
        )

        for headline_size in range(
            TOP5_EDITORIAL_HEADLINE_MAX_SIZE,
            TOP5_EDITORIAL_HEADLINE_MIN_SIZE - 1,
            -4,
        ):
            fonts = _top5_headline_font_stack(headline_size, language)
            try:
                headline_layout = _top5_headline_layout(
                    clean_headline,
                    language,
                    probe,
                    rw,
                    headline_size,
                    max_headline_lines,
                )
            except ValueError:
                continue

            body_font = None
            body_lines = []
            body_height = 0
            if clean_body:
                for body_size in range(
                    TOP5_EDITORIAL_BODY_MAX_SIZE,
                    TOP5_EDITORIAL_BODY_MIN_SIZE - 1,
                    -2,
                ):
                    font = _top5_body_font(body_size, language)
                    lines = _top5_wrap_editorial_words(probe, clean_body, (font,), rw)
                    box = probe.textbbox(
                        (0, 0),
                        "Ag",
                        font=font,
                        stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                    )
                    line_height = box[3] - box[1]
                    body_height = (
                        line_height * len(lines)
                        + TOP5_EDITORIAL_BODY_LINE_GAP * max(0, len(lines) - 1)
                    )
                    if headline_layout["headline_height"] + TOP5_EDITORIAL_HEADLINE_BODY_GAP + body_height <= rh:
                        body_font = font
                        body_lines = lines
                        break
                if body_font is None:
                    continue

            total_height = headline_layout["headline_height"] + (
                TOP5_EDITORIAL_HEADLINE_BODY_GAP + body_height
                if body_lines
                else 0
            )
            if total_height > rh:
                continue

            text_width = max(
                _top5_editorial_measure(
                    probe,
                    " ".join(line),
                    headline_layout["headline_fonts"],
                )[0]
                for line in headline_layout["headline_lines"]
            )
            fill_x = text_width / rw
            fill_y = total_height / rh

            ui_penalty = 0.0
            if ry1 < 230 and rx2 > WIDTH - 220:
                ui_penalty += 260.0
            if ry2 > HEIGHT - 150 and rx2 > WIDTH - 300:
                ui_penalty += 220.0

            score = (
                quiet * 1150.0
                + headline_size * 14.0
                + min(1.0, fill_x / 0.90) * 250.0
                + min(1.0, fill_y / 0.62) * 120.0
                + (body_font.size * 4.0 if body_font is not None else 0.0)
                - ui_penalty
                - abs(fill_x - 0.88) * 80.0
            )

            candidates.append({
                "score": score,
                "composition_mode": "negative-space",
                "region_mode": mode,
                "x": int(rx1 + (rw - text_width) / 2),
                "y": int(ry1 + (rh - total_height) / 2),
                "width": text_width,
                "headline_fonts": headline_layout["headline_fonts"],
                "headline_lines": headline_layout["headline_lines"],
                "headline_height": headline_layout["headline_height"],
                "headline_size": headline_layout["headline_size"],
                "body_font": body_font,
                "body_lines": body_lines,
                "body_height": body_height,
                "body_size": body_font.size if body_font is not None else None,
                "body_gap": TOP5_EDITORIAL_HEADLINE_BODY_GAP if body_lines else 0,
                "total_height": total_height,
                "zone_bottom": safe_bottom,
                "subject_overlap": 0.0,
                "story_number": story_number,
                "quiet_score": quiet,
            })

    if not candidates:
        raise ValueError("Top-5 headline cannot fit inside a readable negative-space region.")

    return max(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["headline_size"],
            candidate["body_size"] or 0,
        ),
    )

def compress_top5_body(body: str, max_words: int) -> str:
    words = " ".join(str(body or "").split()).split()
    if max_words <= 0 or len(words) <= max_words:
        return " ".join(words)

    filler = {
        "actually", "also", "currently", "just", "now", "really",
        "still", "then", "very", "already", "simply",
    }
    reduced = [
        word for word in words
        if word.casefold().strip(".,!?;:") not in filler
    ]

    if len(reduced) <= max_words:
        return " ".join(reduced)

    sentences = []
    current = []
    for word in reduced:
        current.append(word)
        if word.endswith((".", "!", "?")):
            sentences.append(" ".join(current))
            current = []
    if current:
        sentences.append(" ".join(current))

    kept = []
    count = 0
    for sentence in sentences:
        sentence_words = sentence.split()
        if count + len(sentence_words) > max_words:
            break
        kept.extend(sentence_words)
        count += len(sentence_words)

    remaining = max_words - len(kept)
    if remaining > 0 and len(kept) < len(reduced):
        kept.extend(reduced[len(kept):len(kept) + remaining])

    if not kept:
        kept = reduced[:max_words]

    result = " ".join(kept).strip()
    if result and not result.endswith((".", "!", "?")):
        result += "…"
    return result


@lru_cache(maxsize=1)
def _load_top5_birefnet():
    try:
        import torch
        from transformers import AutoModelForImageSegmentation
    except ImportError as exc:
        raise RuntimeError(
            "Top-5 Subject Cutout needs torch and transformers. Run: "
            "python -m pip install -r requirements.txt"
        ) from exc

    model = AutoModelForImageSegmentation.from_pretrained(
        TOP5_SUBJECT_REMOVAL_MODEL,
        trust_remote_code=True,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    if device.type == "cuda":
        model.half()
    return model, device


@lru_cache(maxsize=64)
def _top5_subject_mask(image_bytes: bytes) -> Image.Image | None:
    if not image_bytes:
        return None
    try:
        import torch
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError(
            "Top-5 Subject Cutout needs torch and torchvision. Run: "
            "python -m pip install -r requirements.txt"
        ) from exc

    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGB")

    model, device = _load_top5_birefnet()
    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    tensor = transform(image).unsqueeze(0).to(device)
    if device.type == "cuda":
        tensor = tensor.half()

    with torch.inference_mode():
        prediction = model(tensor)[-1].sigmoid().cpu()

    mask = transforms.ToPILImage()(prediction[0].squeeze())
    mask = mask.resize(image.size, Image.Resampling.BILINEAR)
    mask = mask.filter(ImageFilter.MedianFilter(3))
    if mask.getbbox() is None:
        return None
    return mask

def _draw_top5_editorial_card(base: Image.Image, card: dict) -> Image.Image:
    language = str(card.get("language") or "english")
    headline = " ".join(str(card.get("headline") or "").split())
    body = " ".join(str(card.get("body") or "").split())
    subject_cutout = bool(card.get("subject_cutout"))

    if not headline:
        raise ValueError("Top-5 card requires a headline.")
    if subject_cutout and body:
        raise ValueError("Top-5 Subject Cutout accepts a headline only.")

    source_image = _top5_full_frame_image(base).convert("RGB")
    subject_mask = None
    if subject_cutout:
        source_bytes = BytesIO()
        source_image.save(source_bytes, format="PNG", optimize=False)
        subject_mask = _top5_subject_mask(source_bytes.getvalue())
        if subject_mask is None:
            raise ValueError(
                "Top-5 Subject Cutout could not produce a usable foreground mask."
            )

    layout = _top5_editorial_layout(
        headline,
        body,
        language,
        int(card.get("story_number") or 0),
        int(card.get("max_headline_lines") or TOP5_EDITORIAL_HEADLINE_MAX_LINES),
        image=source_image,
        subject_mask=subject_mask,
    )

    canvas = source_image.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    commands = []
    cursor_y = layout["y"]

    for line_words in layout["headline_lines"]:
        line = " ".join(line_words)
        cursor_x = layout["x"]
        for run, font in _headline_runs(line, layout["headline_fonts"]):
            box = draw.textbbox(
                (0, 0),
                run,
                font=font,
                stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            )
            commands.append(("headline", run, font, cursor_x, cursor_y))
            cursor_x += box[2] - box[0]
        cursor_y += (
            _top5_editorial_measure(
                draw,
                line,
                layout["headline_fonts"],
            )[1]
            + TOP5_EDITORIAL_HEADLINE_LINE_GAP
        )

    if layout["body_lines"] and layout["body_font"] is not None:
        cursor_y = (
            layout["y"]
            + layout["headline_height"]
            + TOP5_EDITORIAL_HEADLINE_BODY_GAP
        )
        for line_words in layout["body_lines"]:
            commands.append((
                "body",
                " ".join(line_words),
                layout["body_font"],
                layout["x"],
                cursor_y,
            ))
            cursor_y += (
                draw.textbbox(
                    (0, 0),
                    "Ag",
                    font=layout["body_font"],
                    stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                )[3]
                - draw.textbbox(
                    (0, 0),
                    "Ag",
                    font=layout["body_font"],
                    stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                )[1]
                + TOP5_EDITORIAL_BODY_LINE_GAP
            )

    text_mask = Image.new("L", canvas.size, 0)
    text_draw = ImageDraw.Draw(text_mask)
    for kind, text, font, x_pos, y_pos in commands:
        box = text_draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
        )
        text_draw.text(
            (x_pos - box[0], y_pos - box[1]),
            text,
            font=font,
            fill=255,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=255,
        )

    source_luma = source_image.convert("L")
    text_values = []
    for yy in range(0, HEIGHT, 6):
        for xx in range(0, WIDTH, 6):
            if text_mask.getpixel((xx, yy)) > 0:
                text_values.append(source_luma.getpixel((xx, yy)))
    mean_luma = (
        sum(text_values) / len(text_values)
        if text_values
        else 127.5
    )
    text_fill = (
        (249, 250, 252, 255)
        if mean_luma < 137
        else (5, 7, 10, 255)
    )
    stroke_fill = (
        (5, 7, 10, 235)
        if mean_luma < 137
        else (249, 250, 252, 235)
    )
    shadow_rgb = (
        (5, 7, 10)
        if mean_luma < 137
        else (249, 250, 252)
    )

    shadow_mask = text_mask.filter(
        ImageFilter.GaussianBlur(TOP5_EDITORIAL_SHADOW_BLUR)
    )
    shadow_mask = shadow_mask.point(
        lambda value: value * TOP5_EDITORIAL_SHADOW_ALPHA // 255
    )
    shadow_layer = Image.new("RGBA", canvas.size, shadow_rgb + (0,))
    shadow_layer.putalpha(shadow_mask)
    shadow_offset = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_offset.alpha_composite(
        shadow_layer,
        dest=(TOP5_EDITORIAL_SHADOW_OFFSET[0], TOP5_EDITORIAL_SHADOW_OFFSET[1]),
    )
    canvas.alpha_composite(shadow_offset)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for kind, text, font, x_pos, y_pos in commands:
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

    if subject_mask is not None:
        headline_mask = Image.new("L", canvas.size, 0)
        headline_draw = ImageDraw.Draw(headline_mask)
        for kind, text, font, x_pos, y_pos in commands:
            if kind != "headline":
                continue
            box = headline_draw.textbbox(
                (0, 0),
                text,
                font=font,
                stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            )
            headline_draw.text(
                (x_pos - box[0], y_pos - box[1]),
                text,
                font=font,
                fill=255,
                stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
                stroke_fill=255,
            )

        occlusion_mask = ImageChops.multiply(
            subject_mask.convert("L"),
            ImageChops.lighter(headline_mask, shadow_mask),
        )
        if occlusion_mask.getbbox() is not None:
            canvas = Image.composite(
                source_image.convert("RGBA"),
                canvas,
                occlusion_mask,
            )

    return canvas.convert("RGBA")

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
    subject_cutout: bool = False,
) -> bytes:
    """Render one static Top-5 slide with adaptive editorial typography."""
    frame = _draw_top5_editorial_card(
        source_image,
        {
            "headline": headline,
            "body": body,
            "story_number": story_number,
            "total_stories": total_stories,
            "subject_cutout": bool(subject_cutout),
        },
    )
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

