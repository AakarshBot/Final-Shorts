from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont, features

import card_studio


def _image_bytes(color=(52, 84, 118), size=(900, 1600)):
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _renderable_card_data(card_type, language="english"):
    data = card_studio.card_data_for_type(card_type, language=language)
    if card_type == "Stat Highlight":
        data.update({
            "headline": "Career Test wicket record",
            "value": "704",
            "unit": "WICKETS",
            "supporting_fields": [
                {"label": "International career", "value": "1994–2015"},
                {"label": "Test appearances", "value": "166"},
            ],
        })
    elif card_type == "Quote / Reaction":
        data.update({
            "quote": "We kept believing until the final ball.",
            "attribution": "Player name",
            "supporting_fields": [],
        })
    elif card_type == "Head-to-Head":
        data.update({
            "headline": "Career comparison",
            "left": {"name": "James Anderson", "values": {}},
            "right": {"name": "Stuart Broad", "values": {}},
            "metrics": [
                {"label": "Test wickets", "left_value": "704", "right_value": "604"},
                {"label": "Test matches", "left_value": "188", "right_value": "167"},
            ],
        })
    elif card_type == "Key Fact / Milestone":
        data.update({
            "value": "704",
            "label": "Test wickets",
            "supporting_fields": [{"label": "Format", "value": "Test cricket"}],
        })
    return data


def test_bottom_gradient_starts_below_the_main_portrait_zone():
    image = Image.new("RGB", (1080, 1920), (175, 100, 70))
    result = card_studio._contrast_bed(image, "bottom", "Soft gradient").convert("RGB")
    assert result.getpixel((540, 990)) == image.getpixel((540, 990))
    assert result.getpixel((540, 1300)) != image.getpixel((540, 1300))


def test_auto_text_zone_uses_texture_when_no_subject_mask_is_available():
    image = Image.new("RGB", (1080, 1920), (80, 80, 80))
    draw = ImageDraw.Draw(image)
    for x in range(660, 850, 8):
        draw.line((x, 190, x, 1480), fill=(240, 240, 240), width=4)
    assert card_studio._choose_text_side(image, None) == "left"


def test_card_studio_outputs_1080x1920_png():
    for card_type in (
        "Stat Highlight",
        "Quote / Reaction",
        "Head-to-Head",
        "Key Fact / Milestone",
    ):
        output = card_studio.render_card(
            card_type,
            _image_bytes(),
            _renderable_card_data(card_type),
        )
        with Image.open(BytesIO(output)) as image:
            assert image.size == (1080, 1920)
            assert image.format == "PNG"


def test_card_studio_defaults_fill_every_wip_field():
    for card_type in (
        "Stat Highlight",
        "Quote / Reaction",
        "Head-to-Head",
        "Key Fact / Milestone",
    ):
        defaults = card_studio.card_data_for_type(card_type)
        assert defaults["layout_position"] == "Auto · Best negative space"
        assert defaults["contrast_treatment"] == "Adaptive gradient"

    stat = card_studio.card_data_for_type("Stat Highlight")
    assert stat["value"] == ""
    assert stat["headline"] == ""
    assert stat["unit"] == ""
    assert stat["supporting_fields"] == []

    quote = card_studio.card_data_for_type("Quote / Reaction")
    assert quote["quote"] == ""
    assert quote["attribution"] == ""
    assert quote["supporting_fields"] == []
    assert "context" not in quote

    head_to_head = card_studio.card_data_for_type("Head-to-Head")
    assert head_to_head["image_mode"] == "One image"
    assert head_to_head["left"]["name"] == ""
    assert head_to_head["right"]["name"] == ""
    assert head_to_head["metrics"] == []

    milestone = card_studio.card_data_for_type("Key Fact / Milestone")
    assert milestone["value"] == ""
    assert milestone["label"] == ""
    assert milestone["supporting_fields"] == []


