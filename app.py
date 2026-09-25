import streamlit as st

from script_writer import apply_script_edits, write_script
from topic_fetcher import fetch_topics

st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {background:#0b0d10;color:#f5f7fa;}
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:3rem;}
.card {background:#15191f;border:1px solid #292f38;border-radius:18px;padding:20px;margin:10px 0;}
.muted {color:#8e98a7;font-size:.9rem;}
.badge {display:inline-block;padding:5px 10px;border-radius:999px;background:#222831;border:1px solid #353d48;font-size:.78rem;}
</style>
""", unsafe_allow_html=True)

st.title("Final Shorts")
st.caption("Free Shorts factory · independent function testing")

mode = st.sidebar.radio("Mode", ["Test", "Live"], key="mode")
if mode == "Live":
    st.sidebar.warning("Live is disabled while the factory is being built.")
    st.header("Live")
    st.info("Live production will be enabled after the individual functions are built and tested.")
    st.stop()

function = st.sidebar.selectbox(
    "Test function",
    ["01 · Topic Fetcher", "02 · Scriptwriter"],
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
    st.session_state.selected_topic = selected_index
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
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_script:
        st.success("Script approved and stored as the handoff for Function 03 · Audio.")
        st.caption("The Audio function is not implemented yet, so no audio API call is made at this stage.")


if function == "01 · Topic Fetcher":
    render_topic_fetcher()
else:
    render_scriptwriter()
