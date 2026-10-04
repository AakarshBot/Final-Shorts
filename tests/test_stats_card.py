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
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: ({}, {}))
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
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: ({}, {}))
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
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: ({}, {}))
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


def test_stats_card_result_exposes_player_image_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: ({}, {}))
    def fake_query(sql):
        if "FROM people" in sql:
            return [{
                "identifier": "abc123",
                "name": "MS Dhoni",
                "unique_name": "MS Dhoni",
            }]
        return [{
            "match_id": "1",
            "start_date": "2020-01-01",
            "innings": 1,
            "batting_team": "India",
            "bowling_team": "Australia",
            "striker": "MS Dhoni",
            "runs": 50,
            "balls_faced": 60,
            "dismissed": 1,
        }]

    monkeypatch.setattr(stats_card, "_query", fake_query)
    result = stats_card.build_stats_card("MS Dhoni ODI stats", _image_bytes(), output_dir=tmp_path)

    assert result["layout"]["width"] == 1080
    assert result["layout"]["height"] == 1920
    assert result["layout"]["image_width"] == 1080
    assert result["layout"]["image_height"] == 860
    assert result["layout"]["panel_height"] == 1060


def test_last_n_card_renders_twenty_innings_without_error(monkeypatch, tmp_path):
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: ({}, {}))
    def fake_query(sql):
        if "FROM people" in sql:
            return [{
                "identifier": "abc123",
                "name": "Virat Kohli",
                "unique_name": "Virat Kohli",
            }]
        return [
            {
                "match_id": str(index),
                "start_date": f"2026-01-{index:02d}",
                "innings": 1,
                "batting_team": "India",
                "bowling_team": "Australia",
                "striker": "Virat Kohli",
                "runs": index * 4,
                "balls_faced": 20 + index,
                "dismissed": 1,
            }
            for index in range(1, 21)
        ]

    monkeypatch.setattr(stats_card, "_query", fake_query)
    result = stats_card.build_stats_card(
        "Virat Kohli last 20 innings scores",
        _image_bytes(),
        output_dir=tmp_path,
    )

    with Image.open(BytesIO(result["bytes"])) as card:
        assert card.size == (1080, 1920)



def _registry_fixture(*people_rows):
    people = {}
    aliases = {}
    for identifier, name, unique_name, *variants in people_rows:
        values = {value for value in (name, unique_name, *variants) if value}
        people[identifier] = {
            "identifier": identifier,
            "name": name,
            "unique_name": unique_name,
            "aliases": set(values),
        }
        for value in values:
            aliases.setdefault(stats_card._name_key(value), set()).add(identifier)
    return people, aliases


def test_cricsheet_registry_loads_canonical_names_and_variants(monkeypatch):
    responses = iter(
        [
            type(
                "Response",
                (),
                {
                    "text": (
                        "identifier,name,unique_name,key_cricinfo\n"
                        "vk1,V Kohli,V Kohli,253802\n"
                        "rs1,RG Sharma,RG Sharma,34102\n"
                    ),
                    "raise_for_status": lambda self: None,
                },
            )(),
            type(
                "Response",
                (),
                {
                    "text": (
                        "identifier,name\n"
                        "vk1,Virat Kohli\n"
                        "vk1,V. Kohli\n"
                        "rs1,Rohit Sharma\n"
                    ),
                    "raise_for_status": lambda self: None,
                },
            )(),
        ]
    )
    monkeypatch.setattr(stats_card.requests, "get", lambda *args, **kwargs: next(responses))
    stats_card._cricsheet_registry.cache_clear()

    people, aliases = stats_card._cricsheet_registry(123456)
    cached_people, cached_aliases = stats_card._cricsheet_registry(123456)

    assert people is cached_people
    assert aliases is cached_aliases
    assert people["vk1"]["unique_name"] == "V Kohli"
    assert aliases[stats_card._name_key("Virat Kohli")] == {"vk1"}
    assert aliases[stats_card._name_key("V. Kohli")] == {"vk1"}
    assert aliases[stats_card._name_key("Rohit Sharma")] == {"rs1"}


