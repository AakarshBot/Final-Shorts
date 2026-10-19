import pytest
from longform_script_writer import LongformScriptWriter


def sample_longform_story():
    return {
        "title": "BCCI Names Bumrah Captain After Rohit Sidelined In Mumbai",
        "url": "https://example.com/bumrah-captain",
        "publisher": "ESPNcricinfo",
        "published_at": "2026-10-12T10:00:00Z",
        "summary": "Rohit Sharma suffers knee swelling during training, elevating Jasprit Bumrah to captaincy.",
        "depth_signals": ["selection", "captaincy", "injury"],
        "reports": [
            {"title": "BCCI Medical Update", "url": "https://example.com/bcci-update", "publisher": "BCCI"},
        ],
    }


def sample_raw_llm_script():
    acts = []
    scene_idx = 1
    for act_num in range(1, 7):
        scenes = []
        for s in range(1, 4):
            scenes.append({
                "scene_number": scene_idx,
                "voiceover": f"Act {act_num} Scene {s} narration providing documentary depth and cricket analysis with verified evidence.",
                "primary_entity": "Jasprit Bumrah" if s % 2 == 0 else "Rohit Sharma",
                "secondary_entity": "BCCI",
                "visual_intent": "match_action" if s == 1 else "press_conference",
                "visual_type": "card" if s == 2 else "photo_kenburns",
                "card_type": "Stat Highlight" if s == 2 else "none",
                "card_required_subject": "Jasprit Bumrah",
                "card_payload": {"hero_stat": "15.8", "stat_label": "4th Innings Average"},
                "search_query": "Jasprit Bumrah bowling action Test match",
            })
            scene_idx += 1
        acts.append({
            "act_number": act_num,
            "chapter_title": f"Chapter {act_num}: The Pivotal Decision",
            "act_thesis": f"Thesis for act {act_num}",
            "scenes": scenes,
        })

    return {
        "title": "Inside India's Captaincy Transition: Why Bumrah Was The Only Choice",
        "titles": [
            "Inside India's Captaincy Transition: Why Bumrah Was The Only Choice",
            "How Rohit's Injury Reshaped India's Leadership Group",
            "Bumrah Takes Charge: The Inside Story Of The Mumbai Decision",
        ],
        "subject_name": "Jasprit Bumrah",
        "core_conflict": "Knee injury forces abrupt captaincy handover before must-win Test match.",
        "seo_description": "An investigative breakdown into the BCCI's leadership transition in Mumbai.",
        "hashtags": ["#Cricket", "#JaspritBumrah", "#RohitSharma", "#Documentary"],
        "pinned_comment": "Can Bumrah successfully lead India to victory in Mumbai? Let us know below.",
        "acts": acts,
    }


def test_validate_and_format_computes_chapters_and_scenes():
    story = sample_longform_story()
    raw = sample_raw_llm_script()

    formatted = LongformScriptWriter.validate_and_format(raw, story)

    assert formatted["title"].startswith("Inside India")
    assert len(formatted["chapters"]) == 6
    assert formatted["chapters"][0]["timestamp"] == "00:00"
    assert len(formatted["scenes"]) == 18
    assert formatted["total_words"] > 100
    assert formatted["estimated_duration_seconds"] > 50.0
    assert "CHAPTERS:" in formatted["seo_description"]


def test_longform_scriptwriter_calls_groq(monkeypatch):
    story = sample_longform_story()
    monkeypatch.setattr("longform_script_writer._research_longform_story", lambda s: "MOCK EVIDENCE PACKET")
    monkeypatch.setattr("longform_script_writer._request_groq", lambda p, u: sample_raw_llm_script())

    res = LongformScriptWriter.write(story)
    assert res["subject_name"] == "Jasprit Bumrah"
    assert len(res["acts"]) == 6
    assert len(res["scenes"]) == 18

def test_format_normalizes_act_and_scene_ids_and_entity_fallback():
    story = sample_longform_story()
    raw = sample_raw_llm_script()
    raw["acts"][0]["act_number"] = 6
    raw["acts"][1]["act_number"] = 6
    raw["acts"][0]["scenes"][0]["scene_number"] = 18
    raw["acts"][0]["scenes"][0].pop("primary_entity")
    raw["acts"][0]["scenes"][0].pop("search_query")

    formatted = LongformScriptWriter.validate_and_format(raw, story)

    assert [act["act_number"] for act in formatted["acts"]] == [1, 2, 3, 4, 5, 6]
    assert [scene["scene_number"] for scene in formatted["scenes"]] == list(range(1, 19))
    assert [scene["scene_number"] for act in formatted["acts"] for scene in act["scenes"]] == list(range(1, 19))
    assert formatted["scenes"][0]["chapter_title"] == formatted["chapters"][0]["title"]
    assert formatted["scenes"][0]["primary_entity"] == story["title"]
    assert formatted["scenes"][0]["search_query"] == f'{story["title"]} cricket'
    assert all("None cricket" not in scene["search_query"] for scene in formatted["scenes"])


def test_description_only_claims_publishers_present_in_story_handoff():
    raw = sample_raw_llm_script()
    story = {"title": "Cricket leadership change", "publisher": "", "reports": []}

    formatted = LongformScriptWriter.validate_and_format(raw, story)

    assert "CHAPTERS:" in formatted["seo_description"]
    assert "Sources:" not in formatted["seo_description"]
    assert "verified wire reports" not in formatted["seo_description"].casefold()
