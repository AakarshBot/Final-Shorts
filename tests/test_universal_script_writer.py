import pytest

import universal_script_writer as writer


def valid_result(scene_count=4):
    if scene_count == 3:
        voiceovers = [
            "Carlos Alcaraz wins a dramatic Tokyo final against a tough opponent.",
            "He recovered from a slow start, changed the momentum, and finished the final with a strong closing stretch.",
            "The confirmed victory adds another major result to Alcaraz's season and gives him the Tokyo championship for this tournament campaign again.",
        ]
    elif scene_count == 4:
        voiceovers = [
            "Carlos Alcaraz wins a dramatic Tokyo final against a tough opponent.",
            "He recovered from a slow start and controlled the decisive stages of the final.",
            "The comeback changed the match, with Alcaraz producing the key points when they mattered most.",
            "The confirmed victory gives Alcaraz the Tokyo championship and strengthens an important part of his season.",
        ]
    elif scene_count == 5:
        voiceovers = [
            "Carlos Alcaraz wins a dramatic Tokyo final against a tough opponent.",
            "He recovered from the opening setback and regained control in the final.",
            "The key turning point came when Alcaraz changed the momentum.",
            "That comeback produced a decisive result in Tokyo.",
            "The confirmed victory gives Alcaraz the tournament title this season.",
        ]
    else:
        voiceovers = ["Carlos Alcaraz wins Tokyo."] * scene_count

    scenes = [
        {
            "voiceover": voiceovers[index],
            "narrative_role": "development",
            "primary_entity": "Carlos Alcaraz",
            "visual_intent": "Carlos Alcaraz tennis action",
            "specific_search_prompt": "Carlos Alcaraz Tokyo tennis final",
            "sport_or_topic_category": "Tennis",
        }
        for index in range(scene_count)
    ]

    return {
        "subject_name": "Carlos Alcaraz",
        "narrative_structure": "result-led",
        "headline": "Alcaraz Wins Tokyo",
        "titles": [
            "Carlos Alcaraz Wins Tokyo Title",
            "Why Alcaraz's Tokyo Win Matters",
            "How Alcaraz Turned Tokyo Around",
        ],
        "seo_description": "Carlos Alcaraz won the Tokyo final after a comeback, sealing the latest major result in his season.",
        "hashtags": ["#CarlosAlcaraz", "#Tennis", "#Tokyo"],
        "comment": "What stood out most about Alcaraz's Tokyo win?",
        "quote": "We fought for every point.",
        "quote_attribution": "Carlos Alcaraz",
        "quote_slide": min(4, scene_count),
        "script": scenes,
    }


def test_angle_schema_requires_exactly_three_options():
    assert writer.ANGLE_SCHEMA["properties"]["angles"]["minItems"] == 3
    assert writer.ANGLE_SCHEMA["properties"]["angles"]["maxItems"] == 3


def test_suggest_universal_story_angles_preserves_search_query(monkeypatch):
    calls = []

    monkeypatch.setattr(
        writer,
        "_research_story",
        lambda story: "FULL STORY",
    )

    def fake_request(model, prompt, source, **kwargs):
        calls.append((prompt, source, kwargs))
        return {
            "angles": [
                {"title": "What He Said", "description": "Focus on the statement.", "evidence_basis": "Direct quote in research."},
                {"title": "How He Won", "description": "Focus on the final.", "evidence_basis": "Final report in research."},
                {"title": "Why It Matters", "description": "Focus on significance.", "evidence_basis": "Season context in research."},
            ]
        }

    monkeypatch.setattr(writer, "_request", fake_request)
    result = writer.suggest_universal_story_angles(
        {"title": "Carlos Alcaraz wins Tokyo"},
        language="english",
        search_query="Carlos Alcaraz speech after Tokyo Open",
    )

    assert "PRIMARY YOUTUBE SEARCH QUERY" in calls[0][0]
    assert "Carlos Alcaraz speech after Tokyo Open" in calls[0][0]
    assert result["search_query"] == "Carlos Alcaraz speech after Tokyo Open"


def test_suggest_universal_story_angles_reads_research_once(monkeypatch):
    calls = []

    monkeypatch.setattr(
        writer,
        "_research_story",
        lambda story: "FULL STORY WITH POST-MATCH QUOTE",
    )

    def fake_request(model, prompt, source, **kwargs):
        calls.append((model, prompt, source, kwargs))
        return {
            "angles": [
                {
                    "title": "What Alcaraz Said",
                    "description": "Focus on his post-match comments and what they revealed.",
                    "evidence_basis": "The research contains his direct post-match statement.",
                },
                {
                    "title": "How He Won",
                    "description": "Focus on the decisive moments of the Tokyo final.",
                    "evidence_basis": "The research documents the final's turning points.",
                },
                {
                    "title": "Why Tokyo Matters",
                    "description": "Focus on the significance of the title for his season.",
                    "evidence_basis": "The research confirms the title and current season context.",
                },
            ]
        }

    monkeypatch.setattr(writer, "_request", fake_request)
    result = writer.suggest_universal_story_angles(
        {"title": "Carlos Alcaraz wins Tokyo"},
        language="english",
    )

    assert len(calls) == 1
    assert calls[0][2] == "FULL STORY WITH POST-MATCH QUOTE"
    assert calls[0][3]["schema"] is writer.ANGLE_SCHEMA
    assert [item["title"] for item in result["angles"]] == [
        "What Alcaraz Said",
        "How He Won",
        "Why Tokyo Matters",
    ]
    assert result["source_evidence"] == "FULL STORY WITH POST-MATCH QUOTE"


