from datetime import datetime, timezone

import visual_fetcher


def _story():
    return {
        "title": "Shubman Gill survives injury scare in Thiruvananthapuram nets",
        "description": "Gill was struck during practice before the West Indies ODI.",
        "source": "Test",
        "url": "https://example.com/original",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def test_build_queries_is_small_and_entity_focused():
    queries = visual_fetcher.build_queries(
        _story()["title"],
        _story()["description"],
        "Shubman Gill",
    )
    assert len(queries) == 3
    assert queries[0] == _story()["title"]
    assert all("Shubman Gill" in query for query in queries[1:])


def test_original_story_url_is_first_and_manual_run_uses_only_manual_query(monkeypatch):
    calls = []

    def fake_crawl_pages(requests):
        calls.append(requests)
        return [{"assets": []} for _ in requests]

    monkeypatch.setattr(visual_fetcher, "_crawl_pages", fake_crawl_pages)
    result = visual_fetcher.crawl_visuals(_story(), manual_query="Gill cricket action")

    assert calls[0][0]["url"] == _story()["url"]
    assert calls[0][0]["query"] == ""
    assert result["queries_used"] == ["Gill cricket action"]
    assert result["manual_query"] == "Gill cricket action"


def test_manual_query_is_not_locked_to_story_entity(monkeypatch):
    calls = []

    def fake_related(queries, original_url, story_title="", entity=""):
        calls.append((queries, original_url, story_title, entity))
        return []

    def fake_crawl_pages(requests):
        return [{"assets": []} for _ in requests]

    monkeypatch.setattr(visual_fetcher, "_collect_related_pages", fake_related)
    monkeypatch.setattr(visual_fetcher, "_crawl_pages", fake_crawl_pages)

    story = {
        **_story(),
        "primary_entity": "Shubman Gill",
    }
    result = visual_fetcher.crawl_visuals(
        story,
        manual_query="Virat Kohli Rohit Sharma",
    )

    assert result["manual_query"] == "Virat Kohli Rohit Sharma"
    assert calls == [
        (
            ["Virat Kohli Rohit Sharma"],
            story["url"],
            story["title"],
            "",
        )
    ]


def test_same_query_is_case_insensitive():
    assert visual_fetcher.same_query("Shubman Gill Cricket", ["shubman gill cricket"])
    assert not visual_fetcher.same_query("Gill nets", ["Gill batting"])


def test_dedupe_keeps_best_unique_assets():
    assets = [
        {"hash": "a", "source_image_url": "https://x/a", "score": 90, "action_score": 1},
        {"hash": "a", "source_image_url": "https://x/b", "score": 80, "action_score": 2},
        {"hash": "b", "source_image_url": "https://x/c", "score": 70, "action_score": 0},
    ]
    result = visual_fetcher._dedupe(assets)
    assert [item["hash"] for item in result] == ["a", "b"]


def test_dedupe_prefers_original_story_assets_on_equal_score():
    assets = [
        {"hash": "related", "source_image_url": "https://x/related", "score": 50, "action_score": 0},
        {"hash": "original", "source_image_url": "https://x/original", "score": 50, "action_score": 0, "original_story": True},
    ]
    result = visual_fetcher._dedupe(assets)
    assert result[0]["hash"] == "original"

def test_crawl_exposes_page_diagnostics(monkeypatch):
    def fake_crawl_pages(requests):
        return [{
            "assets": [],
            "url": requests[0]["url"],
            "title": "Test page",
            "candidate_count": 7,
            "dom_image_count": 12,
            "network_image_count": 9,
            "direct_download_failures": 4,
            "network_fallback_hits": 3,
            "error": "",
        }]

    monkeypatch.setattr(visual_fetcher, "_crawl_pages", fake_crawl_pages)
    result = visual_fetcher.crawl_visuals(_story())

    assert result["failure_state"] == "no_images"
    assert result["diagnostics"][0]["candidates"] == 7
    assert result["diagnostics"][0]["network_fallback_hits"] == 3


def test_related_search_uses_ddgs_and_google_and_filters_unrelated(monkeypatch):
    calls = []

    def fake_ddgs(query, *args, **kwargs):
        calls.append(("ddgs", query))
        return [{
            "title": "Shubman Gill survives injury scare before West Indies ODI",
            "url": "https://example.com/related",
        }]

    def fake_google(query):
        calls.append(("google", query))
        return [{
            "title": "Unrelated football story",
            "url": "https://example.com/unrelated",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }]

    monkeypatch.setattr(visual_fetcher, "_ddgs_news", fake_ddgs)
    monkeypatch.setattr(visual_fetcher, "_google_news_rss", fake_google)

    pages = visual_fetcher._collect_related_pages(
        ["Shubman Gill survives injury scare"],
        "https://example.com/original",
        _story()["title"],
        "Shubman Gill",
    )
    assert [page["url"] for page in pages] == ["https://example.com/related"]
    assert {lane for lane, _ in calls} == {"ddgs", "google"}


def test_profile_search_uses_web_text_search(monkeypatch):
    class FakeDDGS:
        def __init__(self, timeout):
            self.timeout = timeout

        def text(self, **kwargs):
            return [{
                "title": "Joe Root profile",
                "href": "https://example.com/joe-root-profile",
                "source": "Example",
            }]

    monkeypatch.setitem(
        __import__("sys").modules,
        "ddgs",
        type("FakeModule", (), {"DDGS": FakeDDGS}),
    )
    pages = visual_fetcher._collect_profile_pages("Joe Root")
    assert pages
    assert pages[0]["url"].endswith("joe-root-profile")


def test_static_parser_handles_responsive_image_markup():
    parser = visual_fetcher._StaticImageParser()
    parser.feed(
        '<meta property="og:image" content="https://example.com/hero.jpg">'
        '<picture><source data-srcset="https://example.com/a.jpg 1200w, https://example.com/b.jpg 800w">'
        '<img data-lazy-src="https://example.com/c.jpg" alt="Joe Root batting"></picture>'
    )
    parser.close()
    urls = [item[0] for item in parser.candidates]
    assert "https://example.com/a.jpg" in urls
    assert "https://example.com/b.jpg" in urls
    assert "https://example.com/c.jpg" in urls
