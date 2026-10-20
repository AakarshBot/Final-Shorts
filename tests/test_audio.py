import pytest
from pathlib import Path

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


def test_chatterbox_turbo_stack_imports_without_loading_weights():
    import torch
    import torchaudio
    from chatterbox.tts_turbo import ChatterboxTurboTTS

    assert torch is not None
    assert torchaudio is not None
    assert callable(ChatterboxTurboTTS.from_pretrained)


def test_chatterbox_reference_conditioning_failure_is_reported(monkeypatch, tmp_path):
    import audio

    class FakeChatterbox:
        def prepare_conditionals(self, reference_path, exaggeration=0.5):
            raise ValueError("invalid voice reference")

    reference = tmp_path / "audio_reference.wav"
    reference.write_bytes(b"not a real wav, deliberately rejected by fake model")
    monkeypatch.setattr(audio, "get_chatterbox_model", lambda: FakeChatterbox())

    with pytest.raises(RuntimeError, match="could not use the voice reference file"):
        audio.generate_chatterbox_audio(
            approved_script(),
            output_dir=tmp_path / "generated",
            reference=reference,
        )


def test_audio_defaults_to_chatterbox(monkeypatch, tmp_path):
    import audio

    calls = []

    def fake_chatterbox(script, **kwargs):
        calls.append((script, kwargs))
        return {"model": "Chatterbox-Turbo", "total_duration": 2.0}

    monkeypatch.setattr(audio, "generate_chatterbox_audio", fake_chatterbox)
    result = generate_audio(approved_script(), tmp_path)

    assert result["model"] == "Chatterbox-Turbo"
    assert calls[0][1]["output_dir"] == tmp_path
    assert calls[0][1]["run_number"] == 1


def test_top5_audio_defaults_to_chatterbox(monkeypatch, tmp_path):
    import audio

    calls = []

    def fake_chatterbox(script, **kwargs):
        calls.append((script, kwargs))
        return {"schema": "final-shorts.top5-audio.v1", "model": "Chatterbox-Turbo"}

    handoff = approved_top5_script()
    monkeypatch.setattr(audio, "generate_chatterbox_audio", fake_chatterbox)
    result = generate_top5_audio(handoff, tmp_path)

    assert result["schema"] == "final-shorts.top5-audio.v1"
    assert calls[0][0] is handoff
    assert calls[0][1]["output_dir"] == tmp_path


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
    result = generate_audio(approved_script(), tmp_path, engine="edge")

    assert result["total_duration"] == 2.0
    assert result["scenes"][0]["timings"][0]["word"] == "India"


@pytest.mark.parametrize(
    ("language", "first_duration", "should_fail"),
    [
        ("hindi", 5.21, True),
        ("telugu", 5.21, True),
        ("hindi", 5.2, False),
        ("telugu", 5.1, False),
        ("english", 8.0, False),
    ],
)
def test_audio_uses_measured_lead_duration_for_hindi_telugu(
    monkeypatch, tmp_path, language, first_duration, should_fail
):
    import audio

    async def fake_generate(scenes, requested_language, rate_percent, output_dir):
        return [
            {
                "scene": index,
                "path": str(tmp_path / f"voiceover_{index}.mp3"),
                "duration": first_duration if index == 1 else 1.0,
                "timings": [{"word": "sample", "start": 0.0, "end": 0.5}],
                "from_cache": False,
            }
            for index, _scene in enumerate(scenes, 1)
        ]

    monkeypatch.setattr(audio, "_generate_at_rate", fake_generate)
    script = approved_script(language)

    if should_fail:
        with pytest.raises(ValueError, match="first-slide audio.*no more than 5.2 seconds"):
            generate_audio(script, tmp_path, engine="edge")
    else:
        result = generate_audio(script, tmp_path, engine="edge")
        assert result["scenes"][0]["duration"] == first_duration


def test_audio_auto_corrects_hindi_lead_before_applying_the_hard_limit(monkeypatch, tmp_path):
    import audio

    rates = []

    async def fake_generate(scenes, requested_language, rate_percent, output_dir):
        rates.append(rate_percent)
        first_duration = 5.55 if len(rates) == 1 else 4.65
        return [
            {
                "scene": index,
                "path": str(tmp_path / f"voiceover_{index}.mp3"),
                "duration": first_duration if index == 1 else 1.0,
                "timings": [{"word": "sample", "start": 0.0, "end": 0.5}],
                "from_cache": False,
            }
            for index, _scene in enumerate(scenes, 1)
        ]

    monkeypatch.setattr(audio, "_generate_at_rate", fake_generate)
    result = generate_audio(approved_script("hindi"), tmp_path, engine="edge")

    assert result["duration_corrected"] is True
    assert len(rates) == 2
    assert rates[1] > rates[0]
    assert result["scenes"][0]["duration"] <= audio.FIRST_SCENE_MAX_DURATION_SECONDS
    assert result["total_duration"] < audio.MAX_DURATION_SECONDS


