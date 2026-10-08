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


def test_manual_subject_cutout_anchors_text_to_polygon_left_edge(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    data = renderer._manual_subject_cutout_layout_data(
        "India win today",
        ((80, 700), (1000, 700), (1000, 1200), (80, 1200)),
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert data["layouts"]
    for layout in data["layouts"]:
        assert layout["placements"][0][1] == 702
        last_line, last_top, left, bbox = layout["placements"][-1]
        assert last_top + (bbox[3] - bbox[1]) <= 1198
        for _line, _line_top, left, bbox in layout["placements"]:
            line_width = bbox[2] - bbox[0]
            assert left == 82
            assert left + line_width <= 998



def test_manual_subject_cutout_follows_left_edge_of_skewed_polygon(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    data = renderer._manual_subject_cutout_layout_data(
        "India win",
        ((80, 700), (1000, 700), (1000, 1600), (300, 1600), (80, 1200)),
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert data["layouts"]
    one_line = next(layout for layout in data["layouts"] if len(layout["lines"]) == 1)
    assert one_line["placements"][0][2] == 82

def test_manual_subject_cutout_polygon_flow_uses_vertical_indentation(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    polygon = ((120, 700), (640, 700), (920, 1500), (400, 1500))
    flowed = renderer._manual_subject_cutout_layout_data(
        "India win today after a dramatic late turnaround in the final over",
        polygon,
        120,
        "Barlow Condensed",
        "Crisp Outline",
        polygon_flow=True,
    )

    assert flowed["layouts"]
    layout = max(flowed["layouts"], key=lambda item: len(item["lines"]))
    assert flowed["polygon_flow"] is True
    assert len(layout["lines"]) >= 2

    lefts = [placement[2] for placement in layout["placements"]]
    assert lefts[-1] > lefts[0]

def test_production_upload_encode_settings_are_youtube_ready():
    assert renderer.FPS == 30
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



def test_production_renderer_preserves_manual_subject_cutout(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")

    visual = Image.new("RGB", (1080, 1920), (20, 24, 30))
    player_color = (180, 90, 60)
    ImageDraw.Draw(visual).rectangle((390, 620, 690, 1420), fill=player_color)
    visual_buffer = BytesIO()
    visual.save(visual_buffer, format="PNG")

    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((390, 620, 690, 1420), fill=255)
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)

    script = {
        "schema": "final-shorts.top5-script.v1",
        "approved_for_audio": True,
        "slides": [{
            "slide_number": 1,
            "headline": "India dominate the latest result",
            "body": "",
        }],
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    manual = {
        "headline": "India dominate the latest result",
        "mode": "behind-subject",
        "text_polygon": (
            (120, 680),
            (960, 680),
            (960, 1180),
            (120, 1180),
        ),
        "font_size": 140,
    }
    visuals = [{
        "bytes": visual_buffer.getvalue(),
        "source": "Test Source",
        "manual_subject_cutout": manual,
    }]
    seen = []

    def fake_preview(frames, path):
        seen.append(next(iter(frames)))
        path.write_bytes(b"silent")
        return path

    def fake_mux(silent_video, audio_scenes, output):
        output.write_bytes(b"final")
        return output

    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    output = tmp_path / "manual-subject.mp4"
    renderer.render_production_video(
        script,
        audio,
        None,
        visuals,
        output,
        headline_enabled=False,
    )

    assert output.read_bytes() == b"final"
    assert seen
    assert seen[0].getpixel((500, 900)) == player_color


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

    def fake_frame(*args, **kwargs):
        seen.append((args, kwargs))
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
    assert seen[0][0][5] is None
    assert seen[0][1].get("top5_card") is None



def test_top5_editorial_uses_oswald_and_full_frame_safe_area():
    story = renderer._top5_editorial_layout(
        "Virat Kohli returns for another cricket test",
        "The board confirmed the move after reviewing the latest result.",
        "english",
        1,
        image=Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), (28, 32, 38)),
    )
    opener = renderer._top5_editorial_layout(
        "Today's top five cricket stories",
        "",
        "english",
        0,
        image=Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), (28, 32, 38)),
    )

    assert story["headline_fonts"][0].getname()[0].lower() == "oswald"
    assert renderer.TOP5_EDITORIAL_SAFE_TOP <= story["y"] <= renderer.TOP5_EDITORIAL_SAFE_BOTTOM
    assert story["y"] + story["total_height"] <= story["zone_bottom"]
    assert story["x"] >= renderer.TOP5_EDITORIAL_MARGIN_X
    assert renderer.TOP5_EDITORIAL_SAFE_TOP <= opener["y"] <= renderer.TOP5_EDITORIAL_SAFE_BOTTOM


def test_top5_option7_uses_full_frame_for_editorial_overlap():
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((650, 520, 1010, 1650), fill=255)

    layout = renderer._top5_editorial_layout(
        "India dominate the latest cricket result",
        "",
        "english",
        1,
        image=Image.new("RGB", (1080, 1920), (40, 40, 40)),
        subject_mask=subject,
    )

    assert layout["composition_mode"] == "subject-cutout"
    assert layout["region_mode"] == "hero-overlay"
    assert layout["x"] >= renderer.TOP5_EDITORIAL_MARGIN_X
    assert layout["x"] + layout["width"] <= renderer.WIDTH - renderer.TOP5_EDITORIAL_MARGIN_X
    assert layout["headline_size"] >= renderer.TOP5_SUBJECT_HEADLINE_MIN_SIZE
    assert layout["subject_overlap"] > 0


def test_top5_option7_two_subjects_remain_above_headline(monkeypatch):
    background = Image.new("RGB", (1080, 1920), (20, 24, 30))
    player_color = (180, 90, 60)
    draw = ImageDraw.Draw(background)
    draw.rectangle((170, 620, 360, 1440), fill=player_color)
    draw.rectangle((720, 620, 910, 1440), fill=player_color)

    subject = Image.new("L", (1080, 1920), 0)
    subject_draw = ImageDraw.Draw(subject)
    subject_draw.rectangle((170, 620, 360, 1440), fill=255)
    subject_draw.rectangle((720, 620, 910, 1440), fill=255)
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)

    preview = renderer.build_top5_card_preview(
        background,
        "India dominate the latest result",
        "",
        story_number=1,
        subject_cutout=True,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")
    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "",
        "english",
        1,
        image=background,
        subject_mask=subject,
    )

    assert layout["composition_mode"] == "subject-cutout"
    assert layout["subject_overlap"] > 0
    assert any(
        image.getpixel((x, y)) == player_color
        for y in range(layout["y"], layout["y"] + layout["headline_height"])
        for x in range(170, 361)
    )
    assert any(
        image.getpixel((x, y)) == player_color
        for y in range(layout["y"], layout["y"] + layout["headline_height"])
        for x in range(720, 911)
    )



def test_top5_option7_ignores_body_copy():
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((390, 570, 690, 1490), fill=255)

    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "Body should not be rendered by Subject Cutout.",
        "english",
        1,
        subject_mask=subject,
    )

    assert layout["composition_mode"] == "subject-cutout"
    assert layout["body_lines"] == []
    assert layout["body_font"] is None


