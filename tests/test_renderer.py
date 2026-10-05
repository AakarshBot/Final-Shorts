import pytest
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import renderer


TEST_SUBTITLE_DATA = {
    "schema": "final-shorts.subtitles.v1",
    "language": "english",
    "cues": [
        {
            "start": 0.30,
            "end": 1.28,
            "words": [
                {"text": "India", "start": 0.30, "end": 0.52},
                {"text": "started", "start": 0.52, "end": 0.75},
                {"text": "strongly,", "start": 0.75, "end": 0.98},
                {"text": "but", "start": 0.98, "end": 1.28},
            ],
        },
        {
            "start": 1.28,
            "end": 2.27,
            "words": [
                {"text": "the", "start": 1.28, "end": 1.44},
                {"text": "momentum", "start": 1.44, "end": 1.70},
                {"text": "shifted", "start": 1.70, "end": 1.96},
                {"text": "when", "start": 1.96, "end": 2.27},
            ],
        },
        {
            "start": 2.27,
            "end": 2.85,
            "words": [
                {"text": "pressure", "start": 2.27, "end": 2.51},
                {"text": "finally", "start": 2.51, "end": 2.68},
                {"text": "arrived.", "start": 2.68, "end": 2.85},
            ],
        },
    ],
}


def _test_base():
    return Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), "white")


def test_production_upload_encode_settings_are_youtube_ready():
    assert renderer.FPS == 24
    assert renderer.HEADLINE_SECONDS == 1.35


def test_renderer_frame_is_vertical_and_independent():
    base = _test_base()
    frame = renderer.render_frame(base, 0.9)

    assert frame.size == (1080, 1920)
    assert frame.mode == "RGB"
    assert frame is not base


def test_headline_is_large_and_dynamic():
    short_font, short_text, short_lines = renderer._fit_headline_font(
        "GAME CHANGED",
    )
    long_font, long_text, long_lines = renderer._fit_headline_font(
        "THIS IS A MUCH LONGER HEADLINE",
    )

    assert short_text.split() == ["GAME", "CHANGED"]
    assert long_text.split() == ["THIS", "IS", "A", "MUCH", "LONGER", "HEADLINE"]
    assert renderer.HEADLINE_MAX_SIZE >= 250
    assert renderer.HEADLINE_MIN_SIZE >= 120
    assert renderer.HEADLINE_LINE_GAP > 0
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "Oswald-Bold.ttf"
    assert font_path.name == "Oswald-Bold.ttf"
    assert font_path.exists()
    assert 1 <= len(renderer._fit_headline_font(renderer.HEADLINE_TEXT)[2]) <= renderer.HEADLINE_MAX_LINES
    assert renderer._fit_headline_font(renderer.HEADLINE_TEXT)[0].size >= 150
    assert len(long_lines) >= len(short_lines)


def test_renderer_uses_supplied_headline(monkeypatch):
    seen = []

    def fake_draw(base, text, t, language):
        seen.append(text)

    monkeypatch.setattr(renderer, "_draw_headline", fake_draw)
    base = _test_base()

    renderer.render_frame(
        base,
        0.30,
        headline_text="Gill Injury Scare",
        headline_enabled=True,
    )

    assert seen == ["Gill Injury Scare"]


def test_renderer_skips_headline_when_disabled(monkeypatch):
    seen = []
    monkeypatch.setattr(renderer, "_draw_headline", lambda *args: seen.append("headline"))
    base = _test_base()

    renderer.render_frame(
        base,
        0.50,
        headline_text="Gill Injury Scare",
        headline_enabled=False,
    )

    assert seen == []



def test_renderer_shows_headline_and_subtitles_together(monkeypatch):
    calls = []
    monkeypatch.setattr(renderer, "_draw_headline", lambda *args: calls.append("headline"))
    monkeypatch.setattr(renderer, "_draw_subtitles", lambda *args: calls.append("subtitles"))
    base = _test_base()

    renderer.render_frame(
        base,
        0.50,
        headline_text="Gill Injury Scare",
        headline_enabled=True,
    )

    assert calls == ["headline", "subtitles"]


