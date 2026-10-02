from io import BytesIO

from PIL import Image

import renderer


def test_top5_preview_is_vertical_and_uses_full_width_image():
    source = BytesIO()
    Image.new("RGB", (1600, 900), (12, 34, 56)).save(source, format="JPEG")

    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India name a major change today",
        "The decision follows a recent development. The board confirmed the change after reviewing the latest result.",
        story_number=1,
        source_label="Test Sports Desk",
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((60, 400)) == (12, 34, 56)
    assert image.getpixel((60, 1000)) == (246, 247, 249)


def test_top5_preview_handles_long_story_headline():
    source = BytesIO()
    Image.new("RGB", (1600, 900), "white").save(source, format="JPEG")

    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India reshuffles the squad after a late selection change",
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


def test_top5_headline_can_use_two_lines_and_shrinks_when_needed():
    short_font, short_lines = renderer._fit_top5_headline(
        "India make a major change",
    )
    long_font, long_lines = renderer._fit_top5_headline(
        "India reshuffles the squad after a late selection change before the next series",
    )

    assert short_font.size >= long_font.size
    assert len(short_lines) <= 2
    assert len(long_lines) <= 2


def test_top5_body_layout_is_dynamic():
    short_body_font, short_paragraphs = renderer._fit_top5_body(
        "The board confirmed the move. The decision changes the lineup.",
        "english",
        max_height=650,
    )
    long_body_font, long_paragraphs = renderer._fit_top5_body(
        "The board confirmed the move after reviewing the latest result and the selection options. "
        "The decision changes the lineup ahead of the next series and follows the latest update from officials.",
        "english",
        max_height=650,
    )

    assert short_body_font.size >= long_body_font.size
    assert sum(len(lines) for lines in long_paragraphs) >= sum(
        len(lines) for lines in short_paragraphs
    )


def test_top5_body_is_read_as_two_editorial_paragraphs():
    font, paragraphs = renderer._fit_top5_body(
        "The board confirmed the move after the latest result. The decision changes the lineup for the next series.",
        "english",
    )

    assert font is not None
    assert len(paragraphs) == 2
    assert all(paragraph for paragraph in paragraphs)


def test_top5_opener_has_no_body_copy():
    source = BytesIO()
    Image.new("RGB", (900, 1600), "white").save(source, format="JPEG")

    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "Five cricket stories shaping today",
        story_number=0,
    )
    image = Image.open(BytesIO(preview))

    assert image.size == (1080, 1920)
    _, lines = renderer._fit_top5_headline(
        "Five cricket stories shaping today",
    )
    assert len(lines) <= 2
    assert renderer._fit_top5_body("", "english") == (None, [])