def test_top5_option7_surfaces_mask_failure(monkeypatch):
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: None)

    with pytest.raises(ValueError, match="usable foreground mask"):
        renderer.build_top5_card_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India dominate the latest cricket result",
            "",
            story_number=1,
            subject_cutout=True,
        )


def test_top5_option7_restores_player_above_headline(monkeypatch):
    background = Image.new("RGB", (1080, 1920), (20, 24, 30))
    player_color = (180, 90, 60)
    ImageDraw.Draw(background).rectangle((390, 620, 690, 1420), fill=player_color)
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((390, 620, 690, 1420), fill=255)

    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)
    preview = renderer.build_top5_card_preview(
        background,
        "India dominate the latest result",
        "",
        story_number=1,
        subject_cutout=True,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")
    layout = renderer._top5_editorial_layout(
        "India dominate the latest result",
        "",
        "english",
        1,
        image=background,
        subject_mask=subject,
    )

    assert any(
        image.getpixel((x, y)) == player_color
        for y in range(layout["y"], min(layout["y"] + layout["headline_height"], 1420))
        for x in range(max(390, layout["x"]), min(690, layout["x"] + layout["width"]))
    )


def test_top5_manual_subject_cutout_exposes_nine_fonts_and_nine_styles(monkeypatch):
    local_font = (
        renderer.Path(__file__).resolve().parents[1]
        / "fonts"
        / "BarlowCondensed-Black.ttf"
    ).read_bytes()
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: local_font,
    )

    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS) == 9
    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS) == 9

    for font in renderer.MANUAL_SUBJECT_FONT_OPTIONS:
        preview = renderer.build_manual_subject_cutout_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India dominate the latest result",
            mode="negative-space",
            text_polygon=((60, 700), (1020, 700), (1020, 1200), (60, 1200)),
            font_size=140,
            font=font,
            style="Crisp Outline",
        )
        assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)

    for style in renderer.MANUAL_SUBJECT_STYLE_OPTIONS:
        preview = renderer.build_manual_subject_cutout_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India dominate the latest result",
            mode="negative-space",
            text_polygon=((60, 700), (1020, 700), (1020, 1200), (60, 1200)),
            font_size=140,
            font="Barlow Condensed",
            style=style,
        )
        assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)

    assert all(
        renderer.MANUAL_SUBJECT_FONT_OPTIONS[name].get("url")
        for name in ("Bebas Neue", "Teko", "Khand", "Kanit", "Fjalla One")
    )


