import pytest

from script_writer import (
    MAX_WORDS,
    SCENE_1_MAX_WORDS,
    SYSTEM_PROMPT,
    _article_body_from_html,
    _extract_article,
    apply_script_edits,
    write_script,
)


@pytest.fixture(autouse=True)
def disable_live_cricket_research(monkeypatch):
    monkeypatch.setattr(
        "script_writer._cricket_research_candidates",
        lambda *args, **kwargs: [],
    )


def valid_result(scene1="Gill faces a fresh injury scare before ODI."):
    return {
        "headline": "Gill Injury Scare",
        "titles": [
            "Gill injury scare before ODI",
            "India captain hit in nets",
            "Gill fitness update",
        ],
        "seo_description": "Shubman Gill faces an injury scare before India’s next ODI.",
        "hashtags": ["#Cricket", "#ShubmanGill", "#IndiaCricket"],
        "comment": "What do you make of Gill's injury scare before the ODI?",
        "script": [
            {
                "voiceover": scene1,
                "narrative_role": "hook",
                "primary_entity": "Shubman Gill",
                "visual_intent": "cricket action",
                "specific_search_prompt": "Shubman Gill batting India",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "He was struck during net practice and briefly appeared in pain.",
                "narrative_role": "development",
                "primary_entity": "Shubman Gill",
                "visual_intent": "training incident",
                "specific_search_prompt": "Shubman Gill cricket nets",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "India are preparing for the West Indies ODI series.",
                "narrative_role": "context",
                "primary_entity": "India cricket team",
                "visual_intent": "team context",
                "specific_search_prompt": "India cricket team training",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "His availability for the opening match is now the key question.",
                "narrative_role": "consequence",
                "primary_entity": "Shubman Gill",
                "visual_intent": "player fitness",
                "specific_search_prompt": "Shubman Gill fitness cricket",
                "sport_or_topic_category": "Cricket",
            },
        ],
    }


def test_writer_sends_title_and_description_as_story_evidence(monkeypatch):
    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Gill injury scare",
            "description": "Shubman Gill was struck during training before the ODI.",
        }
    )

    assert "Gill injury scare" in captured[0]
    assert "Shubman Gill was struck during training before the ODI." in captured[0]


def test_writer_retries_when_shorts_metadata_is_generic(monkeypatch):
    calls = []

    def fake_request(model, prompt, story):
        calls.append(model)
        result = valid_result()
        if model == "openai/gpt-oss-120b":
            result["titles"] = [
                "Latest Sports Update",
                "Big Update On Gill",
                "What You Need To Know",
            ]
        return result

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {
            "title": "Shubman Gill injury scare in nets",
            "description": "Shubman Gill was struck during practice ahead of the ODI.",
        }
    )

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_rejects_story_unrelated_title(monkeypatch):
    def fake_request(model, prompt, story):
        result = valid_result()
        result["titles"][0] = "Premier League Transfer Sparks Surprise"
        result["titles"][1] = "Champions League Shock Rocks Europe"
        return result

    monkeypatch.setattr("script_writer._request", fake_request)

    try:
        write_script(
            {
                "title": "Shubman Gill injury scare",
                "description": "Shubman Gill was hit in training before the ODI.",
            }
        )
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
    else:
        raise AssertionError("Unrelated title should not pass validation.")


def test_writer_uses_one_primary_groq_call(monkeypatch):
    calls = []

    def fake_request(model, prompt, story):
        calls.append(model)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {
            "title": "Shubman Gill injury scare in nets",
            "description": "Shubman Gill was struck during practice ahead of India vs West Indies.",
            "source": "Test",
        }
    )

    assert calls == ["openai/gpt-oss-120b"]
    assert result["delivery_profile"] == "HYPE COMMENTATOR"
    assert result["source_title"] == "Shubman Gill injury scare in nets"
    assert len(result["titles"]) == 3
    assert 3 <= len(result["headline"].split()) <= 4
    assert result["hashtags"]
    assert result["comment"]
    assert result["word_count"] == 39
    assert len(result["script"]) == 4


