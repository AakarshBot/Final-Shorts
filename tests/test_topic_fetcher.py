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
    assert [row.title for row in prepared] == [rows[-1].title]


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


def test_twenty_results_remain_available_from_large_unique_pool(monkeypatch):
    rows = [
        make_topic(f"Cricket event {index} appointment", source=f"source{index}.com", url=f"https://example.com/{index}")
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
    fallback = [make_topic(f"GDELT cricket story {i} record", url=f"https://gdelt.example/{i}") for i in range(20)]
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: fallback)
    result = topic_fetcher.fetch_topics(profile="cricket_global", limit=20)
    assert len(result) == 20


def test_trendflow_is_not_required_for_topic_fetcher():
    assert not hasattr(topic_fetcher, "trendflow")
