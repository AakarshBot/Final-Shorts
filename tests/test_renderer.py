import inspect

import pytest
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

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

    polygon = ((100, 700), (900, 700), (900, 1500), (500, 1500))
    flowed = renderer._manual_subject_cutout_layout_data(
        "India win",
        polygon,
        120,
        "Barlow Condensed",
        "Crisp Outline",
        polygon_flow=True,
    )

    assert flowed["layouts"]
    layout = next(layout for layout in flowed["layouts"] if len(layout["lines"]) == 2)
    assert flowed["polygon_flow"] is True

    lefts = [placement[2] for placement in layout["placements"]]
    assert lefts[1] > lefts[0]


def test_manual_subject_cutout_polygon_half_screen_vertical_alignment(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    # Vertical left half of the screen
    polygon = ((0, 0), (540, 0), (540, 1920), (0, 1920))
    data = renderer._manual_subject_cutout_layout_data(
        "India dominate the final match today",
        polygon,
        120,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert data["layouts"]
    top_layout = data["layouts"][0]
    # Spans vertically down the half-screen column
    assert len(top_layout["lines"]) >= 3
    first_placement = top_layout["placements"][0]
    assert first_placement[1] == 2  # Starts 2px inside top boundary
    assert first_placement[2] == 2  # Starts 2px inside left boundary
    for _line, line_top, left, bbox in top_layout["placements"]:
        line_w = bbox[2] - bbox[0]
        assert left == 2
        assert left + line_w <= 538  # Stays inside right boundary of 540
        assert line_top + (bbox[3] - bbox[1]) <= 1918  # Stays inside bottom boundary


def test_manual_subject_cutout_polygon_bottom_half_vertical_bounds(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    # Bottom half of screen
    polygon = ((0, 960), (1080, 960), (1080, 1920), (0, 1920))
    data = renderer._manual_subject_cutout_layout_data(
        "India win the cricket world cup",
        polygon,
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert data["layouts"]
    layout = data["layouts"][0]
    assert layout["placements"][0][1] == 962  # Starts 2px inside top boundary of 960
    assert layout["placements"][0][2] == 2    # Starts 2px inside left boundary
    for _line, line_top, left, bbox in layout["placements"]:
        line_w = bbox[2] - bbox[0]
        assert left == 2
        assert left + line_w <= 1078
        assert line_top + (bbox[3] - bbox[1]) <= 1918


def test_manual_subject_cutout_polygon_adapts_to_irregular_end_to_end_shape(monkeypatch):
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    monkeypatch.setattr(
        renderer,
        "_manual_subject_font_bytes",
        lambda _font_name: font_path.read_bytes(),
    )

    # Triangle with tapered top
    polygon = ((540, 100), (900, 1000), (180, 1000))
    data = renderer._manual_subject_cutout_layout_data(
        "Cricket win today",
        polygon,
        120,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert data["layouts"]
    layout = data["layouts"][0]
    for _line, line_top, left, bbox in layout["placements"]:
        line_w = bbox[2] - bbox[0]
        assert left >= 182
        assert left + line_w <= 898
        assert line_top >= 102
        assert line_top + (bbox[3] - bbox[1]) <= 998


def test_manual_subject_cutout_uses_exact_font_size_without_retry(monkeypatch):
    sizes = []

    def no_layout(_headline, _polygon, font_size, *_args):
        sizes.append(font_size)
        return {"font_size": font_size, "layouts": []}

    monkeypatch.setattr(renderer, "_manual_subject_cutout_layout_data", no_layout)
    with pytest.raises(ValueError, match="Text size 150px"):
        renderer._draw_manual_subject_cutout(
            _test_base(),
            {
                "headline": "INDIA WINS",
                "mode": "behind-subject",
                "text_polygon": ((80, 700), (1000, 700), (1000, 1000), (80, 1000)),
                "font_size": 150,
                "font": "Barlow Condensed",
                "style": "Crisp Outline",
                "polygon_flow": True,
            },
        )
    assert sizes == [150]


def test_manual_subject_cutout_line_stretches_word_spacing_not_glyphs():
    font_path = Path(renderer.__file__).resolve().parent / "fonts" / "BarlowCondensed-Black.ttf"
    font = ImageFont.truetype(str(font_path), 80)
    image = Image.new("RGBA", (1080, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    line = "INDIA WINS"
    bbox = draw.textbbox((0, 0), line, font=font, stroke_width=4)

    renderer._draw_manual_subject_cutout_line(
        draw, line, 40, 100, bbox,
        font=font, fill=(255, 255, 255, 255), stroke_width=4,
        stroke_fill=(0, 0, 0, 255), target_width=700, stretch_spaces=True,
    )
    bounds = image.getchannel("A").getbbox()
    assert bounds is not None
    assert bounds[0] == 100
    assert 790 <= bounds[2] <= 802

    one_word_image = Image.new("RGBA", (1080, 240), (0, 0, 0, 0))
    one_word_draw = ImageDraw.Draw(one_word_image)
    one_word_bbox = one_word_draw.textbbox((0, 0), "INDIA", font=font, stroke_width=4)
    renderer._draw_manual_subject_cutout_line(
        one_word_draw, "INDIA", 40, 100, one_word_bbox,
        font=font, fill=(255, 255, 255, 255), stroke_width=4,
        stroke_fill=(0, 0, 0, 255), target_width=700, stretch_spaces=True,
    )
    one_word_bounds = one_word_image.getchannel("A").getbbox()
    assert one_word_bounds is not None
    assert one_word_bounds[2] - one_word_bounds[0] < 400


def test_manual_subject_cutout_layout_previews_do_not_shrink_font_size(monkeypatch):
    sizes = []

    def no_layout(_headline, _polygon, font_size, *_args):
        sizes.append(font_size)
        return {"font_size": font_size, "layouts": []}

    monkeypatch.setattr(renderer, "_manual_subject_cutout_layout_data", no_layout)
    with pytest.raises(ValueError, match="Text size 140px"):
        renderer.build_manual_subject_cutout_layout_previews(
            _test_base(),
            "INDIA WINS",
            mode="behind-subject",
            font_size=140,
            text_polygon=((80, 700), (1000, 700), (1000, 1000), (80, 1000)),
        )
    assert sizes == [140]


def test_visual_boundaries_follow_each_scene_audio_duration_even_when_a_card_hides_subtitles(monkeypatch, tmp_path):
    from io import BytesIO

    monkeypatch.setattr(renderer, "FPS", 2)
    audio_paths = []
    for number in range(1, 4):
        path = tmp_path / f"scene{number}.wav"
        path.write_bytes(b"audio")
        audio_paths.append(path)

    def image_bytes(color):
        buffer = BytesIO()
        Image.new("RGB", (1080, 1920), color).save(buffer, format="PNG")
        return buffer.getvalue()

    visuals = [
        {"bytes": image_bytes((200, 0, 0))},
        {
            "bytes": image_bytes((0, 0, 0)),
            "preview_bytes": image_bytes((245, 245, 245)),
            "manual_subject_cutout": {"headline": "A static card"},
        },
        {"bytes": image_bytes((0, 0, 200))},
    ]
    audio_scenes = [
        {"scene": 1, "path": str(audio_paths[0]), "duration": 0.5},
        {"scene": 2, "path": str(audio_paths[1]), "duration": 0.5},
        {"scene": 3, "path": str(audio_paths[2]), "duration": 0.5},
    ]
    drawn = []
    encoded_frames = []
    monkeypatch.setattr(renderer, "_animate_visual", lambda base, _t, _duration, _seed: base)

    def capture_frame(base_image, t, *_args, **_kwargs):
        drawn.append((base_image.getpixel((0, 0)), t))
        return base_image.convert("RGB").copy()

    monkeypatch.setattr(renderer, "render_frame", capture_frame)

    def capture_video(frames, path):
        encoded_frames.extend(list(frames))
        path.write_bytes(b"silent")
        return path

    monkeypatch.setattr(renderer, "write_preview_video", capture_video)
    monkeypatch.setattr(
        renderer,
        "_mux_audio",
        lambda _silent, _scenes, output: (output.write_bytes(b"final") or output),
    )

    output = tmp_path / "scene-boundaries.mp4"
    renderer.render_production_video(
        {
            "approved_for_audio": True,
            "language_used": "english",
            "script": [
                {"voiceover": "Opening line."},
                {"voiceover": "Card narration."},
                {"voiceover": "Final line."},
            ],
        },
        {
            "approved_for_visuals": True,
            "language": "english",
            "total_duration": 1.5,
            "scenes": audio_scenes,
        },
        TEST_SUBTITLE_DATA,
        visuals,
        output,
    )

    assert len(encoded_frames) == 3
    assert [frame.getpixel((0, 0)) for frame in encoded_frames] == [
        (200, 0, 0),
        (245, 245, 245),
        (0, 0, 200),
    ]
    # Slide 2 hides subtitles but still occupies its measured half-second. Slide 3
    # resumes subtitles on its own absolute timestamp, 1.0s into the same narration.
    assert drawn == [((200, 0, 0), 0.0), ((0, 0, 200), 1.0)]


def test_production_upload_encode_settings_are_youtube_ready():
    assert renderer.FPS == 30


def test_renderer_frame_is_vertical_and_independent():
    base = _test_base()
    frame = renderer.render_frame(base, 0.9)

    assert frame.size == (1080, 1920)
    assert frame.mode == "RGB"
    assert frame is not base


def test_dashboard_headline_is_not_part_of_rendering_contract():
    assert "headline_text" not in inspect.signature(renderer.render_frame).parameters
    assert "headline_enabled" not in inspect.signature(renderer.render_frame).parameters
    assert "headline_text" not in inspect.signature(renderer.render_production_video).parameters
    assert "headline_enabled" not in inspect.signature(renderer.render_production_video).parameters
    assert not hasattr(renderer, "_draw_headline")

    renderer_source = Path(renderer.__file__).read_text(encoding="utf-8")
    assert "_draw_headline" not in renderer_source
    assert "HEADLINE_SECONDS" not in renderer_source

    base = _test_base()
    frame = renderer.render_frame(base, 0.30, source_enabled=False)
    assert ImageChops.difference(base, frame).getbbox() is None


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
    )
    bbox = ImageChops.difference(base, frame).getbbox()

    assert bbox is not None
    assert bbox[0] >= renderer.SUBTITLE_SAFE_MARGIN
    assert bbox[2] <= renderer.WIDTH - renderer.SUBTITLE_SAFE_MARGIN


def test_subtitles_follow_requested_frame_time_without_headline_delay(monkeypatch):
    seen = []

    def fake_draw(base, subtitle_data, t):
        seen.append(t)

    monkeypatch.setattr(renderer, "_draw_subtitles", fake_draw)
    base = _test_base()

    renderer.render_frame(base, 0.30)
    renderer.render_frame(base, 1.65)

    assert seen == [0.30, 1.65]


def test_subtitle_style_and_brand_colors_remain_consistent():
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
    assert seen[0][1].get("source_label") is None
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

    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_EN) == 11
    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_EN) == 11
    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_HI) == 3
    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_HI) == 3
    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_TE) == 3
    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_TE) == 3
    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS) == 17
    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS) == 11

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
        for name in ("Bebas Neue", "Teko", "Khand", "Kanit", "Fjalla One", "Archivo Black", "Russo One", "Rozha One", "Yatra One", "Ramabhadra", "Mandali")
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


