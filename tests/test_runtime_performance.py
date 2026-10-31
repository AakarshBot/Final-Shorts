from pathlib import Path
import re

import renderer


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_uses_only_scoped_visual_job_monitors_not_global_polling():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    refresh_patterns = (
        r"\bst_autorefresh\b",
        r"\bsetInterval\s*\(",
        r"\bsetTimeout\s*\(",
        r"\bthreading\.Timer\s*\(",
        r"\btime\.sleep\s*\(",
        r"\basyncio\.sleep\s*\(",
    )
    for pattern in refresh_patterns:
        assert re.search(pattern, app_source) is None, f"Unexpected dashboard timer/polling: {pattern}"

    # Timed reruns are allowed only in narrow watchers for active background jobs.
    # They do not rerun the entire dashboard while idle.
    assert app_source.count("@st.fragment(run_every=1.0)") == 2

    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'fileWatcherType = "none"' in config
    assert "runOnSave = false" in config


def test_crop_dialog_shows_full_source_and_applies_free_crop_to_9x16():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def _crop_visual_dialog(")
    end = app_source.index("@st.fragment", start)
    crop_source = app_source[start:end]

    assert "_prepare_crop_dialog_canvas(bytes(image_bytes))" in crop_source
    helper_start = app_source.index("def _prepare_crop_dialog_canvas(")
    helper_end = app_source.index("def _reset_crop_dialog_rectangle(", helper_start)
    helper_source = app_source[helper_start:helper_end]
    assert "return image, _largest_9x16_crop_coords(image), original_size" in helper_source
    assert "image.resize(" not in helper_source
    coords_start = app_source.index("def _largest_9x16_crop_coords(")
    coords_end = app_source.index("@st.cache_data(max_entries=4", coords_start)
    assert "return (left, left + width, top, top + height)" in app_source[coords_start:coords_end]
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
    assert "from PIL import Image, ImageOps" in app_source
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
    delete_start = app_source.index("def _delete_visual_asset(")
    delete_end = app_source.index("def _attach_visual_asset(", delete_start)
    delete_source = app_source[delete_start:delete_end]
    assert 'setdefault("live_card_studio_crops" if live else "card_studio_crops", {})' in delete_source
    assert 'setdefault("test_top5_card_studio_crops", {})' in delete_source


def test_card_studio_offers_explicit_story_and_manual_prompt_generation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    studio_source = app_source[app_source.index("def _render_card_studio("):]
    assert "Fill fields from story" in studio_source
    assert "Generate fields from prompt" in studio_source
    assert "generate_card_copy(card_type, story_context, target_language=card_language)" in studio_source
    assert "manual_prompt=manual_prompt.strip()" in studio_source
    script_source = (ROOT / "script_writer.py").read_text(encoding="utf-8")
    assert "def generate_card_copy(" in script_source
    assert "natural, concise Hindi using Devanagari script" in script_source
    assert "natural, concise Telugu using Telugu script" in script_source


def test_crop_assignment_store_is_pipeline_specific():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index('@st.dialog("Crop visual"')
    end = app_source.index("@st.fragment", start)
    crop_source = app_source[start:end]
    assert '"visual_crops": "visual_assignments"' in crop_source
    assert '"live_visual_crops": "live_visual_assignments"' in crop_source
    assert '"test_top5_visual_crops": "test_top5_visual_assignments"' in crop_source
    assert '"card_studio_crops": "visual_assignments"' in crop_source
    assert '"live_card_studio_crops": "live_visual_assignments"' in crop_source
    assert '"test_top5_card_studio_visual_crops": "test_top5_visual_assignments"' in crop_source
    assert '"test_top5_card_studio_crops": "test_top5_visual_assignments"' in crop_source
    assert 'if crop_store in {"live_visual_crops", "live_card_studio_crops"}' in crop_source
    assert 'elif crop_store in {"visual_crops", "card_studio_crops"}' in crop_source
    assert 'assignment["bytes"] = crop_bytes' in crop_source
    assert 'assignment["bytes"] = bytes(image_bytes)' in crop_source
    assert crop_source.count('(assignment.get("result_key") == "card-studio-photo") == card_studio_crop') == 2


def test_visual_pool_work_uses_cached_validation_and_thumbnails():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "@st.cache_data(max_entries=256, show_spinner=False)" in app_source
    assert "def _is_valid_image_payload(value: bytes)" in app_source
    assert "not _is_valid_image_payload(bytes(raw))" in app_source
    assert "@st.cache_data(max_entries=128, show_spinner=False)" in app_source
    assert "def _fit_visual_preview_bytes(" in app_source


def test_balanced_text_wrap_handles_long_headlines_without_combination_search(monkeypatch):
    font_path = ROOT / "fonts" / "BarlowCondensed-Black.ttf"
    font_bytes = font_path.read_bytes()
    monkeypatch.setattr(renderer, "_manual_subject_font_bytes", lambda _name: font_bytes)
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()
    headline = "India cricket team wins a remarkable series after another historic performance today"
    data = renderer._manual_subject_cutout_layout_data(
        headline,
        ((60, 700), (1020, 700), (1020, 1500), (60, 1500)),
        100,
        "Barlow Condensed",
        "Crisp Outline",
    )
    assert data["layouts"]
    assert " ".join(word for line in data["layouts"][0]["lines"] for word in line.split()) == headline.upper()
    assert len({placement[2] for placement in data["layouts"][0]["placements"]}) == 1
    renderer._manual_subject_cutout_layout_data_cached.cache_clear()




def test_manual_subject_cutout_editor_uses_the_polygon_as_its_text_boundary():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer_source = (ROOT / "renderer.py").read_text(encoding="utf-8")

    assert '<polygon id="polygon"' in app_source
    assert 'id="text-box"' not in app_source
    assert "The polygon itself is the text boundary." in app_source
    assert "ImageDraw.Draw(polygon_mask).polygon(points, fill=255)" in renderer_source
    assert "vertical_clearance[line_top] >= ink_height" in renderer_source
    assert "stretch_english_lines" not in renderer_source
    assert "stretch_spaces" not in renderer_source


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

    # Standard Live now has one canonical background render action; Top-5 keeps its separate output directory.
    assert app_source.count(
        'Path(__file__).resolve().parent / "output" / "live" / f"{story_id}.mp4"'
    ) == 1
    assert (
        'Path(__file__).resolve().parent / "output" / "live" / "top5" / f"{key}.mp4"'
        in app_source
    )
    worker_start = app_source.index("def _live_render_final_short(")
    poller_start = app_source.index("def _poll_live_background_jobs(", worker_start)
    poller_end = app_source.index("@st.fragment", poller_start)
    render_worker = app_source[worker_start:poller_start]
    completion_poller = app_source[poller_start:poller_end]

    # The worker returns the rendered path; the dashboard stores that result
    # in Session State only after the Future completes.
    assert "return str(output.resolve())" in render_worker
    assert "st.session_state.live_rendered_video_path = result" in completion_poller
    assert "st.session_state[future_key] = None" in completion_poller

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


def test_local_image_upload_preserves_original_bytes_and_image_dimensions():
    import ast
    import hashlib
    from io import BytesIO
    from PIL import Image, ImageOps

    app_path = ROOT / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    helper_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_local_image_assets"
    )
    namespace = {
        "BytesIO": BytesIO,
        "Image": Image,
        "ImageOps": ImageOps,
        "Path": Path,
        "hashlib": hashlib,
    }
    exec(compile(ast.Module(body=[helper_node], type_ignores=[]), str(app_path), "exec"), namespace)

    image = Image.new("RGB", (1440, 2160), (35, 75, 115))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    original = buffer.getvalue()

    class LocalUpload:
        name = "my-original-frame.png"

        def getvalue(self):
            return original

    assets = namespace["_local_image_assets"]([LocalUpload()])
    assert len(assets) == 1
    assert assets[0]["bytes"] == original
    assert assets[0]["hash"] == hashlib.sha256(original).hexdigest()
    assert assets[0]["width"] == 1440
    assert assets[0]["height"] == 2160
    assert assets[0]["original_bytes_preserved"] is True


