from subtitles import approve_subtitles, generate_subtitles


def _approved_audio():
    return {
        "approved_for_visuals": True,
        "language": "english",
        "scenes": [
            {
                "scene": 1,
                "duration": 2.8,
                "timings": [
                    {"word": "Virat", "start": 0.0, "end": 0.3},
                    {"word": "Kohli", "start": 0.31, "end": 0.62},
                    {"word": "hit", "start": 0.63, "end": 0.82},
                    {"word": "a", "start": 0.83, "end": 0.9},
                    {"word": "century", "start": 0.91, "end": 1.3},
                    {"word": "in", "start": 1.31, "end": 1.45},
                    {"word": "style", "start": 1.46, "end": 1.75},
                ],
            },
            {
                "scene": 2,
                "duration": 1.9,
                "timings": [
                    {"word": "India", "start": 0.0, "end": 0.25},
                    {"word": "won", "start": 0.26, "end": 0.55},
                ],
            },
        ],
    }


def test_generate_subtitles_groups_word_timings_and_writes_srt(tmp_path):
    result = generate_subtitles(_approved_audio(), tmp_path)

    assert result["format"] == "srt"
    assert len(result["scenes"]) == 2
    assert result["scenes"][0]["cues"]
    assert result["scenes"][0]["cues"][0]["text"] == "Virat Kohli hit a century in"
    assert "-->" in result["srt"]
    assert (tmp_path / "final_shorts.srt").exists()
    assert (tmp_path / "scene_1.srt").exists()


def test_generate_subtitles_offsets_combined_cues(tmp_path):
    result = generate_subtitles(_approved_audio(), tmp_path)

    assert result["cues"][0]["start"] == 0.0
    assert result["cues"][-1]["start"] >= 2.8


def test_subtitles_require_approved_audio(tmp_path):
    audio = _approved_audio()
    audio["approved_for_visuals"] = False

    try:
        generate_subtitles(audio, tmp_path)
    except ValueError as exc:
        assert "approved Audio" in str(exc)
    else:
        raise AssertionError("Unapproved audio must be rejected.")


def test_approved_subtitles_are_renderer_handoff(tmp_path):
    result = generate_subtitles(_approved_audio(), tmp_path)
    approved = approve_subtitles(result)

    assert approved["approved_for_renderer"] is True
