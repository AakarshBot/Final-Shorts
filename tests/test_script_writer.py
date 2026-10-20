import json

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
            "Shubman Gill Injury Update",
            "Why Gill's Injury Matters For India",
            "Gill's Fitness Before India's Next ODI",
        ],
        "seo_description": "Shubman Gill's injury status ahead of India's next ODI.",
        "hashtags": ["#Cricket", "#ShubmanGill", "#IndiaCricket"],
        "comment": "Should India risk Gill in the next ODI?",
        "quote": "Gill could be back soon.",
        "quote_attribution": "Aakash Chopra",
        "quote_slide": 1,
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


def test_translate_card_copy_translates_visible_copy_and_preserves_stats(monkeypatch):
    data = {
        "language": "english",
        "eyebrow": "CAREER STAT",
        "headline": "A huge scoring run",
        "value": "1,203",
        "unit": "RUNS",
        "metrics": [
            {"label": "Matches", "value": "38"},
            {"label": "Average", "value": "46.27"},
        ],
    }

    def fake_request(model, prompt, story, schema=None, **kwargs):
        payload = json.loads(story)
        assert "natural Hindi in Devanagari script" in prompt
        assert schema["required"] == list(payload)
        return {
            key: {
                "CAREER STAT": "करियर आँकड़े",
                "A huge scoring run": "रनों की शानदार पारी",
                "RUNS": "रन",
                "Matches": "मैच",
                "Average": "औसत",
            }[value]
            for key, value in payload.items()
        }

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.translate_card_copy("Stat Highlight", data, "hindi")

    assert result["language"] == "hindi"
    assert result["eyebrow"] == "करियर आँकड़े"
    assert result["headline"] == "रनों की शानदार पारी"
    assert result["unit"] == "रन"
    assert result["value"] == "1,203"
    assert result["metrics"] == [
        {"label": "मैच", "value": "38"},
        {"label": "औसत", "value": "46.27"},
    ]


def test_translate_card_copy_remaps_head_to_head_metric_keys(monkeypatch):
    data = {
        "language": "english",
        "eyebrow": "HEAD TO HEAD",
        "headline": "Who has the edge?",
        "left": {"name": "Virat Kohli", "values": {"Runs": "100", "Average": "50"}},
        "right": {"name": "Joe Root", "values": {"Runs": "90", "Average": "45"}},
        "metrics": ["Runs", "Average"],
    }

    def fake_request(model, prompt, story, schema=None, **kwargs):
        payload = json.loads(story)
        translate = {
            "HEAD TO HEAD": "आमने-सामने",
            "Who has the edge?": "किसका पलड़ा भारी?",
            "Runs": "रन",
            "Average": "औसत",
        }
        return {key: translate[value] for key, value in payload.items()}

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.translate_card_copy("Head-to-Head", data, "hindi")

    assert result["metrics"] == ["रन", "औसत"]
    assert result["left"]["values"] == {"रन": "100", "औसत": "50"}
    assert result["right"]["values"] == {"रन": "90", "औसत": "45"}
    assert result["left"]["name"] == "Virat Kohli"
    assert result["right"]["name"] == "Joe Root"


def test_translate_card_copy_translates_textual_milestone_value(monkeypatch):
    data = {
        "language": "english",
        "eyebrow": "MILESTONE",
        "value": "100 international appearances",
        "label": "A career landmark",
        "context": "Reached in the latest match.",
    }

    def fake_request(model, prompt, story, schema=None, **kwargs):
        payload = json.loads(story)
        translate = {
            "MILESTONE": "उपलब्धि",
            "100 international appearances": "100 अंतरराष्ट्रीय मुकाबले",
            "A career landmark": "करियर की खास उपलब्धि",
            "Reached in the latest match.": "हालिया मैच में हासिल हुई।",
        }
        return {key: translate[value] for key, value in payload.items()}

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.translate_card_copy("Key Fact / Milestone", data, "hindi")

    assert result["value"] == "100 अंतरराष्ट्रीय मुकाबले"
    assert result["value"].startswith("100 ")


