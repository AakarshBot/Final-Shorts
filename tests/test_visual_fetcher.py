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



def test_context_can_rescue_a_valid_article_title():
    context = (
        "Virat Kohli and Rohit Sharma were both discussed after India's latest "
        "match, with the two former captains at the centre of the report."
    )
    assert visual_fetcher._context_match(
        "Virat Kohli Rohit Sharma",
        context,
    ) > 0


def test_context_does_not_rescue_an_unrelated_article():
    assert visual_fetcher._context_match(
        "Virat Kohli Rohit Sharma",
        "The latest football transfer news covers European clubs and managers.",
    ) == 0


def test_manual_query_plan_keeps_original_and_expands_context(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": {
                            "historical": True,
                            "queries": [
                                "Virat Kohli century",
                                "Virat Kohli hundred",
                                "Virat Kohli century cricket",
                            ],
                        }
                    }
                }]
            }

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(visual_fetcher.requests, "post", lambda *args, **kwargs: Response())

    plan = visual_fetcher._manual_query_plan("Virat Kohli century")

    assert plan == {
        "historical": True,
        "queries": [
            "Virat Kohli century",
            "Virat Kohli hundred",
            "Virat Kohli century cricket",
        ],
    }


def test_manual_crawl_name_only_keeps_current_search(monkeypatch):
    calls = []

    monkeypatch.setattr(
        visual_fetcher,
        "_manual_query_plan",
        lambda query: {"historical": False, "queries": [query]},
    )

    def fake_related(queries, original_url, story_title="", entity="", historical=False):
        calls.append((queries, historical))
        return []

    monkeypatch.setattr(visual_fetcher, "_collect_related_pages", fake_related)
    monkeypatch.setattr(visual_fetcher, "_crawl_pages", lambda requests: [])

    result = visual_fetcher.manual_crawl_visuals("Virat Kohli")

    assert calls == [(["Virat Kohli"], False)]
    assert result["historical"] is False
    assert result["search_queries"] == ["Virat Kohli"]


def test_manual_crawl_context_enables_historical_search(monkeypatch):
    calls = []

    monkeypatch.setattr(
        visual_fetcher,
        "_manual_query_plan",
        lambda query: {
            "historical": True,
            "queries": [query, "Virat Kohli hundred", "Virat Kohli century cricket"],
        },
    )

    def fake_related(queries, original_url, story_title="", entity="", historical=False):
        calls.append((queries, historical))
        return []

    monkeypatch.setattr(visual_fetcher, "_collect_related_pages", fake_related)
    monkeypatch.setattr(visual_fetcher, "_crawl_pages", lambda requests: [])

    result = visual_fetcher.manual_crawl_visuals("Virat Kohli century")

    assert calls == [(
        ["Virat Kohli century", "Virat Kohli hundred", "Virat Kohli century cricket"],
        True,
    )]
    assert result["historical"] is True
    assert len(result["search_queries"]) == 3


def test_historical_search_keeps_old_relevant_pages(monkeypatch):
    old_date = "2020-10-23T00:00:00+00:00"

    monkeypatch.setattr(
        visual_fetcher,
        "_news_search",
        lambda query, historical=False: [{
            "title": "Virat Kohli century in memorable innings",
            "url": "https://example.com/old",
            "published_at": old_date,
            "body": "Virat Kohli scored a century in a memorable innings.",
            "query": query,
        }],
    )

    current_pages = visual_fetcher._collect_related_pages(
        ["Virat Kohli century"],
        "",
        "",
        "",
        historical=False,
    )
    historical_pages = visual_fetcher._collect_related_pages(
        ["Virat Kohli century"],
        "",
        "",
        "",
        historical=True,
    )

    assert current_pages == []
    assert [page["url"] for page in historical_pages] == ["https://example.com/old"]


def test_manual_crawl_returns_scraped_assets(monkeypatch):
    monkeypatch.setattr(
        visual_fetcher,
        "_manual_query_plan",
        lambda query: {"historical": True, "queries": [query, "MS Dhoni motorcycle"]},
    )
    monkeypatch.setattr(
        visual_fetcher,
        "_collect_related_pages",
        lambda *args, **kwargs: [{
            "url": "https://example.com/article",
            "title": "MS Dhoni motorcycle",
            "source": "Example",
            "published_at": "",
            "query": "MS Dhoni motorcycle",
        }],
    )
    monkeypatch.setattr(
        visual_fetcher,
        "_crawl_pages",
        lambda requests: [{
            "assets": [{
                "bytes": b"image",
                "hash": "abc",
                "source_image_url": "https://example.com/image.jpg",
                "source_page_url": "https://example.com/article",
                "publisher": "Example",
                "article_title": "MS Dhoni motorcycle",
            }],
            "url": "https://example.com/article",
            "title": "MS Dhoni motorcycle",
            "candidate_count": 1,
        }],
    )

    result = visual_fetcher.manual_crawl_visuals("MS Dhoni bike")

    assert result["historical"] is True
    assert result["assets"][0]["query"] == "MS Dhoni motorcycle"
    assert result["assets"][0]["publisher"] == "Example"



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
