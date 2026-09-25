import streamlit as st

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

st.sidebar.markdown("### Test")
function = st.sidebar.selectbox("Function", ["01 · Topic Fetcher"], key="test_function")

profile_labels = {
    "Cricket India / Asia": "cricket_india_asia",
    "Cricket Global": "cricket_global",
    "Niche Sports": "niche_sports",
}

st.header(function)
profile_label = st.selectbox("Desk", list(profile_labels), key="topic_profile")

col1, col2 = st.columns([1, 1])
with col1:
    fetch = st.button("Fetch topics", type="primary", use_container_width=True)
with col2:
    more = st.button("Find 20 more", use_container_width=True)

if "topics" not in st.session_state:
    st.session_state.topics = []
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None

if fetch or more:
    with st.spinner("Fetching current sports stories…"):
        st.session_state.topics = fetch_topics(
            profile_labels[profile_label],
            more=more,
            exclude_topics=st.session_state.topics if more else [],
            limit=20,
        )
    st.session_state.selected_topic = None

st.markdown(
    f"<span class='badge'>{len(st.session_state.topics)} topics</span>",
    unsafe_allow_html=True,
)

for i, topic in enumerate(st.session_state.topics):
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"**{i + 1:02d}  {topic.title}**")
    st.markdown(
        f"<span class='muted'>{topic.source or 'Unknown source'} · "
        f"{topic.published_at.strftime('%d %b %Y, %H:%M UTC')}</span>",
        unsafe_allow_html=True,
    )
    if topic.description:
        st.caption(topic.description[:260])
    if st.button("Select", key=f"select-{i}"):
        st.session_state.selected_topic = i
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.selected_topic is not None and st.session_state.selected_topic < len(st.session_state.topics):
    topic = st.session_state.topics[st.session_state.selected_topic]
    st.divider()
    st.subheader("Selected topic")
    st.write(topic.title)
    st.caption(f"{topic.source} · {topic.url}")
