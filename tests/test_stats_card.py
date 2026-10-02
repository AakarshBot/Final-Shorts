from io import BytesIO

import pytest
from PIL import Image

import stats_card


def _image_bytes():
    image = Image.new("RGB", (600, 900), (40, 50, 60))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_parse_common_stats_queries():
    intent = stats_card._parse_query("MS Dhoni ODI stats")
    assert intent.kind == "career"
    assert intent.format_name == "odi"
    assert intent.player == "MS Dhoni"

    intent = stats_card._parse_query("Ind vs Pak H2H stats")
    assert intent.kind == "h2h"
    assert intent.format_name == "odi"
    assert intent.team1 == "India"
    assert intent.team2 == "Pakistan"

    intent = stats_card._parse_query("Virat Kohli's last 10 innings scores")
    assert intent.kind == "last_n"
    assert intent.format_name == "odi"
    assert intent.player == "Virat Kohli"
    assert intent.count == 10


def test_parse_format_and_gender_variants():
    intent = stats_card._parse_query("Smriti Mandhana women's ODI stats")
    assert intent.kind == "career"
    assert intent.format_name == "odi"
    assert intent.gender == "women"
    assert intent.player == "Smriti Mandhana"

    intent = stats_card._parse_query("India v Pakistan T20 H2H stats")
    assert intent.kind == "h2h"
    assert intent.format_name == "t20"


def test_build_career_card_uses_only_returned_data(monkeypatch, tmp_path):
    calls = []

    def fake_query(sql):
        calls.append(sql)
        if "FROM people" in sql:
            return [{
                "identifier": "abc123",
                "name": "MS Dhoni",
                "unique_name": "MS Dhoni",
            }]
        return [
            {
                "match_id": "1",
                "start_date": "2018-06-01",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "England",
                "striker": "MS Dhoni",
                "runs": 100,
                "balls_faced": 110,
                "dismissed": 0,
            },
            {
                "match_id": "2",
                "start_date": "2018-07-01",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "England",
                "striker": "MS Dhoni",
                "runs": 55,
                "balls_faced": 70,
                "dismissed": 1,
            },
            {
                "match_id": "3",
                "start_date": "2018-08-01",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "Australia",
                "striker": "MS Dhoni",
                "runs": 20,
                "balls_faced": 24,
                "dismissed": 1,
            },
        ]

    monkeypatch.setattr(stats_card, "_query", fake_query)
    result = stats_card.build_stats_card(
        "MS Dhoni ODI stats",
        _image_bytes(),
        output_dir=tmp_path,
    )

    with Image.open(BytesIO(result["bytes"])) as card:
        assert card.size == (1080, 1920)
        assert card.format == "PNG"

    assert result["stats"]["matches"] == 3
    assert result["stats"]["runs"] == 175
    assert result["stats"]["average"] == pytest.approx(87.5)
    assert result["stats"]["strike_rate"] == pytest.approx(85.7843137255)
    assert result["stats"]["high_score"] == "100*"
    assert result["stats"]["hundreds"] == 1
    assert result["stats"]["fifties"] == 1
    assert len(calls) == 2


def test_last_n_returns_latest_completed_innings(monkeypatch):
    def fake_query(sql):
        if "FROM people" in sql:
            return [{
                "identifier": "abc123",
                "name": "Virat Kohli",
                "unique_name": "Virat Kohli",
            }]
        return [
            {
                "match_id": "3",
                "start_date": "2026-01-03",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "Australia",
                "striker": "Virat Kohli",
                "runs": 40,
                "balls_faced": 50,
                "dismissed": 1,
            },
            {
                "match_id": "2",
                "start_date": "2025-12-20",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "South Africa",
                "striker": "Virat Kohli",
                "runs": 80,
                "balls_faced": 90,
                "dismissed": 0,
            },
            {
                "match_id": "1",
                "start_date": "2025-12-01",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "Pakistan",
                "striker": "Virat Kohli",
                "runs": 100,
                "balls_faced": 95,
                "dismissed": 1,
            },
        ]

    monkeypatch.setattr(stats_card, "_query", fake_query)
    intent = stats_card._parse_query("Virat Kohli last 2 innings scores")
    stats = stats_card._stats_for_intent(intent)

    assert [row["runs"] for row in stats["innings"]] == [40, 80]
    assert stats["runs"] == 120
    assert stats["average"] == pytest.approx(120)
    assert stats["count_available"] == 2


def test_h2h_counts_wins_and_other(monkeypatch):
    monkeypatch.setattr(
        stats_card,
        "_query",
        lambda sql: [
            {
                "match_id": "1",
                "start_date": "2025-01-01",
                "team1": "India",
                "team2": "Pakistan",
                "winner": "India",
            },
            {
                "match_id": "2",
                "start_date": "2024-01-01",
                "team1": "Pakistan",
                "team2": "India",
                "winner": "Pakistan",
            },
            {
                "match_id": "3",
                "start_date": "2023-01-01",
                "team1": "India",
                "team2": "Pakistan",
                "winner": None,
            },
        ],
    )

    stats = stats_card._stats_for_intent(
        stats_card._parse_query("India vs Pakistan ODI H2H stats")
    )

    assert stats["matches"] == 3
    assert stats["wins1"] == 1
    assert stats["wins2"] == 1
    assert stats["other"] == 1


def test_no_data_fails_instead_of_guessing(monkeypatch):
    monkeypatch.setattr(stats_card, "_query", lambda sql: [])
    with pytest.raises(stats_card.StatsCardError, match="Could not find player"):
        stats_card.build_stats_card("MS Dhoni ODI stats", _image_bytes())


def test_stats_api_timeout_is_reported_cleanly(monkeypatch):
    def fail(*args, **kwargs):
        raise stats_card.requests.Timeout("timed out")

    monkeypatch.setattr(stats_card.requests, "post", fail)
    with pytest.raises(stats_card.StatsCardError, match="could not be reached"):
        stats_card._query("SELECT 1")

def test_stats_card_preview_uses_card_frame_without_query(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Stats Card preview must not query the database.")

    monkeypatch.setattr(stats_card.requests, "post", fail)
    preview = stats_card.build_stats_card_preview(_image_bytes())

    with Image.open(BytesIO(preview)) as image:
        assert image.size == (1080, 1920)
        assert image.getpixel((0, 100)) == (40, 50, 60)
        assert image.getpixel((0, 1000)) == (246, 247, 249)

def test_query_parses_tigzig_columns_and_data(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "columns": ["name", "runs"],
                "data": [
                    ["MS Dhoni", 4632],
                    ["Virat Kohli", 14797],
                ],
                "truncated": False,
            }

    monkeypatch.setattr(stats_card.requests, "post", lambda *args, **kwargs: FakeResponse())
    assert stats_card._query("SELECT name, runs FROM players") == [
        {"name": "MS Dhoni", "runs": 4632},
        {"name": "Virat Kohli", "runs": 14797},
    ]