def test_headline_wraps_three_and_six_word_inputs_without_overflow():
    for text in ("BIG CRICKET NEWS", "BIG CRICKET NEWS FROM INDIA TODAY"):
        font, clean, lines = renderer._fit_headline_font(text)
        assert 3 <= len(clean.split()) <= 6
        assert 1 <= len(lines) <= renderer.HEADLINE_MAX_LINES
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        width = max(
            probe.textbbox(
                (0, 0),
                " ".join(line),
                font=font,
                stroke_width=renderer.HEADLINE_STROKE_WIDTH,
            )[2]
            - probe.textbbox(
                (0, 0),
                " ".join(line),
                font=font,
                stroke_width=renderer.HEADLINE_STROKE_WIDTH,
            )[0]
            for line in lines
        )
        assert width <= renderer.HEADLINE_MAX_WIDTH


def test_headline_render_stays_inside_canvas_bounds(monkeypatch):
    monkeypatch.setattr(renderer, "_paste_logo", lambda base: None)
    monkeypatch.setattr(renderer, "_paste_source", lambda base: None)
    base = _test_base()

    frame = renderer.render_frame(
        base,
        0.50,
        headline_text="BIG CRICKET NEWS FROM INDIA TODAY",
        headline_enabled=True,
    )
    bbox = ImageChops.difference(base, frame).getbbox()

    assert bbox is not None
    assert bbox[0] >= 0
    assert bbox[2] <= renderer.WIDTH


def test_subtitle_render_stays_inside_safe_screen_bounds(monkeypatch):
    monkeypatch.setattr(renderer, "_paste_logo", lambda base: None)
    monkeypatch.setattr(renderer, "_paste_source", lambda base: None)
    base = _test_base()
    subtitle_data = {
        "schema": "final-shorts.subtitles.v1",
        "language": "english",
        "cues": [
            {
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {"text": "Championship", "start": 0.0, "end": 0.5},
                    {"text": "International", "start": 0.5, "end": 1.0},
                    {"text": "Cricket", "start": 1.0, "end": 1.5},
                    {"text": "Update", "start": 1.5, "end": 2.0},
                ],
            }
        ],
    }

    frame = renderer.render_frame(
        base,
        1.0,
        subtitle_data=subtitle_data,
        headline_enabled=False,
    )
    bbox = ImageChops.difference(base, frame).getbbox()

    assert bbox is not None
    assert bbox[0] >= renderer.SUBTITLE_SAFE_MARGIN
    assert bbox[2] <= renderer.WIDTH - renderer.SUBTITLE_SAFE_MARGIN


def test_headline_and_subtitles_do_not_overlap():
    base = _test_base()

    headline_frame = renderer.render_frame(
        base,
        0.50,
        headline_enabled=True,
    )
    subtitle_frame = renderer.render_frame(
        base,
        renderer.HEADLINE_SECONDS + 0.10,
        headline_enabled=True,
    )

    assert ImageChops.difference(headline_frame, subtitle_frame).getbbox()


def test_subtitles_remain_visible_during_headline(monkeypatch):
    seen = []

    def fake_draw(base, subtitle_data, t):
        seen.append(t)

    monkeypatch.setattr(renderer, "_draw_subtitles", fake_draw)
    base = _test_base()

    renderer.render_frame(base, 0.30, headline_enabled=True)
    renderer.render_frame(
        base,
        renderer.HEADLINE_SECONDS + 0.30,
        headline_enabled=True,
    )

    assert seen == [0.30, renderer.HEADLINE_SECONDS + 0.30]


