from pathlib import Path
import pytest
import torch

from longform_audio import LongformAudioEngine


def sample_script():
    return {
        "title": "BCCI Names Bumrah Captain",
        "scenes": [
            {
                "scene_number": 1,
                "act_number": 1,
                "voiceover": "Jasprit Bumrah takes the helm in Adelaide.",
                "primary_entity": "Jasprit Bumrah",
            },
            {
                "scene_number": 2,
                "act_number": 2,
                "voiceover": "With fifty-two Test wickets, his precision is unmatched.",
                "primary_entity": "Jasprit Bumrah",
            },
        ],
    }


def test_longform_audio_requires_scenes():
    with pytest.raises(ValueError, match="contains no scenes"):
        LongformAudioEngine.generate({"title": "Empty", "scenes": []})


def test_longform_audio_requires_voiceover():
    with pytest.raises(ValueError, match="has no voiceover"):
        LongformAudioEngine.generate({
            "scenes": [{"scene_number": 1, "voiceover": ""}],
        })


def test_longform_audio_rejects_unsupported_chatterbox_language():
    with pytest.raises(ValueError, match="English narration only"):
        LongformAudioEngine.generate({
            "language": "hindi",
            "scenes": [{"scene_number": 1, "voiceover": "यह एक परीक्षण है।"}],
        })


def test_longform_audio_reference_conditioning_failure_is_reported(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        def prepare_conditionals(self, ref_path, exaggeration=0.5):
            raise ValueError("invalid voice reference")

    reference = tmp_path / "audio_reference.wav"
    reference.write_bytes(b"not a real wav, deliberately rejected by fake model")
    monkeypatch.setattr(longform_audio, "get_chatterbox_model", lambda: FakeChatterbox())

    with pytest.raises(RuntimeError, match="could not use the voice reference file"):
        LongformAudioEngine.generate(
            sample_script(),
            reference_audio=reference,
            output_dir=tmp_path / "generated",
        )


def test_longform_audio_generates_with_mock_model(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        sr = 24000

        def prepare_conditionals(self, ref_path, exaggeration=0.5):
            pass

        def generate(self, text, temperature=0.8):
            # Return 0.5s dummy wave
            samples = int(self.sr * 0.5)
            return torch.zeros((samples,))

    monkeypatch.setattr(longform_audio, "get_chatterbox_model", lambda: FakeChatterbox())

    result = LongformAudioEngine.generate(
        sample_script(),
        output_dir=tmp_path,
    )

    assert result["engine"] == "Chatterbox-Turbo"
    assert Path(result["master_path"]).is_file()
    assert len(result["scenes"]) == 2
    assert result["scenes"][0]["timings"][0]["word"] == "Jasprit"
    assert result["total_duration"] > 0


def test_longform_groups_same_act_scenes_into_one_generation(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        sr = 24000

        def __init__(self):
            self.calls = []

        def generate(self, text, **kwargs):
            self.calls.append((text, kwargs))
            return torch.zeros((1, int(self.sr * 4)))

    model = FakeChatterbox()
    monkeypatch.setattr(
        longform_audio,
        "get_chatterbox_model",
        lambda model_version="turbo": model,
    )
    script = sample_script()
    script["scenes"][1]["act_number"] = 1

    result = LongformAudioEngine.generate(script, output_dir=tmp_path)

    expected_text = " ".join(scene["voiceover"] for scene in script["scenes"])
    assert len(model.calls) == 1
    assert model.calls[0] == (
        expected_text,
        {"temperature": 0.90, "top_p": 0.95, "top_k": 1000, "repetition_penalty": 1.15},
    )
    assert result["continuous_audio"] is True
    assert result["model_version"] == "turbo"
    assert len(result["scenes"]) == 2
    assert result["scenes"][1]["start_seconds"] == result["scenes"][0]["duration"]


def test_longform_full_model_uses_controlled_settings_and_chunking(monkeypatch, tmp_path):
    import longform_audio

    class FakeFullChatterbox:
        sr = 24000

        def __init__(self):
            self.calls = []
            self.conds = "builtin"

        def generate(self, text, **kwargs):
            self.calls.append((text, kwargs))
            return torch.zeros((1, int(self.sr * 4)))

    model = FakeFullChatterbox()
    monkeypatch.setattr(
        longform_audio,
        "get_chatterbox_model",
        lambda model_version="turbo": model,
    )
    script = sample_script()
    script["scenes"][1]["act_number"] = 1
    expected_text = " ".join(scene["voiceover"] for scene in script["scenes"])
    captured_profiles = []
    monkeypatch.setattr(
        longform_audio,
        "_infer_chatterbox_delivery_profile",
        lambda text, version: captured_profiles.append((text, version)) or {
            "delivery_tone": "triumphant and celebratory",
            "exaggeration": 0.65,
            "cfg_weight": 0.30,
        },
    )

    result = LongformAudioEngine.generate(
        script,
        output_dir=tmp_path,
        model_version="full",
    )

    assert len(model.calls) == 1
    assert model.calls[0][0] == expected_text
    assert captured_profiles == [(expected_text, "full")]
    assert model.calls[0][1] == {
        "temperature": 0.75,
        "cfg_weight": 0.30,
        "exaggeration": 0.65,
        "min_p": 0.05,
        "top_p": 1.0,
        "repetition_penalty": 1.2,
    }
    assert result["engine"] == "Chatterbox-Full"
    assert result["model_version"] == "full"


def test_longform_serious_story_keeps_clear_temperature_in_opening_act(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        sr = 24000

        def __init__(self):
            self.temperatures = []

        def generate(self, text, **kwargs):
            self.temperatures.append(kwargs)
            return torch.zeros((int(self.sr * 0.5),))

    model = FakeChatterbox()
    monkeypatch.setattr(longform_audio, "get_chatterbox_model", lambda: model)
    script = {
        "title": "Injury Update",
        "scenes": [{
            "scene_number": 1,
            "act_number": 1,
            "voiceover": "A fatal injury has ended his season.",
        }],
    }

    LongformAudioEngine.generate(script, output_dir=tmp_path)

    assert model.temperatures == [{
        "temperature": 0.90,
        "top_p": 0.95,
        "top_k": 1000,
        "repetition_penalty": 1.15,
    }]


def test_longform_audio_approve(tmp_path):
    master_file = tmp_path / "longform_master.wav"
    master_file.write_bytes(b"RIFF" + b"x" * 2000)

    audio_data = {
        "master_path": str(master_file),
        "total_duration": 480.0,
        "scenes": [],
    }

    approved = LongformAudioEngine.approve_audio(audio_data)
    assert approved["approved_for_assembly"] is True


def test_longform_audio_reuses_exact_output_without_regenerating(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        sr = 24000

        def __init__(self):
            self.conds = "builtin"
            self.generated = 0

        def generate(self, text, temperature=0.8):
            self.generated += 1
            return torch.zeros((int(self.sr * 0.5),))

    fake = FakeChatterbox()
    monkeypatch.setattr(longform_audio, "get_chatterbox_model", lambda: fake)

    first = LongformAudioEngine.generate(sample_script(), output_dir=tmp_path)
    second = LongformAudioEngine.generate(sample_script(), output_dir=tmp_path)

    assert first["from_cache"] is False
    assert second["from_cache"] is True
    assert first["master_path"] == second["master_path"]
    assert fake.generated == 2
