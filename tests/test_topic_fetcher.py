from dataclasses import replace
import pytest
import json
from datetime import datetime, timedelta, timezone

import topic_fetcher


def make_topic(title, hours=1, source="Test", url=None, description=""):
    return topic_fetcher.Topic(
        title,
        source,
        datetime.now(timezone.utc) - timedelta(hours=hours),
        url or f"https://example.com/{abs(hash((title, source)))}",
        description,
    )


def test_prepare_preserves_topic_handoff():
    topic = make_topic("Shubman Gill injury update", source="ESPNcricinfo", description="Gill was hit in training.")
    prepared = topic_fetcher._prepare([topic], set(), profile="cricket_india_asia")
    assert prepared == [topic]


def test_cricket_india_asia_accepts_india_asia_and_global_cricket_stories():
    rows = [
        make_topic("BCCI announces India squad", description="India cricket selection"),
        make_topic("MCC changes cricket laws", description="Major cricket law changes"),
        make_topic("MI Emirates appoints Mark Boucher", description="Cricket franchise coaching appointment"),
        make_topic("Premier League club appoints coach", description="Football coaching appointment"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert [row.title for row in prepared] == [
        rows[0].title,
        rows[1].title,
        rows[2].title,
    ]


def test_utility_pages_are_removed():
    rows = [
        make_topic("How to watch India vs West Indies live streaming"),
        make_topic("India vs West Indies playing XI"),
        make_topic("India cricket schedule"),
        make_topic("Shubman Gill injury confirmed"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert [item.title for item in prepared] == [rows[-1].title]


def test_same_event_is_selected_once():
    rows = [
        make_topic("India beat West Indies in first ODI", source="A"),
        make_topic("India complete first ODI win over West Indies", source="B"),
        make_topic("MCC announces cricket law changes", source="C", description="Cricket laws"),
        make_topic("Mark Boucher appointed by MI Emirates", source="D", description="Cricket coach"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 3, set(), profile="cricket_india_asia")
    assert len(chosen) == 3
    assert sum("West Indies" in item.title for item in chosen) == 1
    assert any("MCC" in item.title for item in chosen)
    assert any("Boucher" in item.title for item in chosen)


def test_fuzzy_paraphrases_of_the_same_story_are_collapsed():
    first = make_topic(
        "Shubman Gill ruled out of ODI after fresh injury setback",
        source="SourceA",
        url="https://example.com/a",
    )
    second = make_topic(
        "Fresh injury blow leaves Shubman Gill out of the ODI",
        source="SourceB",
        url="https://example.com/b",
    )
    third = make_topic(
        "Rohit Sharma reveals new training plan before India ODI",
        source="SourceC",
        url="https://example.com/c",
    )
    chosen = topic_fetcher._select(
        [first, second, third],
        3,
        set(),
        profile="cricket_india_asia",
    )
    assert sum("Gill" in item.title for item in chosen) == 1
    assert len(chosen) == 2


def test_same_player_different_events_share_one_tile():
    rows = [
        make_topic(
            "Shubman Gill ruled out after injury",
            url="https://example.com/injury",
        ),
        make_topic(
            "Shubman Gill signs new franchise endorsement deal",
            url="https://example.com/deal",
        ),
        make_topic(
            "MCC announces major law change",
            description="Cricket law change",
            url="https://example.com/law",
        ),
    ]
    chosen = topic_fetcher._select(
        rows,
        2,
        set(),
        profile="cricket_india_asia",
    )
    assert len(chosen) == 2
    gill = next(item for item in chosen if item.group_key == "player:shubman gill")
    assert {item.title for item in gill.group_members} == {
        "Shubman Gill ruled out after injury",
        "Shubman Gill signs new franchise endorsement deal",
    }


def test_country_names_do_not_create_shared_player_tiles():
    rows = [
        make_topic("India announces a new cricket decision", url="https://example.com/india"),
        make_topic("India confirms another cricket decision", url="https://example.com/india-2"),
    ]
    chosen = topic_fetcher._select(
        rows,
        2,
        set(),
        profile="cricket_india_asia",
    )
    assert len(chosen) == 2
    assert all(not item.group_key.startswith("player:") for item in chosen)


def test_existing_player_tile_blocks_new_headline_from_same_player():
    existing = make_topic(
        "Shubman Gill ruled out after injury",
        url="https://example.com/existing",
    )
    existing = replace(existing, group_key="player:shubman gill", group_members=(existing,))
    rows = [
        make_topic(
            "Shubman Gill signs new franchise endorsement deal",
            url="https://example.com/new-gill",
        ),
        make_topic(
            "Rohit Sharma reveals new training plan",
            url="https://example.com/rohit",
        ),
    ]
    chosen = topic_fetcher._select(
        rows,
        2,
        set(),
        existing=[existing],
        profile="cricket_india_asia",
    )
    assert len(chosen) == 1
    assert chosen[0].group_key == "player:rohit sharma"


def test_different_boilerplate_stories_are_not_collapsed():
    rows = [
        make_topic("Alpha player appointed as coach", description="Cricket appointment"),
        make_topic("Beta player appointed as coach", description="Cricket appointment"),
        make_topic("Gamma player appointed as coach", description="Cricket appointment"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 3, set(), profile="cricket_india_asia")
    assert len(chosen) == 3


def test_more_excludes_existing_urls_and_events():
    existing = make_topic("India beat West Indies in first ODI", url="https://example.com/existing")
    rows = [
        make_topic("India complete first ODI win over West Indies", url="https://example.com/repeat"),
        make_topic("WPL retention list announced", url="https://example.com/new"),
    ]
    prepared = topic_fetcher._prepare(rows, {existing.url}, profile="cricket_india_asia")
    chosen = topic_fetcher._select(
        prepared,
        20,
        {existing.url},
        existing=[existing],
        profile="cricket_india_asia",
    )
    assert [item.title for item in chosen] == [rows[1].title]


def test_entity_grouping_still_fills_twenty_tiles():
    gill_titles = [
        "Shubman Gill ruled out with knee injury after training",
        "Shubman Gill signs lucrative franchise endorsement contract",
        "Shubman Gill announces retirement from international cricket",
        "Shubman Gill makes India debut in new format",
        "Shubman Gill returns to captain Gujarat side",
    ]
    rows = [
        make_topic(
            title,
            source=f"gill{index}.com",
            url=f"https://example.com/gill/{index}",
        )
        for index, title in enumerate(gill_titles)
    ]
    rows.extend(
        make_topic(
            f"Player{index} signs Team{index} after Event{index}",
            source=f"source{index}.com",
            url=f"https://example.com/unique/{index}",
        )
        for index in range(25)
    )
    chosen = topic_fetcher._select(
        rows,
        20,
        set(),
        profile="cricket_india_asia",
    )
    assert len(chosen) == 20
    assert sum(item.group_key == "player:shubman gill" for item in chosen) == 1
    gill = next(item for item in chosen if item.group_key == "player:shubman gill")
    assert len(gill.group_members) == 5


def test_twenty_results_remain_available_from_large_unique_pool(monkeypatch):
    actions = [
        "appoints", "signs", "returns", "breaks", "retires",
        "debuts", "reveals", "suspends", "recalls", "releases",
        "stuns", "qualifies",
    ]
    rows = [
        make_topic(
            f"Player{index} {actions[index % len(actions)]} Team{index} after Event{index}",
            source=f"source{index}.com",
            url=f"https://example.com/{index}",
        )
        for index in range(120)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    result = topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert len(result) == 20
    assert len({item.url for item in result}) == 20


def test_more_appends_a_fresh_batch(monkeypatch):
    existing = [
        make_topic(
            f"Existing cricket event {index}",
            url=f"https://example.com/existing/{index}",
        )
        for index in range(20)
    ]
    fresh = [
        make_topic(
            f"Fresh cricket event {index} record",
            source=f"fresh{index}.com",
            url=f"https://example.com/fresh/{index}",
        )
        for index in range(20)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: fresh)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    result = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        more=True,
        exclude_topics=existing,
        limit=20,
    )
    assert len(result) == 20
    assert {item.url for item in result}.isdisjoint({item.url for item in existing})


def test_keyword_search_queries_are_cricket_scoped(monkeypatch):
    captured = []
    rows = [make_topic("Babar Azam Pakistan cricket comeback", url="https://example.com/babar")]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: captured.append(query) or rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    result = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        keyword="Babar Azam",
        limit=1,
    )
    assert result
    assert captured
    assert all("Babar Azam" in query for query in captured)
    assert all("cricket" in query.lower() for query in captured)


def test_stale_story_is_removed():
    stale = make_topic("India cricket record", hours=80)
    fresh = make_topic("India cricket injury", hours=2)
    prepared = topic_fetcher._prepare([stale, fresh], set(), profile="cricket_india_asia")
    assert [item.title for item in prepared] == [fresh.title]


def test_invalid_dates_are_not_fresh():
    topic = topic_fetcher.Topic(
        "India cricket record",
        "Test",
        topic_fetcher._parse_date("not-a-date"),
        "https://example.com/invalid",
        "",
    )
    assert topic_fetcher._prepare([topic], set(), profile="cricket_india_asia") == []


def test_gdelt_is_used_when_google_does_not_fill_pool(monkeypatch):
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: [])
    fallback = [
        make_topic(f"GDELT cricket story {i} {['record','comeback','debuts','retirement'][i % 4]}",
                   url=f"https://gdelt.example/{i}")
        for i in range(20)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: fallback)
    result = topic_fetcher.fetch_topics(profile="cricket_global", limit=20)
    assert len(result) == 20


def test_niche_sports_path_remains_available():
    rows = [make_topic("Tennis title upset", description="Tennis"), make_topic("Cricket record", description="Cricket")]
    prepared = topic_fetcher._prepare(rows, set(), profile="niche_sports")
    assert [row.title for row in prepared] == ["Tennis title upset"]


def test_niche_sports_groups_headlines_by_shared_named_keyword():
    rows = [
        make_topic("Carlos Alcaraz returns after knee injury", url="https://example.com/alcaraz-1"),
        make_topic("Carlos Alcaraz signs major endorsement deal", url="https://example.com/alcaraz-2"),
        make_topic("Lando Norris takes surprise Formula 1 podium", url="https://example.com/norris"),
    ]
    chosen = topic_fetcher._select(rows, 2, set(), profile="niche_sports")
    alcaraz = next(item for item in chosen if item.group_key == "keyword:carlos alcaraz")
    assert len(alcaraz.group_members) == 2
    assert {item.url for item in alcaraz.group_members} == {
        "https://example.com/alcaraz-1",
        "https://example.com/alcaraz-2",
    }


def test_top5_fetcher_uses_smaller_query_plan(monkeypatch):
    queries = []
    rows = [
        make_topic(
            f"Player{index} wins Event{index} cricket headline",
            source=f"source{index}.com",
            url=f"https://example.com/top5/{index}",
            description="Cricket news",
        )
        for index in range(25)
    ]
    monkeypatch.setattr(
        topic_fetcher,
        "_fetch_google",
        lambda query, timeout: queries.append((query, timeout)) or rows,
    )
    result = topic_fetcher.fetch_top5_topics(limit=20)
    assert len(queries) == 2
    assert all(timeout == topic_fetcher.TOP5_TIMEOUT for _, timeout in queries)
    assert len(result) == 20


def test_top5_fetcher_more_excludes_existing(monkeypatch):
    existing = [
        make_topic("Player0 wins Event0 cricket headline", url="https://example.com/top5/0")
    ]
    rows = [
        make_topic(
            f"Fresh player {index} wins new cricket event {index}",
            source=f"fresh{index}.com",
            url=f"https://example.com/top5/fresh/{index}",
            description="Cricket news",
        )
        for index in range(20)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query, timeout: rows)
    result = topic_fetcher.fetch_top5_topics(
        more=True,
        exclude_topics=existing,
        limit=20,
    )
    assert result
    assert all(item.url != existing[0].url for item in result)


def test_youtube_trend_queries_use_youtube_property_and_autocomplete(monkeypatch):
    calls = []

    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload

        def json(self):
            return self._payload

    explore = {
        "widgets": [{
            "id": "RELATED_QUERIES_0",
            "request": {"restriction": {"complexKeywordsRestriction": {"keyword": [{"value": "cricket"}]}}},
            "token": "token",
        }]
    }
    related = {
        "default": {
            "rankedList": [
                {"rankedKeyword": [{"query": "India cricket", "value": 100}]},
                {"rankedKeyword": [{"query": "India cricket today", "value": "Breakout"}]},
            ]
        }
    }

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs.get("params") or {}))
        if "explore" in url:
            return Response(text=")]}'," + json.dumps(explore))
        if "relatedsearches" in url:
            return Response(text=")]}'," + json.dumps(related))
        return Response(payload=["", [["India cricket today", 0], ["cricket", 0]]])

    monkeypatch.setattr(topic_fetcher.requests, "get", fake_get)
    rows = topic_fetcher._youtube_trend_queries("cricket")

    assert any(
        '"property": "youtube"' in params["req"]
        for method, _, params in calls if method == "get" and "explore" in _
    )
    assert rows[1]["autocomplete"] is True
    assert any(row["breakout"] for row in rows)


def test_youtube_trend_queries_use_indian_geo_for_primary_seeds(monkeypatch):
    calls = []

    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload

        def json(self):
            return self._payload

    explore = {
        "widgets": [{
            "id": "RELATED_QUERIES_0",
            "request": {"restriction": {"complexKeywordsRestriction": {"keyword": [{"value": "cricket"}]}}},
            "token": "token",
        }]
    }
    related = {
        "default": {
            "rankedList": [
                {"rankedKeyword": [{"query": "Virat Kohli", "value": 100}]},
            ]
        }
    }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs.get("params") or {}))
        if "explore" in url:
            return Response(text=")]}'," + json.dumps(explore))
        if "relatedsearches" in url:
            return Response(text=")]}'," + json.dumps(related))
        return Response(payload=["", []])

    monkeypatch.setattr(topic_fetcher.requests, "get", fake_get)

    topic_fetcher._youtube_trend_queries("cricket")
    params = next(params for url, params in calls if "explore" in url)
    request = json.loads(params["req"])
    assert request["comparisonItem"][0]["geo"] == "IN"
    assert params["hl"] == "en-IN"


