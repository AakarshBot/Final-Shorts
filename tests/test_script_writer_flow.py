import pytest
import script_writer as writer
from script_writer import ScriptWriter, evaluate_flow, _trim_slide_one_if_needed


def sample_script(scenes_text=None):
    if not scenes_text:
        scenes_text = [
            "Rohit Sharma has officially been ruled out of the Mumbai Test.",  # 11 words
            "The move follows knee swelling during training, forcing doctors to recommend immediate rest.",  # 12 words
            "With India trailing in the series, Jasprit Bumrah takes over captaincy for the must-win clash.",  # 16 words
            "Now, all eyes turn to Wankhede as the hosts fight to protect their historic streak.",  # 16 words
        ]
    return {
        "subject_name": "Rohit Sharma",
        "headline": "Sharma Out Mumbai",
        "titles": [
            "Rohit Sharma Ruled Out Of Mumbai Test",
            "Why Sharma's Injury Matters For India",
            "Inside Rohit Sharma's Mumbai Injury Shock",
        ],
        "seo_description": "Rohit Sharma has been ruled out of the Mumbai Test due to a knee injury.",
        "hashtags": ["#RohitSharma", "#Cricket", "#India"],
        "comment": "Can India win in Mumbai without Rohit Sharma?",
        "quote": "He will need complete rest.",
        "quote_attribution": "BCCI Medical Team",
        "quote_slide": 2,
        "script": [
            {
                "voiceover": text,
                "narrative_role": role,
                "primary_entity": "Rohit Sharma",
                "visual_intent": "action",
                "specific_search_prompt": "cricket action",
                "sport_or_topic_category": "Cricket",
            }
            for text, role in zip(
                scenes_text,
                ["lead", "cause", "stakes", "kicker"][:len(scenes_text)]
            )
        ],
    }


def test_evaluate_flow_measures_broadcast_flow():
    script = sample_script()
    flow = evaluate_flow(script)
    assert flow["flow_score"] >= 9.0
    assert flow["is_within_time"] is True
    assert flow["is_slide_one_compliant"] is True
    assert flow["slide_one_words"] == 11
    assert 50 <= flow["total_words"] <= 70
    assert flow["transitions_count"] >= 2


def test_smart_trim_slide_one_trims_fourteen_words():
    # 14 words starting with "Now,"
    vo_14 = "Now, Rohit Sharma has officially been ruled out of the Mumbai Test with injury."
    assert writer._words(vo_14) == 14
    trimmed = _trim_slide_one_if_needed(vo_14)
    assert writer._words(trimmed) == 13
    assert trimmed.startswith("Rohit Sharma")

    # 13 words remains untouched
    vo_13 = "Rohit Sharma has officially been ruled out of the Mumbai Test with injury."
    assert writer._words(vo_13) == 13
    assert _trim_slide_one_if_needed(vo_13) == vo_13


def test_scriptwriter_dispatches_to_cricket_desks(monkeypatch):
    calls = []
    monkeypatch.setattr(writer, "_research_story", lambda s: "EVIDENCE")

    def fake_request(model, instruction, source, **kwargs):
        calls.append((instruction, source))
        return sample_script()

    monkeypatch.setattr(writer, "_request", fake_request)

    # India/Asia Desk
    res_india = ScriptWriter.write(
        {"title": "Rohit injury"},
        profile="cricket_india_asia",
    )
    assert "SUBCONTINENTAL CRICKET DESK" in calls[-1][0]
    assert res_india["delivery_profile"] == "SUBCONTINENTAL CRICKET DESK"
    assert res_india["flow_metrics"]["flow_score"] >= 9.0

    # Global Cricket Desk
    res_global = ScriptWriter.write(
        {"title": "Ashes squad"},
        profile="cricket_global",
    )
    assert "INTERNATIONAL CRICKET CORRESPONDENT" in calls[-1][0]
    assert res_global["delivery_profile"] == "INTERNATIONAL CRICKET CORRESPONDENT"


def test_scriptwriter_dispatches_to_universal_and_otd(monkeypatch):
    calls = []
    monkeypatch.setattr(writer, "_research_story", lambda s: "EVIDENCE")

    def fake_request(model, instruction, source, **kwargs):
        calls.append((instruction, source))
        return sample_script()

    monkeypatch.setattr(writer, "_request", fake_request)

    # Niche Sports Desk
    res_niche = ScriptWriter.write(
        {"title": "Verstappen pole"},
        profile="niche_sports",
    )
    assert "HIGH-ENERGY MULTI-SPORT DESK" in calls[-1][0]

    # YouTube Trends Desk
    res_yt = ScriptWriter.write(
        {"title": "Virat Kohli record"},
        profile="youtube_trends",
        search_query="Virat Kohli century highlights",
    )
    assert "YOUTUBE SEARCH TRENDS DESK" in calls[-1][0]
    assert "Virat Kohli century highlights" in calls[-1][0]
    assert res_yt["delivery_profile"] == "YOUTUBE SEARCH TRENDS DESK"

    # On This Day Historical Desk
    res_otd = ScriptWriter.write(
        {"title": "Kapil Dev 175"},
        profile="otd",
    )
    assert "ON THIS DAY (HISTORICAL SPORTS MILESTONES)" in calls[-1][0]
    assert res_otd["delivery_profile"] == "ON THIS DAY HISTORICAL DESK"


def test_scriptwriter_top5_dispatch(monkeypatch):
    stories = [
        {"title": f"Story {i}", "url": f"https://example.com/{i}", "source": "Test", "article": f"Article {i}"}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(writer, "research_top5_stories", lambda s: ["Evidence"] * 5)
    monkeypatch.setattr(writer, "_request", lambda model, inst, ev: {
        "slides": [
            {
                "slide_number": 1,
                "story_index": 0,
                "headline": "Top 5 Cricket News Today",
                "body": "Daily roundup summary.",
                "primary_entity": "Cricket",
                "visual_intent": "montage",
                "specific_search_prompt": "cricket news",
                "sport_or_topic_category": "Cricket",
            }
        ] + [
            {
                "slide_number": i + 1,
                "story_index": i,
                "headline": f"Story headline {i} tells the whole fact cleanly",
                "body": f"Story visual body {i}.",
                "primary_entity": f"Player {i}",
                "visual_intent": "action",
                "specific_search_prompt": f"player {i}",
                "sport_or_topic_category": "Cricket",
            }
            for i in range(1, 6)
        ],
        "seo_description": "Top 5 description",
        "hashtags": ["#Cricket", "#Top5", "#Shorts"],
        "comment": "Top 5 comment",
    })

    res = ScriptWriter.write(stories, profile="top_5")
    assert res["delivery_profile"] == "TOP-5 CRICKET EDITOR"
    assert len(res["slides"]) == 6
