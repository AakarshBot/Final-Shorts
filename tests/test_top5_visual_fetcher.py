import asyncio
import sys
from types import SimpleNamespace

import top5_visual_fetcher


def _stories():
    return [
        {
            "title": f"Story {index} headline with enough context",
            "url": f"https://source-{index}.example/story",
            "source": f"Source {index}",
            "published_at": "2026-09-27T10:00:00+00:00",
        }
        for index in range(1, 6)
    ]


def _asset(name, url_base="https://images.example"):
    return {
        "bytes": b"image",
        "hash": name,
        "source_image_url": f"{url_base}/{name}.jpg",
        "source_page_url": "https://source.example/story",
        "publisher": "Example",
        "article_title": "Story headline",
    }


def test_requires_exactly_five_stories():
    try:
        top5_visual_fetcher.crawl_top5_visuals(_stories()[:4])
    except ValueError as exc:
        assert "exactly five" in str(exc)
    else:
        raise AssertionError("Expected exactly-five validation.")


def test_ready_original_url_does_not_trigger_related_search(monkeypatch):
    calls = []

    async def fake_scrape(context, request):
        calls.append(request["url"])
        return {"assets": [_asset(str(i)) for i in range(4)]}

    def fail_related(*args):
        raise AssertionError("Related URL search should not run for a ready source URL.")

    monkeypatch.setattr(top5_visual_fetcher, "_scrape_url", fake_scrape)
    monkeypatch.setattr(top5_visual_fetcher, "_find_related_url", fail_related)

    result = asyncio.run(top5_visual_fetcher._scrape_story(None, _stories()[0], 1))

    assert calls == [_stories()[0]["url"]]
    assert result["image_count"] == 4
    assert result["related_urls"] == []
    assert result["failure_state"] == "ready"


def test_related_url_fallback_repeats_until_pool_reaches_four(monkeypatch):
    story = _stories()[0]
    calls = []
    related_calls = []
    pools = {
        story["url"]: [_asset("original-1"), _asset("original-2")],
        "https://related.example/one": [_asset("related-1")],
        "https://related.example/two": [_asset("related-2")],
    }

    async def fake_scrape(context, request):
        calls.append(request["url"])
        return {"assets": pools.get(request["url"], [])}

    related_urls = iter([
        "https://related.example/one",
        "https://related.example/two",
        "",
    ])

    def fake_related(title, original_url, seen_urls):
        related_calls.append(set(seen_urls))
        return next(related_urls)

    monkeypatch.setattr(top5_visual_fetcher, "_scrape_url", fake_scrape)
    monkeypatch.setattr(top5_visual_fetcher, "_find_related_url", fake_related)

    result = asyncio.run(top5_visual_fetcher._scrape_story(None, story, 1))

    assert calls == [
        story["url"],
        "https://related.example/one",
        "https://related.example/two",
    ]
    assert result["related_urls"] == [
        "https://related.example/one",
        "https://related.example/two",
    ]
    assert result["image_count"] == 4
    assert result["failure_state"] == "ready"
    assert related_calls[0] == {story["url"]}


def test_merge_assets_dedupes_and_keeps_small_pool():
    assets = [
        _asset("1"),
        _asset("1", "https://other.example"),
        _asset("2"),
        _asset("3"),
        _asset("4"),
        _asset("5"),
        _asset("6"),
        _asset("7"),
    ]

    result = top5_visual_fetcher._merge_assets(assets)

    assert [item["hash"] for item in result] == [
        "1", "2", "3", "4", "5", "6"
    ]


def test_static_fallback_only_rechecks_same_url(monkeypatch):
    story = _stories()[0]
    browser_calls = []
    static_calls = []

    async def fake_browser(context, request):
        browser_calls.append(request["url"])
        return {
            "assets": [_asset("browser-1"), _asset("browser-2")],
            "title": story["title"],
            "url": request["url"],
        }

    def fake_static(request):
        static_calls.append(request["url"])
        return {
            "assets": [_asset("static-1"), _asset("static-2")],
            "title": story["title"],
            "url": request["url"],
            "static_candidates": 4,
            "error": "",
        }

    monkeypatch.setattr(top5_visual_fetcher, "_browser_page", fake_browser)
    monkeypatch.setattr(top5_visual_fetcher, "_static_page", fake_static)

    result = asyncio.run(
        top5_visual_fetcher._scrape_url(
            None,
            {"url": story["url"], "title": story["title"]},
        )
    )

    assert browser_calls == [story["url"]]
    assert static_calls == [story["url"]]
    assert len(result["assets"]) == 4
    assert result["method"] == "browser+static"


def test_related_search_excludes_original_and_same_domain(monkeypatch):
    original = "https://publisher.example/original"
    valid = "https://other.example/related"

    class FakeDDGS:
        def __init__(self, timeout):
            self.timeout = timeout

        def news(self, **kwargs):
            return [
                {
                    "title": "Story headline with enough context",
                    "url": original,
                },
                {
                    "title": "Story headline with enough context",
                    "url": "https://publisher.example/other",
                },
                {
                    "title": "Story headline with enough context",
                    "url": valid,
                },
            ]

    monkeypatch.setitem(
        sys.modules,
        "ddgs",
        SimpleNamespace(DDGS=FakeDDGS),
    )

    result = top5_visual_fetcher._find_related_url(
        "Story headline with enough context",
        original,
        {original.casefold().rstrip("/")},
    )

    assert result == valid
