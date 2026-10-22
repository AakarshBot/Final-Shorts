from io import BytesIO
import hashlib
from pathlib import Path
from threading import Event
from datetime import datetime, timezone

from topic_fetcher import Topic

from PIL import Image, ImageChops
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

VISUAL_OPTIONS = (
    "Option 2 · Manual Scraper",
    "Option 3 · Real Image Search",
    "Option 4 · AI Generation",
    "Option 5 · Card Studio",
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


def test_top5_standalone_visual_qc_exposes_card_studio():
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
            "Option 5 · Card Studio",
        )
    )



def test_top5_card_studio_subject_cutout_ui_smoke():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 5 · Card Studio"
    at.session_state["test_top5_visual_playground_image"] = Image.new("RGB", (1080, 1920), (40, 40, 40))
    at.session_state["test_top5_visual_playground_source"] = "Test image"
    at.run()

    assert not at.exception, at.exception
    assert any(button.label == "Select image" for button in at.button)
    assert not any(field.label == "Body" for field in at.text_area)



def test_top5_manual_fetcher_loads():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 3 · Manual Fetcher"
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
    at.session_state["live_visual_option"] = "Option 5 · Card Studio"
    at.session_state["live_visual_result"] = {"assets": assets}
    if crops:
        at.session_state["live_visual_crops"] = crops
    at.run()
    assert not at.exception, at.exception
    assert "Option 5 · Card Studio" in [button.label for button in at.button]
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
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["visual_result"] = {"assets": [asset]}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "source_title": "India win again",
        "script": [{"voiceover": "India win again"}] * 4,
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
            "Option 5 · Card Studio",
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
    assert at.session_state["manual_subject_cutout"]["rendered_config"]["headline"] == "One."
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


def test_manual_subject_cutout_renders_with_manual_line_breaks():
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
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["visual_result"] = {"assets": [asset]}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    next(button for button in at.button if button.label == "Select image").click().run()
    assert not at.exception, at.exception
    manual_lines = next(
        widget for widget in at.text_area
        if widget.label == "Manual line breaks (optional)"
    )
    manual_lines.set_value("India win\nagain").run()
    assert not at.exception, at.exception
    next(button for button in at.button if button.label == "Render Now").click().run()
    assert not at.exception, at.exception
    assert at.session_state["manual_subject_cutout"]["rendered_config"]["source_key"]
    assert at.session_state["manual_subject_cutout"]["rendered_config"]["manual_lines"] == "India win\nagain"

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
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["visual_result"] = {"assets": [asset]}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    assert "Option 5 · Card Studio" in [button.label for button in at.button]
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
    at.session_state["live_visual_option"] = "Option 5 · Card Studio"
    at.session_state["live_visual_result"] = {"assets": [asset]}
    at.run()

    assert not at.exception, at.exception
    assert "Option 5 · Card Studio" in [button.label for button in at.button]
    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    render = next(button for button in at.button if button.label == "Render Now")
    render.click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["rendered_config"]["text_polygon"]


def test_top5_card_studio_uses_shared_editor():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 5 · Card Studio"
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




def test_top5_card_studio_per_slide_uses_shared_editor():
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
    at.session_state["test_top5_visual_option"] = "Option 5 · Card Studio"
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
        key=f"live-standalone-card-studio-select-{second_key}"
    ).click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_manual_subject_cutout"]["image_key"] == second_key


def test_top5_card_studio_second_run_preserves_text_size():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["test_top5_visual_playground_option"] = "Option 5 · Card Studio"
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
    assert at.session_state["live_manual_subject_cutout"]["rendered_config"]["headline"] == "One."

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
    at.session_state["test_top5_visual_playground_option"] = "Option 5 · Card Studio"
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



