from datetime import datetime, timedelta, timezone

import topic_fetcher


def make_topic(title, hours=1, source="Test", url=None, description=""):
    now = datetime.now(timezone.utc)
    return topic_fetcher.Topic(
        title,
        source,
        now - timedelta(hours=hours),
        url or f"https://example.com/{hash(title)}",
        description,
    )


def test_title_source_suffix_is_cleaned():
    topic = make_topic(
        "Need to be ten times better after injury layoff, says Prasidh Krishna | Cricket - hindustantimes.com",
        source="hindustantimes.com",
    )
    prepared = topic_fetcher._prepare([topic], set(), profile="cricket_india_asia")
    assert prepared[0].title == "Need to be ten times better after injury layoff, says Prasidh Krishna"


def test_utility_pages_are_removed():
    rows = [
        make_topic("India cricket schedule and fixtures for next month"),
        make_topic("How to watch India vs West Indies live streaming"),
        make_topic("India vs West Indies 1st ODI Playing XI predicted"),
        make_topic("Shubman Gill suffers injury scare in nets ahead of ODI"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert [r.title for r in prepared] == [rows[3].title]


def test_generic_listing_pages_are_removed():
    rows = [
        make_topic("Sports News"),
        make_topic("Today's Top 10 Cricket News - September 26"),
        make_topic("Virat Kohli confirms 2027 World Cup will be his last"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert len(prepared) == 1


def test_cricket_player_headline_survives_without_cricket_word():
    row = make_topic(
        "Need to be ten times better after injury layoff, says Prasidh Krishna",
        description="Prasidh Krishna discussed his return to international cricket after an injury layoff.",
    )
    prepared = topic_fetcher._prepare([row], set(), profile="cricket_india_asia")
    assert [r.title for r in prepared] == [row.title]


def test_non_cricket_story_is_not_rescued_by_publisher_boilerplate():
    rows = [
        make_topic(
            "President Murmu hails Sawan Barwal's Asian Games marathon silver",
            description="Cricketnmore latest cricket and sports updates.",
        ),
        make_topic("Virat Kohli confirms 2027 World Cup will be his last"),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert [r.title for r in prepared] == [rows[1].title]


def test_same_retirement_event_clusters():
    rows = [
        make_topic("Virat Kohli confirms 2027 ODI World Cup will be his last for India"),
        make_topic("Virat Kohli confirms World Cup 2027 will be his final ODI for India"),
        make_topic("Virat Kohli's 2027 farewell puts India's ODI transition into focus"),
        make_topic("Virat Kohli reveals key mentality switch in ODIs"),
    ]
    chosen = topic_fetcher._select(
        topic_fetcher._prepare(rows, set(), profile="cricket_india_asia"),
        20,
        set(),
    )
    assert len(chosen) == 2


def test_same_subject_different_event_is_kept():
    rows = [
        make_topic("Shubman Gill suffers injury scare in nets ahead of West Indies ODI"),
        make_topic("Shubman Gill scores a century to lead India to a win over England"),
    ]
    chosen = topic_fetcher._select(
        topic_fetcher._prepare(rows, set(), profile="cricket_india_asia"),
        20,
        set(),
    )
    assert len(chosen) == 2


def test_cross_headline_match_context_clusters_related_ind_wi_event():
    rows = [
        make_topic("India vs West Indies first ODI playing 11 announced"),
        make_topic("Rohit and Kohli return as India begin home ODI season against West Indies"),
        make_topic("West Indies tour of India: India vs West Indies first ODI updates"),
    ]
    filtered = [
        rows[1],
        rows[2],
    ]
    prepared = topic_fetcher._prepare(filtered, set(), profile="cricket_india_asia")
    chosen = topic_fetcher._select(prepared, 20, set())
    assert len(chosen) == 1


def test_interest_signals_raise_topic_score():
    generic = make_topic("India cricket wins match")
    pull = make_topic("Shubman Gill reacts after historic record")
    assert topic_fetcher._score(pull) > topic_fetcher._score(generic)


def test_niche_profile_rejects_cricket_only_story():
    row = make_topic("India men's cricket team arrives in Nagoya for Asian Games cricket")
    assert topic_fetcher._prepare([row], set(), profile="niche_sports") == []


def test_freshness_and_profile_relevance_are_enforced():
    rows = [
        make_topic("Old cricket record story", hours=80),
        make_topic("Local politics statement today", hours=1, description="cricket updates"),
        make_topic("Indian badminton star wins major title", hours=2),
        make_topic("Shubman Gill injury scare before West Indies ODI", hours=2),
    ]
    prepared = topic_fetcher._prepare(rows, set(), profile="cricket_india_asia")
    assert [r.title for r in prepared] == [rows[3].title]


def test_more_query_set_is_distinct():
    assert set(topic_fetcher.QUERIES["cricket_india_asia"]).isdisjoint(
        topic_fetcher.MORE_QUERIES["cricket_india_asia"]
    )


def test_fetch_topics_can_return_twenty_distinct_events(monkeypatch):
    rows = [
        make_topic(
            f"India cricket Alpha{i} {'record' if i % 2 == 0 else 'win'}",
            url=f"https://example.com/{i}",
        )
        for i in range(20)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    topics = topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert len(topics) == 20


def test_fetch_topics_uses_secondary_source_when_google_clusters_too_heavily(monkeypatch):
    google_rows = [
        make_topic(
            f"Virat Kohli retirement record story {i}",
            url=f"https://google.example.com/{i}",
        )
        for i in range(10)
    ]
    gdelt_rows = [
        make_topic(
            f"Player{i} cricket record milestone event",
            url=f"https://gdelt.example.com/{i}",
        )
        for i in range(19)
    ]
    monkeypatch.setattr(topic_fetcher, "_fetch_google", lambda query: google_rows)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: gdelt_rows)
    topics = topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert len(topics) == 20


def test_more_results_exclude_existing_events():
    existing = [
        make_topic("Shubman Gill suffers injury scare in nets ahead of West Indies ODI")
    ]
    new_rows = [
        make_topic(
            "Shubman Gill hit by delivery and appears in pain ahead of West Indies ODI",
            url="https://example.com/new",
        ),
        make_topic(
            "Cricket India sponsor deal announced for home series",
            url="https://example.com/other",
        ),
    ]
    rows = topic_fetcher._prepare(new_rows, {existing[0].url}, profile="cricket_india_asia")
    selected = topic_fetcher._select(rows, 20, {existing[0].url}, existing)
    assert [t.title for t in selected] == [new_rows[1].title]


def test_invalid_dates_are_not_treated_as_fresh():
    row = topic_fetcher.Topic(
        "Cricket record story",
        "Test",
        topic_fetcher._parse_date("not-a-date"),
        "https://example.com/invalid-date",
        "",
    )
    assert topic_fetcher._prepare([row], set(), profile="cricket_india_asia") == []


def test_one_failed_google_query_does_not_abort_the_fetch(monkeypatch):
    import requests

    good = make_topic("India cricket record update")
    calls = []

    def fake_google(query):
        calls.append(query)
        if query == topic_fetcher.QUERIES["cricket_india_asia"][0]:
            raise requests.RequestException("temporary")
        return [good]

    monkeypatch.setattr(topic_fetcher, "_fetch_google", fake_google)
    monkeypatch.setattr(topic_fetcher, "_fetch_gdelt", lambda query: [])
    result = topic_fetcher.fetch_topics(profile="cricket_india_asia", limit=20)
    assert result
    assert len(calls) == len(topic_fetcher.QUERIES["cricket_india_asia"])
