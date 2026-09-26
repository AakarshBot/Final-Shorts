import streamlit as st

from audio import approve_audio, generate_audio
from script_writer import apply_script_edits, write_script
from topic_fetcher import fetch_topics
from visual_fetcher import crawl_visuals, same_query

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
    ["01 · Topic Fetcher", "02 · Scriptwriter", "03 · Audio", "04 · Visuals"],
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
if "visual_manual_query" not in st.session_state:
    st.session_state.visual_manual_query = ""

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
            st.session_state.topics = fetch_topics(
                profiles[desk],
                more=more,
                exclude_topics=st.session_state.topics if more else [],
                limit=20,
            )
        st.session_state.selected_topic = None
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
        st.session_state.visual_result = None
        st.session_state.visual_loaded_story = None
        st.session_state.visual_manual_query = ""

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
                st.session_state.visual_manual_query = ""

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
    st.caption("Edit any scene you want. The three generated titles are stored for the later title-selection step and are not shown here.")

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
            approved = apply_script_edits(script, edited_voiceovers)
            st.session_state.approved_script = approved
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_script:
        st.success("Script approved and stored as the handoff for Function 03 · Audio.")


def render_visuals():
    st.header("04 · Visuals")
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

    story_key = story["url"]
    if story_key != st.session_state.get("visual_loaded_story"):
        st.session_state.visual_result = None
        st.session_state.visual_manual_query = ""
        with st.spinner("Scraping the selected story and related publisher pages…"):
            try:
                st.session_state.visual_result = crawl_visuals(story)
                st.session_state.visual_loaded_story = story_key
            except Exception as exc:
                st.session_state.visual_result = {
                    "error": f"{type(exc).__name__}: {exc}"
                }

    result = st.session_state.get("visual_result") or {}
    if result.get("error"):
        st.error(result["error"])
        return
    if not result:
        return

    st.markdown(f"**{topic.title}**")
    st.caption(f"Original story: {result.get('original_story_url', topic.url)}")

    automatic_queries = list(result.get("automatic_queries") or [])
    st.markdown("**Factory visual queries used**")
    if automatic_queries:
        for query in automatic_queries:
            st.code(query)
    else:
        st.caption("No secondary search query was needed.")

    metrics = st.columns(3)
    metrics[0].metric("Images", len(result.get("assets") or []))
    metrics[1].metric("Pages", int(result.get("pages_scraped") or 0))
    metrics[2].metric("Status", "Ready" if len(result.get("assets") or []) >= result.get("success_threshold", 10) else "Underfilled")

    st.subheader("Manual web query")
    st.caption("Enter a new keyword or phrase. The same crawler will keep the original story URL as the anchor and search only this manual query.")
    with st.form("visual_manual_query_form"):
        manual_query = st.text_input(
            "Keyword / phrase / query",
            value=st.session_state.get("visual_manual_query") or "",
            placeholder="e.g. Shubman Gill batting India",
        )
        run_manual = st.form_submit_button(
            "Run manual query",
            type="primary",
            use_container_width=True,
        )

    if run_manual:
        manual_query = manual_query.strip()
        if not manual_query:
            st.warning("Enter a query first.")
        elif same_query(manual_query, automatic_queries):
            st.warning("That query was already used by the factory for this story. Use a different query.")
        else:
            with st.spinner("Scraping the manual query…"):
                try:
                    st.session_state.visual_result = crawl_visuals(
                        story,
                        manual_query=manual_query,
                    )
                    st.session_state.visual_manual_query = manual_query
                    st.rerun()
                except Exception as exc:
                    st.error(f"{type(exc).__name__}: {exc}")

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
                query = asset.get("query") or "original story URL"
                size = f'{asset.get("width", 0)}×{asset.get("height", 0)}'
                action = int(asset.get("action_score") or 0)
                st.caption(
                    f"{publisher} · {size} · action {action}\n{asset.get('article_title') or ''}"
                )
                st.caption(f"Search: {query}")
                source_url = str(asset.get("source_page_url") or "").strip()
                if source_url:
                    st.link_button("Open source", source_url, use_container_width=True)


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
else:
    render_visuals()