def test_production_renderer_keeps_text_cutout_frame_free_of_overlays(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual, format="PNG")
    rendered = BytesIO()
    Image.new("RGB", (1080, 1920), (180, 40, 40)).save(rendered, format="PNG")

    rendered_frames = []

    def capture_frame(frames, path):
        rendered_frames.append(next(iter(frames)).copy())
        path.write_bytes(b"silent")
        return path

    def fail_overlay(*_args):
        raise AssertionError("Manual Subject Cutout must not receive permanent overlays.")

    monkeypatch.setattr(renderer, "_paste_logo", fail_overlay)
    monkeypatch.setattr(renderer, "_paste_source", fail_overlay)
    monkeypatch.setattr(renderer, "write_preview_video", capture_frame)
    monkeypatch.setattr(
        renderer,
        "_mux_audio",
        lambda silent, scenes, output: (output.write_bytes(b"final") or output),
    )

    config = {
        "headline": "Text Cutout Headline",
        "mode": "negative-space",
        "text_polygon": (
            (80, 700),
            (1000, 700),
            (1000, 1120),
            (80, 1120),
        ),
        "font_size": 140,
        "font": "Barlow Condensed",
        "style": "Heavy Drop",
    }
    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A spoken line."}],
        "headline": "Opening Headline",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }

    output = tmp_path / "text-cutout.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        [{
            "bytes": visual.getvalue(),
            "source": "Sports Desk",
            "preview_bytes": rendered.getvalue(),
            "manual_subject_cutout": config,
        }],
        output,
    )

    assert len(rendered_frames) == 1
    expected = Image.open(BytesIO(rendered.getvalue())).convert("RGB")
    assert ImageChops.difference(rendered_frames[0], expected).getbbox() is None

def test_manual_subject_cutout_previews_all_valid_line_breaks(monkeypatch):
    local_font = (
        renderer.Path(__file__).resolve().parents[1]
        / "fonts"
        / "BarlowCondensed-Black.ttf"
    ).read_bytes()
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: local_font,
    )

    options = renderer.build_manual_subject_cutout_layout_previews(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India win today",
        mode="negative-space",
        text_polygon=((60, 700), (1020, 700), (1020, 1400), (60, 1400)),
        font_size=140,
    )

    assert len(options) == 4
    assert {tuple(option["line_breaks"]) for option in options} == {
        (3,),
        (1, 3),
        (2, 3),
        (1, 2, 3),
    }
    assert all(
        Image.open(BytesIO(option["preview"])).size == (360, 640)
        for option in options
    )


