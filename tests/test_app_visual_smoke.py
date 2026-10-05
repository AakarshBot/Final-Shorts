from io import BytesIO
from pathlib import Path

from PIL import Image
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


def test_top5_standalone_visual_qc_exposes_all_seven_options():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "test"
    at.session_state["test_production_line"] = "top_5"
    at.session_state["test_stage"] = "04 · Visuals"
    at.run()

    assert not at.exception, at.exception
    option_sets = [
        [str(option) for option in pills.options]
        for pills in at.pills
        if pills.options
    ]
    eight = next(
        options
        for options in option_sets
        if options[:8] == [
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Manual Fetcher",
            "Option 4 · AI Generation",
            "Option 5 · Stats Card",
            "Option 6 · Quote Card",
            "Option 7 · Subject Cutout",
            "Option 8 · Body Card · WIP",
        ]
    )

    assert eight == [
        "Option 1 · Automatic Scraper",
        "Option 2 · Manual Scraper",
        "Option 3 · Manual Fetcher",
        "Option 4 · AI Generation",
        "Option 5 · Stats Card",
        "Option 6 · Quote Card",
        "Option 7 · Subject Cutout",
        "Option 8 · Body Card · WIP",
        "Option 9 · Manual Subject Cutout",
    ]


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


def test_live_cricket_text_cutout_loads_and_switches_images():
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
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [{"title": "Test story"}]
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_approved_script"] = {
        "headline": "Test headline",
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
    at.run()

    assert not at.exception, at.exception
    option_sets = [
        [str(option) for option in pills.options]
        for pills in at.pills
        if pills.options
    ]
    assert [
        "Option 1 · Automatic Scraper",
        "Option 2 · Manual Scraper",
        "Option 3 · Real Image Search",
        "Option 4 · AI Generation",
        "Option 5 · Stats Card",
        "Option 6 · Quote Card",
        "Option 7 · Text Cutout",
    ] in option_sets
    assert len([button for button in at.button if button.label == "Crop / reposition"]) == 2
    assert any("Polygon points" == field.label for field in at.text_input)
    assert len([button for button in at.button if button.label == "Select image"]) == 2

    select_buttons = [button for button in at.button if button.label == "Select image"]
    select_buttons[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_text_cutout_image_selection"]["bytes"] == assets[0]["bytes"]

    select_buttons = [button for button in at.button if button.label == "Select image"]
    select_buttons[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_text_cutout_image_selection"]["bytes"] == assets[1]["bytes"]

    at.session_state["live_text_cutout_headline"] = "Alternate headline"
    at.session_state["live_text_cutout_mode"] = "Behind Subject"
    at.session_state["live_text_cutout_font"] = "Oswald"
    at.session_state["live_text_cutout_style"] = "Long Fade"
    at.run()
    assert not at.exception, at.exception


def test_live_text_cutout_prefers_the_existing_9x16_crop():
    asset = {
        "bytes": _image_bytes((40, 50, 60)),
        "source": "source-a",
        "article_title": "Image A",
    }
    cropped = _image_bytes((200, 210, 220), size=(1080, 1920))
    identity = "|".join([
        "live-auto",
        str(asset.get("source_page_url") or asset.get("url") or ""),
        str(asset.get("article_title") or asset.get("model") or ""),
        "0",
    ])
    import hashlib

    asset_key = f"live-auto-{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}"

    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["app_mode"] = "live"
    at.session_state["live_production_line"] = "deep_dive"
    at.session_state["live_desk"] = "cricket"
    at.session_state["live_cricket_profile"] = "cricket_india_asia"
    at.session_state["live_topics_profile"] = "cricket_india_asia"
    at.session_state["live_topics"] = [{"title": "Test story"}]
    at.session_state["live_stage"] = "04 · Visuals + Render"
    at.session_state["live_approved_script"] = {
        "headline": "Test headline",
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
    at.session_state["live_visual_crops"] = {asset_key: cropped}
    at.run()

    select = next(button for button in at.button if button.label == "Select image")
    select.click().run()
    assert not at.exception, at.exception
    assert at.session_state["live_text_cutout_image_selection"]["bytes"] == cropped
