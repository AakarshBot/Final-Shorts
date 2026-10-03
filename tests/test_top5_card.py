from io import BytesIO

from PIL import Image

import renderer


TEST_SUBTITLE_DATA = {
    "schema": "final-shorts.subtitles.v1",
    "language": "english",
    "cues": [
        {
            "start": 0.0,
            "end": 0.5,
            "words": [{"text": "A", "start": 0.0, "end": 0.2}],
        }
    ],
}


def _solid_png(size, color):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_top5_preview_is_vertical_and_preserves_full_9x16_crop():
    preview = renderer.build_top5_card_preview(
        _solid_png((1080, 1920), (12, 34, 56)),
        "India name a major change today",
        "The decision follows a recent development. The board confirmed the change after reviewing the latest result.",
        story_number=1,
        source_label="Test Sports Desk",
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((12, 180)) == (12, 34, 56)


def test_top5_preview_keeps_a_9x16_crop_instead_of_recropping_it():
    source = Image.new("RGB", (900, 1600), (80, 20, 120))
    preview = renderer.build_top5_card_preview(
        source,
        "Five cricket stories shaping today",
        story_number=0,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    corner = image.getpixel((12, 300))
    assert corner != (249, 250, 252)


def test_top5_preview_uses_text_only_readability_treatment_not_a_full_width_panel():
    background = (236, 236, 236)
    preview = renderer.build_top5_card_preview(
        _solid_png((1080, 1920), background),
        "India confirm the latest squad change",
        "The board confirmed the move. The decision changes the lineup.",
        story_number=1,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((20, 1180)) == background
    assert image.getpixel((1050, 1180)) == background
    assert image.getpixel((540, 600)) == background

    text_region = image.crop((72, 500, 1008, 1640))
    changed = sum(
        1
        for pixel in text_region.getdata()
        if pixel != background
    )
    assert changed > 1_000
    assert changed < text_region.width * text_region.height // 3


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

    def fake_card(*args, **kwargs):
        card = args[1] if len(args) > 1 else kwargs.get("card")
        seen.append(card)
        return args[0] if args else Image.new("RGBA", (1080, 1920))

    def fake_preview(frames, path):
        next(iter(frames))
        path.write_bytes(b"silent")
        return path

    def fake_mux(silent_video, audio_scenes, output):
        output.write_bytes(b"final")
        return output

    monkeypatch.setattr(renderer, "_draw_top5_editorial_card", fake_card)
    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    output = tmp_path / "top5.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        visuals,
        output,
    )
    assert len(seen) == 1
    assert seen[0]["story_number"] == 2


def test_top5_headline_layout_is_dynamic():
    short_fonts, short_display, short_lines = renderer._fit_top5_editorial_headline(
        "India make a major change",
    )
    long_fonts, long_display, long_lines = renderer._fit_top5_editorial_headline(
        "India reshuffles squad after a late selection change",
    )

    assert short_display == "INDIA MAKE A MAJOR CHANGE"
    assert long_display == "INDIA RESHUFFLES SQUAD AFTER A LATE SELECTION CHANGE"

    assert short_fonts[0].size >= long_fonts[0].size
    assert len(short_lines) <= 2
    assert len(long_lines) <= 2


def test_top5_body_layout_is_dynamic():
    short_body_font, short_paragraphs = renderer._fit_top5_editorial_body(
        "The board confirmed the move. The decision changes the lineup.",
        "english",
    )
    long_body_font, long_paragraphs = renderer._fit_top5_editorial_body(
        "The board confirmed the move after reviewing the latest result and the selection options. "
        "The decision changes the lineup ahead of the next series and follows the latest update from officials.",
        "english",
    )

    assert short_body_font.size >= long_body_font.size
    assert sum(len(lines) for lines in long_paragraphs) >= sum(
        len(lines) for lines in short_paragraphs
    )


def test_top5_body_is_two_editorial_sentences():
    font, paragraphs = renderer._fit_top5_body(
        "The board confirmed the move after the latest result. The decision changes the lineup for the next series.",
        "english",
    )

    assert font is not None
    assert len(paragraphs) == 2
    assert all(paragraph for paragraph in paragraphs)


def test_top5_opener_has_no_body_copy():
    preview = renderer.build_top5_card_preview(
        _solid_png((900, 1600), "white"),
        "Five cricket stories shaping today",
        story_number=0,
    )
    image = Image.open(BytesIO(preview))

    assert image.size == (1080, 1920)
    _, _, lines = renderer._fit_top5_editorial_headline(
        "Five cricket stories shaping today",
    )
    assert len(lines) <= 2
    assert renderer._fit_top5_body("", "english") == (None, [])


def test_top5_text_geometry_respects_bottom_safe_boundary():
    headline_font, headline_lines = renderer._fit_top5_headline(
        "India confirm the latest squad change",
    )
    body_font, body = renderer._fit_top5_body(
        "The board confirmed the move. The decision changes the lineup.",
        "english",
    )
    headline_height, body_height = renderer._top5_text_metrics(
        headline_font,
        headline_lines,
        body_font,
        body,
    )

    content_top, content_bottom, content_height = renderer._top5_text_geometry(
        headline_height,
        body_height,
        True,
    )

    assert content_top < content_bottom
    assert content_height == content_bottom - content_top
    assert content_bottom <= renderer.HEIGHT - renderer.TOP5_TEXT_SAFE_BOTTOM
