"""Stage 06: 16:9 Widescreen Broadcast Documentary Renderer for Final-Shorts.

Renders 1920x1080 30FPS documentary video essays combining 16:9 broadcast cards,
cinematic Ken Burns photos, Act chapter title billboards, clean broadcast lower-third subtitles,
and master voice narration with adaptive sound design.
"""

from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import warnings
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1920
HEIGHT = 1080
FPS = 30

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT_TITLE = FONTS_DIR / "BarlowCondensed-Black.ttf"
FONT_BODY = FONTS_DIR / "Barlow-Regular.ttf"
FONT_BOLD = FONTS_DIR / "Oswald-Bold.ttf"


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _get_font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path.is_file():
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    return ImageFont.load_default()


def _fit_to_widescreen(image_input: bytes | bytearray | Image.Image) -> Image.Image:
    """Scales and crops an image to fit 1920x1080 perfectly."""
    if isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    elif isinstance(image_input, (bytes, bytearray)):
        with Image.open(BytesIO(bytes(image_input))) as src:
            img = src.convert("RGB")
    else:
        raise ValueError("Invalid visual image input.")

    target_ratio = WIDTH / HEIGHT
    current_ratio = img.width / img.height

    if current_ratio > target_ratio:
        crop_width = max(1, int(img.height * target_ratio))
        left = (img.width - crop_width) // 2
        img = img.crop((left, 0, left + crop_width, img.height))
    elif current_ratio < target_ratio:
        crop_height = max(1, int(img.width / target_ratio))
        top = (img.height - crop_height) // 2
        img = img.crop((0, top, img.width, top + crop_height))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _draw_act_billboard(frame: Image.Image, act_number: int, title: str, progress: float) -> Image.Image:
    """Draws a cinematic chapter introduction overlay with fade-in/fade-out."""
    # Compute opacity curve: fade in over 0.2, stay full, fade out over 0.8 to 1.0
    if progress < 0.2:
        alpha = int(255 * (progress / 0.2))
    elif progress > 0.8:
        alpha = int(255 * ((1.0 - progress) / 0.2))
    else:
        alpha = 255
    alpha = max(0, min(255, alpha))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Dark background vignette
    vignette_alpha = int(alpha * 0.72)
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=(5, 8, 15, vignette_alpha))

    # Center card box
    box_w = 1100
    box_h = 240
    box_x = (WIDTH - box_w) // 2
    box_y = (HEIGHT - box_h) // 2

    box_alpha = int(alpha * 0.85)
    draw.rounded_rectangle(
        [(box_x, box_y), (box_x + box_w, box_y + box_h)],
        radius=16,
        fill=(15, 23, 42, box_alpha),
        outline=(217, 119, 6, int(alpha * 0.9)),
        width=3,
    )

    # Act Eyebrow
    font_eyebrow = _get_font(FONT_BOLD, 30)
    eyebrow_text = f"DOCUMENTARY CHAPTER · ACT {act_number:02d}"
    draw.text((WIDTH // 2, box_y + 45), eyebrow_text, font=font_eyebrow, fill=(245, 158, 11, alpha), anchor="mm")

    # Chapter Title
    font_ch_title = _get_font(FONT_TITLE, 64)
    draw.text((WIDTH // 2, box_y + 120), title, font=font_ch_title, fill=(255, 255, 255, alpha), anchor="mm")

    # Decorative underline
    line_w = 160
    draw.line([(WIDTH // 2 - line_w // 2, box_y + 175), (WIDTH // 2 + line_w // 2, box_y + 175)], fill=(217, 119, 6, alpha), width=3)

    return Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")


def _draw_lower_third_subtitle(frame: Image.Image, text: str) -> Image.Image:
    """Renders a clean broadcast documentary lower-third subtitle."""
    if not text:
        return frame

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _get_font(FONT_BODY, 38)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Capsule coordinates
    pad_x = 24
    pad_y = 10
    pill_w = text_w + pad_x * 2
    pill_h = text_h + pad_y * 2
    pill_x = (WIDTH - pill_w) // 2
    pill_y = HEIGHT - 110

    # Draw semi-transparent pill capsule
    draw.rounded_rectangle(
        [(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
        radius=10,
        fill=(10, 15, 25, 205),
        outline=(255, 255, 255, 30),
        width=1,
    )

    # Draw subtitle text
    draw.text((WIDTH // 2, pill_y + pill_h // 2 - 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm")

    return Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")


def _apply_ken_burns(base: Image.Image, progress: float) -> Image.Image:
    """Applies a subtle, cinematic ease-in push to prevent static image monotony."""
    # Scale from 1.00 to 1.05
    scale = 1.0 + (0.05 * progress)
    scaled_w = int(WIDTH * scale)
    scaled_h = int(HEIGHT * scale)

    # Center crop back to 1920x1080
    crop_x = (scaled_w - WIDTH) // 2
    crop_y = (scaled_h - HEIGHT) // 2

    # Fast resize and crop
    scaled = base.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)
    return scaled.crop((crop_x, crop_y, crop_x + WIDTH, crop_y + HEIGHT))


class LongformRenderer:
    """Assembles and renders complete 16:9 broadcast documentaries."""

    @classmethod
    def render_video(
        cls,
        approved_script: dict[str, Any],
        approved_audio: dict[str, Any],
        approved_visuals: dict[str, Any],
        subtitle_data: dict[str, Any],
        output_path: Path | str,
        background_music_path: Path | str | None = None,
        max_duration_seconds: float | None = None,
    ) -> Path:
        if not _ffmpeg_available():
            raise RuntimeError("FFmpeg is required to render Long-form videos.")

        audio_scenes = approved_audio.get("scenes") or []
        if not audio_scenes:
            raise ValueError("Long-form Audio has no rendered scenes.")

        master_audio_path = Path(approved_audio.get("master_path", ""))
        if not master_audio_path.is_file():
            raise ValueError("Long-form master audio track is missing.")

        visual_scenes = approved_visuals.get("scenes_visuals") or []
        cues = subtitle_data.get("cues") or []
        act_billboards = subtitle_data.get("act_billboards") or []

        total_audio_duration = float(approved_audio.get("total_duration", 0))
        if max_duration_seconds:
            total_duration = min(total_audio_duration, float(max_duration_seconds))
        else:
            total_duration = total_audio_duration

        if total_duration <= 0:
            raise ValueError("Invalid total video duration.")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Map scene number to prepared visual base image
        scene_visual_map: dict[int, dict[str, Any]] = {}
        for s in visual_scenes:
            scene_visual_map[int(s.get("scene_number", 1))] = s

        # Build prepared base images
        prepared_bases: list[dict[str, Any]] = []
        for a_scene in audio_scenes:
            sc_num = int(a_scene.get("scene", 1))
            sc_dur = float(a_scene.get("duration", 5.0))
            sc_start = float(a_scene.get("start_seconds", 0.0))
            vis_info = scene_visual_map.get(sc_num, {})

            img_bytes = vis_info.get("image_bytes")
            if img_bytes:
                base_img = _fit_to_widescreen(img_bytes)
            else:
                # Fallback neutral studio backdrop
                base_img = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))

            prepared_bases.append({
                "scene": sc_num,
                "act": a_scene.get("act", 1),
                "start": sc_start,
                "duration": sc_dur,
                "base_image": base_img,
            })

        # Frame Generator
        def frame_generator():
            total_frames = int(math.ceil(total_duration * FPS))
            scene_index = 0
            cue_index = 0
            billboard_index = 0
            for frame_idx in range(total_frames):
                current_time = frame_idx / FPS

                # Scene starts are chronological. Advance a cursor rather than
                # scanning the full scene list for every frame of an 8-minute render.
                # Do not advance into the next scene during a genuine narration
                # gap (e.g. an 0.8s act transition). Hold the prior visual until
                # the next scene's actual audio start time.
                while (
                    scene_index < len(prepared_bases) - 1
                    and current_time >= prepared_bases[scene_index + 1]["start"]
                ):
                    scene_index += 1

                active_scene = prepared_bases[scene_index]

                sc_start = active_scene["start"]
                sc_dur = max(0.1, active_scene["duration"])
                sc_prog = min(1.0, max(0.0, (current_time - sc_start) / sc_dur))

                base = active_scene["base_image"]
                # Apply the existing subtle Ken Burns motion to each scene visual.
                frame = _apply_ken_burns(base, sc_prog)

                # Billboards and subtitles are in timeline order. Advance cursors
                # monotonically rather than scanning every cue on every video frame.
                while billboard_index < len(act_billboards):
                    bb = act_billboards[billboard_index]
                    b_start = float(bb.get("start_time", 0))
                    b_dur = float(bb.get("duration", 3.5))
                    if current_time < b_start + b_dur:
                        break
                    billboard_index += 1
                if billboard_index < len(act_billboards):
                    bb = act_billboards[billboard_index]
                    b_start = float(bb.get("start_time", 0))
                    b_dur = float(bb.get("duration", 3.5))
                    if b_start <= current_time < b_start + b_dur:
                        b_prog = (current_time - b_start) / b_dur
                        frame = _draw_act_billboard(frame, int(bb["act_number"]), str(bb["title"]), b_prog)

                while cue_index < len(cues) and current_time > float(cues[cue_index].get("end", 0)):
                    cue_index += 1
                if cue_index < len(cues):
                    cue = cues[cue_index]
                    c_start = float(cue.get("start", 0))
                    c_end = float(cue.get("end", 0))
                    if c_start <= current_time <= c_end:
                        frame = _draw_lower_third_subtitle(frame, str(cue.get("text", "")))

                yield frame

        # Allocate the temporary file only after input preparation succeeds.
        # This is unique per render and is cleaned for every FFmpeg/mux outcome.
        with tempfile.NamedTemporaryFile(
            prefix=f"{out_file.stem}.",
            suffix=".silent.mp4",
            dir=out_file.parent,
            delete=False,
        ) as temp_handle:
            temp_silent = Path(temp_handle.name)

        # Pipe frames into FFmpeg for rawvideo video stream
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(temp_silent),
        ]
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert proc.stdin is not None

            try:
                for fr in frame_generator():
                    raw = fr.tobytes() if fr.mode == "RGB" else fr.convert("RGB").tobytes()
                    proc.stdin.write(raw)
                proc.stdin.close()
            except BrokenPipeError as exc:
                raise RuntimeError("FFmpeg pipe broke while generating video stream.") from exc

            err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"FFmpeg failed to create silent video: {err.strip()}")

            # Mux master audio track with silent video.
            cls._mux_audio_track(
                temp_silent=temp_silent,
                master_audio=master_audio_path,
                output_file=out_file,
                background_music=Path(background_music_path) if background_music_path else None,
            )
            return out_file
        finally:
            # Any failure during frame generation or muxing must release the
            # intermediate file. Never let cleanup mask the original render error.
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass
            try:
                temp_silent.unlink(missing_ok=True)
            except OSError as exc:
                warnings.warn(
                    f"Long-form render finished or failed, but temporary video cleanup failed for {temp_silent}: {exc}",
                    RuntimeWarning,
                )

    @classmethod
    def _mux_audio_track(
        cls,
        temp_silent: Path,
        master_audio: Path,
        output_file: Path,
        background_music: Path | None = None,
    ) -> None:
        if background_music and background_music.is_file():
            # Mux voiceover and background score with sidechain ducking (-18dB under speech)
            filter_complex = (
                "[1:a]volume=1.0[voice];"
                "[2:a]volume=0.22,aloop=loop=-1:size=2e+09[bg];"
                "[bg][voice]sidechaincompress=threshold=0.08:ratio=6:attack=100:release=400[ducked];"
                "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(temp_silent),
                "-i", str(master_audio),
                "-i", str(background_music),
                "-filter_complex", filter_complex,
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(output_file),
            ]
        else:
            # Clean studio master loudnorm
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(temp_silent),
                "-i", str(master_audio),
                "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]",
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(output_file),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed to mux audio: {res.stderr.strip()}")


__all__ = ["LongformRenderer", "WIDTH", "HEIGHT", "FPS"]
