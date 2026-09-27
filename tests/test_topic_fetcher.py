from datetime import datetime, timedelta, timezone

import pytest

import topic_fetcher


def make_topic(title, hours=1, source="Test", url=None, description="cricket story"):
    now = datetime.now(timezone.utc)
    return topic_fetcher.Topic(
        title=title,
        source=source,
        published_at=now - timedelta(hours=hours),
        url=url or f"https://example.com/{abs(hash(title))}",
        description=description,
    )


def test_non_story_pages_are_removed_but_real_news_is_kept():
    rows = [
        make_topic("India cricket schedule and fixtures for next month"),
        make_topic("Prediction: India vs West Indies 1st ODI lineups and pitch report"),
        make_topic("How to watch India vs West Indies ODI live streaming"),
        make_topic("Sports News - Latest Updates"),
        make_topic("Wisden Weekly Cricket Quiz"),
        make_topic("BCCI announces India squad for West Indies ODI"),
    ]

    prepared = topic_fetcher._prepare(rows, set(), "cricket_india_asia")

    assert [row.title for row in prepared] == [
        "BCCI announces India squad for West Indies ODI"
    ]


def test_wrong_sport_does_not_enter_cricket_profile():
    rows = [
        make_topic(
            "Sonali Shingate dedicates Asian Games kabaddi gold to family",
            description="kabaddi report from the Asian Games",
        ),
        make_topic(
            "India men's cricket team arrives in Nagoya for Asian Games",
            description="cricket report",
        ),
    ]

    prepared = topic_fetcher._prepare(rows, set(), "cricket_india_asia")

    assert [row.title for row in prepared] == [
        "India men's cricket team arrives in Nagoya for Asian Games"
    ]


def test_invalid_and_stale_dates_are_removed():
    stale = make_topic("Old cricket record story", hours=80)
    invalid = topic_fetcher.Topic(
        "Cricket record story with invalid date",
        "Test",
        topic_fetcher._parse_date("not-a-date"),
        "https://example.com/invalid-date",
        "cricket story",
    )

    prepared = topic_fetcher._prepare(
        [stale, invalid],
        set(),
        "cricket_india_asia",
    )

    assert prepared == []


def test_related_headlines_cluster_as_one_story():
    rows = [
        make_topic("Injury scare for Shubman Gill before West Indies ODIs"),
        make_topic(
            "Shubman Gill hit by Mohammed Siraj delivery and appears in pain before 1st ODI vs WI"
        ),
        make_topic(
            "Shubman Gill suffers injury scare in Thiruvananthapuram nets before India vs West Indies"
        ),
        make_topic(
            "India captain Shubman Gill cops elbow blow before West Indies clash"
        ),
    ]

    chosen = topic_fetcher._select(rows, 20, set())

    assert len(chosen) == 1


def test_same_person_different_event_is_kept():
    rows = [
        make_topic("Shubman Gill suffers injury scare before West Indies ODI"),
        make_topic("Shubman Gill scores a century to lead India to a win over England"),
    ]

    chosen = topic_fetcher._select(rows, 20, set())

    assert len(chosen) == 2


def test_same_person_different_statement_is_kept():
    rows = [
        make_topic("Virat Kohli confirms 2027 ODI World Cup will be his final ODI"),
        make_topic("Virat Kohli reveals key mentality switch in ODIs"),
    ]

    chosen = topic_fetcher._select(rows, 20, set())

    assert len(chosen) == 2


def test_same_match_result_reports_cluster_as_one_story():
    rows = [
        make_topic(
            "Nepal chase 102-run target against Afghanistan at Asian Games",
            hours=3,
        ),
        make_topic(
            "Nepal defeat Afghanistan by five wickets at Asian Games",
            hours=5,
        ),
    ]

    chosen = topic_fetcher._select(rows, 20, set())

    assert len(chosen) == 1


def test_exact_duplicate_headline_is_only_selected_once():
    duplicate = make_topic("Cricket Player01 record 1")
    rows = [duplicate, duplicate]

    chosen = topic_fetcher._select(rows, 20, set())

    assert len(chosen) == 1


