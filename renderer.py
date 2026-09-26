"""Function 06 test-only renderer previews.

This module is deliberately independent from the factory handoffs. It uses
only local filler content, a generated sample background, optional logo.png,
and Pillow/FFmpeg. No AI, API, audio, subtitle, or visual-source calls.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 15
HEADLINE_SECONDS = 1.15
FULL_PREVIEW_SECONDS = 2.8
HEADLINE_TEXT = "THE GAME JUST CHANGED"
SOURCE_LABEL = "SPORTS DESK"
FILLER_WORDS = (
    "India",
    "started",
    "strongly,",
    "but",
    "the",
    "momentum",
    "shifted",
    "when",
    "pressure",
    "finally",
    "arrived.",
)
FILLER_WORD_TIMINGS = (
    (0.00, 0.26),
    (0.26, 0.49),
    (0.49, 0.73),
    (0.73, 0.88),
    (0.88, 1.03),
    (1.03, 1.30),
    (1.30, 1.55),
    (1.55, 1.72),
    (1.72, 1.97),
    (1.97, 2.22),
    (2.22, 2.55),
)


STYLE_NAMES = (
    "Clean Editorial",
    "Micro Glass",
    "Broadcast / Data",
)


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


def headline_font(size: int = 118):
    root = Path(__file__).resolve().parent
    return _font(
        (
            root / "fonts" / "BebasNeue-Regular.ttf",
            root / "fonts" / "BebasNeue-Regular.otf",
        ),
        size,
    )


def subtitle_font(size: int = 58):
    root = Path(__file__).resolve().parent
    return _font(
        (
            root / "fonts" / "Montserrat-ExtraBold.ttf",
            root / "fonts" / "Montserrat-ExtraBold.otf",
        ),
        size,
    )


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=0)
    return box[2] - box[0], box[3] - box[1]


def _wrap(text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    for word in words:
        candidate = f"{current} {word}".strip()
        width, _ = _measure(probe, candidate, font)
        if current and width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)
    return lines[:max_lines] if len(lines) > max_lines else lines


def _headline_layout(text: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    clean = " ".join(text.upper().split())
    if not clean:
        clean = HEADLINE_TEXT

    size = 118
    while size >= 78:
        font = headline_font(size)
        lines = _wrap(clean, font, 860, 2)

        if len(lines) <= 2:
            probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            if all(_measure(probe, line, font)[0] <= 860 for line in lines):
                return font, lines
        size -= 4

    font = headline_font(78)
    return font, _wrap(clean, font, 860, 2)


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
    x = WIDTH - logo.width - 42
    y = 36
    base.paste(logo, (x, y), logo)


def _paste_source(base: Image.Image, style: str) -> None:
    draw = ImageDraw.Draw(base)
    font = _font((), 24)
    label_w, _ = _measure(draw, SOURCE_LABEL, font)
    x = WIDTH - label_w - 42
    y = HEIGHT - 86
    draw.text(
        (x, y),
        SOURCE_LABEL,
        font=font,
        fill=(210, 216, 224),
    )


def _headline_position(text_lines: list[str], font, t: float) -> tuple[int, int, float]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [_measure(draw, line, font)[0] for line in text_lines]
    text_width = max(widths) if widths else 0
    start_x = -text_width - 80
    final_x = 72
    progress = min(1.0, max(0.0, t / 0.45))
    eased = 1 - (1 - progress) ** 3
    x = int(start_x + (final_x - start_x) * eased)
    return x, 470, eased


def _draw_headline(base: Image.Image, text: str, t: float) -> None:
    font, lines = _headline_layout(text)
    x, y, progress = _headline_position(lines, font, t)

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    current_y = y
    for line in lines:
        draw.text(
            (x, current_y),
            line,
            font=font,
            fill=(249, 250, 252, 255),
            stroke_width=6,
            stroke_fill=(5, 7, 10, 235),
        )
        current_y += 112

    if t < 0.68 and progress < 1.0:
        layer = layer.filter(
            ImageFilter.GaussianBlur(radius=max(0.0, 2.5 * (1 - progress)))
        )
    base.paste(layer, (0, 0), layer)


def _groups_at_time(t: float) -> tuple[list[str], int]:
    active = len(FILLER_WORD_TIMINGS) - 1
    for index, (start, end) in enumerate(FILLER_WORD_TIMINGS):
        if start <= t < end:
            active = index
            break

    group_start = (active // 4) * 4
    group_end = min(group_start + 4, len(FILLER_WORDS))
    return list(FILLER_WORDS[group_start:group_end]), active - group_start


def _draw_subtitles(base: Image.Image, style: str, t: float) -> None:
    words, active_index = _groups_at_time(t)
    font = subtitle_font()
    draw = ImageDraw.Draw(base)
    text = " ".join(words)

    if style == "Clean Editorial":
        x = WIDTH // 2
        y = 1450
        pieces = text.split()
        widths = [_measure(draw, word, font)[0] for word in pieces]
        total_width = sum(widths) + 18 * max(0, len(pieces) - 1)
        cursor = x - total_width // 2

        for index, word in enumerate(pieces):
            draw.text(
                (cursor, y),
                word,
                font=font,
                fill=(92, 205, 255) if index == active_index else (248, 249, 251),
                stroke_width=5,
                stroke_fill=(5, 7, 10),
            )
            cursor += widths[index] + 18
        return

    if style == "Micro Glass":
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        width = min(930, bbox[2] - bbox[0] + 64)
        height = bbox[3] - bbox[1] + 44
        x = (WIDTH - width) // 2
        y = 1435

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=28,
            fill=(12, 16, 22, 155),
            outline=(138, 153, 169, 100),
            width=1,
        )

        text_start = WIDTH // 2 - (bbox[2] - bbox[0]) // 2
        prefix = " ".join(words[:active_index])
        before = _measure(odraw, prefix, font)[0] + (18 if prefix else 0)
        active_w = _measure(odraw, words[active_index], font)[0]
        odraw.rounded_rectangle(
            (
                text_start + before - 6,
                y + 10,
                text_start + before + active_w + 6,
                y + height - 10,
            ),
            radius=16,
            fill=(92, 205, 255, 55),
        )
        odraw.text(
            (WIDTH // 2, y + height // 2),
            text,
            font=font,
            fill=(248, 249, 251),
            anchor="mm",
            stroke_width=3,
            stroke_fill=(4, 6, 9, 180),
        )
        base.paste(overlay, (0, 0), overlay)
        return

    x = 82
    y = 1405
    draw.text(
        (x, y),
        "BROADCAST",
        font=_font((), 22),
        fill=(154, 166, 180),
    )

    cursor = x
    for index, word in enumerate(words):
        width, _ = _measure(draw, word, font)
        draw.text(
            (cursor, y + 34),
            word,
            font=font,
            fill=(92, 205, 255) if index == active_index else (248, 249, 251),
            stroke_width=4,
            stroke_fill=(5, 7, 10),
        )
        cursor += width + 16


def render_frame(
    base_image: Image.Image,
    style: str,
    t: float,
    headline_text: str = HEADLINE_TEXT,
    headline_enabled: bool = True,
) -> Image.Image:
    if style not in STYLE_NAMES:
        raise ValueError(f"Unknown renderer style: {style}")

    frame = base_image.convert("RGBA").resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS,
    )
    _draw_subtitles(frame, style, t)
    if headline_enabled and t < HEADLINE_SECONDS:
        _draw_headline(frame, headline_text, t)
    _paste_logo(frame)
    _paste_source(frame, style)
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
    videos: dict[str, Path] = {}

    opening_count = max(1, int(HEADLINE_SECONDS * FPS))
    videos["opening"] = write_preview_video(
        (
            render_frame(
                base,
                "Clean Editorial",
                index / FPS,
                headline_text,
                headline_enabled,
            )
            for index in range(opening_count)
        ),
        output / "opening_headline.mp4",
    )

    frame_count = max(1, int(FULL_PREVIEW_SECONDS * FPS))
    filenames = {
        "Clean Editorial": "clean_editorial.mp4",
        "Micro Glass": "micro_glass.mp4",
        "Broadcast / Data": "broadcast_data.mp4",
    }
    for style in STYLE_NAMES:
        videos[style] = write_preview_video(
            (
                render_frame(
                    base,
                    style,
                    index / FPS,
                    headline_text,
                    headline_enabled,
                )
                for index in range(frame_count)
            ),
            output / filenames[style],
        )

    return videos


def get_logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.png"


def get_headline_font_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / "BebasNeue-Regular.ttf"
