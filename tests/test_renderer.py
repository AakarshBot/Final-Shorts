from pathlib import Path

from PIL import ImageChops

import renderer


def test_renderer_frame_is_vertical_and_independent():
    base = renderer.make_sample_background()
    frame = renderer.render_frame(
        base,
        "Clean Editorial",
        0.9,
        "THIS CHANGED EVERYTHING",
        True,
    )

    assert frame.size == (1080, 1920)
    assert frame.mode == "RGB"
    assert frame is not base


def test_renderer_styles_are_visually_distinct():
    base = renderer.make_sample_background()
    first = renderer.render_frame(
        base,
        "Clean Editorial",
        1.8,
        renderer.HEADLINE_TEXT,
        False,
    )
    second = renderer.render_frame(
        base,
        "Micro Glass",
        1.8,
        renderer.HEADLINE_TEXT,
        False,
    )
    third = renderer.render_frame(
        base,
        "Broadcast / Data",
        1.8,
        renderer.HEADLINE_TEXT,
        False,
    )

    assert ImageChops.difference(first, second).getbbox()
    assert ImageChops.difference(second, third).getbbox()


def test_renderer_headline_moves_between_start_and_resting_position():
    base = renderer.make_sample_background()
    before = renderer.render_frame(
        base,
        "Clean Editorial",
        0.0,
        "THIS CHANGED EVERYTHING",
        True,
    )
    settled = renderer.render_frame(
        base,
        "Clean Editorial",
        0.65,
        "THIS CHANGED EVERYTHING",
        True,
    )

    assert ImageChops.difference(before, settled).getbbox()


def test_renderer_paths_point_to_expected_local_assets():
    assert renderer.get_logo_path().name == "logo.png"
    assert Path(renderer.get_headline_font_path()).parent.name == "fonts"


def test_default_headline_is_short_and_fits_and_keeps_all_words():
    assert len(renderer.HEADLINE_TEXT.split()) == 4

    font, lines = renderer._headline_layout(renderer.HEADLINE_TEXT)
    probe = renderer.ImageDraw.Draw(renderer.Image.new("RGB", (1, 1)))

    assert len(lines) <= 2
    assert " ".join(lines).split() == renderer.HEADLINE_TEXT.split()
    assert all(renderer._measure(probe, line, font)[0] <= 860 for line in lines)


def test_subtitles_wait_until_headline_has_disappeared(monkeypatch):
    seen = []

    def fake_groups(t):
        seen.append(t)
        return ["preview"], 0

    monkeypatch.setattr(renderer, "_groups_at_time", fake_groups)
    base = renderer.make_sample_background()

    renderer.render_frame(base, "Clean Editorial", 0.30, renderer.HEADLINE_TEXT, True)
    assert seen == []

    renderer.render_frame(base, "Clean Editorial", renderer.HEADLINE_SECONDS - 0.01, renderer.HEADLINE_TEXT, True)
    assert seen == []

    renderer.render_frame(base, "Clean Editorial", renderer.HEADLINE_SECONDS + 0.30, renderer.HEADLINE_TEXT, True)
    assert round(seen[-1], 2) == 0.30


def test_subtitles_start_immediately_without_headline(monkeypatch):
    seen = []

    def fake_groups(t):
        seen.append(t)
        return ["preview"], 0

    monkeypatch.setattr(renderer, "_groups_at_time", fake_groups)
    base = renderer.make_sample_background()

    renderer.render_frame(base, "Clean Editorial", 0.30, renderer.HEADLINE_TEXT, False)

    assert seen == [0.30]
