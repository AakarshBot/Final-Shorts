from io import BytesIO
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


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


def test_stats_card_visual_screen_loads():
    at = _run_visual_option("Option 5 · Stats Card")
    assert not at.exception, at.exception


def test_quote_card_visual_screen_loads():
    at = _run_visual_option("Option 6 · Quote Card")
    assert not at.exception, at.exception