def test_fetch_youtube_search_trends_india_signals_rank_above_global(monkeypatch):
    def fake_queries(seed):
        if seed == "cricket":
            return [{
                "keyword": "Virat Kohli return",
                "signal": "Rising",
                "rank": 1,
                "breakout": False,
                "seed": seed,
                "autocomplete": False,
            }]
        if seed == "international cricket":
            return [{
                "keyword": "International cricket return",
                "signal": "Rising",
                "rank": 1,
                "breakout": False,
                "seed": seed,
                "autocomplete": False,
            }]
        return []

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)

    def fake_google(query, timeout=topic_fetcher.TIMEOUT, *, geo="IN"):
        if "virat kohli" in query.casefold():
            return [
                make_topic(
                    "Virat Kohli return confirmed",
                    hours=0,
                    source="ESPNcricinfo",
                    description="India cricket development",
                    url="https://example.com/india-story",
                )
            ]
        return [
            make_topic(
                "International cricket return confirmed",
                hours=0,
                source="ESPNcricinfo",
                description="International cricket development",
                url="https://example.com/global-story",
            )
        ]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    result = topic_fetcher.fetch_youtube_search_trends(2)

    assert [item["keyword"] for item in result] == [
        "virat kohli return",
        "international cricket return",
    ]
    assert result[0]["score"] > result[1]["score"]


