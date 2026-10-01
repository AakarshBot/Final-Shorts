import json

import pytest

import script_writer
from script_writer import (
    CRICKET_SCHEMA,
    SLIDE_ONE_SCHEMA,
    LANGUAGE_INSTRUCTIONS,
    SYSTEM_PROMPT,
    _article_body_from_html,
    _request,
    apply_script_edits,
    validate_cricket_script,
    validate_script,
    write_script,
)


def valid_result(scene1="Gill faces a fresh injury scare."):
    return {
        "headline": "Gill Injury Update",
        "titles": [
            "Gill injury update before ODI",
            "What Gill's latest scan means",
            "India captain fitness status explained",
        ],
        "seo_description": "Shubman Gill's injury status, the latest assessment and what it means for India's ODI plans.",
        "hashtags": ["#Cricket", "#ShubmanGill", "#IndiaCricket"],
        "comment": "What should India do if Gill misses the ODI?",
        "script": [
            {
                "voiceover": scene1,
                "narrative_role": "opening",
                "primary_entity": "Shubman Gill",
                "visual_intent": "Gill during India cricket action",
                "specific_search_prompt": "Shubman Gill India cricket",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "Gill was struck during training and returned after treatment.",
                "narrative_role": "development",
                "primary_entity": "Shubman Gill",
                "visual_intent": "Gill at India training",
                "specific_search_prompt": "Shubman Gill cricket training",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "The team is assessing him before the next ODI.",
                "narrative_role": "context",
                "primary_entity": "India cricket team",
                "visual_intent": "India team training",
                "specific_search_prompt": "India cricket team training ODI",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "His availability will depend on the next medical assessment.",
                "narrative_role": "consequence",
                "primary_entity": "Shubman Gill",
                "visual_intent": "Gill fitness assessment",
                "specific_search_prompt": "Shubman Gill fitness India cricket",
                "sport_or_topic_category": "Cricket",
            },
        ],
    }


def test_slide_one_is_strictly_less_than_14_words():
    result = valid_result("Gill faces a fresh injury scare before India's ODI.")
    assert len(result["script"][0]["voiceover"].split()) < 14
    assert validate_cricket_script(result, "")[0]

    invalid = valid_result("Gill faces a fresh injury scare before India's next ODI against West Indies today.")
    assert len(invalid["script"][0]["voiceover"].split()) == 14
    assert validate_cricket_script(invalid, "")[0] is False


def test_cricket_schema_requires_exactly_four_slides():
    script_items = CRICKET_SCHEMA["properties"]["script"]
    assert script_items["minItems"] == 4
    assert script_items["maxItems"] == 4


def test_titles_description_hashtags_and_comment_are_structural_outputs():
    result = valid_result()
    assert validate_cricket_script(result, "")[0]

    result["titles"] = []
    assert validate_cricket_script(result, "")[0] is False

    result = valid_result()
    result["seo_description"] = ""
    assert validate_cricket_script(result, "")[0] is False

    result = valid_result()
    result["hashtags"] = []
    assert validate_cricket_script(result, "")[0] is False

    result = valid_result()
    result["comment"] = ""
    assert validate_cricket_script(result, "")[0] is False


def test_no_new_editorial_heuristics_are_applied():
    result = valid_result("Gill was struck during training before the ODI.")
    result["titles"] = ["A", "B", "C"]
    result["seo_description"] = "Everything important from the source."
    result["hashtags"] = ["#Cricket"]
    valid, _ = validate_cricket_script(result, "")
    assert valid


def test_writer_uses_one_generation_call_when_valid(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "[SELECTED STORY]\nGill injury story")

    def fake_request(*args, **kwargs):
        calls.append((args, kwargs))
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = write_script({"title": "Gill injury story"}, language="english")

    assert len(calls) == 1
    assert len(result["script"]) == 4
    assert result["word_count"] > 0


def test_writer_repairs_an_overlong_slide_one_without_falling_back_models(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "STORY")

    def fake_request(model, prompt, story, schema=None):
        calls.append((model, schema, prompt))
        if schema is CRICKET_SCHEMA:
            return valid_result(
                "Gill faces a fresh injury scare before India's next ODI against West Indies today."
            )
        assert schema is SLIDE_ONE_SCHEMA
        return {"voiceover": "Gill faces an injury scare before India's ODI."}

    monkeypatch.setattr(script_writer, "_request", fake_request)

    result = write_script({"title": "Gill injury story"}, language="english")

    assert [call[0] for call in calls] == ["openai/gpt-oss-120b", "openai/gpt-oss-120b"]
    assert calls[1][1] is SLIDE_ONE_SCHEMA
    assert len(result["script"]) == 4
    assert len(result["script"][0]["voiceover"].split()) < 14


