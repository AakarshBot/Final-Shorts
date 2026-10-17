from pathlib import Path
import re

import renderer


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_no_timed_refresh_or_polling():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    refresh_patterns = (
        r"\bst_autorefresh\b",
        r"\brun_every\s*=",
        r"\bsetInterval\s*\(",
        r"\bsetTimeout\s*\(",
        r"\bthreading\.Timer\s*\(",
        r"\btime\.sleep\s*\(",
        r"\basyncio\.sleep\s*\(",
    )
    for pattern in refresh_patterns:
        assert re.search(pattern, app_source) is None, f"Unexpected dashboard timer/polling: {pattern}"

    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'fileWatcherType = "none"' in config
    assert "runOnSave = false" in config


def test_crop_dialog_uses_bounded_canvas_and_explicit_crop_confirmation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _crop_visual_dialog(")
    end = app_source.index("@st.fragment", start)
    crop_source = app_source[start:end]

    assert "max_canvas_width = 1600" in crop_source
    assert "realtime_update=False" in crop_source
    assert "Double-click to confirm the crop selection." in crop_source


def test_visual_pool_work_uses_cached_validation_and_thumbnails():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "@st.cache_data(max_entries=256, show_spinner=False)" in app_source
    assert "def _is_valid_image_payload(value: bytes)" in app_source
    assert "not _is_valid_image_payload(bytes(raw))" in app_source
    assert "@st.cache_data(max_entries=128, show_spinner=False)" in app_source
    assert "def _fit_visual_preview_bytes(" in app_source


def test_manual_subject_cutout_reuses_layout_geometry(monkeypatch):
    font_path = ROOT / "fonts" / "BarlowCondensed-Black.ttf"
    font_bytes = font_path.read_bytes()
    monkeypatch.setattr(renderer, "_manual_subject_font_bytes", lambda _name: font_bytes)
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()

    calls = 0
    original = renderer._manual_subject_cutout_layout_data_uncached

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(renderer, "_manual_subject_cutout_layout_data_uncached", counted)
    polygon = [
        (80, 700),
        (1000, 700),
        (1000, 1200),
        (80, 1200),
    ]

    first = renderer._manual_subject_cutout_layout_data(
        "India win today",
        polygon,
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )
    second = renderer._manual_subject_cutout_layout_data(
        "  INDIA   win today ",
        tuple(polygon),
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert calls == 1
    assert first is second
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()
