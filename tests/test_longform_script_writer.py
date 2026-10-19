import pytest
from longform_script_writer import LONGFORM_SYSTEM_PROMPT, LongformScriptWriter


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


def test_prompt_does_not_request_unimplemented_footage():
    assert '"ncr_broll"' not in LONGFORM_SYSTEM_PROMPT
    assert "never request or imply match clips" in LONGFORM_SYSTEM_PROMPT.casefold()


def test_longform_research_fetches_sources_concurrently_and_deduplicates_urls(monkeypatch):
    import threading
    import time

    import longform_script_writer as writer

    story = {
        "title": "Research concurrency regression",
        "url": "https://example.com/primary-story",
        "summary": "Discovery summary.",
        "reports": [
            {"url": "https://example.com/primary-story?utm_source=news#article"},
            {"url": "https://example.com/report-one"},
            {"url": "https://example.com/report-two"},
            {"url": "https://example.com/report-three"},
        ],
    }

    lock = threading.Lock()
    active = 0
    peak_active = 0
    fetched_urls = []

    def fake_extract(url):
        nonlocal active, peak_active
        with lock:
            active += 1
            peak_active = max(peak_active, active)
            fetched_urls.append(url)
        time.sleep(0.04)
        with lock:
            active -= 1
        return f"Evidence captured from {url}"

    class FakeDDGS:
        def __init__(self, timeout):
            assert timeout == 5

        def text(self, query, max_results):
            return [{"title": "Supporting report", "body": "Search context."}]

    monkeypatch.setattr(writer, "_extract_article_text", fake_extract)
    monkeypatch.setattr(writer, "DDGS", FakeDDGS)

    packet = writer._research_longform_story(story)

    assert peak_active >= 2
    assert len(fetched_urls) == 4
    assert len(set(fetched_urls)) == 4
    assert packet.index("[PRIMARY SOURCE") < packet.index("[RELATED REPORT 1")
    assert packet.index("[RELATED REPORT 1") < packet.index("[RELATED REPORT 2")
    assert "BACKGROUND CONTEXT & SEARCH SNIPPETS" in packet
    assert "Search context." in packet


def test_format_rejects_missing_narrative_acts_early():
    raw = sample_raw_llm_script()
    raw["acts"].pop()
    with pytest.raises(ValueError, match="exactly six acts"):
        LongformScriptWriter.validate_and_format(raw, sample_longform_story())


def test_format_rejects_empty_voiceover_before_audio_or_visuals():
    raw = sample_raw_llm_script()
    raw["acts"][2]["scenes"][1]["voiceover"] = "   "
    with pytest.raises(ValueError, match="has no voiceover narration"):
        LongformScriptWriter.validate_and_format(raw, sample_longform_story())


def test_groq_400_falls_back_immediately_without_repeating_same_model(monkeypatch):
    import json as json_module
    import requests

    import longform_script_writer as writer

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    requested_models = []

    class FakeResponse:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self.text = body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(
                    f"HTTP {self.status_code}",
                    response=self,
                )

        def json(self):
            return {"choices": [{"message": {"content": json_module.dumps({"ok": True})}}]}

    def fake_post(_url, headers, json, timeout):
        requested_models.append(json["model"])
        if len(requested_models) == 1:
            return FakeResponse(400, '{"error":"invalid response format"}')
        return FakeResponse(200, '{"choices":[]}')

    monkeypatch.setattr(writer.requests, "post", fake_post)

    result = writer._request_groq("test system prompt", "test payload")

    assert result == {"ok": True}
    assert requested_models == [writer.MODELS[0], writer.MODELS[1]]


def test_groq_auth_error_fails_fast_without_retry(monkeypatch):
    import requests

    import longform_script_writer as writer

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    calls = []

    class FakeResponse:
        status_code = 401
        text = '{"error":"unauthorized"}'

        def raise_for_status(self):
            raise requests.HTTPError("HTTP 401", response=self)

    def fake_post(*_args, **_kwargs):
        calls.append(1)
        return FakeResponse()

    monkeypatch.setattr(writer.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        writer._request_groq("test system prompt", "test payload")

    assert len(calls) == 1