def test_manual_subject_cutout_uses_selected_line_breaks(monkeypatch):
    local_font = (
        renderer.Path(__file__).resolve().parents[1]
        / "fonts"
        / "BarlowCondensed-Black.ttf"
    ).read_bytes()
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: local_font,
    )

    common = {
        "mode": "negative-space",
        "text_polygon": ((60, 700), (1020, 700), (1020, 1400), (60, 1400)),
        "font_size": 140,
        "font": "Barlow Condensed",
        "style": "Crisp Outline",
    }
    one_line = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India win today",
        line_breaks=(3,),
        **common,
    )
    three_lines = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India win today",
        line_breaks=(1, 2, 3),
        **common,
    )

    assert ImageChops.difference(
        Image.open(BytesIO(one_line)).convert("RGB"),
        Image.open(BytesIO(three_lines)).convert("RGB"),
    ).getbbox() is not None


def test_manual_subject_cutout_rejects_invalid_line_breaks(monkeypatch):
    local_font = (
        renderer.Path(__file__).resolve().parents[1]
        / "fonts"
        / "BarlowCondensed-Black.ttf"
    ).read_bytes()
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: local_font,
    )

    with pytest.raises(ValueError, match="line-break layout"):
        renderer.build_manual_subject_cutout_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India win today",
            mode="negative-space",
            text_polygon=((60, 700), (1020, 700), (1020, 1400), (60, 1400)),
            font_size=140,
            line_breaks=(1, 1, 3),
        )


def test_top5_manual_subject_cutout_accepts_polygon_text_region(monkeypatch):
    local_font = (
        renderer.Path(__file__).resolve().parents[1]
        / "fonts"
        / "BarlowCondensed-Black.ttf"
    ).read_bytes()
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: local_font,
    )
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((390, 500, 690, 1500), fill=255)
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)

    polygon = (
        (80, 660),
        (1000, 660),
        (1000, 930),
        (760, 1180),
        (320, 1180),
        (80, 930),
    )
    for mode in ("negative-space", "behind-subject"):
        preview = renderer.build_manual_subject_cutout_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India dominate the latest result",
            mode=mode,
            text_polygon=polygon,
            font_size=140,
            font="Barlow Condensed",
            style="Crisp Outline",
        )
        image = Image.open(BytesIO(preview))
        assert image.size == (renderer.WIDTH, renderer.HEIGHT)

def test_manual_subject_cutout_accepts_polygon_without_text_box():
    polygon = (
        (80, 660),
        (1000, 660),
        (1000, 930),
        (760, 1180),
        (320, 1180),
        (80, 930),
    )
    preview = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India dominate the latest result",
        mode="negative-space",
        font_size=140,
        font="Barlow Condensed",
        style="Crisp Outline",
        text_polygon=polygon,
    )
    assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)


def test_top5_manual_subject_cutout_uses_barlow_condensed():
    preview = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India dominate the latest result",
        mode="negative-space",
        text_polygon=((80, 650), (1000, 650), (1000, 1150), (80, 1150)),
        font_size=150,
    )
    image = Image.open(BytesIO(preview))
    assert image.size == (renderer.WIDTH, renderer.HEIGHT)


def test_top5_manual_subject_cutout_accepts_both_modes(monkeypatch):
    subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(subject).rectangle((360, 500, 720, 1500), fill=255)
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)

    for mode in ("negative-space", "behind-subject"):
        preview = renderer.build_manual_subject_cutout_preview(
            Image.new("RGB", (1080, 1920), (40, 40, 40)),
            "India dominate the latest result",
            mode=mode,
            text_polygon=((60, 700), (1020, 700), (1020, 1200), (60, 1200)),
            font_size=140,
        )
        assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)


def test_top5_manual_subject_cutout_negative_space_does_not_use_subject_mask(monkeypatch):
    called = []

    def fail(*_args):
        called.append(True)
        raise AssertionError("Negative Space must not run subject detection.")

    monkeypatch.setattr(renderer, "_top5_subject_mask", fail)
    preview = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (240, 240, 240)),
        "India dominate the latest result",
        mode="negative-space",
        text_polygon=((60, 700), (1020, 700), (1020, 1200), (60, 1200)),
        font_size=130,
    )

    assert preview
    assert not called