def test_headline_marker_and_subtitle_style_are_brand_consistent():
    assert renderer.HEADLINE_MARKER_WIDTH > 0
    assert renderer.HEADLINE_MARKER_HEIGHT > 0
    assert renderer.BRAND_BLUE != renderer.ACCENT
    assert renderer.SUBTITLE_MAX_SIZE > 58
    assert renderer.SUBTITLE_MAX_WIDTH >= 860
    assert renderer.SUBTITLE_WORD_SPACING <= 12
    assert renderer.SUBTITLE_Y < 1450
    assert renderer.SUBTITLE_LINE_GAP >= 12


def test_subtitle_layout_uses_second_line_only_when_needed():
    words = TEST_SUBTITLE_DATA["cues"][0]["words"]

    font, line_lengths, _, line_heights, total_height = renderer._subtitle_render_geometry_cached(
        tuple(word["text"] for word in words),
        "english",
    )
    assert font.size >= renderer.SUBTITLE_MIN_SIZE
    assert 1 <= len(line_lengths) <= 2
    assert line_heights
    assert total_height > 0

    long_words = [
        {"text": "This", "start": 0.0, "end": 0.2},
        {"text": "is", "start": 0.2, "end": 0.4},
        {"text": "a", "start": 0.4, "end": 0.6},
        {"text": "very", "start": 0.6, "end": 0.8},
        {"text": "long", "start": 0.8, "end": 1.0},
        {"text": "sports", "start": 1.0, "end": 1.2},
        {"text": "update", "start": 1.2, "end": 1.4},
        {"text": "today", "start": 1.4, "end": 1.6},
    ]
    _, long_line_lengths, _, _, _ = renderer._subtitle_render_geometry_cached(
        tuple(word["text"] for word in long_words),
        "english",
    )
    assert len(long_line_lengths) == 2
    assert sum(long_line_lengths) == len(long_words)


def test_subtitle_dash_variants_are_normalised():
    values = ["left‐right", "left‑right", "left–right", "left—right", "left−right"]
    assert [
        value.translate(renderer.DASH_TRANSLATION)
        for value in values
    ] == ["left-right"] * len(values)


def test_subtitle_handoff_contract():
    assert renderer.validate_subtitle_handoff(TEST_SUBTITLE_DATA)


def test_invalid_subtitle_handoff_is_rejected():
    bad = {
        "schema": "final-shorts.subtitles.v1",
        "language": "english",
        "cues": [
            {
                "start": 1.0,
                "end": 1.5,
                "words": [{"text": "hello", "start": 1.1, "end": 1.6}],
            }
        ],
    }

    assert renderer.validate_subtitle_handoff(bad) is False



def test_production_renderer_uses_approved_handoffs(monkeypatch, tmp_path):
    from io import BytesIO

    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")

    visual_buffer = BytesIO()
    Image.new("RGB", (1200, 800), "white").save(visual_buffer, format="JPEG")

    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A factual opening sentence."}],
        "headline": "Gill Injury Scare",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    subtitles = {
        "schema": "final-shorts.subtitles.v1",
        "language": "english",
        "cues": [{
            "start": 0.0,
            "end": 0.5,
            "words": [{"text": "A", "start": 0.0, "end": 0.2}],
        }],
    }
    visuals = [{"bytes": visual_buffer.getvalue()}]

    silent = []

    def fake_preview(frames, path):
        list(frames)
        path.write_bytes(b"silent")
        silent.append(path)
        return path

    def fake_mux(silent_video, audio_scenes, output):
        assert silent_video in silent
        assert audio_scenes == audio["scenes"]
        output.write_bytes(b"final")
        return output

    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    output = tmp_path / "final.mp4"
    result = renderer.render_production_video(
        script,
        audio,
        subtitles,
        visuals,
        output,
        headline_text="Gill Injury Scare",
        source_label="Test Sports Desk",
    )

    assert result == output
    assert output.read_bytes() == b"final"
    assert not silent[0].exists()


def test_production_visuals_are_normalised_to_vertical_frame():
    image = renderer._fit_visual_to_frame(Image.new("RGB", (1600, 900), "white"))
    assert image.size == (renderer.WIDTH, renderer.HEIGHT)