def test_mux_audio_uses_one_continuous_chatterbox_master_when_available(monkeypatch, tmp_path):
    silent_video = tmp_path / "silent.mp4"
    silent_video.write_bytes(b"video")
    master = tmp_path / "full.wav"
    master.write_bytes(b"continuous master")
    slide_one = tmp_path / "slide_01.wav"
    slide_two = tmp_path / "slide_02.wav"
    slide_one.write_bytes(b"slice one")
    slide_two.write_bytes(b"slice two")
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
        [
            {"scene": 1, "path": str(slide_one), "continuous_master_path": str(master)},
            {"scene": 2, "path": str(slide_two), "continuous_master_path": str(master)},
        ],
        output,
    )

    assert result == output
    command = seen["command"]
    input_paths = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "-i"
    ]
    assert input_paths == [str(silent_video), str(master)]
    filter_value = command[command.index("-filter_complex") + 1]
    assert filter_value == "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    assert "concat=n=" not in filter_value


def test_mux_audio_falls_back_to_scene_files_when_one_continuous_slice_is_overridden(monkeypatch, tmp_path):
    silent_video = tmp_path / "silent.mp4"
    silent_video.write_bytes(b"video")
    master = tmp_path / "full.wav"
    master.write_bytes(b"continuous master")
    generated_slice = tmp_path / "slide_01.wav"
    human_override = tmp_path / "human_override.mp3"
    generated_slice.write_bytes(b"generated slice")
    human_override.write_bytes(b"human audio")
    output = tmp_path / "output.mp4"
    seen = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        return Result()

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    renderer._mux_audio(
        silent_video,
        [
            {"scene": 1, "path": str(generated_slice), "continuous_master_path": str(master)},
            {"scene": 2, "path": str(human_override), "human_recorded": True},
        ],
        output,
    )

    command = seen["command"]
    input_paths = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "-i"
    ]
    assert input_paths == [str(silent_video), str(generated_slice), str(human_override)]
    filter_value = command[command.index("-filter_complex") + 1]
    assert "concat=n=2:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[a]" in filter_value
    assert str(master) not in input_paths


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


