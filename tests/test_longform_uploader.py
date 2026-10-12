from pathlib import Path
import pytest

from longform_uploader import LongformUploader, format_longform_description


def test_format_longform_description():
    desc = format_longform_description(
        description_text="An in-depth documentary on Jasprit Bumrah's Adelaide spell.",
        chapters="00:00 - Intro\n01:14 - Act I\n03:22 - Act II",
        sources=["https://espncricinfo.com/story1", "https://cricbuzz.com/story2"],
        hashtags=["#Cricket", "#India", "#Bumrah"],
    )

    assert "TIMESTAMPS:" in desc
    assert "01:14 - Act I" in desc
    assert "SOURCES & RESEARCH EVIDENCE:" in desc
    assert "https://espncricinfo.com/story1" in desc
    assert "#Bumrah" in desc


def test_prepare_package(tmp_path):
    fake_video = tmp_path / "documentary.mp4"
    fake_video.write_bytes(b"RIFF" + b"x" * 2000)

    script = {
        "title": "BCCI Names Bumrah Captain",
        "titles": ["Jasprit Bumrah: The Adelaide Test", "Bumrah's Tactical Masterclass"],
        "seo_description": "Documentary on Bumrah",
        "pinned_comment": "Was this the best captaincy spell of 2026? Comment below.",
    }

    topic = {
        "title": "BCCI Names Bumrah Captain",
        "url": "https://espncricinfo.com/bumrah",
        "reports": [],
    }

    package = LongformUploader.prepare_package(script, topic, fake_video)

    assert package["title"] == "Jasprit Bumrah: The Adelaide Test"
    assert len(package["title_candidates"]) == 2
    assert "TIMESTAMPS" in package["description"] or "Bumrah" in package["description"]
    assert package["privacy_status"] == "private"
    assert package["video_path"] == str(fake_video)