def test_fetch_youtube_search_trends_returns_news_backed_story_pool(monkeypatch):
    def fake_queries(seed):
        return [{
            "keyword": "India cricket today",
            "signal": "Rising",
            "rank": 1,
            "breakout": True,
            "seed": seed,
            "autocomplete": True,
        }]

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)
    monkeypatch.setattr(
        topic_fetcher,
        "_fetch_google",
        lambda query, timeout=topic_fetcher.TIMEOUT, *, geo="IN": [
            make_topic(
                "India announce new cricket squad",
                hours=0,
                source="ESPNcricinfo",
                description="India cricket selection",
            ),
            make_topic(
                "India announced a cricket squad yesterday",
                hours=25,
                source="ESPNcricinfo",
                description="India cricket selection",
            ),
        ],
    )
    result = topic_fetcher.fetch_youtube_search_trends(20)
    assert result
    assert result[0]["keyword"] == "india cricket"
    assert result[0]["trend_query"] == "India cricket today"
    assert result[0]["profile"] == "cricket_india_asia"
    assert result[0]["hashtag"] == "#indiacricket"
    assert result[0]["news_count"] == 1
    assert [topic.title for topic in result[0]["topics"]] == ["India announce new cricket squad"]



def test_fetch_youtube_search_trends_checks_only_requested_number_of_candidates(monkeypatch):
    def fake_queries(seed):
        if seed == "tennis":
            return [
                {
                    "keyword": f"Tennis player story {index}",
                    "signal": "Rising",
                    "rank": index,
                    "breakout": False,
                    "seed": seed,
                    "autocomplete": True,
                }
                for index in range(1, 9)
            ]
        return []

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)
    calls = []

    def fake_google(query, timeout=topic_fetcher.TIMEOUT, *, geo="IN"):
        calls.append(query)
        return [
            make_topic(
                "Tennis player story becomes breaking news",
                hours=0,
                source="ATP",
                description="Tennis news",
                url=f"https://example.com/{len(calls)}",
            )
        ]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    result = topic_fetcher.fetch_youtube_search_trends(5)

    assert len(result) == 5
    assert len(calls) == 5


