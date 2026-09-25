from datetime import datetime, timedelta, timezone

import topic_fetcher


def make_topic(title, hours=1, source="Test", url=None):
    now = datetime.now(timezone.utc)
    return topic_fetcher.Topic(
        title,
        source,
        now - timedelta(hours=hours),
        url or f"https://example.com/{hash(title)}",
        "",
    )


def test_utility_pages_are_removed():
    rows = [
        make_topic("India cricket schedule and fixtures for next month"),
        make_topic("BCCI announces India squad for the next ODI"),
        make_topic("Shubman Gill suffers injury scare in nets ahead of ODI"),
    ]
    prepared = topic_fetcher._prepare(rows, set())
    assert [r.title for r in prepared] == [rows[2].title]


def test_related_headlines_cluster_as_one_event():
    rows = [
        make_topic("Injury scare for Shubman Gill before West Indies ODIs"),
        make_topic("Shubman Gill hit by Mohammed Siraj delivery and appears in pain ahead of 1st ODI vs WI"),
        make_topic("Shubman Gill suffers injury scare in Thiruvananthapuram nets ahead of India vs West Indies"),
        make_topic("India captain Shubman Gill cops elbow blow ahead of West Indies clash"),
    ]
    chosen = topic_fetcher._select(rows, 20, set())
    assert len(chosen) == 1


def test_same_subject_different_event_is_kept():
    rows = [
        make_topic("Shubman Gill suffers injury scare in nets ahead of West Indies ODI"),
        make_topic("Shubman Gill scores a century to lead India to a win over England"),
    ]
    chosen = topic_fetcher._select(rows, 20, set())
    assert len(chosen) == 2


def test_freshness_and_sports_relevance_are_enforced():
    rows = [
        make_topic("Old cricket record story", hours=80),
        make_topic("Local politics statement today", hours=1),
        make_topic("Indian badminton star wins major title", hours=2),
    ]
    prepared = topic_fetcher._prepare(rows, set())
    assert [r.title for r in prepared] == [rows[2].title]


def test_more_query_set_is_distinct():
    assert set(topic_fetcher.QUERIES["cricket_india_asia"]).isdisjoint(
        topic_fetcher.MORE_QUERIES["cricket_india_asia"]
    )


def test_fetch_topics_can_return_twenty_distinct_events(monkeypatch):
    rows = [
        make_topic(
            f"Cricket Alpha{i} {'record' if i % 2 == 0 else 'win'}",
            url=f"https://example.com/{i}",
        )
        for i in range(20)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)
    monkeypatch.setattr(
        topic_fetcher,
        "_fetch_gdelt",
        lambda query: (_ for _ in ()).throw(
            AssertionError("fallback should not run")
        ),
    )
    topics = topic_fetcher.fetch_topics(limit=20)
    assert len(topics) == 20


def test_more_results_do_not_repeat_an_existing_event(monkeypatch):
    existing = [
        make_topic(
            "Shubman Gill suffers injury scare in nets ahead of West Indies ODI"
        )
    ]
    new_rows = [
        make_topic(
            "Shubman Gill hit by delivery and appears in pain ahead of West Indies ODI",
            url="https://example.com/new",
        ),
        make_topic(
            "Cricket Alpha replacement wins a major title",
            url="https://example.com/other",
        ),
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: new_rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    topics = topic_fetcher.fetch_topics(
        more=True, exclude_topics=existing, limit=20
    )
    assert [t.title for t in topics] == [new_rows[1].title]
