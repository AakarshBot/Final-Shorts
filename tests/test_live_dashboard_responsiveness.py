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
    assert 'st.rerun(scope="fragment")' in APP_SOURCE

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
        "def _live_start_story(",
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

def test_cricket_live_script_generation_reuses_approved_angle_research_off_thread():
    script_stage = _section(
        "def _render_live_script():",
        "def _render_live_upload():",
    )
    assert "if not universal_story:" in script_stage
    assert "_live_background_executor().submit(" in script_stage
    assert "_script_for_topic," in script_stage
    assert "research_source=st.session_state.live_universal_angle_source" in script_stage
    assert "Evidence basis from the approved research:" in script_stage
    assert 'st.session_state.live_script_status = "running"' in script_stage
    assert "Writing the Short in the background." in script_stage
    # YT Trends and Niche Sports retain their existing synchronous generation path.
    assert "_live_generate_script(" in script_stage
    assert "else:" in script_stage

    poller = _section(
        "def _poll_live_background_jobs():",
        "@st.cache_data(max_entries=128",
    )
    assert '"live_script_future"' in poller
    assert '"live_script_status"' in poller
    assert '"live_script_job_story_key"' in poller
    assert 'if destination == "script":' in poller
    assert "st.session_state.live_script_data = result" in poller

    live_watcher = _section(
        "@st.fragment(run_every=1.0)\ndef _watch_live_background_completion():",
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
    )
    assert '"live_script_future"' in live_watcher
    assert "_poll_live_background_jobs()" in live_watcher

    reset = _section(
        "def _live_reset_downstream():",
        "def _story_payload(",
    )
    assert '"live_script_future": None' in reset
    assert '"live_script_status": "idle"' in reset



def test_live_script_and_top5_visual_jobs_arm_the_completion_watcher():
    dashboard = _section("def render_live_dashboard():", "def render_youtube_trends_topic_fetcher(")
    assert '"live_script_future"' in dashboard
    assert '"live_top5_visual_futures"' in dashboard
    assert '"live_top5_manual_visual_futures"' in dashboard
    assert '"live_top5_real_visual_futures"' in dashboard
    assert '"live_top5_ai_visual_futures"' in dashboard

    watcher = _section(
        "@st.fragment(run_every=1.0)\ndef _watch_live_background_completion():",
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
    )
    assert '"live_script_future"' in watcher
    assert "top5_futures" in watcher
    assert "_poll_live_top5_visual_jobs()" in watcher


def test_automatic_visual_scrapers_require_an_explicit_user_action():
    test_auto = _section(
        "def render_visuals_crawler():",
        "def _render_manual_crawler():",
    )
    assert 'st.session_state.visual_status = "idle"' in test_auto
    assert 'st.button("Start automatic scraper"' in test_auto
    assert "_live_background_executor().submit(crawl_visuals, story)" in test_auto
    assert "if story_key != st.session_state.get(\"visual_loaded_story\"):\n        existing_result" in test_auto

    live_visual_stage = _section(
        'if st.session_state.live_stage == "04 · Visuals + Render":',
        'if st.session_state.live_stage == "05 · Upload":',
    )
    assert "_live_scrape_automatic_visuals()" not in live_visual_stage
    live_fetcher = _section(
        "def _render_two_pane_visual_workspace(",
        "def _render_live_visuals(",
    )
    assert 'key="live-start-auto-visuals"' in live_fetcher


def test_visual_pool_renders_a_bounded_page_and_exposes_every_page():
    pool = _section(
        "def _render_visual_asset_pool(",
        "def _render_visual_board(",
    )
    assert "page_size = 12" in pool
    assert "visible_assets = visible_assets[page_number * page_size:(page_number + 1) * page_size]" in pool
    assert "Previous" in pool
    assert "Next" in pool


def test_completed_background_results_remain_discoverable_after_source_switch():
    status = _section(
        "def _render_visual_job_status(",
        "@st.cache_data(max_entries=128",
    )
    assert '== "complete"' in status
    assert "View {label} · {count}" in status
    assert "st.session_state[option_key] = option" in status
    assert "st.session_state[source_key] = option" in status


