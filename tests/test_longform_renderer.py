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


def test_longform_render_uses_unique_temp_and_cleans_it_when_frame_generation_fails(tmp_path, monkeypatch):
    import longform_renderer

    master_audio = tmp_path / "master.wav"
    master_audio.write_bytes(b"test-audio-placeholder")
    output = tmp_path / "documentary.mp4"
    captured = {}

    class FakePipe:
        def write(self, _data):
            return None

        def close(self):
            return None

    class FakeStderr:
        def read(self):
            return b""

    class FakeProcess:
        def __init__(self):
            self.stdin = FakePipe()
            self.stderr = FakeStderr()
            self.killed = False

        def poll(self):
            return None if not self.killed else -9

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            return -9

    process = FakeProcess()

    def fake_popen(command, **_kwargs):
        captured["temp_path"] = Path(command[-1])
        return process

    monkeypatch.setattr(longform_renderer, "_ffmpeg_available", lambda: True)
    monkeypatch.setattr(longform_renderer.subprocess, "Popen", fake_popen)

    def fail_motion(*_args, **_kwargs):
        raise RuntimeError("injected frame failure")

    monkeypatch.setattr(longform_renderer, "_apply_ken_burns", fail_motion)

    with pytest.raises(RuntimeError, match="injected frame failure"):
        LongformRenderer.render_video(
            approved_script=sample_script(),
            approved_audio={
                "master_path": str(master_audio),
                "total_duration": 1.0,
                "scenes": [{"scene": 1, "act": 1, "start_seconds": 0.0, "duration": 1.0}],
            },
            approved_visuals={"scenes_visuals": [{"scene_number": 1, "image_bytes": _dummy_image_bytes()}]},
            subtitle_data={"cues": [], "act_billboards": []},
            output_path=output,
        )

    temp_path = captured["temp_path"]
    assert temp_path != output.with_name(f"{output.stem}_silent.mp4")
    assert ".silent.mp4" in temp_path.name
    assert not temp_path.exists()
    assert process.killed



def test_longform_renderer_holds_previous_visual_until_next_audio_scene_start(monkeypatch, tmp_path):
    import longform_renderer

    # Use tiny frames/few frames so this tests timeline selection without FFmpeg cost.
    monkeypatch.setattr(longform_renderer, "WIDTH", 32)
    monkeypatch.setattr(longform_renderer, "HEIGHT", 18)
    monkeypatch.setattr(longform_renderer, "FPS", 2)
    monkeypatch.setattr(longform_renderer, "_ffmpeg_available", lambda: True)

    def image_bytes(color):
        buffer = BytesIO()
        Image.new("RGB", (64, 36), color).save(buffer, format="PNG")
        return buffer.getvalue()

    master_audio = tmp_path / "master.wav"
    master_audio.write_bytes(b"mock master audio")
    output = tmp_path / "longform-gap-test.mp4"
    frame_colors = []

    def motion(base, progress):
        frame_colors.append((base.getpixel((0, 0)), progress))
        return base

    monkeypatch.setattr(longform_renderer, "_apply_ken_burns", motion)

    class FakePipe:
        def write(self, _data):
            return None

        def close(self):
            return None

    class FakeStderr:
        def read(self):
            return b""

    class FakeProcess:
        def __init__(self):
            self.stdin = FakePipe()
            self.stderr = FakeStderr()

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(longform_renderer.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    monkeypatch.setattr(
        LongformRenderer,
        "_mux_audio_track",
        staticmethod(lambda **_kwargs: output.write_bytes(b"muxed video")),
    )

    visuals = {
        "scenes_visuals": [
            {"scene_number": 1, "image_bytes": image_bytes((200, 10, 10))},
            {"scene_number": 2, "image_bytes": image_bytes((10, 10, 200))},
        ]
    }
    audio = {
        "master_path": str(master_audio),
        "total_duration": 1.8,
        "scenes": [
            {"scene": 1, "act": 1, "start_seconds": 0.0, "duration": 0.25},
            {"scene": 2, "act": 2, "start_seconds": 1.0, "duration": 0.8},
        ],
    }

    rendered = LongformRenderer.render_video(
        approved_script=sample_script(),
        approved_audio=audio,
        approved_visuals=visuals,
        subtitle_data={"cues": [], "act_billboards": []},
        output_path=output,
    )

    assert rendered.is_file()
    assert [color for color, _progress in frame_colors] == [
        (200, 10, 10),
        (200, 10, 10),
        (10, 10, 200),
        (10, 10, 200),
    ]
    # At t=0.5s, the prior scene holds during the 0.75s act gap.
    assert frame_colors[1][1] == 1.0
    assert frame_colors[2][1] == 0.0
