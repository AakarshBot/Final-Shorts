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
        "The decision follows a recent development. The board confirmed the change.",
        story_number=1,
        source_label="Test Sports Desk",
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((12, 180)) == (12, 34, 56)


def test_top5_preview_does_not_add_a_readability_panel():
    background = (40, 70, 90)
    preview = renderer.build_top5_card_preview(
        _solid_png((1080, 1920), background),
        "India confirm the latest squad change",
        "The board confirmed the move. The decision changes the lineup.",
        story_number=1,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.size == (1080, 1920)
    assert image.getpixel((20, 20)) == background
    assert image.getpixel((20, 1800)) == background


def test_top5_layout_fills_to_the_lower_safe_boundary():
    layout = renderer._top5_editorial_layout(
        "India make a major selection change",
        "The board confirmed the move. The decision changes the lineup.",
        "english",
        1,
    )

    assert layout["x"] == renderer.TOP5_EDITORIAL_MARGIN_X
    assert layout["y"] >= renderer.TOP5_EDITORIAL_SAFE_TOP
    assert layout["y"] + layout["total_height"] == renderer.HEIGHT - renderer.TOP5_EDITORIAL_SAFE_BOTTOM


def test_top5_opener_uses_the_same_dynamic_safe_boundary():
    layout = renderer._top5_editorial_layout(
        "Top 5 Cricket News Today",
        "",
        "english",
        0,
    )

    assert layout["y"] >= renderer.TOP5_EDITORIAL_SAFE_TOP
    assert layout["y"] + layout["total_height"] == renderer.HEIGHT - renderer.TOP5_EDITORIAL_SAFE_BOTTOM


def test_top5_headline_size_adapts_to_copy():
    short = renderer._top5_editorial_layout(
        "India name a major change",
        "",
        "english",
        1,
    )
    long = renderer._top5_editorial_layout(
        "India reshuffles the squad after a late selection change before the series",
        "",
        "english",
        1,
    )

    assert short["headline_fonts"][0].size >= long["headline_fonts"][0].size
    assert long["headline_lines"]
    assert short["headline_lines"]


def test_top5_body_preserves_all_copy_without_sentence_cap():
    body = (
        "The board confirmed the move after the latest result. "
        "The decision changes the lineup for the next series. "
        "Officials also confirmed the timing of the next review."
    )
    layout = renderer._top5_editorial_layout(
        "Selection change",
        body,
        "english",
        1,
    )

    rendered_words = " ".join(
        word
        for line in layout["body_lines"]
        for word in line
    )
    assert "Officials" in rendered_words
    assert "review." in rendered_words
    assert renderer.TOP5_EDITORIAL_BODY_MIN_SIZE <= layout["body_font"].size <= renderer.TOP5_EDITORIAL_BODY_MAX_SIZE


def test_top5_card_uses_a_subtle_letter_fade(monkeypatch):
    calls = []
    original = renderer.ImageFilter.GaussianBlur

    def gaussian_blur(radius):
        calls.append(radius)
        return original(radius)

    monkeypatch.setattr(renderer.ImageFilter, "GaussianBlur", gaussian_blur)
    renderer.build_top5_card_preview(
        _solid_png((1080, 1920), (30, 30, 30)),
        "India confirm the latest squad change",
        "The board confirmed the move.",
        story_number=1,
    )

    assert renderer.TOP5_EDITORIAL_TEXT_FADE_BLUR == 5
    assert renderer.TOP5_EDITORIAL_TEXT_FADE_BLUR in calls
    assert renderer.TOP5_EDITORIAL_TEXT_FADE_ALPHA == 60


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


def test_top5_opener_builds_without_body():
    preview = renderer.build_top5_card_preview(
        _solid_png((900, 1600), "white"),
        "Top 5 Cricket News Today",
        story_number=0,
    )
    image = Image.open(BytesIO(preview))
    assert image.size == (1080, 1920)
