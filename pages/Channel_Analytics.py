from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from channel_analytics import (  # noqa: E402
    ANALYTICS_TOKEN_PATH,
    build_analytics_clients,
    fetch_channel_analytics,
    format_duration,
    load_analytics_credentials,
)

st.set_page_config(page_title="Channel Analytics · Final Shorts", page_icon="📊", layout="wide")
st.title("YouTube Channel Analytics")
st.caption(
    "Free, read-only reporting from Google's official YouTube APIs. "
    "No third-party analytics subscription and no publishing actions."
)

with st.sidebar:
    st.markdown("### Report settings")
    days = st.selectbox(
        "Date range",
        options=[7, 28, 90, 365],
        index=1,
        format_func=lambda value: f"Last {value} days",
        key="channel_analytics_days",
    )
    refresh = st.button("Fetch / refresh stats", type="primary", use_container_width=True)
    st.caption("Cost: ₹0 for this feature. Standard Google API quota limits apply.")

fetch_needed = (
    refresh
    or "channel_analytics_report" not in st.session_state
    or st.session_state.get("channel_analytics_report_days") != days
)
if fetch_needed:
    try:
        with st.spinner("Reading channel analytics from YouTube…"):
            credentials = load_analytics_credentials()
            analytics_client, youtube_client = build_analytics_clients(credentials)
            result = fetch_channel_analytics(analytics_client, youtube_client, days=days)
        st.session_state.channel_analytics_report = result
        st.session_state.channel_analytics_report_days = days
        st.session_state.channel_analytics_error = ""
    except Exception as exc:
        st.session_state.pop("channel_analytics_report", None)
        st.session_state.pop("channel_analytics_report_days", None)
        st.session_state.channel_analytics_error = f"{type(exc).__name__}: {exc}"

error = st.session_state.get("channel_analytics_error", "")
report = st.session_state.get("channel_analytics_report")
if error:
    if not ANALYTICS_TOKEN_PATH.is_file():
        st.warning("The free analytics permission has not been authorized on this computer yet.")
        st.markdown(
            """
            **One-time setup**

            1. Open a terminal in your Final-Shorts project folder.
            2. Run the command below.
            3. Sign into the Google account that owns the YouTube channel and approve the read-only permissions.
            4. Refresh this page.

            The setup creates analytics_token.json and leaves the factory upload token unchanged.
            Never share either token file.
            """
        )
        st.code("python authorize_youtube_analytics.py", language="powershell")
        st.caption("The existing local token.json is needed to reuse the factory's OAuth client details.")
    else:
        st.error("YouTube analytics could not be loaded.")
        st.code(error)
        st.caption(
            "Confirm that YouTube Analytics API and YouTube Data API v3 are enabled in the "
            "Google Cloud project used by the factory. Re-authorize if the read-only scopes are missing."
        )
    st.stop()

if not report:
    st.info("Choose a date range and fetch channel stats.")
    st.stop()

channel = report["channel"]
if channel.get("thumbnail_url"):
    col_image, col_title = st.columns([1, 8], vertical_alignment="center")
    with col_image:
        st.image(channel["thumbnail_url"], width=76)
    with col_title:
        st.subheader(channel["title"])
        details = []
        if channel.get("custom_url"):
            details.append("@" + str(channel["custom_url"]).lstrip("@"))
        details.append("Channel ID: " + str(channel.get("id") or "unavailable"))
        st.caption(" · ".join(details))
else:
    st.subheader(channel["title"])
    st.caption("Channel ID: " + str(channel.get("id") or "unavailable"))

subscriber_count = channel.get("subscribers")
if channel.get("hidden_subscriber_count"):
    subscriber_label = "Hidden"
elif subscriber_count is None:
    subscriber_label = "Unavailable"
else:
    subscriber_label = f"{subscriber_count:,}"

total_cols = st.columns(3)
total_cols[0].metric("Lifetime channel views", f"{channel['lifetime_views']:,}")
total_cols[1].metric("Current subscribers", subscriber_label)
total_cols[2].metric("Videos on channel", f"{channel['video_count']:,}")

st.divider()
st.subheader(f"Performance · {report['start_date']} to {report['end_date']}")
st.caption("Reports end two days before today to reduce incomplete latest-day metrics.")
summary = report.get("summary") or {}
views = int(float(summary.get("views") or 0))
engaged = int(float(summary.get("engagedViews") or 0))
watch_hours = float(summary.get("estimatedMinutesWatched") or 0) / 60
avg_duration = format_duration(summary.get("averageViewDuration"))
gained = int(float(summary.get("subscribersGained") or 0))
lost = int(float(summary.get("subscribersLost") or 0))
net = gained - lost

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Views", f"{views:,}")
kpi2.metric("Engaged views", f"{engaged:,}")
kpi3.metric("Watch time", f"{watch_hours:,.1f} hours")
kpi4.metric("Average view duration", avg_duration)

