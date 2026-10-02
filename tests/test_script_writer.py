import pytest

import script_writer


class Story:
    title = "Shubman Gill injury update"
    description = "Gill is being assessed ahead of the next ODI."
    url = "https://example.com/gill"
    source = "example"


def valid_result(scene1="Shubman Gill faces an injury scare before India's ODI."):
    return {
        "subject_name": "Shubman Gill",
        "headline": "Gill Injury Update",
        "titles": [
            "Shubman Gill Injury Update Ahead Of India ODI",
            "Why Shubman Gill's Injury Could Change India's ODI Plans",
            "Shubman Gill Fitness: What Happens Next?",
            "What Gill's Injury Means For India's ODI",
            "India's Gill Injury Has Cricket Fans Asking Questions",
        ],
        "seo_description": "Shubman Gill's injury status ahead of India's next ODI.",
        "hashtags": ["#Cricket", "#ShubmanGill", "#IndiaCricket", "#ODI"],
        "comment": "Should India risk Gill in the next ODI?",
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


def test_prompt_contains_generation_rules():
    assert "13 words or fewer" in script_writer.SYSTEM_PROMPT
    assert "32 seconds or less" in script_writer.SYSTEM_PROMPT
    assert "exact `subject_name` must appear in the spoken narration" in script_writer.SYSTEM_PROMPT
    assert "all important factual information" in script_writer.SYSTEM_PROMPT.casefold()
    assert "exactly 5 concise" in script_writer.SYSTEM_PROMPT
    assert "SEO / Search" in script_writer.SYSTEM_PROMPT
    assert "Curiosity / Baity" in script_writer.SYSTEM_PROMPT
    assert "Trend / Format" in script_writer.SYSTEM_PROMPT
    assert "4–5 tightly relevant hashtags" in script_writer.SYSTEM_PROMPT


def test_schema_requires_four_slides_and_subject():
    assert script_writer.CRICKET_SCHEMA["properties"]["script"]["minItems"] == 4
    assert script_writer.CRICKET_SCHEMA["properties"]["script"]["maxItems"] == 4
    assert "subject_name" in script_writer.CRICKET_SCHEMA["required"]
    assert script_writer.CRICKET_SCHEMA["properties"]["titles"]["minItems"] == 3
    assert script_writer.CRICKET_SCHEMA["properties"]["titles"]["maxItems"] == 5


def test_validator_rejects_slide_one_over_13_words():
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    assert script_writer._words(result["script"][0]["voiceover"]) == 14
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "Slide 1" in reason


def test_validator_rejects_over_32_seconds():
    result = valid_result()
    result["script"][1]["voiceover"] = " ".join(["important"] * 75)
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "32 seconds" in reason


def test_validator_requires_subject_name_in_narration():
    result = valid_result()
    for scene in result["script"]:
        scene["voiceover"] = scene["voiceover"].replace("Shubman Gill", "the 35-year-old").replace(
            "Gill", "the player"
        )
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "subject" in reason.casefold()


def test_valid_script_passes():
    valid, reason = script_writer.validate_cricket_script(valid_result())
    assert valid, reason


def test_validator_requires_five_distinct_titles():
    result = valid_result()
    result["titles"] = result["titles"][:3]
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "exactly 5 titles" in reason

    result = valid_result()
    result["titles"][4] = result["titles"][0]
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "distinct" in reason

def test_validator_requires_seo_title_to_name_subject():
    result = valid_result()
    result["titles"][0] = "India ODI Plans After Injury"
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "SEO title" in reason

def test_validator_rejects_overlong_title():
    result = valid_result()
    result["titles"][0] = " ".join(["Shubman", "Gill"] + ["update"] * 50)
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "100 characters" in reason

def test_validator_requires_valid_cricket_hashtags():
    result = valid_result()
    result["hashtags"] = ["#Cricket", "#ShubmanGill", "#IndiaCricket"]
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "4–5" in reason

    result = valid_result()
    result["hashtags"][0] = "#India Cricket"
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "valid hashtags" in reason


def test_writer_returns_valid_result_in_one_model_call(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")

    def fake_request(model, prompt, story, schema=None):
        calls.append((model, prompt, story, schema))
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story(), language="english")

    assert len(calls) == 1
    assert result["provider_used"] == "openai/gpt-oss-120b"
    assert result["estimated_seconds"] <= 32


def test_writer_hides_invalid_first_draft_and_rewrites_once(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")
    drafts = [
        valid_result(
            "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
        ),
        valid_result(),
    ]

    def fake_request(model, prompt, story, schema=None):
        calls.append((model, prompt))
        return drafts.pop(0)

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story())

    assert len(calls) == 2
    assert calls[0][0] == "openai/gpt-oss-120b"
    assert calls[1][0] == "openai/gpt-oss-20b"
    assert "HIDDEN REWRITE" in calls[1][1]
    assert "Slide 1" in calls[1][1]
    assert script_writer._words(result["script"][0]["voiceover"]) < 14


def test_writer_hides_overlong_script_and_rewrites_once(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")
    too_long = valid_result()
    too_long["script"][1]["voiceover"] = " ".join(["important"] * 75)

    def fake_request(model, prompt, story, schema=None):
        calls.append(prompt)
        return too_long if len(calls) == 1 else valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story())

    assert len(calls) == 2
    assert "32 seconds" in calls[1]
    assert result["estimated_seconds"] <= 32


def test_writer_never_returns_second_invalid_draft(monkeypatch):
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")
    bad = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    monkeypatch.setattr(script_writer, "_request", lambda *args, **kwargs: bad)

    with pytest.raises(RuntimeError, match="hidden rewrite"):
        script_writer.write_script(Story())


def test_writer_uses_second_model_when_primary_call_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")

    def fake_request(model, prompt, story, schema=None):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("primary failed")
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story())

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_research_uses_primary_and_related_reports(monkeypatch):
    monkeypatch.setattr(
        script_writer,
        "_extract_article",
        lambda url: (
            "Primary article facts " * 80 if "gill" in url else "Related article facts " * 80,
            url,
        ),
    )
    monkeypatch.setattr(
        script_writer,
        "_related_article_urls",
        lambda *args, **kwargs: [
            ("Gill related report", "https://example.com/related")
        ],
    )

    packet = script_writer._research_story(
        {
            "title": "Shubman Gill injury update",
            "description": "Gill assessment",
            "url": "https://example.com/gill",
        }
    )

    assert "[PRIMARY ARTICLE" in packet
    assert "[RELATED REPORT 1" in packet
    assert "Related article facts" in packet


def test_apply_script_edits_keeps_contract():
    result = valid_result()
    edited = script_writer.apply_script_edits(
        result,
        [scene["voiceover"] for scene in result["script"]],
        headline="Gill Injury Update",
    )
    assert edited["approved_for_audio"] is True


def test_niche_writer_import_contract_remains_available():
    from niche_sports_script_writer import write_niche_sports_script

    assert callable(write_niche_sports_script)
