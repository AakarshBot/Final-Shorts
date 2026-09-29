import json

import niche_sports_script_writer as niche


def valid_result():
    return {
        "headline": "Alcaraz Wins Tokyo",
        "titles": [
            "Carlos Alcaraz wins Tokyo title",
            "Alcaraz seals Tokyo crown after comeback",
            "Carlos Alcaraz overturns deficit in Tokyo final",
        ],
        "seo_description": "Carlos Alcaraz wins the Tokyo final after a comeback, securing the tournament title in a dramatic finish.",
        "hashtags": ["#CarlosAlcaraz", "#Tennis", "#Tokyo"],
        "comment": "Was Alcaraz's Tokyo comeback the biggest moment of the tournament?",
        "script": [
            {
                "voiceover": "Carlos Alcaraz has just won the Tokyo title.",
                "narrative_role": "hook",
                "primary_entity": "Carlos Alcaraz",
                "visual_intent": "Alcaraz celebrating after the final",
                "specific_search_prompt": "Carlos Alcaraz Tokyo final trophy celebration",
                "sport_or_topic_category": "tennis",
            },
            {
                "voiceover": "He came back after dropping the opening set.",
                "narrative_role": "development",
                "primary_entity": "Carlos Alcaraz",
                "visual_intent": "Alcaraz competing in the final",
                "specific_search_prompt": "Carlos Alcaraz Tokyo tennis final action",
                "sport_or_topic_category": "tennis",
            },
            {
                "voiceover": "The comeback turned the final in his favour.",
                "narrative_role": "context",
                "primary_entity": "Carlos Alcaraz",
                "visual_intent": "Alcaraz during the deciding stages",
                "specific_search_prompt": "Carlos Alcaraz Tokyo final match action",
                "sport_or_topic_category": "tennis",
            },
            {
                "voiceover": "The victory gives Alcaraz the Tokyo championship.",
                "narrative_role": "consequence",
                "primary_entity": "Carlos Alcaraz",
                "visual_intent": "Alcaraz holding the Tokyo trophy",
                "specific_search_prompt": "Carlos Alcaraz Tokyo trophy ceremony",
                "sport_or_topic_category": "tennis",
            },
        ],
    }


def test_niche_writer_uses_niche_prompt_and_profile(monkeypatch):
    story = {
        "title": "Carlos Alcaraz wins Tokyo title",
        "description": "Alcaraz completed a comeback in the final.",
        "url": "",
    }
    captured = {}

    monkeypatch.setattr(
        niche,
        "_research_story",
        lambda value: "[SELECTED STORY]\nCarlos Alcaraz wins Tokyo title\n\nAlcaraz completed a comeback in the final.",
    )

    def fake_request(model, prompt, source):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["source"] = source
        return valid_result()

    monkeypatch.setattr(niche, "_request", fake_request)

    result = niche.write_niche_sports_script(story)

    assert result["delivery_profile"] == "NICHE SPORTS"
    assert result["provider_used"] == niche.MODELS[0]
    assert "NICHE-SPORTS EDITORIAL STYLE" in captured["prompt"]
    assert "Never use cricket-specific framing" in captured["prompt"]
    assert "RACKET SPORTS" in captured["prompt"]
    assert "Carlos Alcaraz wins Tokyo title" in captured["source"]
    assert "3 seconds" in captured["prompt"] or "3-second" in captured["prompt"]


def test_niche_writer_retries_same_model_after_validation_failure(monkeypatch):
    story = {
        "title": "Carlos Alcaraz wins Tokyo title",
        "url": "",
    }
    calls = []

    monkeypatch.setattr(
        niche,
        "_research_story",
        lambda value: "[SELECTED STORY]\nCarlos Alcaraz wins Tokyo title\n\nFull evidence.",
    )

    bad = valid_result()
    bad["script"][0]["voiceover"] = "Welcome to the latest sports update."
    good = valid_result()

    def fake_request(model, prompt, source):
        calls.append((model, prompt))
        return bad if len(calls) == 1 else good

    monkeypatch.setattr(niche, "_request", fake_request)

    result = niche.write_niche_sports_script(story)

    assert result["delivery_profile"] == "NICHE SPORTS"
    assert calls[0][0] == niche.MODELS[0]
    assert calls[1][0] == niche.MODELS[1]
    assert "Validation failure:" in calls[1][1]
