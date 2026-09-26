"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 15

HEADLINE_SECONDS = 1.15
HEADLINE_TEXT = "THE GAME JUST CHANGED"
SOURCE_LABEL = "SPORTS DESK"
FINAL_STYLE_NAME = "Editorial Highlight"

HEADLINE_MAX_WIDTH = 860
HEADLINE_MAX_SIZE = 118
HEADLINE_MIN_SIZE = 42

ACCENT = (255, 205, 66)
WHITE = (249, 250, 252)
DARK = (5, 7, 10)

# Function 05 should hand this exact shape to Function 06.
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
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)

    return ImageFont.load_default()


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
        return (
            root / "BebasNeue-Regular.ttf",
            root / "BebasNeue-Regular.otf",
        )

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
        root / "Montserrat-ExtraBold.ttf",
        root / "Montserrat-Bold.ttf",
    )


def headline_font(size: int = HEADLINE_MAX_SIZE, language: str = "english"):
    return _font(_font_candidates("headline", language), size)


def subtitle_font(size: int = 58, language: str = "english"):
    return _font(_font_candidates("subtitle", language), size)


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=0)
    return box[2] - box[0], box[3] - box[1]


def _fit_headline_font(
    text: str,
    language: str = "english",
    max_width: int = HEADLINE_MAX_WIDTH,
):
    clean = " ".join(str(text or "").upper().split()) or HEADLINE_TEXT
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def fits(size: int) -> bool:
        font = headline_font(size, language)
        return _measure(probe, clean, font)[0] + 12 <= max_width

    if not fits(HEADLINE_MIN_SIZE):
        raise ValueError("Headline is too long to fit on one line.")

    low, high = HEADLINE_MIN_SIZE, HEADLINE_MAX_SIZE
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1

    font = headline_font(low, language)
    return font, clean, _measure(probe, clean, font)[0]


def make_sample_background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    top = (24, 28, 36)
    bottom = (8, 10, 14)

    for y in range(HEIGHT):
        mix = y / max(1, HEIGHT - 1)
        color = tuple(
            int(top[i] * (1 - mix) + bottom[i] * mix)
            for i in range(3)
        )
        draw.line((0, y, WIDTH, y), fill=color)

    return image


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


def _paste_source(base: Image.Image) -> None:
    draw = ImageDraw.Draw(base)
    font = _font((), 24)
    width, _ = _measure(draw, SOURCE_LABEL, font)
    draw.text(
        (WIDTH - width - 42, HEIGHT - 86),
        SOURCE_LABEL,
        font=font,
        fill=(210, 216, 224),
    )


def _draw_headline(base: Image.Image, text: str, t: float, language: str) -> None:
    font, clean, text_width = _fit_headline_font(text, language)
    progress = min(1.0, max(0.0, t / 0.45))
    eased = 1 - (1 - progress) ** 3
    start_x = -text_width - 80
    final_x = 72
    x = int(start_x + (final_x - start_x) * eased)
    y = 560

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text(
        (x, y),
        clean,
        font=font,
        fill=WHITE,
        stroke_width=6,
        stroke_fill=DARK,
    )

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


def _draw_subtitles(
    base: Image.Image,
    subtitle_data: dict,
    t: float,
) -> None:
    cue = _cue_at_time(subtitle_data, t)
    if cue is None:
        return

    words = cue["words"]
    language = subtitle_data.get("language") or "english"
    font = subtitle_font(58, language)
    draw = ImageDraw.Draw(base)

    pieces = []
    total_width = 0
    spacing = 16
    for word in words:
        text = str(word["text"])
        width, _ = _measure(draw, text, font)
        pieces.append((text, width))
        total_width += width
    total_width += spacing * max(0, len(pieces) - 1)

    cursor = (WIDTH - total_width) // 2
    y = 1450

    for index, (text, width) in enumerate(pieces):
        start = float(words[index]["start"])
        end = float(words[index]["end"])
        active = start <= t < end
        draw.text(
            (cursor, y),
            text,
            font=font,
            fill=ACCENT if active else WHITE,
            stroke_width=5,
            stroke_fill=DARK,
        )
        cursor += width + spacing


def render_frame(
    base_image: Image.Image,
    t: float,
    subtitle_data: dict = PREVIEW_SUBTITLE_DATA,
    headline_text: str = HEADLINE_TEXT,
    headline_enabled: bool = True,
) -> Image.Image:
    if not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Invalid subtitle handoff.")

    frame = base_image.convert("RGBA").resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS,
    )

    if headline_enabled and t < HEADLINE_SECONDS:
        _draw_headline(
            frame,
            headline_text,
            t,
            str(subtitle_data.get("language") or "english"),
        )
    else:
        _draw_subtitles(frame, subtitle_data, t)

    _paste_logo(frame)
    _paste_source(frame)
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
            "24",
            "-pix_fmt",
            "yuv420p",
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


def get_logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.png"


def get_headline_font_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / "BebasNeue-Regular.ttf"
