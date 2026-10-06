from io import BytesIO
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from topic_fetcher import Topic

from PIL import Image, ImageChops
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

VISUAL_OPTIONS = (
    "Option 2 · Manual Scraper",
    "Option 3 · Real Image Search",
    "Option 4 · AI Generation",
    "Option 5 · Stats Card",
    "Option 6 · Quote Card",
)


def _image_bytes(color=(40, 50, 60), size=(600, 900)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _run_visual_option(option: str) -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["visual_test_mode"] = option
    at.session_state["manual_visual_result"] = {
        "assets": [
            {
                "bytes": _image_bytes(),
                "source": "test",
                "article_title": "Test image",
            }
        ]
    }
    at.run()
    return at


def test_manual_visual_options_load():
    for option in VISUAL_OPTIONS[:3]:
        at = _run_visual_option(option)
        assert not at.exception, at.exception


def test_card_visual_options_load():
    for option in VISUAL_OPTIONS[3:]:
        at = _run_visual_option(option)
        assert not at.exception, at.exception


def test_top5_standalone_visual_qc_exposes_all_nine_options():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.run()

    assert not at.exception, at.exception
    button_labels = [button.label for button in at.button]
    assert all(
        option in button_labels
        for option in (
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Manual Fetcher",
            "Option 4 · AI Generation",
            "Option 5 · Stats Card",
            "Option 6 · Quote Card",
            "Option 7 · Subject Cutout",
            "Option 8 · Body Card · WIP",
            "Option 9 · Manual Subject Cutout",
        )
    )


def test_top5_subject_cutout_ui_smoke():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 7 · Subject Cutout"
    at.session_state["test_top5_visual_playground_image"] = Image.new(
        "RGB",
        (1080, 1920),
        (40, 40, 40),
    )
    at.session_state["test_top5_visual_playground_source"] = "Test image"
    at.run()

    assert not at.exception, at.exception
    assert any(button.label == "Render Subject Cutout" for button in at.button)
    assert not any(field.label == "Body" for field in at.text_area)

def test_top5_manual_fetcher_and_body_card_wip_load():
    for option in (
        "Option 3 · Manual Fetcher",
        "Option 8 · Body Card · WIP",
    ):
        at = AppTest.from_file(str(APP_PATH), default_timeout=10)
        at.session_state["app_mode"] = "test"
        at.session_state["test_production_line"] = "top_5"
        at.session_state["test_stage"] = "04 · Visuals"
        at.session_state["test_top5_visual_playground_option"] = option
        at.run()

        assert not at.exception, at.exception




def _live_cricket_text_cutout_test(assets, *, crops=None):
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [Topic(
        title="Test story",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/test-story",
    )]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_approved_script"] = {
        "headline": "India win again",
        "script": [
            {"voiceover": "One."},
            {"voiceover": "Two."},
            {"voiceover": "Three."},
            {"voiceover": "Four."},
        ],
    }
    at.session_state["live_approved_audio"] = {}
    at.session_state["live_subtitle_data"] = {}
    at.session_state["live_visual_option"] = "Option 7 · Text Cutout"
    at.session_state["live_visual_result"] = {"assets": assets}
    if crops:
        at.session_state["live_visual_crops"] = crops
    at.run()
    assert not at.exception, at.exception
    assert "Option 7 · Text Cutout" in [button.label for button in at.button]
    return at


def test_cricket_test_exposes_shared_text_cutout():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["topic_desk_profile"] = "cricket_india_asia"
    at.session_state["visual_test_mode"] = "Option 7 · Text Cutout"
    at.session_state["visual_result"] = {"assets": [asset]}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    button_labels = [button.label for button in at.button]
    assert all(
        option in button_labels
        for option in (
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Real Image Search",
            "Option 4 · AI Generation",
            "Option 5 · Stats Card",
            "Option 6 · Quote Card",
            "Option 7 · Text Cutout",
        )
    )
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    assert at.session_state["manual_subject_cutout"]["polygon_points"] == [
        (120, 700),
        (540, 700),
        (960, 700),
        (960, 950),
        (960, 1200),
        (540, 1200),
        (120, 1200),
        (120, 950),
    ]
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["manual_subject_cutout"]["rendered_config"]["text_polygon"] == (
        (120, 700),
        (540, 700),
        (960, 700),
        (960, 950),
        (960, 1200),
        (540, 1200),
        (120, 1200),
        (120, 950),
    )