def test_youtube_trends_use_broad_trend_query_for_news_matching(monkeypatch):
    def fake_queries(seed):
        if seed == "tennis":
            return [{
                "keyword": "tennis player disqualified",
                "signal": "Rising",
                "rank": 1,
                "breakout": False,
                "seed": seed,
                "autocomplete": True,
            }]
        return []

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)
    captured = []

    def fake_google(query, timeout=topic_fetcher.TIMEOUT, *, geo="IN"):
        captured.append(query)
        return [
            make_topic(
                "Player disqualified after tennis tournament incident",
                hours=0,
                source="ATP",
                description="Tennis disciplinary decision",
            )
        ]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    result = topic_fetcher.fetch_youtube_search_trends(20)

    assert result
    assert result[0]["keyword"] == "tennis player disqualified"
    assert "tennis player disqualified" in captured[0].lower()
    assert result[0]["topics"][0].title.startswith("Player disqualified")
    assert result[0]["top_news_title"] == result[0]["topics"][0].title


def test_youtube_trends_reject_generic_queries_and_validate_real_story_signals(monkeypatch):
    def fake_queries(seed):
        if seed == "tennis":
            return [
                {
                    "keyword": "Carlos Alcaraz",
                    "signal": "Rising",
                    "rank": 1,
                    "breakout": False,
                    "seed": seed,
                    "autocomplete": True,
                },
                {
                    "keyword": "tennis live today",
                    "signal": "Rising",
                    "rank": 2,
                    "breakout": False,
                    "seed": seed,
                    "autocomplete": False,
                },
            ]
        return []

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)

    def fake_google(query, timeout=topic_fetcher.TIMEOUT, *, geo="IN"):
        if "carlos alcaraz" in query.casefold():
            return [
                make_topic(
                    "Carlos Alcaraz advances after straight sets win",
                    hours=0,
                    source="ATP",
                    description="Tennis result",
                )
            ]
        return []

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    result = topic_fetcher.fetch_youtube_search_trends(20)
    assert [item["keyword"] for item in result] == ["carlos alcaraz"]
    assert result[0]["news_count"] == 1


