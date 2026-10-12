from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image

from longform_renderer import (
    LongformRenderer,
    WIDTH,
    HEIGHT,
    _fit_to_widescreen,
    _draw_act_billboard,
    _draw_lower_third_subtitle,
    _ffmpeg_available,
)


def _dummy_image_bytes():
    img = Image.new("RGB", (800, 600), (30, 40, 60))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def sample_script():
    return {
        "title": "BCCI Names Bumrah Captain",
        "acts": [
            {"act_number": 1, "chapter_title": "The Adelaide Dilemma"},
        ],
        "scenes": [
            {"scene_number": 1, "act_number": 1, "voiceover": "Jasprit Bumrah takes the helm in Adelaide."},
        ],
    }


def sample_audio(tmp_path):
    wav_path = tmp_path / "test_master.wav"
    # Create 1 second silent WAV file using FFmpeg or minimal WAV header
    import subprocess
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=f=440:r=24000:d=1.0",
        str(wav_path)
    ], check=True)

    return {
        "master_path": str(wav_path),
        "total_duration": 1.0,
        "scenes": [
            {
                "scene": 1,
                "act": 1,
                "start_seconds": 0.0,
                "duration": 1.0,
                "timings": [{"word": "Jasprit", "start": 0.0, "end": 0.5}],
            }
        ],
    }


def sample_visuals():
    return {
        "scenes_visuals": [
            {
                "scene_number": 1,
                "act_number": 1,
                "visual_type": "photo_kenburns",
                "image_bytes": _dummy_image_bytes(),
            }
        ]
    }


def sample_subtitles():
    return {
        "cues": [
            {"cue_index": 1, "start": 0.0, "end": 0.8, "text": "Jasprit Bumrah takes the helm."}
        ],
        "act_billboards": [
            {"act_number": 1, "title": "THE ADELAIDE DILEMMA", "start_time": 0.0, "duration": 0.5}
        ],
    }


def test_fit_to_widescreen():
    raw = _dummy_image_bytes()
    fitted = _fit_to_widescreen(raw)
    assert fitted.size == (WIDTH, HEIGHT)


def test_draw_act_billboard():
    base = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 20))
    result = _draw_act_billboard(base, 1, "THE ADELAIDE DILEMMA", 0.5)
    assert result.size == (WIDTH, HEIGHT)


def test_draw_lower_third_subtitle():
    base = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 20))
    result = _draw_lower_third_subtitle(base, "Broadcast lower-third test phrase")
    assert result.size == (WIDTH, HEIGHT)


@pytest.mark.skipif(not _ffmpeg_available(), reason="FFmpeg required")
def test_longform_render_short_clip(tmp_path):
    aud = sample_audio(tmp_path)
    out_video = tmp_path / "documentary_test.mp4"

    rendered = LongformRenderer.render_video(
        approved_script=sample_script(),
        approved_audio=aud,
        approved_visuals=sample_visuals(),
        subtitle_data=sample_subtitles(),
        output_path=out_video,
        max_duration_seconds=0.5,
    )

    assert rendered.is_file()
    assert rendered.stat().st_size > 1000
