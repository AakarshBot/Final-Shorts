from datetime import timezone

import pytest

import manual_topic


def test_manual_headline_builds_canonical_topic_without_a_url():
    topic = manual_topic.create_manual_topic(
        headline="India announce a late squad change",
        description="Short editor-provided context.",
    )

    assert topic.title == "India announce a late squad change"
    assert topic.url == ""
    assert topic.source == "Manual headline"
    assert topic.description == "Short editor-provided context."
    assert topic.published_at.tzinfo is not None
    assert topic.published_at.tzinfo == timezone.utc
    assert topic.group_key.startswith("manual:")


def test_url_only_intake_uses_publisher_metadata(monkeypatch):
    class Response:
        status_code = 200
        url = "https://sports.example/news/india-squad-change"
        text = (
            '<html><head>'
            '<meta property="og:title" content="India announce major squad change">'
            '<meta property="og:description" content="The selection committee made a late call.">'
            '</head><body></body></html>'
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr(manual_topic.requests, "get", lambda *args, **kwargs: Response())
    topic = manual_topic.create_manual_topic(url="https://sports.example/news/india-squad-change")

    assert topic.title == "India announce major squad change"
    assert topic.description == "The selection committee made a late call."
    assert topic.url == "https://sports.example/news/india-squad-change"
    assert topic.source == "sports.example"


def test_manual_headline_takes_precedence_over_url_metadata(monkeypatch):
    def fail_request(*args, **kwargs):
        raise AssertionError("A supplied headline should not require a metadata request.")

    monkeypatch.setattr(manual_topic.requests, "get", fail_request)
    topic = manual_topic.create_manual_topic(
        headline="Editor-supplied headline",
        url="https://publisher.example/story/slug",
    )

    assert topic.title == "Editor-supplied headline"
    assert topic.url == "https://publisher.example/story/slug"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://127.0.0.1/private",
        "http://localhost/admin",
        "https://user:password@news.example/story",
    ],
)
def test_manual_url_rejects_non_public_or_non_http_destinations(url):
    with pytest.raises(ValueError):
        manual_topic.create_manual_topic(headline="A sufficiently long headline", url=url)


def test_manual_intake_rejects_empty_input():
    with pytest.raises(ValueError, match="headline"):
        manual_topic.create_manual_topic()
