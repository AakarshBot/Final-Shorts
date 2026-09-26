import json
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from audio import approve_audio, generate_audio
from script_writer import apply_script_edits, write_script
from topic_fetcher import fetch_topics
from visual_fetcher import crawl_visuals, manual_crawl_visuals
from visual_search import search_images
from visual_generator import generate_images
from renderer import HEADLINE_TEXT, FINAL_STYLE_NAME, build_preview_bundle
from subtitles import generate_subtitles

st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {background:#0b0d10;color:#f5f7fa;}
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:3rem;}
.card {background:#15191f;border:1px solid #292f38;border-radius:18px;padding:20px;margin:10px 0;}
.badge {display:inline-block;padding:5px 10px;border-radius:999px;background:#222831;border:1px solid #353d48;font-size:.78rem;}
</style>
""", unsafe_allow_html=True)

st.title("Final Shorts")
st.caption("Free Shorts factory · independent function testing")

function = st.sidebar.selectbox(
    "Test function",
    ["01 · Topic Fetcher", "02 · Scriptwriter", "03 · Audio", "04 · Visuals", "05 · Subtitles", "06 · Renderer"],
    key="test_function",
)

if "topics" not in st.session_state:
    st.session_state.topics = []
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None
if "script_data" not in st.session_state:
    st.session_state.script_data = None
if "approved_script" not in st.session_state:
    st.session_state.approved_script = None
if "audio_data" not in st.session_state:
    st.session_state.audio_data = None
if "approved_audio" not in st.session_state:
    st.session_state.approved_audio = None
if "visual_result" not in st.session_state:
    st.session_state.visual_result = None
if "visual_loaded_story" not in st.session_state:
    st.session_state.visual_loaded_story = None
if "manual_visual_result" not in st.session_state:
    st.session_state.manual_visual_result = None
if "real_image_result" not in st.session_state:
    st.session_state.real_image_result = None
if "ai_image_result" not in st.session_state:
    st.session_state.ai_image_result = None
if "subtitle_data" not in st.session_state:
    st.session_state.subtitle_data = None
if "approved_subtitles" not in st.session_state:
    st.session_state.approved_subtitles = None

profiles = {
    "Cricket India / Asia": "cricket_india_asia",
    "Cricket Global": "cricket_global",
    "Niche Sports": "niche_sports",
}


def render_topic_fetcher():
    st.header("01 · Topic Fetcher")
    desk = st.selectbox("Desk", list(profiles), key="topic_desk")
    col1, col2 = st.columns(2)
    with col1:
        fetch = st.button("Fetch topics", type="primary", use_container_width=True)
    with col2:
        more = st.button("Find 20 more", use_container_width=True)

    if fetch or more:
        with st.spinner("Fetching current sports stories…"):
            existing_topics = list(st.session_state.topics) if more else []
            new_topics = fetch_topics(
                profiles[desk],
                more=more,
                exclude_topics=existing_topics,
                limit=20,
            )
            st.session_state.topics = (
                existing_topics + new_topics if more else new_topics
            )
        st.session_state.selected_topic = None
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None
        st.session_state.visual_result = None
        st.session_state.visual_loaded_story = None

    st.markdown(
        f"<span class='badge'>{len(st.session_state.topics)} topics</span>",
        unsafe_allow_html=True,
    )

    for index, topic in enumerate(st.session_state.topics):
        with st.container(border=True):
            st.markdown(f"**{index + 1:02d}  {topic.title}**")
            st.caption(
                f"{topic.source or 'Unknown source'} · "
                f"{topic.published_at.strftime('%d %b %Y, %H:%M UTC')}"
            )
            if topic.description:
                st.caption(topic.description[:260])
            if st.button("Select story", key=f"topic-select-{index}", use_container_width=True):
                st.session_state.selected_topic = index
                st.session_state.script_data = None
                st.session_state.approved_script = None
                st.session_state.audio_data = None
                st.session_state.approved_audio = None
                st.session_state.visual_result = None
                st.session_state.visual_loaded_story = None
        
    if st.session_state.selected_topic is not None:
        index = st.session_state.selected_topic
        if index < len(st.session_state.topics):
            topic = st.session_state.topics[index]
            st.divider()
            st.subheader("Selected story")
            st.write(topic.title)
            st.caption(f"{topic.source} · {topic.url}")


def render_scriptwriter():
    st.header("02 · Scriptwriter")

    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first, then select a story here.")
        return

    labels = [
        f"{i + 1:02d} · {topic.title}"
        for i, topic in enumerate(st.session_state.topics)
    ]
    current = st.session_state.selected_topic
    default_index = current if isinstance(current, int) and current < len(labels) else 0
    selected_label = st.selectbox(
        "Story",
        labels,
        index=default_index,
        key="script_story",
    )
    selected_index = labels.index(selected_label)
    if selected_index != st.session_state.selected_topic:
        st.session_state.selected_topic = selected_index
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None
    topic = st.session_state.topics[selected_index]

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"**{topic.title}**")
    st.caption(topic.description or "The Topic Fetcher did not provide a longer description.")
    st.markdown("</div>", unsafe_allow_html=True)

    language = st.selectbox(
        "Language",
        ["English", "Hindi", "Telugu"],
        key="script_language",
    )

    if st.button("Generate script", type="primary", use_container_width=True):
        with st.spinner("Writing the Short…"):
            st.session_state.script_data = write_script(
                {
                    "title": topic.title,
                    "description": topic.description,
                    "url": topic.url,
                    "source": topic.source,
                },
                language=language.casefold(),
            )
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None

    script = st.session_state.script_data
    if not script:
        return

    st.divider()
    st.subheader("Script review")
    st.caption("Edit the headline or any narration scene. Titles, description and hashtags are stored for later upload QC.")

    edited_headline = st.text_input(
        "Opening heading (3–4 words)",
        value=script.get("headline", ""),
        max_chars=48,
        key="script-headline",
    )

    edited_voiceovers = []
    for index, scene in enumerate(script.get("script", []), 1):
        edited_voiceovers.append(
            st.text_area(
                f"Slide {index}",
                value=scene.get("voiceover", ""),
                height=110,
                key=f"script-slide-{index}",
            )
        )

    if st.button("Approve script", type="primary", use_container_width=True):
        try:
            approved = apply_script_edits(
                script,
                edited_voiceovers,
                headline=edited_headline,
            )
            st.session_state.approved_script = approved
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_script:
        st.success("Script approved and stored as the handoff for Function 03 · Audio.")


def render_visuals_crawler():
    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first, then select a story for Visuals.")
        return

    labels = [
        f"{i + 1:02d} · {topic.title}"
        for i, topic in enumerate(st.session_state.topics)
    ]
    current = st.session_state.selected_topic
    default_index = current if isinstance(current, int) and current < len(labels) else 0
    selected_label = st.selectbox(
        "Headline",
        labels,
        index=default_index,
        key="visual_story",
    )
    selected_index = labels.index(selected_label)
    if selected_index != st.session_state.selected_topic:
        st.session_state.selected_topic = selected_index
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
    topic = st.session_state.topics[selected_index]

    story = {
        "title": topic.title,
        "description": topic.description,
        "url": topic.url,
        "source": topic.source,
        "published_at": topic.published_at.isoformat(),
    }
    approved_script = st.session_state.get("approved_script")
    if (
        isinstance(approved_script, dict)
        and str(approved_script.get("source_title") or "").strip() == topic.title.strip()
    ):
        scenes = approved_script.get("script") or []
        if scenes and isinstance(scenes[0], dict):
            story["primary_entity"] = str(
                scenes[0].get("primary_entity") or ""
            ).strip()

    story_key = f"{selected_index}:{story['url']}:{story['title']}"

    if story_key != st.session_state.get("visual_loaded_story"):
        st.session_state.visual_result = None
        with st.spinner("Scraping the selected story and related publisher pages…"):
            try:
                st.session_state.visual_result = crawl_visuals(story)
                st.session_state.visual_loaded_story = story_key
            except Exception as exc:
                st.session_state.visual_result = {
                    "error": f"{type(exc).__name__}: {exc}"
                }

    result = st.session_state.get("visual_result") or {}
    automatic_queries = list(result.get("automatic_queries") or [])

    st.markdown(f"**{topic.title}**")
    st.caption(f"Original story: {result.get('original_story_url', topic.url)}")

    if result.get("error"):
        st.error(result["error"])
        return

    st.markdown("**Factory visual queries used**")
    if automatic_queries:
        for query in automatic_queries:
            st.code(query)
    else:
        st.caption("No secondary search query was needed.")

    diagnostics = list(result.get("diagnostics") or [])
    with st.expander("Crawler diagnostics", expanded=not bool(result.get("assets"))):
        if diagnostics:
            st.code(
                json.dumps(diagnostics, indent=2, ensure_ascii=False),
                language="text",
            )
        else:
            st.caption("No page diagnostics were returned.")

    metrics = st.columns(3)
    metrics[0].metric("Images", len(result.get("assets") or []))
    metrics[1].metric("Pages", int(result.get("pages_scraped") or 0))
    metrics[2].metric(
        "Status",
        "Ready"
        if len(result.get("assets") or []) >= result.get("success_threshold", 10)
        else "Underfilled",
    )

    assets = list(result.get("assets") or [])
    if not assets:
        st.warning("The crawler found no usable images.")
        return

    st.subheader("Scraped images")
    for start in range(0, len(assets), 3):
        cols = st.columns(3, gap="medium")
        for col, asset in zip(cols, assets[start:start + 3]):
            with col:
                st.image(asset["bytes"], width="stretch")
                publisher = asset.get("publisher") or "Web source"
                size = f'{asset.get("width", 0)}×{asset.get("height", 0)}'
                action = int(asset.get("action_score") or 0)
                st.caption(
                    f"{publisher} · {size} · action {action}\n"
                    f"{asset.get('article_title') or ''}"
                )
                source_url = str(asset.get("source_page_url") or "").strip()
                if source_url:
                    st.link_button("Open source", source_url, use_container_width=True)


def _render_manual_crawler():
    st.subheader("Option 2 · Manual Scraper")
    st.caption("Manual query only. Searches current publisher pages and scrapes their images.")
    with st.form("manual_crawler_form"):
        query = st.text_input(
            "Search query",
            placeholder="e.g. Virat Kohli Rohit Sharma",
            key="manual_crawler_query",
        )
        scrape = st.form_submit_button(
            "Run manual scrape",
            type="primary",
            use_container_width=True,
        )

    if scrape:
        query = query.strip()
        if not query:
            st.warning("Enter a query first.")
        else:
            with st.spinner("Searching and scraping publisher pages…"):
                try:
                    st.session_state.manual_visual_result = manual_crawl_visuals(query)
                except Exception as exc:
                    st.session_state.manual_visual_result = {
                        "error": f"{type(exc).__name__}: {exc}"
                    }

    result = st.session_state.get("manual_visual_result") or {}
    if result.get("error"):
        st.error(result["error"])
        return
    if not result:
        return

    st.caption(
        f'{len(result.get("assets") or [])} images · '
        f'{int(result.get("pages_scraped") or 0)} pages · '
        f'{"historical search" if result.get("historical") else "current search"}'
    )
    for query in result.get("search_queries") or []:
        st.code(query)
    diagnostics = list(result.get("diagnostics") or [])
    with st.expander("Crawler diagnostics", expanded=not bool(result.get("assets"))):
        if diagnostics:
            st.code(json.dumps(diagnostics, indent=2, ensure_ascii=False), language="text")
        else:
            st.caption("No page diagnostics were returned.")

    assets = list(result.get("assets") or [])
    if not assets:
        st.warning("The manual crawler found no usable images.")
        return

    st.subheader("Scraped images")
    for start in range(0, len(assets), 3):
        cols = st.columns(3, gap="medium")
        for col, asset in zip(cols, assets[start:start + 3]):
            with col:
                st.image(asset["bytes"], width="stretch")
                publisher = asset.get("publisher") or "Web source"
                size = f'{asset.get("width", 0)}×{asset.get("height", 0)}'
                st.caption(
                    f"{publisher} · {size}\n{asset.get('article_title') or ''}"
                )
                source_url = str(asset.get("source_page_url") or "").strip()
                if source_url:
                    st.link_button("Open source", source_url, use_container_width=True)


def _render_manual_real_images():
    st.subheader("Option 3 · Real Image Search")
    st.caption("Manual query only. Searches all configured real-image sources in parallel.")
    with st.form("real_image_search_form"):
        query = st.text_input(
            "Manual query",
            placeholder="e.g. Ben Stokes batting",
            key="real_image_query",
        )
        search = st.form_submit_button(
            "Search real images",
            type="primary",
            use_container_width=True,
        )

    if search:
        query = query.strip()
        if not query:
            st.warning("Enter a query first.")
        else:
            with st.spinner("Searching real-image sources…"):
                st.session_state.real_image_result = search_images(query)

    result = st.session_state.get("real_image_result") or {}
    if not result:
        return
    if result.get("errors"):
        st.caption("Some sources failed; successful sources are still shown.")

    assets = result.get("assets") or []
    st.caption(
        f"{len(assets)} images · "
        + " · ".join(
            f"{name} {count}"
            for name, count in (result.get("providers") or {}).items()
            if count
        )
    )
    if not assets:
        st.warning("No usable images were returned.")
        return

    for start in range(0, len(assets), 3):
        cols = st.columns(3, gap="medium")
        for col, asset in zip(cols, assets[start:start + 3]):
            with col:
                st.image(asset["bytes"], width="stretch")
                st.caption(asset.get("source") or "Web")
                source_url = str(asset.get("source_page_url") or "").strip()
                if source_url:
                    st.link_button("Open source", source_url, use_container_width=True)


def _render_manual_ai_images():
    st.subheader("Option 4 · AI Generation")
    st.caption("Manual query only. Each configured AI provider runs independently.")
    with st.form("ai_image_form"):
        query = st.text_input(
            "Manual prompt",
            placeholder="e.g. Ben Stokes hitting a six in a packed stadium",
            key="ai_image_query",
        )
        generate = st.form_submit_button(
            "Generate images",
            type="primary",
            use_container_width=True,
        )

    if generate:
        query = query.strip()
        if not query:
            st.warning("Enter a prompt first.")
        else:
            with st.spinner("Generating images…"):
                st.session_state.ai_image_result = generate_images(query)

    result = st.session_state.get("ai_image_result") or {}
    if not result:
        return
    if result.get("errors"):
        st.caption("Some AI providers failed; successful providers are still shown.")

    assets = result.get("assets") or []
    st.caption(
        f"{len(assets)} generated · "
        + " · ".join(
            name for name, count in (result.get("providers") or {}).items() if count
        )
    )
    if not assets:
        st.warning("No configured AI provider returned an image.")
        return

    for asset in assets:
        st.image(asset["bytes"], width="stretch")
        st.caption(f'{asset.get("source") or "AI"} · {asset.get("model") or ""}'.strip(" ·"))


def render_visuals():
    st.header("04 · Visuals")
    mode = st.radio(
        "Visual test",
        [
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Real Image Search",
            "Option 4 · AI Generation",
        ],
        horizontal=True,
        key="visual_test_mode",
    )
    if mode.startswith("Option 1"):
        render_visuals_crawler()
    elif mode.startswith("Option 2"):
        _render_manual_crawler()
    elif mode.startswith("Option 3"):
        _render_manual_real_images()
    else:
        _render_manual_ai_images()


def render_subtitles():
    st.header("05 · Subtitles")
    st.caption("Build captions directly from the approved Scriptwriter text and native Audio word timings.")

    script = st.session_state.approved_script
    audio = st.session_state.approved_audio
    if not script or not audio:
        st.info("Approve the Scriptwriter and Audio handoffs first.")
        return

    if st.button("Generate subtitles", type="primary", use_container_width=True):
        try:
            st.session_state.subtitle_data = generate_subtitles(script, audio)
            st.session_state.approved_subtitles = None
        except ValueError as exc:
            st.error(str(exc))

    subtitles = st.session_state.subtitle_data
    if not subtitles:
        return

    st.divider()
    st.subheader("Subtitle review")
    st.caption(
        f'{len(subtitles["cues"])} cues · {subtitles["language"]} · '
        "native Audio timings · no second transcription"
    )

    for index, cue in enumerate(subtitles["cues"], 1):
        words = " ".join(word["text"] for word in cue["words"])
        st.write(
            f'{index:02d} · {cue["start"]:.2f}s–{cue["end"]:.2f}s · {words}'
        )

    if st.button("Approve subtitles", type="primary", use_container_width=True):
        st.session_state.approved_subtitles = dict(subtitles)

    if st.session_state.approved_subtitles:
        st.success("Subtitles approved and stored as the handoff for Function 06 · Renderer.")


def render_renderer_test():
    st.header("06 · Renderer")
    approved_script = st.session_state.get("approved_script")
    headline_text = (
        str(approved_script.get("headline") or "").strip()
        if isinstance(approved_script, dict)
        else ""
    ) or HEADLINE_TEXT
    headline_enabled = True

    st.caption(
        "Uses the approved Scriptwriter heading when available; otherwise uses the renderer test fallback."
    )
    st.code(headline_text, language="text")

    st.caption(
        f"{FINAL_STYLE_NAME} · Oswald Bold block headline · clean word-highlight captions"
    )

    if st.button("Build preview", type="primary", use_container_width=True):
        with st.spinner("Rendering preview…"):
            try:
                st.session_state.renderer_previews = build_preview_bundle(
                    headline_enabled=headline_enabled,
                    headline_text=headline_text.strip() or HEADLINE_TEXT,
                )
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))

    previews = st.session_state.get("renderer_previews") or {}
    if not previews:
        st.info("Build the preview to see the opening treatment and final overlay.")
        return

    opening = previews.get("opening")
    final = previews.get("final")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("**Opening**")
        if opening and Path(opening).exists():
            st.video(str(opening), width=320)
        st.caption("Optional headline enters from the left, then clears before subtitles appear.")

    with right:
        st.markdown("**Final overlay**")
        if final and Path(final).exists():
            st.video(str(final), width=300)
        st.caption("Large bold captions · yellow active word · logo top-right · source bottom-right")


def render_audio():
    st.header("03 · Audio")

    script = st.session_state.approved_script
    if not script:
        st.info("Approve a Scriptwriter result first. Audio only accepts the approved narration handoff.")
        return

    languages = ["English", "Hindi", "Telugu"]
    stored = str(script.get("language_used") or "english").casefold()
    default_language = stored if stored in {"english", "hindi", "telugu"} else "english"
    language = st.selectbox(
        "Language",
        languages,
        index=["english", "hindi", "telugu"].index(default_language),
        key="audio_language",
    )
    st.caption("HYPE COMMENTATOR · female Indian voice · native Edge-TTS word timings")

    if st.button("Generate audio", type="primary", use_container_width=True):
        selected = dict(script)
        selected["language_used"] = language.casefold()
        with st.spinner("Generating voiceover…"):
            try:
                st.session_state.audio_data = generate_audio(selected)
                st.session_state.approved_audio = None
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))
                st.session_state.audio_data = None
                st.session_state.approved_audio = None
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None

    audio = st.session_state.audio_data
    if not audio:
        return

    st.divider()
    st.subheader("Audio review")
    correction = " · one speed correction applied" if audio["duration_corrected"] else ""
    st.caption(
        f'{audio["voice"]} · {audio["rate_percent"]:+.0f}% · '
        f'{audio["total_duration"]:.2f}s total{correction}'
    )

    for scene in audio["scenes"]:
        st.markdown(
            f'**Slide {scene["scene"]}** · {scene["duration"]:.2f}s · '
            f'{len(scene["timings"])} word timings'
        )
        st.audio(scene["path"], format="audio/mp3")
        st.caption("Cached" if scene["from_cache"] else "Fresh TTS generation")

    if st.button("Approve audio", type="primary", use_container_width=True):
        try:
            st.session_state.approved_audio = approve_audio(audio)
            st.session_state.subtitle_data = None
            st.session_state.approved_subtitles = None
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_audio:
        st.success("Audio approved and stored as the handoff for Function 04 · Visuals.")

if function == "01 · Topic Fetcher":
    render_topic_fetcher()
elif function == "02 · Scriptwriter":
    render_scriptwriter()
elif function == "03 · Audio":
    render_audio()
elif function == "04 · Visuals":
    render_visuals()
elif function == "05 · Subtitles":
    render_subtitles()
elif function == "06 · Renderer":
    render_renderer_test()
