from io import BytesIO
from PIL import Image
import pytest

from longform_cards import (
    WIDTH,
    HEIGHT,
    render_longform_stat_card,
    render_longform_quote_card,
    render_longform_h2h_card,
    render_longform_milestone_card,
    render_longform_chapter_card,
    render_longform_timeline_card,
    LongformCardError,
)


def _sample_image_bytes():
    img = Image.new("RGB", (1280, 720), (40, 50, 70))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_render_longform_stat_card():
    data = {
        "player_name": "Jasprit Bumrah",
        "eyebrow": "TEST MATCH TELEMETRY",
        "hero_stat": "15.8",
        "stat_label": "BOWLING AVERAGE IN 4TH INNINGS",
        "context_note": "Lowest fourth-innings average by any visiting fast bowler in Australia since 1990.",
        "tiles": [
            {"label": "WICKETS", "value": "42"},
            {"label": "ECONOMY", "value": "2.44"},
            {"label": "STRIKE RATE", "value": "38.2"},
        ],
    }
    img = render_longform_stat_card(_sample_image_bytes(), data)
    assert img.size == (WIDTH, HEIGHT)
    assert img.size == (1920, 1080)


def test_render_longform_quote_card():
    data = {
        "quote": "We did not drop him because of form. His knee was simply not ready for five days of Test cricket.",
        "speaker": "Ajit Agarkar",
        "role": "CHAIRMAN OF SELECTORS, BCCI",
        "eyebrow": "OFFICIAL CLARIFICATION",
    }
    img = render_longform_quote_card(_sample_image_bytes(), data)
    assert img.size == (1920, 1080)


def test_render_longform_quote_card_requires_quote_text():
    with pytest.raises(LongformCardError, match="Quote Card requires quote text"):
        render_longform_quote_card(_sample_image_bytes(), {"quote": ""})


def test_render_longform_h2h_card():
    data = {
        "headline": "THE CAPTAINCY DUEL",
        "left_name": "Rohit Sharma",
        "right_name": "Jasprit Bumrah",
        "metrics": [
            {"label": "WIN % IN ASIA", "left": "74%", "right": "68%"},
            {"label": "AVERAGE 2024", "left": "41.2", "right": "18.4"},
            {"label": "TEST LOSSES", "left": "5", "right": "1"},
        ],
    }
    img = render_longform_h2h_card(_sample_image_bytes(), data)
    assert img.size == (1920, 1080)


def test_render_longform_milestone_card():
    data = {
        "title": "FASTEST TO 10,000 TEST RUNS",
        "milestone": "ALL-TIME RECORD",
        "subtitle": "Achieved in just 175 innings across 11 calendar years",
        "bullets": [
            "Surpasses Sachin Tendulkar's long-standing benchmark of 195 innings",
            "Scored 28 centuries and 44 half-centuries on the way",
            "Maintains an overall career average of 57.8",
        ],
    }
    img = render_longform_milestone_card(_sample_image_bytes(), data)
    assert img.size == (1920, 1080)


def test_render_longform_chapter_card():
    data = {
        "act": "ACT 03",
        "title": "THE FRACTURED DRESSING ROOM",
        "premise": "How a closed-door team meeting transformed India's red-ball leadership structure.",
        "timestamp": "02:45 · CHAPTER 3 OF 6",
    }
    img = render_longform_chapter_card(None, data)
    assert img.size == (1920, 1080)


def test_render_longform_timeline_card():
    data = {
        "headline": "HOW THE CONTROVERSY UNFOLDED",
        "nodes": [
            {"date": "DAY 1", "title": "Morning Scan", "desc": "Swelling reported during pre-match nets."},
            {"date": "DAY 2", "title": "BCCI Release", "desc": "Medical team confirms rest period."},
            {"date": "DAY 3", "title": "Press Conference", "desc": "Bumrah named captain for Mumbai Test."},
        ],
    }
    img = render_longform_timeline_card(None, data)
    assert img.size == (1920, 1080)

def test_stat_card_requires_source_grounded_values():
    with pytest.raises(LongformCardError, match="source-grounded"):
        render_longform_stat_card(_sample_image_bytes(), {"player_name": "Jasprit Bumrah"})


def test_zero_is_a_valid_source_grounded_stat_value():
    image = render_longform_stat_card(
        _sample_image_bytes(),
        {
            "player_name": "Example Player",
            "hero_stat": 0,
            "stat_label": "Runs in this sample",
            "tiles": [{"label": "Wickets", "value": 0}],
        },
    )
    assert image.size == (WIDTH, HEIGHT)


def test_quote_card_requires_named_speaker():
    with pytest.raises(LongformCardError, match="speaker attribution"):
        render_longform_quote_card(_sample_image_bytes(), {"quote": "We will win."})


def test_head_to_head_card_does_not_invent_default_statistics():
    with pytest.raises(LongformCardError, match="source-grounded comparison metrics"):
        render_longform_h2h_card(
            _sample_image_bytes(),
            {"left_name": "Player One", "right_name": "Player Two"},
        )


def test_milestone_card_requires_evidence_backed_labels():
    with pytest.raises(LongformCardError, match="source-grounded"):
        render_longform_milestone_card(_sample_image_bytes(), {})


def test_timeline_card_requires_supported_event_nodes():
    with pytest.raises(LongformCardError, match="at least two source-grounded"):
        render_longform_timeline_card(_sample_image_bytes(), {"nodes": []})
