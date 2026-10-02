from dataclasses import replace
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
    gill_events = ["injury", "contract", "retirement", "debut", "comeback"]
    rows = [
        make_topic(
            f"Shubman Gill {event} development",
            source=f"gill{index}.com",
            url=f"https://example.com/gill/{index}",
        )
        for index, event in enumerate(gill_events)
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