def test_youtube_trends_reject_sports_only_queries(monkeypatch):
    def fake_queries(seed):
        if seed == "cricket":
            return [{
                "keyword": "t20th cricket live today",
                "signal": "Rising",
                "rank": 1,
                "breakout": True,
                "seed": seed,
                "autocomplete": True,
            }]
        return []

    monkeypatch.setattr(topic_fetcher, "_youtube_trend_queries", fake_queries)
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda *args, **kwargs: [])
    with pytest.raises(RuntimeError, match="story-worthy signals"):
        topic_fetcher.fetch_youtube_search_trends(20)



def test_fetch_youtube_trend_topics_uses_only_last_24_hours_and_global_news(monkeypatch):
    current = make_topic(
        "Virat Kohli returns to India cricket",
        hours=23.5,
        description="Cricket news",
        url="https://example.com/current",
    )
    previous = make_topic(
        "Virat Kohli returns to India cricket yesterday",
        hours=24.5,
        description="Cricket news",
        url="https://example.com/previous",
    )
    captured = []

    def fake_google(query, timeout=topic_fetcher.TIMEOUT, *, geo="IN"):
        captured.append((query, geo))
        return [current, previous]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    result = topic_fetcher.fetch_youtube_trend_topics(
        "Virat Kohli", "cricket_india_asia", limit=20
    )
    assert len(result) == 1
    assert result[0].title == current.title
    assert result[0].url == current.url
    assert result[0].published_at == current.published_at
    assert captured
    assert all(geo is None for _, geo in captured)
    assert all("when:1d" in query for query, _ in captured)
    assert all("after:" not in query and "before:" not in query for query, _ in captured)