def test_writer_honors_search_query_for_packaging(monkeypatch):
    calls = []

    monkeypatch.setattr(
        writer,
        "_research_story",
        lambda story: "FULL STORY",
    )

    def fake_request(model, prompt, source):
        calls.append(prompt)
        return valid_result()

    monkeypatch.setattr(writer, "_request", fake_request)
    result = writer.write_universal_script(
        {"title": "Carlos Alcaraz wins Tokyo"},
        search_query="Carlos Alcaraz speech after Tokyo Open",
    )

    assert "PRIMARY YOUTUBE SEARCH QUERY" in calls[0]
    assert "Carlos Alcaraz speech after Tokyo Open" in calls[0]
    assert result["search_query"] == "Carlos Alcaraz speech after Tokyo Open"


def test_writer_honors_selected_editorial_angle(monkeypatch):
    calls = []

    monkeypatch.setattr(
        writer,
        "_research_story",
        lambda story: "FULL STORY WITH POST-MATCH QUOTE",
    )

    def fake_request(model, prompt, source):
        calls.append((model, prompt, source))
        return valid_result()

    monkeypatch.setattr(writer, "_request", fake_request)
    angle = "What Alcaraz Said: Focus on his post-match comments and what they revealed."
    result = writer.write_universal_script(
        {"title": "Carlos Alcaraz wins Tokyo"},
        angle=angle,
    )

    assert len(calls) == 1
    assert "SELECTED EDITORIAL ANGLE (AUTHORITATIVE)" in calls[0][1]
    assert angle in calls[0][1]
    assert result["story_angle"] == angle


def test_schema_allows_three_to_five_slides():
    schema = writer.SCHEMA["properties"]["script"]
    assert schema["minItems"] == 3
    assert schema["maxItems"] == 5
    assert writer.SCHEMA["properties"]["quote_slide"]["maximum"] == 5


def test_prompt_contains_universal_hard_rules():
    prompt = writer.SYSTEM_PROMPT
    assert "3, 4 or 5 spoken slides" in prompt
    assert "Never return only 1 or 2 slides" in prompt
    assert "fewer than 14 words" in prompt
    assert "at least 18 seconds" in prompt
    assert "strictly under 30 seconds" in prompt
    assert "Read the entire research packet" in prompt
    assert "Do not mechanically summarize the article" in prompt
    assert "article-order" in prompt
    assert "story-dependent" in prompt




def test_schema_requires_story_specific_narrative_structure():
    assert "narrative_structure" in writer.SCHEMA["properties"]
    assert "narrative_structure" in writer.SCHEMA["required"]


def test_validator_requires_narrative_structure():
    result = valid_result()
    result["narrative_structure"] = ""
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "narrative structure" in reason.casefold()


def test_writer_preserves_selected_angle_and_structure(monkeypatch):
    monkeypatch.setattr(writer, "_research_story", lambda story: "FULL STORY")
    monkeypatch.setattr(writer, "_request", lambda *args, **kwargs: valid_result())
    angle = "What Alcaraz Said: Focus on his post-match comments."
    result = writer.write_universal_script({"title": "Carlos Alcaraz wins Tokyo"}, angle=angle)
    assert result["story_angle"] == angle
    assert result["narrative_structure"] == "result-led"


def test_validator_accepts_three_four_and_five_slides():
    for count in (3, 4, 5):
        result = valid_result(scene_count=count)
        valid, reason = writer.validate_universal_script(result)
        assert valid, reason


def test_validator_rejects_two_slides():
    result = valid_result(scene_count=2)
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "3–5" in reason


def test_validator_rejects_slide_one_at_14_words():
    result = valid_result()
    result["script"][0]["voiceover"] = (
        "Carlos Alcaraz wins the dramatic Tokyo final against a very tough opponent right now"
    )
    assert writer._words(result["script"][0]["voiceover"]) == 14
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "Slide 1" in reason


def test_validator_enforces_eighteen_second_word_floor():
    result = valid_result()
    result["script"] = [
        {
            **result["script"][0],
            "voiceover": "Carlos Alcaraz wins Tokyo.",
        },
        {
            **result["script"][1],
            "voiceover": "He completed the comeback in the final.",
        },
        {
            **result["script"][2],
            "voiceover": "The result gives him another major season win.",
        },
    ]
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "18-second" in reason


