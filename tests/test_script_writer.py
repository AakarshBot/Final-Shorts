import json

import pytest

import script_writer
from script_writer import SYSTEM_PROMPT, _article_body_from_html, _request, _request_coverage_audit, apply_script_edits, validate_script, write_script


def valid_result(scene1="Gill faces fresh injury scare."):
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
                "narrative_role": "hook",
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
    assert validate_script(result, "")[0]

    invalid = valid_result("Gill faces a fresh injury scare before India's next big ODI match.")
    assert len(invalid["script"][0]["voiceover"].split()) == 14
    assert validate_script(invalid, "")[0] is False


def test_titles_description_and_hashtags_are_required_outputs():
    result = valid_result()
    assert validate_script(result, "")[0]

    result["titles"] = []
    assert validate_script(result, "")[0] is False

    result = valid_result()
    result["seo_description"] = ""
    assert validate_script(result, "")[0] is False

    result = valid_result()
    result["hashtags"] = []
    assert validate_script(result, "")[0] is False


def test_no_extra_editorial_rules_are_applied():
    result = valid_result(
        "Gill was struck during training before the ODI."
    )
    result["titles"] = ["A", "B", "C"]
    result["seo_description"] = "Everything important from the source."
    result["hashtags"] = ["#Cricket"]
    valid, _ = validate_script(result, "")
    assert valid


def test_writer_produces_exactly_four_slides(monkeypatch):
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "[SELECTED STORY]\nGill injury story")
    monkeypatch.setattr(script_writer, "_request_coverage_audit", lambda source, result: {
        "coverage_pct": 0.96,
        "complete": True,
        "covered_facts": ["injury", "assessment"],
        "missing_facts": [],
    })
    monkeypatch.setattr(script_writer, "_request", lambda *args, **kwargs: valid_result())
    result = write_script({"title": "Gill injury story"}, language="english")
    assert len(result["script"]) == 4
    assert result["word_count"] > 0


def test_writer_uses_low_reasoning_effort(monkeypatch):
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
    _request("openai/gpt-oss-120b", "test", "story")
    assert captured["payload"]["reasoning_effort"] == "low"
    assert captured["payload"]["include_reasoning"] is False


def test_coverage_audit_payload_contains_source_and_script(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": json.dumps({
                    "coverage_pct": 0.95,
                    "complete": True,
                    "covered_facts": ["fact one"],
                    "missing_facts": [],
                })}}]}

        return Response()

    monkeypatch.setattr(script_writer.requests, "post", fake_post)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    audit = _request_coverage_audit("FULL SOURCE STORY", valid_result())
    assert audit["complete"] is True
    text = captured["payload"]["messages"][1]["content"]
    assert "FULL SOURCE STORY" in text
    assert "Gill Injury Update" in text


def test_incomplete_coverage_forces_a_rewrite(monkeypatch):
    calls = []
    audits = iter([
        {"coverage_pct": 0.71, "complete": False, "covered_facts": ["debut"], "missing_facts": ["age", "Ranji wickets", "career background"]},
        {"coverage_pct": 0.97, "complete": True, "covered_facts": ["age", "Ranji wickets", "career background"], "missing_facts": []},
    ])

    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "SOURCE WITH AGE RANJI WICKETS AND CAREER")
    def fake_request(model, prompt, story):
        calls.append(prompt)
        result = valid_result()
        if len(calls) == 1:
            result["script"][0]["voiceover"] = "Gill makes his India debut."
        return result

    monkeypatch.setattr(script_writer, "_request", fake_request)
    monkeypatch.setattr(script_writer, "_request_coverage_audit", lambda source, result: next(audits))
    result = write_script({"title": "Auqib Nabi profile"}, forceful=False)

    assert len(calls) == 2
    assert "age" in calls[1]
    assert "Ranji wickets" in calls[1]
    assert result["coverage_audit"]["complete"] is True


def test_forceful_manual_retry_contains_previous_draft_and_forceful_instruction(monkeypatch):
    captured = []

    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL SOURCE STORY")
    monkeypatch.setattr(script_writer, "_request_coverage_audit", lambda source, result: {
        "coverage_pct": 0.96,
        "complete": True,
        "covered_facts": [],
        "missing_facts": [],
    })

    def fake_request(model, prompt, story):
        captured.append(prompt)
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    previous = valid_result()
    write_script({"title": "Auqib Nabi profile"}, forceful=True, previous_script=previous)

    assert "MANUAL-QC FORCEFUL RETRY" in captured[0]
    assert "PREVIOUS DRAFT TO IMPROVE" in captured[0]
    assert "90%" in captured[0]


def test_research_collects_primary_and_related_current_reports(monkeypatch):
    captured = []

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
            ("Another Auqib Nabi report", "https://other.com/report"),
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
            ["This slide has fourteen words and therefore must fail the rule today.", *[scene["voiceover"] for scene in result["script"][1:]]],
        )


def test_prompt_contains_only_the_requested_editorial_constraints():
    assert "fewer than 14 words" in SYSTEM_PROMPT
    assert "less than 30 seconds" in SYSTEM_PROMPT
    assert "roughly 90%" in SYSTEM_PROMPT
    assert "every slide must contain important information" in SYSTEM_PROMPT
    assert "related current reporting" in SYSTEM_PROMPT
