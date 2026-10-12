from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _run_app(state=None):
    at = AppTest.from_file(str(APP_PATH), default_timeout=20)
    for key, value in (state or {}).items():
        at.session_state[key] = value
    at.run()
    return at


def test_home_selects_format_before_workspace():
    at = _run_app({"app_mode": "home"})

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Open Shorts" in labels
    assert "Open Long-form" in labels
    assert "Open Test" not in labels

    next(button for button in at.button if button.label == "Open Long-form").click().run()

    assert not at.exception, at.exception
    assert at.session_state["factory_format"] == "long_form"
    labels = [button.label for button in at.button]
    assert "Open Test" in labels
    assert "Open Live" in labels


def test_longform_test_shows_only_topic_fetcher():
    at = _run_app({"app_mode": "test", "factory_format": "long_form"})

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Find long-form stories" in labels
    assert "Find more stories" in labels
    assert "Open Deep-Dive" not in labels
    assert "Generate audio" not in labels


def test_longform_live_is_blocked_without_touching_shorts_live():
    at = _run_app({"app_mode": "live", "factory_format": "long_form"})

    assert not at.exception, at.exception
    assert any("Not enabled yet" in str(item.value) for item in at.markdown)
    assert any("Long-form remains Test-only" in str(item.value) for item in at.markdown)
    assert not any("LIVE PRODUCTION" in str(item.value) for item in at.markdown)


def test_existing_shorts_test_line_selector_remains_available():
    at = _run_app({"app_mode": "test", "factory_format": "shorts", "test_production_line": None})

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Open Deep-Dive" in labels
    assert "Open Top-5" in labels
    assert "Open YT Trends" in labels


def test_longform_test_stages_navigation():
    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "02 · Scriptwriter",
        "longform_approved_topic": {
            "title": "BCCI Names Bumrah Captain",
            "publisher": "ESPNcricinfo",
            "reports": [],
        },
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Generate 8-Min Documentary Script" in labels


def test_longform_test_visuals_navigation():
    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "03 · Visuals",
        "longform_approved_topic": {
            "title": "BCCI Names Bumrah Captain",
            "publisher": "ESPNcricinfo",
            "reports": [],
        },
        "longform_approved_script": {
            "title": "BCCI Names Bumrah Captain",
            "scenes": [],
        },
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Run Automated Visual Engine" in labels


def test_longform_test_audio_navigation():
    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "04 · Audio",
        "longform_approved_topic": {
            "title": "BCCI Names Bumrah Captain",
            "publisher": "ESPNcricinfo",
            "reports": [],
        },
        "longform_approved_script": {
            "title": "BCCI Names Bumrah Captain",
            "scenes": [
                {"scene_number": 1, "voiceover": "Bumrah leads the attack.", "primary_entity": "Bumrah"},
            ],
        },
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Synthesize Full Narration" in labels


def test_longform_test_subtitles_navigation():
    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "05 · Subtitles",
        "longform_approved_script": {"title": "BCCI Names Bumrah Captain", "scenes": []},
        "longform_approved_audio": {"total_duration": 10.0, "scenes": [{"scene": 1}]},
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Generate Broadcast Subtitles" in labels


def test_longform_test_renderer_navigation(tmp_path):
    fake_master = tmp_path / "master.wav"
    fake_master.write_bytes(b"RIFF" + b"x" * 2000)

    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "06 · Renderer",
        "longform_approved_script": {"title": "BCCI Names Bumrah Captain", "scenes": []},
        "longform_approved_visuals": {"scenes_visuals": [{"scene_number": 1}]},
        "longform_approved_audio": {"master_path": str(fake_master), "total_duration": 10.0, "scenes": [{"scene": 1}]},
        "longform_approved_subtitles": {"cues": [{"cue_index": 1}]},
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Render 16:9 Documentary Video" in labels


def test_longform_test_upload_qc_navigation(tmp_path):
    fake_video = tmp_path / "doc.mp4"
    fake_video.write_bytes(b"RIFF" + b"x" * 2000)

    at = _run_app({
        "app_mode": "test",
        "factory_format": "long_form",
        "longform_test_stage": "07 · Upload QC",
        "longform_approved_topic": {"title": "BCCI Names Bumrah Captain", "url": "https://espncricinfo.com"},
        "longform_approved_script": {"title": "BCCI Names Bumrah Captain", "titles": ["Title 1"]},
        "longform_approved_video": str(fake_video),
    })

    assert not at.exception, at.exception
    labels = [button.label for button in at.button]
    assert "Upload Documentary to YouTube" in labels


