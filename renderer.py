"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path
import math
import shutil
import subprocess
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 30

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
TOP5_EDITORIAL_HEADLINE_MIN_SIZE = 60
TOP5_EDITORIAL_HEADLINE_MAX_LINES = 2
TOP5_EDITORIAL_HEADLINE_LINE_GAP = 8
TOP5_EDITORIAL_BODY_MAX_SIZE = 50
TOP5_EDITORIAL_BODY_MIN_SIZE = 34
TOP5_EDITORIAL_BODY_LINE_GAP = 10
TOP5_EDITORIAL_HEADLINE_BODY_GAP = 24
TOP5_EDITORIAL_STROKE_WIDTH = 2
TOP5_EDITORIAL_SHADOW_BLUR = 7
TOP5_EDITORIAL_SHADOW_ALPHA = 210
TOP5_EDITORIAL_SHADOW_OFFSET = (0, 5)
TOP5_SUBJECT_HEADLINE_MAX_SIZE = 220
TOP5_SUBJECT_HEADLINE_MIN_SIZE = 92
TOP5_SUBJECT_REMOVAL_MODEL = "ZhengPeng7/BiRefNet"
MANUAL_SUBJECT_MIN_FONT_SIZE = 72
MANUAL_SUBJECT_MAX_FONT_SIZE = 260
MANUAL_SUBJECT_DEFAULT_FONT_SIZE = 150
MANUAL_SUBJECT_FONT_OPTIONS = {
    "Barlow Condensed": {"file": "BarlowCondensed-Black.ttf"},
    "Anton": {"file": "Anton-Regular.ttf"},
    "Oswald": {"file": "Oswald-Bold.ttf"},
    "Barlow": {"file": "Barlow-Regular.ttf"},
    "Bebas Neue": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"},
    "Teko": {"url": "https://raw.githubusercontent.com/itfoundry/teko/master/build/Teko-Bold.otf"},
    "Khand": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/khand/Khand-Bold.ttf"},
    "Kanit": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/kanit/Kanit-Black.ttf"},
    "Fjalla One": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/fjallaone/FjallaOne-Regular.ttf"},
}
MANUAL_SUBJECT_STYLE_OPTIONS = (
    "Crisp Outline",
    "Soft Halo",
    "Long Fade",
    "Editorial Offset",
    "Heavy Drop",
    "Double Edge",
    "Split Shadow",
    "3D Extrusion",
    "Chromatic Echo",
)


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
    path = {
        "hindi": root / "NotoSansDevanagariUI-Regular.ttf",
        "telugu": root / "NotoSansTelugu-Regular.ttf",
    }.get(language, root / "Barlow-Regular.ttf")
    for candidate in (
        path,
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
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
    return _fit_visual_to_frame(image)


def _top5_editorial_measure(draw: ImageDraw.ImageDraw, text: str, fonts: tuple[object, ...]) -> tuple[int, int]:
    runs = _headline_runs(text, fonts)
    if not runs:
        return 0, 0
    boxes = [
        draw.textbbox((0, 0), run, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        for run, font in runs
    ]
    return sum(box[2] - box[0] for box in boxes), max(box[3] - box[1] for box in boxes)


def _top5_wrap_editorial_words(draw: ImageDraw.ImageDraw, text: str, fonts: tuple[object, ...], max_width: int) -> list[list[str]]:
    words = " ".join(str(text or "").split()).split()
    lines = []
    current = []
    for word in words:
        trial = " ".join(current + [word])
        if current and _top5_editorial_measure(draw, trial, fonts)[0] > max_width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


@lru_cache(maxsize=256)
def _top5_headline_font_stack(size: int, language: str) -> tuple[object, ...]:
    root = Path(__file__).resolve().parent / "fonts"
    language = str(language or "english").casefold()
    paths = {
        "hindi": (
            root / "NotoSansDevanagari-CondensedBlack.ttf",
            root / "NotoSansDevanagari-Black.ttf",
        ),
        "telugu": (
            root / "NotoSansTelugu-CondensedBlack.ttf",
            root / "NotoSansTelugu-Black.ttf",
        ),
    }.get(language, (root / "Oswald-Bold.ttf",))
    fonts = []
    for path in paths:
        if path.exists():
            try:
                fonts.append(ImageFont.truetype(str(path), size))
            except OSError:
                pass
    return tuple(fonts) or (ImageFont.load_default(),)


def _top5_two_line_headline(draw: ImageDraw.ImageDraw, words: list[str], fonts: tuple[object, ...]):
    if len(words) < 2:
        width, height = _top5_editorial_measure(draw, " ".join(words), fonts)
        return [words], width, height
    best = None
    for split in range(1, len(words)):
        first, second = words[:split], words[split:]
        w1, h1 = _top5_editorial_measure(draw, " ".join(first), fonts)
        w2, h2 = _top5_editorial_measure(draw, " ".join(second), fonts)
        candidate = (abs(w1 - w2), [first, second], max(w1, w2), h1 + TOP5_EDITORIAL_HEADLINE_LINE_GAP + h2)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1], best[2], best[3]


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
    clean_body = "" if subject_mask is not None else " ".join(str(body or "").split())
    if not clean_headline:
        raise ValueError("Top-5 card requires a headline.")

    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left = TOP5_EDITORIAL_MARGIN_X
    right = WIDTH - TOP5_EDITORIAL_MARGIN_X
    top = TOP5_EDITORIAL_SAFE_TOP
    bottom = TOP5_EDITORIAL_SAFE_BOTTOM
    safe_width = right - left

    def horizontal(region, max_size, min_size):
        rx1, ry1, rx2, ry2 = region
        rw, rh = rx2 - rx1, ry2 - ry1
        words = clean_headline.split()
        for size in range(max_size, min_size - 1, -4):
            fonts = _top5_headline_font_stack(size, language)
            width, height = _top5_editorial_measure(draw, clean_headline, fonts)
            if width <= rw and height <= rh:
                return rx1 + (rw - width) // 2, ry1 + (rh - height) // 2, width, height, fonts, [words], size
            if max_headline_lines >= 2:
                two = _top5_two_line_headline(draw, words, fonts)
                if two[1] <= rw and two[2] <= rh:
                    return rx1 + (rw - two[1]) // 2, ry1 + (rh - two[2]) // 2, two[1], two[2], fonts, two[0], size
            if max_headline_lines > 2:
                lines = _top5_wrap_editorial_words(draw, clean_headline, fonts, rw)
                if 1 <= len(lines) <= max_headline_lines:
                    heights = [_top5_editorial_measure(draw, " ".join(line), fonts)[1] for line in lines]
                    width = max(_top5_editorial_measure(draw, " ".join(line), fonts)[0] for line in lines)
                    height = sum(heights) + TOP5_EDITORIAL_HEADLINE_LINE_GAP * (len(lines) - 1)
                    if width <= rw and height <= rh:
                        return rx1 + (rw - width) // 2, ry1 + (rh - height) // 2, width, height, fonts, lines, size
        return None

    if subject_mask is None:
        layout = horizontal((left, 520, right, bottom), TOP5_EDITORIAL_HEADLINE_DEFAULT_SIZE, TOP5_EDITORIAL_HEADLINE_MIN_SIZE)
        if layout is None:
            raise ValueError("Top-5 headline cannot fit the editorial card.")
        x, y, width, height, fonts, lines, size = layout
        body_font = None
        body_lines = []
        body_height = 0
        if clean_body:
            for body_size in range(TOP5_EDITORIAL_BODY_MAX_SIZE, TOP5_EDITORIAL_BODY_MIN_SIZE - 1, -2):
                font = _top5_body_font(body_size, language)
                lines_body = _top5_wrap_editorial_words(draw, clean_body, (font,), safe_width)
                box = draw.textbbox((0, 0), "Ag", font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
                line_height = box[3] - box[1]
                height_body = line_height * len(lines_body) + TOP5_EDITORIAL_BODY_LINE_GAP * max(0, len(lines_body) - 1)
                if y + height + TOP5_EDITORIAL_HEADLINE_BODY_GAP + height_body <= bottom:
                    body_font, body_lines, body_height = font, lines_body, height_body
                    break
        total_height = height + (TOP5_EDITORIAL_HEADLINE_BODY_GAP + body_height if body_lines else 0)
        return {
            "x": x, "y": max(top, min(bottom - total_height, y)), "width": width,
            "headline_fonts": fonts, "headline_lines": lines, "headline_height": height,
            "headline_size": size, "body_font": body_font, "body_lines": body_lines,
            "body_height": body_height, "body_size": body_font.size if body_font else None,
            "body_gap": TOP5_EDITORIAL_HEADLINE_BODY_GAP if body_lines else 0,
            "total_height": total_height, "zone_bottom": bottom, "subject_overlap": 0.0,
            "subject_bbox": None, "composition_mode": "editorial", "region_mode": "static",
            "story_number": story_number,
        }

    mask = subject_mask.convert("L").point(lambda value: 255 if value >= 96 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("Top-5 Subject Cutout returned no usable foreground subjects.")

    sx1, sy1, sx2, sy2 = bbox
    subject_height = max(1, sy2 - sy1)
    words = clean_headline.split()

    for size in range(TOP5_SUBJECT_HEADLINE_MAX_SIZE, TOP5_SUBJECT_HEADLINE_MIN_SIZE - 1, -2):
        fonts = _top5_headline_font_stack(size, language)
        width, height = _top5_editorial_measure(draw, clean_headline, fonts)
        lines = [words]
        if width > safe_width or height > (bottom - top):
            if max_headline_lines < 2:
                continue
            two = _top5_two_line_headline(draw, words, fonts)
            if two[1] > safe_width or two[2] > (bottom - top):
                continue
            lines, width, height = two[0], two[1], two[2]

        positions = [
            (left + (safe_width - width) / 2, sy1 - height * 0.62),
            (left + (safe_width - width) / 2, sy1 + (subject_height - height) / 2),
            (left + (safe_width - width) / 2, sy2 - height * 0.38),
        ]
        if sx1 > left + width * 0.18:
            positions.append((left, sy1 + (subject_height - height) / 2))
        if sx2 < right - width * 0.18:
            positions.append((right - width, sy1 + (subject_height - height) / 2))

        candidates = []
        for candidate_x, candidate_y in positions:
            x = int(round(max(left, min(right - width, candidate_x))))
            y = int(round(max(top, min(bottom - height, candidate_y))))
            overlap = mask.crop((x, y, x + width, y + height))
            overlap_ratio = sum(overlap.histogram()[1:]) / max(1, width * height)
            distance = abs(overlap_ratio - 0.22)
            candidates.append((distance, -overlap_ratio if overlap_ratio <= 0.42 else overlap_ratio, x, y, overlap_ratio))

        if candidates:
            viable = [candidate for candidate in candidates if candidate[4] <= 0.42]
            if viable:
                _, _, x, y, overlap_ratio = min(viable, key=lambda item: (item[0], item[1]))
                return {
                    "x": x, "y": y, "width": width, "headline_fonts": fonts,
                    "headline_lines": lines, "headline_height": height, "headline_size": size,
                    "body_font": None, "body_lines": [], "body_height": 0, "body_size": None,
                    "body_gap": 0, "total_height": height, "zone_bottom": bottom,
                    "subject_overlap": overlap_ratio, "subject_bbox": bbox,
                    "composition_mode": "subject-cutout", "region_mode": "hero-overlay",
                    "story_number": story_number,
                }

    raise ValueError("Top-5 Subject Cutout could not place the headline.")

@lru_cache(maxsize=1)
def _load_top5_birefnet():
    try:
        import torch
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError("Top-5 Subject Cutout needs the existing torch, torchvision and transformers packages.") from exc

    model = AutoModelForImageSegmentation.from_pretrained(
        TOP5_SUBJECT_REMOVAL_MODEL,
        trust_remote_code=True,
    )
    model = model.to(torch.device("cpu")).float().eval()
    return model, transforms


@lru_cache(maxsize=64)
def _top5_subject_mask(image_bytes: bytes) -> Image.Image | None:
    if not image_bytes:
        return None
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Top-5 Subject Cutout needs torch.") from exc

    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGB")

    model, transforms = _load_top5_birefnet()
    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    tensor = transform(image).unsqueeze(0).to(dtype=torch.float32)

    with torch.inference_mode():
        prediction = model(tensor)
        if isinstance(prediction, (tuple, list)):
            prediction = prediction[-1]
        prediction = prediction.sigmoid().squeeze().cpu()

    mask = transforms.ToPILImage()(prediction)
    mask = mask.resize(image.size, Image.Resampling.BILINEAR)
    if mask.getbbox() is None:
        return None
    return mask.filter(ImageFilter.MedianFilter(3))


def _draw_top5_editorial_card(base: Image.Image, card: dict) -> Image.Image:
    language = str(card.get("language") or "english")
    headline = " ".join(str(card.get("headline") or "").split())
    subject_cutout = bool(card.get("subject_cutout"))
    body = "" if subject_cutout else " ".join(str(card.get("body") or "").split())
    if not headline:
        raise ValueError("Top-5 card requires a headline.")

    source_image = _top5_full_frame_image(base)
    subject_mask = None
    if subject_cutout:
        source_bytes = BytesIO()
        source_image.save(source_bytes, format="PNG", optimize=False)
        subject_mask = _top5_subject_mask(source_bytes.getvalue())
        if subject_mask is None:
            raise ValueError("Top-5 Subject Cutout could not produce a usable foreground mask.")

    layout = _top5_editorial_layout(
        headline,
        body,
        language,
        int(card.get("story_number") or 0),
        int(card.get("max_headline_lines") or TOP5_EDITORIAL_HEADLINE_MAX_LINES),
        image=source_image,
        subject_mask=subject_mask,
    )

    if subject_mask is not None:
        subject_mask = subject_mask.convert("L").point(lambda value: 255 if value >= 96 else 0)
        backdrop = Image.blend(
            source_image.convert("RGBA"),
            Image.new("RGBA", source_image.size, DARK + (255,)),
            0.20,
        )
        canvas = Image.composite(
            source_image.convert("RGBA"),
            backdrop,
            subject_mask,
        )

        subject_shadow = subject_mask.filter(ImageFilter.GaussianBlur(9))
        subject_shadow = subject_shadow.point(lambda value: min(150, value * 150 // 255))
        shadow_layer = Image.new("RGBA", canvas.size, DARK + (0,))
        shadow_layer.putalpha(subject_shadow)
        canvas.alpha_composite(shadow_layer, dest=(0, 7))
    else:
        canvas = source_image.convert("RGBA")

    draw = ImageDraw.Draw(canvas, "RGBA")
    commands = []
    cursor_y = layout["y"]

    for line_words in layout["headline_lines"]:
        line = " ".join(line_words)
        cursor_x = layout["x"]
        for run, font in _headline_runs(line, layout["headline_fonts"]):
            box = draw.textbbox((0, 0), run, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
            commands.append((run, font, cursor_x, cursor_y))
            cursor_x += box[2] - box[0]
        cursor_y += _top5_editorial_measure(draw, line, layout["headline_fonts"])[1] + TOP5_EDITORIAL_HEADLINE_LINE_GAP

    if layout["body_lines"] and layout["body_font"] is not None:
        cursor_y = layout["y"] + layout["headline_height"] + TOP5_EDITORIAL_HEADLINE_BODY_GAP
        for line_words in layout["body_lines"]:
            commands.append((" ".join(line_words), layout["body_font"], layout["x"], cursor_y))
            box = draw.textbbox((0, 0), "Ag", font=layout["body_font"], stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
            cursor_y += box[3] - box[1] + TOP5_EDITORIAL_BODY_LINE_GAP

    crop_box = (
        max(0, layout["x"]),
        max(0, layout["y"]),
        min(WIDTH, layout["x"] + max(1, layout["width"])),
        min(HEIGHT, layout["y"] + max(1, layout["total_height"])),
    )
    luma = source_image.convert("L").crop(crop_box).resize((1, 1)).getpixel((0, 0))
    light_text = luma < 145
    text_fill = (249, 250, 252, 255) if light_text else (5, 7, 10, 255)
    shadow_rgb = (5, 7, 10) if light_text else (249, 250, 252)
    stroke_fill = (5, 7, 10, 235) if light_text else (249, 250, 252, 235)

    text_mask = Image.new("L", canvas.size, 0)
    text_draw = ImageDraw.Draw(text_mask)
    for text, font, x, y in commands:
        box = text_draw.textbbox((0, 0), text, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        text_draw.text(
            (x - box[0], y - box[1]),
            text,
            font=font,
            fill=255,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=255,
        )

    shadow = text_mask.filter(ImageFilter.GaussianBlur(TOP5_EDITORIAL_SHADOW_BLUR))
    shadow = shadow.point(lambda value: value * TOP5_EDITORIAL_SHADOW_ALPHA // 255)
    shadow_layer = Image.new("RGBA", canvas.size, shadow_rgb + (0,))
    shadow_layer.putalpha(shadow)
    canvas.alpha_composite(shadow_layer, dest=TOP5_EDITORIAL_SHADOW_OFFSET)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for text, font, x, y in commands:
        box = draw.textbbox((0, 0), text, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        draw.text(
            (x - box[0], y - box[1]),
            text,
            font=font,
            fill=text_fill,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=stroke_fill,
        )

    if subject_mask is not None:
        canvas = Image.composite(source_image.convert("RGBA"), canvas, subject_mask)

    return canvas


@lru_cache(maxsize=16)
def _manual_subject_font_bytes(font_name: str) -> bytes:
    source = MANUAL_SUBJECT_FONT_OPTIONS.get(font_name)
    if not source:
        raise ValueError("Manual Subject Cutout has an invalid font.")
    if source.get("file"):
        path = Path(__file__).resolve().parent / "fonts" / str(source["file"])
        if not path.exists():
            raise RuntimeError(f"Manual Subject Cutout requires the bundled {font_name} font.")
        return path.read_bytes()
    from urllib.request import urlopen
    try:
        with urlopen(str(source["url"]), timeout=20) as response:
            return response.read()
    except Exception as exc:
        raise RuntimeError(f"Manual Subject Cutout could not load the {font_name} font.") from exc



def _manual_subject_cutout_layout_data(
    headline: str,
    polygon,
    font_size: int,
    font_name: str,
    style: str,
):
    clean_headline = " ".join(str(headline or "").split()).upper()
    if not clean_headline:
        raise ValueError("Manual Subject Cutout requires a headline.")

    if not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
        raise ValueError("Manual Subject Cutout requires a polygon text area.")

    try:
        points = [
            (
                max(0, min(WIDTH, int(point[0]))),
                max(0, min(HEIGHT, int(point[1]))),
            )
            for point in polygon
        ]
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("Manual Subject Cutout has invalid polygon points.") from exc

    box_left = min(x for x, _ in points)
    box_top = min(y for _, y in points)
    box_right = max(x for x, _ in points)
    box_bottom = max(y for _, y in points)
    box_width = box_right - box_left
    box_height = box_bottom - box_top
    if box_width <= 0 or box_height <= 0:
        raise ValueError("Manual Subject Cutout text area must have positive dimensions.")

    try:
        requested_size = int(font_size or MANUAL_SUBJECT_DEFAULT_FONT_SIZE)
    except (TypeError, ValueError) as exc:
        raise ValueError("Manual Subject Cutout has invalid font size.") from exc
    requested_size = max(
        MANUAL_SUBJECT_MIN_FONT_SIZE,
        min(MANUAL_SUBJECT_MAX_FONT_SIZE, requested_size),
    )

    mode = str(font_name or "").strip()
    if mode not in MANUAL_SUBJECT_FONT_OPTIONS:
        raise ValueError("Manual Subject Cutout has an invalid font.")

    clean_style = str(style or "").strip()
    if clean_style not in MANUAL_SUBJECT_STYLE_OPTIONS:
        raise ValueError("Manual Subject Cutout has an invalid text style.")

    font_data = _manual_subject_font_bytes(mode)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    stroke_width = {
        "Crisp Outline": 4,
        "Soft Halo": 2,
        "Long Fade": 2,
        "Editorial Offset": 2,
        "Heavy Drop": 3,
        "Double Edge": 9,
        "Split Shadow": 3,
        "3D Extrusion": 3,
        "Chromatic Echo": 3,
    }[clean_style]

    def polygon_intervals(y_value: float) -> list[tuple[float, float]]:
        y_value = max(0.0, min(HEIGHT - 0.001, y_value))
        intersections = []
        for index, (x1, y1) in enumerate(points):
            x2, y2 = points[(index + 1) % len(points)]
            if y1 == y2:
                continue
            if (y1 <= y_value < y2) or (y2 <= y_value < y1):
                intersections.append(
                    x1 + (y_value - y1) * (x2 - x1) / (y2 - y1)
                )
        intersections.sort()
        return [
            (left, right)
            for left, right in zip(intersections[0::2], intersections[1::2])
            if right > left
        ]

    def line_position(
        line: str,
        font: ImageFont.FreeTypeFont,
        line_top: float,
        line_bottom: float,
    ):
        bbox = probe.textbbox(
            (0, 0),
            line,
            font=font,
            stroke_width=stroke_width,
        )
        line_width = bbox[2] - bbox[0]
        sample_y = [
            line_top + (line_bottom - line_top) * fraction
            for fraction in (0.08, 0.28, 0.5, 0.72, 0.92)
        ]
        regions = [polygon_intervals(y_value) for y_value in sample_y]
        if any(not region for region in regions):
            return None

        widest = [
            max(region, key=lambda interval: interval[1] - interval[0])
            for region in regions
        ]
        common_left = max(interval[0] for interval in widest)
        common_right = min(interval[1] for interval in widest)
        usable_width = common_right - common_left
        if usable_width < line_width:
            return None

        center = (common_left + common_right) / 2
        left = center - line_width / 2
        right = center + line_width / 2
        if not all(
            any(
                interval_left <= left and right <= interval_right
                for interval_left, interval_right in region
            )
            for region in regions
        ):
            return None

        return int(round(left)), bbox, usable_width

    words = clean_headline.split()
    layouts = []
    font = ImageFont.truetype(BytesIO(font_data), requested_size)
    line_box = probe.textbbox(
        (0, 0),
        "Ag",
        font=font,
        stroke_width=stroke_width,
    )
    line_height = max(1, line_box[3] - line_box[1])

    for mask in range(1 << max(0, len(words) - 1)):
        breaks = [
            index + 1
            for index in range(len(words) - 1)
            if mask & (1 << index)
        ]
        breaks.append(len(words))
        lines = []
        start = 0
        for end in breaks:
            lines.append(" ".join(words[start:end]))
            start = end

        total_height = (
            line_height * len(lines)
            + TOP5_EDITORIAL_HEADLINE_LINE_GAP * max(0, len(lines) - 1)
        )
        if total_height > box_height:
            continue

        start_y = box_top + (box_height - total_height) / 2
        placements = []
        fill_ratios = []
        word_index = 0
        valid = True
        for line_index, end in enumerate(breaks):
            line = " ".join(words[word_index:end])
            line_top = start_y + line_index * (
                line_height + TOP5_EDITORIAL_HEADLINE_LINE_GAP
            )
            line_bottom = line_top + line_height
            position = line_position(line, font, line_top, line_bottom)
            if position is None:
                valid = False
                break
            cursor_x, bbox, usable_width = position
            placements.append((line, line_top, cursor_x, bbox))
            fill_ratios.append(
                (bbox[2] - bbox[0]) / max(1.0, usable_width)
            )
            word_index = end

        if valid:
            layouts.append({
                "line_breaks": tuple(breaks),
                "lines": tuple(lines),
                "placements": tuple(placements),
                "fill_ratio": sum(fill_ratios) / len(fill_ratios),
            })

    layouts.sort(
        key=lambda item: (
            item["fill_ratio"],
            -len(item["lines"]),
            item["line_breaks"],
        ),
        reverse=True,
    )
    return {
        "headline": clean_headline,
        "points": points,
        "box_height": box_height,
        "font_size": requested_size,
        "font_name": mode,
        "style": clean_style,
        "font_data": font_data,
        "font": font,
        "stroke_width": stroke_width,
        "layouts": layouts,
    }


def _draw_manual_subject_cutout_frame(
    base: Image.Image,
    data: dict,
    placements,
    *,
    mode: str,
    subject_mask: Image.Image | None = None,
) -> Image.Image:
    canvas = _top5_full_frame_image(base).convert("RGBA")

    if mode == "behind-subject":
        if subject_mask is None:
            source = BytesIO()
            canvas.convert("RGB").save(source, format="PNG", optimize=False)
            subject_mask = _top5_subject_mask(source.getvalue())
            if subject_mask is None:
                raise ValueError("Manual Subject Cutout could not produce a usable subject mask.")
            subject_mask = subject_mask.convert("L").point(
                lambda value: 255 if value >= 96 else value
            )
        backdrop = Image.blend(
            canvas,
            Image.new("RGBA", canvas.size, DARK + (255,)),
            0.18,
        )
        canvas = Image.composite(canvas, backdrop, subject_mask)

    text_mask = Image.new("L", canvas.size, 0)
    text_draw = ImageDraw.Draw(text_mask)
    for line, line_top, cursor_x, bbox in placements:
        text_draw.text(
            (cursor_x - bbox[0], line_top - bbox[1]),
            line,
            font=data["font"],
            fill=255,
            stroke_width=data["stroke_width"],
            stroke_fill=255,
        )

    def shifted_layer(
        offset_x: int,
        offset_y: int,
        alpha: int,
        blur: int = 0,
        fill=DARK,
    ) -> None:
        layer_mask = text_mask.filter(ImageFilter.GaussianBlur(blur)) if blur else text_mask
        layer_mask = layer_mask.point(lambda value: value * alpha // 255)
        layer = Image.new("RGBA", canvas.size, fill + (0,))
        layer.putalpha(layer_mask)
        canvas.alpha_composite(layer, dest=(offset_x, offset_y))

    style = data["style"]
    if style == "Soft Halo":
        shifted_layer(0, 0, 80, 24)
        shifted_layer(0, 4, 175, 16)
    elif style == "Long Fade":
        shifted_layer(0, 4, 115, 7)
        shifted_layer(0, 8, 90, 7)
        shifted_layer(0, 12, 65, 7)
        shifted_layer(0, 16, 40, 7)
    elif style == "Editorial Offset":
        shifted_layer(5, 6, 155, 2, ACCENT)
        shifted_layer(0, 5, 110, 5)
    elif style == "Heavy Drop":
        shifted_layer(4, 8, 235)
        shifted_layer(8, 14, 170)
        shifted_layer(12, 19, 90, 1)
    elif style == "Double Edge":
        shifted_layer(0, 4, 210, 3)
    elif style == "Split Shadow":
        shifted_layer(-7, 5, 145, 2, ACCENT)
        shifted_layer(6, 8, 220, 5)
    elif style == "3D Extrusion":
        shifted_layer(3, 4, 245)
        shifted_layer(6, 8, 225)
        shifted_layer(9, 12, 195)
        shifted_layer(12, 16, 150)
        shifted_layer(15, 20, 105, 1)
    elif style == "Chromatic Echo":
        shifted_layer(-7, 5, 175, 1, ACCENT)
        shifted_layer(7, -4, 130, 2)
        shifted_layer(0, 6, 145, 5)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for line, line_top, cursor_x, bbox in placements:
        position = (cursor_x - bbox[0], line_top - bbox[1])
        if style == "Double Edge":
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=9,
                stroke_fill=DARK + (255,),
            )
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=2,
                stroke_fill=DARK + (245,),
            )
        else:
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=data["stroke_width"],
                stroke_fill=DARK + (245,),
            )

    if subject_mask is not None:
        canvas = Image.composite(
            _top5_full_frame_image(base).convert("RGBA"),
            canvas,
            subject_mask,
        )

    return canvas


def _draw_manual_subject_cutout(base: Image.Image, config: dict) -> Image.Image:
    mode = str(config.get("mode") or "negative-space").strip().casefold()
    if mode not in {"negative-space", "behind-subject"}:
        raise ValueError("Manual Subject Cutout has an invalid composition mode.")

    data = _manual_subject_cutout_layout_data(
        config.get("headline"),
        config.get("text_polygon"),
        config.get("font_size"),
        str(config.get("font") or "Barlow Condensed").strip(),
        str(config.get("style") or "Crisp Outline").strip(),
    )
    layouts = data["layouts"]
    if not layouts:
        raise ValueError(
            f"Text size {data['font_size']}px does not fit the selected polygon. Make the polygon larger or choose a smaller size."
        )

    selected_breaks = config.get("line_breaks")
    if selected_breaks is not None:
        try:
            selected_breaks = tuple(int(value) for value in selected_breaks)
        except (TypeError, ValueError):
            raise ValueError("Manual Subject Cutout has invalid line breaks.")
        layout = next(
            (item for item in layouts if item["line_breaks"] == selected_breaks),
            None,
        )
        if layout is None:
            raise ValueError("The selected line-break layout does not fit the current polygon or text size.")
    else:
        layout = layouts[0]

    subject_mask = None
    if mode == "behind-subject":
        source = BytesIO()
        _top5_full_frame_image(base).convert("RGB").save(source, format="PNG", optimize=False)
        subject_mask = _top5_subject_mask(source.getvalue())
        if subject_mask is None:
            raise ValueError("Manual Subject Cutout could not produce a usable subject mask.")
        subject_mask = subject_mask.convert("L").point(
            lambda value: 255 if value >= 96 else value
        )

    return _draw_manual_subject_cutout_frame(
        base,
        data,
        layout["placements"],
        mode=mode,
        subject_mask=subject_mask,
    )


def build_manual_subject_cutout_preview(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    *,
    mode: str,
    font_size: int,
    font: str = "Barlow Condensed",
    style: str = "Crisp Outline",
    text_polygon: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
    line_breaks: tuple[int, ...] | list[int] | None = None,
) -> bytes:
    frame = _draw_manual_subject_cutout(
        source_image,
        {
            "headline": headline,
            "mode": mode,
            "text_polygon": text_polygon,
            "font_size": int(font_size),
            "font": font,
            "style": style,
            "line_breaks": line_breaks,
        },
    )
    buffer = BytesIO()
    frame.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_manual_subject_cutout_layout_previews(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    *,
    mode: str,
    font_size: int,
    font: str = "Barlow Condensed",
    style: str = "Crisp Outline",
    text_polygon: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
) -> list[dict]:
    selected_mode = str(mode or "negative-space").strip().casefold()
    if selected_mode not in {"negative-space", "behind-subject"}:
        raise ValueError("Manual Subject Cutout has an invalid composition mode.")

    data = _manual_subject_cutout_layout_data(
        headline,
        text_polygon,
        font_size,
        font,
        style,
    )
    if not data["layouts"]:
        raise ValueError(
            f"Text size {data['font_size']}px does not fit the selected polygon. Make the polygon larger or choose a smaller size."
        )

    subject_mask = None
    if selected_mode == "behind-subject":
        base = _top5_full_frame_image(
            source_image if isinstance(source_image, Image.Image) else Image.open(BytesIO(bytes(source_image)))
        ).convert("RGBA")
        source = BytesIO()
        base.convert("RGB").save(source, format="PNG", optimize=False)
        subject_mask = _top5_subject_mask(source.getvalue())
        if subject_mask is None:
            raise ValueError("Manual Subject Cutout could not produce a usable subject mask.")
        subject_mask = subject_mask.convert("L").point(
            lambda value: 255 if value >= 96 else value
        )

    base_image = (
        source_image.convert("RGB")
        if isinstance(source_image, Image.Image)
        else Image.open(BytesIO(bytes(source_image))).convert("RGB")
    )

    previews = []
    for index, layout in enumerate(data["layouts"], 1):
        frame = _draw_manual_subject_cutout_frame(
            base_image,
            data,
            layout["placements"],
            mode=selected_mode,
            subject_mask=subject_mask,
        ).resize((360, 640), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        frame.convert("RGB").save(buffer, format="JPEG", quality=84, optimize=True)
        previews.append({
            "index": index,
            "line_breaks": layout["line_breaks"],
            "lines": layout["lines"],
            "preview": buffer.getvalue(),
        })
    return previews


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
            "max_headline_lines": 10,
        },
    )


def build_quote_card_preview(
    source_image: bytes | bytearray | Image.Image,
    quote: str,
    attribution: str,
    source_label: str | None = None,
    logo_enabled: bool = False,
) -> bytes:
    frame = _draw_quote_card(_top5_full_frame_image(source_image), {
        "quote": quote,
        "attribution": attribution,
    })
    if logo_enabled:
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
        (WIDTH - TOP5_EDITORIAL_MARGIN_X - (box[2] - box[0]), HEIGHT - 48),
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
    logo_enabled: bool = False,
) -> bytes:
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



def _motion_profile(seed: str) -> tuple[int, float, float, int, int]:
    digest = hashlib.sha1(str(seed or "visual").encode("utf-8")).digest()
    return (
        digest[0] % 5,
        1.04 + (digest[1] % 5) * 0.006,
        1.085 + (digest[2] % 5) * 0.006,
        -1 if digest[3] & 1 else 1,
        -1 if digest[4] & 1 else 1,
    )


def _animate_visual(
    image: Image.Image,
    t: float,
    duration: float,
    seed: str,
) -> Image.Image:
    if duration <= 0.0:
        return image.copy()

    mode, start_scale, end_scale, x_direction, y_direction = _motion_profile(seed)
    progress = min(1.0, max(0.0, float(t) / duration))
    eased = 0.5 - 0.5 * math.cos(math.pi * progress)

    if mode == 1:
        scale = end_scale - (end_scale - start_scale) * eased
    elif mode == 4:
        scale = start_scale + (end_scale - start_scale) * eased * 0.65
    else:
        scale = start_scale + (end_scale - start_scale) * eased

    if mode == 0:
        x_progress, y_progress = eased * x_direction, 0.0
    elif mode == 1:
        x_progress, y_progress = 0.0, eased * y_direction
    elif mode == 2:
        x_progress, y_progress = eased * x_direction, eased * y_direction
    elif mode == 3:
        x_progress, y_progress = (eased - 0.5) * 2.0 * x_direction, 0.0
    else:
        x_progress, y_progress = eased * 0.5 * x_direction, (eased - 0.5) * y_direction

    scaled_width = max(WIDTH, int(round(WIDTH * scale)))
    scaled_height = max(HEIGHT, int(round(HEIGHT * scale)))
    scaled = image.resize((scaled_width, scaled_height), Image.Resampling.BICUBIC)
    max_x, max_y = scaled_width - WIDTH, scaled_height - HEIGHT
    x = int(round(max_x / 2.0 + max_x / 2.0 * x_progress))
    y = int(round(max_y / 2.0 + max_y / 2.0 * y_progress))
    x = max(0, min(max_x, x))
    y = max(0, min(max_y, y))
    return scaled.crop((x, y, x + WIDTH, y + HEIGHT))



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
    logo_enabled: bool = False,
    source_enabled: bool = True,
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

    if logo_enabled:
        _paste_logo(frame)
    if source_enabled:
        if source_label is None:
            _paste_source(frame)
        else:
            _paste_source(frame, source_label)
    return frame.convert("RGB")


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None



def write_preview_video(frames, path: Path) -> Path:
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg is required to create renderer videos.")

    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
            "-an",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-profile:v", "high",
            "-bf", "2",
            "-g", str(max(1, FPS // 2)),
            "-keyint_min", str(max(1, FPS // 2)),
            "-flags", "+cgop",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-movflags", "+faststart",
            "-fps_mode", "cfr",
            str(path),
        ],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin is not None

    try:
        wrote_frame = False
        for frame in frames:
            wrote_frame = True
            if frame.size != (WIDTH, HEIGHT):
                frame = frame.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            process.stdin.write(frame.convert("RGB").tobytes())
        if not wrote_frame:
            process.stdin.close()
            process.kill()
            raise ValueError("No frames were provided.")
        process.stdin.close()
    except BrokenPipeError as exc:
        process.kill()
        raise RuntimeError("ffmpeg stopped while creating the video.") from exc

    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise RuntimeError(stderr.strip() or "ffmpeg failed to create the video.")
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
            raise ValueError(f"Audio file for scene {scene.get('scene') or index} is missing.")
        inputs.extend(["-i", str(audio_path)])
        filter_inputs.append(f"[{index}:a]")

    filter_complex = "".join(filter_inputs) + f"concat=n={len(audio_scenes)}:v=0:a=1[a]"

    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(output_path),
        ],
        capture_output=True, text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "ffmpeg failed to attach the audio.")
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
    logo_enabled: bool = False,
    source_enabled: bool = True,
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
        manual_subject_cutout = visual.get("manual_subject_cutout")
        if manual_subject_cutout is not None and not isinstance(manual_subject_cutout, dict):
            raise ValueError(f"Visual {index} has malformed Manual Subject Cutout data.")
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
        if isinstance(manual_subject_cutout, dict):
            preview_bytes = visual.get("preview_bytes")
            if isinstance(preview_bytes, (bytes, bytearray)):
                with Image.open(BytesIO(bytes(preview_bytes))) as preview_image:
                    static_frame = preview_image.convert("RGB").copy()
            else:
                static_frame = _draw_manual_subject_cutout(image, manual_subject_cutout).convert("RGB")
        elif isinstance(top5_card, dict):
            static_frame = _draw_top5_editorial_card(image, top5_card)
            _paste_source(
                static_frame,
                str(visual.get("source") or source_label or "Commons").strip() or "Commons",
            )
            static_frame = static_frame.convert("RGB")
        elif isinstance(quote_card, dict):
            static_frame = _draw_quote_card(image, quote_card)
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
            "manual_subject_cutout": manual_subject_cutout,
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
            while scene_index < len(durations) - 1 and t >= elapsed + durations[scene_index]:
                elapsed += durations[scene_index]
                scene_index += 1

            visual = prepared_visuals[scene_index]
            scene_time = max(0.0, t - elapsed)
            scene_duration = durations[scene_index]
            subtitle_y = None

            if visual["is_stats_card"]:
                image_height = visual["image_height"] or 860
                subtitle_y = max(64, image_height - 96)

            if visual.get("static_frame") is not None:
                yield visual["static_frame"]
                continue

            base_image = visual["image"]
            if not (
                visual["is_stats_card"]
                or visual.get("is_top5_card")
                or visual.get("is_quote_card")
                or visual.get("manual_subject_cutout")
            ):
                visual_seed = "|".join(
                    str(visual.get(key) or "")
                    for key in (
                        "primary_entity",
                        "visual_intent",
                        "specific_search_prompt",
                        "sport_or_topic_category",
                        "source",
                    )
                ).strip("|")
                if not visual_seed:
                    visual_seed = hashlib.sha1(base_image.tobytes()).hexdigest()
                base_image = _animate_visual(
                    base_image, scene_time, scene_duration, visual_seed
                )

            yield render_frame(
                base_image,
                t,
                subtitle_data,
                headline_text or HEADLINE_TEXT,
                headline_enabled,
                source_label,
                subtitle_y,
                None,
                False,
                None,
                logo_enabled=logo_enabled,
                source_enabled=source_enabled,
            )

    try:
        write_preview_video(frames(), silent_video)
        return _mux_audio(silent_video, audio_scenes, output)
    finally:
        try:
            silent_video.unlink()
        except FileNotFoundError:
            pass