kpi5, kpi6, kpi7, kpi8 = st.columns(4)
kpi5.metric("Subscribers gained", f"{gained:,}")
kpi6.metric("Subscribers lost", f"{lost:,}")
kpi7.metric("Net subscribers", f"{net:+,}")
kpi8.metric(
    "Likes · comments · shares",
    f"{int(float(summary.get('likes') or 0)):,} · "
    f"{int(float(summary.get('comments') or 0)):,} · "
    f"{int(float(summary.get('shares') or 0)):,}",
)

tab_trends, tab_videos, tab_sources, tab_export = st.tabs(
    ["Trends", "Top videos", "Traffic sources", "CSV export"]
)
daily = report.get("daily") or []
top_videos = report.get("top_videos") or []
traffic_sources = report.get("traffic_sources") or []

with tab_trends:
    if daily:
        frame = pd.DataFrame(daily)
        if "day" in frame.columns:
            frame["day"] = pd.to_datetime(frame["day"], errors="coerce")
            frame = frame.dropna(subset=["day"]).set_index("day").sort_index()
        view_cols = [name for name in ("views", "engagedViews") if name in frame.columns]
        if view_cols:
            st.markdown("**Daily views**")
            st.line_chart(frame[view_cols])
        if "estimatedMinutesWatched" in frame.columns:
            st.markdown("**Daily watch time (minutes)**")
            st.area_chart(frame[["estimatedMinutesWatched"]].rename(
                columns={"estimatedMinutesWatched": "Watch minutes"}
            ))
        if {"subscribersGained", "subscribersLost"}.issubset(frame.columns):
            st.markdown("**Daily subscriber movement**")
            st.bar_chart(frame[["subscribersGained", "subscribersLost"]])
    else:
        st.info("No daily trend rows were returned for this period.")
    st.caption(
        "Engaged views are shown separately for Shorts-oriented analysis. "
        "Use YouTube's definitions for these metrics rather than treating every view measure as identical."
    )

with tab_videos:
    if top_videos:
        table = []
        for video in top_videos:
            table.append({
                "Video": video.get("title") or video.get("video_id") or "Untitled",
                "Open": video.get("url") or "",
                "Views in range": int(float(video.get("views") or 0)),
                "Engaged views": int(float(video.get("engagedViews") or 0)),
                "Watch hours": round(float(video.get("estimatedMinutesWatched") or 0) / 60, 2),
                "Avg. duration": format_duration(video.get("averageViewDuration")),
                "Subscribers gained": int(float(video.get("subscribersGained") or 0)),
                "Likes": int(float(video.get("likes") or 0)),
                "Comments": int(float(video.get("comments") or 0)),
                "Shares": int(float(video.get("shares") or 0)),
                "Lifetime views": int(video.get("lifetime_views") or 0),
            })
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                "Open": st.column_config.LinkColumn("Open", display_text="Watch video"),
                "Watch hours": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    else:
        st.info("No video-level rows were returned for this period.")

with tab_sources:
    if traffic_sources:
        frame = pd.DataFrame([{
            "Traffic source": str(row.get("insightTrafficSourceType") or "UNKNOWN").replace("_", " ").title(),
            "Views": int(float(row.get("views") or 0)),
            "Watch minutes": round(float(row.get("estimatedMinutesWatched") or 0), 1),
        } for row in traffic_sources])
        st.bar_chart(frame, x="Traffic source", y="Views")
        st.dataframe(frame, width="stretch", hide_index=True)
    else:
        st.info("No traffic-source rows were returned for this period.")

with tab_export:
    for label, rows, filename in (
        ("Daily trends", daily, "youtube-daily"),
        ("Top videos", top_videos, "youtube-top-videos"),
        ("Channel summary", [{**summary, "channel_id": channel.get("id"), "channel_title": channel.get("title")}], "youtube-summary"),
    ):
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Download " + label + " CSV",
            data=csv_bytes,
            file_name=f"{filename}-{report['start_date']}-to-{report['end_date']}.csv",
            mime="text/csv",
        )

for report_name, report_error in (report.get("optional_errors") or {}).items():
    st.warning(f"Partial report: {report_name} — {report_error}")

st.divider()
st.markdown("#### How to use the report")
st.markdown(
    "Compare like formats with like formats. Look at engaged views and average view duration "
    "together, identify which topics win subscribers, and use traffic-source shifts to tell "
    "discovery changes from weak retention. This page does not change factory settings or publish anything."
)
