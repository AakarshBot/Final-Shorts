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


def test_top5_preview_keeps_the_photograph_clean_behind_editorial_text():
    background = (236, 236, 236)
    preview = renderer.build_top5_card_preview(
        _solid_png((1080, 1920), background),
        "India confirm the latest squad change",
        "The board confirmed the move. The decision changes the lineup.",
        story_number=1,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((20, 20)) == background
    assert image.getpixel((20, 700)) == background
    assert image.getpixel((20, 1800)) == background


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


def test_top5_production_accepts_six_slides_without_subtitles(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene.mp3"
    audio_file.write_bytes(b"audio")
    image_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()

    script = {
        "schema": "final-shorts.top5-script.v1",
        "approved_for_audio": True,
        "slides": [
            {
                "slide_number": number,
                "story_index": number - 1,
                "headline": (
                    "Top 5 Cricket News Today"
                    if number == 1
                    else f"India confirm the selected cricket development number {number}"
                ),
                "body": (
                    "India confirmed a squad change while two other major cricket developments also made the roundup."
                    if number == 1
                    else "The board confirmed the move. The decision changes the lineup."
                ),
            }
            for number in range(1, 7)
        ],
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [
            {
                "scene": number,
                "duration": 0.5,
                "path": str(audio_file),
            }
            for number in range(1, 7)
        ],
    }
    visuals = [
        {
            "bytes": image_bytes,
            "source": "Commons",
            "top5_card": {
                "headline": slide["headline"],
                "body": slide["body"],
                "story_number": 0 if number == 1 else number - 1,
                "total_stories": 5,
            },
        }
        for number, slide in enumerate(script["slides"], 1)
    ]

    seen = []
    monkeypatch.setattr(
        renderer,
        "_draw_top5_editorial_card",
        lambda base, card: (seen.append(card) or base),
    )
    monkeypatch.setattr(
        renderer,
        "write_preview_video",
        lambda frames, path: (
            list(frames),
            path.write_bytes(b"silent"),
            path,
        )[-1],
    )
    monkeypatch.setattr(
        renderer,
        "_mux_audio",
        lambda silent, scenes, output: (output.write_bytes(b"final") or output),
    )

    output = tmp_path / "top5.mp4"
    renderer.render_production_video(script, audio, None, visuals, output)
    assert len(seen) == 6
    assert [card["story_number"] for card in seen] == [0, 1, 2, 3, 4, 5]


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
    assert short_lines
    assert long_lines


def test_top5_editorial_headline_has_no_arbitrary_line_cap():
    fonts, display, lines = renderer._fit_top5_editorial_headline(
        "India announce a major selection change after the latest international cricket result and confirm another late squad decision",
    )
    assert display
    assert len(lines) > 2
    assert fonts[0].size >= renderer.TOP5_EDITORIAL_HEADLINE_MIN_SIZE


def test_top5_body_layout_is_dynamic_without_line_cap():
    short_body_font, short_paragraphs = renderer._fit_top5_editorial_body(
        "The board confirmed the move. The decision changes the lineup.",
        "english",
    )
    long_body_font, long_paragraphs = renderer._fit_top5_editorial_body(
        "The board confirmed the move after reviewing the latest result and the selection options. "
        "The decision changes the lineup ahead of the next series and follows the latest update from officials. "
        "Officials also confirmed the timing of the next review and the squad decision that follows it.",
        "english",
    )

    assert short_body_font.size >= long_body_font.size
    assert short_paragraphs
    assert long_paragraphs


def test_top5_body_is_two_editorial_sentences():
    font, paragraphs = renderer._fit_top5_body(
        "The board confirmed the move after the latest result. The decision changes the lineup for the next series.",
        "english",
    )

    assert font is not None
    assert len(paragraphs) == 2
    assert all(paragraph for paragraph in paragraphs)


def test_top5_opener_accepts_body_copy():
    preview = renderer.build_top5_card_preview(
        _solid_png((900, 1600), "white"),
        "Top 5 Cricket News Today",
        "India confirmed a squad change while two other major cricket developments also made the day's biggest stories.",
        story_number=0,
    )
    image = Image.open(BytesIO(preview))

    assert image.size == (1080, 1920)
    _, _, lines = renderer._fit_top5_editorial_headline(
        "Top 5 Cricket News Today",
    )
    assert lines
    body_font, body = renderer._fit_top5_editorial_body(
        "India confirmed a squad change while two other major cricket developments also made the day's biggest stories.",
        "english",
    )
    assert body_font is not None
    assert body


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


def test_top5_editorial_card_accepts_long_headline_and_body():
    preview = renderer.build_top5_card_preview(
        _solid_png((1080, 1920), (28, 42, 64)),
        "India announce a major selection change after the latest international cricket result and confirm another late squad decision",
        "The board confirmed the move after reviewing the latest result and the selection options. The decision changes the lineup ahead of the next series and follows the latest update from officials. Officials also confirmed the timing of the next review and the squad decision that follows it.",
        story_number=1,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")
    assert image.size == (1080, 1920)