def test_recropping_source_invalidates_cached_card_results_for_all_source_images():
    state = {
        "test-card-studio-result": {
            "bytes": b"old-render",
            "source_key": "asset-primary",
            "source_keys": ["asset-primary"],
        },
        "test-head-to-head-result": {
            "bytes": b"old-two-image-render",
            "source_key": "asset-primary",
            "source_keys": ["asset-primary", "asset-secondary"],
        },
        "test-unrelated-card-result": {
            "bytes": b"keep",
            "source_key": "other-asset",
            "source_keys": ["other-asset"],
        },
        "visual_result": {"assets": []},
    }

    invalidated = card_studio.invalidate_card_studio_results_for_source(
        state, "asset-secondary"
    )

    assert invalidated == 1
    assert state["test-head-to-head-result"] is None
    assert state["test-card-studio-result"]["bytes"] == b"old-render"
    assert state["test-unrelated-card-result"]["bytes"] == b"keep"
    assert state["visual_result"] == {"assets": []}


def test_all_editorial_cards_support_manual_photo_compositions():
    for card_type in (
        "Stat Highlight",
        "Quote / Reaction",
        "Head-to-Head",
        "Key Fact / Milestone",
    ):
        for position in card_studio.CARD_LAYOUT_POSITIONS:
            data = _renderable_card_data(card_type)
            data["layout_position"] = position
            data["contrast_treatment"] = "Soft gradient"
            output = card_studio.render_card(card_type, _image_bytes(), data)
            with Image.open(BytesIO(output)) as image:
                assert image.size == (1080, 1920)
                assert image.format == "PNG"


def test_changed_composition_invalidates_a_stale_rendered_preview():
    state = {
        "card-result": {
            "bytes": b"old-render",
            "type": "Quote / Reaction",
            "data": {
                "layout_position": "Left half",
                "contrast_treatment": "Soft gradient",
            },
        }
    }

    changed = card_studio.invalidate_card_studio_result_for_composition(
        state,
        "card-result",
        "Quote / Reaction",
        "Bottom half",
        "Soft gradient",
    )

    assert changed is True
    assert state["card-result"] is None


def test_contrast_treatments_are_manual_and_visually_distinct():
    image = Image.new("RGB", (1080, 1920), (175, 100, 70))
    soft = card_studio._contrast_bed(image, "left", "Soft gradient")
    deep = card_studio._contrast_bed(image, "left", "Deep gradient")
    panel = card_studio._contrast_bed(image, "left", "Editorial panel")

    assert soft.getpixel((140, 800)) != deep.getpixel((140, 800))
    assert panel.getpixel((100, 300)) != soft.getpixel((100, 300))
    assert soft.getpixel((1010, 800))[:3] == image.getpixel((1010, 800))


def test_quote_reaction_uses_editorial_layout_with_subject_aware_placement():
    mask = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(mask).rectangle((88, 220, 620, 1300), fill=255)
    data = _renderable_card_data("Quote / Reaction")

    output = card_studio.render_card(
        "Quote / Reaction",
        _image_bytes(),
        data,
        subject_mask=mask,
    )

    with Image.open(BytesIO(output)) as image:
        assert image.size == (1080, 1920)
        assert image.getbbox() is not None


def test_head_to_head_supports_two_images_with_manual_split_direction():
    left = _image_bytes((180, 60, 60))
    right = _image_bytes((60, 80, 180))
    data = _renderable_card_data("Head-to-Head")
    data["image_mode"] = "Two images"

    left_mask = Image.new("L", (900, 1600), 0)
    right_mask = Image.new("L", (900, 1600), 0)
    ImageDraw.Draw(left_mask).ellipse((500, 180, 850, 950), fill=255)
    ImageDraw.Draw(right_mask).ellipse((70, 200, 390, 980), fill=255)

    for direction in ("Vertical", "Horizontal"):
        data["split_direction"] = direction
        output = card_studio.render_card(
            "Head-to-Head",
            (left, right),
            data,
            subject_mask=(left_mask, right_mask),
        )
        with Image.open(BytesIO(output)) as image:
            assert image.size == (1080, 1920)
            assert image.format == "PNG"