def test_translate_card_copy_rejects_text_subject_cutout():
    with pytest.raises(ValueError, match="not supported"):
        script_writer.translate_card_copy("Text Subject Cutout", {}, "hindi")


def test_prompt_contains_generation_rules():
    assert "13 words or fewer" in script_writer.SYSTEM_PROMPT
    assert "exact `subject_name` must appear in the spoken narration" in script_writer.SYSTEM_PROMPT
    assert "all important factual information" in script_writer.SYSTEM_PROMPT.casefold()
    assert "fit within 30 seconds" in script_writer.SYSTEM_PROMPT
    assert "between 50 and 70 spoken words (~20 to 28 seconds)" in script_writer.SYSTEM_PROMPT
    assert "Return 3–5 spoken slides" in script_writer.SYSTEM_PROMPT
    assert "direct quote" in script_writer.SYSTEM_PROMPT
    assert "Do not create an extra slide for a quote" in script_writer.SYSTEM_PROMPT


def test_schema_allows_three_to_five_slides_and_subject():
    assert script_writer.CRICKET_SCHEMA["properties"]["script"]["minItems"] == 3
    assert script_writer.CRICKET_SCHEMA["properties"]["script"]["maxItems"] == 5
    assert "subject_name" in script_writer.CRICKET_SCHEMA["required"]
    assert script_writer.CRICKET_SCHEMA["properties"]["titles"]["minItems"] == 3
    assert script_writer.CRICKET_SCHEMA["properties"]["titles"]["maxItems"] == 3
    assert script_writer.CRICKET_SCHEMA["properties"]["quote"]["type"] == "string"
    assert script_writer.CRICKET_SCHEMA["properties"]["quote_attribution"]["type"] == "string"
    assert script_writer.CRICKET_SCHEMA["properties"]["quote_slide"]["minimum"] == 0
    assert script_writer.CRICKET_SCHEMA["properties"]["quote_slide"]["maximum"] == 5


@pytest.mark.parametrize("slide_count", [3, 4, 5])
def test_cricket_validator_accepts_three_to_five_slides(slide_count):
    result = valid_result()
    if slide_count < 4:
        result["script"] = result["script"][:slide_count]
    elif slide_count > 4:
        result["script"].append(
            {
                **result["script"][-1],
                "voiceover": "Shubman Gill's next medical assessment will determine his availability.",
            }
        )

    valid, reason = script_writer.validate_cricket_script(result)
    assert valid, reason


@pytest.mark.parametrize("slide_count", [2, 6])
def test_cricket_validator_rejects_slide_counts_outside_three_to_five(slide_count):
    result = valid_result()
    if slide_count < 3:
        result["script"] = result["script"][:slide_count]
    else:
        result["script"].extend([dict(result["script"][-1]), dict(result["script"][-1])])

    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "3–5" in reason


def test_prompt_contains_three_title_angles():
    prompt = script_writer.SYSTEM_PROMPT
    assert "SEO / Search" in prompt
    assert "Consequence / Why It Matters" in prompt
    assert "Curiosity" in prompt


def test_indic_generation_preflight_catches_long_lead_without_changing_public_validator():
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's next ODI against England"
    )

    valid, reason = script_writer.validate_cricket_script(result, language="hindi")
    generation_valid, generation_reason = script_writer._validate_generated_cricket_draft(
        result, "hindi"
    )

    assert valid, reason
    assert not generation_valid
    assert "Slide 1" in generation_reason
    assert "nine or fewer" in generation_reason


def test_indic_generation_preflight_targets_total_length_without_padding():
    result = valid_result("Shubman Gill is facing an injury concern.")
    result["script"][1]["voiceover"] += " " + " ".join(["context"] * 30)

    issue = script_writer._indic_generation_delivery_issue(result, "telugu")

    assert "narration has" in issue
    assert "62 or fewer" in issue
    assert "without dropping essential facts or adding filler" in issue