def test_audio_approval_cannot_bypass_hindi_lead_duration_limit(tmp_path):
    import audio

    first = tmp_path / "voiceover_1.mp3"
    second = tmp_path / "voiceover_2.mp3"
    first.write_bytes(b"x" * 700)
    second.write_bytes(b"x" * 700)

    with pytest.raises(ValueError, match="first-slide audio.*no more than 5.2 seconds"):
        approve_audio(
            {
                "language": "hindi",
                "scenes": [
                    {"scene": 1, "path": str(first), "duration": 5.21, "timings": []},
                    {"scene": 2, "path": str(second), "duration": 1.0, "timings": []},
                ],
                "total_duration": 6.21,
            }
        )


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
    result = generate_top5_audio(approved_top5_script(), tmp_path, engine="edge")

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
    result = generate_top5_audio(approved_top5_script(), tmp_path, engine="edge")

    assert result["duration_corrected"] is True
    assert len(rates) == 2
    assert rates[1] > rates[0]
    assert result["total_duration"] == 24.0


def test_top5_audio_requires_exactly_six_slides(monkeypatch, tmp_path):
    script = approved_top5_script()
    script["slides"] = script["slides"][:5]
    with pytest.raises(ValueError, match="exactly six spoken slides"):
        generate_top5_audio(script, tmp_path, engine="edge")