def test_final_renderer_refuses_audio_at_30_seconds(tmp_path):
    import renderer

    audio_path = tmp_path / "lead.mp3"
    audio_path.write_bytes(b"x" * 700)
    visual_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual_buffer, format="PNG")

    with pytest.raises(ValueError, match="strictly under 30 seconds"):
        renderer.render_production_video(
            {
                "approved_for_audio": True,
                "language_used": "english",
                "script": [{"voiceover": "The Short must stay within its limit."}],
            },
            {
                "approved_for_visuals": True,
                "language": "english",
                "scenes": [{"scene": 1, "path": str(audio_path), "duration": 30.0}],
            },
            TEST_SUBTITLE_DATA,
            [{"bytes": visual_buffer.getvalue()}],
            tmp_path / "too-long.mp4",
        )


def test_final_renderer_refuses_hindi_lead_over_5_2_seconds(tmp_path):
    import renderer

    audio_path = tmp_path / "lead.mp3"
    audio_path.write_bytes(b"x" * 700)
    visual_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual_buffer, format="PNG")

    with pytest.raises(ValueError, match="Hindi Slide 1 audio is 5.21s"):
        renderer.render_production_video(
            {
                "approved_for_audio": True,
                "language_used": "hindi",
                "script": [{"voiceover": "भारत की टीम तैयार है।"}],
            },
            {
                "approved_for_visuals": True,
                "language": "hindi",
                "scenes": [{"scene": 1, "path": str(audio_path), "duration": 5.21}],
            },
            TEST_SUBTITLE_DATA,
            [{"bytes": visual_buffer.getvalue()}],
            tmp_path / "long-indic-lead.mp4",
        )