def test_resolve_full_player_name_to_canonical_match_name(monkeypatch):
    people, aliases = _registry_fixture(
        ("vk1", "V Kohli", "V Kohli", "Virat Kohli", "V. Kohli"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    player = stats_card._resolve_player(stats_card._parse_query("Virat Kohli ODI stats"))

    assert player["identifier"] == "vk1"
    assert player["name"] == "Virat Kohli"
    assert player["unique_name"] == "V Kohli"


@pytest.mark.parametrize(
    "query",
    [
        "v. kohli",
        "V KOHLI",
        "Virat Kohli",
    ],
)
def test_resolve_name_normalization_variants(monkeypatch, query):
    people, aliases = _registry_fixture(
        ("vk1", "V Kohli", "V Kohli", "Virat Kohli", "V. Kohli"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    player = stats_card._resolve_player(stats_card._parse_query(query))

    assert player["identifier"] == "vk1"


def test_resolve_published_name_change_alias(monkeypatch):
    people, aliases = _registry_fixture(
        ("p1", "S Example", "S Example", "Sam Oldsurname", "Sam Newsurname"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    player = stats_card._resolve_player(
        stats_card._parse_query("Sam Newsurname ODI stats")
    )

    assert player["identifier"] == "p1"
    assert player["unique_name"] == "S Example"


def test_resolve_unique_surname_without_guessing(monkeypatch):
    people, aliases = _registry_fixture(
        ("vk1", "V Kohli", "V Kohli", "Virat Kohli"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    player = stats_card._resolve_player(
        stats_card._parse_query("Kohli ODI stats")
    )

    assert player["identifier"] == "vk1"


def test_duplicate_name_uses_requested_format_to_disambiguate(monkeypatch):
    people, aliases = _registry_fixture(
        ("p1", "A Smith", "AB Smith"),
        ("p2", "A Smith", "AC Smith"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    def fake_query(sql):
        if "FROM ball_by_ball_odi_men" in sql:
            return [{"striker": "AB Smith"}]
        raise AssertionError(f"Unexpected SQL: {sql}")

    monkeypatch.setattr(stats_card, "_query", fake_query)

    player = stats_card._resolve_player(
        stats_card._parse_query("A Smith ODI stats")
    )

    assert player["identifier"] == "p1"
    assert player["unique_name"] == "AB Smith"


def test_same_name_across_genders_uses_requested_gender(monkeypatch):
    people, aliases = _registry_fixture(
        ("male1", "A Lee", "AB Lee"),
        ("female1", "A Lee", "AC Lee"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    def fake_query(sql):
        if "FROM ball_by_ball_odi_women" in sql:
            return [{"striker": "AC Lee"}]
        raise AssertionError(f"Unexpected SQL: {sql}")

    monkeypatch.setattr(stats_card, "_query", fake_query)

    player = stats_card._resolve_player(
        stats_card._parse_query("A Lee women's ODI stats")
    )

    assert player["identifier"] == "female1"
    assert player["unique_name"] == "AC Lee"


def test_duplicate_name_remains_ambiguous_when_format_cannot_disambiguate(monkeypatch):
    people, aliases = _registry_fixture(
        ("p1", "A Smith", "AB Smith"),
        ("p2", "A Smith", "AC Smith"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))
    monkeypatch.setattr(stats_card, "_query", lambda sql: [])

    with pytest.raises(stats_card.StatsCardError, match="ambiguous"):
        stats_card._resolve_player(
            stats_card._parse_query("A Smith ODI stats")
        )


def test_high_confidence_typo_is_resolved(monkeypatch):
    people, aliases = _registry_fixture(
        ("vk1", "V Kohli", "V Kohli", "Virat Kohli"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    player = stats_card._resolve_player(
        stats_card._parse_query("Virat Kholi ODI stats")
    )

    assert player["identifier"] == "vk1"


def test_close_fuzzy_matches_are_not_auto_selected(monkeypatch):
    people, aliases = _registry_fixture(
        ("p1", "John Smith", "John Smith"),
        ("p2", "John Smyth", "John Smyth"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))

    with pytest.raises(stats_card.StatsCardError, match="Could not find player"):
        stats_card._resolve_player(
            stats_card._parse_query("John Smth ODI stats")
        )


def test_registry_outage_falls_back_to_tigzig_people(monkeypatch):
    def fail_registry(_):
        raise stats_card.requests.Timeout("registry unavailable")

    def fake_query(sql):
        assert "FROM people" in sql
        return [{
            "identifier": "vk1",
            "name": "V Kohli",
            "unique_name": "V Kohli",
        }]

    monkeypatch.setattr(stats_card, "_cricsheet_registry", fail_registry)
    monkeypatch.setattr(stats_card, "_query", fake_query)

    player = stats_card._resolve_player(
        stats_card._parse_query("Virat Kohli ODI stats")
    )

    assert player["identifier"] == "vk1"
    assert player["unique_name"] == "V Kohli"


def test_player_rows_uses_canonical_unique_name(monkeypatch):
    captured = []

    def fake_query(sql):
        captured.append(sql)
        return []

    monkeypatch.setattr(stats_card, "_query", fake_query)

    stats_card._player_rows(
        stats_card._parse_query("V Kohli ODI stats"),
        {
            "identifier": "vk1",
            "name": "V Kohli",
            "unique_name": "V Kohli",
        },
    )

    assert "lower(b.striker) = lower('V Kohli')" in captured[0]
    assert "IN (" not in captured[0]


def test_resolved_player_with_no_format_data_reports_data_gap(monkeypatch):
    people, aliases = _registry_fixture(
        ("vk1", "V Kohli", "V Kohli", "Virat Kohli"),
    )
    monkeypatch.setattr(stats_card, "_cricsheet_registry", lambda _: (people, aliases))
    monkeypatch.setattr(stats_card, "_query", lambda sql: [])

    with pytest.raises(stats_card.StatsCardError, match="No ODI batting data"):
        stats_card._stats_for_intent(
            stats_card._parse_query("Virat Kohli ODI stats")
        )


def test_dynamic_planner_clarification_is_returned_verbatim(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": {
                            "ready": False,
                            "message": "Tell me which format you want for Kohli: ODI, T20, Test, or IPL.",
                        }
                    }
                }]
            }

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(stats_card.requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(stats_card.StatsCardError, match=r"Tell me which format you want for Kohli: ODI, T20, Test, or IPL\."):
        stats_card._plan_dynamic_stats("Kohli stats")


def test_dynamic_player_card_uses_ai_metrics_and_existing_image(monkeypatch, tmp_path):
    plan = {
        "ready": True,
        "message": "",
        "scope": "player",
        "format": "odi",
        "gender": "men",
        "player": "Virat Kohli",
        "opponent_team": "",
        "team1": "",
        "team2": "",
        "count": 0,
        "metrics": [
            "runs", "average", "strike_rate", "high_score", "hundreds",
            "fifties", "fours", "sixes", "balls_faced", "not_outs",
        ],
        "detail_table": "none",
        "detail_limit": 0,
    }
    monkeypatch.setattr(stats_card, "_plan_dynamic_stats", lambda query: dict(plan))
    monkeypatch.setattr(
        stats_card,
        "_cricsheet_registry",
        lambda _: (
            {"vk1": {
                "identifier": "vk1", "name": "V Kohli", "unique_name": "V Kohli",
                "aliases": {"Virat Kohli"},
            }},
            {stats_card._name_key("Virat Kohli"): {"vk1"}},
        ),
    )

    def fake_query(sql):
        assert "SUM(CASE WHEN b.runs_off_bat = 4" in sql
        assert "SUM(CASE WHEN b.runs_off_bat = 6" in sql
        return [
            {
                "match_id": "1", "start_date": "2026-01-01", "innings": 1,
                "batting_team": "India", "bowling_team": "Australia",
                "runs": 82, "balls_faced": 91, "fours": 8, "sixes": 1, "dismissed": 1,
            },
            {
                "match_id": "2", "start_date": "2025-12-01", "innings": 1,
                "batting_team": "India", "bowling_team": "South Africa",
                "runs": 101, "balls_faced": 99, "fours": 10, "sixes": 0, "dismissed": 0,
            },
        ]

    monkeypatch.setattr(stats_card, "_query", fake_query)
    result = stats_card.build_test_stats_card("Virat Kohli career stats", _image_bytes(), output_dir=tmp_path)

    assert result["plan"]["scope"] == "player"
    assert result["stats"]["runs"] == 183
    assert result["stats"]["average"] == pytest.approx(183)
    assert result["stats"]["strike_rate"] == pytest.approx(96.8253968254)
    assert result["stats"]["fours"] == 18
    assert result["stats"]["sixes"] == 1
    assert result["stats"]["not_outs"] == 1
    assert result["stats"]["high_score"] == "101*"
    with Image.open(BytesIO(result["bytes"])) as card:
        assert card.size == (1080, 1920)


def test_dynamic_last_n_card_renders_20_rows_without_clipping_error(monkeypatch, tmp_path):
    plan = {
        "ready": True,
        "message": "",
        "scope": "player_last_n",
        "format": "odi",
        "gender": "men",
        "player": "Virat Kohli",
        "opponent_team": "",
        "team1": "",
        "team2": "",
        "count": 20,
        "metrics": list(stats_card.DYNAMIC_DEFAULT_METRICS["player_last_n"]),
        "detail_table": "innings",
        "detail_limit": 20,
    }
    monkeypatch.setattr(stats_card, "_plan_dynamic_stats", lambda query: dict(plan))
    monkeypatch.setattr(
        stats_card,
        "_cricsheet_registry",
        lambda _: (
            {"vk1": {
                "identifier": "vk1", "name": "Virat Kohli", "unique_name": "Virat Kohli",
                "aliases": {"Virat Kohli"},
            }},
            {stats_card._name_key("Virat Kohli"): {"vk1"}},
        ),
    )
    rows = [
        {
            "match_id": str(index),
            "start_date": f"2026-{(index % 12) + 1:02d}-01",
            "innings": 1,
            "batting_team": "India",
            "bowling_team": "Very Long Opponent Name That Must Never Push Into The Score Column",
            "runs": index,
            "balls_faced": 20,
            "fours": 1,
            "sixes": 0,
            "dismissed": index % 2,
        }
        for index in range(20)
    ]
    monkeypatch.setattr(stats_card, "_query", lambda sql: rows)
    result = stats_card.build_test_stats_card("Virat Kohli last 20 ODI innings", _image_bytes(), output_dir=tmp_path)
    with Image.open(BytesIO(result["bytes"])) as card:
        assert card.size == (1080, 1920)
