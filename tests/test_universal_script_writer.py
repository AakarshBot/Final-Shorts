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
    assert "legend" in prompt
    assert "wait till the end" in prompt
    assert "Do not mechanically summarize the article" in prompt


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
