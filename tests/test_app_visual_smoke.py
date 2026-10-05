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


def _image_bytes() -> bytes:
    image = Image.new("RGB", (600, 900), (40, 50, 60))
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
    seven = next(
        options
        for options in option_sets
        if options[:7] == [
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Real Image Search · WIP",
            "Option 4 · AI Generation",
            "Option 5 · Stats Card",
            "Option 6 · Quote Card",
            "Option 7 · Subject Cutout",
        ]
    )

    assert seven == [
        "Option 1 · Automatic Scraper",
        "Option 2 · Manual Scraper",
        "Option 3 · Real Image Search · WIP",
        "Option 4 · AI Generation",
        "Option 5 · Stats Card",
        "Option 6 · Quote Card",
        "Option 7 · Subject Cutout",
    ]
