from io import BytesIO
from PIL import Image

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
