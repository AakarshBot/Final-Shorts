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


def test_crop_dialog_shows_full_source_and_applies_free_crop_to_9x16():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _crop_visual_dialog(")
    end = app_source.index("@st.fragment", start)
    crop_source = app_source[start:end]

    assert "max_canvas_width=1600" in crop_source
    assert "realtime_update=True" in crop_source
    assert "aspect_ratio=None" in crop_source
    assert "Reset rectangle to centred 9:16" in crop_source
    assert "Use original image" in crop_source
    assert "final_preview = cropped.convert(\"RGB\").resize((1080, 1920)" in crop_source
    assert "crop-reset-" in crop_source
    assert "def _prepare_crop_dialog_canvas(" in app_source
    assert "@st.cache_data(max_entries=4, show_spinner=False)" in app_source
    assert "invalidate_card_studio_results_for_source(" in crop_source
    assert "card_selector=True" in app_source


def test_applied_9x16_crop_thumbnails_preserve_the_entire_final_frame():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _fit_visual_preview_bytes(")
    end = app_source.index("def _delete_visual_asset(", start)
    preview_source = app_source[start:end]
    assert preview_source.count("abs(current_ratio - (9 / 16)) < 0.005") == 2
    assert preview_source.count("ImageOps.contain(image, (width, height)") == 2
    assert "preview.paste(fitted" in preview_source


def test_card_studio_receives_original_visuals_and_uses_an_independent_crop_store():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _visual_pool_entries(")
    end = app_source.index("def _render_card_studio(", start)
    pool_source = app_source[start:end]
    assert "raw = asset.get(\"bytes\")" in pool_source
    assert "crop_store.get(asset_key)" not in pool_source
    studio_source = app_source[app_source.index("def _render_card_studio("):]
    assert 'crop_store_name = "live_card_studio_crops" if live else "card_studio_crops"' in studio_source
    assert 'crop_store_name = "test_top5_card_studio_visual_crops"' in studio_source


def test_crop_assignment_store_is_pipeline_specific():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index('@st.dialog("Crop visual"')
    end = app_source.index("@st.fragment", start)
    crop_source = app_source[start:end]
    assert '"visual_crops": "visual_assignments"' in crop_source
    assert '"live_visual_crops": "live_visual_assignments"' in crop_source
    assert '"test_top5_visual_crops": "test_top5_visual_assignments"' in crop_source


def test_visual_pool_work_uses_cached_validation_and_thumbnails():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "@st.cache_data(max_entries=256, show_spinner=False)" in app_source
    assert "def _is_valid_image_payload(value: bytes)" in app_source
    assert "not _is_valid_image_payload(bytes(raw))" in app_source
    assert "@st.cache_data(max_entries=128, show_spinner=False)" in app_source
    assert "def _fit_visual_preview_bytes(" in app_source


def test_layout_search_prunes_line_counts_that_cannot_fit(monkeypatch):
    font_path = ROOT / "fonts" / "BarlowCondensed-Black.ttf"
    font_bytes = font_path.read_bytes()
    monkeypatch.setattr(renderer, "_manual_subject_font_bytes", lambda _name: font_bytes)
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()

    original_combinations = renderer.combinations
    generated = 0

    def counted_combinations(values, count):
        nonlocal generated
        results = list(original_combinations(values, count))
        generated += len(results)
        return iter(results)

    monkeypatch.setattr(renderer, "combinations", counted_combinations)
    headline = "India cricket team wins a remarkable series after another historic performance today"
    data = renderer._manual_subject_cutout_layout_data(
        headline,
        ((60, 700), (1020, 700), (1020, 900), (60, 900)),
        140,
        "Barlow Condensed",
        "Crisp Outline",
    )

    assert generated < 100
    assert data["layouts"] == []
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()


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


def test_card_studio_exposes_manual_composition_controls_for_all_editorial_cards():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _render_card_studio(")
    end = app_source.index("def _top5_fit_preview(", start)
    studio_source = app_source[start:end]

    assert "CARD_LAYOUT_POSITIONS" in studio_source
    assert "CARD_CONTRAST_TREATMENTS" in studio_source
    assert '"Text / gradient position"' in studio_source
    assert '"Contrast treatment"' in studio_source
    assert 'data["layout_position"] = layout_position' in studio_source
    assert 'data["contrast_treatment"] = contrast_treatment' in studio_source
    assert "invalidate_card_studio_result_for_composition(" in studio_source
    assert "Card type or composition changed. Render the card again" in studio_source
    assert "Text Subject Cutout is unchanged." in studio_source


def test_live_card_studio_uses_approved_card_allowlist():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _render_card_studio(")
    end = app_source.index("def _top5_fit_preview(", start)
    studio_source = app_source[start:end]

    assert "card_types = LIVE_CARD_TYPES if live else TEST_CARD_TYPES" in studio_source


def test_live_rendered_video_path_survives_upload_qc_reruns():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    # Live render output paths are anchored to app.py's repository folder,
    # and the same absolute path is kept in session state for Upload QC.
    assert app_source.count(
        'Path(__file__).resolve().parent / "output" / "live" / f"{story_id}.mp4"'
    ) == 2
    assert (
        'Path(__file__).resolve().parent / "output" / "live" / "top5" / f"{key}.mp4"'
        in app_source
    )
    assert app_source.count(
        "st.session_state.live_rendered_video_path = str(output.resolve())"
    ) == 3

    upload_start = app_source.index("def _render_live_upload():")
    upload_end = app_source.index("def render_live_top5():", upload_start)
    upload_source = app_source[upload_start:upload_end]
    assert 'stored_video_path = st.session_state.get("live_rendered_video_path")' in upload_source
    assert "if video_path is not None and not video_path.is_absolute():" in upload_source
    assert "video_path.stat().st_size <= 0" in upload_source

def test_shorts_renderer_uses_faster_encode_preset_without_changing_quality_target():
    renderer_source = (ROOT / "renderer.py").read_text(encoding="utf-8")
    assert '"-preset", "veryfast"' in renderer_source
    assert '"-crf", "18"' in renderer_source
    assert renderer.FPS == 30


def test_motion_profile_is_cached_by_visual_seed():
    renderer._motion_profile.cache_clear()

    first = renderer._motion_profile("performance-regression-seed")
    second = renderer._motion_profile("performance-regression-seed")
    info = renderer._motion_profile.cache_info()

    assert first == second
    assert info.misses == 1
    assert info.hits == 1
    renderer._motion_profile.cache_clear()


def test_render_loop_does_not_rebuild_motion_seed_or_hash_image_each_frame():
    source = (ROOT / "renderer.py").read_text(encoding="utf-8")
    render_start = source.index("def render_production_video(")
    render_end = source.find("\ndef ", render_start + 5)
    if render_end < 0:
        render_end = len(source)
    render_source = source[render_start:render_end]
    preparation_end = render_source.index("    def frames():")
    preparation = render_source[:preparation_end]
    frame_loop = render_source[preparation_end:]

    assert '"motion_seed": motion_seed' in preparation
    assert "hashlib.sha1(image.tobytes()).hexdigest()" in preparation
    assert "hashlib.sha1(base_image.tobytes()).hexdigest()" not in frame_loop
    assert 'visual["motion_seed"]' in frame_loop


def test_longform_render_uses_monotonic_scene_cursor():
    source = (ROOT / "longform_renderer.py").read_text(encoding="utf-8")
    start = source.index("        def frame_generator():")
    end = source.index("\n        # Pipe frames", start)
    frame_source = source[start:end]

    assert "scene_index = 0" in frame_source
    assert "while (" in frame_source
    assert "for sc in prepared_bases" not in frame_source
    assert "cue_index = 0" in frame_source
    assert "billboard_index = 0" in frame_source
    assert "for c in cues" not in frame_source
    assert "for bb in act_billboards" not in frame_source
