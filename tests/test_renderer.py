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
