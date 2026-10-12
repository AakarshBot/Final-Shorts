import io
from PIL import Image
import pytest

from longform_visuals import (
    LongformVisualMatcher,
    _entity_matches,
    _image_valid_and_hires,
    _score_asset,
)
from tests.test_longform_script_writer import sample_longform_story, sample_raw_llm_script
from longform_script_writer import LongformScriptWriter


def _create_dummy_image(w=1400, h=800):
    img = Image.new("RGB", (w, h), (30, 40, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_entity_matches():
    assert _entity_matches("Jasprit Bumrah bowling in Australia", "", "Jasprit Bumrah") is True
    assert _entity_matches("Bumrah strikes twice in evening session", "", "Jasprit Bumrah") is True
    assert _entity_matches("Virat Kohli century in Perth", "", "Jasprit Bumrah") is False
    assert _entity_matches("Rohit Sharma press conference", "", "Rohit Sharma") is True


def test_image_valid_and_hires():
    valid, w, h = _image_valid_and_hires(_create_dummy_image(1400, 800))
    assert valid is True
    assert w == 1400 and h == 800

    too_small, _, _ = _image_valid_and_hires(_create_dummy_image(400, 300))
    assert too_small is False


def test_score_asset_boosts_matching_entity_and_intent():
    asset = {
        "title": "Jasprit Bumrah bowling delivery during Test match",
        "source": "Commons",
        "source_page_url": "https://commons.wikimedia.org/wiki/File:Bumrah.jpg",
    }
    score = _score_asset(asset, "Jasprit Bumrah", "match_action")
    assert score > 10.0


def test_longform_visual_matcher_runs(monkeypatch):
    story = sample_longform_story()
    script = LongformScriptWriter.validate_and_format(sample_raw_llm_script(), story)

    mock_asset = {
        "bytes": _create_dummy_image(1600, 900),
        "hash": "hash_bumrah_123",
        "source": "Commons",
        "source_page_url": "https://commons.wikimedia.org/Bumrah.jpg",
        "title": "Jasprit Bumrah Test bowling action",
    }

    monkeypatch.setattr("longform_visuals.search_images", lambda q: {"assets": [mock_asset]})

    result = LongformVisualMatcher.match_and_collect(script, story)

    assert result["total_scenes"] == 18
    assert len(result["scenes_visuals"]) == 18
    # Scene 2 was specified as a card in sample_raw_llm_script
    card_scenes = [s for s in result["scenes_visuals"] if s["visual_type"] == "card"]
    assert len(card_scenes) >= 1
    assert card_scenes[0]["image_bytes"] is not None
