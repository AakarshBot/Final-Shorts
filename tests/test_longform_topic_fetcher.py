from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET

import pytest
import requests

import longform_topic_fetcher as fetcher


@pytest.fixture(autouse=True)
def _disable_curated_network_feeds_in_unit_tests(monkeypatch):
    # Networked feed parsing is tested separately; preserve deterministic mocks.
    monkeypatch.setattr(fetcher, "fetch_cricket_feed_items", lambda **kwargs: [])


def _item(title, url, publisher="ESPNcricinfo", hours=2, summary="A detailed report covering the decision and its consequences."):
    published = format_datetime(datetime.now(timezone.utc) - timedelta(hours=hours))
    return (
        "<item>"
        f"<title>{title}</title>"
        f"<link>{url}</link>"
        f"<description>{summary}</description>"
        f"<pubDate>{published}</pubDate>"
        f'<source url="https://{publisher.lower().replace(" ", "")}.com">{publisher}</source>'
        "</item>"
    )


def _feed(*items):
    return "<rss><channel>" + "".join(items) + "</channel></rss>"


class _Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def _mock_feeds(monkeypatch, xml):
    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, dict(params), timeout))
        return _Response(xml)

    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    return calls


def test_fetch_returns_ranked_story_with_source_metadata(monkeypatch):
    xml = _feed(_item(
        "India selectors drop senior batter after major selection dispute",
        "https://publisher.example/cricket/selection-story",
    ))
    calls = _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics(limit=20)

    assert len(result) == 1
    story = result[0]
    assert story["title"].startswith("India selectors")
    assert story["url"] == "https://publisher.example/cricket/selection-story"
    assert story["publisher"] == "ESPNcricinfo"
    assert story["desk"] == "Cricket"
    assert story["profile"] == "Long-form"
    assert story["story_id"]
    assert story["event_id"]
    assert story["ranking_reason"]
    assert len(calls) == len(fetcher.QUERIES)
    assert all(set(params) == {"q", "hl"} for _, params, _ in calls)


def test_filters_stale_utility_and_non_cricket_results(monkeypatch):
    xml = _feed(
        _item("India cricket board faces major governance dispute", "https://a.test/story"),
        _item("Cricket live score and scorecard today", "https://a.test/scorecard"),
        _item("Football club announces new manager after dispute", "https://a.test/football"),
        _item(
            "Cricket selection dispute reaches new turning point",
            "https://a.test/stale",
            hours=24 * (fetcher.LOOKBACK_DAYS + 2),
        ),
    )
    _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics()

    assert [story["url"] for story in result] == ["https://a.test/story"]


def test_same_event_reports_merge_without_losing_source_urls(monkeypatch):
    xml = _feed(
        _item(
            "India selectors drop senior batter from squad after poor form",
            "https://espn.example/india-selection",
            "ESPNcricinfo",
        ),
        _item(
            "India selectors drop experienced batter from squad following poor form",
            "https://news.example/selection-followup",
            "BBC Sport",
            hours=3,
        ),
    )
    _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics()

    assert len(result) == 1
    assert result[0]["report_count"] == 2
    assert {report["url"] for report in result[0]["reports"]} == {
        "https://espn.example/india-selection",
        "https://news.example/selection-followup",
    }


def test_same_player_different_event_families_remain_separate(monkeypatch):
    xml = _feed(
        _item(
            "Virat Kohli faces new selection dispute after squad decision",
            "https://a.test/selection",
        ),
        _item(
            "Virat Kohli retirement decision sparks career debate",
            "https://b.test/retirement",
            "BBC Sport",
            hours=3,
        ),
    )
    _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics()

    assert len(result) == 2
    assert {story["url"] for story in result} == {
        "https://a.test/selection",
        "https://b.test/retirement",
    }


def test_more_uses_alternate_queries_and_excludes_seen_event(monkeypatch):
    seen = {
        "title": "India selectors drop senior batter from squad after poor form",
        "url": "https://seen.example/selection",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    xml = _feed(
        _item(
            "India selectors drop experienced batter from squad following poor form",
            "https://other.example/same-event",
        ),
        _item(
            "Cricket board governance dispute changes domestic competition plans",
            "https://new.example/governance",
            "Reuters",
            hours=4,
        ),
    )
    calls = _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics(already_seen=[seen], more=True, limit=20)

    assert [story["url"] for story in result] == ["https://new.example/governance"]
    assert len(calls) == len(fetcher.MORE_QUERIES)
    assert calls[0][1]["q"] in fetcher.MORE_QUERIES


def test_manual_keyword_adds_focused_queries(monkeypatch):
    xml = _feed(_item(
        "Chennai Super Kings franchise governance decision opens new debate",
        "https://a.test/csk",
    ))
    calls = _mock_feeds(monkeypatch, xml)

    fetcher.fetch_longform_topics(keyword="Chennai Super Kings")

    queries = [params["q"] for _, params, _ in calls]
    assert len(queries) == len(fetcher.QUERIES) + 2
    assert any('"Chennai Super Kings" cricket when:14d' == query for query in queries)


def test_feed_failure_is_reported(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(fetcher.requests, "get", fail)
    with pytest.raises(RuntimeError, match="Google News could not be reached"):
        fetcher.fetch_longform_topics()


def test_iso_publication_dates_rank_recent_over_old():
    now = datetime.now(timezone.utc)
    base = {
        "title": "India cricket selection decision",
        "publisher": "ESPNcricinfo",
        "summary": "An evidence-rich story with relevant background and consequences.",
        "depth_signals": ["selection", "decision"],
    }
    recent = {**base, "published_at": now.isoformat()}
    older = {**base, "published_at": (now - timedelta(days=10)).isoformat()}

    assert fetcher._score(recent, now) > fetcher._score(older, now)


def test_topic_limit_is_respected(monkeypatch):
    xml = _feed(
        _item(
            "India cricket board governance dispute changes league contract terms",
            "https://a.test/one",
        ),
        _item(
            "England cricket selectors announce controversial captaincy decision",
            "https://b.test/two",
            "BBC Sport",
            hours=4,
        ),
        _item(
            "Australia cricket retirement announcement reshapes team plans",
            "https://c.test/three",
            "Reuters",
            hours=5,
        ),
    )
    _mock_feeds(monkeypatch, xml)

    result = fetcher.fetch_longform_topics(limit=2)

    assert len(result) == 2