def test_live_top5_visual_fetches_are_collected_without_blocking_the_visual_stage():
    poller = _section(
        "def _poll_live_top5_visual_jobs():",
        "def _poll_live_background_jobs():",
    )
    assert "if future is None or not future.done():" in poller
    assert "future.result()" in poller

    stage = _section(
        '    if stage == "04 · Visuals":',
        '    if stage == "06 · Renderer":',
    )
    assert "future.result()" not in stage
    assert "st.spinner(\"Finishing automatic image scraping…\")" not in stage

    top5 = _section("def render_live_top5():", "def render_live_dashboard():")
    assert '_live_background_executor().submit(search_images, query)' in top5
    assert '_live_background_executor().submit(manual_crawl_visuals, query)' in top5
    assert '_live_background_executor().submit(generate_images, query)' in top5
    assert "for start in range(0, len(visible_assets), 4)" in top5



def test_live_top5_script_audio_and_renderer_use_the_dashboard_job_watcher():
    poller = _section(
        "def _poll_live_background_jobs():",
        "@st.fragment(run_every=1.0)\ndef _watch_live_background_completion():",
    )
    for future_key in (
        "live_top5_script_future",
        "live_top5_audio_future",
        "live_top5_render_future",
    ):
        assert future_key in poller
    for destination in ("top5_script", "top5_audio", "top5_render"):
        assert f'destination == "{destination}"' in poller

    watcher = _section(
        "@st.fragment(run_every=1.0)\ndef _watch_live_background_completion():",
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
    )
    for future_key in (
        "live_top5_script_future",
        "live_top5_audio_future",
        "live_top5_render_future",
    ):
        assert future_key in watcher

    top5 = _section("def render_live_top5():", "def render_live_dashboard():")
    assert "generate_top5_script," in top5
    assert "generate_top5_audio," in top5
    assert "_live_render_final_short," in top5
    assert "with st.spinner(\"Generating the six spoken Top-5 lines…\")" not in top5
    assert "with st.spinner(\"Rendering the final Top-5 Short…\")" not in top5


def test_test_top5_visual_jobs_are_collected_from_the_test_dashboard_root():
    root = _section(
        'elif st.session_state.app_mode == "test":',
        'elif st.session_state.app_mode == "live":',
    )
    assert "_poll_test_visual_jobs()" in root
    assert '"test_top5_visual_jobs"' in root
    assert '"test_top5_visual_playground_job"' in root
    assert "_watch_test_visual_fetch_completion()" in root

    poller = _section(
        "def _poll_test_top5_visual_jobs():",
        "@st.fragment(run_every=1.0)\ndef _watch_test_visual_fetch_completion():",
    )
    assert "if future is None or not future.done():" in poller
    assert "results[int(slide_number)] = merged" in poller
    assert "test_top5_visual_playground_status" in poller


def test_all_test_top5_visual_sources_submit_background_jobs():
    stage = _section(
        'elif line_name == "Top-5" and stage == "04 · Visuals":',
        'elif line_name == "Top-5" and stage == "06 · Renderer":',
    )
    for function in ("crawl_visuals", "manual_crawl_visuals", "search_images", "generate_images"):
        assert f"_live_background_executor().submit({function}" in stage
    assert "crawl_visuals(story_payload)" not in stage
    assert "manual_crawl_visuals(query)" not in stage
    assert "search_images(query)" not in stage
    assert "generate_images(query)" not in stage

def test_test_standard_visual_forms_prevent_duplicate_background_jobs():
    manual = _section(
        "def _render_manual_crawler():",
        "def _render_manual_real_images():",
    )
    real = _section(
        "def _render_manual_real_images():",
        "def _render_manual_ai_images():",
    )
    ai = _section(
        "def _render_manual_ai_images():",
        "@st.fragment\\ndef render_visuals():",
    )

    assert 'disabled=st.session_state.get("manual_visual_status") == "running"' in manual
    assert 'disabled=st.session_state.get("real_visual_status") == "running"' in real
    assert 'disabled=st.session_state.get("ai_visual_status") == "running"' in ai

    # Live's standard lanes already enforce the same single-flight behavior.
    live_workspace = _section(
        "def _render_two_pane_visual_workspace(",
        "def _render_live_visuals(",
    )
    assert 'disabled=st.session_state.get("live_manual_visual_status") == "running"' in live_workspace
    assert 'disabled=st.session_state.get("live_real_image_status") == "running"' in live_workspace