def test_card_studio_accepts_variable_supporting_stat_rows():
    data = _renderable_card_data("Stat Highlight")
    data["supporting_fields"].extend(
        {"label": f"Extra metric {index}", "value": str(index)}
        for index in range(1, 5)
    )
    output = card_studio.render_card("Stat Highlight", _image_bytes(), data)
    with Image.open(BytesIO(output)) as image:
        assert image.size == (1080, 1920)
        assert image.format == "PNG"


def test_card_studio_keeps_subject_cutout_on_shared_editor():
    try:
        card_studio.render_card("Text Subject Cutout", _image_bytes(), {})
    except card_studio.CardStudioError as exc:
        assert "approved shared subject-cutout editor" in str(exc)
    else:
        raise AssertionError("Expected CardStudioError")


def test_card_type_lists_match_approval_scope():
    assert "Text Subject Cutout" in card_studio.TEST_CARD_TYPES
    assert card_studio.LIVE_CARD_TYPES == card_studio.TEST_CARD_TYPES


def test_subject_mask_uses_the_same_centre_crop_as_the_photo():
    image = Image.new("RGB", (1000, 1000), (80, 90, 100))
    mask = Image.new("L", (1000, 1000), 0)
    ImageDraw.Draw(mask).rectangle((300, 200, 450, 800), fill=255)

    covered, aligned = card_studio._cover_with_mask(image, mask)

    assert covered.size == (1080, 1920)
    assert aligned is not None
    assert aligned.size == covered.size
    bbox = aligned.point(lambda value: 255 if value >= 96 else 0).getbbox()
    assert bbox is not None
    assert 130 <= bbox[0] <= 180
    assert 400 <= bbox[2] <= 470


def test_dynamic_text_side_moves_away_from_subject():
    image = Image.new("RGB", (1080, 1920), (90, 90, 90))
    right_subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(right_subject).rectangle((700, 260, 1020, 1400), fill=255)
    left_subject = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(left_subject).rectangle((90, 260, 350, 1400), fill=255)

    assert card_studio._choose_text_side(image, right_subject) == "left"
    assert card_studio._choose_text_side(image, left_subject) == "right"


def test_all_non_cutout_cards_render_with_subject_masks():
    source = _image_bytes(size=(900, 1600))
    mask = Image.new("L", (900, 1600), 0)
    ImageDraw.Draw(mask).ellipse((500, 180, 850, 950), fill=255)

    for card_type in (
        "Stat Highlight",
        "Quote / Reaction",
        "Head-to-Head",
        "Key Fact / Milestone",
    ):
        output = card_studio.render_card(
            card_type,
            source,
            _renderable_card_data(card_type),
            subject_mask=mask,
        )
        with Image.open(BytesIO(output)) as image:
            assert image.size == (1080, 1920)
            assert image.format == "PNG"




def test_localized_card_starter_copy_and_native_script_rendering():
    card_types = (
        "Stat Highlight",
        "Quote / Reaction",
        "Head-to-Head",
        "Key Fact / Milestone",
    )
    for language, start, end, font_name in (
        ("hindi", 0x0900, 0x097F, "NotoSansDevanagari-Bold.ttf"),
        ("telugu", 0x0C00, 0x0C7F, "NotoSansTelugu-Bold.ttf"),
    ):
        for card_type in card_types:
            data = card_studio.card_data_for_type(card_type, language=language)
            assert data["language"] == language
            serialized = repr(data)
            assert any(start <= ord(char) <= end for char in serialized), (language, card_type)
            output = card_studio.render_card(card_type, _image_bytes(), data)
            with Image.open(BytesIO(output)) as image:
                assert image.size == (1080, 1920)
                assert image.format == "PNG"

        script_sample = "हिंदी कार्ड क्षेत्र की उपलब्धि" if language == "hindi" else "తెలుగు కార్డు ప్రత్యేకమైన క్రీడ"
        font = card_studio._font_for_text(script_sample, 28, card_studio._font_headline)
        assert Path(font.path).name == font_name
        assert font.layout_engine == ImageFont.Layout.RAQM
        for complex_text in (
            ("क्षेत्र", "क्रीड़ा नहीं"),
            ("తెలుగు", "ప్రత్యేకమైన క్రీడాకారుడు"),
        ):
            for sample in complex_text:
                selected = card_studio._font_for_text(sample, 36, card_studio._font_headline)
                assert selected.layout_engine == ImageFont.Layout.RAQM
                assert selected.getmask(sample).getbbox() is not None