def test_writer_hidden_rewrite_fixes_indic_timing_preflight(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")
    too_long = valid_result(
        "Shubman Gill faces a fresh injury scare before India's next ODI against England"
    )
    concise = valid_result("Shubman Gill faces an injury scare before India's next ODI.")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append((model, prompt))
        return too_long if len(calls) == 1 else concise

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story(), language="hindi")

    assert len(calls) == 2
    assert "Indic generation timing preflight" in calls[1][1]
    assert "no more than nine compact" in calls[1][1]
    assert result["script"][0]["voiceover"] == concise["script"][0]["voiceover"]


def test_generation_prompts_cover_validator_requirements():
    cricket = script_writer.SYSTEM_PROMPT
    universal = script_writer.UNIVERSAL_SYSTEM_PROMPT
    top5 = script_writer.TOP5_SYSTEM_PROMPT

    assert "Each slide must include non-empty primary_entity, visual_intent, specific_search_prompt, and sport_or_topic_category" in cricket
    assert "a non-empty, crisp dashboard-only headline" in cricket
    assert "at least one relevant hashtag" in cricket
    assert "quote_attribution and quote_slide from 1–5" in cricket
    assert "never greater than the generated slide count" in cricket
    assert "3–5 hashtags each beginning with # and containing no spaces" in universal
    assert "quote, quote_attribution, and quote_slide must agree" in universal
    assert "story_index equals slide_number minus one" in top5
    assert "SATISFY EVERY EXISTING TOP-5 GENERATION CHECK" in top5
    assert "set to change cricket" in top5
    assert "not only Slide 1" in top5
    assert "need to see/watch/know" in top5



def test_validator_rejects_slide_one_over_13_words():
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    assert script_writer._words(result["script"][0]["voiceover"]) == 14
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "Slide 1" in reason


@pytest.mark.parametrize("language", ["hindi", "telugu"])
def test_indic_script_validator_uses_audio_duration_instead_of_word_count(language):
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    assert script_writer._words(result["script"][0]["voiceover"]) == 14

    valid, reason = script_writer.validate_cricket_script(result, language=language)

    assert valid, reason


def test_generation_validator_accepts_long_dashboard_only_headline():
    result = valid_result()
    result["headline"] = (
        "Shubman Gill injury update explains what India's next ODI selection decision depends on"
    )

    valid, reason = script_writer.validate_cricket_script(result)

    assert valid, reason


@pytest.mark.parametrize("language", ["hindi", "telugu"])
def test_generation_validator_requires_but_does_not_limit_dashboard_headline(language):
    result = valid_result()
    result["headline"] = (
        "A much longer headline that remains crisp but only appears on the dashboard"
    )

    valid, reason = script_writer.validate_cricket_script(result, language=language)

    assert valid, reason


@pytest.mark.parametrize("language", ["hindi", "telugu"])
def test_universal_validator_allows_long_dashboard_headline_and_duration_based_lead(language):
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    result["headline"] = (
        "Shubman Gill injury update explains what India's next ODI selection decision depends on"
    )
    result["script"][3]["voiceover"] += (
        " The selection decision will follow the medical review and the team's final assessment before match day."
    )

    valid, reason = script_writer.validate_universal_script(result, language=language)

    assert valid, reason


def test_universal_validator_keeps_english_13_word_limit():
    result = valid_result(
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England"
    )
    result["script"][3]["voiceover"] += (
        " The selection decision will follow the medical review and the team's final assessment before match day."
    )

    valid, reason = script_writer.validate_universal_script(result, language="english")

    assert not valid
    assert "Slide 1" in reason


def test_validator_requires_subject_name_in_narration():
    result = valid_result()
    for scene in result["script"]:
        scene["voiceover"] = scene["voiceover"].replace("Shubman Gill", "the 35-year-old").replace(
            "Gill", "the player"
        )
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "subject" in reason.casefold()


def test_validator_requires_headline_when_generating():
    result = valid_result()
    result["headline"] = ""
    valid, reason = script_writer.validate_cricket_script(result)
    assert not valid
    assert "headline is required" in reason