def test_top5_manual_subject_cutout_wraps_headline_inside_polygon():
    preview = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India dominate the latest cricket result today",
        mode="negative-space",
        text_polygon=((120, 700), (960, 700), (960, 1260), (120, 1260)),
        font_size=110,
    )

    assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)

    preview = renderer.build_manual_subject_cutout_preview(
        Image.new("RGB", (1080, 1920), (40, 40, 40)),
        "India dominate the latest cricket result today",
        mode="negative-space",
        text_polygon=((120, 700), (960, 700), (960, 1500), (120, 1500)),
        font_size=140,
    )
    assert Image.open(BytesIO(preview)).size == (renderer.WIDTH, renderer.HEIGHT)


def test_top5_manual_subject_cutout_keeps_two_subjects_above_text(monkeypatch):
    background = Image.new("RGB", (1080, 1920), (20, 24, 30))
    player_color = (180, 90, 60)
    draw = ImageDraw.Draw(background)
    draw.rectangle((160, 620, 360, 1440), fill=player_color)
    draw.rectangle((720, 620, 920, 1440), fill=player_color)

    subject = Image.new("L", (1080, 1920), 0)
    subject_draw = ImageDraw.Draw(subject)
    subject_draw.rectangle((160, 620, 360, 1440), fill=255)
    subject_draw.rectangle((720, 620, 920, 1440), fill=255)
    monkeypatch.setattr(renderer, "_top5_subject_mask", lambda *_args: subject)

    preview = renderer.build_manual_subject_cutout_preview(
        background,
        "India dominate the latest result",
        mode="behind-subject",
        text_polygon=((120, 680), (960, 680), (960, 1180), (120, 1180)),
        font_size=140,
    )
    image = Image.open(BytesIO(preview)).convert("RGB")

    assert image.getpixel((200, 900)) == player_color
    assert image.getpixel((800, 900)) == player_color


def test_top5_subject_mask_uses_local_birefnet_without_fp16(monkeypatch):
    import torch

    seen_dtypes = []

    class FakeModel:
        def eval(self):
            return self

        def __call__(self, input_images):
            seen_dtypes.append(input_images.dtype)
            return [torch.ones((1, 1, 1024, 1024), dtype=torch.float32)]

    renderer._top5_subject_mask.cache_clear()
    monkeypatch.setattr(
        renderer,
        "_load_top5_birefnet",
        lambda: (FakeModel(), __import__("torchvision").transforms),
    )

    source = BytesIO()
    Image.new("RGB", (1080, 1920), (20, 24, 30)).save(source, format="PNG")
    mask = renderer._top5_subject_mask(source.getvalue())

    assert mask is not None
    assert mask.size == (1080, 1920)
    assert seen_dtypes == [torch.float32]

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


def test_top5_editorial_body_remains_readable_when_it_fits():
    body = (
        "The board confirmed the move after reviewing the latest result and selection options. "
        "The decision changes the lineup ahead of the next match."
    )

    layout = renderer._top5_editorial_layout(
        "Selection picture changes after the latest result",
        body,
        "english",
        1,
        image=Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), (28, 32, 38)),
    )

    assert layout["body_lines"]
    assert layout["body_font"] is not None
    assert layout["body_size"] >= renderer.TOP5_EDITORIAL_BODY_MIN_SIZE



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



def test_mux_audio_loudnorm_is_inside_complex_filtergraph(monkeypatch, tmp_path):
    silent_video = tmp_path / "silent.mp4"
    silent_video.write_bytes(b"video")
    audio = tmp_path / "scene.mp3"
    audio.write_bytes(b"audio")
    output = tmp_path / "output.mp4"
    seen = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        return Result()

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    result = renderer._mux_audio(
        silent_video,
        [{"scene": 1, "path": str(audio)}],
        output,
    )

    assert result == output
    command = seen["command"]
    filter_index = command.index("-filter_complex")
    filter_value = command[filter_index + 1]
    assert "concat=n=1:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[a]" in filter_value
    assert "-af" not in command


