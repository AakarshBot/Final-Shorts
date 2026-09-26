from pathlib import Path

from PIL import ImageChops

import renderer


def test_renderer_frame_is_vertical_and_independent():
    base = renderer.make_sample_background()
    frame = renderer.render_frame(base, 0.9)

    assert frame.size == (1080, 1920)
    assert frame.mode == "RGB"
    assert frame is not base


def test_headline_is_single_line_and_dynamic():
    short_font, short_text, short_width = renderer._fit_headline_font(
        "GAME CHANGED",
    )
    long_font, long_text, long_width = renderer._fit_headline_font(
        "THIS IS A MUCH LONGER HEADLINE",
    )

    assert short_text.split() == ["GAME", "CHANGED"]
    assert long_text.split() == ["THIS", "IS", "A", "MUCH", "LONGER", "HEADLINE"]
    assert short_width <= renderer.HEADLINE_MAX_WIDTH
    assert long_width <= renderer.HEADLINE_MAX_WIDTH
    assert renderer.HEADLINE_MAX_SIZE > 118
    assert long_font.size < short_font.size


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


def test_subtitles_start_after_headline(monkeypatch):
    seen = []

    def fake_draw(base, subtitle_data, t):
        seen.append(t)

    monkeypatch.setattr(renderer, "_draw_subtitles", fake_draw)
    base = renderer.make_sample_background()

    renderer.render_frame(base, 0.30, headline_enabled=True)
    assert seen == []

    renderer.render_frame(
        base,
        renderer.HEADLINE_SECONDS + 0.30,
        headline_enabled=True,
    )
    assert seen == [renderer.HEADLINE_SECONDS + 0.30]


def test_headline_marker_and_subtitle_style_are_brand_consistent():
    assert renderer.HEADLINE_MARKER_WIDTH > 0
    assert renderer.HEADLINE_MARKER_HEIGHT > 0
    assert renderer.BRAND_BLUE != renderer.ACCENT
    assert renderer.SUBTITLE_MAX_SIZE > 58
    assert renderer.SUBTITLE_MAX_WIDTH >= 860
    assert renderer.SUBTITLE_Y < 1450
    assert renderer.SUBTITLE_LINE_GAP > 0


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


def test_renderer_paths_point_to_expected_local_assets():
    assert renderer.get_logo_path().name == "logo.png"
    assert Path(renderer.get_headline_font_path()).parent.name == "fonts"