def test_final_renderer_quality_contract():
    import inspect
    import renderer

    source = inspect.getsource(renderer.write_preview_video)
    assert renderer.FPS == 30
    assert renderer._motion_profile("same") == renderer._motion_profile("same")
    assert renderer._motion_profile("visual-a") != renderer._motion_profile("visual-b")
    for setting in (
        '"-preset", "veryfast"',
        '"-crf", "18"',
        '"-profile:v", "high"',
        '"-bf", "2"',
        '"-flags", "+cgop"',
        '"-movflags", "+faststart"',
    ):
        assert setting in source


def test_short_motion_profiles_offer_ten_stable_story_paths():
    profiles = [
        renderer._motion_profile(f"story-scene-{index}")
        for index in range(250)
    ]

    assert {profile[0] for profile in profiles} == set(range(10))
    assert renderer._motion_profile("same story beat") == renderer._motion_profile("same story beat")
    for _mode, start_scale, end_scale, x_direction, y_direction in profiles:
        assert 1.025 <= start_scale <= 1.065
        assert 1.075 <= end_scale <= 1.125
        assert end_scale > start_scale
        assert x_direction in {-1, 1}
        assert y_direction in {-1, 1}


def test_standard_short_motion_seed_uses_spoken_scene_and_angle(monkeypatch, tmp_path):
    captured = {}
    audio_path = tmp_path / "lead.mp3"
    audio_path.write_bytes(b"x" * 700)
    output = tmp_path / "story-aware.mp4"
    image = Image.new("RGB", (1080, 1920), "white")
    ImageDraw.Draw(image).rectangle((110, 220, 880, 1450), fill="navy")
    visual_buffer = BytesIO()
    image.save(visual_buffer, format="PNG")

    def fake_animate(source, t, duration, seed):
        captured["seed"] = seed
        return source.copy()

    def fake_preview(frames, path):
        next(iter(frames))
        path.write_bytes(b"silent")
        return path

    def fake_mux(silent_path, scenes, output_path):
        output_path.write_bytes(b"final")
        return output_path

    monkeypatch.setattr(renderer, "_animate_visual", fake_animate)
    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)

    result = renderer.render_production_video(
        {
            "approved_for_audio": True,
            "language_used": "english",
            "source_title": "India's tactical collapse",
            "story_angle": "the field change that shifted the chase",
            "script": [{"voiceover": "The captain moved a fielder after the second boundary."}],
        },
        {
            "approved_for_visuals": True,
            "language": "english",
            "total_duration": 1.0,
            "scenes": [{"scene": 1, "path": str(audio_path), "duration": 1.0}],
        },
        TEST_SUBTITLE_DATA,
        [{
            "bytes": visual_buffer.getvalue(),
            "primary_entity": "India captain",
            "visual_intent": "field placement change",
            "specific_search_prompt": "India captain adjusts field in cricket match",
            "sport_or_topic_category": "Cricket",
            "source": "Sports Desk",
        }],
        output,
    )

    assert result == output
    assert output.read_bytes() == b"final"
    assert "India's tactical collapse" in captured["seed"]
    assert "the field change that shifted the chase" in captured["seed"]
    assert "The captain moved a fielder after the second boundary." in captured["seed"]
    assert "scene:1" in captured["seed"]