def test_top5_card_preview_honors_logo_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(renderer, "_paste_logo", lambda *_args: calls.append("logo"))

    image = Image.new("RGB", (1080, 1920), "white")
    renderer.build_top5_card_preview(
        image,
        "Top five result changes",
        "",
        logo_enabled=False,
    )
    assert calls == []

    renderer.build_top5_card_preview(
        image,
        "Top five result changes",
        "",
        logo_enabled=True,
    )
    assert calls == ["logo"]


def test_production_top5_card_honors_logo_and_source_flags(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual, format="PNG")
    calls = []

    monkeypatch.setattr(renderer, "_draw_top5_editorial_card", lambda base, card: base)
    monkeypatch.setattr(renderer, "_paste_logo", lambda *_args: calls.append("logo"))
    monkeypatch.setattr(renderer, "_paste_source", lambda *_args: calls.append("source"))
    monkeypatch.setattr(renderer, "write_preview_video", lambda frames, path: (next(iter(frames)), path.write_bytes(b"silent"), path)[-1])
    monkeypatch.setattr(renderer, "_mux_audio", lambda silent, scenes, output: (output.write_bytes(b"final") or output))

    script = {
        "schema": "final-shorts.top5-script.v1",
        "approved_for_audio": True,
        "slides": [{"slide_number": 1, "headline": "Top five result"}],
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }

    renderer.render_production_video(
        script,
        audio,
        None,
        [{"bytes": visual.getvalue(), "top5_card": {"headline": "Top five result"}}],
        tmp_path / "top5.mp4",
        logo_enabled=True,
        source_enabled=False,
    )
    assert calls == ["logo"]


def test_production_renderer_uses_card_studio_static_preview_and_overlays(monkeypatch, tmp_path):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual, format="PNG")
    rendered = BytesIO()
    Image.new("RGB", (1080, 1920), (28, 42, 64)).save(rendered, format="PNG")

    calls = []
    frames = []

    monkeypatch.setattr(renderer, "_paste_logo", lambda *_args: calls.append("logo"))
    monkeypatch.setattr(renderer, "_paste_source", lambda *_args: calls.append("source"))
    monkeypatch.setattr(
        renderer,
        "write_preview_video",
        lambda iterable, path: (
            frames.append(next(iter(iterable))),
            path.write_bytes(b"silent"),
            path,
        )[-1],
    )
    monkeypatch.setattr(
        renderer,
        "_mux_audio",
        lambda silent, scenes, output: (output.write_bytes(b"final") or output),
    )

    script = {
        "approved_for_audio": True,
        "script": [{"voiceover": "A spoken line."}],
        "headline": "Card headline",
    }
    audio = {
        "approved_for_visuals": True,
        "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}],
    }
    preview_bytes = rendered.getvalue()

    output = tmp_path / "card.mp4"
    renderer.render_production_video(
        script,
        audio,
        TEST_SUBTITLE_DATA,
        [{
            "bytes": visual.getvalue(),
            "source": "Test Sports Desk",
            "preview_bytes": preview_bytes,
            "card_studio": {
                "type": "Stat Highlight",
                "data": {"headline": "Card headline", "value": "100"},
            },
        }],
        output,
        logo_enabled=True,
        source_enabled=True,
    )

    assert len(frames) == 1
    assert frames[0].size == (renderer.WIDTH, renderer.HEIGHT)
    assert calls == ["logo", "source"]


def test_final_renderer_quality_contract():
    import inspect
    import renderer

    source = inspect.getsource(renderer.write_preview_video)
    assert renderer.FPS == 30
    assert renderer._motion_profile("same") == renderer._motion_profile("same")
    assert renderer._motion_profile("visual-a") != renderer._motion_profile("visual-b")
    for setting in (
        '"-preset", "fast"',
        '"-crf", "18"',
        '"-profile:v", "high"',
        '"-bf", "2"',
        '"-flags", "+cgop"',
        '"-movflags", "+faststart"',
    ):
        assert setting in source
