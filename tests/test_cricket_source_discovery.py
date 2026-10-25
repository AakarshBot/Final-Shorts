from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import cricket_source_discovery as discovery


def test_parse_rss_feed_keeps_publisher_and_removes_tracking_parameters():
    now = datetime.now(timezone.utc)
    published = (now - timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = f"""<?xml version="1.0"?>
    <rss version="2.0"><channel><item>
      <title>Former India captain questions selection policy - ESPNcricinfo</title>
      <link>https://example.com/cricket/story?utm_source=rss&amp;id=42</link>
      <description><![CDATA[An interview about the squad and the board's decision.]]></description>
      <pubDate>{published}</pubDate><source>ESPNcricinfo</source>
    </item></channel></rss>"""
    rows = discovery._parse_feed(xml, "Test feed", now=now)
    assert len(rows) == 1
    assert rows[0]["title"] == "Former India captain questions selection policy"
    assert rows[0]["source"] == "ESPNcricinfo"
    assert rows[0]["url"] == "https://example.com/cricket/story?id=42"
    assert rows[0]["published_at"].tzinfo == timezone.utc


def test_parse_atom_and_youtube_style_entries():
    now = datetime.now(timezone.utc)
    published = (now - timedelta(days=2)).isoformat()
    xml = f"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <entry>
        <id>yt:video:abc123</id>
        <yt:videoId>abc123</yt:videoId>
        <title>Former player discusses the captaincy debate</title>
        <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
        <published>{published}</published>
        <author><name>Cricbuzz</name></author>
        <summary>A long-form interview about recent cricket developments.</summary>
      </entry>
    </feed>"""
    rows = discovery._parse_feed(xml, "Cricbuzz YouTube", now=now)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert rows[0]["source"] == "Cricbuzz YouTube"
    assert "interview" in rows[0]["description"]


def test_parse_feed_rejects_invalid_urls_missing_dates_and_old_items():
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=20)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = f"""<rss><channel>
      <item><title>Missing date</title><link>https://example.com/no-date</link></item>
      <item><title>Old article</title><link>https://example.com/old</link><pubDate>{old_date}</pubDate></item>
      <item><title>No valid link</title><link>/relative</link><pubDate>{old_date}</pubDate></item>
    </channel></rss>"""
    assert discovery._parse_feed(xml, "Test feed", now=now) == []


def test_feed_collection_isolates_failed_sources_and_honours_lookback(monkeypatch):
    now = datetime.now(timezone.utc)
    fresh = {
        "title": "Current cricket analysis",
        "source": "BBC Sport Cricket",
        "published_at": now - timedelta(hours=4),
        "url": "https://example.com/fresh",
        "description": "Selection analysis",
        "feed_source": "BBC Sport Cricket",
    }
    stale = {
        **fresh,
        "title": "Old cricket analysis",
        "published_at": now - timedelta(days=9),
        "url": "https://example.com/stale",
    }
    monkeypatch.setattr(discovery, "CRICKET_FEEDS", (
        ("BBC Sport Cricket", "https://example.com/feed-a", "publisher"),
        ("Broken feed", "https://example.com/feed-b", "publisher"),
    ))

    def fake_fetch(source, url, kind, now_ts):
        if source == "Broken feed":
            raise OSError("offline")
        return [fresh, stale]

    monkeypatch.setattr(discovery, "_fetch_feed", fake_fetch)
    rows = discovery.fetch_cricket_feed_items(lookback_days=7)
    assert [row["url"] for row in rows] == ["https://example.com/fresh"]
