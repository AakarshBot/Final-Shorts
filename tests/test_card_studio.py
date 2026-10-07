from io import BytesIO

from PIL import Image

import card_studio


def _image_bytes():
    image = Image.new("RGB", (900, 1600), (52, 84, 118))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_card_studio_outputs_1080x1920_png():
    for card_type, data in (
        (
            "Stat Highlight",
            {
                "eyebrow": "CAREER",
                "headline": "A huge scoring run",
                "value": "1,203",
                "unit": "RUNS",
                "metrics": [
                    {"label": "Matches", "value": "38"},
                    {"label": "Average", "value": "46.27"},
                    {"label": "Strike rate", "value": "132.4"},
                ],
            },
        ),
        (
            "Quote / Reaction",
            {
                "eyebrow": "REACTION",
                "quote": "We believed from the first ball.",
                "attribution": "Player Name · after the final",
                "context": "Post-match reaction",
            },
        ),
        (
            "Head-to-Head",
            {
                "eyebrow": "HEAD TO HEAD",
                "headline": "Who has the edge?",
                "left": {"name": "Player A", "values": {"Runs": "1,020", "Average": "48.4"}},
                "right": {"name": "Player B", "values": {"Runs": "934", "Average": "42.1"}},
                "metrics": ["Runs", "Average"],
            },
        ),
        (
            "Key Fact / Milestone",
            {
                "eyebrow": "MILESTONE",
                "value": "100",
                "label": "International appearances",
                "context": "A landmark reached in the latest match.",
            },
        ),
    ):
        output = card_studio.render_card(card_type, _image_bytes(), data)
        with Image.open(BytesIO(output)) as image:
            assert image.size == (1080, 1920)
            assert image.format == "PNG"


def test_card_studio_rejects_overloaded_stat_card():
    data = {
        "headline": "A huge scoring run",
        "value": "1,203",
        "metrics": [{"label": str(i), "value": str(i)} for i in range(4)],
    }
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
