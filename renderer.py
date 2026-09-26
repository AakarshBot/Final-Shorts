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
FINAL_STYLE_NAME = "Editorial Highlight"

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

ACCENT = (255, 205, 66)
BRAND_BLUE = (35, 105, 255)
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
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
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
        root / "Montserrat-ExtraBold.ttf",
        root / "Montserrat-Bold.ttf",
    )


def headline_font(size: int = HEADLINE_MAX_SIZE, language: str = "english"):
    return _font(_font_candidates("headline", language), size)


def subtitle_font(size: int = SUBTITLE_MAX_SIZE, language: str = "english"):
    return _font(_font_candidates("subtitle", language), size)


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
    font,
) -> list[list[str]]:
    words = text.split()
    if not words:
        return []

    measurements = [
        _measure(draw, word, font, HEADLINE_STROKE_WIDTH)[0]
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


def _fit_headline_font(
    text: str,
    language: str = "english",
):
    clean = " ".join(str(text or "").upper().split()) or HEADLINE_TEXT
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    for size in range(HEADLINE_MAX_SIZE, HEADLINE_MIN_SIZE - 1, -1):
        font = headline_font(size, language)
        try:
            lines = _headline_lines(clean, probe, font)
        except ValueError:
            continue
        return font, clean, lines

    raise ValueError("Headline is too long to fit in two lines.")
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


def _draw_headline(base: Image.Image, text: str, t: float, language: str) -> None:
    font, clean, lines = _fit_headline_font(text, language)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    line_boxes = [
        draw.textbbox(
            (0, 0),
            " ".join(line),
            font=font,
            stroke_width=HEADLINE_STROKE_WIDTH,
        )
        for line in lines
    ]
    line_widths = [box[2] - box[0] for box in line_boxes]
    line_heights = [box[3] - box[1] for box in line_boxes]

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
        box = line_boxes[row]
        draw.text(
            (line_x - box[0], cursor_y - box[1]),
            line_text,
            font=font,
            fill=WHITE,
            stroke_width=HEADLINE_STROKE_WIDTH,
            stroke_fill=DARK,
        )
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
        font = subtitle_font(size, language)
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
    y = SUBTITLE_Y - total_height // 2

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
            text = str(word["text"])
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
        prepared_visuals.append(
            _fit_visual_to_frame(visual.get("bytes"))
        )

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
            yield render_frame(
                prepared_visuals[scene_index],
                t,
                subtitle_data,
                headline_text or HEADLINE_TEXT,
                True,
                source_label,
            )

    try:
        write_preview_video(frames(), silent_video)
        return _mux_audio(silent_video, audio_scenes, output)
    finally:
        try:
            silent_video.unlink()
        except FileNotFoundError:
            pass

def get_logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.png"


def get_headline_font_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / "Oswald-Bold.ttf"
