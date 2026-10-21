from io import BytesIO
from PIL import Image, ImageDraw

import card_studio
import renderer


def test_language_font_and_style_options_structure():
    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_EN) == 11
    assert "Archivo Black" in renderer.MANUAL_SUBJECT_FONT_OPTIONS_EN
    assert "Russo One" in renderer.MANUAL_SUBJECT_FONT_OPTIONS_EN

    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_EN) == 11
    assert "Neon Pulse" in renderer.MANUAL_SUBJECT_STYLE_OPTIONS_EN
    assert "Deep Block" in renderer.MANUAL_SUBJECT_STYLE_OPTIONS_EN

    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_HI) == 3
    assert set(renderer.MANUAL_SUBJECT_FONT_OPTIONS_HI.keys()) == {
        "Noto Sans Devanagari", "Rozha One", "Yatra One"
    }

    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_HI) == 3
    assert renderer.MANUAL_SUBJECT_STYLE_OPTIONS_HI == ("Crisp Outline", "Heavy Drop", "Soft Halo")

    assert len(renderer.MANUAL_SUBJECT_FONT_OPTIONS_TE) == 3
    assert set(renderer.MANUAL_SUBJECT_FONT_OPTIONS_TE.keys()) == {
        "Noto Sans Telugu", "Ramabhadra", "Mandali"
    }

    assert len(renderer.MANUAL_SUBJECT_STYLE_OPTIONS_TE) == 3
    assert renderer.MANUAL_SUBJECT_STYLE_OPTIONS_TE == ("Crisp Outline", "Heavy Drop", "Soft Halo")


def test_hindi_text_subject_cutout_renders_all_three_hindi_fonts():
    img = Image.new("RGB", (1080, 1920), (30, 30, 30))
    polygon = ((100, 500), (980, 500), (980, 1100), (100, 1100))
    sample = "क्षेत्र की उपलब्धि"

    for font_name in ("Noto Sans Devanagari", "Rozha One", "Yatra One"):
        for style in ("Crisp Outline", "Heavy Drop", "Soft Halo"):
            preview_bytes = renderer.build_manual_subject_cutout_preview(
                img,
                sample,
                mode="negative-space",
                font_size=110,
                font=font_name,
                style=style,
                text_polygon=polygon,
            )
            result = Image.open(BytesIO(preview_bytes))
            assert result.size == (1080, 1920)


def test_telugu_text_subject_cutout_renders_all_three_telugu_fonts():
    img = Image.new("RGB", (1080, 1920), (30, 30, 30))
    polygon = ((100, 500), (980, 500), (980, 1100), (100, 1100))
    sample = "ప్రత్యేకమైన క్రీడాకారుడు"

    for font_name in ("Noto Sans Telugu", "Ramabhadra", "Mandali"):
        for style in ("Crisp Outline", "Heavy Drop", "Soft Halo"):
            preview_bytes = renderer.build_manual_subject_cutout_preview(
                img,
                sample,
                mode="negative-space",
                font_size=110,
                font=font_name,
                style=style,
                text_polygon=polygon,
            )
            result = Image.open(BytesIO(preview_bytes))
            assert result.size == (1080, 1920)


def test_english_text_subject_cutout_renders_new_fonts_and_styles():
    img = Image.new("RGB", (1080, 1920), (30, 30, 30))
    polygon = ((100, 500), (980, 500), (980, 1100), (100, 1100))
    sample = "CHAMPIONS TROPHY VICTORY"

    for font_name in ("Archivo Black", "Russo One"):
        for style in ("Neon Pulse", "Deep Block"):
            preview_bytes = renderer.build_manual_subject_cutout_preview(
                img,
                sample,
                mode="negative-space",
                font_size=110,
                font=font_name,
                style=style,
                text_polygon=polygon,
            )
            result = Image.open(BytesIO(preview_bytes))
            assert result.size == (1080, 1920)


def test_card_studio_renders_hindi_and_telugu_without_errors():
    img = Image.new("RGB", (1080, 1920), (45, 45, 45))
    
    # Hindi Stat Highlight
    stat_hi = card_studio.render_card("Stat Highlight", img, {
        "value": "100",
        "unit": "शतक",
        "headline": "विराट कोहली का शतक",
        "layout_position": "Bottom half",
    })
    assert len(stat_hi) > 0

    # Telugu Quote
    quote_te = card_studio.render_card("Quote / Reaction", img, {
        "quote": "ఇది నా కెరీర్‌లో అత్యంత ప్రత్యేకమైన క్షణం.",
        "attribution": "విరాట్ కోహ్లీ",
        "layout_position": "Bottom half",
    })
    assert len(quote_te) > 0


