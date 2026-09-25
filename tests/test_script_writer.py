from script_writer import apply_script_edits, write_script

def valid_result(scene1="Gill suffers a fresh injury scare before India’s ODI."):
    return {
        "titles": ["Gill injury scare before ODI", "India captain hit in nets", "Gill fitness update"],
        "recommended_title_index": 1,
        "seo_description": "Shubman Gill faces an injury scare before India’s next ODI.",
        "pinned_comment": "How serious do you think this could be?",
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

    def fake_request(model, system_prompt, story_text, timeout=30):
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
    assert len(result["titles"]) == 3
    assert len(result["script"]) == 4


def test_writer_falls_back_to_groq_20b_on_provider_failure(monkeypatch):
    calls = []

    def fake_request(model, system_prompt, story_text, timeout=30):
        calls.append(model)
        if model == "openai/gpt-oss-120b":
            raise RuntimeError("primary unavailable")
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script({"title": "India cricket injury update", "description": "A player faces an injury scare."})

    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_repairs_a_bad_first_draft(monkeypatch):
    calls = []

    def fake_request(model, system_prompt, story_text, timeout=30):
        calls.append(story_text)
        if len(calls) == 1:
            return valid_result(scene1="Before the first ODI, Shubman Gill suffered an injury scare during a lengthy training session.")
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {"title": "Gill injury scare", "description": "Shubman Gill was hit in training before the ODI."}
    )

    assert len(calls) == 2
    assert result["repair_applied"] is True


def test_approved_edits_preserve_titles_and_validate_structure():
    original = valid_result()
    edited = apply_script_edits(
        original,
        [
            "Gill faces an injury scare before India’s ODI.",
            original["script"][1]["voiceover"],
            original["script"][2]["voiceover"],
            original["script"][3]["voiceover"],
        ],
    )

    assert edited["titles"] == original["titles"]
    assert edited["script"][0]["voiceover"].startswith("Gill faces")
    assert edited["human_script_edited"] is True


def test_writer_rejects_retention_bait(monkeypatch):
    monkeypatch.setattr(
        "script_writer._request",
        lambda *args, **kwargs: valid_result(
            "Wait until the end because this injury update changes everything."
        ),
    )

    try:
        write_script({"title": "India cricket injury update", "description": "A player faces an injury scare."})
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
    else:
        raise AssertionError("Retention-bait draft should not pass.")