def test_writer_uses_20b_only_when_primary_fails(monkeypatch):
    calls = []

    def fake_request(model, prompt, story):
        calls.append(model)
        if model == "openai/gpt-oss-120b":
            raise RuntimeError("primary unavailable")
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {
            "title": "India cricket injury update",
            "description": "A player faces an injury scare.",
        }
    )

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_uses_20b_when_primary_output_fails_validation(monkeypatch):
    calls = []

    def fake_request(model, prompt, story):
        calls.append(model)
        if model == "openai/gpt-oss-120b":
            return valid_result("Wait until the end because this changes everything.")
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {"title": "Gill injury scare", "description": "Shubman Gill was hit in training before the ODI."}
    )

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_fallback_receives_validation_failure(monkeypatch):
    prompts = []

    def fake_request(model, prompt, story):
        prompts.append(prompt)
        if model == "openai/gpt-oss-120b":
            return valid_result("Shubman Gill faces a fresh injury scare before India starts its first ODI campaign this week.")
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {"title": "Gill injury scare", "description": "Shubman Gill was hit in training before the ODI."}
    )

    assert result["provider_used"] == "openai/gpt-oss-20b"
    assert "Scene 1 exceeds 14 words." in prompts[1]
    assert "fixing this exact failure" in prompts[1]


def test_writer_rejects_missing_comment(monkeypatch):
    def fake_request(model, prompt, story):
        result = valid_result()
        result.pop("comment")
        return result

    monkeypatch.setattr("script_writer._request", fake_request)

    try:
        write_script(
            {
                "title": "Gill injury scare",
                "description": "Shubman Gill was hit in training before the ODI.",
            }
        )
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
    else:
        raise AssertionError("Missing upload comment should not pass.")


def test_writer_rejects_headline_with_wrong_word_count(monkeypatch):
    def fake_request(model, prompt, story):
        result = valid_result()
        result["headline"] = "Gill Injury Scare Before ODI"
        return result

    monkeypatch.setattr("script_writer._request", fake_request)

    try:
        write_script(
            {
                "title": "Gill injury scare",
                "description": "Shubman Gill was hit in training before the ODI.",
            }
        )
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
    else:
        raise AssertionError("Invalid headline should not pass.")


def test_approved_edits_can_bypass_validation_for_live_manual_qc():
    original = valid_result()
    approved = apply_script_edits(
        original,
        [
            "This is deliberately a longer manual edit that exceeds the writer's normal limit.",
            original["script"][1]["voiceover"],
            original["script"][2]["voiceover"],
            original["script"][3]["voiceover"],
        ],
        headline="",
        validate=False,
    )

    assert approved["headline"] == ""
    assert approved["approved_for_audio"] is True


def test_approved_edits_preserve_titles_and_metadata_and_mark_audio_handoff():
    original = valid_result()
    edited = apply_script_edits(
        original,
        [
            "Gill faces an injury scare before India’s ODI.",
            original["script"][1]["voiceover"],
            original["script"][2]["voiceover"],
            original["script"][3]["voiceover"],
        ],
        headline="Gill Update Unfolds",
    )

    assert edited["titles"] == original["titles"]
    assert edited["hashtags"] == original["hashtags"]
    assert edited["headline"] == "Gill Update Unfolds"
    assert edited["script"][0]["voiceover"].startswith("Gill faces")
    assert edited["human_script_edited"] is True
    assert edited["approved_for_audio"] is True


def test_writer_rejects_hook_over_three_seconds(monkeypatch):
    def fake_request(model, prompt, story):
        return valid_result(
            "Gill faces a fresh injury scare before India starts the ODI this week."
        )

    monkeypatch.setattr("script_writer._request", fake_request)

    try:
        write_script(
            {
                "title": "Gill injury scare",
                "description": "Shubman Gill was hit in training before the ODI.",
            }
        )
    except RuntimeError as exc:
        assert "3-second hook limit" in str(exc)
    else:
        raise AssertionError("A hook above three seconds should not pass validation.")


def test_writer_rejects_retention_bait(monkeypatch):
    def fake_request(model, prompt, story):
        return valid_result(
            "Wait until the end because this injury update changes everything."
        )

    monkeypatch.setattr("script_writer._request", fake_request)

    try:
        write_script(
            {
                "title": "India cricket injury update",
                "description": "A player faces an injury scare.",
            }
        )
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
    else:
        raise AssertionError("Retention-bait draft should not pass.")


def test_writer_rejects_other_retention_phrases(monkeypatch):
    for phrase in ("Watch till the end for the full story.", "Don't skip this.", "Keep watching."):
        def fake_request(model, prompt, story, phrase=phrase):
            return valid_result(phrase)

        monkeypatch.setattr("script_writer._request", fake_request)
        try:
            write_script(
                {
                    "title": "India cricket injury update",
                    "description": "A player faces an injury scare.",
                }
            )
        except RuntimeError as exc:
            assert "failed" in str(exc).lower()
        else:
            raise AssertionError(f"Retention phrase passed: {phrase}")

