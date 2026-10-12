import pytest

from longform_subtitles import LongformSubtitleEngine, SCHEMA


def sample_script():
    return {
        "title": "BCCI Names Bumrah Captain",
        "acts": [
            {"act_number": 1, "chapter_title": "The Adelaide Dilemma"},
            {"act_number": 2, "chapter_title": "The Strategic Turning Point"},
        ],
        "scenes": [
            {"scene_number": 1, "act_number": 1, "voiceover": "Jasprit Bumrah takes the helm in Adelaide."},
            {"scene_number": 2, "act_number": 2, "voiceover": "With fifty-two Test wickets, his precision is unmatched."},
        ],
    }


def sample_audio():
    return {
        "total_duration": 12.0,
        "scenes": [
            {
                "scene": 1,
                "act": 1,
                "start_seconds": 0.0,
                "duration": 5.0,
                "timings": [
                    {"word": "Jasprit", "start": 0.0, "end": 0.5},
                    {"word": "Bumrah", "start": 0.5, "end": 1.0},
                    {"word": "takes", "start": 1.0, "end": 1.4},
                    {"word": "the", "start": 1.4, "end": 1.6},
                    {"word": "helm", "start": 1.6, "end": 2.0},
                    {"word": "in", "start": 2.0, "end": 2.3},
                    {"word": "Adelaide.", "start": 2.3, "end": 3.0},
                ],
            },
            {
                "scene": 2,
                "act": 2,
                "start_seconds": 5.5,
                "duration": 6.0,
                "timings": [
                    {"word": "With", "start": 0.0, "end": 0.3},
                    {"word": "fifty-two", "start": 0.3, "end": 0.9},
                    {"word": "Test", "start": 0.9, "end": 1.3},
                    {"word": "wickets,", "start": 1.3, "end": 1.8},
                    {"word": "his", "start": 1.8, "end": 2.1},
                    {"word": "precision", "start": 2.1, "end": 2.7},
                    {"word": "is", "start": 2.7, "end": 3.0},
                    {"word": "unmatched.", "start": 3.0, "end": 3.8},
                ],
            },
        ],
    }


def test_longform_subtitles_requires_valid_handoffs():
    with pytest.raises(ValueError, match="Scriptwriter data"):
        LongformSubtitleEngine.generate({}, {})

    with pytest.raises(ValueError, match="Audio scenes"):
        LongformSubtitleEngine.generate(sample_script(), {})


def test_longform_subtitles_generates_cues_and_billboards():
    result = LongformSubtitleEngine.generate(sample_script(), sample_audio())

    assert result["schema"] == SCHEMA
    assert result["cue_count"] >= 2
    assert len(result["act_billboards"]) == 2
    assert result["act_billboards"][0]["title"] == "THE ADELAIDE DILEMMA"
    assert "-->" in result["srt_content"]
    assert "Jasprit Bumrah" in result["srt_content"]


def test_longform_subtitles_approve():
    result = LongformSubtitleEngine.generate(sample_script(), sample_audio())
    approved = LongformSubtitleEngine.approve(result)

    assert approved["approved_for_render"] is True
