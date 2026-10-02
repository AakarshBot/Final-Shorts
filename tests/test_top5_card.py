from io import BytesIO

from PIL import Image

import renderer


def test_top5_card_preview_is_vertical_and_contains_card():
    source = BytesIO()
    Image.new("RGB", (1600, 900), "white").save(source, format="JPEG")
    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India name a major change today",
        "The decision follows a recent development. More detail is included here for the visual-only summary.",
        story_number=1,
        source_label="Test Sports Desk",
    )
    image = Image.open(BytesIO(preview))
    assert image.size == (1080, 1920)


def test_top5_card_preview_handles_long_story_headline():
    source = BytesIO()
    Image.new("RGB", (1600, 900), "white").save(source, format="JPEG")
    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India reshuffles the squad after a late selection change before the next major series",
        "The move changes the lineup and follows the latest selection update.",
        story_number=3,
    )
    assert Image.open(BytesIO(preview)).size == (1080, 1920)


def test_top5_production_visual_uses_card_payload(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")

    visual_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual_buffer, format="PNG")

    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A factual opening sentence."}],
        "headline": "Gill Injury Scare",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    visuals = [{
        "bytes": visual_buffer.getvalue(),
        "top5_card": {
            "headline": "A major cricket development",
            "body": "A concise factual summary sits below the spoken headline.",
            "story_number": 2,
            "total_stories": 5,
        },
    }]

    seen = []

    def fake_frame(*args, **kwargs):
        seen.append(kwargs.get("top5_card"))
        return args[0]

    def fake_preview(frames, path):
        next(iter(frames))
        path.write_bytes(b"silent")
        return path

    def fake_mux(silent_video, audio_scenes, output):
        output.write_bytes(b"final")
        return output

    monkeypatch.setattr(renderer, "render_frame", fake_frame)
    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    output = tmp_path / "top5.mp4"
    renderer.render_production_video(
        script,
        audio,
        renderer.PREVIEW_SUBTITLE_DATA,
        visuals,
        output,
    )
    assert seen and seen[0]["story_number"] == 2