def test_yt_trends_test_exposes_shared_text_cutout_option_7():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "youtube_trends"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["visual_test_mode"] = "Option 7 · Text Cutout"
    at.session_state["visual_result"] = {"assets": [asset]}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    assert "Option 7 · Text Cutout" in [button.label for button in at.button]
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["manual_subject_cutout"]["rendered_config"]["text_polygon"]


def test_yt_trends_live_exposes_shared_text_cutout_option_7():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "youtube_trends"
    at.session_state["live_desk"] = "youtube_trends"
    at.session_state["live_topics_profile"] = "youtube_trends"
    at.session_state["live_topics"] = [Topic(
        title="Test story",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/test-story",
    )]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_approved_script"] = {
        "headline": "India win again",
        "script": [
            {"voiceover": "One."},
            {"voiceover": "Two."},
            {"voiceover": "Three."},
            {"voiceover": "Four."},
        ],
    }
    at.session_state["live_approved_audio"] = {}
    at.session_state["live_subtitle_data"] = {}
    at.session_state["live_visual_option"] = "Option 7 · Text Cutout"
    at.session_state["live_visual_result"] = {"assets": [asset]}
    at.run()

    assert not at.exception, at.exception
    assert "Option 7 · Text Cutout" in [button.label for button in at.button]
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["rendered_config"]["text_polygon"]


def test_top5_option9_uses_shared_editor():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 9 · Manual Subject Cutout"
    at.session_state["test_top5_visual_playground_image"] = Image.new(
        "RGB",
        (1080, 1920),
        (40, 40, 40),
    )
    at.session_state["test_top5_visual_playground_source"] = "Test image"
    at.session_state["test_top5_visual_playground_headline"] = "India win again"
    at.run()

    assert not at.exception, at.exception
    assert any(
        button.label == "Crop / reposition"
        for button in at.button
    )
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_playground"]["polygon_points"] == [
        (120, 700),
        (540, 700),
        (960, 700),
        (960, 950),
        (960, 1200),
        (540, 1200),
        (120, 1200),
        (120, 950),
    ]
    assert any(field.label == "Manual Subject Cutout headline" for field in at.text_area)
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_playground"]["rendered_config"]["text_polygon"]




def test_top5_option9_per_slide_uses_shared_editor():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_script_handoff"] = {
        "slides": [
            {
                "headline": f"Story {index} headline",
                "body": "",
                "specific_search_prompt": "cricket",
                "visual_intent": "editorial",
            }
            for index in range(1, 7)
        ],
        "stories": [{"title": f"Story {index}"} for index in range(1, 6)],
    }
    at.session_state["test_top5_visual_option"] = "Option 9 · Manual Subject Cutout"
    at.session_state["test_top5_visual_results"] = {
        1: {"assets": [asset]},
    }
    at.run()

    assert not at.exception, at.exception
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_cutouts"][1]["rendered_config"]["text_polygon"]