def test_production_renderer_uses_stats_card_image_height_for_subtitles(monkeypatch, tmp_path):
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
        "result_key": "stats-card",
        "card_layout": {
            "width": 1080,
            "height": 1920,
            "image_width": 1080,
            "image_height": 860,
            "panel_height": 1060,
        },
    }]

    seen = []

    def fake_frame(*args):
        seen.append(args)
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

    output = tmp_path / "final.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        visuals,
        output,
        headline_text="Gill Injury Scare",
        source_label="Test Sports Desk",
    )

    assert seen
    assert seen[0][0].size == (1080, 1920)
    assert seen[0][6] == 764


def test_production_renderer_keeps_normal_visual_subtitles_on_default_position(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")

    visual_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual_buffer, format="PNG")

    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A factual opening sentence."}],
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    seen = []

    def fake_frame(*args):
        seen.append(args)
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

    output = tmp_path / "normal.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        [{"bytes": visual_buffer.getvalue(), "result_key": "real"}],
        output,
    )

    assert seen
    assert seen[0][6] is None



def test_quote_card_preview_uses_top5_full_frame_treatment():
    image_buffer = BytesIO()
    Image.new("RGB", (1200, 800), "white").save(image_buffer, format="JPEG")

    preview = renderer.build_quote_card_preview(
        image_buffer.getvalue(),
        "I think Virat Kohli will finish on 98 centuries.",
        "Aakash Chopra",
    )

    image = Image.open(BytesIO(preview))
    assert image.size == (renderer.WIDTH, renderer.HEIGHT)


def test_quote_card_preview_accepts_multiline_quote():
    quote = (
        "The latest result changes the selection picture, but the final decision still depends on the "
        "team balance, the next match conditions and what the selectors see before the series begins."
    )
    image_buffer = BytesIO()
    Image.new("RGB", (1200, 800), "white").save(image_buffer, format="JPEG")
    preview = renderer.build_quote_card_preview(
        image_buffer.getvalue(),
        quote,
        "Speaker Name",
    )
    image = Image.open(BytesIO(preview))
    assert image.size == (renderer.WIDTH, renderer.HEIGHT)



def test_quote_card_suppresses_headline_and_subtitles(monkeypatch):
    calls = []

    monkeypatch.setattr(renderer, "_draw_quote_card", lambda *args: calls.append("quote"))
    monkeypatch.setattr(renderer, "_draw_headline", lambda *args: calls.append("headline"))
    monkeypatch.setattr(renderer, "_draw_subtitles", lambda *args: calls.append("subtitles"))
    monkeypatch.setattr(renderer, "_paste_logo", lambda *args: None)
    monkeypatch.setattr(renderer, "_paste_source", lambda *args: None)

    base = _test_base()
    renderer.render_frame(
        base,
        0.5,
        quote_card={
            "quote": "I think Virat Kohli will finish on 98 centuries.",
            "attribution": "Aakash Chopra",
        },
        headline_enabled=True,
    )

    assert calls == ["quote"]


def test_production_renderer_preserves_quote_card_handoff(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual = Image.new("RGB", (1080, 1920), "white")
    visual_buffer = BytesIO()
    visual.save(visual_buffer, format="PNG")

    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "Aakash Chopra predicts 98 centuries."}],
        "headline": "Kohli On 98 Centuries",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    subtitles = TEST_SUBTITLE_DATA
    quote_card = {
        "quote": "I think Virat Kohli will finish on 98 centuries.",
        "attribution": "Aakash Chopra",
        "language": "english",
    }
    seen = []

    def fake_quote(*args, **kwargs):
        seen.append(args[1] if len(args) > 1 else kwargs.get("card"))
        return args[0]

    def fake_preview(frames, path):
        next(iter(frames))
        path.write_bytes(b"silent")
        return path

    def fake_mux(silent_video, audio_scenes, output):
        output.write_bytes(b"final")
        return output

    monkeypatch.setattr(renderer, "_draw_quote_card", fake_quote)
    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    output = tmp_path / "quote.mp4"
    renderer.render_production_video(
        script,
        audio,
        subtitles,
        [{
            "bytes": visual_buffer.getvalue(),
            "result_key": "quote-card",
            "quote_card": quote_card,
        }],
        output,
    )

    assert seen == [quote_card]