def test_visual_studio_offers_local_upload_across_pipelines():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Option 6 · Upload Local Image"' in app_source
    assert 'key="test-local-image-upload"' in app_source
    assert 'key="live-local-image-upload"' in app_source
    assert 'key="test-top5-playground-local-upload"' in app_source
    assert 'key=f"test-top5-local-upload-{active_slide}"' in app_source
    assert 'key=f"live-top5-local-upload-{active_slide}"' in app_source



def test_six_visual_source_cards_use_two_balanced_rows_and_show_upload_quality():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '(":material/upload_file:", "Upload original image files")' in app_source
    assert '<div class="section-count">6 ways to build</div>' in app_source
    assert "for start in range(0, len(options), 3):" in app_source
    assert "st.columns(min(3, len(options) - start), gap=\"small\")" in app_source
    assert '<div class="section-count">5 Image Sources</div>' in app_source
    assert 'Original source: {source_width:,} × {source_height:,} px' in app_source


def test_manual_uploaded_images_remain_available_to_card_studio():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    pool_start = app_source.index("def _visual_pool_entries(")
    pool_end = app_source.index("def _render_card_studio(", pool_start)
    pool_source = app_source[pool_start:pool_end]
    assert '("local_visual_result", "local-upload", "Local Upload")' in pool_source
    assert '("live_local_visual_result", "local-upload", "Local Upload")' in pool_source

    workspace_start = app_source.index("def _render_two_pane_visual_workspace(")
    workspace_end = app_source.index("def _render_live_visuals(", workspace_start)
    workspace_source = app_source[workspace_start:workspace_end]
    assert 'st.session_state.local_visual_result = {"assets": local_assets}' in workspace_source
    assert 'st.session_state.live_local_visual_result = {"assets": local_assets}' in workspace_source