def test_quote_handoff_survives_script_edits():
    result = valid_result()
    result["quote"] = "I think Virat Kohli will finish on 98 centuries."
    result["quote_attribution"] = "Aakash Chopra"
    result["quote_slide"] = 1
    edited = script_writer.apply_script_edits(
        result,
        [scene["voiceover"] for scene in result["script"]],
        headline=result["headline"],
    )
    assert edited["quote"] == result["quote"]
    assert edited["quote_attribution"] == "Aakash Chopra"
    assert edited["quote_slide"] == 1


def test_apply_script_edits_allows_disabled_headline():
    result = valid_result()
    edited = script_writer.apply_script_edits(
        result,
        [scene["voiceover"] for scene in result["script"]],
        headline="",
    )
    assert edited["headline"] == ""
    assert edited["approved_for_audio"] is True



@pytest.mark.parametrize(
    "apply_edits",
    [script_writer.apply_script_edits, script_writer.apply_universal_script_edits],
)
def test_manual_edits_are_not_rejected_by_editorial_validation(apply_edits):
    result = valid_result()
    edited_voiceovers = [
        "Shubman Gill faces a fresh injury scare before India's crucial next ODI against England",
        "The player was struck during training and returned after treatment.",
        "The team is assessing him before the next ODI.",
        "His availability will depend on the next medical assessment.",
    ]
    edited_voiceovers = [
        voiceover.replace("Shubman Gill", "the player").replace("Gill", "the player")
        for voiceover in edited_voiceovers
    ]

    approved = apply_edits(
        result,
        edited_voiceovers,
        headline="A much longer human-written headline is acceptable",
    )

    assert approved["approved_for_audio"] is True
    assert approved["headline"] == "A much longer human-written headline is acceptable"
    assert approved["script"][0]["voiceover"] == edited_voiceovers[0]
    assert "Shubman Gill" not in " ".join(scene["voiceover"] for scene in approved["script"])


def test_valid_script_passes():
    valid, reason = script_writer.validate_cricket_script(valid_result())
    assert valid, reason


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


def test_cricket_angle_schema_requires_exactly_three_options():
    assert script_writer.ANGLE_SCHEMA["properties"]["angles"]["minItems"] == 3
    assert script_writer.ANGLE_SCHEMA["properties"]["angles"]["maxItems"] == 3


def test_validate_cricket_story_angles():
    valid = {
        "angles": [
            {"title": "Injury Scare", "description": "Focus on the injury.", "evidence_basis": "Medical team assessment."},
            {"title": "India Selection Impact", "description": "Focus on squad dynamics.", "evidence_basis": "Upcoming ODI series."},
            {"title": "Chopra Reaction", "description": "Focus on Chopra's quote.", "evidence_basis": "Direct statement in research."},
        ]
    }
    ok, err = script_writer._validate_cricket_story_angles(valid)
    assert ok, err

    bad = {"angles": valid["angles"][:2]}
    ok, err = script_writer._validate_cricket_story_angles(bad)
    assert not ok
    assert "exactly 3" in err

    duplicate = {
        "angles": [
            valid["angles"][0],
            valid["angles"][0],
            valid["angles"][2],
        ]
    }
    ok, err = script_writer._validate_cricket_story_angles(duplicate)
    assert not ok
    assert "duplicate" in err


def test_suggest_cricket_story_angles(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda story: "CRICKET RESEARCH EVIDENCE")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append((model, prompt, story, schema, kwargs))
        return {
            "angles": [
                {"title": "Injury Scare", "description": "Focus on the injury.", "evidence_basis": "Medical team assessment."},
                {"title": "Selection Impact", "description": "Focus on squad dynamics.", "evidence_basis": "Upcoming ODI series."},
                {"title": "What Chopra Said", "description": "Focus on Chopra's quote.", "evidence_basis": "Direct statement in research."},
            ]
        }

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.suggest_cricket_story_angles(Story(), language="english")

    assert len(calls) == 1
    assert calls[0][2] == "CRICKET RESEARCH EVIDENCE"
    assert calls[0][3] is script_writer.ANGLE_SCHEMA
    assert len(result["angles"]) == 3
    assert result["angles"][0]["title"] == "Injury Scare"
    assert result["source_evidence"] == "CRICKET RESEARCH EVIDENCE"