def test_production_renderer_uses_quote_source_label(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual, format="PNG")

    quote_card = {
        "quote": "A concise quoted line from the speaker.",
        "attribution": "Speaker Name",
        "language": "english",
        "source_label": "Quote Source",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A spoken line."}],
        "headline": "Quote headline",
    }
    seen = []

    monkeypatch.setattr(renderer, "_draw_quote_card", lambda base, card: base)
    monkeypatch.setattr(renderer, "_paste_logo", lambda base: None)
    monkeypatch.setattr(renderer, "_paste_source", lambda base, label=None: seen.append(label))
    monkeypatch.setattr(
        renderer,
        "write_preview_video",
        lambda frames, path: (next(iter(frames)), path.write_bytes(b"silent"), path)[-1],
    )
    monkeypatch.setattr(
        renderer,
        "_mux_audio",
        lambda silent, scenes, output: (output.write_bytes(b"final") or output),
    )

    output = tmp_path / "quote-source.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        [{
            "bytes": visual.getvalue(),
            "source": "Quote Card · Speaker Name",
            "quote_card": quote_card,
        }],
        output,
    )

    assert seen == ["Quote Source"]


def test_top5_editorial_uses_barlow_and_dynamic_safe_area():
    story = renderer._top5_editorial_layout(
        "Virat Kohli returns for another cricket test",
        "The board confirmed the move after reviewing the latest result.",
        "english",
        1,
    )
    opener = renderer._top5_editorial_layout(
        "Today's top five cricket stories",
        "",
        "english",
        0,
    )

    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    assert font_path.exists()
    assert story["width"] == renderer.TOP5_EDITORIAL_MAX_WIDTH == renderer.WIDTH - 128
    assert story["headline_fonts"][0].getname()[0].lower().startswith("barlow")
    assert renderer.TOP5_EDITORIAL_SAFE_TOP <= story["y"] <= renderer.TOP5_EDITORIAL_SAFE_BOTTOM
    assert story["y"] + story["total_height"] <= story["zone_bottom"]
    assert renderer.TOP5_EDITORIAL_SAFE_TOP <= opener["y"] <= renderer.TOP5_EDITORIAL_SAFE_BOTTOM


def test_top5_editorial_moves_into_quiet_vertical_copy_space():
    image = Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    for y in range(1160, 1650, 20):
        for x in range(0, renderer.WIDTH, 20):
            value = 255 if ((x // 20) + (y // 20)) % 2 else 0
            draw.rectangle((x, y, x + 19, y + 19), fill=(value, value, value))

    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "The board confirmed the move today.",
        "english",
        1,
        image=image,
    )

    assert layout["y"] < 1000
    assert layout["composition_score"] >= renderer.TOP5_EDITORIAL_MIN_COMPOSITION_SCORE


def test_top5_editorial_moves_down_when_lower_copy_space_is_quieter():
    image = Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), (20, 22, 26))
    draw = ImageDraw.Draw(image)
    for y in range(620, 1050, 20):
        for x in range(0, renderer.WIDTH, 20):
            value = 255 if ((x // 20) + (y // 20)) % 2 else 0
            draw.rectangle((x, y, x + 19, y + 19), fill=(value, value, value))

    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "The board confirmed the move today.",
        "english",
        1,
        image=image,
    )

    assert layout["y"] > 1000
    assert layout["composition_score"] >= renderer.TOP5_EDITORIAL_MIN_COMPOSITION_SCORE


def test_top5_subject_aware_layout_targets_controlled_headline_overlap(monkeypatch):
    image = Image.new("RGB", (1080, 1920), (70, 70, 70))
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((60, 620, 620, 980), fill=255)

    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "The board confirmed the move.",
        "english",
        1,
        image=image,
        subject_mask=subject,
    )

    overlap = renderer._top5_subject_overlap_score(
        subject,
        layout["x"],
        layout["y"],
        layout["width"],
        layout["headline_height"],
    )
    assert overlap > 0
    assert layout["composition_score"] >= renderer.TOP5_EDITORIAL_MIN_COMPOSITION_SCORE