def test_interest_signals_raise_topic_score():
    generic = make_topic("India cricket story update")
    pull = make_topic("Shubman Gill reveals historic record")

    assert topic_fetcher._score(pull) > topic_fetcher._score(generic)


def test_term_matching_does_not_treat_latest_as_test():
    assert not topic_fetcher._contains_any(
        "latest cricket update",
        {"test"},
    )
    assert topic_fetcher._contains_any(
        "India Test cricket update",
        {"test"},
    )


def test_more_query_set_is_distinct():
    assert set(topic_fetcher.QUERIES["cricket_india_asia"]).isdisjoint(
        topic_fetcher.MORE_QUERIES["cricket_india_asia"]
    )


def test_query_batches_progress_after_existing_story_pool():
    batches = topic_fetcher._query_batches(
        "cricket_india_asia",
        more=False,
        existing_count=0,
    )
    more_batches = topic_fetcher._query_batches(
        "cricket_india_asia",
        more=True,
        existing_count=20,
    )

    assert batches[0][0] == topic_fetcher.QUERIES["cricket_india_asia"][0]
    assert more_batches[0][0] == topic_fetcher.QUERIES["cricket_india_asia"][6]


def test_fetch_topics_can_return_100_distinct_events(monkeypatch):
    rows = [
        make_topic(
            f"Cricket Player{i:03d} record {i}",
            url=f"https://example.com/story-{i}",
        )
        for i in range(100)
    ]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)

    def no_gdelt(query):
        raise AssertionError("GDELT recovery should not run when Google supplies 100 stories.")

    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", no_gdelt)

    topics = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        more=False,
        limit=100,
    )

    assert len(topics) == 100
    assert len({topic.url for topic in topics}) == 100
    assert len({topic.title for topic in topics}) == 100


def test_more_results_exclude_existing_event_and_headline(monkeypatch):
    existing = [
        make_topic(
            "Shubman Gill suffers injury scare in nets before West Indies ODI",
            url="https://example.com/existing",
        )
    ]
    rows = [
        make_topic(
            "Shubman Gill hit by delivery and appears in pain before West Indies ODI",
            url="https://example.com/repeat",
        ),
        make_topic(
            "Cricket Player002 comeback after long injury layoff",
            url="https://example.com/new",
        ),
    ]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])

    topics = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        more=True,
        exclude_topics=existing,
        limit=20,
    )

    assert [topic.title for topic in topics] == [rows[1].title]


def test_one_failed_google_query_does_not_abort_fetch(monkeypatch):
    import requests

    good = make_topic("India cricket record update", url="https://example.com/good")
    calls = []

    def fake_google(query):
        calls.append(query)
        if query == topic_fetcher.QUERIES["cricket_india_asia"][0]:
            raise requests.RequestException("temporary")
        return [good]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])

    result = topic_fetcher.fetch_topics(
        profile="cricket_india_asia",
        limit=20,
    )

    assert result
    assert result[0].title == good.title
    assert len(calls) == len(topic_fetcher.QUERIES["cricket_india_asia"]) + len(topic_fetcher.MORE_QUERIES["cricket_india_asia"])


def test_parse_rss_removes_publisher_suffix():
    xml = """
    <rss>
      <channel>
        <item>
          <title>Virat Kohli confirms final ODI - News18</title>
          <link>https://example.com/kohli?utm_source=google</link>
          <pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate>
          <description>Virat Kohli confirms his 2027 ODI plans.</description>
          <source>News18</source>
        </item>
      </channel>
    </rss>
    """

    rows = topic_fetcher._parse_rss(xml)

    assert rows[0].title == "Virat Kohli confirms final ODI"
    assert rows[0].url == "https://example.com/kohli"


def test_profile_specific_relevance_for_niche_sports():
    rows = [
        make_topic(
            "Tennis star completes stunning comeback after injury",
            description="tennis story",
        ),
        make_topic(
            "India cricket team wins ODI",
            description="cricket story",
        ),
    ]

    prepared = topic_fetcher._prepare(rows, set(), "niche_sports")

    assert [row.title for row in prepared] == [
        "Tennis star completes stunning comeback after injury"
    ]
