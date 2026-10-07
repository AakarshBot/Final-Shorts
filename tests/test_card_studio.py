from io import BytesIO

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


def test_card_studio_subject_aware_position_prefers_negative_space():
    mask = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(mask).rectangle((88, 220, 620, 1460), fill=255)

    x, y = card_studio._best_text_position(
        mask,
        300,
        140,
        (88, 260, 864, 900),
        88,
        300,
    )

    assert x > 600
    assert y >= 260


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

    for direction in ("Vertical", "Horizontal"):
        data["split_direction"] = direction
        output = card_studio.render_card(
            "Head-to-Head",
            (left, right),
            data,
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
    assert card_studio.LIVE_CARD_TYPES == ("Text Subject Cutout",)
