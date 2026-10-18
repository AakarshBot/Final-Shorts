from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

import card_studio


def _image_bytes(color=(52, 84, 118), size=(900, 1600)):
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


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
            card_studio.card_data_for_type(card_type),
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
        assert defaults["contrast_treatment"] == "Soft gradient"


    stat = card_studio.card_data_for_type("Stat Highlight")
    assert all(stat[key] for key in ("eyebrow", "headline", "value", "unit"))
    assert len(stat["metrics"]) == 3
    assert all(metric["label"] and metric["value"] for metric in stat["metrics"])

    quote = card_studio.card_data_for_type("Quote / Reaction")
    assert all(quote[key] for key in ("eyebrow", "quote", "attribution", "context"))

    head_to_head = card_studio.card_data_for_type("Head-to-Head")
    assert all(head_to_head[key] for key in ("eyebrow", "headline", "image_mode", "split_direction"))
    assert head_to_head["left"]["name"]
    assert head_to_head["right"]["name"]
    assert len(head_to_head["metrics"]) == 3
    assert all(
        head_to_head["left"]["values"].get(metric)
        and head_to_head["right"]["values"].get(metric)
        for metric in head_to_head["metrics"]
    )

    milestone = card_studio.card_data_for_type("Key Fact / Milestone")
    assert all(milestone[key] for key in ("eyebrow", "value", "label", "context"))


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
            data = card_studio.card_data_for_type(card_type)
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
    data = card_studio.card_data_for_type("Quote / Reaction")

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
    data = card_studio.card_data_for_type("Head-to-Head")
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


def test_card_studio_rejects_overloaded_stat_card():
    data = card_studio.card_data_for_type("Stat Highlight")
    data["metrics"].append({"label": "Extra", "value": "5"})
    try:
        card_studio.render_card("Stat Highlight", _image_bytes(), data)
    except card_studio.CardStudioError as exc:
        assert "at most three" in str(exc)
    else:
        raise AssertionError("Expected CardStudioError")


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
            card_studio.card_data_for_type(card_type),
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
        ("hindi", "\\u0900", "\\u097f", "NotoSansDevanagari-Bold.ttf"),
        ("telugu", "\\u0c00", "\\u0c7f", "NotoSansTelugu-Bold.ttf"),
    ):
        for card_type in card_types:
            data = card_studio.card_data_for_type(card_type, language=language)
            assert data["language"] == language
            serialized = repr(data)
            assert any(start <= char <= end for char in serialized), (language, card_type)
            output = card_studio.render_card(card_type, _image_bytes(), data)
            with Image.open(BytesIO(output)) as image:
                assert image.size == (1080, 1920)
                assert image.format == "PNG"

        script_sample = "हिंदी कार्ड" if language == "hindi" else "తెలుగు కార్డు"
        font = card_studio._font_for_text(script_sample, 28, card_studio._font_headline)
        assert Path(font.path).name == font_name


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
