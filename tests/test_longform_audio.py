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


def test_longform_serious_story_keeps_clear_temperature_in_opening_act(monkeypatch, tmp_path):
    import longform_audio

    class FakeChatterbox:
        sr = 24000

        def __init__(self):
            self.temperatures = []

        def generate(self, text, temperature=0.8):
            self.temperatures.append(temperature)
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

    assert model.temperatures == [0.80]


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
