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


def test_generation_prompts_cover_validator_requirements():
    cricket = script_writer.SYSTEM_PROMPT
    universal = script_writer.UNIVERSAL_SYSTEM_PROMPT
    top5 = script_writer.TOP5_SYSTEM_PROMPT

    assert "Each slide must include non-empty primary_entity, visual_intent, specific_search_prompt, and sport_or_topic_category" in cricket
    assert "a non-empty 3–4-word opening headline" in cricket
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
    assert "3 or 4 words" in reason


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


