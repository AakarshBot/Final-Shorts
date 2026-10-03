import pytest

from audio import approve_audio, approve_top5_audio, generate_audio, generate_top5_audio


def approved_script(language="english"):
    return {
        "approved_for_audio": True,
        "language_used": language,
        "script": [
            {"voiceover": "India won."},
            {"voiceover": "Bowlers held."},
        ],
    }


def approved_top5_script():
    return {
        "schema": "final-shorts.top5-script.v1",
        "slides": [
            {
                "slide_number": index,
                "story_index": index - 1,
                "headline": f"Story {index} headline contains the approved spoken development",
                "body": f"Visual-only body for story {index} must never be narrated.",
            }
            for index in range(1, 7)
        ],
        "hashtags": ["#Cricket", "#Top5", "#Shorts"],
    }


def test_audio_requires_approved_script():
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
    result = generate_audio(approved_script(), tmp_path)

    assert result["total_duration"] == 2.0
    assert result["scenes"][0]["timings"][0]["word"] == "India"


def test_top5_audio_uses_six_spoken_headlines_only(monkeypatch, tmp_path):
    import audio

    captured = []

    async def fake_generate(scenes, language, rate_percent, output_dir):
        captured.append(scenes)
        return [
            {
                "scene": index,
                "path": str(tmp_path / f"voiceover_{index}.mp3"),
                "duration": 2.0,
                "timings": [{"word": "Story", "start": 0.0, "end": 0.5}],
                "from_cache": False,
            }
            for index in range(1, 7)
        ]

    monkeypatch.setattr(audio, "_generate_at_rate", fake_generate)
    result = generate_top5_audio(approved_top5_script(), tmp_path)

    assert len(captured) == 1
    assert len(captured[0]) == 6
    assert [scene["voiceover"] for scene in captured[0]] == [
        slide["headline"] for slide in approved_top5_script()["slides"]
    ]
    assert all("Visual-only body" not in scene["voiceover"] for scene in captured[0])
    assert result["schema"] == "final-shorts.top5-audio.v1"
    assert result["total_duration"] == 12.0


def test_top5_audio_corrects_total_duration(monkeypatch, tmp_path):
    import audio

    rates = []

    async def fake_generate(scenes, language, rate_percent, output_dir):
        rates.append(rate_percent)
        total = 31.0 if len(rates) == 1 else 24.0
        duration = total / 6
        return [
            {
                "scene": index,
                "path": str(tmp_path / f"voiceover_{index}.mp3"),
                "duration": duration,
                "timings": [{"word": "Story", "start": 0.0, "end": 0.5}],
                "from_cache": False,
            }
            for index in range(1, 7)
        ]

    monkeypatch.setattr(audio, "_generate_at_rate", fake_generate)
    result = generate_top5_audio(approved_top5_script(), tmp_path)

    assert result["duration_corrected"] is True
    assert len(rates) == 2
    assert rates[1] > rates[0]
    assert result["total_duration"] == 24.0


def test_top5_audio_requires_exactly_six_slides(monkeypatch, tmp_path):
    script = approved_top5_script()
    script["slides"] = script["slides"][:5]
    with pytest.raises(ValueError, match="exactly six spoken slides"):
        generate_top5_audio(script, tmp_path)


def test_top5_audio_approval_requires_six_valid_scenes(tmp_path):
    scenes = []
    for index in range(1, 7):
        path = tmp_path / f"voiceover_{index}.mp3"
        path.write_bytes(b"x" * 700)
        scenes.append(
            {"scene": index, "path": str(path), "duration": 2.0, "timings": []}
        )

    result = approve_top5_audio(
        {
            "schema": "final-shorts.top5-audio.v1",
            "scenes": scenes,
            "total_duration": 12.0,
        }
    )

    assert result["approved_for_visuals"] is True


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
    monkeypatch.setattr(audio, "CACHE_DIR", tmp_path / "cache")
    out = tmp_path / "out"

    first = generate_audio(approved_script(), out)
    second = generate_audio(approved_script(), out)

    assert first["scenes"][0]["from_cache"] is False
    assert second["scenes"][0]["from_cache"] is True
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
    monkeypatch.setattr(audio, "CACHE_DIR", tmp_path / "cache")
    result = generate_audio(approved_script(), tmp_path)

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
    result = generate_audio(approved_script(), tmp_path)

    assert result["duration_corrected"] is True
    assert rates[0] == 8.0
    assert rates[1] > rates[0]
    assert result["total_duration"] == 25.0


def test_audio_approval_creates_visual_handoff(tmp_path):
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
