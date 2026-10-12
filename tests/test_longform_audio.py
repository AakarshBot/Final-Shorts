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
