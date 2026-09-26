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
    assert len(queries) == 2
    assert all("Shubman Gill" in query for query in queries)


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