def test_top5_audio_approval_requires_six_valid_scenes_and_allows_one_long_line(tmp_path):
    scenes = []
    for index in range(1, 7):
        path = tmp_path / f"voiceover_{index}.mp3"
        path.write_bytes(b"x" * 700)
        scenes.append(
            {
                "scene": index,
                "path": str(path),
                "duration": 16.0 if index == 1 else 2.0,
                "timings": [],
            }
        )

    result = approve_top5_audio(
        {
            "schema": "final-shorts.top5-audio.v1",
            "scenes": scenes,
            "total_duration": 26.0,
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

    first = generate_audio(approved_script(), out, engine="edge")
    second = generate_audio(approved_script(), out, engine="edge")

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
    result = generate_audio(approved_script(), tmp_path, engine="edge")

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
    result = generate_audio(approved_script(), tmp_path, engine="edge")

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


def test_chatterbox_reuses_matching_audio_and_invalidates_changed_script(monkeypatch, tmp_path):
    import sys
    import types
    import torch
    import audio

    class FakeChatterbox:
        sr = 16000

        def __init__(self):
            self.generate_calls = []
            self.conditioning_calls = []

        def prepare_conditionals(self, reference_path, exaggeration=0.5):
            self.conditioning_calls.append(reference_path)

        def generate(self, text, temperature=0.8):
            self.generate_calls.append((text, temperature))
            return torch.ones((1, self.sr), dtype=torch.float32)

    model = FakeChatterbox()
    fake_torchaudio = types.SimpleNamespace(
        save=lambda path, waveform, sample_rate: Path(path).write_bytes(b"WAVE" + b"x" * 1200)
    )
    from pathlib import Path

    monkeypatch.setitem(sys.modules, "torchaudio", fake_torchaudio)
    monkeypatch.setattr(audio, "get_chatterbox_model", lambda: model)
    monkeypatch.setattr(audio, "AUDIO_REFERENCE", tmp_path / "missing-reference.wav")
    monkeypatch.setattr(audio, "_CHATTERBOX_CONDITIONALS_MODEL_ID", None)

    script = approved_script()
    output_dir = tmp_path / "chatterbox-output"
    first = audio.generate_chatterbox_audio(script, output_dir=output_dir)
    second = audio.generate_chatterbox_audio(script, output_dir=output_dir)

    assert all(not scene["from_cache"] for scene in first["scenes"])
    assert model.generate_calls[0][0] == audio._join_narration_texts([scene["voiceover"] for scene in script["script"]])
    assert model.generate_calls[0][1] == 0.80
    assert all(scene["continuous_master_path"] == first["full_path"] for scene in first["scenes"])
    assert all(scene["from_cache"] for scene in second["scenes"])
    assert len(model.generate_calls) == 1
    assert len(model.conditioning_calls) == 0
    assert Path(second["full_path"]).is_file()

    changed_script = approved_script()
    changed_script["script"][0]["voiceover"] = "India lost."
    third = audio.generate_chatterbox_audio(changed_script, output_dir=output_dir)

    assert all(not scene["from_cache"] for scene in third["scenes"])
    assert len(model.generate_calls) == 2


def test_chatterbox_full_generates_one_continuous_take_with_stable_controls(monkeypatch, tmp_path):
    import sys
    import types
    import torch
    import audio
    from pathlib import Path

    class FakeFullChatterbox:
        sr = 16000

        def __init__(self):
            self.calls = []
            self.conditioning_calls = 0
            self.conds = "builtin"

        def prepare_conditionals(self, reference_path, exaggeration=0.5):
            self.conditioning_calls += 1

        def generate(self, text, **kwargs):
            self.calls.append((text, kwargs))
            return torch.ones((1, self.sr * 4), dtype=torch.float32)

    model = FakeFullChatterbox()
    fake_torchaudio = types.SimpleNamespace(
        save=lambda path, waveform, sample_rate: Path(path).write_bytes(b"WAVE" + b"x" * 1200)
    )
    monkeypatch.setitem(sys.modules, "torchaudio", fake_torchaudio)
    monkeypatch.setattr(audio, "get_chatterbox_model", lambda model_version="full": model)
    monkeypatch.setattr(audio, "AUDIO_REFERENCE", tmp_path / "missing-reference.wav")
    monkeypatch.setattr(audio, "_CHATTERBOX_CONDITIONALS_MODEL_ID", None)

    script = approved_script()
    result = audio.generate_chatterbox_audio(
        script,
        output_dir=tmp_path / "full-output",
        model_version="full",
    )

    assert len(model.calls) == 1
    assert model.calls[0][0] == audio._join_narration_texts([scene["voiceover"] for scene in script["script"]])
    assert model.calls[0][1] == {
        "temperature": 0.75,
        "cfg_weight": 0.35,
        "exaggeration": 0.35,
        "min_p": 0.05,
        "top_p": 1.0,
        "repetition_penalty": 1.2,
    }
    assert result["model_version"] == "full"
    assert result["continuous_audio"] is True
    assert all(scene["continuous_master_path"] == result["full_path"] for scene in result["scenes"])


def test_chatterbox_prepares_a_matching_reference_only_once(monkeypatch, tmp_path):
    import sys
    import types
    import torch
    import audio
    from pathlib import Path

    class FakeChatterbox:
        sr = 16000

        def __init__(self):
            self.generate_calls = 0
            self.conditioning_calls = 0

        def prepare_conditionals(self, reference_path, exaggeration=0.5):
            self.conditioning_calls += 1

        def generate(self, text, temperature=0.8):
            self.generate_calls += 1
            return torch.ones((1, self.sr), dtype=torch.float32)

    model = FakeChatterbox()
    fake_torchaudio = types.SimpleNamespace(
        save=lambda path, waveform, sample_rate: Path(path).write_bytes(b"WAVE" + b"x" * 1200)
    )
    reference = tmp_path / "audio_reference.wav"
    reference.write_bytes(b"reference audio bytes")
    monkeypatch.setitem(sys.modules, "torchaudio", fake_torchaudio)
    monkeypatch.setattr(audio, "get_chatterbox_model", lambda: model)
    monkeypatch.setattr(audio, "_CHATTERBOX_CONDITIONALS_MODEL_ID", None)

    audio.generate_chatterbox_audio(
        approved_script(), output_dir=tmp_path / "one", reference=reference
    )
    changed_script = approved_script()
    changed_script["script"][0]["voiceover"] = "A different sentence."
    audio.generate_chatterbox_audio(
        changed_script, output_dir=tmp_path / "two", reference=reference
    )

    assert model.conditioning_calls == 1
    assert model.generate_calls == 2


def test_continuous_narration_join_preserves_sentence_boundaries():
    import audio

    assert audio._join_narration_texts([
        "Virat wins",
        "The team celebrates!",
        "A new record.",
    ]) == "Virat wins. The team celebrates! A new record."
    assert audio._join_narration_texts([
        "A narrow win,",
        "followed by a record",
    ]) == "A narrow win. followed by a record."


def test_chatterbox_delivery_uses_flat_temperature_and_no_heuristic_acting():
    import audio

    texts = [
        "A routine report today.",
        "A heartbreaking injury ends the season.",
        "The captain opened the innings.",
        "An unbelievable last-ball finish stuns the favourites.",
        "The final result changed everything.",
    ]
    assert all(
        audio._chatterbox_delivery(text, number, len(texts))[1] == 0.80
        for number, text in enumerate(texts, 1)
    )
    assert audio._chatterbox_audio_texts(texts) == texts


def test_three_local_chatterbox_voice_choices_are_configured(monkeypatch, tmp_path):
    import audio

    expected = {
        "Voice 1 · Original": "audio_reference.wav",
        "Voice 2": "audio_reference_2.wav",
        "Voice 3": "audio_reference_3.wav",
    }
    assert {label: path.name for label, path in audio.CHATTERBOX_VOICE_REFERENCES.items()} == expected
    for label, name in expected.items():
        file_path = tmp_path / name
        file_path.write_bytes(b"local voice reference")
        monkeypatch.setitem(audio.CHATTERBOX_VOICE_REFERENCES, label, file_path)
        assert audio.resolve_chatterbox_reference(label) == file_path


def test_chatterbox_voice_variant_outputs_do_not_overwrite_each_other(monkeypatch, tmp_path):
    import sys
    import types
    import torch
    from pathlib import Path
    import audio

    class FakeChatterbox:
        sr = 16000

        def __init__(self):
            self.conds = "builtin"
            self.generated = 0

        def prepare_conditionals(self, reference_path, exaggeration=0.5):
            self.conds = Path(reference_path).name

        def generate(self, text, temperature=0.8):
            self.generated += 1
            return torch.ones((1, self.sr), dtype=torch.float32)

    model = FakeChatterbox()
    fake_torchaudio = types.SimpleNamespace(
        save=lambda path, waveform, sample_rate: Path(path).write_bytes(b"WAVE" + b"x" * 1200)
    )
    refs = [tmp_path / "voice_a.wav", tmp_path / "voice_b.wav"]
    for ref in refs:
        ref.write_bytes(b"sample reference content")
    monkeypatch.setitem(sys.modules, "torchaudio", fake_torchaudio)
    monkeypatch.setattr(audio, "get_chatterbox_model", lambda: model)
    monkeypatch.setattr(audio, "_CHATTERBOX_CONDITIONALS_MODEL_ID", None)
    monkeypatch.setattr(audio, "_CHATTERBOX_CONDITIONALS_CACHE", {})
    monkeypatch.setattr(audio, "_CHATTERBOX_DEFAULT_CONDITIONALS", None)

    output = tmp_path / "same-output-root"
    first = audio.generate_chatterbox_audio(approved_script(), output_dir=output, reference=refs[0])
    second = audio.generate_chatterbox_audio(approved_script(), output_dir=output, reference=refs[1])
    again = audio.generate_chatterbox_audio(approved_script(), output_dir=output, reference=refs[0])

    assert first["full_path"] != second["full_path"]
    assert first["full_path"] == again["full_path"]
    assert all(s["from_cache"] for s in again["scenes"])
    assert model.generated == 2



def test_dashboard_exposes_full_and_turbo_for_every_chatterbox_audio_route():
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

    # Standard Shorts (Test/Live), Top-5 (Test/Live), and shared Long-form (Test/Live).
    assert app_source.count('"Chatterbox model"') == 5
    for key in (
        "audio_chatterbox_model_choice",
        "live_audio_chatterbox_model",
        "test_top5_chatterbox_model",
        "live_top5_chatterbox_model",
        '{prefix}audio_chatterbox_model',
    ):
        assert key in app_source

    assert app_source.count('["Turbo", "Full"]') == 5
    assert 'model_version=chatterbox_model_choice.casefold()' in app_source
    assert 'model_version=st.session_state.get("live_audio_chatterbox_model", "Turbo").casefold()' in app_source
    assert 'model_version=t5_chatterbox_model_choice.casefold()' in app_source
    assert 'model_version=live_top5_chatterbox_model_choice.casefold()' in app_source
    assert 'model_version=longform_chatterbox_model_choice.casefold()' in app_source
    assert "def _audio_selection_mismatch(" in app_source
    assert "disabled=model_mismatch" in app_source
    assert "Chatterbox Turbo (Voice Cloning)" not in app_source
