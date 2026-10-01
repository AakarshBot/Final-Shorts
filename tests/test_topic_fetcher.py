from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import topic_fetcher


def make_topic(title, hours=1, source="Test", url=None, description=""):
    now = datetime.now(timezone.utc)
    return topic_fetcher.Topic(
        title,
        source,
        now - timedelta(hours=hours),
        url or f"https://example.com/{abs(hash(title))}",
        description,
    )


def test_handoff_contract_is_unchanged():
    topic = make_topic("Shubman Gill injury update", source="ESPNcricinfo")
    prepared = topic_fetcher._prepare([topic], set(), profile="cricket_india_asia")
    assert prepared[0].title == topic.title
    assert prepared[0].source == topic.source
    assert prepared[0].published_at == topic.published_at
    assert prepared[0].url == topic.url
    assert prepared[0].description == topic.description


def test_requested_cricket_story_types_survive_filter():
    rows = [
        make_topic("MCC announces major cricket law changes", description="The MCC Head of Cricket announced changes to the Laws of Cricket aimed at curbing bat dominance."),
        make_topic("WPL 2027 retention lists drop", description="The Women's Premier League announced franchise retention and release lists."),
        make_topic("South Africa's exchangeable pitch innovation", description="Cricket South Africa is trialing exchangeable pitches to address pitch fatigue."),
        make_topic("Mark Boucher takes the MI Emirates reins", description="Mark Boucher has been appointed head coach of the MI Emirates cricket franchise."),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert len(prepared) == 4


def test_non_cricket_story_is_still_rejected():
    row = make_topic("President announces new policy", description="National politics and government policy update.")
    assert topic_fetcher._prepare([row], set(), profile="cricket_india_asia") == []


def test_same_match_event_clusters_but_different_events_survive():
    rows = [
        make_topic("India beat West Indies in first ODI", url="https://x/1"),
        make_topic("India complete win over West Indies in ODI", url="https://x/2"),
        make_topic("MCC announces major cricket law changes", description="MCC law changes to rebalance bat and ball", url="https://x/3"),
        make_topic("Mark Boucher appointed by MI Emirates", description="Mark Boucher joins MI Emirates as head coach", url="https://x/4"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 3, set(), profile="cricket_india_asia")
    assert len(chosen) == 3
    assert sum("West Indies" in x.title for x in chosen) == 1
    assert any("MCC" in x.title for x in chosen)
    assert any("Boucher" in x.title for x in chosen)


def test_many_articles_of_one_event_do_not_fill_twenty():
    rows = [
        make_topic(
            f"India beat West Indies first ODI report number {i}",
            url=f"https://x/w{i}",
        )
        for i in range(18)
    ]
    categories = ["appointment", "record", "injury", "retention"]
    rows.extend(
        make_topic(
            f"Alpha{i} Beta{i} cricket {categories[i % len(categories)]}",
            url=f"https://x/e{i}",
        )
        for i in range(20)
    )
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 20, set(), profile="cricket_india_asia")
    assert len(chosen) == 20
    assert sum("West Indies" in x.title for x in chosen) == 1


def test_more_excludes_existing_event():
    existing = [make_topic("India beat West Indies first ODI", url="https://x/old")]
    rows = [
        make_topic("India defeat West Indies in first ODI", url="https://x/new"),
        make_topic("WPL announces retention list", description="Women's Premier League", url="https://x/wpl"),
    ]
    prepared = topic_fetcher._prepare(rows, {existing[0].url}, profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 20, {existing[0].url}, existing=existing, profile="cricket_india_asia")
    assert [x.title for x in chosen] == [rows[1].title]


def test_more_fetch_skips_trend_lookup(monkeypatch):
    captured = []

    def fail_trends(*args, **kwargs):
        raise AssertionError("More fetch must not call the trend service")

    monkeypatch.setattr(topic_fetcher, "_trend_signals", fail_trends)
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda q: captured.append(q) or [])
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda q: [])

    topic_fetcher.fetch_topics(profile="cricket_india_asia", more=True, limit=20)

    assert captured == topic_fetcher.MORE_QUERIES["cricket_india_asia"]


def test_prepare_deduplicates_repeated_article_urls():
    topic = make_topic("WPL retention list announced", url="https://example.com/story?utm_source=one")
    duplicate = make_topic("WPL franchise retention list announced", url="https://example.com/story?utm_source=two")
    prepared = topic_fetcher._prepare([topic, duplicate], set(), profile="cricket_india_asia")
    assert len(prepared) == 1


def test_trendflow_is_optional(monkeypatch):
    monkeypatch.setattr(topic_fetcher, "trendflow", None)
    assert topic_fetcher._trend_signals("cricket_india_asia") == []


def test_trend_signal_becomes_search_query(monkeypatch):
    captured = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def trending_now(self, region=None, **kwargs):
            item = SimpleNamespace(
                title="WPL 2027 retention",
                growth=300,
                volume=50000,
                started_at=datetime.now(timezone.utc),
                active=True,
            )
            return SimpleNamespace(results=[item])

    monkeypatch.setattr(topic_fetcher, "trendflow", SimpleNamespace(Client=FakeClient))
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda q: captured.append(q) or [])
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda q: [])
    topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert any("WPL 2027 retention" in q for q in captured)


def test_keyword_search_still_uses_keyword_queries(monkeypatch):
    captured = []
    monkeypatch.setattr(
        topic_fetcher,
        "_fetch_google",
        lambda q: captured.append(q) or [make_topic("Babar Azam Pakistan cricket comeback")],
    )
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda q: [])
    result = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        keyword="Babar Azam",
        limit=1,
    )
    assert result
    assert captured and all("Babar Azam" in q for q in captured)


def test_fetch_topics_preserves_a_twenty_story_pool(monkeypatch):
    rows = [
        make_topic(
            f"Cricket event {i} announcement",
            source=f"source{i % 6}.com",
            url=f"https://example.com/{i}",
        )
        for i in range(30)
    ]
    monkeypatch.setattr(topic_fetcher, "_trend_signals", lambda *args, **kwargs: [])
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    result = topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert len(result) == 20
    assert len({topic.url for topic in result}) == 20


def test_invalid_dates_are_not_fresh():
    row = topic_fetcher.Topic(
        "Cricket record story",
        "Test",
        topic_fetcher._parse_date("not-a-date"),
        "https://example.com/invalid",
        "",
    )
    assert topic_fetcher._prepare([row], set(), profile="cricket_india_asia") == []


def test_niche_profile_rejects_cricket():
    row = make_topic("India cricket team wins", description="Cricket update")
    assert topic_fetcher._prepare([row], set(), profile="niche_sports") == []

def test_similar_boilerplate_does_not_merge_distinct_events():
    rows = [
        make_topic("Alpha player appointed as coach", description="Cricket appointment"),
        make_topic("Beta player appointed as coach", description="Cricket appointment"),
        make_topic("Gamma player appointed as coach", description="Cricket appointment"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 3, set(), profile="cricket_india_asia")
    assert len(chosen) == 3
