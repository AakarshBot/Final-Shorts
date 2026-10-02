from io import BytesIO

from PIL import Image

import renderer


def test_top5_card_preview_is_vertical_and_contains_card():
    source = BytesIO()
    Image.new("RGB", (1600, 900), "white").save(source, format="JPEG")
    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India name a major change today",
        "The decision follows a recent development. The board confirmed the change after reviewing the latest result.",
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


def test_top5_headline_is_one_line():
    font, lines = renderer._fit_top5_headline(
        "India reshuffles the squad after the latest selection change"
    )
    assert len(lines) == 1
    assert font.size < renderer.TOP5_HEADLINE_MAX_SIZE


def test_top5_card_uses_separate_image_and_body_zones():
    source = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(source, format="PNG")

    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "India confirm the latest squad change",
        "The board confirmed the move after reviewing the latest result. "
        "The decision changes the lineup ahead of the upcoming series.",
        story_number=2,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.getpixel((60, 500)) == (255, 255, 255)
    bottom = image.getpixel((60, 1500))
    assert bottom[0] < 80 and bottom[1] < 80 and bottom[2] < 80


def test_top5_layout_is_driven_by_text_length():
    short_headline_font, short_headline_lines = renderer._fit_top5_headline(
        "India make a major change",
    )
    long_headline_font, long_headline_lines = renderer._fit_top5_headline(
        "India reshuffles the squad after a late selection change before the next major series",
    )
    short_body_font, short_body_lines = renderer._fit_top5_body(
        "The decision follows the latest selection update.",
        "english",
    )
    long_body_font, long_body_lines = renderer._fit_top5_body(
        "The move changes the lineup and follows the latest selection update. "
        "Officials said the decision was made after reviewing the latest developments "
        "and the expected requirements for the next series.",
        "english",
    )

    assert short_headline_font.size >= long_headline_font.size
    assert len(short_headline_lines) == len(long_headline_lines) == 1
    assert short_body_font.size >= long_body_font.size
    assert len(long_body_lines) >= len(short_body_lines)


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
    _, lines = renderer._fit_top5_headline("Five cricket stories shaping today")
    assert len(lines) == 1
    assert renderer._fit_top5_body("", "english") == (None, [])


def test_top5_interaction_animation_is_supported():
    source = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(source, format="PNG")
    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "A major cricket development",
        "The board confirmed the move after reviewing the latest result. "
        "The decision changes the lineup for the next series.",
        story_number=2,
        interaction_animation="heart",
    )
    assert Image.open(BytesIO(preview)).size == (1080, 1920)


def test_top5_bottom_panel_is_opaque_card_zone():
    source = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(source, format="PNG")

    preview = renderer.build_top5_card_preview(
        source.getvalue(),
        "A major cricket development",
        "The board confirmed the move after reviewing the latest result. The decision changes the lineup for the next series.",
        story_number=2,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    top_pixel = image.getpixel((20, 500))
    lower_pixel = image.getpixel((20, 1500))

    assert top_pixel == (255, 255, 255)
    assert lower_pixel[0] < 80
    assert lower_pixel[1] < 80
    assert lower_pixel[2] < 80