def test_writer_research_uses_full_article_before_generation(monkeypatch):
    class FakeResponse:
        url = "https://example.com/story"

        def raise_for_status(self):
            return None

        text = "<html>full article page</html>"

    captured = []

    monkeypatch.setattr("script_writer.requests.get", lambda *args, **kwargs: FakeResponse())
    article = (
        "Shubman Gill was struck during practice and returned after treatment. "
        "India are assessing his availability for the ODI. "
        "The team continued its session while medical staff monitored him closely. "
        "The coaching staff later reviewed the incident and the next training plan. "
        "His availability remains dependent on further assessment before the match. "
    ) * 3
    monkeypatch.setattr(
        "script_writer.trafilatura.extract",
        lambda *args, **kwargs: article,
    )

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training.",
            "url": "https://example.com/story",
        }
    )

    assert "[PRIMARY ARTICLE — https://example.com/story]" in captured[0]
    assert "returned after treatment" in captured[0]


def test_writer_research_uses_ddgs_extract_when_page_extractors_fail(monkeypatch):
    class FakeResponse:
        url = "https://example.com/story"
        text = "<html><body>not enough article text</body></html>"

        def raise_for_status(self):
            return None

    article = (
        "Shubman Gill was hit in training before the ODI. "
        "India are assessing his availability after the incident. "
        "The coaching staff reviewed his condition before the next session. "
    ) * 8

    class FakeDDGS:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, url, fmt):
            assert url == "https://example.com/story"
            assert fmt == "text_plain"
            return {"url": url, "content": article}

    monkeypatch.setattr("script_writer.requests.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("script_writer.trafilatura.extract", lambda *args, **kwargs: "")
    monkeypatch.setattr("script_writer.DDGS", FakeDDGS)

    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training.",
            "url": "https://example.com/story",
        }
    )

    assert "[PRIMARY ARTICLE — https://example.com/story]" in captured[0]
    assert "India are assessing his availability" in captured[0]


def test_writer_research_reads_jsonld_article_body_when_trafilatura_is_thin(monkeypatch):
    class FakeResponse:
        url = "https://example.com/story"

        def raise_for_status(self):
            return None

        text = """<html><head>
        <script type="application/ld+json">
        {"@type":"NewsArticle","articleBody":"Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. Shubman Gill was struck during practice and returned after treatment. India are assessing his availability for the ODI. The coaching staff reviewed the incident before the next training session. "}
        </script>
        </head><body><p>Thin page.</p></body></html>"""

    monkeypatch.setattr("script_writer.requests.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("script_writer.trafilatura.extract", lambda *args, **kwargs: "")

    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training.",
            "url": "https://example.com/story",
        }
    )

    assert "[PRIMARY ARTICLE — https://example.com/story]" in captured[0]
    assert "India are assessing his availability" in captured[0]


def test_writer_research_uses_independent_report_for_cricket_context(monkeypatch):
    calls = []

    def fake_extract(url):
        calls.append(url)
        if url == "https://example.com/story":
            return "", url
        return (
            (
                "Independent report: Shubman Gill was hit in training before the ODI. "
                "India are assessing his availability after the incident. "
            ) * 6,
            url,
        )

    monkeypatch.setattr("script_writer._extract_article", fake_extract)
    monkeypatch.setattr(
        "script_writer._cricket_research_candidates",
        lambda title, url: [
            {
                "title": "Shubman Gill injury update before ODI",
                "url": "https://other.com/gill-story",
                "domain": "other.com",
                "score": 8.0,
            }
        ],
    )

    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training.",
            "url": "https://example.com/story",
        }
    )

    assert calls == ["https://example.com/story", "https://other.com/gill-story"]
    assert "[INDEPENDENT REPORT 1 — Shubman Gill injury update before ODI — https://other.com/gill-story]" in captured[0]
    assert "Independent report: Shubman Gill was hit in training before the ODI." in captured[0]



def test_writer_can_use_topic_evidence_when_article_research_fails(monkeypatch):
    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    monkeypatch.setattr(
        "script_writer._extract_article",
        lambda url: ("", "https://example.com/story"),
    )
    monkeypatch.setattr(
        "script_writer._fallback_article",
        lambda title, url: ("", ""),
    )

    result = write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training before the ODI.",
            "url": "https://example.com/story",
        }
    )

    assert result["provider_used"] == "openai/gpt-oss-120b"
    assert "[SELECTED STORY]" in captured[0]
    assert "Shubman Gill injury scare" in captured[0]
    assert "Gill was hit during training before the ODI." in captured[0]


