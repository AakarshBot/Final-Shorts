from PIL import Image
import io

import visual_search


def _jpeg_bytes(value):
    image = Image.new("RGB", (10, 10), value)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_search_images_dedupes_same_content(monkeypatch):
    data = _jpeg_bytes("red")

    def first(_query):
        return [{
            "bytes": data,
            "hash": "same",
            "source": "First",
            "source_page_url": "https://example.com/1",
            "source_image_url": "https://img.example.com/1.jpg",
            "title": "one",
        }]

    def second(_query):
        return [{
            "bytes": data,
            "hash": "same",
            "source": "Second",
            "source_page_url": "https://example.com/2",
            "source_image_url": "https://img.example.com/2.jpg",
            "title": "two",
        }]

    monkeypatch.setattr(
        visual_search,
        "PROVIDERS",
        (("First", first, True), ("Second", second, True)),
    )

    result = visual_search.search_images("Ben Stokes")

    assert len(result["assets"]) == 1
    assert result["assets"][0]["source"] == "First"


def test_search_images_requires_manual_query():
    result = visual_search.search_images("")

    assert result["assets"] == []
    assert result["providers"] == {}


def test_valid_image_accepts_decodable_bytes():
    assert visual_search._valid_image(_jpeg_bytes("blue")) is True


def test_search_images_configures_serpapi_when_key_present(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test_key")
    called_providers = []

    def mock_provider(name):
        def _fn(q):
            called_providers.append(name)
            return []
        return _fn

    patched_providers = tuple(
        (name, mock_provider(name), always_on)
        for name, _, always_on in visual_search.PROVIDERS
    )
    monkeypatch.setattr(visual_search, "PROVIDERS", patched_providers)

    result = visual_search.search_images("cricket")
    assert "Bing" in called_providers
    assert "Google Images" in called_providers
    assert "Wikidata" in called_providers


def test_search_images_omits_serpapi_when_key_absent(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    called_providers = []

    def mock_provider(name):
        def _fn(q):
            called_providers.append(name)
            return []
        return _fn

    patched_providers = tuple(
        (name, mock_provider(name), always_on)
        for name, _, always_on in visual_search.PROVIDERS
    )
    monkeypatch.setattr(visual_search, "PROVIDERS", patched_providers)

    result = visual_search.search_images("cricket")
    assert "Bing" not in called_providers
    assert "Google Images" not in called_providers
    assert "Wikidata" in called_providers


def test_serpapi_bing_extracts_items(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test_key")

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "images_results": [
                    {
                        "original": "https://example.com/bing_orig.jpg",
                        "thumbnail": "https://example.com/bing_thumb.jpg",
                        "link": "https://example.com/page",
                        "title": "Bing Image Title",
                    }
                ]
            }

    downloaded = []
    monkeypatch.setattr(visual_search.requests, "get", lambda *args, **kwargs: MockResponse())
    monkeypatch.setattr(visual_search, "_download_many", lambda items: items)

    items = visual_search._serpapi_bing("Rohit Sharma")
    assert len(items) == 1
    url, meta = items[0]
    assert url == "https://example.com/bing_orig.jpg"
    assert meta["source"] == "Bing"
    assert meta["fallback_url"] == "https://example.com/bing_thumb.jpg"


def test_serpapi_google_extracts_items(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test_key")

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "images_results": [
                    {
                        "original": "https://example.com/google_orig.jpg",
                        "thumbnail": "https://example.com/google_thumb.jpg",
                        "link": "https://example.com/gpage",
                        "title": "Google Image Title",
                    }
                ]
            }

    monkeypatch.setattr(visual_search.requests, "get", lambda *args, **kwargs: MockResponse())
    monkeypatch.setattr(visual_search, "_download_many", lambda items: items)

    items = visual_search._serpapi_google("Virat Kohli")
    assert len(items) == 1
    url, meta = items[0]
    assert url == "https://example.com/google_orig.jpg"
    assert meta["source"] == "Google Images"
    assert meta["fallback_url"] == "https://example.com/google_thumb.jpg"


def test_wikidata_extracts_claims_and_builds_items(monkeypatch):
    class MockSearchResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "search": [
                    {"id": "Q123", "label": "Test Player"}
                ]
            }

    class MockClaimsResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "entities": {
                    "Q123": {
                        "claims": {
                            "P18": [
                                {
                                    "mainsnak": {
                                        "datavalue": {"value": "Test_Player.jpg"}
                                    }
                                }
                            ]
                        }
                    }
                }
            }

    class MockCommonsResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Test_Player.jpg",
                            "imageinfo": [
                                {
                                    "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                                    "url": "https://upload.wikimedia.org/orig.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/desc",
                                }
                            ]
                        }
                    }
                }
            }

    def mock_get(url, *args, **kwargs):
        if "wbsearchentities" in str(kwargs.get("params", {}).get("action", "")):
            return MockSearchResp()
        if "wbgetentities" in str(kwargs.get("params", {}).get("action", "")):
            return MockClaimsResp()
        return MockCommonsResp()

    monkeypatch.setattr(visual_search.requests, "get", mock_get)
    monkeypatch.setattr(visual_search, "_download_many", lambda items: items)

    items = visual_search._wikidata("Test Player")
    assert len(items) == 1
    url, meta = items[0]
    assert "upload.wikimedia.org" in url
    assert meta["source"] == "Wikidata"