def test_live_cricket_text_cutout_switches_images_and_reuses_crop():
    assets = [
        {
            "bytes": _image_bytes((40, 50, 60)),
            "source": "source-a",
            "article_title": "Image A",
        },
        {
            "bytes": _image_bytes((80, 90, 100)),
            "source": "source-b",
            "article_title": "Image B",
        },
    ]
    identity = "|".join([
        str(assets[0].get("source_page_url") or assets[0].get("url") or ""),
        str(assets[0].get("article_title") or assets[0].get("model") or ""),
        "0",
    ])
    asset_key = f"live-auto-{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}"
    cropped = _image_bytes((200, 210, 220), size=(1080, 1920))

    at = _live_cricket_text_cutout_test(
        assets,
        crops={asset_key: cropped},
    )
    assert not at.exception, at.exception
    selects = [button for button in at.button if button.label == "Select image"]
    assert selects
    selects[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["image_key"] == asset_key
    second_identity = "|".join([
        str(assets[1].get("source_page_url") or assets[1].get("url") or ""),
        str(assets[1].get("article_title") or assets[1].get("model") or ""),
        "1",
    ])
    second_key = f"live-auto-{hashlib.sha1(second_identity.encode('utf-8')).hexdigest()[:12]}"
    at.button(
        key=f"live-cricket-manual-subject-select-{second_key}"
    ).click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["image_key"] == second_key


def test_top5_option9_second_run_preserves_text_size():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 9 · Manual Subject Cutout"
    at.session_state["test_top5_visual_playground_image"] = Image.new(
        "RGB",
        (1080, 1920),
        (40, 40, 40),
    )
    at.session_state["test_top5_visual_playground_source"] = "Test image"
    at.session_state["test_top5_visual_playground_headline"] = "India win again"
    at.run()

    next(button for button in at.button if button.label == "Select image").click().run()
    assert not at.exception, at.exception
    next(button for button in at.button if button.label == "Render Now").click().run()
    assert not at.exception, at.exception

    first_preview = bytes(at.session_state["test_top5_manual_subject_playground"]["rendered_preview"])
    at.slider[0].set_value(220).run()
    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_playground"]["rendered_config"]["font_size"] == 150
    next(button for button in at.button if button.label == "Render Now").click().run()
    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_playground"]["rendered_config"]["font_size"] == 220
    second_preview = bytes(at.session_state["test_top5_manual_subject_playground"]["rendered_preview"])
    assert ImageChops.difference(
        Image.open(BytesIO(first_preview)).convert("RGB"),
        Image.open(BytesIO(second_preview)).convert("RGB"),
    ).getbbox() is not None


def test_live_cricket_text_cutout_second_run_preserves_text_size():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "Image A",
    }
    at = _live_cricket_text_cutout_test([asset])
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception

    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert [slider.label for slider in at.slider] == ["Text size"]

    first_preview = bytes(at.session_state["live_manual_subject_cutout"]["rendered_preview"])
    at.slider[0].set_value(220).run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["rendered_config"]["font_size"] == 150

    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["rendered_config"]["font_size"] == 220
    second_preview = bytes(at.session_state["live_manual_subject_cutout"]["rendered_preview"])
    assert ImageChops.difference(
        Image.open(BytesIO(first_preview)).convert("RGB"),
        Image.open(BytesIO(second_preview)).convert("RGB"),
    ).getbbox() is not None



def test_manual_subject_cutout_migrates_four_point_polygon_to_eight_points():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 9 · Manual Subject Cutout"
    at.session_state["test_top5_visual_playground_image"] = Image.new("RGB", (1080, 1920), (40, 40, 40))
    at.session_state["test_top5_visual_playground_source"] = "Test image"
    at.session_state["test_top5_visual_playground_headline"] = "India win again"
    at.run()

    assert not at.exception, at.exception
    next(button for button in at.button if button.label == "Select image").click().run()
    assert not at.exception, at.exception

    at.session_state["test_top5_manual_subject_playground"]["polygon_points"] = [
        (120, 700),
        (960, 700),
        (960, 1200),
        (120, 1200),
    ]
    at.run()

    assert not at.exception, at.exception
    assert at.session_state["test_top5_manual_subject_playground"]["polygon_points"] == [
        (120, 700),
        (540, 700),
        (960, 700),
        (960, 950),
        (960, 1200),
        (540, 1200),
        (120, 1200),
        (120, 950),
    ]
