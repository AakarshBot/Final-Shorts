from script_writer import apply_script_edits, write_script


def valid_result(scene1="Gill suffers a fresh injury scare before India’s ODI."):
    return {
        "titles": [
            "Gill injury scare before ODI",
            "India captain hit in nets",
            "Gill fitness update",
        ],
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


def test_approved_edits_preserve_titles_and_mark_audio_handoff():
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



def test_scriptwriter_preserves_audio_language_handoff(monkeypatch):
    def fake_request(model, prompt, story):
        return valid_result()

    monkeypatch.setattr("script_writer._request", fake_request)
    result = write_script(
        {"title": "Gill injury scare", "description": "Shubman Gill was hit in training."},
        language="hindi",
    )
    assert result["language_used"] == "hindi"


def _approved_audio_script(language="english"):
    return {
        "approved_for_audio": True,
        "language_used": language,
        "script": [
            {"voiceover": "India won."},
            {"voiceover": "Bowlers held."},
        ],
    }


def test_audio_requires_approved_script():
    from audio import generate_audio
    import pytest

    with pytest.raises(ValueError, match="approved Scriptwriter handoff"):
        generate_audio({"script": [{"voiceover": "Hello world."}]})


def test_audio_uses_edge_word_boundaries(monkeypatch, tmp_path):
    import audio

    class FakeCommunicate:
        def __init__(self, *args, **kwargs):
            assert kwargs["boundary"] == "WordBoundary"
            assert args[1] == audio.VOICES["english"]

        async def stream(self):
            yield {"type": "audio", "data": b"x" * 700}
            yield {"type": "WordBoundary", "text": "India", "offset": 0, "duration": 3000000}
            yield {"type": "WordBoundary", "text": "won", "offset": 3000000, "duration": 3000000}

    monkeypatch.setattr(audio.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(audio, "_probe_duration", lambda path: 1.0)
    result = audio.generate_audio(_approved_audio_script(), tmp_path)

    assert result["total_duration"] == 2.0
    assert result["scenes"][0]["timings"][0]["word"] == "India"


def test_audio_cache_avoids_second_tts_call(monkeypatch, tmp_path):
    import audio

    calls = []

    class FakeCommunicate:
        def __init__(self, *args, **kwargs):
            calls.append(1)

        async def stream(self):
            yield {"type": "audio", "data": b"x" * 700}
            yield {"type": "WordBoundary", "text": "India", "offset": 0, "duration": 3000000}
            yield {"type": "WordBoundary", "text": "won", "offset": 3000000, "duration": 3000000}

    monkeypatch.setattr(audio.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(audio, "_probe_duration", lambda path: 1.0)
    audio.CACHE_DIR = tmp_path / "cache"
    out = tmp_path / "out"

    audio.generate_audio(_approved_audio_script(), out)
    audio.generate_audio(_approved_audio_script(), out)

    assert len(calls) == 2


def test_audio_retries_transient_failure_once(monkeypatch, tmp_path):
    import audio

    attempts = []

    class FakeCommunicate:
        def __init__(self, *args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise ConnectionError("connection reset")

        async def stream(self):
            yield {"type": "audio", "data": b"x" * 700}
            yield {"type": "WordBoundary", "text": "India", "offset": 0, "duration": 3000000}
            yield {"type": "WordBoundary", "text": "won", "offset": 3000000, "duration": 3000000}

    monkeypatch.setattr(audio.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(audio, "_probe_duration", lambda path: 1.0)
    result = audio.generate_audio(_approved_audio_script(), tmp_path)

    assert result["total_duration"] == 2.0
    assert len(attempts) == 3


def test_audio_speed_correction_runs_once_when_over_limit(monkeypatch, tmp_path):
    import audio

    rates = []

    async def fake_generate(script, language, rate_percent, output_dir):
        rates.append(rate_percent)
        duration = 31.0 if len(rates) == 1 else 25.0
        return [
            {
                "scene": 1,
                "path": str(tmp_path / "voiceover_1.mp3"),
                "duration": duration / 2,
                "timings": [{"word": "India", "start": 0.0, "end": 0.5}],
                "from_cache": False,
            },
            {
                "scene": 2,
                "path": str(tmp_path / "voiceover_2.mp3"),
                "duration": duration / 2,
                "timings": [{"word": "won", "start": 0.5, "end": 1.0}],
                "from_cache": False,
            },
        ]

    monkeypatch.setattr(audio, "_generate_at_rate", fake_generate)
    result = audio.generate_audio(_approved_audio_script(), tmp_path)

    assert result["duration_corrected"] is True
    assert rates[0] == 8.0
    assert rates[1] > rates[0]
    assert result["total_duration"] == 25.0


def test_audio_approval_creates_visual_handoff(tmp_path):
    from audio import approve_audio

    first = tmp_path / "voiceover_1.mp3"
    second = tmp_path / "voiceover_2.mp3"
    first.write_bytes(b"x" * 700)
    second.write_bytes(b"x" * 700)
    result = approve_audio(
        {
            "scenes": [
                {"scene": 1, "path": str(first), "duration": 1.0, "timings": []},
                {"scene": 2, "path": str(second), "duration": 1.0, "timings": []},
            ],
            "total_duration": 2.0,
        }
    )
    assert result["approved_for_visuals"] is True