def test_writer_research_keeps_primary_and_caps_independent_reports(monkeypatch):
    primary = (
        "Primary report: Shubman Gill was struck during practice and returned after treatment. "
        "India are assessing his availability for the ODI. "
    ) * 6
    alternate = (
        "Independent report: Gill continued training after the incident and the team reviewed his status. "
        "His availability remains under assessment. "
    ) * 6

    def fake_extract(url):
        if url == "https://example.com/story":
            return primary, url
        return alternate, url

    monkeypatch.setattr("script_writer._extract_article", fake_extract)
    monkeypatch.setattr(
        "script_writer._cricket_research_candidates",
        lambda title, url: [
            {
                "title": "Gill injury update before ODI",
                "url": "https://other.com/gill-story",
                "domain": "other.com",
                "score": 7.5,
            },
            {
                "title": "Gill training status ahead of India ODI",
                "url": "https://third.com/gill-status",
                "domain": "third.com",
                "score": 7.0,
            },
            {
                "title": "Gill training story from another outlet",
                "url": "https://fourth.com/gill-status",
                "domain": "fourth.com",
                "score": 6.5,
            },
        ],
    )

    extracted_urls = []

    def capture_extract(url):
        extracted_urls.append(url)
        return fake_extract(url)

    monkeypatch.setattr("script_writer._extract_article", capture_extract)

    captured = []

    def fake_request(model, prompt, story):
        captured.append(story)
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    write_script(
        {
            "title": "Shubman Gill injury scare",
            "description": "Gill was hit during training.",
            "url": "https://example.com/story",
        }
    )

    packet = captured[0]
    assert "[PRIMARY ARTICLE — https://example.com/story]" in packet
    assert "[INDEPENDENT REPORT 1 — Gill injury update before ODI — https://other.com/gill-story]" in packet
    assert "[INDEPENDENT REPORT 2 — Gill training status ahead of India ODI — https://third.com/gill-status]" in packet
    assert "https://fourth.com/gill-status" not in packet
    assert extracted_urls == [
        "https://example.com/story",
        "https://other.com/gill-story",
        "https://third.com/gill-status",
    ]


def test_writer_keeps_existing_retention_limits():
    assert SCENE_1_MAX_WORDS == 14
    assert MAX_WORDS == 75
    assert "Use 4 narration scenes by default" in __import__("script_writer").SYSTEM_PROMPT


def test_structured_html_fallback_keeps_article_table_facts():
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type":"NewsArticle","articleBody":"Auqib Nabi made his India ODI debut at 29."}
      </script>
    </head><body>
      <p>Jammu and Kashmir pacer Auqib Nabi earned his India cap.</p>
      <table>
        <tr><th>Ranji Trophy 2025-26</th><th>60 wickets</th></tr>
        <tr><td>First-class career</td><td>170 wickets</td></tr>
        <tr><td>Best bowling</td><td>7/24</td></tr>
      </table>
    </body></html>
    """
    extracted = _article_body_from_html(html)

    assert "Auqib Nabi made his India ODI debut at 29." in extracted
    assert "Ranji Trophy 2025-26 | 60 wickets" in extracted
    assert "First-class career | 170 wickets" in extracted
    assert "Best bowling | 7/24" in extracted


def test_article_extraction_includes_tables_in_trafilatura():
    class FakeResponse:
        url = "https://example.com/story"
        text = "<html><body>full article</body></html>"

        def raise_for_status(self):
            return None

    article = (
        "Auqib Nabi made his India ODI debut after a strong Ranji Trophy season. "
        "He took 60 wickets and led the tournament wicket charts. "
    ) * 8
    captured = {}

    def fake_extract(*args, **kwargs):
        captured.update(kwargs)
        return article

    monkeypatch_response = lambda *args, **kwargs: FakeResponse()
    import script_writer
    original_get = script_writer.requests.get
    original_extract = script_writer.trafilatura.extract
    try:
        script_writer.requests.get = monkeypatch_response
        script_writer.trafilatura.extract = fake_extract
        extracted, resolved = _extract_article("https://example.com/story")
    finally:
        script_writer.requests.get = original_get
        script_writer.trafilatura.extract = original_extract

    assert extracted
    assert resolved == "https://example.com/story"
    assert captured["include_tables"] is True


def test_writer_prompt_prioritises_editorial_promise_and_full_story_coverage():
    assert "actual editorial promise" in SYSTEM_PROMPT
    assert "4–7 most useful supported facts" in SYSTEM_PROMPT
    assert "profile/breakout" in SYSTEM_PROMPT
    assert "complete Short, not a compressed article dump" in SYSTEM_PROMPT
    assert "62–72 spoken words" in SYSTEM_PROMPT
    assert "under 30 seconds" in SYSTEM_PROMPT
