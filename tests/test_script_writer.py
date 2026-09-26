from script_writer import apply_script_edits, write_script


def valid_result(scene1="Gill suffers a fresh injury scare before India’s ODI."):
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