@pytest.mark.parametrize(
    ("language", "sample", "font_name"),
    [
        ("hindi", "क्षेत्र की उपलब्धि", "NotoSansDevanagari-Bold.ttf"),
        ("telugu", "ప్రత్యేకమైన క్రీడాకారుడు", "NotoSansTelugu-Bold.ttf"),
    ],
)
def test_indic_renderer_font_paths_use_bundled_noto_and_raqm(language, sample, font_name):
    if not renderer.features.check_feature("raqm"):
        with pytest.raises(RuntimeError, match="RAQM text-shaping engine"):
            renderer._renderer_font_for_text(sample, 96, language)
        return

    font = renderer._renderer_font_for_text(sample, 96, language)
    assert Path(font.path).name == font_name
    assert font.layout_engine == ImageFont.Layout.RAQM
    assert font.getmask(sample).getbbox() is not None

    top5_font = renderer._top5_headline_font_stack(72, language)[0]
    assert Path(top5_font.path).name == font_name
    assert top5_font.layout_engine == ImageFont.Layout.RAQM
    assert top5_font.getmask(sample).getbbox() is not None

    top5_body_font = renderer._top5_body_font(36, language)
    assert Path(top5_body_font.path).name == font_name
    assert top5_body_font.layout_engine == ImageFont.Layout.RAQM
    assert top5_body_font.getmask(sample).getbbox() is not None

    subtitle_font, _line_lengths, _measurements, _heights, _total = (
        renderer._subtitle_render_geometry_cached(tuple(sample.split()), language)
    )
    assert Path(subtitle_font.path).name == font_name
    assert subtitle_font.layout_engine == ImageFont.Layout.RAQM
    assert subtitle_font.getmask(sample).getbbox() is not None


@pytest.mark.parametrize(
    ("sample", "font_name"),
    [
        ("क्षेत्र की उपलब्धि", "NotoSansDevanagari-Bold.ttf"),
        ("ప్రత్యేకమైన క్రీడాకారుడు", "NotoSansTelugu-Bold.ttf"),
    ],
)
def test_text_subject_cutout_uses_script_specific_noto_font(sample, font_name):
    if not renderer.features.check_feature("raqm"):
        with pytest.raises(RuntimeError, match="RAQM text-shaping engine"):
            renderer._manual_subject_cutout_layout_data(
                sample,
                ((60, 600), (1020, 600), (1020, 1450), (60, 1450)),
                120,
                "Barlow Condensed",
                "Crisp Outline",
            )
        return

    data = renderer._manual_subject_cutout_layout_data(
        sample,
        ((60, 600), (1020, 600), (1020, 1450), (60, 1450)),
        120,
        "Barlow Condensed",
        "Crisp Outline",
    )
    assert data["font"].layout_engine == ImageFont.Layout.RAQM
    assert data["font_data"] == (
        Path(renderer.__file__).resolve().parent / "fonts" / font_name
    ).read_bytes()
    assert data["layouts"]


def test_production_render_does_not_fail_when_windows_locks_silent_intermediate(
    monkeypatch, tmp_path
):
    audio_file = tmp_path / "scene1.mp3"
    audio_file.write_bytes(b"audio")
    visual_buffer = BytesIO()
    Image.new("RGB", (1080, 1920), "white").save(visual_buffer, format="PNG")
    locked_paths = []

    def fake_preview(frames, path):
        list(frames)
        path.write_bytes(b"silent")
        locked_paths.append(path)
        return path

    def fake_mux(silent_video, audio_scenes, output):
        assert silent_video.exists()
        output.write_bytes(b"final")
        return output

    original_unlink = Path.unlink

    def simulate_windows_lock(path, *args, **kwargs):
        if path in locked_paths:
            raise PermissionError(
                32,
                "The process cannot access the file because it is being used by another process",
                str(path),
            )
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(renderer, "write_preview_video", fake_preview)
    monkeypatch.setattr(renderer, "_mux_audio", fake_mux)
    monkeypatch.setattr(Path, "unlink", simulate_windows_lock)

    output = tmp_path / "final.mp4"
    with pytest.warns(RuntimeWarning, match="temporary silent video could not be deleted"):
        result = renderer.render_production_video(
            {"approved_for_audio": True, "script": [{"voiceover": "A spoken line."}]},
            {"approved_for_visuals": True, "scenes": [{"scene": 1, "duration": 1.0, "path": str(audio_file)}]},
            TEST_SUBTITLE_DATA,
            [{"bytes": visual_buffer.getvalue()}],
            output,
        )

    assert result == output
    assert output.read_bytes() == b"final"
    assert len(locked_paths) == 1
    assert locked_paths[0].exists()
    assert ".silent.mp4" in locked_paths[0].name
    assert locked_paths[0].name != f"{output.stem}.silent.mp4"


