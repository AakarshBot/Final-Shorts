from io import BytesIO

from PIL import Image, ImageDraw

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


def test_top5_layout_chooses_quiet_side_of_the_photo():
    image = Image.new("RGB", (1080, 1920), (28, 35, 45))
    draw = ImageDraw.Draw(image)
    for x in range(850, 1080, 8):
        for y in range(0, 1920, 8):
            if (x + y) // 8 % 2:
                draw.rectangle((x, y, x + 7, y + 7), fill=(230, 230, 230))

    layout = renderer._top5_editorial_layout(
        image,
        "India make a major selection change",
        "The board confirmed the move. The decision changes the lineup.",
        "english",
    )

    assert layout["align"] == "left"
    assert layout["x"] == renderer.TOP5_EDITORIAL_MARGIN_X


def test_top5_layout_is_not_locked_to_a_bottom_anchor():
    image = Image.new("RGB", (1080, 1920), (36, 44, 54))
    draw = ImageDraw.Draw(image)
    for x in range(0, 1080, 10):
        for y in range(980, 1920, 10):
            if (x + y) // 10 % 2:
                draw.rectangle((x, y, x + 9, y + 9), fill=(235, 235, 235))

    layout = renderer._top5_editorial_layout(
        image,
        "Top 5 Cricket News Today",
        "",
        "english",
    )

    assert layout["y"] == 180


def test_top5_headline_size_adapts_to_copy():
    image = Image.new("RGB", (1080, 1920), (25, 30, 36))

    short = renderer._top5_editorial_layout(
        image,
        "India name a major change",
        "",
        "english",
    )
    long = renderer._top5_editorial_layout(
        image,
        "India reshuffles the squad after a late selection change before the next international series",
        "",
        "english",
    )

    assert short["headline_fonts"][0].size >= long["headline_fonts"][0].size
    assert short["headline_lines"]
    assert long["headline_lines"]


def test_top5_body_preserves_all_copy_without_sentence_cap():
    body = (
        "The board confirmed the move after the latest result. "
        "The decision changes the lineup for the next series. "
        "Officials also confirmed the timing of the next review."
    )
    layout = renderer._top5_editorial_layout(
        Image.new("RGB", (1080, 1920), (20, 24, 30)),
        "Selection change",
        body,
        "english",
    )

    rendered_words = " ".join(" ".join(line) for line in layout["body_lines"])
    assert "Officials" in rendered_words
    assert "review." in rendered_words
    assert layout["body_font"].size >= renderer.TOP5_EDITORIAL_BODY_MIN_SIZE


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