@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("hindi", "भारत के क्रिकेट खिलाड़ी"),
        ("telugu", "భారత క్రికెట్ ఆటగాళ్లు"),
    ],
)
def test_localized_cards_fail_closed_without_raqm(monkeypatch, language, text):
    monkeypatch.setattr(card_studio.features, "check_feature", lambda _feature: False)
    with pytest.raises(card_studio.CardStudioError, match="RAQM shaping engine"):
        card_studio._localized_font.cache_clear()
        card_studio._font_for_text(text, 32, card_studio._font_headline)
    card_studio._localized_font.cache_clear()

def test_changing_card_language_invalidates_the_old_render():
    state = {
        "card-result": {
            "bytes": b"old-render",
            "type": "Quote / Reaction",
            "data": {
                "layout_position": "Left half",
                "contrast_treatment": "Soft gradient",
                "language": "english",
            },
        }
    }
    changed = card_studio.invalidate_card_studio_result_for_composition(
        state,
        "card-result",
        "Quote / Reaction",
        "Left half",
        "Soft gradient",
        language="hindi",
    )
    assert changed is True
    assert state["card-result"] is None


def test_adaptive_gradient_strength_responds_to_photo_brightness():
    bounds = (100, 300, 500, 900)
    dark = Image.new("RGB", (1080, 1920), (15, 15, 15))
    bright = Image.new("RGB", (1080, 1920), (240, 240, 240))

    dark_result = card_studio._contrast_bed(
        dark, "left", "Adaptive gradient", content_bounds=bounds
    ).convert("RGB")
    bright_result = card_studio._contrast_bed(
        bright, "left", "Adaptive gradient", content_bounds=bounds
    ).convert("RGB")

    assert dark_result.getpixel((300, 600)) != dark.getpixel((300, 600))
    assert bright_result.getpixel((300, 600)) != bright.getpixel((300, 600))
    assert bright_result.getpixel((300, 600))[0] > dark_result.getpixel((300, 600))[0]
    assert bright_result.getpixel((900, 600)) == bright.getpixel((900, 600))


def test_quote_editorial_summary_does_not_render_as_a_verbatim_quote(monkeypatch):
    captured = {}

    def capture(_image, _position, _treatment, _x, _width, _top, blocks):
        captured["blocks"] = blocks
        return Image.new("RGB", (1080, 1920), (0, 0, 0))

    monkeypatch.setattr(card_studio, "_draw_editorial_stack", capture)
    data = card_studio.card_data_for_type("Quote / Reaction")
    data.update({
        "quote": "The team remained composed in the final overs.",
        "attribution": "Editorial summary",
    })
    card_studio._render_quote_reaction(_image_bytes(), data, None)
    quote = next(block for block in captured["blocks"] if block.get("kind") == "quote")
    assert quote["show_quote_mark"] is False

    data["attribution"] = "James Anderson"
    card_studio._render_quote_reaction(_image_bytes(), data, None)
    quote = next(block for block in captured["blocks"] if block.get("kind") == "quote")
    assert quote["show_quote_mark"] is True


def test_quote_card_can_render_without_attribution_or_context():
    data = card_studio.card_data_for_type("Quote / Reaction")
    data["quote"] = "We kept believing until the final ball."
    output = card_studio.render_card("Quote / Reaction", _image_bytes(), data)
    with Image.open(BytesIO(output)) as image:
        assert image.size == (1080, 1920)
        assert image.format == "PNG"


def test_head_to_head_support_rows_adapt_to_the_count_and_safe_columns():
    data = _renderable_card_data("Head-to-Head")
    data["metrics"] = [
        {"label": "Test wickets", "left_value": "704", "right_value": "604"},
        {"label": "Test matches", "left_value": "188", "right_value": "167"},
    ]
    output = card_studio.render_card("Head-to-Head", _image_bytes(), data)
    with Image.open(BytesIO(output)) as image:
        assert image.size == (1080, 1920)
        assert image.format == "PNG"