def test_windows_fribidi_bootstrap_runs_existing_no_pip_powershell_installer(monkeypatch, tmp_path):
    script = tmp_path / "setup_windows_indic_rendering.ps1"
    script.write_text("# mocked setup script", encoding="utf-8")
    captured = {}

    class ProcessResult:
        returncode = 0
        stdout = "FriBiDi package checksum verified."
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        dll_dir = tmp_path / "dlls"
        license_dir = dll_dir
        dll_dir.mkdir(parents=True, exist_ok=True)
        (dll_dir / "libfribidi-0.dll").write_bytes(b"D" * 20_000)
        (license_dir / "FRIBIDI-COPYING.txt").write_text("LGPL-2.1-or-later", encoding="ascii")
        return ProcessResult()

    monkeypatch.setattr(renderer.shutil, "which", lambda name: "powershell.exe" if name == "powershell.exe" else None)
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    renderer._install_windows_fribidi_via_powershell(tmp_path)

    command = captured["command"]
    assert command[0] == "powershell.exe"
    assert command[1:5] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    assert command[5] == str(script)
    assert "pip" not in " ".join(command).casefold()
    assert captured["kwargs"]["timeout"] == 180
    assert (tmp_path / "dlls" / "libfribidi-0.dll").stat().st_size == 20_000
    assert (tmp_path / "dlls" / "FRIBIDI-COPYING.txt").is_file()


def test_windows_fribidi_bootstrap_surfaces_checksum_failure_without_accepting_dll(monkeypatch, tmp_path):
    script = tmp_path / "setup_windows_indic_rendering.ps1"
    script.write_text("# mocked setup script", encoding="utf-8")

    class ProcessResult:
        returncode = 1
        stdout = "Trying trusted MSYS2 mirrors"
        stderr = "No checksum-verified FriBiDi package was obtained."

    monkeypatch.setattr(renderer.shutil, "which", lambda name: "powershell.exe" if name == "powershell.exe" else None)
    monkeypatch.setattr(renderer.subprocess, "run", lambda *_args, **_kwargs: ProcessResult())

    with pytest.raises(RuntimeError, match="No checksum-verified FriBiDi package was obtained"):
        renderer._install_windows_fribidi_via_powershell(tmp_path)

    assert not (tmp_path / "dlls" / "libfribidi-0.dll").exists()


def test_raqm_runtime_probe_catches_true_feature_flag_with_broken_font_load(monkeypatch):
    monkeypatch.setattr(renderer.features, "check_feature", lambda _feature: True)

    def broken_font(*_args, **_kwargs):
        raise OSError("libfribidi DLL load failed")

    monkeypatch.setattr(renderer.ImageFont, "truetype", broken_font)

    available, reason = renderer._raqm_runtime_probe("hindi")

    assert not available
    assert "real RAQM font-load/shaping test failed" in reason
    assert "libfribidi DLL load failed" in reason


def test_windows_fribidi_installer_has_checksum_verified_zstd_fallback():
    script_path = Path(renderer.__file__).resolve().with_name("setup_windows_indic_rendering.ps1")
    source = script_path.read_text(encoding="utf-8")

    assert "zstd-v1.5.7-win64.zip" in source
    assert "Get-FileHash -Path $ZstdZipPath -Algorithm SHA512" in source
    assert "$ExpectedSha256 = " in source
    assert "$ZstdZipSha512 = " in source
    assert "if (-not $Extracted)" in source
    assert "No Python packages were installed" in source


def test_windows_indic_installer_has_a_checksum_pinned_zstd_fallback():
    script_path = Path(renderer.__file__).resolve().parent / "setup_windows_indic_rendering.ps1"
    script = script_path.read_text(encoding="utf-8")

    # Older Windows tar.exe builds cannot always unpack .tar.zst. The fallback
    # must remain pinned and verified; do not silently accept a downloaded tool.
    assert '$ExpectedSha256 = "3581ee03cf83a9bb0e98bf688c4f532a29553500e317532d90746de295b0f8a8"' in script
    assert '$ZstdZipSha512 = "a96dc5417943c03fa231bf2d6a586b7ae7254fa52fdc15d302f296b5ff88e1ff0f07120a720149eb82ea0f0c65444393ebf05d2ee1bd1db341b803ff65a2e675"' in script
    assert "Get-FileHash -Path $ZstdZipPath -Algorithm SHA512" in script
    assert "Get-FileHash -Path $PackagePath -Algorithm SHA256" in script
    assert "& $ZstdExe.FullName -d -q -f -o $TarPath $PackagePath" in script


def test_indic_raqm_error_explains_actual_shaping_and_automatic_bootstrap(monkeypatch):
    monkeypatch.setattr(renderer.features, "check_feature", lambda _feature: False)
    monkeypatch.setattr(renderer.os, "name", "posix")
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: (False, "Pillow reports no RAQM"))
    with pytest.raises(RuntimeError, match="compiled RAQM support"):
        renderer._require_raqm("hindi")