def test_writer_falls_back_to_second_model_only_after_primary_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "STORY")

    def fake_request(model, prompt, story, schema=None):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("primary failed")
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = write_script({"title": "Gill injury story"}, language="english")

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_prompt_contains_retention_and_information_objectives():
    assert "RETENTION" in SYSTEM_PROMPT
    assert "INFORMATIVE" in SYSTEM_PROMPT
    assert "roughly 90%" in SYSTEM_PROMPT
    assert "fewer than 14 words" in SYSTEM_PROMPT
    assert "less than 30 seconds" in SYSTEM_PROMPT
    assert "rivalry" in SYSTEM_PROMPT
    assert "Do not deliberately target a word count" in SYSTEM_PROMPT
    assert "3-second" not in SYSTEM_PROMPT.casefold()


def test_forceful_retry_is_a_full_rewrite_not_a_coverage_patch(monkeypatch):
    captured = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL SOURCE STORY")

    def fake_request(model, prompt, story, schema=None):
        captured.append(prompt)
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)

    previous = valid_result()
    write_script(
        {"title": "Auqib Nabi profile"},
        forceful=True,
        previous_script=previous,
    )

    assert len(captured) == 1
    assert "MANUAL-QC REWRITE" in captured[0]
    assert "rewrite from scratch" in captured[0].casefold()
    assert "90%" in captured[0]
    assert "PREVIOUS DRAFT" in captured[0]


def test_request_uses_requested_schema_and_low_reasoning(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(valid_result())}}]}

        return Response()

    monkeypatch.setattr(script_writer.requests, "post", fake_post)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    _request("openai/gpt-oss-120b", "test", "story", schema=CRICKET_SCHEMA)

    payload = captured["payload"]
    assert payload["reasoning_effort"] == "low"
    assert payload["include_reasoning"] is False
    assert payload["response_format"]["json_schema"]["schema"] == CRICKET_SCHEMA


def test_research_keeps_primary_and_related_reporting(monkeypatch):
    primary = "Primary story facts: Auqib Nabi made his India ODI debut at 29 and had a strong domestic record. " * 12
    related = "Related report facts: Auqib Nabi took 60 Ranji Trophy wickets and has 170 first-class wickets. " * 10

    monkeypatch.setattr(
        script_writer,
        "_extract_article",
        lambda url: (primary if url.endswith("/primary") else related, url),
    )
    monkeypatch.setattr(
        script_writer,
        "_related_article_urls",
        lambda *args, **kwargs: [
            ("Related Auqib Nabi stats", "https://example.com/related"),
        ],
    )

    packet = script_writer._research_story({
        "title": "Auqib Nabi India debut profile",
        "description": "Age, stats and career background",
        "url": "https://example.com/primary",
    })

    assert "[PRIMARY ARTICLE — https://example.com/primary]" in packet
    assert "[RELATED CURRENT REPORT 1 — Related Auqib Nabi stats — https://example.com/related]" in packet
    assert "60 Ranji Trophy wickets" in packet


def test_structured_html_keeps_tables():
    html = """<html><head>
    <script type="application/ld+json">{"articleBody":"Auqib Nabi made his India debut."}</script>
    </head><body>
    <h2>Career statistics</h2>
    <table>
      <tr><th>Ranji Trophy</th><th>60 wickets</th></tr>
      <tr><td>First-class</td><td>170 wickets</td></tr>
    </table>
    </body></html>"""
    text = _article_body_from_html(html)
    assert "Career statistics" in text
    assert "Ranji Trophy | 60 wickets" in text
    assert "First-class | 170 wickets" in text


def test_apply_edits_preserves_four_slides_and_checks_slide_one():
    result = valid_result()
    edited = apply_script_edits(
        result,
        [
            "Gill returns after treatment.",
            result["script"][1]["voiceover"],
            result["script"][2]["voiceover"],
            result["script"][3]["voiceover"],
        ],
    )
    assert len(edited["script"]) == 4
    assert edited["approved_for_audio"] is True

    with pytest.raises(ValueError):
        apply_script_edits(
            result,
            [
                "Gill faces a fresh injury scare before India's next ODI against West Indies today.",
                *[scene["voiceover"] for scene in result["script"][1:]],
            ],
        )


def test_validate_script_remains_available_for_niche_compatibility():
    result = valid_result()
    valid, reason = validate_script(result, "")
    assert valid, reason