def test_card_studio_shows_image_pool_crop_controls_and_default_fields(monkeypatch):
    import script_writer

    def fake_generate(card_type, story, target_language="english", manual_prompt=""):
        assert card_type == "Stat Highlight"
        assert story["title"] == "India win again"
        assert target_language == "english"
        return {
            "eyebrow": "AUTO CAREER STAT",
            "headline": "Generated from approved story",
            "value": "999",
            "unit": "RUNS",
            "metrics": [
                {"label": "Matches", "value": "12"},
                {"label": "Average", "value": "46.2"},
                {"label": "Centuries", "value": "3"},
            ],
        }

    monkeypatch.setattr(script_writer, "generate_card_copy", fake_generate)
    assets = [
        {"bytes": _image_bytes((40, 50, 60)), "source": "source-a", "article_title": "Image A"},
        {"bytes": _image_bytes((70, 80, 90)), "source": "source-b", "article_title": "Image B"},
        {"bytes": _image_bytes((100, 110, 120)), "source": "source-c", "article_title": "Image C"},
    ]
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["test-standalone-card-studio-type"] = "Stat Highlight"
    at.session_state["visual_result"] = {"assets": assets}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    assert [button.label for button in at.button].count("Crop / reposition") == 3
    next(button for button in at.button if button.label == "Select image").click().run()
    assert not at.exception, at.exception
    values = {field.label: field.value for field in at.text_input}
    assert values["Eyebrow"] == "CAREER STAT"
    assert values["Headline"] == "A huge scoring run"
    assert values["Hero value"] == "1,203"
    assert values["Unit"] == "RUNS"
    assert any(field.label == "Metric 1 label" and field.value == "Matches" for field in at.text_input)

    next(button for button in at.button if button.label == "Auto-fill this card from story").click().run()
    assert not at.exception, at.exception
    generated_values = {field.label: field.value for field in at.text_input}
    assert generated_values["Eyebrow"] == "AUTO CAREER STAT"
    assert generated_values["Headline"] == "Generated from approved story"
    assert generated_values["Hero value"] == "999"
    assert generated_values["Unit"] == "RUNS"
    assert any(field.label == "Metric 1 label" and field.value == "Matches" for field in at.text_input)


def test_card_studio_direct_attach_photo_to_slide():
    assets = [
        {"bytes": _image_bytes((40, 50, 60)), "source": "source-a", "article_title": "Image A"},
    ]
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["test-standalone-card-studio-type"] = "Stat Highlight"
    at.session_state["visual_result"] = {"assets": assets}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    # Click select image
    select_btn = next((button for button in at.button if button.label == "Select image"), None)
    if select_btn:
        select_btn.click().run()
    assert not at.exception, at.exception

    # Check that direct attach button is present
    direct_btn = next((button for button in at.button if "Attach to Slide" in button.label and "directly" in button.label), None)
    assert direct_btn is not None, f"Expected direct attach button, found buttons: {[b.label for b in at.button]}"

    # Click direct attach
    direct_btn.click().run()
    assert not at.exception, at.exception

    # Verify visual assignment is created on slide 1 with direct photo
    assignments = at.session_state.get("visual_assignments") or {}
    assert 1 in assignments
    assert assignments[1]["result_key"] == "card-studio-photo"
    assert assignments[1]["source"] in {"source-a", "Automatic Scraper"}
    assert len(assignments[1]["bytes"]) > 0


def test_card_studio_cutout_direct_attach_photo_to_slide():
    assets = [
        {"bytes": _image_bytes((40, 50, 60)), "source": "source-a", "article_title": "Image A"},
    ]
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "04 · Visuals"
    at.session_state["visual_test_mode"] = "Option 5 · Card Studio"
    at.session_state["test-standalone-card-studio-type"] = "Text Subject Cutout"
    at.session_state["visual_result"] = {"assets": assets}
    at.session_state["script_data"] = {
        "headline": "India win again",
        "script": [{"voiceover": "One."}] * 4,
    }
    at.run()

    assert not at.exception, at.exception
    select_btn = next((button for button in at.button if button.label == "Select image"), None)
    if select_btn:
        select_btn.click().run()
    assert not at.exception, at.exception

    # Check that direct attach button is present
    direct_btn = next((button for button in at.button if "Attach to Slide" in button.label and "directly" in button.label), None)
    assert direct_btn is not None, f"Expected direct attach button, found buttons: {[b.label for b in at.button]}"

    # Click direct attach
    direct_btn.click().run()
    assert not at.exception, at.exception

    # Verify visual assignment is created on slide 1
    assignments = at.session_state.get("visual_assignments") or {}
    assert 1 in assignments
    assert assignments[1]["result_key"] == "card-studio-photo"
    assert assignments[1]["source"] in {"source-a", "Automatic Scraper"}
    assert len(assignments[1]["bytes"]) > 0