def test_visual_fetchers_run_outside_the_dashboard_interaction_thread():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    auto_start = app_source.index("def render_visuals_crawler(")
    auto_end = app_source.index("def _render_manual_crawler(", auto_start)
    assert "_live_background_executor().submit(crawl_visuals, story)" in app_source[auto_start:auto_end]

    manual_start = app_source.index("def _render_manual_crawler(")
    manual_end = app_source.index("def _render_manual_real_images(", manual_start)
    assert "_live_background_executor().submit(manual_crawl_visuals, query)" in app_source[manual_start:manual_end]

    real_start = app_source.index("def _render_manual_real_images(")
    real_end = app_source.index("def _render_manual_ai_images(", real_start)
    assert "_live_background_executor().submit(search_images, query)" in app_source[real_start:real_end]

    ai_start = app_source.index("def _render_manual_ai_images(")
    ai_end = app_source.index("def render_visuals(", ai_start)
    assert "_live_background_executor().submit(generate_images, query)" in app_source[ai_start:ai_end]
    assert "def _render_visual_job_status(" in app_source
    assert "results are collected on the next dashboard interaction" not in app_source
    assert "def _watch_live_background_completion()" in app_source
    assert "def _watch_test_visual_fetch_completion()" in app_source


def test_manual_story_intake_is_wired_to_existing_pipeline_candidates():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'manual_topic = _render_manual_story_intake("test-topic"' in app_source
    assert 'manual_topic = _render_manual_story_intake("live-story-desk"' in app_source
    assert 'manual_topic = _render_manual_story_intake("test-otd-manual-story"' in app_source
    assert 'heading="Add a manual headline or news URL to Long-form candidates"' in app_source
    assert '"live-top5-manual-story"' in app_source
    assert '"test-top5-manual-story"' in app_source
    assert "def _start_test_with_manual_topic(" in app_source
    assert "def _start_live_with_manual_topic(" in app_source
    assert "_story_payload(topic)" in app_source


def test_card_studio_does_not_reset_the_active_visual_source():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    grid_start = app_source.index("def _render_visual_option_grid(")
    grid_end = app_source.index("def _live_start_story(", grid_start)
    grid_source = app_source[grid_start:grid_end]
    assert '"visual_test_mode": "test_visual_source_mode"' in grid_source
    assert '"live_visual_option": "live_visual_source_mode"' in grid_source
    assert 'if source_state_key and not option.startswith("Option 5")' in grid_source

    workspace_start = app_source.index("def _render_two_pane_visual_workspace(")
    workspace_end = app_source.index("def _render_live_visuals(", workspace_start)
    workspace_source = app_source[workspace_start:workspace_end]
    assert 'saved_source_key = "live_visual_source_mode" if live else "test_visual_source_mode"' in workspace_source