def test_indic_text_subject_cutout_multiline_spacing_no_overlap():
    # Multi-line Hindi and Telugu headlines must never have overlapping lines
    polygon = ((100, 200), (980, 200), (980, 1400), (100, 1400))
    hindi_headline = "भारत के प्रमुख सांस्कृतिक क्षेत्रों की उपलब्धियां"
    telugu_headline = "భారతదేశ ప్రధాన క్రీడాకారుల విజయం చరిత్రలో నిలిచింది"

    data_hi = renderer._manual_subject_cutout_layout_data(
        hindi_headline,
        polygon,
        font_size=80,
        font_name="Noto Sans Devanagari",
        style="Crisp Outline",
        polygon_flow=False,
    )
    assert data_hi["layouts"], "Expected at least one valid layout"
    layout_hi = data_hi["layouts"][0]
    placements_hi = layout_hi["placements"]
    assert len(placements_hi) >= 2, "Expected multi-line layout"
    for i in range(len(placements_hi) - 1):
        line_cur, top_cur, left_cur, bbox_cur = placements_hi[i]
        line_next, top_next, left_next, bbox_next = placements_hi[i + 1]
        cur_bottom = top_cur + (bbox_cur[3] - bbox_cur[1])
        # Next line top must be strictly below current line bottom (positive clearance)
        assert top_next >= cur_bottom, (
            f"Line overlap detected: line {i} bottom {cur_bottom} exceeds line {i+1} top {top_next}"
        )

    data_te = renderer._manual_subject_cutout_layout_data(
        telugu_headline,
        polygon,
        font_size=80,
        font_name="Noto Sans Telugu",
        style="Crisp Outline",
        polygon_flow=False,
    )
    assert data_te["layouts"], "Expected at least one valid layout"
    layout_te = data_te["layouts"][0]
    placements_te = layout_te["placements"]
    assert len(placements_te) >= 2, "Expected multi-line layout"
    for i in range(len(placements_te) - 1):
        line_cur, top_cur, left_cur, bbox_cur = placements_te[i]
        line_next, top_next, left_next, bbox_next = placements_te[i + 1]
        cur_bottom = top_cur + (bbox_cur[3] - bbox_cur[1])
        assert top_next >= cur_bottom, (
            f"Line overlap detected: line {i} bottom {cur_bottom} exceeds line {i+1} top {top_next}"
        )


def test_card_studio_draw_lines_indic_spacing():
    canvas = Image.new("RGB", (600, 600), (0, 0, 0))
    font_hi = card_studio._font_for_text("भारत", 48, card_studio._font_headline)
    lines_hi = ["भारत के प्रमुख", "सांस्कृतिक क्षेत्रों"]

    end_y = card_studio._draw_lines(canvas, lines_hi, 50, 100, font_hi, gap=5)
    # The total vertical height consumed must be larger than Latin "Ag" height * 2
    draw = ImageDraw.Draw(canvas)
    ag_box = draw.textbbox((0, 0), "Ag", font=font_hi)
    ag_height = ag_box[3] - ag_box[1]
    consumed_height = end_y - 100
    assert consumed_height > ag_height * 2, (
        f"Consumed height {consumed_height} should reflect full Indic metrics and gap, not Latin Ag"
    )


def test_top5_editorial_indic_body_line_spacing():
    headline = "CHAMPIONS UPDATE"
    body_hi = "भारत के प्रमुख सांस्कृतिक क्षेत्रों में आयोजित विशेष प्रतियोगिता की पूरी जानकारी"
    layout = renderer._top5_editorial_layout(
        headline=headline,
        body=body_hi,
        language="english",
        story_number=1,
    )
    assert layout["body_lines"]
    assert len(layout["body_lines"]) >= 2
    # Check that body height is sufficient for Indic lines
    font = layout["body_font"]
    ascent, descent = font.getmetrics()
    expected_min_height = (ascent + descent) * len(layout["body_lines"])
    assert layout["body_height"] >= expected_min_height * 0.9


def test_indic_subtitles_geometry_uses_metric_height():
    words = ("भारत", "के", "प्रमुख", "खिलाड़ी", "मैदान", "पर", "उतरे")
    font, line_lengths, _, line_heights, total_height = renderer._subtitle_render_geometry_cached(
        words,
        "hindi",
    )
    ascent, descent = font.getmetrics()
    metric_height = ascent + descent + renderer.SUBTITLE_STROKE_WIDTH * 2
    for lh in line_heights:
        assert lh >= metric_height, f"Subtitle line height {lh} must be at least metric height {metric_height}"

