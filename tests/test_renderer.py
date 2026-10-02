from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import renderer


def test_production_upload_encode_settings_are_youtube_ready():
    assert renderer.FPS == 24
    assert renderer.HEADLINE_SECONDS == 1.35


def test_renderer_frame_is_vertical_and_independent():
    base = renderer.make_sample_background()
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
    base = renderer.make_sample_background()

    renderer.render_frame(
        base,
        0.30,
        headline_text="Gill Injury Scare",
        headline_enabled=True,
    )

    assert seen == ["Gill Injury Scare"]


def test_renderer_shows_headline_and_subtitles_together(monkeypatch):
    calls = []
    monkeypatch.setattr(renderer, "_draw_headline", lambda *args: calls.append("headline"))
    monkeypatch.setattr(renderer, "_draw_subtitles", lambda *args: calls.append("subtitles"))
    base = renderer.make_sample_background()

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
    base = renderer.make_sample_background()

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
    base = renderer.make_sample_background()
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
    base = renderer.make_sample_background()

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
    base = renderer.make_sample_background()

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
    words = renderer.PREVIEW_SUBTITLE_DATA["cues"][0]["words"]

    font, lines = renderer._fit_subtitle_layout(words, "english")
    assert font.size >= renderer.SUBTITLE_MIN_SIZE
    assert 1 <= len(lines) <= 2

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
    font, two_lines = renderer._fit_subtitle_layout(long_words, "english")
    assert len(two_lines) == 2
    assert sum(len(line) for line in two_lines) == len(long_words)


def test_subtitle_dash_variants_are_normalised():
    values = ["left‐right", "left‑right", "left–right", "left—right", "left−right"]
    assert [
        value.translate(renderer.DASH_TRANSLATION)
        for value in values
    ] == ["left-right"] * len(values)


def test_subtitle_handoff_contract():
    assert renderer.validate_subtitle_handoff(renderer.PREVIEW_SUBTITLE_DATA)


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
        renderer.PREVIEW_SUBTITLE_DATA,
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
        renderer.PREVIEW_SUBTITLE_DATA,
        [{"bytes": visual_buffer.getvalue(), "result_key": "real"}],
        output,
    )

    assert seen
    assert seen[0][6] is None
