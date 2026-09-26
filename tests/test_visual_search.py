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
