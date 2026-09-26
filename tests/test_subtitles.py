import pytest

from subtitles import generate_subtitles


def approved_script(language="english"):
    return {
        "approved_for_audio": True,
        "language_used": language,
        "script": [
            {"voiceover": "India won the match."},
            {"voiceover": "Bowlers held their nerve."},
        ],
    }


def approved_audio(language="english"):
    return {
        "approved_for_visuals": True,
        "language": language,
        "total_duration": 3.0,
        "scenes": [
            {
                "scene": 1,
                "duration": 1.4,
                "timings": [
                    {"word": "India", "start": 0.0, "end": 0.3},
                    {"word": "won", "start": 0.3, "end": 0.6},
                    {"word": "the", "start": 0.6, "end": 0.8},
                    {"word": "match", "start": 0.8, "end": 1.0},
                ],
            },
            {
                "scene": 2,
                "duration": 1.6,
                "timings": [
                    {"word": "Bowlers", "start": 0.1, "end": 0.4},
                    {"word": "held", "start": 0.4, "end": 0.7},
                    {"word": "their", "start": 0.7, "end": 0.9},
                    {"word": "nerve", "start": 0.9, "end": 1.2},
                ],
            },
        ],
    }


def test_subtitles_create_absolute_timestamps_across_scenes():
    result = generate_subtitles(approved_script(), approved_audio())
    assert result["schema"] == "final-shorts.subtitles.v1"
    assert result["language"] == "english"
    assert result["cues"][0]["start"] == 0.0
    assert result["cues"][0]["end"] == 1.0
    assert result["cues"][1]["start"] == 1.5
    assert result["cues"][1]["end"] == 2.6


def test_subtitles_preserve_script_punctuation_when_audio_word_matches():
    result = generate_subtitles(approved_script(), approved_audio())
    assert result["cues"][0]["words"][-1]["text"] == "match."


def test_subtitles_break_into_small_readable_cues():
    script = approved_script()
    script["script"][0]["voiceover"] = "One two three four five six seven eight."
    audio = approved_audio()
    audio["scenes"][0]["timings"] = [
        {"word": word, "start": index * 0.2, "end": (index + 1) * 0.2}
        for index, word in enumerate("One two three four five six seven eight".split())
    ]
    result = generate_subtitles(script, audio)
    assert all(len(cue["words"]) <= 4 for cue in result["cues"])
    assert len(result["cues"]) >= 2


def test_subtitles_require_approved_handoffs():
    with pytest.raises(ValueError, match="approved Scriptwriter"):
        generate_subtitles({}, approved_audio())
    with pytest.raises(ValueError, match="approved Audio"):
        generate_subtitles(approved_script(), {})


def test_subtitles_reject_mismatched_languages():
    with pytest.raises(ValueError, match="languages"):
        generate_subtitles(approved_script("hindi"), approved_audio("english"))
