from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


def _section(start: str, end: str) -> str:
    start_index = APP_SOURCE.index(start)
    end_index = APP_SOURCE.index(end, start_index)
    return APP_SOURCE[start_index:end_index]


def test_live_ai_generation_is_backgrounded_and_does_not_block_visual_edits():
    workspace = _section(
        "def _render_two_pane_visual_workspace(",
        "def _render_live_visuals(",
    )
    assert "_live_background_executor().submit(" in workspace
    assert "generate_images, query" in workspace
    assert "st.session_state.live_ai_image_result = generate_images(query)" not in workspace
    assert 'st.session_state.get("live_ai_image_status") == "running"' in workspace
    assert "Switch sources while generation runs; results appear automatically." in workspace


def test_live_final_render_uses_the_existing_renderer_contract_off_thread():
    worker = _section(
        "def _live_render_final_short(",
        "def _poll_live_background_jobs(",
    )
    assert "render_production_video(" in worker
    assert "script," in worker
    assert "audio," in worker
    assert "subtitles," in worker
    assert "visuals," in worker
    assert "output_path=output" in worker
    assert "source_label=" not in worker

    visual_stage = _section(
        "def _render_live_visuals(",
        "def _render_packaging_deck_and_phone(",
    )
    assert "_live_background_executor().submit(" in visual_stage
    assert "_live_render_final_short," in visual_stage
    assert 'with st.spinner("Rendering the final Short…")' not in visual_stage
    assert "render_production_video(" not in visual_stage
    assert visual_stage.count('key="live-approve-visuals-top"') == 1
    assert 'key="live-approve-visuals",' not in visual_stage


def test_live_render_does_not_approve_stale_visual_assignments():
    poller = _section(
        "def _poll_live_background_jobs(",
        "@st.cache_data(max_entries=128, show_spinner=False)",
    )
    assert "live_render_job_visual_snapshot" in poller
    assert "if current_visuals != snapshot:" in poller
    assert "st.session_state.live_visuals_approved = False" in poller
    assert "the assignments changed while it was rendering" in poller
    assert "st.session_state.live_rendered_video_path = None" in poller


def test_live_background_jobs_avoid_global_timer_and_watch_render_locally():
    poller = _section(
        "def _poll_live_background_jobs(",
        "@st.cache_data(max_entries=128, show_spinner=False)",
    )
    assert '"live_ai_image_future"' in poller
    assert '"live_render_future"' in poller
    assert "future.done()" in poller
    assert "future.result()" in poller
    assert "st_autorefresh" not in APP_SOURCE
    assert "setInterval(" not in APP_SOURCE
    assert "time.sleep(" not in APP_SOURCE
    assert "Refresh background status" not in APP_SOURCE

    live_watcher = _section(
        "@st.fragment(run_every=1.0)\ndef _watch_live_background_completion():",
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
    )
    assert "future.done()" in live_watcher
    assert "_poll_live_background_jobs()" in live_watcher
    assert 'st.rerun(scope="app")' in live_watcher

    test_watcher = _section(
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
        "def _poll_test_visual_jobs(",
    )
    assert "future.done()" in test_watcher
    assert "_poll_test_visual_jobs()" in test_watcher
    assert 'st.rerun(scope="app")' in test_watcher


def test_live_render_pauses_visual_editing_and_advances_to_upload_qc():
    visual_stage = _section(
        "def _render_live_visuals(",
        "def _render_packaging_deck_and_phone(",
    )
    assert 'if st.session_state.get("live_render_status") == "running":' in visual_stage
    assert "The visual editor is paused" in visual_stage
    assert "_watch_live_render_completion()" not in visual_stage
    assert "You can continue editing cards; the result will be checked" not in visual_stage

    poller = _section(
        "def _poll_live_background_jobs(",
        "@st.cache_data(max_entries=128, show_spinner=False)",
    )
    assert 'st.session_state.live_stage = "05 · Upload"' in poller
    assert 'if st.session_state.get("live_stage") == "04 · Visuals + Render":' not in poller
    assert '"next": "Moving to Upload."' in poller


def test_discarding_live_handoffs_cancels_queued_jobs_and_clears_render_state():
    cancel_helper = _section(
        "def _cancel_live_background_jobs(",
        "def _live_render_final_short(",
    )
    reset = _section(
        "def _live_reset_downstream(",
        "def _story_payload(",
    )
    assert "future.cancel()" in cancel_helper
    assert "_cancel_live_background_jobs()" in reset
    assert '"live_ai_image_future": None' in reset
    assert '"live_render_future": None' in reset
    assert '"live_render_job_visual_snapshot": None' in reset




def test_visual_source_switches_are_fragment_scoped_in_live_and_test():
    assert "@st.fragment\ndef _render_live_visuals(slide_count: int):" in APP_SOURCE
    assert "@st.fragment\ndef render_visuals():" in APP_SOURCE

    selector = _section(
        "def _render_visual_option_grid(",
        "def _test_visual_slide_count(",
    )
    assert "st.session_state[session_key] = option" in selector
    assert "st.rerun()" not in selector


def test_test_ai_to_real_search_fallback_is_backgrounded():
    fallback_start = APP_SOURCE.index('key="ai-fallback-to-real-search"')
    fallback_end = APP_SOURCE.index("\n        return", fallback_start)
    fallback = APP_SOURCE[fallback_start:fallback_end]
    assert "_live_background_executor().submit(search_images, last_query)" in fallback
    assert 'st.rerun(scope="app")' in fallback
    assert "search_images(last_query)" not in fallback
    assert "with st.spinner(" not in fallback


def test_live_visual_layout_clicks_do_not_force_a_second_dashboard_run():
    workspace = _section(
        "def _render_two_pane_visual_workspace(",
        "def _render_live_visuals(",
    )
    control_start = workspace.index('if st.button(\n            "Split"')
    control_end = workspace.index("current_view = st.session_state[pane_key]", control_start)
    layout_controls = workspace[control_start:control_end]
    assert "st.rerun()" not in layout_controls

    asset_pool = _section(
        "def _render_visual_asset_pool(",
        "def _render_visual_board(",
    )
    button_key = 'key=f"{prefix}use-card-studio-{asset_key}"'
    button_key_index = asset_pool.index(button_key)
    studio_button_start = asset_pool.rfind("if st.button(", 0, button_key_index)
    studio_button_end = asset_pool.index("choose_col, crop_col, delete_col", button_key_index)
    studio_select = asset_pool[studio_button_start:studio_button_end]
    studio_button_end = asset_pool.index("choose_col, crop_col, delete_col", studio_button_start)
    studio_select = asset_pool[studio_button_start:studio_button_end]
    assert 'st.toast("Loaded image into Card Studio!"' in studio_select
    assert "st.rerun()" not in studio_select