def test_hindi_live_card_studio_exposes_translation_and_hindi_starter_copy():
    asset = {
        "bytes": _image_bytes(),
        "source": "source-a",
        "article_title": "India cricket image",
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [Topic(
        title="Test Hindi story",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/hindi-story",
    )]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_script_language"] = "hindi"
    at.session_state["live_approved_script"] = {
        "headline": "भारत की जीत",
        "language_used": "hindi",
        "script": [
            {"voiceover": "भारत ने शानदार जीत दर्ज की।"},
            {"voiceover": "टीम ने पूरे मैच में अच्छा प्रदर्शन किया।"},
            {"voiceover": "इस जीत से टीम का आत्मविश्वास बढ़ेगा।"},
        ],
    }
    at.session_state["live_approved_audio"] = {}
    at.session_state["live_subtitle_data"] = {}
    at.session_state["live_visual_option"] = "Option 5 · Card Studio"
    at.session_state["live_visual_result"] = {"assets": [asset]}
    at.session_state["live-standalone-card-studio-type"] = "Stat Highlight"
    at.run()

    assert not at.exception, at.exception
    assert any(button.label == "Stat Highlight" for button in at.button)
    assert any(button.label == "Option 5 · Card Studio" for button in at.button)
    assert at.session_state["live-standalone-card-studio-selected-type"] == "Stat Highlight"
    next(button for button in at.button if button.label == "Select image").click().run()

    assert not at.exception, at.exception
    assert any(button.label == "Translate card text to Hindi" for button in at.button)
    values = {field.label: field.value for field in at.text_input}
    assert values["Eyebrow"] == "करियर के आँकड़े"
    assert values["Headline"] == "रनों की शानदार पारी"
    assert values["Unit"] == "रन"



def test_live_scriptwriter_can_select_hindi_before_generating_angles():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [Topic(
        title="Test Hindi story",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/hindi-story",
    )]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "02 · Script"
    at.session_state["live_script_language"] = "english"
    at.session_state["live_script_data"] = None
    at.session_state["live_universal_angles"] = None
    at.run()

    assert not at.exception, at.exception
    language = next(pill for pill in at.pills if pill.label == "Script language")
    assert language.value == "English"
    language.set_value("Hindi").run()

    assert not at.exception, at.exception
    assert at.session_state["live_script_language"] == "hindi"
    assert at.session_state["live_universal_angles"] is None
    assert any(button.label == "Generate Script" for button in at.button)


def _dashboard_headline_test_script(language="english"):
    return {
        "language_used": language,
        "subject_name": "Shubman Gill",
        "headline": "Shubman Gill injury update explains what India's next ODI selection decision depends on and how the latest assessment may affect the squad",
        "titles": ["Shubman Gill injury update", "Why India's selection decision matters", "What the latest assessment means"],
        "seo_description": "The latest confirmed update on Shubman Gill before India's next ODI.",
        "hashtags": ["#Cricket", "#ShubmanGill", "#IndiaCricket"],
        "comment": "Should India wait for the medical assessment before selecting Gill?",
        "script": [
            {"voiceover": "Shubman Gill faces a new injury concern.", "narrative_role": "hook"},
            {"voiceover": "He was assessed after returning from training.", "narrative_role": "development"},
            {"voiceover": "The team will review his availability before the ODI.", "narrative_role": "consequence"},
        ],
    }


def test_test_scriptwriter_headline_is_dashboard_only_and_unlimited():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "02 · Scriptwriter"
    at.session_state["topics"] = [Topic(
        title="Shubman Gill injury update",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/gill",
    )]
    at.session_state["selected_topic"] = 0
    at.session_state["script_data"] = _dashboard_headline_test_script()
    at.run()

    assert not at.exception, at.exception
    headline = next(field for field in at.text_input if field.label == "Dashboard-only headline")
    assert len(headline.value) > 100
    assert not any(toggle.label == "Use opening headline" for toggle in at.toggle)


def test_live_scriptwriter_headline_is_dashboard_only_and_unlimited():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [Topic(
        title="Shubman Gill injury update",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/gill",
    )]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "02 · Script"
    at.session_state["live_script_data"] = _dashboard_headline_test_script()
    at.session_state["live_script_language"] = "english"
    at.session_state["live_approved_script"] = None
    at.run()

    assert not at.exception, at.exception
    headline = next(field for field in at.text_input if field.label == "Dashboard-only opening headline")
    assert len(headline.value) > 100
    assert not any(toggle.label == "Use opening headline" for toggle in at.toggle)



def test_live_automatic_scraper_runs_once_without_blocking_visual_qc(monkeypatch):
    import visual_fetcher

    started = Event()
    release = Event()
    calls = []

    def slow_scrape(story):
        calls.append(story)
        started.set()
        release.wait(timeout=5)
        return {"assets": [], "success_threshold": 10, "pages_scraped": 1}

    monkeypatch.setattr(visual_fetcher, "crawl_visuals", slow_scrape)
    topic = Topic(
        title="Test cricket story",
        description="Test story description",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/test-story",
    )
    script = {
        "headline": "Test story headline",
        "script": [
            {
                "voiceover": f"Test narration slide {number}.",
                "primary_entity": "Test player",
                "visual_intent": "player in cricket action",
                "specific_search_prompt": "Test player cricket",
            }
            for number in range(1, 5)
        ],
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [topic]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_script_data"] = script
    at.session_state["live_approved_script"] = script
    at.session_state["live_approved_audio"] = {}
    at.session_state["live_subtitle_data"] = {}
    at.session_state["live_visual_result"] = None
    at.session_state["live_visual_status"] = "idle"
    at.session_state["live_visual_option"] = "Option 3 · Real Image Search"

    try:
        at.run()
        assert not at.exception, at.exception
        assert started.wait(timeout=3), "The automatic scraper was not dispatched."
        assert at.session_state["live_visual_status"] == "running"
        assert any(button.label == "Search real images" for button in at.button)

        # An ordinary Streamlit rerun while scraping is in flight must not submit a duplicate.
        at.run()
        assert not at.exception, at.exception
        assert len(calls) == 1
        assert at.session_state["live_visual_status"] == "running"
    finally:
        release.set()
        future = at.session_state.get("live_visual_future")
        if future is not None:
            future.result(timeout=5)


def test_live_measured_audio_failure_is_sent_back_to_scriptwriter(monkeypatch):
    import script_writer

    observed = {}
    corrected = {
        "headline": "Gill injury update",
        "language_used": "hindi",
        "story_angle": "selection uncertainty",
        "titles": ["Gill update", "Selection question", "What happens next"],
        "seo_description": "The latest confirmed cricket update.",
        "hashtags": ["#Cricket"],
        "comment": "Should India wait for the assessment?",
        "script": [
            {
                "voiceover": "शुभमन गिल की फिटनेस पर चिंता है।",
                "primary_entity": "शुभमन गिल",
                "visual_intent": "शुभमन गिल cricket",
                "specific_search_prompt": "शुभमन गिल India cricket",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "डॉक्टर उनकी स्थिति की समीक्षा कर रहे हैं।",
                "primary_entity": "शुभमन गिल",
                "visual_intent": "medical assessment",
                "specific_search_prompt": "Shubman Gill medical assessment cricket",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "अगले मैच के लिए चयन अभी तय नहीं है।",
                "primary_entity": "India cricket team",
                "visual_intent": "India cricket team",
                "specific_search_prompt": "India cricket team squad",
                "sport_or_topic_category": "Cricket",
            },
        ],
    }

    def fake_write(cls, story, profile="cricket_india_asia", language="english", angle=None,
                   research_source=None, search_query=None, **kwargs):
        observed.update({
            "language": language,
            "angle": angle,
            "feedback": kwargs.get("validation_feedback"),
            "profile": profile,
        })
        return corrected

    monkeypatch.setattr(script_writer.ScriptWriter, "write", classmethod(fake_write))
    topic = Topic(
        title="Shubman Gill injury update",
        description="Gill is being assessed ahead of the next ODI.",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/gill-injury",
    )
    original = {
        **corrected,
        "language_used": "hindi",
        "script": [
            {**scene, "voiceover": "शुभमन गिल की फिटनेस पर लंबी चिंता है, और चयन अभी तय नहीं है।"}
            for scene in corrected["script"]
        ],
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [topic]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "03 · Audio + Subs"
    at.session_state["live_script_language"] = "hindi"
    at.session_state["live_script_data"] = original
    at.session_state["live_approved_script"] = original
    at.session_state["live_audio_engine_choice_v2"] = "Edge-TTS Neural"
    at.session_state["live_audio_status"] = "failed"
    at.session_state["live_audio_error"] = (
        "Hindi/Telugu first-slide audio is 5.83s; it must be no more than 5.2 seconds. "
        "Shorten Slide 1 in Scriptwriter and regenerate Audio."
    )
    at.session_state["live_handoff_error"] = at.session_state["live_audio_error"]
    at.session_state["live_approved_audio"] = None
    at.session_state["live_subtitle_data"] = None
    at.session_state["live_universal_angle_source"] = "Confirmed source evidence for the injury update."
    at.run()

    assert not at.exception, at.exception
    rewrite = next(
        button for button in at.button
        if button.label == "Rewrite Script for measured audio limits"
    )
    rewrite.click().run()
    assert not at.exception, at.exception
    assert observed["language"] == "hindi"
    assert observed["angle"] == "selection uncertainty"
    assert "5.83s" in observed["feedback"]
    assert "5.2 seconds" in observed["feedback"]
    assert "Rejected narration that produced this audio" in observed["feedback"]
    assert "शुभमन गिल की फिटनेस पर लंबी चिंता है" in observed["feedback"]
    assert observed["profile"] == "cricket_india_asia"
    assert at.session_state["live_stage"] == "02 · Script"
    assert at.session_state["live_approved_script"] is None
    assert at.session_state["live_script_data"]["headline"] == "Gill injury update"


def test_live_audio_runs_in_background_while_visual_qc_opens(monkeypatch):
    import audio
    import subtitles
    import visual_fetcher

    started = Event()
    release = Event()

    def slow_audio(*_args, **_kwargs):
        started.set()
        release.wait(timeout=5)
        return {"audio_path": "fake-audio.wav", "duration": 5.0}

    monkeypatch.setattr(audio, "generate_audio", slow_audio)
    monkeypatch.setattr(audio, "approve_audio", lambda value: {"approved": True, **value})
    monkeypatch.setattr(subtitles, "generate_subtitles", lambda _script, _audio: {"subtitles": True})
    monkeypatch.setattr(
        visual_fetcher,
        "crawl_visuals",
        lambda _story: {"assets": [], "success_threshold": 10, "pages_scraped": 1},
    )
    topic = Topic(
        title="Test cricket story",
        description="Test story description",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/test-story",
    )
    script = {
        "headline": "Test story headline",
        "language_used": "english",
        "script": [
            {
                "voiceover": f"Test narration slide {number}.",
                "primary_entity": "Test player",
                "visual_intent": "player in cricket action",
                "specific_search_prompt": "Test player cricket",
            }
            for number in range(1, 5)
        ],
    }
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [topic]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "03 · Audio + Subs"
    at.session_state["live_script_data"] = script
    at.session_state["live_approved_script"] = script
    at.session_state["live_audio_engine_choice_v2"] = "Edge-TTS Neural"
    at.session_state["live_audio_status"] = "idle"
    at.session_state["live_audio_future"] = None
    at.session_state["live_visual_option"] = "Option 3 · Real Image Search"
    at.session_state["live_approved_audio"] = None
    at.session_state["live_subtitle_data"] = None
    at.session_state["live_visual_result"] = None
    at.session_state["live_visual_status"] = "idle"

    try:
        at.run()
        assert not at.exception, at.exception
        start_button = next(button for button in at.button if button.label == "Start Audio + Subtitles in Background")
        start_button.click().run()
        assert not at.exception, at.exception
        assert started.wait(timeout=3), "The audio worker was not dispatched."
        assert at.session_state["live_stage"] == "04 · Visuals + Render"
        assert at.session_state["live_audio_status"] == "running"
        assert any(button.label == "Search real images" for button in at.button)
        assert at.session_state["live_visual_status"] in {"running", "complete"}
    finally:
        release.set()
        future = at.session_state.get("live_audio_future")
        if future is not None:
            future.result(timeout=5)

    at.run()
    assert not at.exception, at.exception
    assert at.session_state["live_audio_status"] == "complete"
    assert at.session_state["live_approved_audio"]["approved"] is True
    assert at.session_state["live_subtitle_data"] == {"subtitles": True}



def _indic_script_package(story_angle="selection uncertainty"):
    return {
        "headline": "Gill fitness decision",
        "story_angle": story_angle,
        "language_used": "hindi",
        "subject_name": "शुभमन गिल",
        "titles": ["Gill fitness update", "India selection decision", "Latest cricket news"],
        "seo_description": "The latest confirmed update on Shubman Gill's fitness.",
        "hashtags": ["#Cricket"],
        "comment": "Should India wait for the assessment?",
        "script": [
            {
                "voiceover": "शुभमन गिल की फिटनेस पर चिंता है।",
                "primary_entity": "शुभमन गिल",
                "visual_intent": "शुभमन गिल cricket",
                "specific_search_prompt": "शुभमन गिल India cricket",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "डॉक्टर उनकी स्थिति की समीक्षा कर रहे हैं।",
                "primary_entity": "शुभमन गिल",
                "visual_intent": "medical assessment",
                "specific_search_prompt": "Shubman Gill medical assessment cricket",
                "sport_or_topic_category": "Cricket",
            },
            {
                "voiceover": "अगले मैच के लिए चयन अभी तय नहीं है।",
                "primary_entity": "India cricket team",
                "visual_intent": "India cricket team",
                "specific_search_prompt": "India cricket team squad",
                "sport_or_topic_category": "Cricket",
            },
        ],
    }


def test_test_scriptwriter_same_angle_retry_receives_previous_failure(monkeypatch):
    import script_writer

    observed = []
    attempts = {"count": 0}
    topic = Topic(
        title="Shubman Gill injury update",
        description="Gill is being assessed ahead of the next ODI.",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/gill-retry",
    )
    angle = {
        "title": "Selection uncertainty",
        "description": "Will India wait for the final fitness assessment?",
        "evidence_basis": "The assessment is still pending.",
    }
    selected_angle = (
        f'{angle["title"]}: {angle["description"]}'
    )

    def fake_write(cls, story, profile="cricket_india_asia", language="english",
                   angle=None, research_source=None, search_query=None, **kwargs):
        observed.append(kwargs.get("validation_feedback"))
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError(
                "Indic generation timing preflight: Slide 1 has 9 whitespace-separated tokens."
            )
        return _indic_script_package(selected_angle)

    monkeypatch.setattr(script_writer.ScriptWriter, "write", classmethod(fake_write))
    story_key = hashlib.sha1(f"{topic.title}|{topic.url}".encode("utf-8")).hexdigest()[:12]
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["factory_format"] = "shorts"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "02 · Scriptwriter"
    at.session_state["topic_desk_profile"] = "cricket_india_asia"
    at.session_state["topics"] = [topic]
    at.session_state["selected_topic"] = 0
    at.session_state["script_language"] = "Hindi"
    at.session_state["script_data"] = None
    at.session_state["approved_script"] = None
    at.session_state["test_universal_angles"] = [angle]
    at.session_state["test_universal_angle_source"] = "Fitness assessment remains pending."
    at.session_state["test_universal_angle_selected"] = 0
    at.session_state["test_universal_angle_custom"] = ""
    at.session_state["test_universal_angle_story_key"] = story_key
    at.run()

    assert not at.exception, at.exception
    generate = next(button for button in at.button if button.label == "⚡ Generate Viral Short from Selected Lens")
    generate.click().run()
    assert not at.exception, at.exception
    assert "Slide 1 has 9" in at.session_state["test_scriptwriter_retry"]["feedback"]

    generate = next(button for button in at.button if button.label == "⚡ Generate Viral Short from Selected Lens")
    generate.click().run()
    assert not at.exception, at.exception
    assert len(observed) == 2
    assert observed[0] is None
    assert "Slide 1 has 9 whitespace-separated tokens" in observed[1]
    assert at.session_state["script_data"]["language_used"] == "hindi"
    assert "test_scriptwriter_retry" not in at.session_state


def test_test_audio_timing_rewrite_sends_error_and_rejected_narration(monkeypatch):
    import audio
    import script_writer

    observed = {}

    def fail_audio(*_args, **_kwargs):
        raise ValueError(
            "Hindi/Telugu first-slide audio is 6.37s; it must be no more than 5.2 seconds. "
            "Shorten Slide 1 in Scriptwriter and regenerate Audio."
        )

    def fake_write(cls, story, profile="cricket_india_asia", language="english",
                   angle=None, research_source=None, search_query=None, **kwargs):
        observed.update({
            "profile": profile,
            "language": language,
            "angle": angle,
            "feedback": kwargs.get("validation_feedback"),
        })
        return _indic_script_package(angle or "selection uncertainty")

    monkeypatch.setattr(audio, "generate_audio", fail_audio)
    monkeypatch.setattr(script_writer.ScriptWriter, "write", classmethod(fake_write))
    topic = Topic(
        title="Shubman Gill injury update",
        description="Gill is being assessed ahead of the next ODI.",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/gill-audio-retry",
    )
    original = _indic_script_package("selection uncertainty")
    original["script"][0]["voiceover"] = "शुभमन गिल की फिटनेस पर लंबी चिंता है, और चयन अभी तय नहीं है।"
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["factory_format"] = "shorts"
    at.session_state["test_production_line"] = "deep_dive"
    at.session_state["test_stage"] = "03 · Audio"
    at.session_state["topic_desk_profile"] = "cricket_india_asia"
    at.session_state["topics"] = [topic]
    at.session_state["selected_topic"] = 0
    at.session_state["script_data"] = original
    at.session_state["approved_script"] = original
    at.session_state["audio_data"] = None
    at.session_state["approved_audio"] = None
    at.session_state["audio_engine_choice_v2"] = "Edge-TTS Neural"
    at.session_state["audio_language"] = "Hindi"
    at.session_state["test_universal_angle_source"] = "Fitness assessment remains pending."
    at.session_state["test_universal_angles"] = [{
        "title": "Selection uncertainty",
        "description": "Will India wait for the fitness assessment?",
        "evidence_basis": "The final fitness assessment is still pending.",
    }]
    at.session_state["test_universal_angle_selected"] = 0
    at.session_state["test_universal_angle_custom"] = ""
    at.run()

    assert not at.exception, at.exception
    next(button for button in at.button if button.label == "Generate audio").click().run()
    assert not at.exception, at.exception
    assert "6.37s" in at.session_state["test_audio_error"]
    rewrite = next(button for button in at.button if button.label == "Rewrite Script for measured audio limits")
    rewrite.click().run()

    assert not at.exception, at.exception
    assert observed["profile"] == "cricket_india_asia"
    assert observed["language"] == "hindi"
    assert observed["angle"] == "Selection uncertainty: Will India wait for the fitness assessment?"
    assert "6.37s" in observed["feedback"]
    assert "5.2 seconds" in observed["feedback"]
    assert "Rejected narration that produced this audio" in observed["feedback"]
    assert "शुभमन गिल की फिटनेस पर लंबी चिंता है" in observed["feedback"]
    assert at.session_state["test_stage"] == "02 · Scriptwriter"
    assert at.session_state["approved_script"] is None
    assert at.session_state["script_data"]["headline"] == "Gill fitness decision"


def test_live_pipeline_allows_direct_stage_selection_after_topic_choice():
    topic = Topic(
        title="Test cricket story",
        description="Test story description.",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        url="https://example.com/live-stage-navigation",
    )
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["factory_format"] = "shorts"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [topic]
    at.session_state["live_selected_topic"] = 0
    at.session_state["live_stage"] = "02 · Script"
    at.session_state["live_script_data"] = None
    at.session_state["live_approved_script"] = None
    at.session_state["live-stage-switcher"] = "03 · Audio + Subs"
    at.run()

    assert not at.exception, at.exception
    assert at.session_state["live_stage"] == "03 · Audio + Subs"
    assert any("Approve the Scriptwriter before generating Audio" in warning.value for warning in at.warning)



def test_test_and_live_stage_pickers_do_not_mix_default_with_session_state():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

    test_picker = source.index('selected = st.pills(\n                "Pipeline",')
    test_picker_end = source.index(
        "if selected != st.session_state.test_stage:",
        test_picker,
    )
    test_picker_call = source[test_picker:test_picker_end]
    assert 'key="test-stage-switcher"' in test_picker_call
    assert "default=" not in test_picker_call

    live_picker = source.index('selected = st.pills(\n                    "Live pipeline",')
    live_picker_end = source.index(
        'if selected != st.session_state.get("live_stage"):',
        live_picker,
    )
    live_picker_call = source[live_picker:live_picker_end]
    assert 'key="live-stage-switcher"' in live_picker_call
    assert "default=" not in live_picker_call
    assert '"test-stage-switcher" not in st.session_state' in source
    assert '"live-stage-switcher" not in st.session_state' in source