def test_top5_headline_subject_occlusion_sits_above_type(monkeypatch):
    background = Image.new("RGB", (1080, 1920), (20, 24, 30))
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((60, 620, 600, 960), fill=255)

    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)
    occluded = renderer.build_top5_card_preview(
        background,
        "India dominate the latest cricket result",
        "The board confirmed the move after the latest result.",
        story_number=1,
        subject_cutout=True,
    )

    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: None)
    normal = renderer.build_top5_card_preview(
        background,
        "India dominate the latest cricket result",
        "The board confirmed the move after the latest result.",
        story_number=1,
    )

    assert ImageChops.difference(
        Image.open(BytesIO(occluded)).convert("RGB"),
        Image.open(BytesIO(normal)).convert("RGB"),
    ).getbbox() is not None


def test_top5_subject_mask_uses_local_birefnet(monkeypatch):
    import torch

    class FakeModel:
        def eval(self):
            return self

        def __call__(self, input_images):
            return [torch.ones((1, 1, 1024, 1024))]

    renderer._top5_subject_mask.cache_clear()
    monkeypatch.setattr(
        renderer,
        "_load_top5_birefnet",
        lambda: (FakeModel(), torch.device("cpu")),
    )

    source = BytesIO()
    Image.new("RGB", (1080, 1920), (20, 24, 30)).save(source, format="PNG")
    mask = renderer._top5_subject_mask(source.getvalue())

    assert mask is not None
    assert mask.size == (1080, 1920)
    assert mask.getbbox() is not None


def test_top5_editorial_uses_opaque_text_and_targeted_shadow(monkeypatch):
    calls = []
    original_blur = renderer.ImageFilter.GaussianBlur

    def spy_blur(radius):
        calls.append(radius)
        return original_blur(radius)

    monkeypatch.setattr(renderer.ImageFilter, "GaussianBlur", spy_blur)
    preview = renderer.build_top5_card_preview(
        Image.new("RGB", (1080, 1920), (28, 42, 64)),
        "Big cricket result changes",
        "The board confirmed the move after reviewing the latest result.",
        story_number=1,
    )

    assert preview
    assert renderer.TOP5_EDITORIAL_SHADOW_BLUR in calls
    assert not hasattr(renderer, "TOP5_EDITORIAL_LOCAL_SCRIM_ALPHA")
    assert not hasattr(renderer, "TOP5_EDITORIAL_LOCAL_SCRIM_BLUR")


def test_top5_editorial_body_rejects_copy_below_readable_floor():
    body = " ".join(
        [
            "The board confirmed the move after reviewing the latest result and selection options.",
            "The decision changes the lineup ahead of the next match and follows the latest update from officials.",
        ] * 7
    )

    with pytest.raises(ValueError) as error:
        renderer._top5_editorial_layout(
            "Selection picture changes after the latest result",
            body,
            "english",
            1,
        )

    assert error.value.top5_max_words > 0
    assert error.value.top5_max_words < len(body.split())



def test_top5_card_preview_renders_the_shared_editorial_treatment():
    preview = renderer.build_top5_card_preview(
        Image.new("RGB", (1080, 1920), (28, 42, 64)),
        "Big cricket result changes the selection picture",
        "The board confirmed the move after reviewing the latest result. The decision changes the lineup for the next match.",
        story_number=1,
        total_stories=5,
        source_label="Test Source",
    )

    image = Image.open(BytesIO(preview))
    assert image.size == (renderer.WIDTH, renderer.HEIGHT)