def test_validator_enforces_under_thirty_second_word_ceiling():
    result = valid_result(scene_count=5)
    long_voiceover = (
        "Carlos Alcaraz delivered another important result after controlling the final, "
        "creating a significant moment for his season and adding more pressure around his next event. "
        "The confirmed score and opponent make the result especially notable for the tournament."
    )
    result["script"][0]["voiceover"] = "Carlos Alcaraz wins Tokyo after a dramatic final."
    result["script"][1]["voiceover"] = long_voiceover
    result["script"][2]["voiceover"] = long_voiceover
    result["script"][3]["voiceover"] = long_voiceover
    result["script"][4]["voiceover"] = long_voiceover
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "under 30 seconds" in reason


@pytest.mark.parametrize(
    "phrase",
    [
        "wait till the end",
        "watch until the end",
        "don't scroll",
        "stay tuned",
        "you won't believe this",
        "here is the latest",
    ],
)
def test_validator_rejects_filler_and_retention_bait(phrase):
    result = valid_result()
    result["script"][2]["voiceover"] = (
        f"Carlos Alcaraz {phrase} after the Tokyo final."
    )
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "filler" in reason or "retention" in reason


def test_validator_requires_subject_name_in_narration():
    result = valid_result()
    for scene in result["script"]:
        scene["voiceover"] = scene["voiceover"].replace("Carlos Alcaraz", "the legend").replace(
            "Alcaraz", "the legend"
        )
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "subject" in reason.casefold()


def test_validator_requires_metadata_and_visual_handoff():
    result = valid_result()
    result["titles"] = ["Only one title"]
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "3 titles" in reason

    result = valid_result()
    result["script"][0]["specific_search_prompt"] = ""
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "specific_search_prompt" in reason


def test_validator_rejects_bad_quote_handoff():
    result = valid_result()
    result["quote_slide"] = 0
    valid, reason = writer.validate_universal_script(result)
    assert not valid
    assert "quote" in reason.casefold()


def test_apply_edits_preserves_metadata_and_approval():
    result = valid_result()
    edited = writer.apply_universal_script_edits(
        result,
        [scene["voiceover"] for scene in result["script"]],
        headline=result["headline"],
    )
    assert edited["quote"] == result["quote"]
    assert edited["quote_attribution"] == result["quote_attribution"]
    assert edited["quote_slide"] == 4
    assert edited["approved_for_audio"] is True


def test_writer_uses_one_model_when_first_draft_is_valid(monkeypatch):
    calls = []

    monkeypatch.setattr(
        writer,
        "_research_story",
        lambda story: "FULL STORY",
    )

    def fake_request(model, prompt, source):
        calls.append((model, prompt, source))
        return valid_result()

    monkeypatch.setattr(writer, "_request", fake_request)
    result = writer.write_universal_script({"title": "Carlos Alcaraz wins Tokyo"})

    assert len(calls) == 1
    assert calls[0][0] == writer.MODELS[0]
    assert result["delivery_profile"] == "UNIVERSAL SPORTS"


def test_writer_hides_invalid_draft_and_rewrites_once(monkeypatch):
    calls = []
    monkeypatch.setattr(writer, "_research_story", lambda story: "FULL STORY")
    bad = valid_result()
    bad["script"][1]["voiceover"] = (
        "Wait till the end. Alcaraz recovered from the opening setback and controlled "
        "the final with a decisive response in Tokyo."
    )
    good = valid_result()

    def fake_request(model, prompt, source):
        calls.append((model, prompt))
        return bad if len(calls) == 1 else good

    monkeypatch.setattr(writer, "_request", fake_request)
    result = writer.write_universal_script({"title": "Carlos Alcaraz wins Tokyo"})

    assert len(calls) == 2
    assert calls[0][0] == writer.MODELS[0]
    assert calls[1][0] == writer.MODELS[1]
    assert "RECOVERY" in calls[1][1]
    assert "filler" in calls[1][1].casefold() or "retention" in calls[1][1].casefold()
    assert result["provider_used"] == writer.MODELS[1]


def test_research_reads_primary_and_related_reports(monkeypatch):
    monkeypatch.setattr(
        writer,
        "_extract_article",
        lambda url: (
            "Primary article facts " * 200 if "primary" in url else "Related article facts " * 120,
            url,
        ),
    )
    monkeypatch.setattr(
        writer,
        "_related_article_urls",
        lambda *args, **kwargs: [
            ("Related report", "https://example.com/related"),
        ],
    )

    packet = writer._research_story(
        {
            "title": "Carlos Alcaraz wins Tokyo",
            "description": "A tennis final update.",
            "url": "https://example.com/primary",
        }
    )

    assert "[PRIMARY ARTICLE" in packet
    assert "[RELATED REPORT 1" in packet
    assert "Related article facts" in packet