def test_write_script_with_angle(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda story: "CRICKET STORY")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append(prompt)
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(
        Story(),
        language="english",
        angle={"title": "Injury Scare", "description": "Focus on the injury."},
    )

    assert "SELECTED EDITORIAL ANGLE (AUTHORITATIVE)" in calls[0]
    assert "Injury Scare: Focus on the injury." in calls[0]
    assert result["story_angle"] == "Injury Scare: Focus on the injury."




def test_groq_http_errors_include_provider_detail_and_retry_after(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    class FakeResponse:
        status_code = 429
        headers = {"Retry-After": "12"}
        text = '{"error":{"message":"rate limit exceeded","code":"rate_limit_exceeded"}}'

        def json(self):
            return {"error": {"message": "rate limit exceeded", "code": "rate_limit_exceeded"}}

    monkeypatch.setattr(script_writer.requests, "post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(script_writer.GroqAPIError, match="rate_limit_exceeded.*rate limit exceeded") as caught:
        script_writer._request("openai/gpt-oss-120b", "Write a JSON script", "evidence")

    assert caught.value.status_code == 429
    assert caught.value.retry_after == "12"
    assert "Retry-After: 12" in str(caught.value)


def test_groq_400_body_is_preserved_for_schema_debugging(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    class FakeResponse:
        status_code = 400
        headers = {}
        text = ""

        def json(self):
            return {
                "error": {
                    "message": "Invalid JSON schema at properties.script",
                    "type": "invalid_request_error",
                    "code": "json_schema_validation_error",
                }
            }

    monkeypatch.setattr(script_writer.requests, "post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(script_writer.GroqAPIError, match="json_schema_validation_error.*Invalid JSON schema") as caught:
        script_writer._request("openai/gpt-oss-20b", "Write a JSON script", "evidence")

    assert caught.value.status_code == 400


def test_groq_json_validate_failed_retries_once_in_json_object_mode(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    captured = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.headers = {}
            self._payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    responses = [
        FakeResponse(
            400,
            {
                "error": {
                    "message": "Failed to generate JSON. Please adjust your prompt.",
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "failed_generation": {"reason": "constrained output generation failed"},
                }
            },
        ),
        FakeResponse(200, {"choices": [{"message": {"content": json.dumps(valid_result())}}]}),
    ]

    def fake_post(_url, *, json, **_kwargs):
        captured.append(json)
        return responses.pop(0)

    monkeypatch.setattr(script_writer.requests, "post", fake_post)
    result = script_writer._request(
        "openai/gpt-oss-20b",
        "Generate a cricket script. Return only JSON matching the supplied schema.",
        "FULL STORY",
        schema=script_writer.CRICKET_SCHEMA,
        schema_name="cricket_shorts_script",
    )

    assert result == valid_result()
    assert len(captured) == 2
    assert captured[0]["response_format"]["type"] == "json_schema"
    assert captured[0]["response_format"]["json_schema"]["strict"] is True
    assert captured[1]["response_format"] == {"type": "json_object"}
    assert "JSON OUTPUT CONTRACT" in captured[1]["messages"][1]["content"]
    assert '"subject_name"' in captured[1]["messages"][1]["content"]


def test_groq_http_error_preserves_failed_generation_detail():
    class FakeResponse:
        status_code = 400
        headers = {}

        def json(self):
            return {
                "error": {
                    "message": "Failed to generate JSON.",
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "failed_generation": {"reason": "constrained generation stopped"},
                }
            }

    error = script_writer._groq_http_error(FakeResponse())
    assert error.status_code == 400
    assert "json_validate_failed" in str(error)
    assert "failed_generation" in str(error)
    assert "constrained generation stopped" in str(error)


def test_subject_validation_gives_specific_english_name_to_rewrite():
    result = valid_result("He faces a fresh injury scare before India's ODI.")
    valid, reason = script_writer.validate_cricket_script(result, language="english")

    assert not valid
    assert "Shubman Gill" in reason
    assert "verbatim" in reason


def test_hindi_subject_validation_requests_consistent_native_script():
    result = valid_result("शुभमन गिल की फिटनेस पर नई चिंता है।")
    valid, reason = script_writer.validate_cricket_script(result, language="hindi")

    assert not valid
    assert "Devanagari/Telugu spelling" in reason
    assert "voiceover" in reason


def test_writer_rewrite_prompt_carries_subject_name_rule(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")
    bad = valid_result("He faces a fresh injury scare before India's ODI.")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append((model, prompt, kwargs))
        if len(calls) == 1:
            return bad
        assert "Shubman Gill" in prompt
        assert "same script and spelling" in prompt
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story(), language="english")

    assert len(calls) == 2
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_uses_fresh_backup_after_rate_limit_not_hidden_rewrite(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append((model, prompt))
        if len(calls) == 1:
            raise script_writer.GroqAPIError(429, "Rate limit reached", "15")
        return valid_result()

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.write_script(Story(), language="hindi")

    assert [call[0] for call in calls] == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert "HIDDEN REWRITE" not in calls[1][1]
    assert "RECOVERY" not in calls[1][1]
    assert result["provider_used"] == "openai/gpt-oss-20b"


def test_writer_stops_on_groq_400_without_spending_another_request(monkeypatch):
    calls = []
    monkeypatch.setattr(script_writer, "_research_story", lambda *args, **kwargs: "FULL STORY")

    def fake_request(model, prompt, story, schema=None, **kwargs):
        calls.append(model)
        raise script_writer.GroqAPIError(400, "The provider rejected the request: json_schema_validation_error")

    monkeypatch.setattr(script_writer, "_request", fake_request)

    with pytest.raises(RuntimeError, match="Groq rejected the Scriptwriter request.*json_schema_validation_error"):
        script_writer.write_script(Story(), language="hindi")

    assert calls == ["openai/gpt-oss-120b"]


def test_groq_strict_schema_omits_undocumented_array_length_keywords(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(_url, *, json, **_kwargs):
        captured.update(json)
        return FakeResponse()

    monkeypatch.setattr(script_writer.requests, "post", fake_post)
    script_writer._request(
        "openai/gpt-oss-120b",
        "Generate a cricket script",
        "evidence",
        schema=script_writer.CRICKET_SCHEMA,
        schema_name="cricket_shorts_script",
    )

    provider_schema = captured["response_format"]["json_schema"]["schema"]
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert "minItems" in script_writer.CRICKET_SCHEMA["properties"]["script"]
    assert "maxItems" in script_writer.CRICKET_SCHEMA["properties"]["script"]
    assert not _contains_array_length_constraints(provider_schema)
    assert provider_schema["properties"]["script"]["items"]["required"] == (
        script_writer.CRICKET_SCHEMA["properties"]["script"]["items"]["required"]
    )


def _contains_array_length_constraints(value):
    if isinstance(value, dict):
        return any(
            key in {"minItems", "maxItems"} or _contains_array_length_constraints(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_array_length_constraints(child) for child in value)
    return False


@pytest.mark.parametrize(
    ("language", "native_name", "lead"),
    [
        ("hindi", "शुभमन गिल", "शुभमन गिल की फिटनेस पर सवाल उठ रहे हैं।"),
        ("telugu", "శుభ్‌మన్ గిల్", "శుభ్‌మన్ గిల్ ఫిట్‌నెస్‌పై ప్రశ్నలు కొనసాగుతున్నాయి."),
    ],
)
def test_generated_script_recovery_normalises_title_count_and_native_subject(
    language, native_name, lead
):
    result = valid_result()
    result["subject_name"] = "Shubman Gill"
    result["titles"] = result["titles"][:2]
    result["script"][0]["voiceover"] = lead
    result["script"][0]["primary_entity"] = native_name

    prepared = script_writer._prepare_generated_script(result, language)

    assert prepared["subject_name"] == native_name
    assert len(prepared["titles"]) == 3
    assert len({script_writer._normalise_name(title) for title in prepared["titles"]}) == 3
    valid, reason = script_writer.validate_cricket_script(prepared, language=language)
    assert valid, reason


@pytest.mark.parametrize(
    "titles",
    [
        ["First title", "Second title"],
        ["First title", "Second title", "Third title", "Fourth title"],
        ["First title", "First title", "Second title"],
    ],
)
def test_generated_script_titles_are_always_three_distinct_candidates(titles):
    result = valid_result()
    result["titles"] = titles

    prepared = script_writer._prepare_generated_script(result, "hindi")

    assert len(prepared["titles"]) == 3
    assert len({script_writer._normalise_name(title) for title in prepared["titles"]}) == 3


def test_name_normalisation_preserves_indic_marks_and_ignores_zero_width_formatting():
    assert script_writer._normalise_name("శుభ్‌మన్ గిల్") == script_writer._normalise_name(
        "శుభ్‌మన్ గిల్".replace("\u200c", "")
    )
    assert script_writer._normalise_name("शुभमन गिल") == script_writer._normalise_name("शुभमन गिल")


def test_groq_request_retries_rate_limit_after_retry_after(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    captured = []
    sleeps = []

    class FakeResponse:
        def __init__(self, status_code, payload, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}
            self.text = json.dumps(payload, ensure_ascii=False)

        def json(self):
            return self._payload

    responses = [
        FakeResponse(
            429,
            {"error": {"message": "TPM rate limit reached", "code": "rate_limit_exceeded"}},
            {"Retry-After": "8"},
        ),
        FakeResponse(200, {"choices": [{"message": {"content": json.dumps(valid_result())}}]}),
    ]

    def fake_post(_url, *, json, **_kwargs):
        captured.append(json)
        return responses.pop(0)

    monkeypatch.setattr(script_writer.requests, "post", fake_post)
    monkeypatch.setattr(script_writer.time, "sleep", sleeps.append)

    result = script_writer._request("openai/gpt-oss-20b", "Write one script as JSON", "evidence")

    assert result == valid_result()
    assert len(captured) == 2
    assert sleeps == [8.0]


@pytest.mark.parametrize(
    ("language", "subject", "voiceovers"),
    [
        (
            "hindi",
            "शुभमन गिल",
            [
                "शुभमन गिल की फिटनेस पर टीम अभी भी फैसला नहीं कर पाई है",
                "रिपोर्ट के मुताबिक अभ्यास के दौरान उन्हें परेशानी हुई और बाद में जांच की गई",
                "टीम प्रबंधन अगला फैसला मेडिकल रिपोर्ट मिलने के बाद ही करेगा जिससे चयन पर असर पड़ सकता है",
                "अगर वह समय पर फिट नहीं होते तो अगले मुकाबले में भारत को नए विकल्प पर भरोसा करना पड़ सकता है",
            ],
        ),
        (
            "telugu",
            "శుభ్‌మన్ గిల్",
            [
                "శుభ్‌మన్ గిల్ ఫిట్‌నెస్‌పై జట్టు ఇంకా తుది నిర్ణయం తీసుకోలేకపోయింది",
                "నివేదిక ప్రకారం సాధన సమయంలో అతనికి ఇబ్బంది ఎదురైంది తరువాత వైద్య పరీక్ష కూడా జరిగింది",
                "వైద్య నివేదిక అందిన తర్వాతే జట్టు యాజమాన్యం నిర్ణయం తీసుకుంటుంది దీంతో ఎంపికపై ప్రభావం పడవచ్చు",
                "అతను సమయానికి ఫిట్ కాకపోతే తదుపరి మ్యాచ్‌లో భారత్ కొత్త ఆటగాడిపై ఆధారపడాల్సి రావచ్చు దీంతో వ్యూహం కూడా మారే అవకాశం ఉంది కోచ్‌లు దీనిని గమనిస్తున్నారు",
            ],
        ),
    ],
)
def test_universal_validator_counts_hindi_telugu_words_without_splitting_script_marks(
    language, subject, voiceovers
):
    result = valid_result()
    result["subject_name"] = subject
    result["headline"] = "Story headline"
    result["titles"] = [
        "కథ శీర్షిక ఒకటి" if language == "telugu" else "कहानी शीर्षक एक",
        "ఇది ఎందుకు ముఖ్యం" if language == "telugu" else "यह क्यों महत्वपूर्ण है",
        "తర్వాత ఏమవుతుంది" if language == "telugu" else "अब आगे क्या होगा",
    ]
    result["seo_description"] = "Story-specific description."
    result["quote"] = ""
    result["quote_attribution"] = ""
    result["quote_slide"] = 0
    for scene, voiceover in zip(result["script"], voiceovers):
        scene["voiceover"] = voiceover
        scene["primary_entity"] = subject
    narration = " ".join(voiceovers)

    valid, reason = script_writer.validate_universal_script(result, language=language)

    assert script_writer._spoken_word_count(narration, language) == len(narration.split())
    assert script_writer.MIN_WORDS <= script_writer._spoken_word_count(narration, language) <= script_writer.MAX_WORDS
    assert valid, reason
    metrics = script_writer.evaluate_flow({**result, "language_used": language})
    assert metrics["total_words"] == len(narration.split())


def test_generate_stat_card_copy_preserves_story_and_ascii_digits(monkeypatch):
    captured = {}
    response = {
        "eyebrow": "करियर रिकॉर्ड",
        "headline": "शानदार पारी",
        "value": "१२३",
        "unit": "रन",
        "metrics": [
            {"label": "औसत", "value": "४६.२७"},
            {"label": "मैच", "value": "१२"},
            {"label": "शतक", "value": "३"},
        ],
    }

    def fake_request(model, prompt, story, **kwargs):
        captured.update({"prompt": prompt, "story": story, "kwargs": kwargs})
        return response

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.generate_card_copy(
        "Stat Highlight",
        {"title": "Gill scores 123", "script": [{"voiceover": "He scored 123 runs."}]},
        target_language="hindi",
        manual_prompt="Focus on the record.",
    )
    assert result["value"] == "123"
    assert result["metrics"][0]["value"] == "46.27"
    assert result["metrics"][1]["value"] == "12"
    assert "Hindi" in captured["prompt"]
    assert "Focus on the record." in captured["prompt"]
    assert "Gill scores 123" in captured["story"]
    assert captured["kwargs"]["schema_name"] == "editorial_card_copy"


def test_generate_head_to_head_card_copy_returns_renderer_shape(monkeypatch):
    monkeypatch.setattr(script_writer, "_request", lambda *args, **kwargs: {
        "eyebrow": "HEAD TO HEAD", "headline": "Who leads?",
        "left_name": "Player One", "right_name": "Player Two",
        "metrics": [
            {"label": "Runs", "left_value": "1,020", "right_value": "990"},
            {"label": "Average", "left_value": "48.2", "right_value": "44.1"},
            {"label": "Centuries", "left_value": "3", "right_value": "2"},
        ],
    })
    result = script_writer.generate_card_copy("Head-to-Head", {"title": "Comparison"})
    assert result["metrics"] == ["Runs", "Average", "Centuries"]
    assert result["left"]["name"] == "Player One"
    assert result["left"]["values"]["Runs"] == "1,020"
    assert result["right"]["values"]["Centuries"] == "2"


def test_generate_card_copy_rejects_text_subject_cutout():
    with pytest.raises(ValueError, match="existing shared editor"):
        script_writer.generate_card_copy("Text Subject Cutout", {}, "english")


def test_generate_telugu_card_copy_uses_telugu_script_and_ascii_digits(monkeypatch):
    captured = {}

    def fake_request(model, prompt, story, **kwargs):
        captured["prompt"] = prompt
        return {
            "eyebrow": "రికార్డు",
            "value": "౧౨౩",
            "label": "పరుగులు",
            "context": "మ్యాచ్‌లో సాధించిన స్కోరు",
        }

    monkeypatch.setattr(script_writer, "_request", fake_request)
    result = script_writer.generate_card_copy(
        "Key Fact / Milestone",
        {"title": "Gill scores 123 runs"},
        target_language="telugu",
    )
    assert result["language"] == "telugu"
    assert result["value"] == "123"
    assert "Telugu" in captured["prompt"]