def test_windows_raqm_bootstrap_rechecks_real_font_after_install(monkeypatch):
    calls = []
    probes = iter([
        (False, "FriBiDi could not be loaded by Pillow"),
        (True, ""),
    ])

    monkeypatch.setattr(renderer.os, "name", "nt")
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_register_windows_dll_paths", lambda: None)
    monkeypatch.setattr(renderer, "_activate_windows_fribidi", lambda: "")
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: next(probes))
    monkeypatch.setattr(
        renderer,
        "_install_windows_fribidi_via_powershell",
        lambda: calls.append("installed"),
    )

    renderer._require_raqm("hindi")

    assert calls == ["installed"]


def test_windows_raqm_bootstraps_when_feature_flag_is_true_but_real_font_fails(monkeypatch):
    calls = []
    probes = iter([
        (False, "RAQM font-load/shaping test failed: cannot load FriBiDi"),
        (True, ""),
    ])
    monkeypatch.setattr(renderer.os, "name", "nt")
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_register_windows_dll_paths", lambda: None)
    monkeypatch.setattr(renderer, "_activate_windows_fribidi", lambda: "")
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: next(probes))
    monkeypatch.setattr(
        renderer,
        "_install_windows_fribidi_via_powershell",
        lambda: calls.append("installed"),
    )

    renderer._require_raqm("telugu")

    assert calls == ["installed"]


def test_windows_raqm_uses_bundled_pillow_when_feature_exists_but_shaping_fails(
    monkeypatch, tmp_path
):
    calls = []
    shape_error = "The real RAQM font-load/shaping test failed: cannot load FriBiDi"
    target = tmp_path / ".deps" / "raqm_pillow_11_3_0_cp311"

    monkeypatch.setattr(renderer.os, "name", "nt")
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_READY_FOR_RESTART", False)
    monkeypatch.setattr(renderer, "_register_windows_dll_paths", lambda: None)
    monkeypatch.setattr(renderer, "_activate_windows_fribidi", lambda: "")
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: (False, shape_error))
    monkeypatch.setattr(
        renderer,
        "_install_windows_fribidi_via_powershell",
        lambda: calls.append("fribidi"),
    )
    monkeypatch.setattr(
        renderer,
        "_install_raqm_enabled_pillow",
        lambda: calls.append("pillow-wheel") or target,
    )

    with pytest.raises(RuntimeError, match="compiled with vendored RAQM"):
        renderer._require_raqm("hindi")

    assert calls == ["fribidi", "pillow-wheel"]
    assert renderer._WINDOWS_RAQM_PILLOW_READY_FOR_RESTART is True


def test_windows_raqm_bootstrap_surfaces_the_setup_failure_details(monkeypatch):
    monkeypatch.setattr(renderer.os, "name", "nt")
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_register_windows_dll_paths", lambda: None)
    monkeypatch.setattr(renderer, "_activate_windows_fribidi", lambda: "")
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: (False, "Pillow reports no RAQM"))
    monkeypatch.setattr(
        renderer,
        "_install_windows_fribidi_via_powershell",
        lambda: (_ for _ in ()).throw(RuntimeError("all trusted MSYS2 sources failed checksum verification")),
    )

    with pytest.raises(RuntimeError, match="all trusted MSYS2 sources failed checksum verification"):
        renderer._require_raqm("hindi")


def test_isolated_raqm_pillow_bootstrap_precedes_normal_pil_import(monkeypatch, tmp_path):
    target = tmp_path / ".deps" / "raqm_pillow_11_3_0_cp311"
    package = target / "PIL"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "_imagingft.cp311-win_amd64.pyd").write_bytes(b"test extension")
    (target / "python_executable.txt").write_text(str(renderer.sys.executable), encoding="utf-8")

    monkeypatch.setattr(renderer.sys, "path", list(renderer.sys.path))
    assert renderer._activate_bundled_raqm_pillow(tmp_path)
    assert renderer.sys.path[0] == str(target.resolve())


def test_isolated_raqm_pillow_installer_uses_checksum_verified_factory_wheel(monkeypatch, tmp_path):
    import hashlib
    import zipfile

    wheel_name = "pillow-11.3.0-cp311-cp311-win_amd64.whl"
    wheel_buffer = BytesIO()
    with zipfile.ZipFile(wheel_buffer, "w") as wheel:
        wheel.writestr("PIL/__init__.py", "")
        wheel.writestr("PIL/features.py", "# mocked package")
        wheel.writestr("PIL/_imagingft.cp311-win_amd64.pyd", b"test extension")
    wheel_bytes = wheel_buffer.getvalue()
    wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
    requested = []

    def fake_urlopen(url, timeout=0):
        requested.append((url, timeout))
        if url.endswith(".whl.sha256"):
            return BytesIO(f"{wheel_sha256}  {wheel_name}\n".encode("ascii"))
        assert url.endswith(wheel_name)
        return BytesIO(wheel_bytes)

    class ProcessResult:
        returncode = 0
        stdout = ""
        stderr = ""

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return ProcessResult()

    monkeypatch.setattr(renderer, "urlopen", fake_urlopen)
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer.sys, "version_info", (3, 11, 9, "final", 0))
    monkeypatch.setattr(renderer.sysconfig, "get_platform", lambda: "win-amd64")

    target = renderer._install_raqm_enabled_pillow(tmp_path)

    assert target == tmp_path / ".deps" / "raqm_pillow_11_3_0_cp311"
    assert len(requested) == 2
    assert requested[0][0].endswith(f"/{wheel_name}")
    assert requested[1][0].endswith(f"/{wheel_name}.sha256")
    assert (target / "PIL" / "_imagingft.cp311-win_amd64.pyd").is_file()
    assert "os.add_dll_directory" in (target / "sitecustomize.py").read_text(encoding="utf-8")
    assert (target / "python_executable.txt").read_text(encoding="utf-8") == str(renderer.sys.executable)
    assert captured["command"][:3] == [str(renderer.sys.executable), "-I", "-S"]
    assert "PYTHONPATH" not in captured["kwargs"]["env"]
    assert "PYTHONHOME" not in captured["kwargs"]["env"]
    assert "NotoSansDevanagari-Bold.ttf" in captured["command"][-1]
    assert "NotoSansTelugu-Bold.ttf" in captured["command"][-1]
    assert "font.layout_engine == ImageFont.Layout.RAQM" in captured["command"][-1]


def test_raqm_pillow_installer_rejects_bad_checksum(monkeypatch, tmp_path):
    def fake_urlopen(url, timeout=0):
        if url.endswith(".whl.sha256"):
            return BytesIO((("0" * 64) + "  wheel\n").encode("ascii"))
        return BytesIO(b"not-a-wheel")

    monkeypatch.setattr(renderer, "urlopen", fake_urlopen)
    monkeypatch.setattr(renderer.sys, "version_info", (3, 11, 9, "final", 0))
    monkeypatch.setattr(renderer.sysconfig, "get_platform", lambda: "win-amd64")

    with pytest.raises(RuntimeError, match="failed SHA-256 verification"):
        renderer._install_raqm_enabled_pillow(tmp_path)

    assert not (tmp_path / ".deps" / "raqm_pillow_11_3_0_cp311" / "python_executable.txt").exists()


def test_windows_raqm_prepare_isolated_pillow_when_active_build_has_no_raqm(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer.os, "name", "nt")
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_FRIBIDI_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED", False)
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_INSTALL_ERROR", "")
    monkeypatch.setattr(renderer, "_WINDOWS_RAQM_PILLOW_READY_FOR_RESTART", False)
    monkeypatch.setattr(renderer, "_register_windows_dll_paths", lambda: None)
    monkeypatch.setattr(renderer, "_activate_windows_fribidi", lambda: "")
    monkeypatch.setattr(renderer, "_install_windows_fribidi_via_powershell", lambda: None)
    monkeypatch.setattr(renderer, "_raqm_runtime_probe", lambda _language: (False, "This Pillow build does not report RAQM support."))
    installed = []
    monkeypatch.setattr(
        renderer,
        "_install_raqm_enabled_pillow",
        lambda: installed.append("isolated-wheel") or (tmp_path / ".deps" / "raqm_pillow_11_3_0_cp311"),
    )

    with pytest.raises(RuntimeError, match="Run_Final_Shorts.bat"):
        renderer._require_raqm("hindi")

    assert installed == ["isolated-wheel"]
    assert renderer._WINDOWS_RAQM_PILLOW_READY_FOR_RESTART is True


def test_windows_fribidi_installer_skips_overwrite_when_existing_dll_is_loaded():
    script_path = Path(renderer.__file__).resolve().with_name("setup_windows_indic_rendering.ps1")
    script = script_path.read_text(encoding="utf-8")

    assert '$SourceDllHash = (Get-FileHash -Path $SourceDll -Algorithm SHA256).Hash.ToLowerInvariant()' in script
    assert '$TargetDllHash -eq $SourceDllHash' in script
    assert "leaving it in place" in script
    assert "Close every Final-Shorts / Streamlit process" in script


def test_final_renderer_refuses_overlength_top5_handoff_before_preparing_visuals(tmp_path):
    import renderer

    script = {
        "schema": "final-shorts.top5-script.v1",
        "approved_for_audio": True,
        "slides": [{"slide_number": number} for number in range(1, 7)],
    }
    audio = {
        "approved_for_visuals": True,
        "total_duration": 30.1,
        "scenes": [
            {"scene": number, "duration": 5.0, "path": "unused"}
            for number in range(1, 7)
        ],
    }

    with pytest.raises(ValueError, match="strictly under 30 seconds"):
        renderer.render_production_video(
            script,
            audio,
            None,
            [{} for _ in range(6)],
            tmp_path / "overlength-top5.mp4",
        )

