from __future__ import annotations
import base64
import hashlib
import json
import os
from io import BytesIO
from dataclasses import replace
from PIL import Image
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)


st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

VISUAL_OPTIONS = (
    "Option 1 · Automatic Scraper",
    "Option 2 · Manual Scraper",
    "Option 3 · Real Image Search",
    "Option 4 · AI Generation",
    "Option 5 · Card Studio",
)
CRICKET_TEST_VISUAL_OPTIONS = VISUAL_OPTIONS
CRICKET_LIVE_VISUAL_OPTIONS = VISUAL_OPTIONS
YT_TRENDS_VISUAL_OPTIONS = VISUAL_OPTIONS
TOP5_LIVE_VISUAL_OPTIONS = VISUAL_OPTIONS
MANUAL_SUBJECT_CUTOUT_POLYGON_EDITOR = None
if not st.get_option("global.appTest"):
    MANUAL_SUBJECT_CUTOUT_POLYGON_EDITOR = st.components.v2.component(
        name="manual_subject_cutout_polygon_editor",
        html="""
<div class="text-cutout-editor">
  <svg viewBox="0 0 1080 1920" aria-label="Manual Subject Cutout polygon editor">
    <image id="background" x="0" y="0" width="1080" height="1920" preserveAspectRatio="none"></image>
    <polygon id="polygon" fill="#2f6255" fill-opacity=".16" stroke="#2f6255" stroke-width="5" vector-effect="non-scaling-stroke"></polygon>
    <g id="handles"></g>
  </svg>
  <div class="help">Drag a point to reshape. Drag inside the highlighted area to move the whole polygon. Click an edge to add a point.</div>
</div>
""",
        css="""
.text-cutout-editor{width:100%;height:100%;font-family:Inter,ui-sans-serif,sans-serif}
.text-cutout-editor svg{display:block;width:100%;height:100%;border:1px solid #d4d4cc;border-radius:12px;background:#111;touch-action:none}
.text-cutout-editor .handle{cursor:move}
.text-cutout-editor #polygon{cursor:grab}
.text-cutout-editor #polygon:active{cursor:grabbing}
.text-cutout-editor .help{margin:6px 0;color:#52574f;font-size:12px;line-height:1.2;opacity:.78}
""",
        js="""
export default function(component) {
    const { data, setStateValue, parentElement } = component;
    const svg = parentElement.querySelector("svg");
    const image = parentElement.querySelector("#background");
    const polygon = parentElement.querySelector("#polygon");
    const handles = parentElement.querySelector("#handles");
    if (!svg || !image || !polygon || !handles) return;

    image.setAttribute("href", "data:image/jpeg;base64," + data.image);

    if (!parentElement.__manualSubjectCutoutEditor) {
        const editor = {
            points: [],
            handles: [],
            draggingPoint: null,
            draggingPolygon: false,
            dragStart: null,
            originalPoints: null,
            moved: false,
            suppressClick: false,
            clamp(value, min, max) {
                return Math.max(min, Math.min(max, value));
            },
            svgPoint(event) {
                const rect = svg.getBoundingClientRect();
                return [
                    this.clamp((event.clientX - rect.left) / rect.width * 1080, 0, 1080),
                    this.clamp((event.clientY - rect.top) / rect.height * 1920, 0, 1920),
                ];
            },
            persist() {
                setStateValue("points", this.points.map((point) => [
                    Math.round(point[0]),
                    Math.round(point[1]),
                ]));
            },
            render() {
                polygon.setAttribute("points", this.points.map((point) => point.join(",")).join(" "));
                while (this.handles.length < this.points.length) {
                    const handle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    handle.setAttribute("class", "handle");
                    handle.setAttribute("r", "13");
                    handle.setAttribute("fill", "#fff");
                    handle.setAttribute("stroke", "#2f6255");
                    handle.setAttribute("stroke-width", "4");
                    handle.setAttribute("vector-effect", "non-scaling-stroke");
                    handles.appendChild(handle);
                    this.handles.push(handle);

                    handle.addEventListener("pointerdown", (event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        const index = Number(handle.dataset.index);
                        editor.draggingPoint = index;
                        editor.suppressClick = true;
                        handle.setPointerCapture(event.pointerId);

                        const move = (moveEvent) => {
                            const next = editor.svgPoint(moveEvent);
                            editor.points[index] = [Math.round(next[0]), Math.round(next[1])];
                            editor.render();
                        };
                        const stop = () => {
                            handle.removeEventListener("pointermove", move);
                            editor.draggingPoint = null;
                            editor.persist();
                        };
                        handle.addEventListener("pointermove", move);
                        handle.addEventListener("pointerup", stop, {once: true});
                        handle.addEventListener("pointercancel", stop, {once: true});
                    });
                }
                this.handles.forEach((handle, index) => {
                    handle.dataset.index = String(index);
                    handle.style.display = index < this.points.length ? "block" : "none";
                    if (index >= this.points.length) return;
                    handle.setAttribute("cx", this.points[index][0]);
                    handle.setAttribute("cy", this.points[index][1]);
                });
            },
        };

        parentElement.__manualSubjectCutoutEditor = editor;

        polygon.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();
            editor.draggingPolygon = true;
            editor.dragStart = editor.svgPoint(event);
            editor.originalPoints = editor.points.map((point) => [point[0], point[1]]);
            editor.moved = false;
            editor.suppressClick = false;
            svg.setPointerCapture(event.pointerId);
        });

        svg.addEventListener("pointermove", (event) => {
            if (!editor.draggingPolygon || !editor.dragStart || !editor.originalPoints) return;
            const current = editor.svgPoint(event);
            const dx = editor.clamp(
                current[0] - editor.dragStart[0],
                -Math.min(...editor.originalPoints.map((point) => point[0])),
                1080 - Math.max(...editor.originalPoints.map((point) => point[0])),
            );
            const dy = editor.clamp(
                current[1] - editor.dragStart[1],
                -Math.min(...editor.originalPoints.map((point) => point[1])),
                1920 - Math.max(...editor.originalPoints.map((point) => point[1])),
            );
            if (Math.hypot(dx, dy) <= 2) return;
            editor.moved = true;
            editor.suppressClick = true;
            editor.points = editor.originalPoints.map((point) => [
                Math.round(point[0] + dx),
                Math.round(point[1] + dy),
            ]);
            editor.render();
        });

        const stopPolygon = () => {
            if (!editor.draggingPolygon) return;
            if (editor.moved) editor.persist();
            editor.draggingPolygon = false;
            editor.dragStart = null;
            editor.originalPoints = null;
            editor.moved = false;
        };
        svg.addEventListener("pointerup", stopPolygon);
        svg.addEventListener("pointercancel", stopPolygon);

        svg.addEventListener("click", (event) => {
            if (editor.suppressClick || editor.draggingPoint !== null || editor.draggingPolygon) {
                editor.suppressClick = false;
                return;
            }
            if (event.target.classList && event.target.classList.contains("handle")) return;

            const point = editor.svgPoint(event);
            let best = null;
            editor.points.forEach((start, index) => {
                const end = editor.points[(index + 1) % editor.points.length];
                const dx = end[0] - start[0];
                const dy = end[1] - start[1];
                const length2 = dx * dx + dy * dy;
                const t = length2
                    ? editor.clamp(
                        ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2,
                        0,
                        1,
                    )
                    : 0;
                const projected = [start[0] + t * dx, start[1] + t * dy];
                const distance = Math.hypot(point[0] - projected[0], point[1] - projected[1]);
                if (!best || distance < best.distance) {
                    best = {index, distance, point: projected};
                }
            });

            if (!best || best.distance > 32) return;
            editor.points.splice(best.index + 1, 0, [
                Math.round(best.point[0]),
                Math.round(best.point[1]),
            ]);
            editor.render();
            editor.persist();
        });
    }

    const editor = parentElement.__manualSubjectCutoutEditor;
    editor.points = (data.points || []).map((point) => [Number(point[0]), Number(point[1])]);
    editor.render();
}
""",
    )
TOP5_VISUAL_OPTIONS = (
    "Option 1 · Automatic Scraper",
    "Option 2 · Manual Scraper",
    "Option 3 · Manual Fetcher",
    "Option 4 · AI Generation",
    "Option 5 · Card Studio",
)

STAGES = [
    {"key": "01 · Topic Fetcher", "number": "01", "label": "Topics", "desc": "Find the story"},
    {"key": "02 · Scriptwriter", "number": "02", "label": "Script", "desc": "Write the Short"},
    {"key": "03 · Audio", "number": "03", "label": "Audio", "desc": "Create voice"},
    {"key": "04 · Visuals", "number": "04", "label": "Visuals", "desc": "Source imagery"},
    {"key": "05 · Subtitles", "number": "05", "label": "Subs", "desc": "Build captions"},
    {"key": "06 · Renderer", "number": "06", "label": "Render", "desc": "Build video"},
    {"key": "07 · Upload QC", "number": "07", "label": "Upload", "desc": "Publish"},
]
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
  --bg: #f5f7fb;
  --surface: #ffffff;
  --surface-raised: #ffffff;
  --surface-soft: #f1f5f9;
  --surface-active: #eef2ff;
  --card-bg: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --ink: #0f172a;
  --ink-secondary: #334155;
  --muted: #64748b;
  --subtle: #94a3b8;
  --line: rgba(15, 23, 42, 0.08);
  --line-strong: rgba(15, 23, 42, 0.14);
  --primary: #4f46e5;
  --primary-hover: #4338ca;
  --accent: #2563eb;
  --accent-soft: rgba(37, 99, 235, 0.10);
  --accent-hover: #1d4ed8;
  --success: #059669;
  --success-soft: rgba(5, 150, 105, 0.10);
  --warning: #b45309;
  --warning-soft: rgba(180, 83, 9, 0.10);
  --danger: #dc2626;
  --danger-soft: rgba(220, 38, 38, 0.10);
  --focus: #4f46e5;
  --shadow-xs: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
  --shadow-sm: 0 2px 6px 0 rgba(15, 23, 42, 0.06);
  --shadow: 0 4px 14px -1px rgba(15, 23, 42, 0.08);
  --shadow-hover: 0 8px 24px -2px rgba(15, 23, 42, 0.12);
  --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

html, body, .stApp {
  font-family: var(--font-sans)!important;
  color: var(--ink)!important;
  background: var(--bg)!important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

[data-testid="stAppViewContainer"] { background: var(--bg)!important; }
[data-testid="stHeader"] { background: transparent!important; }
section[data-testid="stSidebar"] { display: none!important; }
footer, #MainMenu { visibility: hidden; }

.block-container {
  max-width: 1440px;
  padding: 24px 32px 64px!important;
}

/* Typography Hierarchy */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-sans)!important;
  color: var(--ink)!important;
  letter-spacing: -0.03em!important;
  font-weight: 850!important;
  margin: 0 0 0.5rem 0!important;
}
h1 { font-size: 2.1rem!important; line-height: 1.15!important; }
h2 { font-size: 1.5rem!important; line-height: 1.25!important; }
h3 { font-size: 1.2rem!important; line-height: 1.3!important; }
h4 { font-size: 1.05rem!important; line-height: 1.35!important; }

p { color: var(--muted); }
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] small { color: var(--muted)!important; font-size: 0.8rem!important; }
[data-testid="stMarkdownContainer"] strong { color: var(--ink); font-weight: 700; }

/* Awwwards Tactile Buttons */
button {
  font-family: var(--font-sans)!important;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1)!important;
}

[data-testid="stButton"] > button,
[data-testid="stFormSubmitButton"] > button {
  min-height: 44px;
  border-radius: 12px!important;
  border: 1px solid var(--line-strong)!important;
  background: var(--surface-raised)!important;
  color: var(--ink)!important;
  font-weight: 700!important;
  font-size: 0.875rem!important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05)!important;
  letter-spacing: -0.01em;
}

[data-testid="stButton"] > button p,
[data-testid="stFormSubmitButton"] > button p {
  color: inherit!important;
  font-weight: inherit!important;
  margin: 0!important;
}

[data-testid="stButton"] > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1.5px);
  border-color: rgba(99, 102, 241, 0.6)!important;
  background: var(--surface-active)!important;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.12)!important;
  color: var(--ink)!important;
}

[data-testid="stButton"] > button:active,
[data-testid="stFormSubmitButton"] > button:active {
  transform: translateY(0);
}

[data-testid="stButton"] > button[kind="primary"],
[data-testid="stButton"] > button[data-testid="baseButton-primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)!important;
  border: 1px solid rgba(129, 140, 248, 0.5)!important;
  color: #ffffff!important;
  font-weight: 800!important;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.16)!important;
}

[data-testid="stButton"] > button[kind="primary"] *,
[data-testid="stButton"] > button[data-testid="baseButton-primary"] *,
[data-testid="stFormSubmitButton"] > button[kind="primary"] *,
[data-testid="stFormSubmitButton"] > button[data-testid="baseButton-primary"] * {
  color: #ffffff!important;
}

[data-testid="stButton"] > button[kind="primary"]:hover,
[data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button[data-testid="baseButton-primary"]:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)!important;
  border-color: #818cf8!important;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.22)!important;
  transform: translateY(-1.5px);
}

/* Glass Studio Inputs & Text Areas */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stFileUploader"] label {
  color: var(--ink-secondary)!important;
  font-weight: 700!important;
  font-size: 0.8125rem!important;
  letter-spacing: -0.01em;
}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [role="combobox"] {
  background: var(--surface)!important;
  color: var(--ink)!important;
  border: 1px solid var(--line-strong)!important;
  border-radius: 12px!important;
  box-shadow: var(--shadow-xs)!important;
  font-size: 0.875rem!important;
  transition: all 0.15s ease;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: #64748b!important;
  opacity: 1;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stSelectbox"] [role="combobox"]:focus {
  border-color: var(--focus)!important;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12)!important;
}

/* Pills & Segmented Controls */
[data-testid="stPills"] {
  margin-bottom: 0.6rem;
  overflow-x: auto;
  scrollbar-width: none;
}
[data-testid="stPills"]::-webkit-scrollbar { display: none; }

[data-testid="stPills"] button {
  min-height: 36px!important;
  padding: 0.35rem 0.95rem!important;
  background: var(--surface)!important;
  color: var(--muted)!important;
  border: 1px solid var(--line)!important;
  border-radius: 999px!important;
  box-shadow: var(--shadow-xs)!important;
  font-weight: 700!important;
  font-size: 0.8125rem!important;
  white-space: nowrap;
}

[data-testid="stPills"] button:hover {
  color: var(--ink)!important;
  border-color: var(--line-strong)!important;
  background: var(--surface-soft)!important;
  transform: none;
}

[data-testid="stPills"] button[aria-pressed="true"] {
  background: var(--primary)!important;
  color: #ffffff!important;
  border-color: var(--primary)!important;
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.35)!important;
}

[data-testid="stPills"] button[aria-pressed="true"] * {
  color: #ffffff!important;
}

/* Pro Studio Navigation Bar */
.st-key-workspace-nav {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 12px 18px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}

.nav-brand {
  font-size: 1rem;
  font-weight: 850;
  letter-spacing: -0.03em;
  color: var(--ink);
}

.nav-sub {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--subtle);
  letter-spacing: 0.02em;
}

/* Home Page Hero & Workspaces */
.home-hero {
  padding: 32px 0 24px;
  max-width: 800px;
}
.home-kicker {
  font-size: 0.6875rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}
.home-title {
  font-size: clamp(2.4rem, 5vw, 3.5rem);
  font-weight: 850;
  line-height: 1.05;
  letter-spacing: -0.05em;
  margin: 8px 0 12px;
  color: var(--ink);
}
.home-copy {
  max-width: 560px;
  color: var(--muted);
  font-size: 0.925rem;
  line-height: 1.45;
}

.st-key-landing-test,
.st-key-landing-live {
  min-height: 250px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: var(--surface);
  position: relative;
  overflow: hidden;
  transition: all 0.18s ease;
}
.st-key-landing-test:hover,
.st-key-landing-live:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
}
.st-key-landing-test::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--accent);
}
.st-key-landing-live::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--success);
}
.home-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.workspace-index {
  font-size: 0.6875rem;
  font-weight: 800;
  color: var(--accent);
  letter-spacing: 0.08em;
}
.home-card-kind {
  font-size: 0.625rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--subtle);
}
.workspace-name {
  font-size: 2.25rem;
  font-weight: 850;
  letter-spacing: -0.05em;
  line-height: 1;
  margin: 12px 0 8px;
  color: var(--ink);
}
.workspace-desc {
  font-size: 0.85rem;
  color: var(--muted);
  line-height: 1.4;
  margin-bottom: 16px;
}

/* Production Line & Desk Choices */
.st-key-choice-cricket,
.st-key-choice-niche,
.st-key-choice-top5,
.st-key-choice-otd,
.st-key-choice-youtube-trends,
.st-key-live-choice-cricket,
.st-key-live-choice-niche,
.st-key-live-cricket-india,
.st-key-live-cricket-global,
.st-key-live-line-deep-dive,
.st-key-live-line-top-5,
.st-key-live-line-otd,
.st-key-live-line-youtube-trends {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 22px;
  min-height: 190px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: var(--shadow-sm);
  transition: all 0.18s ease;
}
.st-key-choice-cricket:hover,
.st-key-choice-niche:hover,
.st-key-choice-top5:hover,
.st-key-choice-otd:hover,
.st-key-choice-youtube-trends:hover,
.st-key-live-choice-cricket:hover,
.st-key-live-choice-niche:hover,
.st-key-live-cricket-india:hover,
.st-key-live-cricket-global:hover,
.st-key-live-line-deep-dive:hover,
.st-key-live-line-top-5:hover,
.st-key-live-line-otd:hover,
.st-key-live-line-youtube-trends:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
}
.choice-title {
  font-size: 1.65rem;
  font-weight: 850;
  letter-spacing: -0.04em;
  line-height: 1.15;
  margin: 6px 0 8px;
  color: var(--ink);
}
.choice-copy {
  font-size: 0.8125rem;
  color: var(--muted);
  line-height: 1.45;
}

/* Live Header Surface */
.live-product-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}
.live-product-title {
  font-size: clamp(2rem, 4.5vw, 3.25rem);
  font-weight: 850;
  letter-spacing: -0.05em;
  line-height: 1.05;
  margin-top: 6px;
  color: var(--ink);
}
.live-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  font-size: 0.72rem;
  font-weight: 750;
  white-space: nowrap;
  box-shadow: var(--shadow-sm);
}
.live-status span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 4px var(--success-soft);
}
.hero-subtitle {
  font-size: 0.875rem;
  color: var(--muted);
  max-width: 620px;
  line-height: 1.45;
  margin-top: 6px;
}

/* Pipeline Handoff Banner */
.handoff-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--success-soft);
  border: 1px solid #86efac;
  border-radius: 14px;
  padding: 12px 18px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(5, 150, 105, 0.08);
}
.handoff-mark {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--success);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 0.95rem;
  flex-shrink: 0;
}
.handoff-title {
  font-size: 0.875rem;
  font-weight: 800;
  color: var(--ink);
  line-height: 1.25;
}
.handoff-copy {
  font-size: 0.75rem;
  color: var(--muted);
  line-height: 1.35;
  margin-top: 2px;
}

/* Pipeline Stepper Rail */
.pipeline-wrap {
  position: relative;
  margin: 18px 0 22px;
  padding: 16px 18px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
}

.pipeline-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.pipeline-meta-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}

.pipeline-meta-value {
  font-size: 0.75rem;
  font-weight: 750;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.pipeline-steps {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 0 2px;
  scrollbar-width: none;
}
.pipeline-steps::-webkit-scrollbar { display: none; }

.pipeline-step {
  flex: 1 0 115px;
  min-width: 115px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface-soft);
  transition: all 0.16s cubic-bezier(0.16, 1, 0.3, 1);
}

.pipeline-step:hover {
  border-color: var(--line-strong);
  background: #ffffff;
  transform: translateY(-1px);
  box-shadow: var(--shadow-xs);
}

.pipeline-step.complete {
  background: var(--success-soft);
  border-color: #a7f3d0;
  box-shadow: inset 3px 0 0 var(--success);
}

.pipeline-step.current {
  background: #ffffff;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--accent-soft), var(--shadow-xs);
}

.pipeline-step-number {
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--subtle);
}

.pipeline-step.current .pipeline-step-number,
.pipeline-step.current .pipeline-step-label {
  color: var(--primary);
  font-weight: 800;
}

.pipeline-step.complete .pipeline-step-number,
.pipeline-step.complete .pipeline-step-label {
  color: var(--success);
}

.pipeline-step-label {
  margin-top: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pipeline-step-state {
  margin-top: 4px;
  font-size: 0.6rem;
  font-weight: 750;
  color: var(--subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.pipeline-step.current .pipeline-step-state { color: var(--accent); font-weight: 800; }
.pipeline-step.complete .pipeline-step-state { color: var(--success); }

/* Badges & Meta Chips */
.eyebrow, .mini-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--subtle);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 750;
  letter-spacing: -0.01em;
}

/* Editorial Canvas & Sections */
.canvas-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.canvas-title {
  font-size: 1.85rem;
  font-weight: 850;
  letter-spacing: -0.04em;
  line-height: 1.1;
  color: var(--ink);
}

.canvas-copy {
  font-size: 0.84rem;
  color: var(--muted);
  max-width: 720px;
  line-height: 1.45;
  margin-top: 6px;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin: 24px 0 12px;
}

.section-title {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.025em;
  color: var(--ink);
}

.section-count {
  font-size: 0.65rem;
  font-weight: 800;
  color: var(--subtle);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Story Discovery Deck */
.st-key-topic-toolbar {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 8px 12px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-xs);
}

.topic-title {
  font-size: 0.95rem;
  line-height: 1.3;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--ink);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  min-height: 3.6em;
  margin: 6px 0 6px;
}

.topic-meta {
  font-size: 0.68rem;
  color: var(--subtle);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topic-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 16px;
  margin-bottom: 4px;
}

.topic-rank {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--accent);
}

.topic-tile-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 0 0 8px;
  border-bottom: 1px solid var(--line);
  font-size: 0.625rem;
  font-weight: 750;
  color: var(--subtle);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

[data-testid="stVerticalBlock"] [class*="st-key-test-top5-topic-"],
[data-testid="stVerticalBlock"] [class*="st-key-live-topic-"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 10px;
  min-height: 165px;
  box-shadow: var(--shadow-xs);
  transition: all 0.16s ease;
}

[data-testid="stVerticalBlock"] [class*="st-key-test-top5-topic-"]:hover,
[data-testid="stVerticalBlock"] [class*="st-key-live-topic-"]:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow);
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-xs);
  overflow: hidden;
  transition: all 0.16s ease;
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"]:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow);
  transform: translateY(-1px);
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-header-"] [data-testid="stButton"] > button {
  min-height: 60px!important;
  justify-content: flex-start!important;
  text-align: left!important;
  padding: 0.9rem 1.1rem!important;
  border: 0!important;
  border-radius: 0!important;
  background: transparent!important;
  color: var(--ink)!important;
  font-size: 0.875rem!important;
  line-height: 1.35!important;
  font-weight: 700!important;
  box-shadow: none!important;
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-header-"] [data-testid="stButton"] > button:hover {
  background: var(--surface-soft)!important;
  transform: none!important;
  box-shadow: none!important;
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stHorizontalBlock"] {
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stHorizontalBlock"]:last-child {
  border-bottom: 0;
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] .topic-title {
  min-height: 0;
  margin: 0 0 4px;
}

[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stButton"] > button {
  min-height: 38px!important;
  padding: 0.35rem 0.75rem!important;
}

/* Selected Story Banner */
.st-key-selected-story-card {
  margin-top: 16px;
  background: var(--surface);
  border: 1.5px solid var(--accent);
  border-radius: 16px;
  padding: 16px 20px;
  box-shadow: 0 4px 18px rgba(79, 70, 229, 0.08);
}

.selected-story-title {
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1.25;
  color: var(--ink);
}

/* Storyboard Slide Cards & Dropzones */
.empty-slot {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 2px dashed var(--line-strong);
  border-radius: 14px;
  color: var(--subtle);
  background: var(--surface-soft);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  transition: all 0.15s ease;
}

.empty-slot:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.visual-source {
  font-size: 0.68rem;
  font-weight: 750;
  color: var(--ink);
  margin-top: 8px;
}

.visual-detail {
  font-size: 0.65rem;
  color: var(--muted);
  line-height: 1.35;
  margin-top: 3px;
}

.visual-crop-label {
  display: inline-flex;
  margin-top: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--success-soft);
  color: var(--success);
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.06em;
}

/* Visual Cards */
[data-testid="stVerticalBlock"] [class*="visual-card-"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 10px;
  box-shadow: var(--shadow-xs);
  transition: all 0.15s ease;
}

[data-testid="stVerticalBlock"] [class*="visual-card-"]:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow);
}

/* Audio Scene Deck Containers */
[data-testid="stVerticalBlock"] [class*="st-key-audio-scene-"],
[data-testid="stVerticalBlock"] [class*="st-key-live-top5-audio-scene-"],
[data-testid="stVerticalBlock"] [class*="st-key-test-top5-audio-scene-"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-xs);
}

/* Teleprompter & Inspectors */
.st-key-script-editor,
.st-key-subtitle-editor,
.st-key-renderer-inspector,
.st-key-audio-inspector {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.scene-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--subtle);
  margin: 12px 0 6px;
}

.inspector-line {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--line);
  font-size: 0.75rem;
}

.inspector-line:last-child { border-bottom: 0; }
.inspector-value { font-weight: 750; color: var(--ink); font-variant-numeric: tabular-nums; }

/* Streamlit Native Elements Overrides */
hr, [data-testid="stDivider"] {
  border: 0!important;
  border-top: 1px solid var(--line)!important;
  margin: 18px 0!important;
}

[data-testid="stVerticalBlockBorderWrapper"] > div {
  border-color: var(--line)!important;
  border-radius: 14px!important;
  background: var(--surface);
}

[data-testid="stExpander"] {
  background: var(--surface)!important;
  border: 1px solid var(--line)!important;
  border-radius: 14px!important;
  box-shadow: var(--shadow-xs)!important;
  overflow: hidden;
}

[data-testid="stExpander"] summary {
  padding: 0.85rem 1rem!important;
  color: var(--ink)!important;
  font-weight: 700!important;
}

[data-testid="stExpander"] summary:hover {
  background: var(--surface-soft)!important;
}

/* Clean Custom Scrollbars for Trays */
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="overflow"]::-webkit-scrollbar,
[data-testid="stContainer"][style*="overflow"]::-webkit-scrollbar,
div[style*="overflow-y"]::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="overflow"]::-webkit-scrollbar-thumb,
[data-testid="stContainer"][style*="overflow"]::-webkit-scrollbar-thumb,
div[style*="overflow-y"]::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 999px;
}
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="overflow"]::-webkit-scrollbar-track,
[data-testid="stContainer"][style*="overflow"]::-webkit-scrollbar-track,
div[style*="overflow-y"]::-webkit-scrollbar-track {
  background: var(--surface-soft);
}

/* Responsive adjustments */
@media(max-width: 900px) {
  .block-container { padding: 18px 18px 48px!important; }
  .canvas-title { font-size: 1.45rem; }
  .pipeline-step { flex-basis: 100px; min-width: 100px; }
}

/* Studio 2.0 Topic Radar & Story Discovery */
.radar-banner {
  background: var(--surface-raised);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px 20px;
  margin-bottom: 20px;
  color: var(--ink);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow-sm);
}
.radar-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.03em;
  background: var(--surface-soft);
  color: var(--ink-secondary);
  border: 1px solid var(--line);
}
.radar-topic-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-xs);
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.radar-topic-card:hover {
  border-color: #94a3b8;
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}
.radar-topic-card.selected-card {
  border: 2px solid var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow);
  background: #ffffff;
}

/* Studio 2.0 Broadcast Prompter Deck */
.prompter-flow-bar {
  background: var(--surface-raised);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 18px;
  margin-bottom: 18px;
  color: var(--ink);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow-sm);
}
.cue-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 14px 0 6px;
  padding: 6px 12px;
  background: var(--surface-soft);
  border-radius: 8px;
  border: 1px solid var(--line);
}
.cue-role-title {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink);
}
.hook-meter-ok {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 800;
}
.hook-meter-warn {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fde68a;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 800;
}
.hook-meter-bad {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 800;
}
.teleprompter-article-view {
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px 20px;
  color: var(--ink);
  font-size: 0.95rem;
  line-height: 1.6;
  letter-spacing: -0.01em;
  margin-top: 12px;
  box-shadow: var(--shadow-xs);
}
.teleprompter-article-view strong {
  color: var(--primary);
  font-weight: 800;
}
.teleprompter-cue-separator {
  display: inline-block;
  margin: 0 6px;
  color: #64748b;
  font-weight: 700;
}

/* Awwwards Studio 2.0 Bento Angles */
.angle-bento-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.angle-bento-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 18px;
  border: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 190px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: var(--shadow-sm);
}
.angle-bento-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.5);
  box-shadow: var(--shadow);
}
.angle-bento-card.active-angle {
  border: 2px solid var(--primary);
  background: var(--surface-active);
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.10);
}
.angle-pill-debate {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
  padding: 3px 8px;
  border-radius: 999px;
}
.angle-pill-stat {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  padding: 3px 8px;
  border-radius: 999px;
}
.angle-pill-drama {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: #f5f3ff;
  color: #6d28d9;
  border: 1px solid #ddd6fe;
  padding: 3px 8px;
  border-radius: 999px;
}

/* Custom Prompt Terminal */
.custom-prompt-terminal {
  background: var(--surface-raised);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  margin-top: 14px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
}
.custom-prompt-terminal.active-terminal {
  border: 2px solid var(--primary);
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.10);
}

/* 9:16 Interactive Mobile Phone Simulator */
.phone-sim-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 0;
}
.phone-sim-frame {
  width: 260px;
  height: 480px;
  background: #000000;
  border-radius: 36px;
  border: 4px solid #1e2236;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), inset 0 0 0 2px rgba(255, 255, 255, 0.05);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px 14px 18px;
}
.phone-sim-notch {
  width: 90px;
  height: 16px;
  background: #111422;
  border-radius: 0 0 12px 12px;
  margin: -14px auto 14px;
}
.phone-billboard-badge {
  background: #ef4444;
  color: #ffffff;
  font-size: 0.65rem;
  font-weight: 900;
  letter-spacing: 0.05em;
  padding: 4px 10px;
  border-radius: 6px;
  text-align: center;
  text-transform: uppercase;
  margin-bottom: 8px;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
}
.phone-sim-headline {
  background: rgba(0, 0, 0, 0.85);
  color: #facc15;
  font-size: 1.05rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  text-align: center;
  line-height: 1.15;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(250, 204, 21, 0.3);
  text-transform: uppercase;
  margin-bottom: 12px;
  text-shadow: 0 2px 4px rgba(0,0,0,0.8);
}
.phone-sim-preview-video {
  flex: 1;
  background: linear-gradient(180deg, #141829 0%, #0a0d17 100%);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
}
.phone-sim-hook-text {
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  padding: 8px 10px;
  color: #ffffff;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1.3;
  border-left: 3px solid #38bdf8;
}
.phone-sim-ui-overlay {
  position: absolute;
  right: 8px;
  bottom: 50px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}
.phone-sim-action-btn {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  color: #fff;
}

/* Viral Packaging Suite */
.packaging-tile {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  transition: all 0.15s ease;
}
.packaging-tile:hover {
  border-color: rgba(99, 102, 241, 0.5);
  background: var(--surface-raised);
}
.packaging-tile-type {
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.packaging-tile-text {
  font-size: 0.85rem;
  font-weight: 750;
  color: var(--ink);
  line-height: 1.3;
}
.comment-bait-container {
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 14px;
  margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "home"
if "factory_format" not in st.session_state:
    st.session_state.factory_format = None
if "longform_test_stage" not in st.session_state:
    st.session_state.longform_test_stage = "01 · Topic Fetcher"
if "longform_topic_keyword" not in st.session_state:
    st.session_state.longform_topic_keyword = ""
if "longform_topics" not in st.session_state:
    st.session_state.longform_topics = []
if "longform_selected_topic" not in st.session_state:
    st.session_state.longform_selected_topic = None
if "longform_approved_topic" not in st.session_state:
    st.session_state.longform_approved_topic = None
if "longform_topic_error" not in st.session_state:
    st.session_state.longform_topic_error = ""
if "longform_script_data" not in st.session_state:
    st.session_state.longform_script_data = None
if "longform_approved_script" not in st.session_state:
    st.session_state.longform_approved_script = None
if "longform_script_error" not in st.session_state:
    st.session_state.longform_script_error = ""
if "longform_visuals_data" not in st.session_state:
    st.session_state.longform_visuals_data = None
if "longform_approved_visuals" not in st.session_state:
    st.session_state.longform_approved_visuals = None
if "longform_visuals_error" not in st.session_state:
    st.session_state.longform_visuals_error = ""
if "longform_audio_data" not in st.session_state:
    st.session_state.longform_audio_data = None
if "longform_approved_audio" not in st.session_state:
    st.session_state.longform_approved_audio = None
if "longform_audio_error" not in st.session_state:
    st.session_state.longform_audio_error = ""
if "longform_subtitles_data" not in st.session_state:
    st.session_state.longform_subtitles_data = None
if "longform_approved_subtitles" not in st.session_state:
    st.session_state.longform_approved_subtitles = None
if "longform_subtitles_error" not in st.session_state:
    st.session_state.longform_subtitles_error = ""
if "longform_rendered_video" not in st.session_state:
    st.session_state.longform_rendered_video = None
if "longform_approved_video" not in st.session_state:
    st.session_state.longform_approved_video = None
if "longform_render_error" not in st.session_state:
    st.session_state.longform_render_error = ""
if "longform_upload_result" not in st.session_state:
    st.session_state.longform_upload_result = None
if "longform_upload_error" not in st.session_state:
    st.session_state.longform_upload_error = ""

# Long-form Live session state
if "longform_live_stage" not in st.session_state:
    st.session_state.longform_live_stage = "01 · Topic Fetcher"
if "longform_live_topic_keyword" not in st.session_state:
    st.session_state.longform_live_topic_keyword = ""
if "longform_live_topics" not in st.session_state:
    st.session_state.longform_live_topics = []
if "longform_live_selected_topic" not in st.session_state:
    st.session_state.longform_live_selected_topic = None
if "longform_live_approved_topic" not in st.session_state:
    st.session_state.longform_live_approved_topic = None
if "longform_live_topic_error" not in st.session_state:
    st.session_state.longform_live_topic_error = ""
if "longform_live_script_data" not in st.session_state:
    st.session_state.longform_live_script_data = None
if "longform_live_approved_script" not in st.session_state:
    st.session_state.longform_live_approved_script = None
if "longform_live_script_error" not in st.session_state:
    st.session_state.longform_live_script_error = ""
if "longform_live_visuals_data" not in st.session_state:
    st.session_state.longform_live_visuals_data = None
if "longform_live_approved_visuals" not in st.session_state:
    st.session_state.longform_live_approved_visuals = None
if "longform_live_visuals_error" not in st.session_state:
    st.session_state.longform_live_visuals_error = ""
if "longform_live_audio_data" not in st.session_state:
    st.session_state.longform_live_audio_data = None
if "longform_live_approved_audio" not in st.session_state:
    st.session_state.longform_live_approved_audio = None
if "longform_live_audio_error" not in st.session_state:
    st.session_state.longform_live_audio_error = ""
if "longform_live_subtitles_data" not in st.session_state:
    st.session_state.longform_live_subtitles_data = None
if "longform_live_approved_subtitles" not in st.session_state:
    st.session_state.longform_live_approved_subtitles = None
if "longform_live_subtitles_error" not in st.session_state:
    st.session_state.longform_live_subtitles_error = ""
if "longform_live_rendered_video" not in st.session_state:
    st.session_state.longform_live_rendered_video = None
if "longform_live_approved_video" not in st.session_state:
    st.session_state.longform_live_approved_video = None
if "longform_live_render_error" not in st.session_state:
    st.session_state.longform_live_render_error = ""
if "longform_live_upload_result" not in st.session_state:
    st.session_state.longform_live_upload_result = None
if "longform_live_upload_error" not in st.session_state:
    st.session_state.longform_live_upload_error = ""
if "test_production_line" not in st.session_state:
    st.session_state.test_production_line = None
if "test_stage" not in st.session_state:
    st.session_state.test_stage = "01 · Topic Fetcher"
if "test_top5_content_type" not in st.session_state:
    st.session_state.test_top5_content_type = "Cricket"
if "test_top5_topics" not in st.session_state:
    st.session_state.test_top5_topics = []
if "test_top5_selected" not in st.session_state:
    st.session_state.test_top5_selected = []
if "test_top5_topic_open_tile" not in st.session_state:
    st.session_state.test_top5_topic_open_tile = None
if "test_top5_handoff" not in st.session_state:
    st.session_state.test_top5_handoff = None
if "test_top5_script_data" not in st.session_state:
    st.session_state.test_top5_script_data = None
if "test_top5_script_handoff" not in st.session_state:
    st.session_state.test_top5_script_handoff = None
if "test_top5_audio_data" not in st.session_state:
    st.session_state.test_top5_audio_data = None
if "test_top5_audio_handoff" not in st.session_state:
    st.session_state.test_top5_audio_handoff = None
if "test_top5_visual_crops" not in st.session_state:
    st.session_state.test_top5_visual_crops = {}
if "test_top5_visual_results" not in st.session_state:
    st.session_state.test_top5_visual_results = {}
if "test_top5_visual_selected" not in st.session_state:
    st.session_state.test_top5_visual_selected = {}
if "test_top5_visual_previews" not in st.session_state:
    st.session_state.test_top5_visual_previews = {}
if "test_top5_visual_assignments" not in st.session_state:
    st.session_state.test_top5_visual_assignments = {}
if "test_top5_visual_handoff" not in st.session_state:
    st.session_state.test_top5_visual_handoff = None
if "test_top5_manual_subject_cutouts" not in st.session_state:
    st.session_state.test_top5_manual_subject_cutouts = {}
if "manual_subject_cutout" not in st.session_state:
    st.session_state.manual_subject_cutout = {}
if "test_top5_manual_subject_playground" not in st.session_state:
    st.session_state.test_top5_manual_subject_playground = {}
if "test_top5_rendered_video_path" not in st.session_state:
    st.session_state.test_top5_rendered_video_path = None
if "test_top5_upload_qc_approved" not in st.session_state:
    st.session_state.test_top5_upload_qc_approved = False
if "test_top5_upload_qc" not in st.session_state:
    st.session_state.test_top5_upload_qc = None
if "test_top5_upload_description" not in st.session_state:
    st.session_state.test_top5_upload_description = ""
if "test_top5_upload_hashtags" not in st.session_state:
    st.session_state.test_top5_upload_hashtags = ""
if "test_top5_upload_comment" not in st.session_state:
    st.session_state.test_top5_upload_comment = ""
if "test_top5_upload_result" not in st.session_state:
    st.session_state.test_top5_upload_result = None
if "test_pipeline_notice" not in st.session_state:
    st.session_state.test_pipeline_notice = None
if "visual_crops" not in st.session_state:
    st.session_state.visual_crops = {}
if "visual_deleted" not in st.session_state:
    st.session_state.visual_deleted = set()
if "visual_assignments" not in st.session_state:
    st.session_state.visual_assignments = {}
if "approved_visuals" not in st.session_state:
    st.session_state.approved_visuals = None
if "visuals_approved" not in st.session_state:
    st.session_state.visuals_approved = False
if "topics" not in st.session_state:
    st.session_state.topics = []
if "topic_keyword" not in st.session_state:
    st.session_state.topic_keyword = ""
if "youtube_trend_results" not in st.session_state:
    st.session_state.youtube_trend_results = []
if "youtube_trend_selected" not in st.session_state:
    st.session_state.youtube_trend_selected = None
if "youtube_trend_keyword" not in st.session_state:
    st.session_state.youtube_trend_keyword = ""
if "youtube_trend_search_query" not in st.session_state:
    st.session_state.youtube_trend_search_query = ""
if "youtube_trend_error" not in st.session_state:
    st.session_state.youtube_trend_error = ""
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None
if "topic_open_tile" not in st.session_state:
    st.session_state.topic_open_tile = None
if "test_universal_angles" not in st.session_state:
    st.session_state.test_universal_angles = None
if "test_universal_angle_source" not in st.session_state:
    st.session_state.test_universal_angle_source = None
if "test_universal_angle_selected" not in st.session_state:
    st.session_state.test_universal_angle_selected = 0
if "test_universal_angle_custom" not in st.session_state:
    st.session_state.test_universal_angle_custom = ""
if "test_universal_angle_story_key" not in st.session_state:
    st.session_state.test_universal_angle_story_key = None

if "script_data" not in st.session_state:
    st.session_state.script_data = None
if "approved_script" not in st.session_state:
    st.session_state.approved_script = None
if "audio_data" not in st.session_state:
    st.session_state.audio_data = None
if "approved_audio" not in st.session_state:
    st.session_state.approved_audio = None
if "subtitle_data" not in st.session_state:
    st.session_state.subtitle_data = None
if "approved_subtitles" not in st.session_state:
    st.session_state.approved_subtitles = None
if "visual_result" not in st.session_state:
    st.session_state.visual_result = None
if "visual_loaded_story" not in st.session_state:
    st.session_state.visual_loaded_story = None
if "rendered_video_path" not in st.session_state:
    st.session_state.rendered_video_path = None
if "upload_qc_approved" not in st.session_state:
    st.session_state.upload_qc_approved = False
if "upload_result" not in st.session_state:
    st.session_state.upload_result = None
if "upload_qc" not in st.session_state:
    st.session_state.upload_qc = None
if "upload_title_options" not in st.session_state:
    st.session_state.upload_title_options = []
if "upload_title_choice" not in st.session_state:
    st.session_state.upload_title_choice = 0
if "upload_description" not in st.session_state:
    st.session_state.upload_description = ""
if "upload_hashtags" not in st.session_state:
    st.session_state.upload_hashtags = ""
if "upload_comment" not in st.session_state:
    st.session_state.upload_comment = ""
if "manual_visual_result" not in st.session_state:
    st.session_state.manual_visual_result = None
if "real_image_result" not in st.session_state:
    st.session_state.real_image_result = None
if "ai_image_result" not in st.session_state:
    st.session_state.ai_image_result = None
if "live_production_line" not in st.session_state:
    st.session_state.live_production_line = None
if "live_desk" not in st.session_state:
    st.session_state.live_desk = None
if "live_cricket_profile" not in st.session_state:
    st.session_state.live_cricket_profile = None
if "live_topics" not in st.session_state:
    st.session_state.live_topics = []
if "live_topic_keyword" not in st.session_state:
    st.session_state.live_topic_keyword = ""
if "live_topic_open_tile" not in st.session_state:
    st.session_state.live_topic_open_tile = None
if "live_selected_topic" not in st.session_state:
    st.session_state.live_selected_topic = None
if "live_stage" not in st.session_state:
    st.session_state.live_stage = "01 · Story"
if "live_topics_profile" not in st.session_state:
    st.session_state.live_topics_profile = None
if "live_youtube_trend_results" not in st.session_state:
    st.session_state.live_youtube_trend_results = []
if "live_youtube_trend_selected" not in st.session_state:
    st.session_state.live_youtube_trend_selected = None
if "live_youtube_trend_keyword" not in st.session_state:
    st.session_state.live_youtube_trend_keyword = ""
if "live_youtube_trend_search_query" not in st.session_state:
    st.session_state.live_youtube_trend_search_query = ""
if "live_youtube_trend_error" not in st.session_state:
    st.session_state.live_youtube_trend_error = ""
if "live_universal_angles" not in st.session_state:
    st.session_state.live_universal_angles = None
if "live_universal_angle_source" not in st.session_state:
    st.session_state.live_universal_angle_source = None
if "live_universal_angle_selected" not in st.session_state:
    st.session_state.live_universal_angle_selected = 0
if "live_universal_angle_custom" not in st.session_state:
    st.session_state.live_universal_angle_custom = ""
if "live_universal_angle_story_key" not in st.session_state:
    st.session_state.live_universal_angle_story_key = None

if "live_script_data" not in st.session_state:
    st.session_state.live_script_data = None
if "live_approved_script" not in st.session_state:
    st.session_state.live_approved_script = None
if "live_script_error" not in st.session_state:
    st.session_state.live_script_error = ""
if "live_audio_data" not in st.session_state:
    st.session_state.live_audio_data = None
if "live_approved_audio" not in st.session_state:
    st.session_state.live_approved_audio = None
if "live_subtitle_data" not in st.session_state:
    st.session_state.live_subtitle_data = None
if "live_handoff_error" not in st.session_state:
    st.session_state.live_handoff_error = ""
if "live_visual_result" not in st.session_state:
    st.session_state.live_visual_result = None
if "live_manual_visual_result" not in st.session_state:
    st.session_state.live_manual_visual_result = None
if "live_real_image_result" not in st.session_state:
    st.session_state.live_real_image_result = None
if "live_ai_image_result" not in st.session_state:
    st.session_state.live_ai_image_result = None
if "live_manual_subject_cutout" not in st.session_state:
    st.session_state.live_manual_subject_cutout = {}
if "live_visual_option" not in st.session_state:
    st.session_state.live_visual_option = "Option 1 · Automatic Scraper"
if "live_script_language" not in st.session_state:
    st.session_state.live_script_language = "english"
if "live_headline_enabled" not in st.session_state:
    st.session_state.live_headline_enabled = True
if "live_top5_topics" not in st.session_state:
    st.session_state.live_top5_topics = []
if "live_top5_selected" not in st.session_state:
    st.session_state.live_top5_selected = []
if "live_top5_topic_open_tile" not in st.session_state:
    st.session_state.live_top5_topic_open_tile = None
if "live_top5_handoff" not in st.session_state:
    st.session_state.live_top5_handoff = None
if "live_top5_script_data" not in st.session_state:
    st.session_state.live_top5_script_data = None
if "live_top5_script_handoff" not in st.session_state:
    st.session_state.live_top5_script_handoff = None
if "live_top5_audio_data" not in st.session_state:
    st.session_state.live_top5_audio_data = None
if "live_top5_audio_handoff" not in st.session_state:
    st.session_state.live_top5_audio_handoff = None
if "live_top5_visual_results" not in st.session_state:
    st.session_state.live_top5_visual_results = {}
if "live_top5_manual_visual_results" not in st.session_state:
    st.session_state.live_top5_manual_visual_results = {}
if "live_top5_real_image_results" not in st.session_state:
    st.session_state.live_top5_real_image_results = {}
if "live_top5_ai_image_results" not in st.session_state:
    st.session_state.live_top5_ai_image_results = {}
if "live_top5_visual_handoff" not in st.session_state:
    st.session_state.live_top5_visual_handoff = None
if "live_top5_visual_done" not in st.session_state:
    st.session_state.live_top5_visual_done = {}
if "live_top5_visual_futures" not in st.session_state:
    st.session_state.live_top5_visual_futures = {}
if "live_top5_visual_active_slide" not in st.session_state:
    st.session_state.live_top5_visual_active_slide = 1
if "live_visual_crops" not in st.session_state:
    st.session_state.live_visual_crops = {}
if "live_visual_deleted" not in st.session_state:
    st.session_state.live_visual_deleted = set()
if "live_visual_assignments" not in st.session_state:
    st.session_state.live_visual_assignments = {}
if "live_visuals_approved" not in st.session_state:
    st.session_state.live_visuals_approved = False
if "live_rendered_video_path" not in st.session_state:
    st.session_state.live_rendered_video_path = None
if "live_render_error" not in st.session_state:
    st.session_state.live_render_error = ""
if "live_upload_qc_approved" not in st.session_state:
    st.session_state.live_upload_qc_approved = False
if "live_upload_qc" not in st.session_state:
    st.session_state.live_upload_qc = None
if "live_upload_result" not in st.session_state:
    st.session_state.live_upload_result = None
if "live_upload_titles" not in st.session_state:
    st.session_state.live_upload_titles = []
if "live_upload_title_choice" not in st.session_state:
    st.session_state.live_upload_title_choice = 0
if "live_upload_description" not in st.session_state:
    st.session_state.live_upload_description = ""
if "live_upload_hashtags" not in st.session_state:
    st.session_state.live_upload_hashtags = ""
if "live_upload_comment" not in st.session_state:
    st.session_state.live_upload_comment = ""
if "live_pipeline_notice" not in st.session_state:
    st.session_state.live_pipeline_notice = None
def _asset_to_image(value):
    from PIL import Image
    try:
        if isinstance(value, Image.Image):
            return value.convert("RGB")
        if isinstance(value, (bytes, bytearray)):
            with Image.open(BytesIO(bytes(value))) as image:
                return image.convert("RGB")
    except (OSError, ValueError):
        return None
    return None


@st.cache_data(max_entries=256, show_spinner=False)
def _is_valid_image_payload(value: bytes) -> bool:
    try:
        with Image.open(BytesIO(value)) as image:
            image.verify()
    except (OSError, ValueError, SyntaxError):
        return False
    return True


def _largest_9x16_crop_coords(image: Image.Image) -> tuple[int, int, int, int]:
    aspect = 9 / 16
    width = min(image.width, max(1, int(image.height * aspect)))
    height = min(image.height, max(1, int(width / aspect)))
    left = max(0, (image.width - width) // 2)
    top = max(0, (image.height - height) // 2)
    return (left, left + width, top, top + height)


@st.cache_data(max_entries=24, show_spinner=False)
def _prepare_crop_dialog_canvas(image_bytes: bytes, max_canvas_width: int = 1600):
    """Build the bounded crop canvas once per source image, not on every drag."""
    from PIL import Image, ImageFilter, ImageOps

    image = _asset_to_image(image_bytes)
    if image is None:
        return None, None, (0, 0)

    canvas_width = max(image.width, int(round(image.height * 9 / 16)))
    canvas_height = int(round(canvas_width * 16 / 9))
    scale = min(1.0, max_canvas_width / canvas_width)
    scaled_canvas_width = max(1, int(round(canvas_width * scale)))
    scaled_canvas_height = max(1, int(round(canvas_height * scale)))

    rgb_image = image.convert("RGB")
    if scale < 1.0:
        working_image = rgb_image.resize(
            (
                max(1, int(round(rgb_image.width * scale))),
                max(1, int(round(rgb_image.height * scale))),
            ),
            Image.Resampling.LANCZOS,
        )
    else:
        working_image = rgb_image

    background = ImageOps.fit(
        working_image,
        (scaled_canvas_width, scaled_canvas_height),
        method=Image.Resampling.LANCZOS,
    ).filter(ImageFilter.GaussianBlur(radius=max(18, scaled_canvas_width // 55)))
    canvas = background.copy()
    offset_x = (scaled_canvas_width - working_image.width) // 2
    offset_y = (scaled_canvas_height - working_image.height) // 2
    canvas.paste(working_image, (offset_x, offset_y))

    default = _largest_9x16_crop_coords(working_image)
    default_coords = (
        offset_x + default[0],
        offset_x + default[1],
        offset_y + default[2],
        offset_y + default[3],
    )
    return canvas, default_coords, (image.width, image.height)


def _visual_asset_key(result_key: str, index: int, asset: dict) -> str:
    identity = (
        str(asset.get("source_page_url") or asset.get("url") or "")
        + "|"
        + str(asset.get("article_title") or asset.get("model") or "")
        + "|"
        + str(index)
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"{result_key}-{digest}"


@st.dialog("Crop visual", width="large")
def _crop_visual_dialog(
    asset_key: str,
    image_bytes: bytes,
    label: str,
    crop_store: str = "visual_crops",
    card_selector: bool = False,
):
    canvas, default_coords, original_size = _prepare_crop_dialog_canvas(
        bytes(image_bytes), max_canvas_width=1600
    )
    if canvas is None:
        st.error("This visual could not be opened for cropping.")
        return

    st.markdown('<div class="crop-dialog-kicker">MANUAL CROP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="crop-dialog-title">{label}</div>', unsafe_allow_html=True)
    if card_selector:
        st.caption(
            "9:16 frame · drag to reposition or resize the crop. The preview follows your selection; "
            "click Apply crop when the framing is right. Zooming out reveals a blurred extension of the same image."
        )
    else:
        st.caption(
            "9:16 frame · drag to reposition or resize the crop. Double-click to confirm the crop selection. "
            "Zooming out reveals a blurred extension of the same image."
        )

    from streamlit_cropper import st_cropper

    store = st.session_state.setdefault(crop_store, {})
    cropped = st_cropper(
        canvas,
        realtime_update=card_selector,
        default_coords=default_coords,
        box_color="#4F46E5",
        aspect_ratio=(9, 16),
        return_type="image",
        key=f"cropper-{hashlib.sha1(asset_key.encode('utf-8')).hexdigest()[:12]}",
        stroke_width=2,
    )

    left, right = st.columns([1.2, .8], gap="large")
    with left:
        st.markdown('<div class="crop-dialog-kicker">PREVIEW</div>', unsafe_allow_html=True)
        st.image(cropped, width="stretch")
    with right:
        st.markdown('<div class="crop-dialog-kicker">ORIGINAL SIZE</div>', unsafe_allow_html=True)
        st.caption(f"{original_size[0]} × {original_size[1]}px")
        st.markdown('<div class="crop-dialog-kicker" style="margin-top:1rem;">OUTPUT</div>', unsafe_allow_html=True)
        st.caption("Applying the crop changes the selected slide framing only; the original visual stays untouched.")
        if st.button("Apply crop", type="primary", width="stretch"):
            buffer = BytesIO()
            cropped.convert("RGB").save(buffer, format="JPEG", quality=92, optimize=True)
            crop_bytes = buffer.getvalue()
            store[asset_key] = crop_bytes
            assignments = st.session_state.get("live_visual_assignments") or {}
            for assignment in assignments.values():
                if assignment.get("asset_key") == asset_key:
                    assignment["bytes"] = crop_bytes
            invalidated_cards = 0
            if card_selector:
                from card_studio import invalidate_card_studio_results_for_source

                invalidated_cards = invalidate_card_studio_results_for_source(
                    st.session_state, asset_key
                )
            if invalidated_cards:
                st.toast("Crop applied. Re-render the card and add it to the slide again.", icon="✂️")
            st.rerun()


@st.fragment
def _render_manual_subject_cutout(
    *,
    state: dict,
    assets: list[dict],
    crop_store: dict,
    crop_store_name: str,
    state_id: str,
    default_headline: str,
    handoff: str | None = None,
    slide_count: int = 0,
    active_slide: int | None = None,
    assignment_store: dict | None = None,
    approval_state: str | None = None,
    polygon_flow: bool = True,
):
    from renderer import (
        MANUAL_SUBJECT_FONT_OPTIONS,
        MANUAL_SUBJECT_STYLE_OPTIONS,
        build_manual_subject_cutout_layout_previews,
        build_manual_subject_cutout_preview,
    )

    if not assets:
        st.info("No existing images are available for Manual Subject Cutout.")
        return

    for key, value in {
        "image_key": None,
        "mode": "Negative Space",
        "font": "Barlow Condensed",
        "style": "Crisp Outline",
        "headline_source": "",
        "polygon_points": None,
        "font_size": 150,
        "line_breaks": None,
        "layout_options": None,
        "layout_signature": None,
        "rendered_config": None,
        "rendered_preview": None,
        "source_key": None,
        "source_digest": None,
        "editor_image_digest": None,
        "editor_image_data": None,
    }.items():
        state.setdefault(key, value)

    default_headline = str(default_headline or "").strip()
    headline_key = f"{state_id}-headline"
    size_key = f"{state_id}-font-size"

    if state["headline_source"] != default_headline:
        state.update(
            headline_source=default_headline,
            rendered_config=None,
            rendered_preview=None,
            font_size=150,
            line_breaks=None,
            layout_options=None,
            layout_signature=None,
        )
        st.session_state.pop(headline_key, None)
        st.session_state.pop(size_key, None)

    asset_map = {str(asset["asset_key"]): asset for asset in assets}
    selected_key = str(state.get("image_key") or "")
    if selected_key not in asset_map:
        shared_selected = str(st.session_state.get("card_studio_selected_asset_key") or "")
        if shared_selected in asset_map:
            state["image_key"] = shared_selected
        else:
            state["image_key"] = None

    if len(assets) == 1:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:space-between;margin:0.35rem 0 0.55rem 0;font-size:0.75rem;color:var(--muted);">'
            '<span><strong style="color:var(--accent);">1 image transferred from fetcher</strong> · active subject</span>'
            '<span>Crop or position for polygon cutout</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin:0.35rem 0 0.55rem 0;font-size:0.75rem;color:var(--muted);">'
            f'<span><strong>{len(assets)} images available</strong> · scroll inside tray to select subject image</span>'
            f'<span>Crop or select image for polygon cutout</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    container_ctx = st.container(height=520) if len(assets) > 1 else st.container()
    with container_ctx:
        for start in range(0, len(assets), 4):
            cols = st.columns(min(4, len(assets) - start), gap="small")
            for col, asset in zip(cols, assets[start:start + 4]):
                with col:
                    asset_key = str(asset["asset_key"])
                    raw_preview = crop_store.get(asset_key) or asset.get("bytes")
                    preview = _fit_visual_preview(raw_preview, width=240, height=360)
                    if preview is not None:
                        st.image(preview, width="stretch")
                    st.markdown(
                        f'<div class="visual-source">{asset["source"]}</div>'
                        f'<div class="visual-detail">{asset["label"]}</div>',
                        unsafe_allow_html=True,
                    )
                    if asset_key in crop_store:
                        st.markdown('<div class="visual-crop-label">CROP APPLIED</div>', unsafe_allow_html=True)

                    crop_col, select_col = st.columns(2, gap="small")
                    with crop_col:
                        if st.button("Crop / reposition", width="stretch", key=f"{state_id}-crop-{asset_key}"):
                            raw = asset.get("bytes")
                            if isinstance(raw, (bytes, bytearray)):
                                _crop_visual_dialog(
                                    asset_key,
                                    bytes(raw),
                                    str(asset["label"]),
                                    crop_store=crop_store_name,
                                 )
                            else:
                                st.warning("This visual is not crop-ready.")

                    with select_col:
                        is_selected_image = asset_key == str(state.get("image_key") or "")
                        if st.button(
                            "Selected" if is_selected_image else "Select image",
                            type="primary" if is_selected_image else "secondary",
                            width="stretch",
                            key=f"{state_id}-select-{asset_key}",
                        ) and not is_selected_image:
                            state.update(
                                image_key=asset_key,
                                polygon_points=None,
                                rendered_config=None,
                                rendered_preview=None,
                                font_size=150,
                                line_breaks=None,
                                layout_options=None,
                                layout_signature=None,
                                source_key=None,
                                source_digest=None,
                                editor_image_digest=None,
                                editor_image_data=None,
                            )
                            st.session_state["card_studio_selected_asset_key"] = asset_key
                            st.session_state.pop(size_key, None)

    selected = asset_map.get(str(state.get("image_key") or ""))
    if selected is None:
        return

    working_bytes = crop_store.get(selected["asset_key"]) or selected.get("bytes")
    if not isinstance(working_bytes, (bytes, bytearray)):
        st.error("The selected image does not contain a usable image payload.")
        return

    working_bytes = bytes(working_bytes)
    source_digest = hashlib.sha1(working_bytes).hexdigest()[:12]
    if state.get("source_key") != selected["asset_key"] or state.get("source_digest") != source_digest:
        state.update(
            source_key=selected["asset_key"],
            source_digest=source_digest,
            polygon_points=None,
            rendered_config=None,
            rendered_preview=None,
            font_size=150,
            line_breaks=None,
            layout_options=None,
            layout_signature=None,
            editor_image_digest=None,
            editor_image_data=None,
        )
        st.session_state.pop(size_key, None)

    if (handoff == "cricket" and assignment_store is not None and slide_count > 0) or (handoff == "top5" and active_slide is not None):
        with st.container():
            st.markdown(
                '<div style="background:var(--surface-soft, rgba(255,255,255,0.03));border:1px solid var(--line, rgba(255,255,255,0.08));border-radius:8px;padding:8px 12px;margin:8px 0 14px 0;">'
                '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
                '<span style="font-size:0.75rem;font-weight:700;color:var(--ink-secondary, #94a3b8);letter-spacing:0.04em;">📌 DIRECT SLIDE ATTACHMENT</span>'
                '<span style="font-size:0.72rem;color:var(--text-muted, #64748b);">Attach this image directly to a slide without creating a card</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            col_target, col_btn = st.columns([1, 1.6], gap="small", vertical_alignment="center")
            with col_target:
                if handoff == "top5" and active_slide is not None:
                    target_slide = active_slide
                    st.markdown(f'<div style="font-weight:700;font-size:0.85rem;color:var(--ink);">Target: Slide {active_slide}</div>', unsafe_allow_html=True)
                else:
                    target_slide = st.selectbox(
                        "Attach to",
                        list(range(1, max(1, slide_count) + 1)),
                        key=f"{state_id}-direct-slide-select",
                        label_visibility="collapsed",
                    )
            with col_btn:
                if st.button(
                    f"Attach to Slide {target_slide} directly ➜",
                    type="secondary",
                    width="stretch",
                    key=f"{state_id}-direct-attach-btn",
                ):
                    if handoff == "top5" and active_slide is not None:
                        image = _asset_to_image(working_bytes)
                        if image is None:
                            st.warning("This visual could not be decoded as an image.")
                        else:
                            buffer = BytesIO()
                            image.save(buffer, format="JPEG", quality=94, optimize=True)
                            selected_bytes = buffer.getvalue()
                            st.session_state.test_top5_visual_assignments[active_slide] = {
                                "asset_key": selected["asset_key"],
                                "result_key": "manual-subject",
                                "source": selected["source"],
                                "label": selected.get("label") or "Manual Subject",
                                "bytes": selected_bytes,
                            }
                            st.session_state.test_top5_visual_handoff = None
                            st.session_state.test_top5_rendered_video_path = None
                            st.toast(f"Attached image directly to Slide {active_slide}!", icon="📌")
                            st.rerun()
                    elif assignment_store is not None:
                        assignment_store[target_slide] = {
                            "asset_key": selected["asset_key"],
                            "result_key": "card-studio-photo",
                            "source": str(selected.get("source") or "Card Studio Photo"),
                            "label": str(selected.get("label") or "Direct Photo"),
                            "bytes": bytes(working_bytes),
                        }
                        if approval_state:
                            st.session_state[approval_state] = False
                            if approval_state == "visuals_approved":
                                st.session_state.approved_visuals = None
                        st.toast(f"Attached image directly to Slide {target_slide}!", icon="📌")
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    if headline_key not in st.session_state:
        st.session_state[headline_key] = default_headline
    headline = st.text_area(
        "Manual Subject Cutout headline",
        key=headline_key,
        height=82,
        label_visibility="collapsed",
    ).strip()

    state["mode"] = st.pills(
        "Composition",
        ["Negative Space", "Behind Subject"],
        default=state["mode"],
        key=f"{state_id}-mode",
        label_visibility="collapsed",
    ) or state["mode"]
    state["font"] = st.pills(
        "Font",
        list(MANUAL_SUBJECT_FONT_OPTIONS),
        default=state["font"],
        key=f"{state_id}-font",
        label_visibility="collapsed",
    ) or state["font"]
    state["style"] = st.pills(
        "Text style",
        list(MANUAL_SUBJECT_STYLE_OPTIONS),
        default=state["style"],
        key=f"{state_id}-style",
        label_visibility="collapsed",
    ) or state["style"]

    selected_mode = "behind-subject" if state["mode"] == "Behind Subject" else "negative-space"
    default_polygon = (
        (120, 700), (540, 700), (960, 700), (960, 950),
        (960, 1200), (540, 1200), (120, 1200), (120, 950),
    )
    polygon_points = state.get("polygon_points") or default_polygon
    try:
        polygon_points = [
            (max(0, min(1080, int(point[0]))), max(0, min(1920, int(point[1]))))
            for point in polygon_points
        ]
    except (TypeError, ValueError, IndexError):
        polygon_points = list(default_polygon)

    migrated_from_four_points = len(polygon_points) == 4
    if migrated_from_four_points:
        polygon_points = [
            polygon_points[0],
            ((polygon_points[0][0] + polygon_points[1][0]) // 2, (polygon_points[0][1] + polygon_points[1][1]) // 2),
            polygon_points[1],
            ((polygon_points[1][0] + polygon_points[2][0]) // 2, (polygon_points[1][1] + polygon_points[2][1]) // 2),
            polygon_points[2],
            ((polygon_points[2][0] + polygon_points[3][0]) // 2, (polygon_points[2][1] + polygon_points[3][1]) // 2),
            polygon_points[3],
            ((polygon_points[3][0] + polygon_points[0][0]) // 2, (polygon_points[3][1] + polygon_points[0][1]) // 2),
        ]
    if len(polygon_points) < 3:
        polygon_points = list(default_polygon)

    if state["editor_image_digest"] != source_digest or not state.get("editor_image_data"):
        source_image = _asset_to_image(working_bytes)
        if source_image is None:
            st.error("The selected image could not be opened.")
            return
        preview_image = source_image.resize((360, 640), Image.Resampling.LANCZOS)
        image_buffer = BytesIO()
        preview_image.save(image_buffer, format="JPEG", quality=82, optimize=True)
        state["editor_image_digest"] = source_digest
        state["editor_image_data"] = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    component_key = f"{state_id}-polygon-{selected['asset_key']}-{source_digest}"

    def sync_polygon_state():
        result = st.session_state.get(component_key)
        points = getattr(result, "points", None)
        if not points:
            return
        try:
            state["polygon_points"] = [
                (max(0, min(1080, int(point[0]))), max(0, min(1920, int(point[1]))))
                for point in points
            ]
        except (TypeError, ValueError, IndexError):
            return

    editor = None
    if MANUAL_SUBJECT_CUTOUT_POLYGON_EDITOR is not None:
        editor = MANUAL_SUBJECT_CUTOUT_POLYGON_EDITOR(
            data={"image": state["editor_image_data"], "points": polygon_points},
            default={"points": polygon_points},
            on_points_change=sync_polygon_state,
            key=component_key,
            width=360,
            height=640,
        )

    component_state = st.session_state.get(component_key)
    current_points = getattr(component_state, "points", None)
    if current_points is None and editor is not None:
        current_points = getattr(editor, "points", None)
    if current_points:
        try:
            normalized_points = [
                (max(0, min(1080, int(point[0]))), max(0, min(1920, int(point[1]))))
                for point in current_points
            ]
            if not (migrated_from_four_points and len(normalized_points) == 4):
                polygon_points = normalized_points
        except (TypeError, ValueError, IndexError):
            pass

    state["polygon_points"] = polygon_points

    st.session_state.setdefault(size_key, int(state["font_size"]))
    font_size = int(st.slider(
        "Text size",
        min_value=80,
        max_value=260,
        step=10,
        format="%d px",
        key=size_key,
    ))
    state["font_size"] = font_size

    layout_signature = hashlib.sha1(
        repr(
            (
                headline,
                selected_mode,
                state["font"],
                state["style"],
                font_size,
                tuple(polygon_points),
                bool(polygon_flow),
                source_digest,
            )
        ).encode("utf-8")
    ).hexdigest()

    current_layouts = (
        state.get("layout_options")
        if state.get("layout_signature") == layout_signature
        else None
    )
    selected_line_breaks = (
        tuple(state.get("line_breaks") or ())
        if current_layouts
        else None
    )

    if st.button(
        "Preview all valid line-break options",
        width="stretch",
        key=f"{state_id}-preview-line-breaks",
    ):
        try:
            with st.spinner("Rendering every valid line-break layout…"):
                current_layouts = build_manual_subject_cutout_layout_previews(
                    working_bytes,
                    headline,
                    mode=selected_mode,
                    font_size=font_size,
                    font=state["font"],
                    style=state["style"],
                    text_polygon=tuple(polygon_points),
                    polygon_flow=polygon_flow,
                )
            state["layout_options"] = current_layouts
            state["layout_signature"] = layout_signature
            state["line_breaks"] = tuple(current_layouts[0]["line_breaks"]) if current_layouts else None
            selected_line_breaks = tuple(state["line_breaks"] or ())
        except (ValueError, OSError, RuntimeError, ImportError) as exc:
            state["layout_options"] = None
            state["layout_signature"] = None
            state["line_breaks"] = None
            current_layouts = None
            st.error(str(exc))

    if current_layouts:
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">LINE-BREAK OPTIONS</div>'
            '<div class="section-title">Choose the exact text layout</div></div>'
            f'<div class="section-count">{len(current_layouts)} valid combinations</div></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Every option keeps the requested font size and uses the polygon as the actual end-to-end text space from left to right and top to bottom. "
            "More lines are created as needed to fill the space."
        )
        for start in range(0, len(current_layouts), 3):
            cols = st.columns(min(3, len(current_layouts) - start), gap="medium")
            for col, option in zip(cols, current_layouts[start:start + 3]):
                with col:
                    st.image(option["preview"], width=300)
                    st.markdown(
                        '<div class="visual-detail">'
                        + " / ".join(option["lines"])
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                    is_selected_layout = tuple(option["line_breaks"]) == tuple(state.get("line_breaks") or ())
                    if st.button(
                        "Selected" if is_selected_layout else "Use this layout",
                        type="primary" if is_selected_layout else "secondary",
                        width="stretch",
                        key=f"{state_id}-line-break-{option['index']}",
                    ):
                        state["line_breaks"] = tuple(option["line_breaks"])
                        selected_line_breaks = tuple(option["line_breaks"])
        state["layout_signature"] = layout_signature

    st.caption(
        "English only · Negative Space does not detect subjects · Behind Subject uses BiRefNet. "
        "Polygon is the full text field from one end to the other: text spans left to right and aligns top to bottom inside the polygon boundaries. "
        "Render Now replaces the rendered frame."
    )

    if selected_line_breaks:
        selected_lines = next(
            (
                option["lines"]
                for option in (current_layouts or [])
                if tuple(option["line_breaks"]) == selected_line_breaks
            ),
            (),
        )
        if selected_lines:
            st.caption("Selected layout: " + " / ".join(selected_lines))

    if st.button("Render Now", type="primary", width="stretch", key=f"{state_id}-cutout-render", help="Generate and render card frame"):
        if not headline:
            st.warning("Please enter a headline before rendering the card.")
        else:
            with st.spinner("Rendering Text Subject Cutout frame…"):
                try:
                    config = {
                        "headline": headline,
                        "mode": selected_mode,
                        "text_polygon": tuple(polygon_points),
                        "font_size": font_size,
                        "font": state["font"],
                        "style": state["style"],
                        "line_breaks": selected_line_breaks or None,
                        "polygon_flow": bool(polygon_flow),
                        "source_key": selected["asset_key"],
                        "source_digest": source_digest,
                    }
                    state["rendered_preview"] = build_manual_subject_cutout_preview(
                        working_bytes,
                        headline,
                        mode=selected_mode,
                        font_size=font_size,
                        font=state["font"],
                        style=state["style"],
                        text_polygon=config["text_polygon"],
                        line_breaks=config["line_breaks"],
                        polygon_flow=polygon_flow,
                    )
                    state["font_size"] = font_size
                    state["rendered_config"] = config
                    st.success("✅ Card frame generated! Preview updated below.")
                    st.toast("Card generated successfully!", icon="✨")
                except (ValueError, OSError, RuntimeError, ImportError) as exc:
                    state["rendered_preview"] = None
                    st.error(str(exc))

    if state.get("rendered_preview"):
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">RENDERED PREVIEW</div>'
            '<div class="section-title">Exact Manual Subject Cutout frame</div></div>'
            '<div class="section-count">1080 × 1920 · no overlays</div></div>',
            unsafe_allow_html=True,
        )
        st.image(state["rendered_preview"], width=360)

        if handoff == "cricket" and assignment_store is not None and slide_count > 0:
            slide = st.selectbox(
                "Add this to slide",
                list(range(1, slide_count + 1)),
                key=f"{state_id}-slide",
            )
            if st.button(
                "Add this to Slide →",
                type="primary",
                width="stretch",
                key=f"{state_id}-use",
            ):
                working_bytes = crop_store.get(selected["asset_key"]) or selected["bytes"]
                assignment_key = hashlib.sha1(
                    json.dumps(state["rendered_config"], sort_keys=True).encode("utf-8")
                ).hexdigest()[:12]
                assignment_store[slide] = {
                    "asset_key": f"text-cutout-{assignment_key}",
                    "result_key": "text-cutout",
                    "source": selected["source"],
                    "label": "Text Cutout",
                    "bytes": bytes(working_bytes),
                    "preview_bytes": bytes(state["rendered_preview"]),
                    "manual_subject_cutout": dict(state["rendered_config"]),
                }
                if approval_state:
                    st.session_state[approval_state] = False
                st.rerun()

        if handoff == "top5" and active_slide is not None:
            if st.button(
                f"Add this to Slide {active_slide} →",
                type="primary",
                width="stretch",
                key=f"{state_id}-use",
            ):
                working_bytes = crop_store.get(selected["asset_key"]) or selected["bytes"]
                image = _asset_to_image(working_bytes)
                if image is None:
                    st.warning("This visual could not be decoded as an image.")
                else:
                    buffer = BytesIO()
                    image.save(buffer, format="JPEG", quality=94, optimize=True)
                    selected_bytes = buffer.getvalue()
                    st.session_state.test_top5_visual_assignments[active_slide] = {
                        "asset_key": selected["asset_key"],
                        "result_key": "manual-subject",
                        "source": selected["source"],
                        "label": "Manual Subject Cutout",
                        "bytes": selected_bytes,
                        "preview_bytes": bytes(state["rendered_preview"]),
                        "manual_subject_cutout": dict(state["rendered_config"]),
                    }
                    st.session_state.test_top5_visual_handoff = None
                    st.session_state.test_top5_rendered_video_path = None
                    st.rerun()


def _visual_pool_entries(live: bool) -> list[tuple[str, int, dict, bytes, str]]:
    if live:
        specs = [
            ("live_visual_result", "auto", "Automatic Scraper"),
            ("live_manual_visual_result", "manual", "Manual Scraper"),
            ("live_real_image_result", "real", "Real Image Search"),
            ("live_ai_image_result", "ai", "AI Generation"),
        ]
        crop_store = st.session_state.get("live_visual_crops") or {}
        deleted = st.session_state.get("live_visual_deleted") or set()
    else:
        specs = [
            ("visual_result", "auto-crawler", "Automatic Scraper"),
            ("manual_visual_result", "manual-crawler", "Manual Scraper"),
            ("real_image_result", "real-search", "Real Image Search"),
            ("ai_image_result", "ai-generation", "AI Generation"),
        ]
        crop_store = st.session_state.get("visual_crops") or {}
        deleted = set()

    entries = []
    for state_key, result_key, source_name in specs:
        result = st.session_state.get(state_key) or {}
        for index, asset in enumerate(result.get("assets") or []):
            asset_key = (
                _visual_asset_key(f"live-{result_key}", index, asset)
                if live
                else _visual_asset_key(result_key, index, asset)
            )
            if asset_key in deleted:
                continue
            raw = crop_store.get(asset_key) or asset.get("bytes")
            if not isinstance(raw, (bytes, bytearray)) or not _is_valid_image_payload(bytes(raw)):
                continue
            entries.append((asset_key, index, asset, bytes(raw), source_name))
    return entries


def _render_card_studio(
    *,
    live: bool = False,
    slide_count: int = 0,
    top5: bool = False,
    active_slide: int | None = None,
    current_image=None,
    current_source: str = "Test image",
    polygon_flow: bool = True,
    active_mode: str = "",
    split_view: bool = False,
):
    from card_studio import (
        CardStudioError,
        LIVE_CARD_TYPES,
        TEST_CARD_TYPES,
        card_data_for_type,
        render_card,
    )

    card_types = LIVE_CARD_TYPES if live else TEST_CARD_TYPES
    state_id = (
        f"{'live' if live else 'test'}-"
        f"{'top5-' if top5 else ''}"
        f"{active_slide or 'standalone'}-card-studio"
    )
    card_type = st.pills(
        "Card type",
        list(card_types),
        default=st.session_state.get(f"{state_id}-type", card_types[0]),
        key=f"{state_id}-type",
    ) or card_types[0]

    if card_type == "Text Subject Cutout":
        if top5 and active_slide is None:
            image = _asset_to_image(current_image)
            if image is None:
                st.error("The current image could not be opened.")
                return
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=94, optimize=True)
            _render_manual_subject_cutout(
                state=st.session_state.test_top5_manual_subject_playground,
                assets=[{
                    "asset_key": f"top5-card-studio-{hashlib.sha1(buffer.getvalue()).hexdigest()[:12]}",
                    "bytes": buffer.getvalue(),
                    "source": current_source,
                    "label": "Current test image",
                }],
                crop_store={},
                crop_store_name="card-studio-top5",
                state_id=state_id,
                default_headline=st.session_state.get("test_top5_visual_playground_headline", ""),
                polygon_flow=polygon_flow,
            )
            return

        if top5 and active_slide is not None:
            result = st.session_state.test_top5_visual_results.get(active_slide) or {}
            image_assets = list(result.get("assets") or [])
            if not image_assets:
                st.info("Run one of Options 1–4 for this slide first. Card Studio reuses that image pool.")
                return
            manual_assets = [
                {
                    "asset_key": _visual_asset_key(f"card-studio-{active_slide}", index, asset),
                    "bytes": asset.get("bytes"),
                    "source": str(asset.get("publisher") or asset.get("source") or asset.get("model") or "Web source"),
                    "label": str(asset.get("article_title") or asset.get("title") or asset.get("model") or "Selected visual"),
                }
                for index, asset in enumerate(image_assets)
            ]
            slides = (st.session_state.get("test_top5_script_handoff") or {}).get("slides") or [{}]
            headline = str(slides[active_slide - 1].get("headline") or "") if active_slide <= len(slides) else ""
            _render_manual_subject_cutout(
                state=st.session_state.test_top5_manual_subject_cutouts.setdefault(active_slide, {}),
                assets=manual_assets,
                crop_store=st.session_state.test_top5_visual_crops,
                crop_store_name="test_top5_visual_crops",
                state_id=state_id,
                default_headline=headline,
                handoff="top5",
                active_slide=active_slide,
                polygon_flow=polygon_flow,
            )
            return

        entries = _visual_pool_entries(live)
        if not entries:
            if split_view:
                st.markdown(
                    '<div style="background:var(--card-bg, #ffffff);border:1px dashed var(--border, #e2e8f0);border-radius:12px;padding:28px 20px;text-align:center;margin:1rem 0;">'
                    '<div style="font-size:1.8rem;margin-bottom:8px;">🔍</div>'
                    '<div style="font-weight:700;font-size:0.95rem;color:var(--ink, #0f172a);letter-spacing:0.02em;">NO IMAGES FETCHED YET</div>'
                    '<div style="font-size:0.82rem;color:var(--muted, #64748b);margin:6px 0 0 0;line-height:1.4;">'
                    'Use <strong>Visual Fetcher</strong> on the right pane to search or scrape images. Once images appear, click <strong>"Select for Card Studio ➜"</strong> to start styling cards.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                return
            st.info("Run one of the existing visual sources first. Card Studio reuses that image pool.")
            return

        entries_by_key = {str(item[0]): item for item in entries}
        selected_key = str(st.session_state.get("card_studio_selected_asset_key") or "")

        if not active_mode.startswith("Option 5"):
            if selected_key in entries_by_key:
                target_entries = [entries_by_key[selected_key]]
            elif len(entries) == 1 and not split_view:
                target_entries = entries
                st.session_state["card_studio_selected_asset_key"] = entries[0][0]
            else:
                st.markdown(
                    '<div style="background:var(--card-bg, #ffffff);border:1px dashed var(--border, #e2e8f0);border-radius:12px;padding:28px 20px;text-align:center;margin:1rem 0;">'
                    '<div style="font-size:1.8rem;margin-bottom:8px;">👉</div>'
                    '<div style="font-weight:700;font-size:0.95rem;color:var(--ink, #0f172a);letter-spacing:0.02em;">AWAITING IMAGE SELECTION</div>'
                    '<div style="font-size:0.82rem;color:var(--muted, #64748b);margin:6px 0 16px 0;line-height:1.4;">'
                    'Select an image from the <strong>Visual Fetcher</strong> on the right pane (click <strong>"Select for Card Studio ➜"</strong>) to transfer it here and begin designing cards.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                if entries and st.button(
                    "Quick-transfer first fetched image ➜",
                    type="primary",
                    width="stretch",
                    key=f"{state_id}-quick-transfer",
                ):
                    first_key = entries[0][0]
                    st.session_state["card_studio_selected_asset_key"] = first_key
                    if live:
                        st.session_state.setdefault("live_manual_subject_cutout", {})["image_key"] = first_key
                        st.session_state["live-cricket-card-studio-image-1"] = first_key
                    else:
                        st.session_state.setdefault("manual_subject_cutout", {})["image_key"] = first_key
                        st.session_state["test-standalone-card-studio-image-1"] = first_key
                    st.rerun()
                return
        else:
            target_entries = entries

        script = (
            st.session_state.get("live_approved_script")
            if live
            else st.session_state.get("approved_script") or st.session_state.get("script_data")
        ) or {}
        _render_manual_subject_cutout(
            state=st.session_state.live_manual_subject_cutout if live else st.session_state.manual_subject_cutout,
            assets=[
                {
                    "asset_key": asset_key,
                    "bytes": image_bytes,
                    "source": source_name,
                    "label": str(asset.get("article_title") or asset.get("model") or source_name),
                }
                for asset_key, _index, asset, image_bytes, source_name in target_entries
            ],
            crop_store=(
                st.session_state.get("live_visual_crops") or {}
                if live
                else st.session_state.get("visual_crops") or {}
            ),
            crop_store_name="live_visual_crops" if live else "visual_crops",
            state_id=state_id,
            default_headline=str(script.get("headline") or ""),
            handoff="cricket",
            slide_count=slide_count,
            assignment_store=(
                st.session_state.live_visual_assignments
                if live
                else st.session_state.visual_assignments
            ),
            approval_state="live_visuals_approved" if live else "visuals_approved",
            polygon_flow=polygon_flow,
        )
        return

    defaults = card_data_for_type(card_type)

    if top5 and active_slide is None:
        image = _asset_to_image(current_image)
        if image is None:
            st.error("The current image could not be opened.")
            return
        raw = BytesIO()
        image.save(raw, format="JPEG", quality=94, optimize=True)
        asset_key = f"top5-card-studio-{hashlib.sha1(raw.getvalue()).hexdigest()[:12]}"
        crop_store_name = "test_top5_card_studio_crops"
        crop_store = st.session_state.setdefault(crop_store_name, {})
        assets = [{
            "asset_key": asset_key,
            "bytes": raw.getvalue(),
            "source": current_source,
            "label": "Current test image",
        }]
    elif top5:
        result = st.session_state.test_top5_visual_results.get(active_slide) or {}
        raw_assets = list(result.get("assets") or [])
        if not raw_assets:
            st.info("Run one of Options 1–4 for this slide first. Card Studio reuses that image pool.")
            return
        crop_store_name = "test_top5_visual_crops"
        crop_store = st.session_state.setdefault(crop_store_name, {})
        assets = [
            {
                "asset_key": _visual_asset_key(f"card-studio-{active_slide}", index, asset),
                "bytes": asset.get("bytes"),
                "source": str(asset.get("publisher") or asset.get("source") or asset.get("model") or "Web source"),
                "label": str(asset.get("article_title") or asset.get("title") or asset.get("model") or "Selected visual"),
            }
            for index, asset in enumerate(raw_assets)
        ]
    else:
        entries = _visual_pool_entries(live)
        if not entries:
            if split_view:
                st.markdown(
                    '<div style="background:var(--card-bg, #ffffff);border:1px dashed var(--border, #e2e8f0);border-radius:12px;padding:28px 20px;text-align:center;margin:1rem 0;">'
                    '<div style="font-size:1.8rem;margin-bottom:8px;">🔍</div>'
                    '<div style="font-weight:700;font-size:0.95rem;color:var(--ink, #0f172a);letter-spacing:0.02em;">NO IMAGES FETCHED YET</div>'
                    '<div style="font-size:0.82rem;color:var(--muted, #64748b);margin:6px 0 0 0;line-height:1.4;">'
                    'Use <strong>Visual Fetcher</strong> on the right pane to search or scrape images. Once images appear, click <strong>"Select for Card Studio ➜"</strong> to start styling cards.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                return
            st.info("Run one of the existing visual sources first. Card Studio reuses that image pool.")
            return

        entries_by_key = {str(item[0]): item for item in entries}
        selected_key = str(st.session_state.get("card_studio_selected_asset_key") or "")

        if not active_mode.startswith("Option 5"):
            if selected_key in entries_by_key:
                target_entries = [entries_by_key[selected_key]]
            elif len(entries) == 1 and not split_view:
                target_entries = entries
                st.session_state["card_studio_selected_asset_key"] = entries[0][0]
            else:
                st.markdown(
                    '<div style="background:var(--card-bg, #ffffff);border:1px dashed var(--border, #e2e8f0);border-radius:12px;padding:28px 20px;text-align:center;margin:1rem 0;">'
                    '<div style="font-size:1.8rem;margin-bottom:8px;">👉</div>'
                    '<div style="font-weight:700;font-size:0.95rem;color:var(--ink, #0f172a);letter-spacing:0.02em;">AWAITING IMAGE SELECTION</div>'
                    '<div style="font-size:0.82rem;color:var(--muted, #64748b);margin:6px 0 16px 0;line-height:1.4;">'
                    'Select an image from the <strong>Visual Fetcher</strong> on the right pane (click <strong>"Select for Card Studio ➜"</strong>) to transfer it here and begin designing cards.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                if entries and st.button(
                    "Quick-transfer first fetched image ➜",
                    type="primary",
                    width="stretch",
                    key=f"{state_id}-quick-transfer",
                ):
                    first_key = entries[0][0]
                    st.session_state["card_studio_selected_asset_key"] = first_key
                    if live:
                        st.session_state.setdefault("live_manual_subject_cutout", {})["image_key"] = first_key
                        st.session_state["live-cricket-card-studio-image-1"] = first_key
                    else:
                        st.session_state.setdefault("manual_subject_cutout", {})["image_key"] = first_key
                        st.session_state["test-standalone-card-studio-image-1"] = first_key
                    st.rerun()
                return
        else:
            target_entries = entries

        crop_store_name = "live_visual_crops" if live else "visual_crops"
        crop_store = st.session_state.setdefault(crop_store_name, {})
        assets = [
            {
                "asset_key": asset_key,
                "bytes": image_bytes,
                "source": source_name,
                "label": str(asset.get("article_title") or asset.get("title") or asset.get("model") or source_name),
            }
            for asset_key, _index, asset, image_bytes, source_name in target_entries
        ]

    if len(assets) == 1:
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TRANSFERRED IMAGE</div>'
            '<div class="section-title">Active Card Studio Image</div></div>'
            '<div class="section-count">1 image transferred · ready to design</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">IMAGE POOL</div>'
            '<div class="section-title">Choose the Card Studio image</div></div>'
            f'<div class="section-count">{len(assets)} images · crop before selection</div></div>',
            unsafe_allow_html=True,
        )

    primary_key = f"{state_id}-image-1"
    secondary_key = f"{state_id}-image-2"
    if len(assets) == 1 and not st.session_state.get(primary_key) and st.session_state.get("card_studio_selected_asset_key"):
        st.session_state[primary_key] = str(assets[0]["asset_key"])
    selected_primary = str(st.session_state.get(primary_key) or "")
    selected_secondary = str(st.session_state.get(secondary_key) or "")

    image_mode = "One image"
    split_direction = "Vertical"
    if card_type == "Head-to-Head":
        mode_key = f"{state_id}-image-mode"
        split_key = f"{state_id}-split-direction"
        st.session_state.setdefault(mode_key, defaults.get("image_mode", "One image"))
        st.session_state.setdefault(split_key, defaults.get("split_direction", "Vertical"))
        image_mode = st.radio(
            "Image mode",
            ["One image", "Two images"],
            horizontal=True,
            key=mode_key,
        )
        if image_mode == "Two images":
            split_direction = st.radio(
                "Split direction",
                ["Vertical", "Horizontal"],
                horizontal=True,
                key=split_key,
            )

    container_ctx = st.container(height=520) if len(assets) > 1 else st.container()
    with container_ctx:
        for start in range(0, len(assets), 4):
            cols = st.columns(min(4, len(assets) - start), gap="small")
            for col, asset in zip(cols, assets[start:start + 4]):
                with col:
                    key = asset["asset_key"]
                    cropped = crop_store.get(key)
                    preview_bytes = cropped if cropped else asset.get("bytes")
                    preview = _fit_visual_preview(preview_bytes, width=240, height=360)
                    if preview is not None:
                        st.image(preview, width="stretch")
                    st.markdown(
                        f'<div class="visual-source">{asset["source"]}</div>'
                        f'<div class="visual-detail">{asset["label"]}</div>',
                        unsafe_allow_html=True,
                    )
                    if cropped:
                        st.markdown(
                            '<div class="visual-crop-label">CROP APPLIED · USE CROPPED FRAME</div>',
                            unsafe_allow_html=True,
                        )

                    crop_col, action_col = st.columns(2, gap="small")
                    with crop_col:
                        if st.button(
                            "Crop / reposition",
                            width="stretch",
                            key=f"{state_id}-crop-{key}",
                        ):
                            raw = asset.get("bytes")
                            if isinstance(raw, (bytes, bytearray)):
                                _crop_visual_dialog(
                                    key,
                                    bytes(raw),
                                    str(asset["label"]),
                                    crop_store=crop_store_name,
                                    card_selector=True,
                                )
                            else:
                                st.warning("This visual is not crop-ready.")

                    with action_col:
                        if image_mode == "Two images" and card_type == "Head-to-Head":
                            if st.button(
                                "Use as Image 1",
                                width="stretch",
                                type="primary" if selected_primary == key else "secondary",
                                key=f"{state_id}-use-1-{key}",
                            ):
                                st.session_state[primary_key] = key
                            if st.button(
                                "Use as Image 2",
                                width="stretch",
                                type="primary" if selected_secondary == key else "secondary",
                                key=f"{state_id}-use-2-{key}",
                            ):
                                st.session_state[secondary_key] = key
                        else:
                            if st.button(
                                "Selected" if selected_primary == key else "Select image",
                                width="stretch",
                                type="primary" if selected_primary == key else "secondary",
                                key=f"{state_id}-use-{key}",
                            ):
                                st.session_state[primary_key] = key
                                selected_primary = key

    assets_by_key = {str(asset["asset_key"]): asset for asset in assets}
    if selected_primary not in assets_by_key:
        shared_selected = str(st.session_state.get("card_studio_selected_asset_key") or "")
        if shared_selected in assets_by_key:
            selected_primary = shared_selected
            st.session_state[primary_key] = shared_selected
        else:
            selected_primary = ""
            st.session_state[primary_key] = ""
    if selected_secondary not in assets_by_key:
        selected_secondary = ""
        st.session_state[secondary_key] = ""

    selected_primary_asset = assets_by_key.get(selected_primary)
    selected_secondary_asset = assets_by_key.get(selected_secondary)

    if card_type == "Head-to-Head" and image_mode == "Two images":
        if not selected_primary_asset or not selected_secondary_asset:
            st.info("Select an image for both sides before entering the card content.")
            return

    if not selected_primary_asset:
        st.info("Select an image before entering the card content.")
        return

    st.caption(
        (
            f'Image 1: {selected_primary_asset["label"]} · Image 2: {selected_secondary_asset["label"]}'
            if card_type == "Head-to-Head" and image_mode == "Two images"
            else f'Image: {selected_primary_asset["label"]}'
        )
    )

    direct_bytes = bytes(
        crop_store.get(selected_primary_asset["asset_key"])
        or selected_primary_asset.get("bytes")
        or b""
    )
    if direct_bytes and (slide_count > 0 or (top5 and active_slide is not None)):
        with st.container():
            st.markdown(
                '<div style="background:var(--surface-soft, rgba(255,255,255,0.03));border:1px solid var(--line, rgba(255,255,255,0.08));border-radius:8px;padding:8px 12px;margin:8px 0 14px 0;">'
                '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
                '<span style="font-size:0.75rem;font-weight:700;color:var(--ink-secondary, #94a3b8);letter-spacing:0.04em;">📌 DIRECT SLIDE ATTACHMENT</span>'
                '<span style="font-size:0.72rem;color:var(--text-muted, #64748b);">Attach this image directly to a slide without creating a card</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            col_target, col_btn = st.columns([1, 1.6], gap="small", vertical_alignment="center")
            with col_target:
                if top5 and active_slide is not None:
                    target_slide = active_slide
                    st.markdown(f'<div style="font-weight:700;font-size:0.85rem;color:var(--ink);">Target: Slide {active_slide}</div>', unsafe_allow_html=True)
                elif top5:
                    target_slide = st.selectbox("Attach to", list(range(1, 7)), key=f"{state_id}-direct-slide-select", label_visibility="collapsed")
                else:
                    target_slide = st.selectbox("Attach to", list(range(1, max(1, slide_count) + 1)), key=f"{state_id}-direct-slide-select", label_visibility="collapsed")
            with col_btn:
                if st.button(f"Attach to Slide {target_slide} directly ➜", type="secondary", width="stretch", key=f"{state_id}-direct-attach-btn"):
                    direct_assignment = {
                        "asset_key": selected_primary_asset["asset_key"],
                        "result_key": "card-studio-photo",
                        "source": str(selected_primary_asset.get("source") or "Card Studio Photo"),
                        "label": str(selected_primary_asset.get("label") or "Direct Photo"),
                        "bytes": direct_bytes,
                    }
                    if top5:
                        st.session_state.test_top5_visual_assignments[target_slide] = direct_assignment
                        st.session_state.test_top5_visual_handoff = None
                        st.session_state.test_top5_rendered_video_path = None
                    else:
                        target_assignments = st.session_state.live_visual_assignments if live else st.session_state.visual_assignments
                        target_assignments[target_slide] = direct_assignment
                        if live:
                            st.session_state.live_visuals_approved = False
                        else:
                            st.session_state.visuals_approved = False
                            st.session_state.approved_visuals = None
                    st.toast(f"Attached image directly to Slide {target_slide}!", icon="📌")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    def value_key(field):
        return f"{state_id}-{card_type.lower().replace(' ', '-').replace('/', '-').replace('&', 'and')}-{field}"

    if card_type == "Stat Highlight":
        st.markdown(
            '<div class="archetype-badge" style="background: rgba(15, 23, 42, 0.04); border-left: 3px solid #F4CA3D; padding: 10px 14px; border-radius: 4px; margin: 12px 0 16px 0;">'
            '<strong style="color: #0F172A; font-size: 0.9rem;">FEATURE STAT · PERFORMANCE STORY</strong><br>'
            '<span style="font-size: 0.86rem; color: #475569;">Photo-led editorial layout with an oversized record number, a concise headline and supporting figures in a clean ruled list. Text placement adapts around the detected subject when available.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        eyebrow_key = value_key("eyebrow")
        headline_key = value_key("headline")
        hero_value_key = value_key("value")
        unit_key = value_key("unit")
        for key, default in (
            (eyebrow_key, defaults["eyebrow"]),
            (headline_key, defaults["headline"]),
            (hero_value_key, defaults["value"]),
            (unit_key, defaults["unit"]),
        ):
            st.session_state.setdefault(key, default)
        col_top = st.columns(2)
        with col_top[0]:
            eyebrow_val = st.text_input("Eyebrow", key=eyebrow_key)
        with col_top[1]:
            headline_val = st.text_input("Headline", key=headline_key)
        col_hero = st.columns(2)
        with col_hero[0]:
            hero_val = st.text_input("Hero value", key=hero_value_key)
        with col_hero[1]:
            unit_val = st.text_input("Unit", key=unit_key)
        data = {
            "eyebrow": eyebrow_val,
            "headline": headline_val,
            "value": hero_val,
            "unit": unit_val,
            "metrics": [],
        }
        st.caption("Scorecard Shelf · Supporting Metrics (Up to 3)")
        for index, metric in enumerate(defaults["metrics"], 1):
            label_key = value_key(f"metric-{index}-label")
            metric_value_key = value_key(f"metric-{index}-value")
            st.session_state.setdefault(label_key, metric["label"])
            st.session_state.setdefault(metric_value_key, metric["value"])
            cols = st.columns(2)
            with cols[0]:
                label = st.text_input(f"Metric {index} label", key=label_key)
            with cols[1]:
                value = st.text_input(f"Metric {index} value", key=metric_value_key)
            data["metrics"].append({"label": label, "value": value})
    elif card_type == "Quote / Reaction":
        st.markdown(
            '<div class="archetype-badge" style="background: rgba(15, 23, 42, 0.04); border-left: 3px solid #F4CA3D; padding: 10px 14px; border-radius: 4px; margin: 12px 0 16px 0;">'
            '<strong style="color: #0F172A; font-size: 0.9rem;">THE PULL QUOTE · REACTION OR INTERVIEW</strong><br>'
            '<span style="font-size: 0.86rem; color: #475569;">A restrained magazine pull quote with clear attribution and context. The quote is positioned against the photo’s available negative space, with a subtle contrast fade only where text sits.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        eyebrow_key = value_key("eyebrow")
        quote_key = value_key("quote")
        attribution_key = value_key("attribution")
        context_key = value_key("context")
        for key, default in (
            (eyebrow_key, defaults["eyebrow"]),
            (quote_key, defaults["quote"]),
            (attribution_key, defaults["attribution"]),
            (context_key, defaults["context"]),
        ):
            st.session_state.setdefault(key, default)
        eyebrow_val = st.text_input("Eyebrow", key=eyebrow_key)
        quote_val = st.text_area("Quote", height=120, key=quote_key)
        col_attr = st.columns(2)
        with col_attr[0]:
            attr_val = st.text_input("Attribution", key=attribution_key)
        with col_attr[1]:
            context_val = st.text_input("Context", key=context_key)
        data = {
            "eyebrow": eyebrow_val,
            "quote": quote_val,
            "attribution": attr_val,
            "context": context_val,
        }
    elif card_type == "Head-to-Head":
        st.markdown(
            '<div class="archetype-badge" style="background: rgba(15, 23, 42, 0.04); border-left: 3px solid #F4CA3D; padding: 10px 14px; border-radius: 4px; margin: 12px 0 16px 0;">'
            '<strong style="color: #0F172A; font-size: 0.9rem;">THE COMPARISON · HEAD TO HEAD</strong><br>'
            '<span style="font-size: 0.86rem; color: #475569;">A clean comparison layout with matched names and values. Use one image or a two-image split; the comparison table keeps its hierarchy and stays inside the Shorts-safe area.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        eyebrow_key = value_key("eyebrow")
        headline_key = value_key("headline")
        left_name_key = value_key("left-name")
        right_name_key = value_key("right-name")
        for key, default in (
            (eyebrow_key, defaults["eyebrow"]),
            (headline_key, defaults["headline"]),
            (left_name_key, defaults["left"]["name"]),
            (right_name_key, defaults["right"]["name"]),
        ):
            st.session_state.setdefault(key, default)
        col_h2h_top = st.columns(2)
        with col_h2h_top[0]:
            eyebrow_val = st.text_input("Eyebrow", key=eyebrow_key)
        with col_h2h_top[1]:
            headline_val = st.text_input("Headline", key=headline_key)
        col_names = st.columns(2)
        with col_names[0]:
            left_name_val = st.text_input("Left name", key=left_name_key)
        with col_names[1]:
            right_name_val = st.text_input("Right name", key=right_name_key)
        data = {
            "eyebrow": eyebrow_val,
            "headline": headline_val,
            "left": {"name": left_name_val, "values": {}},
            "right": {"name": right_name_val, "values": {}},
            "metrics": [],
            "image_mode": image_mode,
            "split_direction": split_direction,
        }
        st.caption("Comparison Scorecard · Metric Duel Rows (Up to 3)")
        for index, metric in enumerate(defaults["metrics"], 1):
            label_key = value_key(f"metric-{index}-label")
            left_key = value_key(f"metric-{index}-left")
            right_key = value_key(f"metric-{index}-right")
            st.session_state.setdefault(label_key, metric)
            st.session_state.setdefault(left_key, defaults["left"]["values"].get(metric, ""))
            st.session_state.setdefault(right_key, defaults["right"]["values"].get(metric, ""))
            cols = st.columns(3)
            with cols[0]:
                label = st.text_input(f"Metric {index}", key=label_key)
            with cols[1]:
                left_value = st.text_input(f"Left {index}", key=left_key)
            with cols[2]:
                right_value = st.text_input(f"Right {index}", key=right_key)
            if label.strip():
                data["metrics"].append(label.strip())
                data["left"]["values"][label.strip()] = left_value.strip()
                data["right"]["values"][label.strip()] = right_value.strip()
    else:
        st.markdown(
            '<div class="archetype-badge" style="background: rgba(15, 23, 42, 0.04); border-left: 3px solid #F4CA3D; padding: 10px 14px; border-radius: 4px; margin: 12px 0 16px 0;">'
            '<strong style="color: #0F172A; font-size: 0.9rem;">THE RECORD · MILESTONE OR KEY FACT</strong><br>'
            '<span style="font-size: 0.86rem; color: #475569;">A record-led editorial layout with a large value, a clear achievement label and concise context. Its text position adapts to the subject and image composition when a subject mask is available.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        eyebrow_key = value_key("eyebrow")
        hero_value_key = value_key("value")
        label_key = value_key("label")
        context_key = value_key("context")
        for key, default in (
            (eyebrow_key, defaults["eyebrow"]),
            (hero_value_key, defaults["value"]),
            (label_key, defaults["label"]),
            (context_key, defaults["context"]),
        ):
            st.session_state.setdefault(key, default)
        col_m_top = st.columns(2)
        with col_m_top[0]:
            eyebrow_val = st.text_input("Eyebrow", key=eyebrow_key)
        with col_m_top[1]:
            hero_val = st.text_input("Value", key=hero_value_key)
        label_val = st.text_input("Label", key=label_key)
        context_val = st.text_area("Context", height=90, key=context_key)
        data = {
            "eyebrow": eyebrow_val,
            "value": hero_val,
            "label": label_val,
            "context": context_val,
        }

    result_key = f"{state_id}-result"
    if st.button("Render card", type="primary", width="stretch", key=f"{state_id}-render", help="Generate and render card"):
        with st.spinner("Rendering editorial card…"):
            try:
                from renderer import _top5_subject_mask

                first_bytes = bytes(
                    crop_store.get(selected_primary_asset["asset_key"])
                    or selected_primary_asset.get("bytes")
                    or b""
                )
                if not first_bytes:
                    raise CardStudioError("The selected image has no usable image bytes.")

                if card_type == "Head-to-Head" and image_mode == "Two images":
                    second_bytes = bytes(
                        crop_store.get(selected_secondary_asset["asset_key"])
                        or selected_secondary_asset.get("bytes")
                        or b""
                    )
                    if not second_bytes:
                        raise CardStudioError("The second selected image has no usable image bytes.")
                    source = (first_bytes, second_bytes)
                    try:
                        mask_1 = _top5_subject_mask(first_bytes)
                    except Exception:
                        mask_1 = None
                    try:
                        mask_2 = _top5_subject_mask(second_bytes)
                    except Exception:
                        mask_2 = None
                    subject_mask = (mask_1, mask_2)
                else:
                    source = first_bytes
                    try:
                        subject_mask = _top5_subject_mask(first_bytes)
                    except Exception:
                        subject_mask = None

                source_keys = [selected_primary_asset["asset_key"]]
                if card_type == "Head-to-Head" and image_mode == "Two images":
                    source_keys.append(selected_secondary_asset["asset_key"])

                st.session_state[result_key] = {
                    "bytes": render_card(
                        card_type,
                        source,
                        data,
                        subject_mask=subject_mask,
                    ),
                    "type": card_type,
                    "data": data,
                    "source": selected_primary_asset["source"],
                    "source_key": selected_primary_asset["asset_key"],
                    "source_keys": source_keys,
                }
            except (CardStudioError, OSError, RuntimeError) as exc:
                st.session_state[result_key] = {"error": str(exc)}

    result = st.session_state.get(result_key) or {}
    if result.get("error"):
        st.error(result["error"])
    if not result.get("bytes"):
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">CARD STUDIO</div>'
        '<div class="section-title">Rendered card · manual QC</div></div>'
        '<div class="section-count">1080 × 1920 · exact frame</div></div>',
        unsafe_allow_html=True,
    )
    col_card_prev, col_card_action = st.columns([1, 1], gap="medium")
    with col_card_prev:
        st.image(result["bytes"], width=300)

    with col_card_action:
        st.markdown(
            f'<div style="padding:10px 12px;background:var(--surface-soft);border-radius:10px;border:1px solid var(--line);margin-bottom:12px;">'
            f'<div class="eyebrow">ATTACH TO SLIDE</div>'
            f'<div style="font-weight:700;color:var(--ink);">{card_type}</div>'
            f'<div class="topic-meta">{selected_primary_asset.get("source", "Card Studio")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if top5 and active_slide is not None:
            slide = active_slide
        elif top5:
            slide = st.selectbox("Add card to slide", list(range(1, 7)), key=f"{state_id}-slide")
        else:
            slide = st.selectbox("Add card to slide", list(range(1, slide_count + 1)), key=f"{state_id}-slide")

        if st.button(
            f"Add to Slide {slide} →",
            type="primary",
            width="stretch",
            key=f"{state_id}-use",
        ):
            first_bytes = bytes(
                crop_store.get(selected_primary_asset["asset_key"])
                or selected_primary_asset.get("bytes")
                or b""
            )
            assignment = {
                "asset_key": f"card-studio-{slide}-{selected_primary_asset['asset_key']}",
                "result_key": "card-studio",
                "source": result.get("source") or "Card Studio",
                "label": f"Card Studio · {result.get('type') or 'Card'}",
                "bytes": first_bytes,
                "preview_bytes": bytes(result["bytes"]),
                "card_studio": {
                    "type": result.get("type"),
                    "data": dict(result.get("data") or {}),
                },
            }
            if top5:
                st.session_state.test_top5_visual_assignments[slide] = assignment
                st.session_state.test_top5_visual_handoff = None
                st.session_state.test_top5_rendered_video_path = None
            else:
                assignments = st.session_state.live_visual_assignments if live else st.session_state.visual_assignments
                assignments[slide] = assignment
                if live:
                    st.session_state.live_visuals_approved = False
                else:
                    st.session_state.visuals_approved = False
                    st.session_state.approved_visuals = None
            st.rerun()


def _top5_fit_preview(value, width=300, height=533):
    from PIL import Image
    image = _asset_to_image(value)
    if image is None:
        return None
    target_ratio = width / height
    current_ratio = image.width / image.height
    if current_ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif current_ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))
    return image.resize((width, height), Image.Resampling.LANCZOS)

def _render_home():
    factory_format = st.session_state.get("factory_format")
    if not factory_format:
        st.markdown(
            '<div class="home-hero">'
            '<div class="home-kicker">FINAL SHORTS</div>'
            '<div class="home-title">Choose your format.</div>'
            '<div class="home-copy">Select Shorts or Long-form, then choose Test or Live.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns(2, gap="medium")
        choices = (
            (left, "01", "SHORTS", "Short-form cricket and sports production.", "Open Shorts", "shorts"),
            (right, "02", "LONG-FORM", "Long-form cricket production. Test is currently WIP.", "Open Long-form", "long_form"),
        )
        for column, number, title, copy, button, value in choices:
            with column:
                with st.container(key=f"format-choice-{value}"):
                    st.markdown(
                        f'<div class="home-card-top"><span class="workspace-index">{number}</span>'
                        f'<span class="home-card-kind">FORMAT</span></div>'
                        f'<div class="workspace-name">{title}</div>'
                        f'<div class="workspace-desc">{copy}</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(button, key=f"choose-format-{value}", type="primary", width="stretch"):
                        st.session_state.factory_format = value
                        st.session_state.test_production_line = None
                        st.session_state.app_mode = "home"
                        st.rerun()
        return

    format_label = "Shorts" if factory_format == "shorts" else "Long-form"
    st.markdown(
        '<div class="home-hero">'
        f'<div class="home-kicker">FINAL SHORTS · {format_label.upper()}</div>'
        '<div class="home-title">Choose a workspace.</div>'
        '<div class="home-copy">Test builds and inspects. Live runs approved production.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="landing-test"):
            st.markdown(
                '<div class="home-card-top">'
                '<span class="workspace-index">01</span>'
                '<span class="home-card-kind">BUILD</span>'
                '</div>'
                '<div class="workspace-name">Test</div>'
                '<div class="workspace-desc">Build and inspect without touching production.</div>',
                unsafe_allow_html=True,
            )
            if factory_format == "long_form":
                st.markdown('<div><span class="badge">7 stages</span> <span class="badge">documentary lab</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div><span class="badge">7 stages</span> <span class="badge">manual</span></div>', unsafe_allow_html=True)
            if st.button("Open Test", key="open-test", type="primary", width="stretch"):
                st.session_state.app_mode = "test"
                st.rerun()
    with right:
        with st.container(key="landing-live"):
            st.markdown(
                '<div class="home-card-top">'
                '<span class="workspace-index">02</span>'
                '<span class="home-card-kind">SHIP</span>'
                '</div>'
                '<div class="workspace-name">Live</div>'
                '<div class="workspace-desc">Run the approved production flow.</div>',
                unsafe_allow_html=True,
            )
            if factory_format == "long_form":
                st.markdown('<div><span class="badge">production</span> <span class="badge">8-min documentary</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div><span class="badge">production</span> <span class="badge">public / private</span></div>', unsafe_allow_html=True)
            if st.button("Open Live", key="open-live", type="primary", width="stretch"):
                st.session_state.app_mode = "live"
                st.rerun()
    if st.button("Change format", key="change-factory-format", width="content"):
        st.session_state.factory_format = None
        st.session_state.test_production_line = None
        st.session_state.app_mode = "home"
        st.rerun()

def _render_pipeline_progress(
    labels: list[str],
    current_index: int,
    complete_last: bool = False,
):
    total = len(labels)
    if not total:
        return
    current_index = max(0, min(total - 1, current_index))
    completed = total if complete_last else current_index
    progress = completed / total

    st.markdown(
        '<div class="pipeline-wrap">'
        '<div class="pipeline-meta">'
        '<span class="pipeline-meta-label">PRODUCTION PROGRESS</span>'
        f'<span class="pipeline-meta-value">Step {current_index + 1} of {total} · {labels[current_index]}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.progress(progress)
    steps = ['<div class="pipeline-steps">']
    for index, label in enumerate(labels):
        if index < completed:
            state_class, state = "complete", "Done"
        elif index == current_index:
            state_class, state = "current", "Now"
        else:
            state_class, state = "", "Next"
        steps.append(
            f'<div class="pipeline-step {state_class}">'
            f'<div class="pipeline-step-number">0{index + 1}</div>'
            f'<div class="pipeline-step-label">{label}</div>'
            f'<div class="pipeline-step-state">{state}</div>'
            '</div>'
        )
    steps.append("</div></div>")
    st.markdown("".join(steps), unsafe_allow_html=True)


def _render_pipeline_notice(state_key: str):
    notice = st.session_state.get(state_key)
    if not isinstance(notice, dict):
        return
    st.markdown(
        '<div class="handoff-card">'
        '<div class="handoff-mark">✓</div>'
        '<div>'
        f'<div class="handoff-title">{notice.get("confirmed") or "QC confirmed"}</div>'
        f'<div class="handoff-copy">{notice.get("next") or "Ready for the next action."}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _render_app_sidebar():
    with st.container(key="workspace-nav"):
        col_brand, col_switch, col_nav = st.columns([1.3, 1, 0.8], gap="small", vertical_alignment="center")
        with col_brand:
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;">'
                '<div style="width:28px;height:28px;border-radius:8px;background:#0f172a;display:grid;place-items:center;color:#fff;font-weight:900;font-size:13px;letter-spacing:-0.05em;">FS</div>'
                '<div>'
                '<div class="nav-brand">FINAL SHORTS <span style="font-size:0.65rem;padding:2px 7px;border-radius:999px;background:#eef2ff;color:#4f46e5;font-weight:750;margin-left:4px;">PRO STUDIO</span></div>'
                '<div class="nav-sub">Autonomous Vertical Video Factory</div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with col_switch:
            current_workspace = "TEST" if st.session_state.app_mode == "test" else "LIVE"
            workspace = st.pills(
                "Workspace",
                ["TEST", "LIVE"],
                default=current_workspace,
                key="workspace-switcher",
                label_visibility="collapsed",
            ) or current_workspace
            target_mode = "test" if workspace == "TEST" else "live"
            if target_mode != st.session_state.app_mode:
                st.session_state.app_mode = target_mode
                st.rerun()
        with col_nav:
            btn_home, btn_back = st.columns([1, 1], gap="small")
            with btn_home:
                if st.button("Home", key="workspace-home", width="stretch"):
                    st.session_state.app_mode = "home"
                    st.rerun()
            with btn_back:
                if st.session_state.app_mode == "test" and st.session_state.test_production_line:
                    if st.button("Lines", key="test-back-to-lines", width="stretch"):
                        st.session_state.test_production_line = None
                        st.session_state.test_stage = "01 · Topic Fetcher"
                        st.session_state.test_pipeline_notice = None
                        st.rerun()
                elif st.session_state.app_mode == "live" and st.session_state.live_production_line:
                    if st.button("Lines", key="live-back-to-lines", width="stretch"):
                        _live_reset_downstream()
                        st.session_state.live_production_line = None
                        st.session_state.live_desk = None
                        st.session_state.live_cricket_profile = None
                        st.session_state.live_topics = []
                        st.session_state.live_topics_profile = None
                        st.session_state.live_stage = "01 · Story"
                        st.rerun()

        if st.session_state.get("factory_format") == "long_form":
            if st.session_state.app_mode == "test":
                st.markdown(
                    '<div class="nav-sub" style="margin-top:12px;">LONG-FORM · TEST</div>',
                    unsafe_allow_html=True,
                )
                selected = st.pills(
                    "Long-form stages",
                    ["01 · Topic Fetcher", "02 · Scriptwriter", "03 · Visuals", "04 · Audio", "05 · Subtitles", "06 · Renderer", "07 · Upload QC"],
                    default=st.session_state.longform_test_stage,
                    key="longform-test-stage-switcher",
                    label_visibility="collapsed",
                ) or st.session_state.longform_test_stage
                if selected != st.session_state.longform_test_stage:
                    st.session_state.longform_test_stage = selected
                    st.rerun()
            elif st.session_state.app_mode == "live":
                st.markdown(
                    '<div class="nav-sub" style="margin-top:12px;">LONG-FORM · LIVE PRODUCTION</div>',
                    unsafe_allow_html=True,
                )
                unlocked = _longform_live_get_unlocked_stages()
                selected = st.pills(
                    "Long-form Live stages",
                    unlocked,
                    default=st.session_state.longform_live_stage,
                    key="longform-live-stage-switcher",
                    label_visibility="collapsed",
                ) or st.session_state.longform_live_stage
                if selected != st.session_state.longform_live_stage:
                    st.session_state.longform_live_stage = selected
                    st.rerun()
        elif st.session_state.app_mode == "test" and st.session_state.test_production_line:
            line_name = {
                "deep_dive": "Deep-Dive Cricket",
                "top_5": "Top-5 Stories",
                "otd": "On This Day",
                "youtube_trends": "YouTube Trends",
            }.get(
                st.session_state.test_production_line,
                str(st.session_state.test_production_line).replace("_", " ").title(),
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin:12px 0 6px 0;">'
                f'<span class="eyebrow" style="color:var(--accent);font-size:0.65rem;">{line_name.upper()} · PRODUCTION PIPELINE</span>'
                f'<span style="font-size:0.68rem;color:var(--subtle);font-weight:650;">Direct Stage Navigation</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            labels = [stage["key"] for stage in STAGES]
            current = st.session_state.test_stage
            selected = st.pills(
                "Pipeline",
                labels,
                default=current,
                format_func=lambda value: f'{value.split(" · ")[0]}  {value.split(" · ")[-1]}',
                key="test-stage-switcher",
                label_visibility="collapsed",
            ) or current
            if selected != st.session_state.test_stage:
                st.session_state.test_stage = selected
                st.session_state.test_pipeline_notice = None


def _longform_live_reset_downstream():
    for key, value in {
        "longform_live_selected_topic": None,
        "longform_live_approved_topic": None,
        "longform_live_topic_error": "",
        "longform_live_script_data": None,
        "longform_live_approved_script": None,
        "longform_live_script_error": "",
        "longform_live_visuals_data": None,
        "longform_live_approved_visuals": None,
        "longform_live_visuals_error": "",
        "longform_live_audio_data": None,
        "longform_live_approved_audio": None,
        "longform_live_audio_error": "",
        "longform_live_subtitles_data": None,
        "longform_live_approved_subtitles": None,
        "longform_live_subtitles_error": "",
        "longform_live_rendered_video": None,
        "longform_live_approved_video": None,
        "longform_live_render_error": "",
        "longform_live_upload_result": None,
        "longform_live_upload_error": "",
    }.items():
        st.session_state[key] = value


def _longform_live_get_unlocked_stages() -> list[str]:
    stage_order = [
        "01 · Topic Fetcher",
        "02 · Scriptwriter",
        "03 · Visuals",
        "04 · Audio",
        "05 · Subtitles",
        "06 · Renderer",
        "07 · Upload QC",
    ]
    current_stage = st.session_state.get("longform_live_stage") or "01 · Topic Fetcher"
    curr_idx = stage_order.index(current_stage) if current_stage in stage_order else 0
    stages = set(stage_order[: curr_idx + 1])
    if st.session_state.get("longform_live_approved_topic"):
        stages.add("02 · Scriptwriter")
    if st.session_state.get("longform_live_approved_script"):
        stages.add("03 · Visuals")
    if st.session_state.get("longform_live_approved_visuals"):
        stages.add("04 · Audio")
    if st.session_state.get("longform_live_approved_audio"):
        stages.add("05 · Subtitles")
    if st.session_state.get("longform_live_approved_subtitles"):
        stages.add("06 · Renderer")
    if st.session_state.get("longform_live_approved_video"):
        stages.add("07 · Upload QC")
    return [s for s in stage_order if s in stages]


def _live_story_key(topic) -> str:
    return hashlib.sha1(
        f"{topic.title}|{topic.url}".encode("utf-8")
    ).hexdigest()[:12]


def _live_reset_downstream():
    for key, value in {
        "live_selected_topic": None,
        "live_pipeline_notice": None,
        "live_stage": "01 · Story",
        "live_topic_open_tile": None,
        "live_script_data": None,
        "live_approved_script": None,
        "live_script_error": "",
        "live_universal_angles": None,
        "live_universal_angle_source": None,
        "live_universal_angle_selected": 0,
        "live_universal_angle_custom": "",
        "live_universal_angle_story_key": None,
        "live_audio_data": None,
        "live_approved_audio": None,
        "live_subtitle_data": None,
        "live_handoff_error": "",
        "live_visual_result": None,
        "live_manual_visual_result": None,
        "live_real_image_result": None,
        "live_ai_image_result": None,
        "live_manual_subject_cutout": {},
        "live_visual_option": "Option 1 · Automatic Scraper",
        "live_visual_crops": {},
        "live_visual_deleted": set(),
        "live_visual_assignments": {},
        "live_visuals_approved": False,
        "live_rendered_video_path": None,
        "live_render_error": "",
        "live_upload_qc_approved": False,
        "live_upload_qc": None,
        "live_upload_result": None,
        "live_upload_titles": [],
        "live_upload_title_choice": 0,
        "live_upload_description": "",
        "live_upload_hashtags": "",
        "live_upload_comment": "",
        "live_headline_enabled": True,
        "live_top5_topics": [],
        "live_top5_selected": [],
        "live_top5_topic_open_tile": None,
        "live_top5_handoff": None,
        "live_top5_script_data": None,
        "live_top5_script_handoff": None,
        "live_top5_audio_data": None,
        "live_top5_audio_handoff": None,
        "live_top5_visual_results": {},
        "live_top5_manual_visual_results": {},
        "live_top5_real_image_results": {},
        "live_top5_ai_image_results": {},
        "live_top5_visual_handoff": None,
        "live_top5_visual_done": {},
        "live_top5_visual_futures": {},
        "live_top5_visual_active_slide": 1,
    }.items():
        st.session_state[key] = value


def _story_payload(topic) -> dict:
    return {
        "title": topic.title,
        "description": topic.description,
        "url": topic.url,
        "source": topic.source,
        "published_at": topic.published_at.isoformat(),
    }


def _script_for_topic(
    topic,
    profile: str,
    language: str,
    *,
    universal: bool = False,
    angle=None,
    research_source=None,
    search_query=None,
) -> dict:
    from script_writer import ScriptWriter

    desk_profile = profile or ("youtube_trends" if universal else "cricket_india_asia")
    return ScriptWriter.write(
        _story_payload(topic),
        profile=desk_profile,
        language=language,
        angle=angle,
        research_source=research_source,
        search_query=search_query,
    )


def _upload_metadata(script: dict) -> dict:
    return {
        "titles": list(script.get("titles") or []),
        "description": str(script.get("seo_description") or ""),
        "hashtags": " ".join(str(item) for item in (script.get("hashtags") or [])),
        "comment": str(script.get("comment") or ""),
    }


def _visual_story_for_topic(topic, script: dict | None = None) -> dict:
    story = _story_payload(topic)
    if isinstance(script, dict):
        scenes = script.get("script") or []
        first_scene = scenes[0] if scenes and isinstance(scenes[0], dict) else {}
        story["primary_entity"] = str(first_scene.get("primary_entity") or "").strip()
        story["specific_search_prompt"] = str(
            first_scene.get("specific_search_prompt") or ""
        ).strip()
        story["visual_intent"] = str(
            first_scene.get("visual_intent") or ""
        ).strip()
    return story


def _render_topic_tiles(
    topics,
    selected_index,
    *,
    columns: int,
    open_state_key: str,
    key_prefix: str,
):
    selection = None
    for start in range(0, len(topics), columns):
        row = st.columns(columns, gap="medium")
        for col, (index, tile) in zip(
            row,
            enumerate(topics[start:start + columns], start=start),
        ):
            members = tuple(sorted(
                tile.group_members or (tile,),
                key=lambda item: item.score,
                reverse=True,
            ))
            if tile.group_key.startswith("keyword:"):
                tile_tag = f"KEYWORD · {tile.group_key.split(':', 1)[1].upper()}"
            elif tile.group_key.startswith("player:"):
                tile_tag = f"PLAYER · {tile.group_key.split(':', 1)[1].upper()}"
            elif tile.group_key.startswith("otd:"):
                tile_tag = "HISTORICAL MILESTONE"
            else:
                tile_tag = "BREAKING DEVELOPMENTS"

            with col:
                primary_member = members[0]
                is_selected = (
                    selected_index == index
                    and (not topics[index].url or topics[index].url == primary_member.url)
                )
                card_class = "radar-topic-card selected-card" if is_selected else "radar-topic-card"
                with st.container(key=f"{key_prefix}topic-tile-{index}"):
                    source_name = primary_member.source or "Sports Wire"
                    pub_str = f"{primary_member.published_at:%d %b, %H:%M}"
                    extra_count = len(members) - 1
                    extra_badge = f'<span class="badge" style="font-size:0.6rem; padding:2px 7px; background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;">+{extra_count} sources</span>' if extra_count > 0 else ""

                    st.markdown(
                        f'<div class="{card_class}">'
                        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                        f'<span class="badge" style="font-size:0.65rem; font-weight:800; color:var(--accent); text-transform:uppercase;">{tile_tag}</span>'
                        f'<span style="font-size:0.65rem; color:var(--subtle); font-weight:600;">{pub_str}</span>'
                        f'</div>'
                        f'<div class="topic-title" style="margin:6px 0 10px; font-size:0.95rem; font-weight:800; line-height:1.35; color:var(--ink); min-height:3.6em;">{primary_member.title}</div>'
                        f'<div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--surface-soft); padding-top:8px;">'
                        f'<span style="font-size:0.7rem; font-weight:700; color:var(--muted);">{source_name}</span>'
                        f'{extra_badge}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    btn_label = "✓ Story Selected" if is_selected else "Produce Short →"
                    if st.button(
                        btn_label,
                        key=f"{key_prefix}topic-select-{index}-0",
                        width="stretch",
                        type="primary" if is_selected else "secondary",
                    ):
                        selection = (index, primary_member, members)

                    if len(members) > 1:
                        with st.expander(f"Inspect all {len(members)} coverage reports", expanded=False):
                            for headline_index, member in enumerate(members[1:], start=1):
                                member_selected = (
                                    selected_index == index
                                    and topics[index].url == member.url
                                )
                                st.markdown(f"**{member.title}**")
                                st.caption(f"{member.source or 'Wire'} · {member.published_at:%d %b, %H:%M}")
                                if st.button(
                                    "Selected" if member_selected else "Use this source",
                                    key=f"{key_prefix}topic-select-{index}-{headline_index}",
                                    width="stretch",
                                    type="primary" if member_selected else "secondary",
                                ):
                                    selection = (index, member, members)
    return selection


def _render_universal_angle_picker(
    angles: list[dict],
    *,
    selected_key: str,
    custom_key: str,
    button_prefix: str,
) -> str | None:
    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">VIRAL STORY LENS</div>'
        '<div class="section-title">Choose What This Short Is Actually About</div></div>'
        '<div class="section-count">3 Creator Archetypes + Custom Prompt</div></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The selected angle is authoritative. The scriptwriter builds the narration around this specific thesis rather than reading a scorecard."
    )

    selected_index = int(st.session_state.get(selected_key, 0) or 0)
    selected_index = max(0, min(selected_index, len(angles) - 1))
    custom_val = str(st.session_state.get(custom_key) or "").strip()

    angle_types = [
        ("⚡ HIGH-STAKES DEBATE", "angle-pill-debate", "#f59e0b"),
        ("📊 FREAK STAT & RECORD", "angle-pill-stat", "#38bdf8"),
        ("👁️ NARRATIVE INVERSION", "angle-pill-drama", "#c084fc"),
    ]

    cols = st.columns(3, gap="medium")
    for index, angle in enumerate(angles):
        with cols[index]:
            title = str(angle.get("title") or f"Angle 0{index + 1}")
            description = str(angle.get("description") or "")
            evidence = str(angle.get("evidence_basis") or "")
            is_active = (selected_index == index and not custom_val)
            badge_title, badge_class, accent_color = angle_types[index % len(angle_types)]
            active_class = "active-angle" if is_active else ""
            selected_badge = f'<span style="font-size:0.65rem; font-weight:800; color:#10b981; background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); padding:2px 8px; border-radius:999px;">✓ ACTIVE</span>' if is_active else ""

            st.markdown(
                f'<div class="angle-bento-card {active_class}">'
                f'<div>'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                f'<span class="{badge_class}">{badge_title}</span>'
                f'{selected_badge}'
                f'</div>'
                f'<div style="font-size:1rem; font-weight:800; color:var(--ink); line-height:1.25; margin-bottom:6px;">{title}</div>'
                f'<div style="font-size:0.78rem; color:var(--muted); line-height:1.4; margin-bottom:8px;">{description}</div>'
                f'</div>'
                f'<div style="font-size:0.68rem; color:var(--muted); border-top:1px solid var(--line); padding-top:8px;"><strong>Grounding:</strong> {evidence}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Selected" if is_active else "Choose Angle",
                type="primary" if is_active else "secondary",
                width="stretch",
                key=f"{button_prefix}-angle-{index}",
            ):
                st.session_state[selected_key] = index
                if custom_val:
                    st.session_state[custom_key] = ""
                st.rerun()

    # Creator Studio Prompt Terminal
    terminal_active = bool(custom_val)
    terminal_class = "active-terminal" if terminal_active else ""
    armed_badge = (
        '<span style="font-size:0.68rem; font-weight:800; color:var(--primary); background:var(--accent-soft); border:1px solid var(--line-strong); padding:2px 8px; border-radius:999px;">● ARMED (OVERRIDES CARDS)</span>'
        if terminal_active
        else ""
    )
    st.markdown(
        f'<div class="custom-prompt-terminal {terminal_class}">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">'
        f'<div style="font-size:0.75rem; font-weight:850; letter-spacing:0.1em; color:var(--primary); text-transform:uppercase;">✨ FREEFORM CREATOR PROMPT & MANUAL ANGLE</div>'
        f'{armed_badge}'
        f'</div>'
        f'<div style="font-size:0.78rem; color:var(--muted); line-height:1.4; margin-bottom:12px;">'
        f'Type any viral angle, controversy, or debate (e.g. <em>"Is a 33-ball duck better than a golden duck in Test cricket?"</em>). The AI will research facts to back up this lens and compose the Short around it.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    custom = st.text_area(
        "Custom angle prompt",
        value=str(st.session_state.get(custom_key) or ""),
        height=85,
        placeholder='e.g. "Is a 33-ball duck better than a golden duck in Test cricket? Debate tactical grit vs wasted balls."',
        key=custom_key,
        label_visibility="collapsed",
    ).strip()

    if custom:
        selected_text = custom
        col_c1, col_c2 = st.columns([0.8, 0.2])
        with col_c1:
            st.caption(f"⚡ Custom Lens Armed: '{custom}'")
        with col_c2:
            if st.button("Clear Custom", key=f"{button_prefix}-clear-custom"):
                st.session_state[custom_key] = ""
                st.rerun()
    else:
        angle = angles[selected_index]
        selected_text = (
            f'{str(angle.get("title") or "").strip()}: '
            f'{str(angle.get("description") or "").strip()}'
        ).strip(": ")

    if st.button(
        "⚡ Generate Viral Short from Selected Lens",
        type="primary",
        width="stretch",
        key=f"{button_prefix}-generate",
    ):
        return selected_text
    return None


def _render_visual_option_grid(
    options: tuple[str, ...],
    *,
    session_key: str,
    button_prefix: str,
) -> str:
    current = st.session_state.get(session_key)
    if current not in options:
        current = options[0]
        st.session_state[session_key] = current

    st.markdown(
        '<div style="display:flex;justify-content:space-between;margin:0.2rem 0 0.5rem 0;font-size:0.75rem;letter-spacing:0.05em;color:var(--text-muted, #888);">'
        '<span>STAGE 1: COLLECTION (SCRAPE & SEARCH)</span>'
        '<span>STAGE 2: BUILDER (CARDS & CUTOUT)</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    for start in range(0, len(options), 4):
        cols = st.columns(min(4, len(options) - start), gap="small")
        for col, option in zip(cols, options[start:start + 4]):
            with col:
                if st.button(
                    option,
                    type="primary" if option == current else "secondary",
                    width="stretch",
                    key=f"{button_prefix}-{options.index(option)}",
                ):
                    current = option
                    st.session_state[session_key] = option
    return current


def _live_start_story(index: int):
    _live_reset_downstream()
    st.session_state.live_selected_topic = index
    st.session_state.live_stage = "02 · Script"
    st.session_state.live_pipeline_notice = {
        "confirmed": "Story confirmed",
        "next": "Moving to Script.",
    }


def _live_generate_script(
    angle=None,
    research_source=None,
):
    selected_index = st.session_state.get("live_selected_topic")
    topics = st.session_state.get("live_topics") or []
    if selected_index is None or not 0 <= selected_index < len(topics):
        raise ValueError("No valid Live story is selected.")

    topic = topics[selected_index]
    script = _script_for_topic(
        topic,
        st.session_state.get("live_topics_profile") or "",
        st.session_state.get("live_script_language", "english"),
        universal=st.session_state.get("live_production_line") == "youtube_trends",
        angle=angle,
        research_source=research_source,
        search_query=(
            st.session_state.get("live_youtube_trend_search_query")
            if st.session_state.get("live_production_line") == "youtube_trends"
            else None
        ),
    )
    st.session_state.live_script_data = script
    st.session_state.live_script_error = ""
    metadata = _upload_metadata(script)
    st.session_state.live_upload_titles = metadata["titles"]
    st.session_state.live_upload_description = metadata["description"]
    st.session_state.live_upload_hashtags = metadata["hashtags"]
    st.session_state.live_upload_comment = metadata["comment"]
    st.session_state.live_manual_subject_cutout = {}
    return script


def _live_scrape_automatic_visuals():
    selected_index = st.session_state.get("live_selected_topic")
    topics = st.session_state.get("live_topics") or []
    script = st.session_state.get("live_script_data")
    if selected_index is None or not 0 <= selected_index < len(topics):
        raise ValueError("No valid Live story is selected.")
    if not isinstance(script, dict):
        raise ValueError("Generate the Live Scriptwriter result before scraping visuals.")

    story = _visual_story_for_topic(
        topics[selected_index],
        script,
    )
    from visual_fetcher import crawl_visuals

    st.session_state.live_visual_result = crawl_visuals(story)
    return st.session_state.live_visual_result


def _live_generate_audio_and_subtitles():
    approved_script = st.session_state.live_approved_script
    if not isinstance(approved_script, dict):
        return

    st.session_state.live_handoff_error = ""
    st.session_state.live_audio_data = None
    st.session_state.live_approved_audio = None
    st.session_state.live_subtitle_data = None

    from audio import approve_audio, generate_audio, resolve_chatterbox_reference
    from subtitles import generate_subtitles

    selected_engine = (
        "edge"
        if st.session_state.get("live_audio_engine_choice_v2") == "Edge-TTS Neural"
        else "chatterbox"
    )
    reference = (
        resolve_chatterbox_reference(st.session_state.get("live_audio_voice_reference"))
        if selected_engine == "chatterbox"
        else None
    )
    audio = generate_audio(
        approved_script,
        output_dir="output/live/audio",
        engine=selected_engine,
        reference=reference,
    )
    approved_audio = approve_audio(audio)
    subtitles = generate_subtitles(approved_script, approved_audio)

    st.session_state.live_audio_data = audio
    st.session_state.live_approved_audio = approved_audio
    st.session_state.live_subtitle_data = subtitles


@st.cache_data(max_entries=128, show_spinner=False)
def _fit_visual_preview_bytes(value: bytes, width: int, height: int) -> bytes | None:
    image = _asset_to_image(value)
    if image is None:
        return None

    target_ratio = width / height
    current_ratio = image.width / image.height
    if current_ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif current_ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    preview = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    preview.save(buffer, format="JPEG", quality=84, optimize=True)
    return buffer.getvalue()


def _fit_visual_preview(value, width=360, height=640):
    if isinstance(value, Image.Image):
        image = value.convert("RGB")
        target_ratio = width / height
        current_ratio = image.width / image.height
        if current_ratio > target_ratio:
            crop_width = max(1, int(image.height * target_ratio))
            left = (image.width - crop_width) // 2
            image = image.crop((left, 0, left + crop_width, image.height))
        elif current_ratio < target_ratio:
            crop_height = max(1, int(image.width / target_ratio))
            top = (image.height - crop_height) // 2
            image = image.crop((0, top, image.width, top + crop_height))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    if not isinstance(value, (bytes, bytearray)):
        return None
    return _fit_visual_preview_bytes(bytes(value), int(width), int(height))


def _delete_visual_asset(result_key: str, index: int, asset: dict, live: bool = False):
    asset_key = _visual_asset_key(
        f"live-{result_key}" if live else result_key,
        index,
        asset,
    )
    deleted_key = "live_visual_deleted" if live else "visual_deleted"
    assignments_key = "live_visual_assignments" if live else "visual_assignments"
    crops_key = "live_visual_crops" if live else "visual_crops"
    st.session_state[deleted_key].add(asset_key)
    for slide, assignment in list(st.session_state[assignments_key].items()):
        if assignment.get("asset_key") == asset_key:
            del st.session_state[assignments_key][slide]
    st.session_state[crops_key].pop(asset_key, None)
    if live:
        st.session_state.live_visuals_approved = False
    else:
        st.session_state.visuals_approved = False
        st.session_state.approved_visuals = None


def _attach_visual_asset(
    result_key: str,
    index: int,
    asset: dict,
    slide: int,
    live: bool = False,
):
    raw = asset.get("bytes")
    if not isinstance(raw, (bytes, bytearray)):
        st.warning("This visual has no usable image payload.")
        return

    asset_key = _visual_asset_key(
        f"live-{result_key}" if live else result_key,
        index,
        asset,
    )
    crops_key = "live_visual_crops" if live else "visual_crops"
    assignments_key = "live_visual_assignments" if live else "visual_assignments"
    cropped = st.session_state[crops_key].get(asset_key)
    selected_bytes = bytes(cropped) if cropped else bytes(raw)
    st.session_state[assignments_key][slide] = {
        "asset_key": asset_key,
        "result_key": result_key,
        "source": str(
            asset.get("publisher")
            or asset.get("source")
            or asset.get("model")
            or "Web source"
        ),
        "label": str(
            asset.get("article_title")
            or asset.get("model")
            or "Selected visual"
        ),
        "bytes": selected_bytes,
    }
    if live:
        st.session_state.live_visuals_approved = False
    else:
        st.session_state.visuals_approved = False
        st.session_state.approved_visuals = None


def _render_visual_asset_pool(
    assets: list[dict],
    result_key: str,
    slide_count: int,
    live: bool = False,
):
    prefix = "live-" if live else "test-"
    asset_result_key = f"live-{result_key}" if live else result_key
    crops_key = "live_visual_crops" if live else "visual_crops"
    deleted = st.session_state.get(
        "live_visual_deleted" if live else "visual_deleted"
    ) or set()

    visible_assets = [
        (index, asset)
        for index, asset in enumerate(assets)
        if _visual_asset_key(asset_result_key, index, asset) not in deleted
    ]
    if not visible_assets:
        st.caption("No images are currently available from this option.")
        return

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin:0.35rem 0 0.55rem 0;font-size:0.75rem;color:var(--muted);">'
        f'<span><strong>{len(visible_assets)} images in pool</strong> · scroll inside tray to browse</span>'
        f'<span>Attach to slide or delete unneeded assets</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.container(height=520):
        for start in range(0, len(visible_assets), 4):
            cols = st.columns(4, gap="small")
            for col, (index, asset) in zip(cols, visible_assets[start:start + 4]):
                with col:
                    asset_key = _visual_asset_key(asset_result_key, index, asset)
                    source = str(
                        asset.get("publisher")
                        or asset.get("source")
                        or asset.get("model")
                        or "Web source"
                    )
                    label = str(
                        asset.get("article_title")
                        or asset.get("model")
                        or "Selected visual"
                    )
                    with st.container(key=f"{prefix}visual-card-{result_key}-{index}"):
                        preview_bytes = st.session_state[crops_key].get(asset_key)
                        preview = _fit_visual_preview(
                            preview_bytes if preview_bytes else asset.get("bytes"),
                            width=240,
                            height=360,
                        )
                        if preview is not None:
                            st.image(preview, width="stretch")
                        st.markdown(
                            f'<div class="visual-source">{source}</div>',
                            unsafe_allow_html=True,
                        )
                        if label:
                            st.markdown(
                                f'<div class="visual-detail">{label}</div>',
                                unsafe_allow_html=True,
                            )
                        if preview_bytes:
                            st.markdown(
                                '<div class="visual-crop-label">CROP APPLIED</div>',
                                unsafe_allow_html=True,
                            )

                        is_studio_active = (
                            st.session_state.get("card_studio_selected_asset_key") == asset_key
                        )
                        if st.button(
                            "In Card Studio ✓" if is_studio_active else "Select for Card Studio ➜",
                            type="primary" if is_studio_active else "secondary",
                            width="stretch",
                            key=f"{prefix}use-card-studio-{asset_key}",
                        ):
                            st.session_state["card_studio_selected_asset_key"] = asset_key
                            if live:
                                st.session_state.setdefault("live_manual_subject_cutout", {})["image_key"] = asset_key
                                st.session_state["live-cricket-card-studio-image-1"] = asset_key
                            else:
                                st.session_state.setdefault("manual_subject_cutout", {})["image_key"] = asset_key
                                st.session_state["test-standalone-card-studio-image-1"] = asset_key
                            st.toast("Loaded image into Card Studio!", icon="🎨")
                            st.rerun()

                        choose_col, crop_col, delete_col = st.columns(3, gap="small")
                        with choose_col:
                            with st.popover("Choose for slide"):
                                selected_slide = st.selectbox(
                                    "Slide",
                                    list(range(1, slide_count + 1)),
                                    index=0,
                                    key=f"{prefix}attach-slide-{asset_key}",
                                )
                                if st.button(
                                    "Attach",
                                    type="primary",
                                    width="stretch",
                                    key=f"{prefix}attach-{asset_key}",
                                ):
                                    _attach_visual_asset(
                                        result_key,
                                        index,
                                        asset,
                                        selected_slide,
                                        live=live,
                                    )
                                    st.rerun()
                        with crop_col:
                            raw = asset.get("bytes")
                            if st.button(
                                "Crop",
                                width="stretch",
                                key=f"{prefix}crop-{asset_key}",
                            ):
                                if isinstance(raw, (bytes, bytearray)):
                                    _crop_visual_dialog(
                                        asset_key,
                                        bytes(raw),
                                        source,
                                        crop_store=crops_key,
                                    )
                                else:
                                    st.warning("This visual does not have a crop-ready payload.")
                        with delete_col:
                            if st.button(
                                "Delete",
                                width="stretch",
                                key=f"{prefix}delete-{asset_key}",
                            ):
                                _delete_visual_asset(
                                    result_key,
                                    index,
                                    asset,
                                    live=live,
                                )
                                st.rerun()


def _render_visual_board(slide_count: int, live: bool = False):
    prefix = "live_" if live else ""
    assignments = st.session_state.get(
        "live_visual_assignments" if live else "visual_assignments"
    ) or {}
    script = st.session_state.get(
        f"{prefix}approved_script"
        if live
        else "approved_script"
    )
    if not live and not isinstance(script, dict):
        script = st.session_state.get("script_data")
    scenes = script.get("script") if isinstance(script, dict) else []
    scenes = scenes if isinstance(scenes, list) else []

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">VISUAL BOARD</div>'
        '<div class="section-title">Attach one visual to every slide</div></div>'
        f'<div class="section-count">{slide_count} slides required</div></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(slide_count, gap="small")
    for slide in range(1, slide_count + 1):
        with cols[slide - 1]:
            assignment = assignments.get(slide)
            scene = scenes[slide - 1] if slide <= len(scenes) and isinstance(scenes[slide - 1], dict) else {}
            voiceover = str(scene.get("voiceover") or "").strip()
            body = str(scene.get("body") or "").strip() if not live else ""
            visual_headline = str(scene.get("headline") or "").strip() if not live else ""
            if voiceover or body or visual_headline:
                with st.container(key=f"{prefix}visual-slide-{slide}"):
                    st.markdown(
                        f'<div class="eyebrow">SLIDE {slide}</div>',
                        unsafe_allow_html=True,
                    )
                    if visual_headline:
                        st.markdown(
                            '<div class="mini-label" style="margin-top:.45rem;">HEADLINE</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**{visual_headline}**")
                    if voiceover:
                        st.markdown(
                            '<div class="mini-label" style="margin-top:.45rem;">SCRIPT</div>',
                            unsafe_allow_html=True,
                        )
                        st.text(voiceover)
                    if body:
                        st.markdown(
                            '<div class="mini-label" style="margin-top:.45rem;">VISUAL BODY</div>',
                            unsafe_allow_html=True,
                        )
                        st.text(body)

            preview_source = (
                assignment.get("preview_bytes")
                if assignment and assignment.get("preview_bytes")
                else assignment.get("bytes") if assignment else None
            )
            preview = (
                _fit_visual_preview(preview_source, 300, 533)
                if preview_source is not None
                else None
            )
            with st.container(key=f"{prefix}visual-slide-preview-{slide}"):
                if preview is not None:
                    st.image(preview, width="stretch")
                    st.caption(assignment.get("source") or "Attached visual")
                else:
                    st.markdown(
                        f'<div class="empty-slot">'
                        f'<div style="font-size:1.6rem;color:var(--line-strong);line-height:1;">⬚</div>'
                        f'<div>SLOT {slide} READY</div>'
                        f'<div style="font-size:0.6rem;color:var(--subtle);font-weight:600;margin-top:2px;">Select from pool below</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


def _render_two_pane_visual_workspace(
    active_mode: str,
    slide_count: int,
    live: bool = False,
    polygon_flow: bool = True,
):
    prefix = "live_" if live else "test_"
    pane_key = f"{prefix}visuals_pane_view"
    st.session_state.setdefault(pane_key, "⊞ Side-by-Side (Split)")

    st.markdown(
        '<div style="display:flex;align-items:center;justify-content:space-between;margin:0.75rem 0 0.45rem 0;">'
        '<div style="font-size:0.76rem;letter-spacing:0.06em;font-weight:700;color:var(--text-muted);text-transform:uppercase;">'
        'WORKPLACE LAYOUT · TWO-PANE EDITORIAL DESK'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    view_cols = st.columns([1.6, 0.45, 0.45, 0.45], gap="small")
    with view_cols[0]:
        st.markdown(
            '<div style="font-size:0.78rem;color:var(--text-muted);padding-top:6px;">'
            '👈 <strong>Left:</strong> Card Studio (Apply themes) &nbsp;|&nbsp; 👉 <strong>Right:</strong> Visual Fetcher (Fetch & Select)'
            '</div>',
            unsafe_allow_html=True,
        )
    with view_cols[1]:
        if st.button(
            "⊞ Split View",
            type="primary" if st.session_state[pane_key] == "⊞ Side-by-Side (Split)" else "secondary",
            width="stretch",
            key=f"{prefix}view-split-btn",
        ):
            st.session_state[pane_key] = "⊞ Side-by-Side (Split)"
            st.rerun()
    with view_cols[2]:
        if st.button(
            "◀ Focus Studio",
            type="primary" if st.session_state[pane_key] in {"◀ Card Studio Focus", "▶ Card Studio Focus"} else "secondary",
            width="stretch",
            key=f"{prefix}view-studio-btn",
        ):
            st.session_state[pane_key] = "◀ Card Studio Focus"
            st.rerun()
    with view_cols[3]:
        if st.button(
            "▶ Focus Fetcher",
            type="primary" if st.session_state[pane_key] in {"▶ Visual Fetcher Focus", "◀ Visual Fetcher Focus"} else "secondary",
            width="stretch",
            key=f"{prefix}view-fetcher-btn",
        ):
            st.session_state[pane_key] = "▶ Visual Fetcher Focus"
            st.rerun()

    current_view = st.session_state[pane_key]
    show_fetcher = current_view in {"⊞ Side-by-Side (Split)", "▶ Visual Fetcher Focus", "◀ Visual Fetcher Focus"}
    show_studio = current_view in {"⊞ Side-by-Side (Split)", "◀ Card Studio Focus", "▶ Card Studio Focus"}

    if active_mode.startswith("Option 5") and not show_studio:
        show_studio = True

    if show_fetcher and show_studio:
        col_studio, col_fetcher = st.columns([1, 1], gap="large")
    elif show_studio:
        col_studio = st.container()
        col_fetcher = None
    else:
        col_studio = None
        col_fetcher = st.container()

    if col_fetcher is not None:
        with col_fetcher:
            st.markdown(
                '<div class="section-head" style="margin-bottom:0.75rem;"><div>'
                '<div class="eyebrow">RIGHT PANE · VISUAL FETCHER</div>'
                '<div class="section-title">Image Acquisition Desk</div></div>'
                '<div class="section-count">4 Image Sources</div></div>',
                unsafe_allow_html=True,
            )
            fetcher_mode = active_mode if not active_mode.startswith("Option 5") else "Option 1 · Automatic Scraper"
            if live:
                if fetcher_mode.startswith("Option 1"):
                    result = st.session_state.get("live_visual_result") or {}
                    if result.get("error"):
                        st.error(result["error"])
                        if st.button(
                            "Retry automatic scrape",
                            type="primary",
                            width="stretch",
                            key="live-retry-auto-visuals",
                        ):
                            st.session_state.live_visual_result = None
                            st.rerun()
                    else:
                        asset_count = len(result.get("assets") or [])
                        threshold = int(result.get("success_threshold") or 10)
                        if asset_count < threshold:
                            st.warning(
                                f"Automatic scraper returned {asset_count} images. "
                                "You can retry it or use another visual source."
                            )
                            if st.button(
                                "Retry automatic scrape",
                                width="stretch",
                                key="live-retry-auto-visuals-underfilled",
                            ):
                                st.session_state.live_visual_result = None
                                st.rerun()
                        st.caption(
                            f'{len(result.get("assets") or [])} images · '
                            f'{int(result.get("pages_scraped") or 0)} pages'
                        )
                        _render_visual_asset_pool(
                            list(result.get("assets") or []),
                            "auto",
                            slide_count,
                            live=True,
                        )
                elif fetcher_mode.startswith("Option 2"):
                    st.caption("Manual query only. This searches publisher pages and scrapes their images.")
                    with st.form("live-manual-crawler-form"):
                        query = st.text_input(
                            "Manual query",
                            placeholder="e.g. Ben Stokes batting",
                            key="live-manual-crawler-query",
                        )
                        run = st.form_submit_button(
                            "Run manual scrape",
                            type="primary",
                            width="stretch",
                        )
                    if run:
                        query = query.strip()
                        if not query:
                            st.warning("Enter a query first.")
                        else:
                            with st.spinner("Searching and scraping publisher pages…"):
                                try:
                                    from visual_fetcher import manual_crawl_visuals
                                    st.session_state.live_manual_visual_result = manual_crawl_visuals(query)
                                except Exception as exc:
                                    st.session_state.live_manual_visual_result = {
                                        "error": f"{type(exc).__name__}: {exc}"
                                    }
                    result = st.session_state.get("live_manual_visual_result") or {}
                    if result.get("error"):
                        st.error(result["error"])
                    elif result:
                        st.caption(
                            f'{len(result.get("assets") or [])} images · '
                            f'{int(result.get("pages_scraped") or 0)} pages'
                        )
                        _render_visual_asset_pool(
                            list(result.get("assets") or []),
                            "manual",
                            slide_count,
                            live=True,
                        )
                elif fetcher_mode.startswith("Option 3"):
                    st.caption("Manual query only. Searches the configured real-image providers.")
                    with st.form("live-real-image-form"):
                        query = st.text_input(
                            "Manual query",
                            placeholder="e.g. Ben Stokes batting",
                            key="live-real-image-query",
                        )
                        run = st.form_submit_button(
                            "Search real images",
                            type="primary",
                            width="stretch",
                        )
                    if run:
                        query = query.strip()
                        if not query:
                            st.warning("Enter a query first.")
                        else:
                            with st.spinner("Searching real-image sources…"):
                                try:
                                    from visual_search import search_images
                                    st.session_state.live_real_image_result = search_images(query)
                                except Exception as exc:
                                    st.session_state.live_real_image_result = {
                                        "error": f"{type(exc).__name__}: {exc}"
                                    }
                    result = st.session_state.get("live_real_image_result") or {}
                    if result.get("error"):
                        st.error(result["error"])
                    elif result:
                        st.caption(f'{len(result.get("assets") or [])} images')
                        _render_visual_asset_pool(
                            list(result.get("assets") or []),
                            "real",
                            slide_count,
                            live=True,
                        )
                elif fetcher_mode.startswith("Option 4"):
                    providers_label = ["Pollinations.ai (Flux)"]
                    if os.getenv("HF_TOKEN"):
                        providers_label.append("Hugging Face")
                    if os.getenv("CLOUDFLARE_API_TOKEN") and os.getenv("CLOUDFLARE_ACCOUNT_ID"):
                        providers_label.append("Cloudflare Workers AI")
                    st.caption(f"Manual prompt only. Active AI providers: {', '.join(providers_label)}.")
                    with st.form("live-ai-image-form"):
                        query = st.text_input(
                            "Manual prompt",
                            placeholder="e.g. Ben Stokes hitting a six in a packed stadium",
                            key="live-ai-image-query",
                        )
                        run = st.form_submit_button(
                            "Generate images",
                            type="primary",
                            width="stretch",
                        )
                    if run:
                        query = query.strip()
                        if not query:
                            st.warning("Enter a prompt first.")
                        else:
                            with st.spinner("Generating images…"):
                                try:
                                    from visual_generator import generate_images
                                    st.session_state.live_ai_image_result = generate_images(query)
                                except Exception as exc:
                                    st.session_state.live_ai_image_result = {
                                        "error": f"{type(exc).__name__}: {exc}"
                                    }
                    result = st.session_state.get("live_ai_image_result") or {}
                    if result.get("error"):
                        st.error(result["error"])
                    elif result:
                        assets = list(result.get("assets") or [])
                        if not assets:
                            st.warning("No configured AI provider returned an image.")
                            last_query = query if run else str(result.get("query") or "").strip()
                            if last_query:
                                if st.button("Search Real Images for this query instead →", type="primary", key="live-ai-fallback-to-real-search"):
                                    with st.spinner(f"Searching real photography for '{last_query}'…"):
                                        try:
                                            from visual_search import search_images
                                            st.session_state.live_real_image_result = search_images(last_query)
                                            st.session_state.live_visual_mode = "Option 3 · Real Image Search"
                                            st.session_state.live_ai_image_result = None
                                            st.rerun()
                                        except Exception as exc:
                                            st.error(f"Search failed: {exc}")
                        else:
                            st.caption(f'{len(assets)} images')
                            _render_visual_asset_pool(
                                assets,
                                "ai",
                                slide_count,
                                live=True,
                            )
            else:
                if fetcher_mode.startswith("Option 1"):
                    render_visuals_crawler()
                elif fetcher_mode.startswith("Option 2"):
                    _render_manual_crawler()
                elif fetcher_mode.startswith("Option 3"):
                    _render_manual_real_images()
                elif fetcher_mode.startswith("Option 4"):
                    _render_manual_ai_images()

    if col_studio is not None:
        with col_studio:
            st.markdown(
                '<div class="section-head" style="margin-bottom:0.75rem;"><div>'
                '<div class="eyebrow">LEFT PANE · CARD STUDIO</div>'
                '<div class="section-title">Editorial Card Studio</div></div>'
                '<div class="section-count">5 Card Themes</div></div>',
                unsafe_allow_html=True,
            )
            _render_card_studio(
                live=live,
                slide_count=slide_count,
                polygon_flow=polygon_flow,
                active_mode=active_mode,
                split_view=show_fetcher,
            )


def _render_live_visuals(slide_count: int):
    if st.session_state.live_visuals_approved:
        st.success("Visuals approved and final render completed.")
        st.caption("Visual review is complete. The dashboard has moved this production to Upload.")
        return

    visual_options = (
        YT_TRENDS_VISUAL_OPTIONS
        if st.session_state.get("live_production_line") == "youtube_trends"
        else CRICKET_LIVE_VISUAL_OPTIONS
        if st.session_state.get("live_topics_profile") in {"cricket_india_asia", "cricket_global"}
        else VISUAL_OPTIONS
    )
    if st.session_state.get("live_visual_option") not in visual_options:
        st.session_state.live_visual_option = visual_options[0]
    visual_option = _render_visual_option_grid(
        visual_options,
        session_key="live_visual_option",
        button_prefix="live-visual-source",
    )

    _render_visual_board(slide_count, live=True)

    assigned = len(st.session_state.live_visual_assignments)
    st.caption(
        f"{assigned}/{slide_count} slides attached. "
        "Attached images remain in their original pools until you delete them."
    )

    ready = all(
        slide in st.session_state.live_visual_assignments
        for slide in range(1, slide_count + 1)
    )
    if ready and not st.session_state.live_visuals_approved:
        top_col1, top_col2 = st.columns([1.2, 0.8], gap="medium")
        with top_col1:
            st.markdown(
                f'<div style="padding:10px 14px;background:var(--success-soft);border:1px solid #86efac;border-radius:10px;font-size:0.85rem;font-weight:700;color:var(--success);">'
                f'✓ All {slide_count} slides attached! Ready for production render.</div>',
                unsafe_allow_html=True,
            )
        with top_col2:
            if st.button(
                "Approve visuals and render",
                type="primary",
                width="stretch",
                key="live-approve-visuals-top",
            ):
                assigned_items = [
                    st.session_state.live_visual_assignments[slide]
                    for slide in range(1, slide_count + 1)
                ]
                story = st.session_state.live_topics[
                    st.session_state.live_selected_topic
                ]
                story_id = _live_story_key(story)
                output = Path(__file__).resolve().parent / "output" / "live" / f"{story_id}.mp4"
                try:
                    with st.spinner("Rendering the final Short…"):
                        from renderer import render_production_video

                        render_production_video(
                            st.session_state.live_approved_script,
                            st.session_state.live_approved_audio,
                            st.session_state.live_subtitle_data,
                            assigned_items,
                            output_path=output,
                            headline_text=st.session_state.live_approved_script.get("headline", ""),
                            headline_enabled=bool(
                                st.session_state.live_approved_script.get("headline_overlay_enabled", False)
                            ),
                        )
                    st.session_state.live_rendered_video_path = str(output.resolve())
                    st.session_state.live_visuals_approved = True
                    st.session_state.live_render_error = ""
                    st.session_state.live_stage = "05 · Upload"
                    st.session_state.live_pipeline_notice = {
                        "confirmed": "Visuals QC and render confirmed",
                        "next": "Moving to Upload.",
                    }
                    st.rerun()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.session_state.live_render_error = str(exc)

    _render_two_pane_visual_workspace(visual_option, slide_count, live=True, polygon_flow=True)

    ready = all(
        slide in st.session_state.live_visual_assignments
        for slide in range(1, slide_count + 1)
    )
    if ready:
        if not st.session_state.live_visuals_approved:
            if st.button(
                "Retry render" if st.session_state.live_render_error else "Approve visuals and render",
                type="primary",
                width="stretch",
                key="live-approve-visuals",
            ):
                assigned = [
                    st.session_state.live_visual_assignments[slide]
                    for slide in range(1, slide_count + 1)
                ]
                story = st.session_state.live_topics[
                    st.session_state.live_selected_topic
                ]
                story_id = _live_story_key(story)
                output = Path(__file__).resolve().parent / "output" / "live" / f"{story_id}.mp4"
                try:
                    with st.spinner("Rendering the final Short…"):
                        from renderer import render_production_video

                        render_production_video(
                            st.session_state.live_approved_script,
                            st.session_state.live_approved_audio,
                            st.session_state.live_subtitle_data,
                            assigned,
                            output_path=output,
                            headline_text=st.session_state.live_approved_script.get("headline", ""),
                            headline_enabled=bool(
                                st.session_state.live_approved_script.get(
                                    "headline_enabled",
                                    st.session_state.live_headline_enabled,
                                )
                            ),
                            source_label=story.source or "SPORTS DESK",
                        )
                    st.session_state.live_rendered_video_path = str(output.resolve())
                    st.session_state.live_visuals_approved = True
                    st.session_state.live_render_error = ""
                    st.session_state.live_stage = "05 · Upload"
                    st.session_state.live_pipeline_notice = {
                        "confirmed": "Visual QC confirmed",
                        "next": "Moving to Upload.",
                    }
                    st.rerun()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.session_state.live_render_error = str(exc)
        else:
            st.success("Visuals approved and final render completed.")
    else:
        st.info("Attach every slide before Visuals can be approved.")

    if st.session_state.live_render_error:
        st.error(st.session_state.live_render_error)


def _render_packaging_deck_and_phone(
    script: dict,
    story_title: str,
    current_headline: str,
    current_vo1: str,
    headline_enabled: bool = True,
):
    headline_display = current_headline.strip() if headline_enabled and current_headline.strip() else ""
    vo_display = current_vo1.strip()[:140] if current_vo1 else ""

    st.markdown('<div class="mini-label" style="margin-top:16px; margin-bottom:8px;">9:16 IN-FEED PHONE SIMULATOR</div>', unsafe_allow_html=True)
    headline_html = f'<div class="phone-sim-headline">{headline_display}</div>' if headline_display else ""
    st.markdown(
        f'<div class="phone-sim-wrapper">'
        f'<div class="phone-sim-frame">'
        f'<div class="phone-sim-notch"></div>'
        f'<div>'
        f'<div class="phone-billboard-badge">🔴 SHORTS FEED PREVIEW</div>'
        f'{headline_html}'
        f'</div>'
        f'<div class="phone-sim-preview-video">'
        f'<div class="phone-sim-ui-overlay">'
        f'<div class="phone-sim-action-btn">❤️</div>'
        f'<div class="phone-sim-action-btn">💬</div>'
        f'<div class="phone-sim-action-btn">↗️</div>'
        f'</div>'
        f'<div class="phone-sim-hook-text">'
        f'<span style="color:#facc15; font-weight:800; font-size:0.65rem;">HOOK:</span> {vo_display}'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    titles = script.get("titles") or []
    if titles:
        st.markdown('<div class="mini-label" style="margin-top:16px; margin-bottom:8px;">VIRAL PACKAGING SUITE (3 ARCHETYPES)</div>', unsafe_allow_html=True)
        title_meta = [
            ("🔍 SEARCH / SEO INTENT", "#0369a1", "Captures YouTube Search & Explore algorithm"),
            ("⚡ HIGH-STAKES DEBATE", "#92400e", "Drives hundreds of comments arguing in thread"),
            ("👁️ CURIOSITY GAP", "#6d28d9", "Irresistible open loop that boosts watch time"),
        ]
        for t_idx, title_cand in enumerate(titles[:3]):
            tag, color, desc = title_meta[t_idx % len(title_meta)]
            st.markdown(
                f'<div class="packaging-tile">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<span class="packaging-tile-type" style="color:{color};">{tag}</span>'
                f'<span style="font-size:0.62rem; color:#64748b;">Option 0{t_idx+1}</span>'
                f'</div>'
                f'<div class="packaging-tile-text">{title_cand}</div>'
                f'<div style="font-size:0.68rem; color:#64748b; margin-top:4px;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    comment = script.get("comment") or ""
    if comment:
        st.markdown(
            f'<div class="comment-bait-container">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
            f'<span style="font-size:0.65rem; font-weight:850; letter-spacing:0.08em; color:var(--primary); text-transform:uppercase;">💬 PINNED COMMENT DEBATE BAIT</span>'
            f'<span style="font-size:0.6rem; color:#10b981; font-weight:800;">ALGORITHM DRIVER</span>'
            f'</div>'
            f'<div style="font-size:0.82rem; color:var(--ink); font-weight:600; line-height:1.35;">{comment}</div>'
            f'<div style="font-size:0.65rem; color:var(--muted); margin-top:4px;">Pins automatically as the 1st comment to trigger viewer arguments.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_live_script():
    script = st.session_state.get("live_script_data")
    story = st.session_state.live_topics[st.session_state.live_selected_topic]
    story_id = _live_story_key(story)
    universal_story = (
        st.session_state.get("live_production_line") == "youtube_trends"
        or st.session_state.get("live_topics_profile") == "niche_sports"
    )

    if not isinstance(script, dict):
        angles = st.session_state.get("live_universal_angles")
        if not angles:
            if st.button(
                "Retry angle discovery" if st.session_state.get("live_script_error") else "Generate Script",
                type="primary",
                width="stretch",
                key="live-generate-script",
            ):
                st.session_state.live_script_error = ""
                try:
                    with st.spinner("Reading the full story and finding the strongest angles…"):
                        if universal_story:
                            from script_writer import suggest_universal_story_angles
                            result = suggest_universal_story_angles(
                                _story_payload(story),
                                language=st.session_state.get("live_script_language", "english"),
                                search_query=st.session_state.get("live_youtube_trend_search_query"),
                            )
                        else:
                            from script_writer import suggest_cricket_story_angles
                            result = suggest_cricket_story_angles(
                                _story_payload(story),
                                language=st.session_state.get("live_script_language", "english"),
                            )
                    st.session_state.live_universal_angles = result["angles"]
                    st.session_state.live_universal_angle_source = result["source_evidence"]
                    st.session_state.live_universal_angle_selected = 0
                    st.session_state.live_universal_angle_custom = ""
                except Exception as exc:
                    st.session_state.live_script_error = f"{type(exc).__name__}: {exc}"
                st.rerun()
            if st.session_state.get("live_script_error"):
                st.error("Scriptwriter failed: " + st.session_state.live_script_error)
            else:
                st.info("Press Generate Script to identify three evidence-backed story angles.")
            return

        selected_angle = _render_universal_angle_picker(
            angles,
            selected_key="live_universal_angle_selected",
            custom_key="live_universal_angle_custom",
            button_prefix=f"live-{story_id}",
        )
        if selected_angle:
            st.session_state.live_script_error = ""
            try:
                with st.spinner("Writing the Short from the selected angle…"):
                    _live_generate_script(
                        angle=selected_angle,
                        research_source=st.session_state.live_universal_angle_source,
                    )
            except Exception as exc:
                st.session_state.live_script_error = f"{type(exc).__name__}: {exc}"
            else:
                st.rerun()
        if not isinstance(st.session_state.get("live_script_data"), dict):
            if st.session_state.get("live_script_error"):
                st.error("Scriptwriter failed: " + st.session_state.live_script_error)
            return
        script = st.session_state.live_script_data

    if st.session_state.get("live_script_error"):
        st.error(
            "Script approval failed: "
            + st.session_state.live_script_error
        )
        st.caption("Correct the highlighted edit and approve the script again.")

    story = st.session_state.live_topics[st.session_state.live_selected_topic]
    story_id = _live_story_key(story)
    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">SCRIPT QC</div>'
        '<div class="section-title">Edit once, approve once</div></div>'
        '<div class="section-count">no second script QC</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Manual QC is the final editorial decision. The opening headline is optional; leaving it empty is accepted."
    )
    if str(script.get("story_angle") or "").strip():
        st.caption("Selected story angle: " + str(script.get("story_angle") or "").strip())
        if st.button(
            "Change angle and regenerate",
            width="stretch",
            key=f"live-change-angle-{story_id}",
        ):
            st.session_state.live_script_data = None
            st.session_state.live_approved_script = None
            st.session_state.live_script_error = ""
            st.session_state.live_audio_data = None
            st.session_state.live_approved_audio = None
            st.session_state.live_subtitle_data = None
            st.session_state.live_handoff_error = ""
            st.session_state.live_visual_result = None
            st.session_state.live_manual_visual_result = None
            st.session_state.live_real_image_result = None
            st.session_state.live_ai_image_result = None
            st.session_state.live_visual_assignments = {}
            st.session_state.live_visuals_approved = False
            st.session_state.live_rendered_video_path = None
            st.session_state.live_render_error = ""
            st.session_state.live_stage = "02 · Script"
            st.rerun()

    col_left, col_right = st.columns([1.5, .55], gap="large")
    with col_left:
        delivery_p = str(script.get("delivery_profile") or "Live Broadcast Short")
        flow = script.get("flow_metrics") or {}
        flow_score = flow.get("flow_score") or 9.0

        current_vo1 = st.session_state.get(f"live-script-scene-{story_id}-1", script.get("script", [{}])[0].get("voiceover", ""))
        s1_words_live = len(str(current_vo1).split()) if current_vo1 else 0

        total_words_live = sum(
            len(str(st.session_state.get(f"live-script-scene-{story_id}-{idx}", sc.get("voiceover", ""))).split())
            for idx, sc in enumerate(script.get("script", []), 1)
        )
        est_seconds_live = round(total_words_live / 2.5, 1) if total_words_live else 0.0

        st.markdown(
            f'<div class="prompter-flow-bar">'
            f'<div>'
            f'<span class="badge" style="background:var(--surface-soft); color:var(--ink-secondary); border:1px solid var(--line); margin-right:8px;">{delivery_p}</span>'
            f'<span style="font-size:0.8rem; font-weight:800; letter-spacing:0.02em;">⚡ Broadcast Flow: {flow_score}/10</span>'
            f'</div>'
            f'<div style="font-size:0.75rem; font-weight:750; color:var(--muted);">'
            f'{total_words_live} words · ~{est_seconds_live}s runtime (Lead: {s1_words_live}w)'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.session_state.live_headline_enabled = st.toggle(
            "Use opening headline",
            value=st.session_state.get("live_headline_enabled", True),
            key=f"live-headline-enabled-{story_id}",
        )

        edited_headline = st.text_input(
            "Opening headline",
            value=str(script.get("headline") or "") if st.session_state.live_headline_enabled else "",
            max_chars=100,
            key=f"live-script-headline-{story_id}",
            disabled=not st.session_state.live_headline_enabled,
        )

        scene_roles = {
            1: "THE LEAD HOOK (<14w)",
            2: "THE TURN / CAUSE",
            3: "STAKES & EVIDENCE",
            4: "THE KICKER / IMPACT",
            5: "OUTLOOK / STATUS",
            6: "CLOSING",
        }
        edited_voiceovers = []
        for index, scene in enumerate(script.get("script") or [], 1):
            raw_text = scene.get("voiceover", "")
            cur_text = st.session_state.get(f"live-script-scene-{story_id}-{index}", raw_text)
            word_count = len(str(cur_text).split()) if cur_text else 0
            est_seconds = round(word_count / 2.5, 1) if word_count else 0.0
            role = scene.get("narrative_role") or scene_roles.get(index, f"SCENE {index}")

            if index == 1:
                if word_count <= 13:
                    meter_badge = f'<span class="hook-meter-ok">✓ LEAD HOOK: {word_count}w (&lt;14w target)</span>'
                elif word_count == 14:
                    meter_badge = f'<span class="hook-meter-warn">⚠️ LEAD HOOK: 14w (At threshold)</span>'
                else:
                    meter_badge = f'<span class="hook-meter-bad">⛔ LEAD HOOK: {word_count}w (Shorten for retention)</span>'
            else:
                meter_badge = f'<span style="font-size:0.72rem; font-weight:700; color:var(--muted); background:var(--surface-soft); padding:3px 8px; border-radius:6px; border:1px solid var(--line);">{word_count} words · ~{est_seconds}s</span>'

            st.markdown(
                f'<div class="cue-card-header">'
                f'<span class="cue-role-title">CUE {index} · {role}</span>'
                f'{meter_badge}'
                f'</div>',
                unsafe_allow_html=True,
            )
            edited_voiceovers.append(
                st.text_area(
                    f"Slide {index} narration",
                    value=str(scene.get("voiceover") or ""),
                    height=105,
                    key=f"live-script-scene-{story_id}-{index}",
                    label_visibility="collapsed",
                )
            )

        if st.button(
            "Approve script and hand to Audio",
            type="primary",
            width="stretch",
            key="live-approve-script",
        ):
            try:
                from script_writer import ScriptWriter
                desk_p = st.session_state.get("live_topics_profile") or ("youtube_trends" if st.session_state.get("live_production_line") == "youtube_trends" else "cricket_india_asia")
                approved = ScriptWriter.apply_edits(
                    script,
                    edited_voiceovers,
                    headline=edited_headline if st.session_state.live_headline_enabled else "",
                    profile=desk_p,
                )
                approved["headline_enabled"] = bool(st.session_state.live_headline_enabled)
            except ValueError as exc:
                st.session_state.live_script_error = str(exc)
                st.rerun()
            st.session_state.live_approved_script = approved
            st.session_state.live_script_error = ""
            st.session_state.live_handoff_error = ""
            st.session_state.live_stage = "03 · Audio + Subs"
            st.session_state.live_pipeline_notice = {
                "confirmed": "Script QC confirmed",
                "next": "Moving to Audio + Subtitles.",
            }
            st.rerun()

    with col_right:
        st.markdown('<div class="inspector">', unsafe_allow_html=True)
        st.markdown('<div class="mini-label">LIVE TELEPROMPTER</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-weight:800;line-height:1.35;margin:.25rem 0 .75rem; color:var(--ink);">{story.title}</div>', unsafe_allow_html=True)
        scenes_count = len(script.get("script") or [])
        st.markdown(f'<div class="inspector-line"><span>Cues</span><span class="inspector-value">{scenes_count} scenes</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="inspector-line"><span>Total Speech</span><span class="inspector-value">{total_words_live} words</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="inspector-line"><span>Est. Runtime</span><span class="inspector-value">~{est_seconds_live}s</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Cadence Target</span><span class="inspector-value">~150 WPM</span></div>', unsafe_allow_html=True)
        if st.session_state.live_approved_script:
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);border:1px solid #86efac;">✓ Script Approved</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="teleprompter-article-view">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.65rem; font-weight:800; letter-spacing:0.1em; color:var(--primary); text-transform:uppercase; margin-bottom:8px;">CONTINUOUS SPOKEN BROADCAST ARTICLE</div>', unsafe_allow_html=True)
        article_parts = []
        for s_idx, sc in enumerate(script.get("script", []), 1):
            vo_text = st.session_state.get(f"live-script-scene-{story_id}-{s_idx}", sc.get("voiceover", "")).strip()
            if vo_text:
                if s_idx == 1:
                    article_parts.append(f'<span style="color:var(--primary); font-weight:800;">[LEAD]</span> {vo_text}')
                else:
                    article_parts.append(f'<span class="teleprompter-cue-separator">▸</span> {vo_text}')
        if article_parts:
            st.markdown(" ".join(article_parts), unsafe_allow_html=True)
        else:
            st.markdown("<em>Narration cues will display here as continuous text.</em>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        _render_packaging_deck_and_phone(
            script=script,
            story_title=story.title,
            current_headline=edited_headline,
            current_vo1=current_vo1,
            headline_enabled=bool(st.session_state.live_headline_enabled),
        )

    if st.session_state.live_approved_script:
        st.success("Script approved. Audio and subtitle handoffs are ready.")
        if st.session_state.live_handoff_error:
            st.error(st.session_state.live_handoff_error)
            if st.button(
                "Retry Audio / Subtitles",
                key="live-retry-handoffs",
            ):
                try:
                    with st.spinner("Retrying audio and subtitle handoffs…"):
                        _live_generate_audio_and_subtitles()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.session_state.live_handoff_error = str(exc)
                st.rerun()


def _render_live_upload():
    is_top5 = st.session_state.live_production_line == "top_5"
    stored_video_path = st.session_state.get("live_rendered_video_path")
    video_path = Path(stored_video_path) if stored_video_path else None
    if video_path is not None and not video_path.is_absolute():
        video_path = Path(__file__).resolve().parent / video_path

    if is_top5:
        script = st.session_state.live_top5_script_handoff
        slides = list(script.get("slides") or []) if isinstance(script, dict) else []
        title = str(slides[0].get("headline") or "").strip() if slides else ""
        if not isinstance(script, dict) or len(slides) != 6 or not title:
            st.info("Approve the Top-5 Scriptwriter result first.")
            return
        story_id = "top5"
    else:
        script = st.session_state.live_approved_script
        story = st.session_state.live_topics[st.session_state.live_selected_topic]
        story_id = _live_story_key(story)

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">UPLOAD QC</div>'
        '<div class="section-title">Final video and publish metadata</div></div>'
        '<div class="section-count">one approval</div>',
        unsafe_allow_html=True,
    )
    if video_path is None:
        st.error("Renderer did not hand a video path to Upload QC.")
        return
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        st.error(f"The rendered video cannot be found or is empty: {video_path}")
        st.caption("The factory expects the rendered file inside the Final-Shorts output folder. Return to Renderer and retry if needed.")
        return
    st.video(str(video_path), width=520)

    if is_top5:
        st.markdown("**Title**")
        st.write(title)
        st.caption("Top-5 uses the approved Slide 1 spoken headline as the YouTube title.")
    else:
        titles = list(st.session_state.live_upload_titles or script.get("titles") or [])
        if not titles:
            st.error("Scriptwriter did not return title candidates.")
            return
        st.caption("Edit the title candidates, choose the one to publish, then approve the metadata once.")
        edited_titles = []
        for index, candidate in enumerate(titles, 1):
            edited_titles.append(
                st.text_input(
                    f"Title {index} · {TITLE_OPTION_STYLES[index - 1]}",
                    value=str(candidate),
                    max_chars=100,
                    key=f"live-upload-title-{story_id}-{index}",
                )
            )
        st.session_state.live_upload_titles = edited_titles
        choice = st.pills(
            "Title to publish",
            list(range(len(edited_titles))),
            default=min(int(st.session_state.live_upload_title_choice), len(edited_titles) - 1),
            format_func=lambda index: edited_titles[index] or f"Title option {index + 1}",
            key=f"live-upload-choice-{story_id}",
        )
        if choice is None:
            choice = 0
        st.session_state.live_upload_title_choice = choice
        title = edited_titles[choice].strip()

    description_key = f"live-upload-description-{story_id}"
    hashtags_key = f"live-upload-hashtags-{story_id}"
    comment_key = f"live-upload-comment-{story_id}"
    if not st.session_state.live_upload_description:
        st.session_state.live_upload_description = str(script.get("seo_description") or "")
    if not st.session_state.live_upload_hashtags:
        st.session_state.live_upload_hashtags = " ".join(str(tag) for tag in script.get("hashtags") or [])
    if not st.session_state.live_upload_comment:
        st.session_state.live_upload_comment = str(script.get("comment") or "")

    st.text_area("Description", key=description_key, value=st.session_state.live_upload_description, height=150)
    st.text_input("Hashtags", key=hashtags_key, value=st.session_state.live_upload_hashtags)
    st.text_area("Public comment", key=comment_key, value=st.session_state.live_upload_comment, height=100)
    st.session_state.live_upload_description = st.session_state.get(description_key, "")
    st.session_state.live_upload_hashtags = st.session_state.get(hashtags_key, "")
    st.session_state.live_upload_comment = st.session_state.get(comment_key, "")

    if not st.session_state.live_upload_qc_approved:
        if st.button(
            "Approve Upload QC",
            type="primary",
            width="stretch",
            key="live-top5-approve-upload-qc" if is_top5 else "live-approve-upload-qc",
        ):
            st.session_state.live_upload_qc = {
                "title": title,
                "description": st.session_state.live_upload_description.strip(),
                "hashtags": st.session_state.live_upload_hashtags.strip(),
                "comment": st.session_state.live_upload_comment.strip(),
            }
            st.session_state.live_upload_qc_approved = True
            st.session_state.live_upload_result = None
            st.session_state.live_pipeline_notice = {
                "confirmed": "Upload QC confirmed",
                "next": "Upload controls are now unlocked.",
            }
            st.rerun()
        return

    qc = st.session_state.live_upload_qc or {}
    st.success("Metadata approved.")
    st.write(f"**Title:** {qc.get('title') or ''}")
    st.write(f"**Description:** {qc.get('description') or ''}")
    st.write(f"**Hashtags:** {qc.get('hashtags') or ''}")
    st.write(f"**Comment:** {qc.get('comment') or ''}")

    result = st.session_state.live_upload_result
    if result:
        st.success(f"Upload successful · Video ID: {result.get('video_id')}")
        if result.get("url"):
            st.link_button("Open YouTube video", result["url"], width="stretch")
        if result.get("requested_privacy") == "public":
            if result.get("comment_posted"):
                st.success("Public upload comment added to YouTube.")
            elif result.get("comment_error"):
                st.warning(
                    "The video was uploaded publicly, but the comment was not accepted: "
                    + str(result["comment_error"])
                )
        return

    left, right = st.columns(2, gap="medium")
    with left:
        public = st.button(
            "Upload Public",
            type="primary",
            width="stretch",
            key="live-top5-upload-public" if is_top5 else "live-upload-public",
        )
    with right:
        private = st.button(
            "Upload Private",
            width="stretch",
            key="live-top5-upload-private" if is_top5 else "live-upload-private",
        )
    if not (public or private):
        return

    privacy = "public" if public else "private"
    try:
        with st.spinner(f"Uploading video as {privacy}…"):
            from uploader import upload_video
            st.session_state.live_upload_result = upload_video(
                video_path,
                qc.get("title", ""),
                qc.get("description", ""),
                qc.get("hashtags", ""),
                qc.get("comment", ""),
                privacy,
            )
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(str(exc))
        return
    st.rerun()


def render_live_top5():
    from concurrent.futures import ThreadPoolExecutor

    from renderer import build_top5_card_preview
    from script_writer import estimate_speech_seconds, generate_top5_script

    stages = [
        "01 · Top-5 Topics",
        "02 · Scriptwriter",
        "03 · Audio",
        "04 · Visuals",
        "06 · Renderer",
        "07 · Upload QC",
    ]
    stage = st.session_state.get("live_stage")
    if stage not in stages:
        stage = stages[0]
        st.session_state.live_stage = stage

    _render_pipeline_progress(
        ["Topics", "Script", "Audio", "Visuals", "Render", "Upload"],
        stages.index(stage),
        complete_last=stage == "07 · Upload QC" and bool(st.session_state.live_upload_result),
    )
    _render_pipeline_notice("live_pipeline_notice")

    if stage == "01 · Top-5 Topics":
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TOP-5 · 01 · TOPIC PRODUCTION</div>'
            '<div class="section-title">Select and order five cricket stories</div>'
            '<div class="canvas-copy">Choose five headlines from the 20 grouped cricket stories, then set their exact order.</div></div>'
            '<div class="section-count">0–5 selected</div></div>',
            unsafe_allow_html=True,
        )
        topics = st.session_state.live_top5_topics
        left, mid, right = st.columns([1, 1, .8], gap="small")
        with left:
            fetch = st.button("Fetch current cricket stories", type="primary", width="stretch", key="live-top5-fetch")
        with mid:
            more = st.button("20 more articles", width="stretch", key="live-top5-more", disabled=not topics)
        with right:
            st.markdown(
                f'<div style="text-align:right;padding:.65rem .15rem;"><span class="badge">{len(topics)} stories</span></div>',
                unsafe_allow_html=True,
            )

        if fetch or more:
            existing = list(topics) if more else []
            with st.spinner("Fetching current cricket stories…"):
                try:
                    from topic_fetcher import fetch_top5_topics
                    new_topics = fetch_top5_topics(more=more, exclude_topics=existing, limit=20)
                    st.session_state.live_top5_topics = existing + new_topics
                    st.session_state.live_top5_selected = [] if not more else st.session_state.live_top5_selected
                    if not more:
                        st.session_state.live_top5_topic_open_tile = None
                except Exception as exc:
                    st.error(f"Failed to fetch cricket stories: {exc}")
            st.rerun()

        selected = st.session_state.live_top5_selected
        if selected:
            st.markdown(
                f'<div class="section-head"><div><div class="eyebrow">TOP 5 SELECTION</div>'
                f'<div class="section-title">{len(selected)} / 5 selected</div></div>'
                f'<div class="section-count">order matters</div></div>',
                unsafe_allow_html=True,
            )
            for slot, index in enumerate(list(selected)):
                topic = topics[index]
                row = st.columns([.12, 1.55, .26, .26, .34], gap="small")
                with row[0]:
                    st.markdown(f'<div class="topic-rank">#{slot + 1}</div>', unsafe_allow_html=True)
                with row[1]:
                    st.markdown(
                        f'<div class="topic-title">{topic.title}</div><div class="topic-meta">{topic.source or "Sports desk"}</div>',
                        unsafe_allow_html=True,
                    )
                with row[2]:
                    if st.button("↑", key=f"live-top5-up-{index}", disabled=slot == 0, width="stretch"):
                        selected[slot - 1], selected[slot] = selected[slot], selected[slot - 1]
                        st.rerun()
                with row[3]:
                    if st.button("↓", key=f"live-top5-down-{index}", disabled=slot == len(selected) - 1, width="stretch"):
                        selected[slot + 1], selected[slot] = selected[slot], selected[slot + 1]
                        st.rerun()
                with row[4]:
                    if st.button("Remove", key=f"live-top5-remove-{index}", width="stretch"):
                        selected.remove(index)
                        st.rerun()

        if topics:
            for start in range(0, len(topics), 2):
                cols = st.columns(2, gap="medium")
                for col, (index, tile) in zip(cols, enumerate(topics[start:start + 2], start=start)):
                    members = tuple(sorted(tile.group_members or (tile,), key=lambda item: item.score, reverse=True))
                    if tile.group_key.startswith("keyword:"):
                        tile_title = tile.group_key.split(":", 1)[1].title()
                    elif tile.group_key.startswith("player:"):
                        tile_title = tile.group_key.split(":", 1)[1].title()
                    else:
                        tile_title = tile.title
                    with col:
                        with st.container(key=f"live-top5-topic-{index}"):
                            open_tile = st.session_state.live_top5_topic_open_tile == index
                            if st.button(
                                f'{"▾" if open_tile else "▸"}  {tile_title}',
                                key=f"live-top5-topic-header-{index}",
                                width="stretch",
                                type="primary" if open_tile else "secondary",
                            ):
                                st.session_state.live_top5_topic_open_tile = None if open_tile else index
                                st.rerun()
                            if not open_tile:
                                continue
                            for member_index, member in enumerate(members):
                                selected_here = index in selected and topics[index].url == member.url
                                disabled = index not in selected and len(selected) >= 5
                                with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute", gap="small"):
                                    st.markdown(
                                        f'<div class="topic-title">{member.title}</div><div class="topic-meta">{member.source or "Sports desk"} · {member.published_at:%d %b · %H:%M UTC}</div>',
                                        unsafe_allow_html=True,
                                    )
                                    if st.button(
                                        "Selected" if selected_here else "Choose",
                                        key=f"live-top5-select-{index}-{member_index}",
                                        width="content",
                                        type="primary" if selected_here else "secondary",
                                        disabled=disabled,
                                    ):
                                        st.session_state.live_top5_topics[index] = replace(member, group_key=tile.group_key, group_members=members)
                                        if index not in selected:
                                            selected.append(index)
                                        st.session_state.live_top5_selected = selected
                                        st.session_state.live_top5_topic_open_tile = None
                                        st.rerun()
        else:
            st.markdown(
                '<div class="empty-state"><div class="empty-state-title">No cricket stories loaded</div>'
                '<div class="empty-state-copy">Fetch the current cricket story pool to start.</div></div>',
                unsafe_allow_html=True,
            )

        if len(selected) == 5 and st.button(
            "Approve Top-5 selection",
            type="primary",
            width="stretch",
            key="live-top5-approve-topics",
        ):
            stories = [
                {
                    "title": topics[index].title,
                    "url": topics[index].url,
                    "article": topics[index].description,
                    "source": topics[index].source,
                    "published_at": topics[index].published_at.isoformat(),
                }
                for index in selected
            ]
            st.session_state.live_top5_handoff = stories
            st.session_state.live_top5_script_data = None
            st.session_state.live_top5_script_handoff = None
            st.session_state.live_top5_audio_data = None
            st.session_state.live_top5_audio_handoff = None
            st.session_state.live_top5_visual_results = {
                number: {"source": "automatic", "assets": [], "success_threshold": 10}
                for number in range(1, 6)
            }
            st.session_state.live_top5_manual_visual_results = {}
            st.session_state.live_top5_real_image_results = {}
            st.session_state.live_top5_ai_image_results = {}
            st.session_state.live_top5_visual_handoff = None
            st.session_state.live_top5_visual_done = {number: False for number in range(1, 6)}
            st.session_state.live_top5_visual_futures = {}
            st.session_state.live_top5_visual_active_slide = 1
            st.session_state.live_visual_assignments = {}
            st.session_state.live_visual_crops = {}
            st.session_state.live_visuals_approved = False
            st.session_state.live_rendered_video_path = None
            st.session_state.live_upload_qc_approved = False
            st.session_state.live_upload_qc = None
            st.session_state.live_upload_result = None
            st.session_state.live_upload_description = ""
            st.session_state.live_upload_hashtags = ""
            st.session_state.live_upload_comment = ""

            from visual_fetcher import crawl_visuals
            executor = ThreadPoolExecutor(max_workers=5)
            for number, story in enumerate(stories, 1):
                st.session_state.live_top5_visual_futures[number] = executor.submit(
                    crawl_visuals,
                    dict(story),
                )
            st.session_state.live_top5_visual_executor = executor
            st.session_state.live_stage = "02 · Scriptwriter"
            st.session_state.live_pipeline_notice = {
                "confirmed": "Top-5 selection confirmed",
                "next": "Scriptwriter started. Automatic image scraping is running in parallel for all five stories.",
            }
            st.rerun()
        return

    if stage == "02 · Scriptwriter":
        stories = list(st.session_state.live_top5_handoff or [])
        if len(stories) != 5:
            st.info("Approve exactly five stories in Top-5 Topic Production first.")
            return
        result = st.session_state.live_top5_script_data
        if not isinstance(result, dict):
            if st.button(
                "Generate Top-5 Script",
                type="primary",
                width="stretch",
                key="live-top5-generate-script",
            ):
                try:
                    with st.spinner("Researching the five stories and writing the six-slide package…"):
                        result = generate_top5_script(stories)
                    st.session_state.live_top5_script_data = result
                    for slide in result.get("slides") or []:
                        number = int(slide.get("slide_number") or 0)
                        st.session_state[f"live-top5-script-headline-{number}"] = str(slide.get("headline") or "")
                        st.session_state[f"live-top5-script-body-{number}"] = str(slide.get("body") or "")
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
                    return
                st.rerun()
            st.info("Press Generate Top-5 Script to start the Scriptwriter.")
            return
        slides = list(result.get("slides") or [])
        if len(slides) != 6:
            st.error("Top-5 Scriptwriter must return exactly six slides.")
            return

        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TOP-5 · 02 · SCRIPTWRITER</div>'
            '<div class="section-title">Review the six-slide package</div></div>'
            '<div class="section-count">5 stories → 6 slides</div></div>',
            unsafe_allow_html=True,
        )
        for slide in slides:
            number = int(slide.get("slide_number") or 0)
            st.markdown(
                f'<div class="mini-label">SLIDE {number} · {"PACKAGE OPENER" if number == 1 else f"STORY {number - 1}"} · SPOKEN</div>',
                unsafe_allow_html=True,
            )
            headline = st.text_area("Spoken headline", key=f"live-top5-script-headline-{number}", height=88 if number == 1 else 105, max_chars=260)
            st.caption(f'{len(headline.split())} words · {estimate_speech_seconds(headline):.1f}s estimated speech')
            st.text_area("Visual-only body", key=f"live-top5-script-body-{number}", height=120, max_chars=600)
            st.divider()

        if st.button("Approve Top-5 Script", type="primary", width="stretch", key="live-top5-approve-script"):
            edited = {
                "slides": [
                    {
                        **slide,
                        "headline": st.session_state.get(f"live-top5-script-headline-{int(slide.get('slide_number') or 0)}", "").strip(),
                        "body": st.session_state.get(f"live-top5-script-body-{int(slide.get('slide_number') or 0)}", "").strip(),
                    }
                    for slide in slides
                ],
                "seo_description": str(result.get("seo_description") or "").strip(),
                "hashtags": list(result.get("hashtags") or []),
                "comment": str(result.get("comment") or "").strip(),
            }
            handoff = {
                "schema": "final-shorts.top5-script.v1",
                "slides": edited["slides"],
                "seo_description": edited["seo_description"],
                "hashtags": edited["hashtags"],
                "comment": edited["comment"],
                "stories": stories,
                "provider_used": result.get("provider_used"),
                "approved_for_audio": True,
            }
            st.session_state.live_top5_script_handoff = handoff
            st.session_state.live_approved_script = handoff
            st.session_state.live_top5_audio_data = None
            st.session_state.live_top5_audio_handoff = None
            st.session_state.live_stage = "03 · Audio"
            st.session_state.live_pipeline_notice = {
                "confirmed": "Top-5 Script QC confirmed",
                "next": "Moving to Audio.",
            }
            st.rerun()
        return

    if stage == "03 · Audio":
        from audio import approve_top5_audio, generate_top5_audio
        handoff = st.session_state.live_top5_script_handoff
        if not isinstance(handoff, dict):
            st.info("Approve the Top-5 Scriptwriter result first.")
            return
        audio = st.session_state.live_top5_audio_data
        if not isinstance(audio, dict):
            live_top5_engine_choice = st.pills(
                "Voice Engine",
                ["Chatterbox Turbo (Voice Cloning)", "Edge-TTS Neural"],
                default="Chatterbox Turbo (Voice Cloning)",
                key="live_top5_audio_engine_choice_v2",
            ) or "Chatterbox Turbo (Voice Cloning)"
            is_live_top5_chatterbox = "Chatterbox" in live_top5_engine_choice
            live_top5_reference = None
            live_top5_reference_ready = True
            if is_live_top5_chatterbox:
                from audio import CHATTERBOX_VOICE_REFERENCES
                live_top5_reference_label = st.selectbox(
                    "Narrator voice",
                    list(CHATTERBOX_VOICE_REFERENCES),
                    key="live_top5_chatterbox_voice_reference",
                )
                live_top5_reference = CHATTERBOX_VOICE_REFERENCES[live_top5_reference_label]
                live_top5_reference_ready = live_top5_reference.is_file()
                st.caption(
                    f"{live_top5_reference_label}: "
                    + (f"reference ready ({live_top5_reference.name})" if live_top5_reference_ready
                       else f"missing {live_top5_reference.name} — place it in the factory root")
                )
            if st.button(
                "Generate Top-5 Audio",
                type="primary",
                width="stretch",
                key="live-top5-generate-audio",
                disabled=is_live_top5_chatterbox and not live_top5_reference_ready,
            ):
                try:
                    with st.spinner("Generating the six spoken Top-5 lines…"):
                        audio = generate_top5_audio(
                            handoff,
                            output_dir="output/live/top5_audio",
                            engine="chatterbox" if is_live_top5_chatterbox else "edge",
                            reference=live_top5_reference if is_live_top5_chatterbox else None,
                        )
                    st.session_state.live_top5_audio_data = audio
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
                    return
                st.rerun()
            st.info("Press Generate Top-5 Audio to start voice generation.")
            return
        for scene in audio.get("scenes") or []:
            with st.container(key=f"live-top5-audio-scene-{scene['scene']}"):
                st.markdown(
                    f'**Line {scene["scene"]}** <span class="topic-meta">· {scene["duration"]:.2f}s · {len(scene["timings"])} timings</span>',
                    unsafe_allow_html=True,
                )
                st.audio(
                    scene["path"],
                    format="audio/wav" if str(scene["path"]).lower().endswith(".wav") else "audio/mp3",
                )
                st.caption("Cached" if scene["from_cache"] else "Fresh TTS generation")
        st.caption(
            f'Voice: {audio.get("voice") or "HYPE COMMENTATOR"} · Rate: {audio.get("rate_percent", 0):+.0f}% · Total: {audio.get("total_duration", 0):.2f}s'
        )
        if not isinstance(st.session_state.live_top5_audio_handoff, dict):
            if st.button("Approve Top-5 audio", type="primary", width="stretch", key="live-top5-approve-audio"):
                try:
                    st.session_state.live_top5_audio_handoff = approve_top5_audio(audio)
                except ValueError as exc:
                    st.error(str(exc))
                    return
                st.session_state.live_approved_audio = st.session_state.live_top5_audio_handoff
                st.session_state.live_stage = "04 · Visuals"
                st.session_state.live_pipeline_notice = {
                    "confirmed": "Top-5 Audio QC confirmed",
                    "next": "Moving to Visuals.",
                }
                st.rerun()
        return

    if stage == "04 · Visuals":
        script = st.session_state.live_top5_script_handoff
        if not isinstance(script, dict) or len(script.get("slides") or []) != 6:
            st.info("Approve the Top-5 Scriptwriter result first.")
            return

        assignments = st.session_state.live_visual_assignments
        slides = list(script.get("slides") or [])
        stories = list(script.get("stories") or [])

        scraper_waiting = [
            future for number, future in st.session_state.live_top5_visual_futures.items()
            if future is not None and not st.session_state.live_top5_visual_done.get(number)
        ]
        if scraper_waiting:
            with st.spinner("Finishing automatic image scraping…"):
                for number, future in st.session_state.live_top5_visual_futures.items():
                    if future is None or st.session_state.live_top5_visual_done.get(number):
                        continue
                    try:
                        st.session_state.live_top5_visual_results[number] = future.result()
                    except Exception as exc:
                        st.session_state.live_top5_visual_results[number] = {
                            "source": "automatic",
                            "assets": [],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    st.session_state.live_top5_visual_done[number] = True
                executor = st.session_state.get("live_top5_visual_executor")
                if executor is not None:
                    executor.shutdown(wait=True)
                    st.session_state.live_top5_visual_executor = None

        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TOP-5 · 04 · VISUALS</div>'
            '<div class="section-title">Build and review all six slides</div></div>',
            unsafe_allow_html=True,
        )

        labels = [f"Slide {number}" for number in range(1, 7)]
        active_label = st.pills(
            "Top-5 slide",
            labels,
            default=f'Slide {int(st.session_state.live_top5_visual_active_slide or 1)}',
            key="live-top5-visual-slide",
            label_visibility="collapsed",
        ) or labels[0]
        active_slide = labels.index(active_label) + 1
        st.session_state.live_top5_visual_active_slide = active_slide

        slide = slides[active_slide - 1]
        headline = str(slide.get("headline") or "").strip()
        body = str(slide.get("body") or "").strip()
        specific_prompt = str(slide.get("specific_search_prompt") or "").strip()
        visual_intent = str(slide.get("visual_intent") or "").strip()
        story_number = 1 if active_slide <= 2 else active_slide - 1

        st.markdown(
            f'<div class="mini-label">SLIDE {active_slide} · {"PACKAGE OPENER" if active_slide == 1 else f"STORY {active_slide - 1}"} · APPROVED SCRIPT</div>',
            unsafe_allow_html=True,
        )
        if active_slide > 1 and len(stories) >= active_slide - 1:
            st.caption(str(stories[active_slide - 2].get("title") or "Selected story"))
        st.markdown(f"**{headline}**")
        if body:
            st.caption(f"Visual body: {body}")
        if visual_intent:
            st.caption(f"Visual intent: {visual_intent}")
        if specific_prompt:
            st.caption(f"Visual search prompt: {specific_prompt}")

        option = _render_visual_option_grid(
            TOP5_LIVE_VISUAL_OPTIONS,
            session_key="live_visual_option",
            button_prefix="live-top5-visual-source",
        )

        assets = []
        result_key = "auto"
        if option == "Option 3 · Real Image Search":
            with st.form(f"live-top5-real-{active_slide}"):
                query = st.text_input(
                    "Real image query",
                    value=specific_prompt,
                    key=f"live-top5-real-query-{active_slide}",
                )
                run = st.form_submit_button(
                    "Search real images",
                    type="primary",
                    width="stretch",
                )
            if run:
                query = query.strip()
                if query:
                    try:
                        from visual_search import search_images
                        st.session_state.live_top5_real_image_results[active_slide] = search_images(query)
                    except Exception as exc:
                        st.session_state.live_top5_real_image_results[active_slide] = {
                            "error": f"{type(exc).__name__}: {exc}"
                        }
                    st.rerun()
                else:
                    st.warning("Enter a query first.")
            result = st.session_state.live_top5_real_image_results.get(active_slide) or {}
            if result.get("error"):
                st.error(result["error"])
            assets = list(result.get("assets") or [])
            result_key = "real"
        elif option == "Option 5 · Card Studio":
            _render_card_studio(
                live=True,
                slide_count=6,
                top5=True,
                active_slide=active_slide,
                polygon_flow=True,
            )
            assets = []
            result_key = "card"
        elif option in {
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 4 · AI Generation",
        }:
            if option == "Option 1 · Automatic Scraper":
                source_story = 1 if active_slide <= 2 else active_slide - 1
                result = st.session_state.live_top5_visual_results.get(source_story) or {}
                assets = list(result.get("assets") or [])
                if result.get("error"):
                    st.error(result["error"])
                st.caption(
                    f'{len(assets)} images available · '
                    f'{"Finished" if st.session_state.live_top5_visual_done.get(source_story) else "Scraping in background"}'
                )
                result_key = "auto"
            elif option == "Option 2 · Manual Scraper":
                with st.form(f"live-top5-manual-{active_slide}"):
                    query = st.text_input(
                        "Manual query",
                        value=specific_prompt,
                        key=f"live-top5-manual-query-{active_slide}",
                    )
                    run = st.form_submit_button(
                        "Run manual scrape",
                        type="primary",
                        width="stretch",
                    )
                if run:
                    query = query.strip()
                    if query:
                        try:
                            from visual_fetcher import manual_crawl_visuals
                            st.session_state.live_top5_manual_visual_results[active_slide] = manual_crawl_visuals(query)
                        except Exception as exc:
                            st.session_state.live_top5_manual_visual_results[active_slide] = {
                                "error": f"{type(exc).__name__}: {exc}"
                            }
                        st.rerun()
                    else:
                        st.warning("Enter a query first.")
                result = st.session_state.live_top5_manual_visual_results.get(active_slide) or {}
                if result.get("error"):
                    st.error(result["error"])
                assets = list(result.get("assets") or [])
                result_key = "manual"
            else:
                with st.form(f"live-top5-ai-{active_slide}"):
                    query = st.text_input(
                        "AI prompt",
                        value=specific_prompt,
                        key=f"live-top5-ai-query-{active_slide}",
                    )
                    run = st.form_submit_button(
                        "Generate images",
                        type="primary",
                        width="stretch",
                    )
                if run:
                    query = query.strip()
                    if query:
                        try:
                            from visual_generator import generate_images
                            st.session_state.live_top5_ai_image_results[active_slide] = generate_images(query)
                        except Exception as exc:
                            st.session_state.live_top5_ai_image_results[active_slide] = {
                                "error": f"{type(exc).__name__}: {exc}"
                            }
                        st.rerun()
                    else:
                        st.warning("Enter a prompt first.")
                result = st.session_state.live_top5_ai_image_results.get(active_slide) or {}
                if result.get("error"):
                    st.error(result["error"])
                assets = list(result.get("assets") or [])
                result_key = "ai"

            if assets:
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin:0.35rem 0 0.55rem 0;font-size:0.75rem;color:var(--muted);">'
                    f'<span><strong>{len(assets)} images in pool</strong> · scroll inside tray to browse</span>'
                    f'<span>Choose for slide {active_slide}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                with st.container(height=520):
                    for start in range(0, len(assets), 4):
                        cols = st.columns(4, gap="small")
                        for offset, raw_asset in enumerate(assets[start:start + 4]):
                            index = start + offset
                            asset = dict(raw_asset)
                            asset_key = _visual_asset_key(f"live-{result_key}", index, asset)
                            cropped = st.session_state.live_visual_crops.get(asset_key)
                            source = str(asset.get("publisher") or asset.get("source") or asset.get("model") or "Web source").strip()
                            label = str(asset.get("article_title") or asset.get("title") or asset.get("model") or "Selected visual").strip()
                            preview = _fit_visual_preview(cropped if cropped else asset.get("bytes"), 240, 360)
                            with cols[offset]:
                                with st.container(key=f"live-top5-visual-card-{active_slide}-{result_key}-{index}"):
                                    if preview is not None:
                                        st.image(preview, width="stretch")
                                    st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                                    if label:
                                        st.markdown(f'<div class="visual-detail">{label}</div>', unsafe_allow_html=True)
                                    if cropped:
                                        st.markdown('<span class="visual-crop-label">CROP APPLIED</span>', unsafe_allow_html=True)
                                    use_col, crop_col = st.columns(2, gap="small")
                                    with use_col:
                                        if st.button("Use this image", type="primary", width="stretch", key=f"live-top5-use-{active_slide}-{result_key}-{index}"):
                                            selected_bytes = bytes(cropped) if cropped else bytes(asset.get("bytes") or b"")
                                            try:
                                                card_preview = build_top5_card_preview(
                                                    selected_bytes, headline, body,
                                                    story_number=story_number,
                                                    total_stories=5,
                                                    source_label=source,
                                                    subject_cutout=False,
                                                )
                                            except Exception:
                                                card_preview = selected_bytes
                                            st.session_state.live_visual_assignments[active_slide] = {
                                                "asset_key": asset_key,
                                                "result_key": result_key,
                                                "source": source,
                                                "label": label,
                                                "bytes": selected_bytes,
                                                "preview_bytes": card_preview,
                                                "top5_card": {
                                                    "headline": headline,
                                                    "body": body,
                                                    "story_number": story_number,
                                                    "total_stories": 5,
                                                },
                                            }
                                            st.session_state.live_visuals_approved = False
                                            st.rerun()
                                    with crop_col:
                                        if st.button("Crop / reposition", width="stretch", key=f"live-top5-crop-{active_slide}-{result_key}-{index}"):
                                            if isinstance(asset.get("bytes"), (bytes, bytearray)):
                                                _crop_visual_dialog(asset_key, bytes(asset["bytes"]), label, crop_store="live_visual_crops")
        assignment = assignments.get(active_slide)
        if assignment:
            st.divider()
            st.markdown('<div class="mini-label">CURRENT ATTACHMENT · ACTUAL RENDER</div>', unsafe_allow_html=True)
            col_t5_p, col_t5_i = st.columns([1, 1], gap="medium")
            preview = assignment.get("preview_bytes") or assignment.get("bytes")
            with col_t5_p:
                if preview:
                    st.image(preview, width=280)
            with col_t5_i:
                st.caption(f'**Source:** {assignment.get("source") or "Visual"}\n\n**Label:** {assignment.get("label") or "Selected"}')
                if st.button("Clear attached slide", width="stretch", key=f"live-top5-clear-{active_slide}"):
                    assignments.pop(active_slide, None)
                    st.session_state.live_visuals_approved = False
                    st.rerun()

        board_cols = st.columns(3, gap="medium")
        for number in range(1, 7):
            with board_cols[(number - 1) % 3]:
                item = assignments.get(number)
                board_slide = slides[number - 1]
                with st.container(key=f"live-top5-board-{number}"):
                    st.markdown(f'<div class="eyebrow">SLIDE {number}</div>', unsafe_allow_html=True)
                    st.markdown(f'**{str(board_slide.get("headline") or "").strip()}**')
                    board_body = str(board_slide.get("body") or "").strip()
                    if board_body:
                        st.caption(board_body)
                    if item and (item.get("preview_bytes") or item.get("bytes")):
                        st.image(item.get("preview_bytes") or item.get("bytes"), width="stretch")
                    else:
                        st.markdown('<div class="empty-slot">NOT ATTACHED</div>', unsafe_allow_html=True)

        if len(assignments) == 6:
            if st.button("Approve Top-5 visuals", type="primary", width="stretch", key="live-top5-approve-visuals"):
                st.session_state.live_top5_visual_handoff = [assignments[number] for number in range(1, 7)]
                st.session_state.live_visuals_approved = True
                st.session_state.live_stage = "06 · Renderer"
                st.session_state.live_pipeline_notice = {
                    "confirmed": "Top-5 Visual QC confirmed",
                    "next": "Moving to Renderer.",
                }
                st.rerun()
        else:
            st.info("Attach one visual treatment to each of the six slides before approving Visuals.")

        return

    if stage == "06 · Renderer":
        from renderer import render_production_video
        script = st.session_state.live_top5_script_handoff
        audio = st.session_state.live_top5_audio_handoff
        visuals = st.session_state.live_top5_visual_handoff
        if not isinstance(script, dict) or not isinstance(audio, dict) or not isinstance(visuals, list) or len(visuals) != 6:
            st.info("Renderer is waiting for the approved Top-5 Script, Audio and Visual handoffs.")
            return
        video_path = st.session_state.live_rendered_video_path
        if not video_path:
            key = hashlib.sha1(
                "|".join(str(item.get("url") or item.get("title") or "") for item in script.get("stories") or []).encode("utf-8")
            ).hexdigest()[:12]
            output = Path(__file__).resolve().parent / "output" / "live" / "top5" / f"{key}.mp4"
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                with st.spinner("Rendering the final Top-5 Short…"):
                    render_production_video(
                        script, audio, None, visuals,
                        output_path=output,
                        headline_enabled=False,
                    )
                st.session_state.live_rendered_video_path = str(output.resolve())
                st.rerun()
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
                return
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TOP-5 · 06 · RENDERER</div>'
            '<div class="section-title">Review the finished six-slide Short</div></div>'
            '<div class="section-count">explicit approval</div></div>',
            unsafe_allow_html=True,
        )
        st.video(str(video_path), width=520)
        if st.button("Approve Top-5 Renderer", type="primary", width="stretch", key="live-top5-approve-renderer"):
            st.session_state.live_stage = "07 · Upload QC"
            st.session_state.live_pipeline_notice = {
                "confirmed": "Top-5 Renderer QC confirmed",
                "next": "Moving to Upload QC.",
            }
            st.rerun()
        return

    if stage == "07 · Upload QC":
        _render_live_upload()


def render_live_dashboard():
    left, right = st.columns([1.4, .45], gap="large")
    with left:
        st.markdown(
            '<div class="live-product-head">'
            '<div><div class="eyebrow">LIVE PRODUCTION</div>'
            '<div class="live-product-title">Make the Short.</div>'
            '<div class="hero-subtitle">Choose a production line to start.</div></div>'
            '<div class="live-status"><span></span> Ready for a story</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with right:
        controls = st.columns(2, gap="small")
        with controls[0]:
            if st.button("New", key="live-new-short", width="stretch"):
                _live_reset_downstream()
                st.session_state.live_production_line = None
                st.session_state.live_desk = None
                st.session_state.live_cricket_profile = None
                st.session_state.live_topics = []
                st.session_state.live_topics_profile = None
                st.session_state.live_stage = "01 · Story"
                st.rerun()
        with controls[1]:
            if st.button("Home", key="live-home", width="stretch"):
                st.session_state.app_mode = "home"
                st.rerun()

    if st.session_state.live_production_line is None:
        st.space("medium")
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">START PRODUCTION</div>'
            '<div class="section-title">Choose a production line</div></div>'
            '<div class="section-count">select one to begin</div></div>',
            unsafe_allow_html=True,
        )
        choices = [
            (
                "live-line-deep-dive",
                "01 · DEEP-DIVE",
                "DEEP-DIVE",
                "Single-story production. Choose Cricket or Niche Sports after entering.",
            ),
            (
                "live-line-top-5",
                "02 · TOP-5",
                "TOP-5",
                "Five cricket stories in one daily production package. Design in progress.",
            ),
            (
                "live-line-otd",
                "03 · OTD",
                "ON THIS DAY",
                "A daily historical sports package built around the date. Design in progress.",
            ),
            (
                "live-line-youtube-trends",
                "04 · YT TRENDS",
                "YT Trends",
                "Start from current YouTube search trends.",
            ),
        ]
        cols = st.columns(4, gap="small")
        for col, (key, eyebrow, title, copy) in zip(cols, choices):
            with col:
                with st.container(key=key):
                    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="choice-title">{title}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="choice-copy">{copy}</div>', unsafe_allow_html=True)
                    st.space("medium")
                    button_label = {
                        "01 · DEEP-DIVE": "Choose Deep-Dive →",
                        "02 · TOP-5": "Open Top-5 →",
                        "03 · OTD": "Open OTD →",
                        "04 · YT TRENDS": "Open YT Trends →",
                    }[eyebrow]
                    if st.button(button_label, type="primary", width="stretch", key=f"{key}-button"):
                        st.session_state.live_production_line = {
                            "01 · DEEP-DIVE": "deep_dive",
                            "02 · TOP-5": "top_5",
                            "03 · OTD": "otd",
                            "04 · YT TRENDS": "youtube_trends",
                        }[eyebrow]
                        _live_reset_downstream()
                        st.session_state.live_desk = (
                            "youtube_trends" if eyebrow == "04 · YT TRENDS" else None
                        )
                        st.session_state.live_cricket_profile = None
                        st.session_state.live_topics_profile = None
                        st.session_state.live_topics = []
                        if eyebrow == "04 · YT TRENDS":
                            from topic_fetcher import fetch_youtube_search_trends
                            st.session_state.live_youtube_trend_results = []
                            st.session_state.live_youtube_trend_selected = None
                            st.session_state.live_youtube_trend_keyword = ""
                            st.session_state.live_youtube_trend_error = ""
                            try:
                                with st.spinner("Reading current YouTube search trends…"):
                                    st.session_state.live_youtube_trend_results = fetch_youtube_search_trends(limit=20)
                            except (RuntimeError, ValueError, OSError) as exc:
                                st.session_state.live_youtube_trend_error = str(exc)
                        st.rerun()
        return

    if (
        st.session_state.live_production_line == "youtube_trends"
        and st.session_state.live_stage == "01 · Story"
    ):
        render_youtube_trends_topic_fetcher(live=True)
        return

    if st.session_state.live_production_line == "top_5":
        return render_live_top5()


    if st.session_state.live_production_line == "otd":
        st.space("medium")
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">03 · OTD · TEST-FIRST STAGE</div>'
            '<div class="section-title">On This Day (WIP)</div></div></div>',
            unsafe_allow_html=True,
        )
        st.info(
            "On This Day is currently undergoing Test-first proving. Per factory operating rules "
            "(TEST FIRST → USER APPROVAL → PUSH TO LIVE), OTD topic fetching and script generation "
            "are active in the Test Lab awaiting user review and approval."
        )
        col1, col2 = st.columns([1, 1], gap="small")
        with col1:
            if st.button("Open OTD in Test Lab →", type="primary", key="live-otd-to-test", width="stretch"):
                st.session_state.app_mode = "test"
                st.session_state.test_production_line = "otd"
                st.session_state.test_stage = "01 · Topic Fetcher"
                st.rerun()
        with col2:
            if st.button("← Back to production lines", key="live-back-from-otd", width="stretch"):
                st.session_state.live_production_line = None
                st.session_state.live_desk = None
                st.rerun()
        return

    if st.session_state.live_production_line == "deep_dive":
        st.space("medium")
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">DEEP-DIVE</div>'
            '<div class="section-title">Choose your sports desk</div></div>'
            '<div class="section-count">single-story production</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("← Back to production lines", key="live-back-from-deep-dive"):
            _live_reset_downstream()
            st.session_state.live_production_line = None
            st.session_state.live_desk = None
            st.session_state.live_cricket_profile = None
            st.session_state.live_topics_profile = None
            st.session_state.live_topics = []
            st.rerun()

    if st.session_state.live_desk is None:
        left, right = st.columns(2, gap="small")
        with left:
            with st.container(key="live-choice-cricket"):
                st.markdown('<div class="eyebrow">01 · CRICKET</div>', unsafe_allow_html=True)
                st.markdown('<div class="choice-title">CRICKET</div>', unsafe_allow_html=True)
                st.markdown('<div class="choice-copy">India / Asia and global cricket.</div>', unsafe_allow_html=True)
                st.space("medium")
                if st.button("Choose Cricket →", type="primary", width="stretch", key="live-choose-cricket"):
                    st.session_state.live_desk = "cricket"
                    st.rerun()
        with right:
            with st.container(key="live-choice-niche"):
                st.markdown('<div class="eyebrow">02 · NICHE SPORTS</div>', unsafe_allow_html=True)
                st.markdown('<div class="choice-title">NICHE</div>', unsafe_allow_html=True)
                st.markdown('<div class="choice-copy">Tennis, badminton, motorsport, athletics, hockey, chess and more.</div>', unsafe_allow_html=True)
                st.space("medium")
                if st.button("Choose Niche Sports →", type="primary", width="stretch", key="live-choose-niche"):
                    st.session_state.live_desk = "niche"
                    st.session_state.live_cricket_profile = None
                    st.session_state.live_topics_profile = None
                    st.session_state.live_topics = []
                    profile = "niche_sports"
                    with st.spinner("Finding the top 20 niche-sports stories…"):
                        try:
                            from topic_fetcher import fetch_topics
                            st.session_state.live_topics = fetch_topics(
                                profile,
                                more=False,
                                exclude_topics=[],
                                limit=20,
                            )
                        except Exception as exc:
                            st.error(f"Story fetch failed: {exc}")
                            st.session_state.live_topics = []
                    st.session_state.live_topics_profile = profile
                    st.rerun()
        return

    if st.session_state.live_desk == "cricket" and st.session_state.live_cricket_profile is None:
        st.space("medium")
        st.markdown('<div class="section-head"><div><div class="eyebrow">CRICKET DESK</div><div class="section-title">Choose the cricket lane</div></div></div>', unsafe_allow_html=True)
        left, right = st.columns(2, gap="small")
        cricket_choices = [
            ("live-cricket-india", "01 · INDIA / ASIA", "INDIA / ASIA", "cricket_india_asia"),
            ("live-cricket-global", "02 · GLOBAL", "GLOBAL", "cricket_global"),
        ]
        for col, (key, eyebrow, title, profile) in zip((left, right), cricket_choices):
            with col:
                with st.container(key=key):
                    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="choice-title">{title}</div>', unsafe_allow_html=True)
                    if st.button(f"Choose {title} →", type="primary", width="stretch", key=f"{key}-button"):
                        st.session_state.live_cricket_profile = profile
                        st.session_state.live_topics = []
                        with st.spinner("Finding the top 20 cricket stories…"):
                            try:
                                from topic_fetcher import fetch_topics
                                st.session_state.live_topics = fetch_topics(
                                    profile,
                                    more=False,
                                    exclude_topics=[],
                                    limit=20,
                                )
                            except Exception as exc:
                                st.error(f"Story fetch failed: {exc}")
                                st.session_state.live_topics = []
                        st.session_state.live_topics_profile = profile
                        st.rerun()
        return

    if not st.session_state.live_topics:
        st.warning("No stories were returned for this desk.")
        if st.button(
            "Retry story search",
            type="primary",
            width="stretch",
            key="live-retry-topics",
        ):
            profile = st.session_state.live_topics_profile
            if profile:
                with st.spinner("Searching for current sports stories…"):
                    try:
                        from topic_fetcher import fetch_topics
                        st.session_state.live_topics = fetch_topics(
                            profile,
                            more=False,
                            exclude_topics=[],
                            limit=20,
                        )
                    except Exception as exc:
                        st.error(f"Story fetch failed: {exc}")
                        st.session_state.live_topics = []
                st.rerun()
        return

    live_stage_order = ["01 · Story", "02 · Script", "03 · Audio + Subs", "04 · Visuals + Render", "05 · Upload"]
    live_stage_labels = ["Story", "Script", "Audio + Subs", "Visuals + Render", "Upload"]
    current_stage = live_stage_order.index(st.session_state.live_stage)
    upload_complete = current_stage == len(live_stage_order) - 1 and bool(st.session_state.live_upload_result)
    _render_pipeline_progress(live_stage_labels, current_stage, complete_last=upload_complete)
    _render_pipeline_notice("live_pipeline_notice")

    if st.session_state.live_stage == "01 · Story":
        if st.session_state.live_production_line == "youtube_trends":
            render_youtube_trends_topic_fetcher(live=True)
            return
        st.markdown('<div class="section-head"><div><div class="eyebrow">STORY DESK</div><div class="section-title">Choose your story</div></div><div class="section-count">select one headline to start production</div></div>', unsafe_allow_html=True)
        topics = st.session_state.live_topics
        cricket_profile = st.session_state.live_topics_profile in {"cricket_india_asia", "cricket_global"}

        if cricket_profile:
            search_col, button_col = st.columns([3, 1], gap="small")
            with search_col:
                keyword = st.text_input(
                    "Search by player, team, event or keyword",
                    placeholder="e.g. Babar Azam, Asia Cup, record",
                    key="live_topic_keyword",
                    label_visibility="collapsed",
                ).strip()
            with button_col:
                keyword_search = st.button(
                    "Search keyword",
                    width="stretch",
                    key="live-topic-keyword-search",
                )
        else:
            keyword = ""
            keyword_search = False

        selection = _render_topic_tiles(
            topics,
            st.session_state.live_selected_topic,
            columns=2,
            open_state_key="live_topic_open_tile",
            key_prefix="live-",
        )
        if selection:
            index, member, members = selection
            st.session_state.live_topics[index] = replace(
                member,
                group_key=topics[index].group_key,
                group_members=members,
            )
            _live_start_story(index)
            st.rerun()

        more_clicked = st.button("Find 20 more unique stories", width="stretch", key="live-find-more")
        if keyword_search or more_clicked:
            if keyword_search and not keyword:
                st.warning("Enter a keyword first.")
            else:
                with st.spinner(
                    "Searching targeted cricket stories…" if keyword_search
                    else "Searching for 20 additional unique stories…"
                ):
                    try:
                        existing = list(st.session_state.live_topics)
                        from topic_fetcher import fetch_topics
                        new_topics = fetch_topics(
                            st.session_state.live_topics_profile,
                            more=more_clicked and not keyword_search,
                            exclude_topics=existing,
                            limit=20,
                            keyword=keyword if keyword_search else None,
                        )
                        if keyword_search:
                            keyword_members = tuple(
                                member
                                for topic in new_topics
                                for member in (topic.group_members or (topic,))
                            )
                            if keyword_members:
                                keyword_tile = replace(
                                    keyword_members[0],
                                    group_key=f"keyword:{keyword}",
                                    group_members=keyword_members,
                                )
                                st.session_state.live_topics = existing + [keyword_tile]
                        else:
                            st.session_state.live_topics = existing + new_topics
                    except Exception as exc:
                        st.error(f"Failed to fetch additional stories: {exc}")
                st.rerun()
        return

    selected_index = st.session_state.live_selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.live_topics):
        st.session_state.live_stage = "01 · Story"
        st.rerun()

    topic = st.session_state.live_topics[selected_index]
    st.markdown(
        f'<div class="section-head"><div><div class="eyebrow">SELECTED STORY</div><div class="section-title">{topic.title}</div></div>'
        f'<div class="section-count">{st.session_state.live_stage.upper()}</div></div>',
        unsafe_allow_html=True,
    )

    if st.button("← Back to stories", key="live-back-to-stories"):
        _live_reset_downstream()
        st.rerun()

    if st.session_state.live_stage == "02 · Script":
        _render_live_script()
        return

    if st.session_state.live_stage == "03 · Audio + Subs":
        script = st.session_state.live_approved_script
        if not isinstance(script, dict):
            st.warning("Approve the Scriptwriter before generating Audio.")
            return
        live_audio_engine_choice = st.pills(
            "Voice Engine",
            ["Chatterbox Turbo (Voice Cloning)", "Edge-TTS Neural"],
            default="Chatterbox Turbo (Voice Cloning)",
            key="live_audio_engine_choice_v2",
        ) or "Chatterbox Turbo (Voice Cloning)"
        live_language = str(script.get("language_used") or "english").strip().casefold()
        is_live_chatterbox = "Chatterbox" in live_audio_engine_choice
        if is_live_chatterbox and live_language not in {"english", "en"}:
            st.warning("Chatterbox Turbo supports English only. Select Edge-TTS Neural for Hindi or Telugu narration.")
        live_reference_ready = True
        if is_live_chatterbox:
            from audio import CHATTERBOX_VOICE_REFERENCES
            live_reference_label = st.selectbox(
                "Narrator voice",
                list(CHATTERBOX_VOICE_REFERENCES),
                key="live_audio_voice_reference",
            )
            live_reference_path = CHATTERBOX_VOICE_REFERENCES[live_reference_label]
            live_reference_ready = live_reference_path.is_file()
            st.caption(
                f"{live_reference_label}: "
                + (f"reference ready ({live_reference_path.name})" if live_reference_ready
                   else f"missing {live_reference_path.name} — place it in the factory root")
            )
        if not isinstance(st.session_state.live_approved_audio, dict) or not isinstance(st.session_state.live_subtitle_data, dict):
            if st.session_state.live_handoff_error:
                st.error(st.session_state.live_handoff_error)
            if st.button(
                "Retry Audio / Subtitles" if st.session_state.live_handoff_error else "Generate Audio + Subtitles",
                type="primary",
                width="stretch",
                key="live-generate-handoffs-stage",
                disabled=(is_live_chatterbox and live_language not in {"english", "en"}) or (is_live_chatterbox and not live_reference_ready),
            ):
                st.session_state.live_handoff_error = ""
                st.session_state.live_approved_audio = None
                st.session_state.live_subtitle_data = None
                try:
                    with st.spinner("Generating Audio and Subtitles…"):
                        _live_generate_audio_and_subtitles()
                    st.session_state.live_stage = "04 · Visuals + Render"
                    st.session_state.live_pipeline_notice = {
                        "confirmed": "Audio + Subtitles ready",
                        "next": "Moving to Visuals + Render.",
                    }
                except (RuntimeError, ValueError, OSError) as exc:
                    st.session_state.live_handoff_error = str(exc)
                st.rerun()
            return
        st.success("Audio and subtitles are approved. Moving to Visuals.")
        return

    if st.session_state.live_stage == "04 · Visuals + Render":
        script = st.session_state.live_approved_script
        audio_ready = isinstance(st.session_state.live_approved_audio, dict)
        subtitle_ready = isinstance(st.session_state.live_subtitle_data, dict)
        if not audio_ready or not subtitle_ready:
            st.warning("Audio and subtitle handoffs are not ready yet.")
            return

        visual_result = st.session_state.get("live_visual_result")
        if visual_result is None:
            with st.spinner("Scraping the selected story and related publisher pages…"):
                try:
                    _live_scrape_automatic_visuals()
                except Exception as exc:
                    st.session_state.live_visual_result = {
                        "error": f"{type(exc).__name__}: {exc}"
                    }
        _render_live_visuals(len(script.get("script") or []) if isinstance(script, dict) else 0)
        return

    if st.session_state.live_stage == "05 · Upload":
        _render_live_upload()
        return

profiles = {
    "Cricket India / Asia": "cricket_india_asia",
    "Cricket Global": "cricket_global",
    "Niche Sports": "niche_sports",
}



def render_youtube_trends_topic_fetcher(*, live=False):
    from topic_fetcher import fetch_youtube_search_trends, fetch_youtube_trend_topics

    results_key = "live_youtube_trend_results" if live else "youtube_trend_results"
    selected_key = "live_youtube_trend_selected" if live else "youtube_trend_selected"
    keyword_key = "live_youtube_trend_keyword" if live else "youtube_trend_keyword"
    search_query_key = "live_youtube_trend_search_query" if live else "youtube_trend_search_query"
    error_key = "live_youtube_trend_error" if live else "youtube_trend_error"
    topics_key = "live_topics" if live else "topics"
    selected_topic_key = "live_selected_topic" if live else "selected_topic"
    open_tile_key = "live_topic_open_tile" if live else "topic_open_tile"
    profile_key = "live_topics_profile" if live else "topic_desk_profile"
    button_prefix = "live-youtube-trend-" if live else "youtube-trend-"

    if st.session_state.get(error_key):
        st.error(st.session_state[error_key])
        if st.button(
            "Retry YT trends",
            type="primary",
            width="stretch",
            key=f"{button_prefix}retry",
        ):
            st.session_state[error_key] = ""
            st.session_state[search_query_key] = ""
            try:
                with st.spinner("Reading current YouTube search trends…"):
                    st.session_state[results_key] = fetch_youtube_search_trends(limit=20)
            except (RuntimeError, ValueError, OSError) as exc:
                st.session_state[error_key] = str(exc)
            st.rerun()

    results = st.session_state[results_key]
    if not results:
        st.info("No current YouTube search trends were returned.")
        return

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">01 · YT TRENDS</div>'
        '<div class="canvas-title">Choose a story driven by current YouTube search trends</div>'
        '<div class="canvas-copy">These are current YouTube search signals with relevant news published in the last 24 hours.</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">TOP 20</div>'
        '<div class="section-title">Story opportunities</div></div>'
        '<div class="section-count">single trend pool</div></div>',
        unsafe_allow_html=True,
    )

    for index, item in enumerate(results):
        left, mid, right = st.columns([1.65, .75, .42], gap="small")
        with left:
            st.markdown(
                f'<div class="topic-title">{item["top_news_title"]}</div>'
                f'<div class="topic-meta">{item["signal"]}'
                f'{" · autocomplete" if item["youtube_autocomplete"] else ""}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f'Search target: “{item["trend_query"]}”')
            st.caption(
                f'Story subject: {item["keyword"]} · '
                f'{item["news_count"]} current '
                f'{"story" if item["news_count"] == 1 else "stories"}'
            )
            st.caption(item["hashtag"])
        with mid:
            st.caption(f'Rank #{index + 1}')
            st.caption(f'Opportunity {item["score"]:.0f}')
        with right:
            selected = st.session_state[selected_key] == index
            if st.button(
                "Selected" if selected else "Use",
                type="primary" if selected else "secondary",
                width="stretch",
                key=f"{button_prefix}select-{index}",
            ):
                keyword = item["keyword"]
                st.session_state[selected_key] = index
                st.session_state[keyword_key] = keyword
                st.session_state[search_query_key] = item["trend_query"]
                st.session_state[profile_key] = item["profile"]
                if live:
                    _live_reset_downstream()
                else:
                    st.session_state[selected_topic_key] = None
                    st.session_state[open_tile_key] = None
                    st.session_state.script_data = None
                    st.session_state.approved_script = None
                    st.session_state.audio_data = None
                    st.session_state.approved_audio = None
                    st.session_state.subtitle_data = None
                    st.session_state.approved_subtitles = None
                    st.session_state.visual_result = None
                    st.session_state.visual_loaded_story = None
                    st.session_state.visual_assignments = {}
                    st.session_state.approved_visuals = None
                    st.session_state.visuals_approved = False
                    st.session_state.rendered_video_path = None
                try:
                    stories = list(item.get("topics") or [])
                    if stories:
                        st.session_state[topics_key] = stories
                    else:
                        with st.spinner(f'Searching news from the last 24 hours for “{keyword}”…'):
                            st.session_state[topics_key] = fetch_youtube_trend_topics(
                                keyword,
                                item["profile"],
                                limit=20,
                            )
                except (RuntimeError, ValueError, OSError) as exc:
                    st.session_state[error_key] = str(exc)
                    st.session_state[topics_key] = []
                st.rerun()

    topics = st.session_state[topics_key]
    if not topics:
        if st.session_state[selected_key] is not None:
            st.warning(
                f'No news in the last 24 hours matched “{st.session_state[keyword_key]}”. Choose another trend.'
            )
        return

    keyword = st.session_state[keyword_key]
    st.divider()
    st.markdown(
        f'<div class="section-head"><div><div class="eyebrow">NEWS PUBLISHED IN THE LAST 24 HOURS</div>'
        f'<div class="section-title">{keyword}</div></div>'
        f'<div class="section-count">{len(topics)} headlines</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Only articles published in the last 24 hours in the factory timezone are included.")

    if st.button(
        "Find up to 20 more from the last 24 hours",
        width="stretch",
        key=f"{button_prefix}more",
    ):
        with st.spinner(f'Finding more news from the last 24 hours for “{keyword}”…'):
            try:
                existing = list(topics)
                more_topics = fetch_youtube_trend_topics(
                    keyword,
                    st.session_state[profile_key],
                    more=True,
                    exclude_topics=existing,
                    limit=20,
                )
                st.session_state[topics_key] = existing + more_topics
            except (RuntimeError, ValueError, OSError) as exc:
                st.session_state[error_key] = str(exc)
        st.rerun()

    selection = _render_topic_tiles(
        topics,
        st.session_state[selected_topic_key],
        columns=2 if live else 3,
        open_state_key=open_tile_key,
        key_prefix=button_prefix,
    )
    if selection:
        index, member, members = selection
        st.session_state[topics_key][index] = replace(
            member,
            group_key=topics[index].group_key,
            group_members=members,
        )
        st.session_state[selected_topic_key] = index
        st.session_state[open_tile_key] = None
        if live:
            _live_start_story(index)
            st.session_state.live_topic_keyword = keyword
        else:
            st.session_state.test_stage = "02 · Scriptwriter"
            st.session_state.test_pipeline_notice = {
                "confirmed": "Trend-driven story confirmed",
                "next": "Moving to Script.",
            }
            st.session_state.script_data = None
            st.session_state.approved_script = None
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
            st.session_state.subtitle_data = None
            st.session_state.approved_subtitles = None
            st.session_state.renderer_previews = None
            st.session_state.rendered_video_path = None
            st.session_state.upload_qc_approved = False
            st.session_state.upload_result = None
            st.session_state.upload_qc = None
        st.rerun()

def render_longform_topic_fetcher(live: bool = False):
    from longform_topic_fetcher import fetch_longform_topics

    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    topics_key = f"{prefix}topics"
    kw_key = f"{prefix}topic_keyword"
    selected_key = f"{prefix}selected_topic"
    approved_key = f"{prefix}approved_topic"
    error_key = f"{prefix}topic_error"

    stage_title = "LONG-FORM · LIVE · 01 · STORY DESK" if live else "LONG-FORM · 01 · STORY DESK"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        '<div class="canvas-title">Find a story that can sustain long-form</div>'
        '<div class="canvas-copy">Current cricket stories are ranked for narrative depth and source coverage. No article body is fetched until a story is selected.</div></div></div>',
        unsafe_allow_html=True,
    )

    st.text_input(
        "Optional player, team, competition or subject",
        key=kw_key,
        placeholder="e.g. Chennai Super Kings ownership",
    )
    topics = list(st.session_state.get(topics_key) or [])
    left, right = st.columns(2, gap="small")
    with left:
        if st.button("Find long-form stories", type="primary", width="stretch", key=f"{k_prefix}find-stories"):
            try:
                with st.spinner("Searching current cricket coverage…"):
                    found = fetch_longform_topics(
                        limit=20,
                        keyword=st.session_state.get(kw_key, ""),
                    )
                st.session_state[topics_key] = found
                st.session_state[selected_key] = None
                st.session_state[approved_key] = None
                st.session_state[error_key] = ""
            except (RuntimeError, ValueError, OSError) as exc:
                st.session_state[error_key] = str(exc)
            st.rerun()
    with right:
        if st.button(
            "Find more stories",
            width="stretch",
            key=f"{k_prefix}find-more-stories",
            disabled=not topics,
        ):
            try:
                with st.spinner("Searching a different set of cricket queries…"):
                    found = fetch_longform_topics(
                        limit=20,
                        already_seen=topics,
                        more=True,
                        keyword=st.session_state.get(kw_key, ""),
                    )
                known_ids = {item.get("story_id") for item in topics}
                st.session_state[topics_key] = topics + [
                    item for item in found if item.get("story_id") not in known_ids
                ]
                st.session_state[error_key] = ""
                if not found:
                    st.session_state[error_key] = "No additional distinct long-form candidates were found. Try a different focus or search again later."
            except (RuntimeError, ValueError, OSError) as exc:
                st.session_state[error_key] = str(exc)
            st.rerun()

    if st.session_state.get(error_key):
        st.warning(st.session_state[error_key])
    topics = list(st.session_state.get(topics_key) or [])
    selected = st.session_state.get(selected_key)
    approved = st.session_state.get(approved_key)
    if topics:
        st.caption(f"{len(topics)} candidates · ranked by freshness, narrative signals, specificity and source coverage. These are candidates, not a guarantee that every story can sustain eight minutes.")
        for number, story in enumerate(topics, 1):
            story_id = str(story.get("story_id") or number)
            title = str(story.get("title") or "Untitled cricket story")
            with st.container(key=f"{k_prefix}topic-{story_id}"):
                st.markdown(f"**{number:02d}. {title}**")
                published = str(story.get("published_at") or "").replace("T", " ").replace("+00:00", " UTC")
                publishers = ", ".join(story.get("publishers") or [story.get("publisher") or "Unknown publisher"])
                st.caption(f"{publishers} · {published}")
                summary = str(story.get("summary") or "").strip()
                if summary:
                    st.write(summary)
                st.caption(str(story.get("ranking_reason") or "Recent cricket story; depth requires editorial review."))
                with st.expander("Source reports"):
                    for report in story.get("reports") or [{"title": title, "url": story.get("url", ""), "publisher": story.get("publisher", "")}]:
                        report_title = str(report.get("title") or title)
                        report_url = str(report.get("url") or "")
                        report_publisher = str(report.get("publisher") or "Publisher")
                        st.markdown(f"- [{report_publisher}: {report_title}]({report_url})")
                if st.button(
                    "Select this story",
                    key=f"{k_prefix}select-{story_id}",
                    type="primary" if selected and selected.get("story_id") == story_id else "secondary",
                    width="content",
                ):
                    st.session_state[selected_key] = story
                    st.session_state[approved_key] = None
                    st.rerun()
                st.divider()

    selected = st.session_state.get(selected_key)
    if selected:
        st.markdown("### Selected story")
        st.markdown(f"**{selected.get('title', 'Untitled cricket story')}**")
        st.caption(f"{selected.get('publisher', 'Unknown publisher')} · {selected.get('published_at', '')}")
        if st.button("Approve topic for Long-form", type="primary", width="stretch", key=f"{k_prefix}approve-topic"):
            st.session_state[approved_key] = dict(selected)
            if live:
                st.session_state.longform_live_stage = "02 · Scriptwriter"
            st.rerun()

    approved = st.session_state.get(approved_key)
    if approved:
        st.success("Topic approved and saved to the Long-form handoff. Scriptwriter is the next stage; it has not been generated yet.")
        st.markdown(f"[Open primary source]({approved.get('url', '')})")


def render_longform_scriptwriter(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_topic = st.session_state.get(f"{prefix}approved_topic")
    if not approved_topic:
        st.info("No topic has been approved for Long-form yet. Open **01 · Topic Fetcher** and approve a cricket story first.")
        return

    stage_title = "LONG-FORM · LIVE · 02 · SCRIPTWRITER" if live else "02 · LONG-FORM SCRIPTWRITER · 8-MINUTE DOCUMENTARY"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        f'<div class="canvas-title">{approved_topic.get("title", "Documentary Script")}</div>'
        '<div class="canvas-copy">Researched 6-Act narrative arc (~1,150 words) with scene-level entity tags, broadcast cards, and YouTube chapters.</div></div></div>',
        unsafe_allow_html=True,
    )

    with st.container(key=f"{k_prefix}script-toolbar"):
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button("Generate 8-Min Documentary Script", type="primary", width="stretch", key=f"{k_prefix}gen-script"):
                with st.spinner("Extracting multi-source evidence and structuring 6-Act documentary script..."):
                    try:
                        from longform_script_writer import LongformScriptWriter
                        script = LongformScriptWriter.write(approved_topic)
                        st.session_state[f"{prefix}script_data"] = script
                        st.session_state[f"{prefix}approved_script"] = None
                        st.session_state[f"{prefix}script_error"] = ""
                        st.rerun()
                    except Exception as exc:
                        st.session_state[f"{prefix}script_error"] = str(exc)
        with col_info:
            st.caption(f"Sources: {approved_topic.get('publisher')} + {len(approved_topic.get('reports', []))} linked reports · Lookback: 14 days")

    if st.session_state.get(f"{prefix}script_error"):
        st.error(st.session_state[f"{prefix}script_error"])

    script = st.session_state.get(f"{prefix}script_data")
    if not script:
        return

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    mins = int(script.get("estimated_duration_seconds", 0) // 60)
    secs = int(script.get("estimated_duration_seconds", 0) % 60)
    m_col1.metric("Total Spoken Words", f"{script.get('total_words', 0):,}")
    m_col2.metric("Estimated Runtime", f"{mins}m {secs:02d}s")
    m_col3.metric("Narrative Structure", f"{len(script.get('acts', []))} Acts")
    m_col4.metric("Documentary Beats", f"{script.get('scene_count', 0)} Scenes")

    with st.expander("📺 YouTube Publish Package & Chapter Timestamps", expanded=False):
        st.markdown("**Proposed Title Candidates:**")
        for idx, t in enumerate(script.get("titles", []), 1):
            st.markdown(f"- **Option {idx}:** {t}")
        st.markdown("**Description & Chapters:**")
        st.text_area("YouTube Description", script.get("seo_description", ""), height=180, key=f"{k_prefix}seo-desc")
        st.markdown(f"**Pinned Comment:** {script.get('pinned_comment', '')}")
        st.caption(f"Hashtags: {' '.join(script.get('hashtags', []))}")

    st.markdown("### 6-Act Narrative Teleprompter")
    for act in script.get("acts", []):
        act_num = act.get("act_number", 1)
        ch_title = act.get("chapter_title", f"Act {act_num}")
        act_scenes = act.get("scenes", [])
        act_words = sum(len(s.get("voiceover", "").split()) for s in act_scenes)
        with st.expander(f"ACT {act_num:02d} · {ch_title.upper()} ({act_words} words, {len(act_scenes)} beats)", expanded=True):
            for sc in act_scenes:
                sc_col1, sc_col2 = st.columns([3, 1])
                with sc_col1:
                    st.markdown(f"**Beat {sc.get('scene_number')}:** {sc.get('voiceover')}")
                with sc_col2:
                    st.caption(f"**Entity:** `{sc.get('primary_entity')}`")
                    st.caption(f"**Visual:** `{sc.get('visual_type')}` ({sc.get('card_type', 'none')})")

    st.markdown("---")
    app_col1, app_col2 = st.columns([2, 1])
    with app_col1:
        if st.button("Approve Script for Long-form", type="primary", width="stretch", key=f"{k_prefix}approve-script"):
            st.session_state[f"{prefix}approved_script"] = dict(script)
            if live:
                st.session_state.longform_live_stage = "03 · Visuals"
            else:
                st.session_state.longform_test_stage = "03 · Visuals"
            st.rerun()
    with app_col2:
        if st.session_state.get(f"{prefix}approved_script"):
            st.success("✓ Script Approved")


def render_longform_visuals(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_script = st.session_state.get(f"{prefix}approved_script")
    approved_topic = st.session_state.get(f"{prefix}approved_topic")
    if not approved_script or not approved_topic:
        st.info("No approved script found. Please approve a script in **02 · Scriptwriter** first.")
        return

    stage_title = "LONG-FORM · LIVE · 03 · AUTOMATED VISUALS" if live else "03 · AUTOMATED VISUALS · 16:9 WIDESCREEN ENGINE"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        f'<div class="canvas-title">Visual Matcher & Card Studio</div>'
        '<div class="canvas-copy">100% automated visual sourcing, entity verification, and broadcast card rendering. Zero manual QC needed.</div></div></div>',
        unsafe_allow_html=True,
    )

    with st.container(key=f"{k_prefix}visuals-toolbar"):
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button("Run Automated Visual Engine", type="primary", width="stretch", key=f"{k_prefix}run-visuals"):
                with st.spinner("Searching open sources, verifying entities, and rendering 16:9 broadcast cards..."):
                    try:
                        from longform_visuals import LongformVisualMatcher
                        vis_result = LongformVisualMatcher.match_and_collect(approved_script, approved_topic)
                        st.session_state[f"{prefix}visuals_data"] = vis_result
                        st.session_state[f"{prefix}visuals_error"] = ""
                        st.rerun()
                    except Exception as exc:
                        st.session_state[f"{prefix}visuals_error"] = str(exc)
        with col_info:
            st.caption("Visual pipeline queries Commons, Wikipedia, DuckDuckGo & Flickr, and builds 1920×1080 cards.")

    if st.session_state.get(f"{prefix}visuals_error"):
        st.error(st.session_state[f"{prefix}visuals_error"])

    v_data = st.session_state.get(f"{prefix}visuals_data")
    if not v_data:
        return

    v_col1, v_col2, v_col3, v_col4 = st.columns(4)
    v_col1.metric("Documentary Scenes", v_data.get("total_scenes", 0))
    v_col2.metric("Open Asset Pool", v_data.get("pool_size", 0))
    v_col3.metric("Broadcast Cards", v_data.get("cards_count", 0))
    v_col4.metric("Ken Burns Photos", v_data.get("photos_count", 0))

    st.markdown("### Widescreen 16:9 Documentary Storyboard")
    scenes_vis = v_data.get("scenes_visuals", [])
    for i in range(0, len(scenes_vis), 3):
        row_scenes = scenes_vis[i:i+3]
        cols = st.columns(3)
        for c, s in zip(cols, row_scenes):
            with c:
                with st.container(border=True):
                    st.caption(f"**Scene {s.get('scene_number')}** · Act {s.get('act_number')} ({s.get('visual_type')})")
                    if s.get("image_bytes"):
                        st.image(s["image_bytes"], use_container_width=True)
                    st.caption(f"Entity: `{s.get('primary_entity')}` · Source: {s.get('image_source')}")
                    st.text(s.get("voiceover", "")[:90] + "…")

    st.markdown("---")
    app_col1, app_col2 = st.columns([2, 1])
    with app_col1:
        if st.button("Proceed to Audio · 04", type="primary", width="stretch", key=f"{k_prefix}proceed-audio"):
            st.session_state[f"{prefix}approved_visuals"] = dict(v_data)
            if live:
                st.session_state.longform_live_stage = "04 · Audio"
            else:
                st.session_state.longform_test_stage = "04 · Audio"
            st.rerun()
    with app_col2:
        if st.session_state.get(f"{prefix}approved_visuals"):
            st.success("✓ Visuals Ready")


def render_longform_audio(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_script = st.session_state.get(f"{prefix}approved_script")
    if not approved_script:
        st.info("No approved script found. Please approve a script in **02 · Scriptwriter** first.")
        return

    stage_title = "LONG-FORM · LIVE · 04 · AUDIO ENGINE" if live else "04 · LONG-FORM AUDIO ENGINE · CHATTERBOX TURBO"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        '<div class="canvas-title">Voice Cloning & Paced Narration</div>'
        '<div class="canvas-copy">Script-aware delivery cues, reusable local voice conditioning, atmospheric act pauses, and cached repeat renders.</div></div></div>',
        unsafe_allow_html=True,
    )

    from pathlib import Path
    from audio import CHATTERBOX_VOICE_REFERENCES
    voice_label = st.selectbox(
        "Narrator voice",
        list(CHATTERBOX_VOICE_REFERENCES),
        key=f"{prefix}audio_voice_reference",
    )
    ref_file = CHATTERBOX_VOICE_REFERENCES[voice_label]
    ref_ready = ref_file.is_file()
    ref_status = (
        f"🎙️ Using `{ref_file.name}` voice conditioning"
        if ref_ready
        else f"Missing `{ref_file.name}` — place it in the factory root"
    )
    st.caption(f"{voice_label}: " + ("reference ready" if ref_ready else "reference file missing"))

    st.markdown(
        f'<div style="background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin: 10px 0 14px 0;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
        f'<span style="font-size:0.65rem; font-weight:800; letter-spacing:0.08em; color:var(--accent); text-transform:uppercase;">AUDIO ENGINE · CHATTERBOX TURBO TTS</span>'
        f'<span style="font-size:0.72rem; font-weight:700; color:var(--muted);">{ref_status}</span>'
        f'</div>'
        f'<div style="font-size:0.88rem; font-weight:800; color:var(--ink);">Documentary Narration Suite (6 Acts · ~8 Min)</div>'
        f'<div style="font-size:0.72rem; color:var(--subtle); margin-top:2px;">Script-led narration · Shared Chatterbox model · Cached master and scene audio</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.container(key=f"{k_prefix}audio-toolbar"):
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button("Synthesize Full Narration", type="primary", width="stretch", key=f"{k_prefix}gen-audio", disabled=not ref_ready):
                with st.spinner("Synthesizing ~8-minute documentary narration with Chatterbox Turbo..."):
                    try:
                        from longform_audio import LongformAudioEngine
                        out_dir = Path("output/live/longform_audio") if live else Path("output/longform_audio")
                        audio_res = LongformAudioEngine.generate(
                            approved_script,
                            reference_audio=ref_file,
                            output_dir=out_dir,
                        )
                        st.session_state[f"{prefix}audio_data"] = audio_res
                        st.session_state[f"{prefix}audio_error"] = ""
                        st.rerun()
                    except Exception as exc:
                        st.session_state[f"{prefix}audio_error"] = str(exc)
        with col_info:
            st.caption("Narration is rendered scene-by-scene with 0.8s act pauses and breath gaps, generating full master audio + word timings.")

    if st.session_state.get(f"{prefix}audio_error"):
        st.error(st.session_state[f"{prefix}audio_error"])

    audio_data = st.session_state.get(f"{prefix}audio_data")
    if not audio_data:
        return

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    tot_s = audio_data.get("total_duration", 0)
    mins = int(tot_s // 60)
    secs = int(tot_s % 60)
    m_col1.metric("Master Duration", f"{mins}m {secs:02d}s")
    m_col2.metric("Narrated Scenes", len(audio_data.get("scenes", [])))
    m_col3.metric("Engine", audio_data.get("engine", "Chatterbox-Turbo"))
    m_col4.metric("Reference Voice", "Conditioned" if "audio_reference" in audio_data.get("reference", "") else "Built-in")

    st.markdown("### Master Audio Track")
    master_path = audio_data.get("master_path")
    if master_path and Path(master_path).exists():
        st.audio(master_path)

    with st.expander("🎧 Scene-by-Scene Audio Breakdown & Timings", expanded=False):
        for sc in audio_data.get("scenes", []):
            sc_c1, sc_c2 = st.columns([1, 2])
            with sc_c1:
                st.caption(f"**Scene {sc.get('scene')}** (Act {sc.get('act')}) · {sc.get('duration')}s")
                p = sc.get("path")
                if p and Path(p).exists():
                    st.audio(p)
            with sc_c2:
                timings = sc.get("timings", [])
                st.caption(f"Word timings ({len(timings)} words):")
                preview_words = " ".join(t.get("word", "") for t in timings[:15])
                if len(timings) > 15:
                    preview_words += "…"
                st.text(preview_words)

    st.markdown("---")
    app_col1, app_col2 = st.columns([2, 1])
    with app_col1:
        if st.button("Approve Audio for Long-form", type="primary", width="stretch", key=f"{k_prefix}approve-audio"):
            from longform_audio import LongformAudioEngine
            st.session_state[f"{prefix}approved_audio"] = LongformAudioEngine.approve_audio(audio_data)
            if live:
                st.session_state.longform_live_stage = "05 · Subtitles"
            else:
                st.session_state.longform_test_stage = "05 · Subtitles"
            st.rerun()
    with app_col2:
        if st.session_state.get(f"{prefix}approved_audio"):
            st.success("✓ Audio Approved")


def render_longform_subtitles(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_script = st.session_state.get(f"{prefix}approved_script")
    approved_audio = st.session_state.get(f"{prefix}approved_audio")
    if not approved_script or not approved_audio:
        st.info("Approve the Scriptwriter (02) and Audio (04) stages first.")
        return

    stage_title = "LONG-FORM · LIVE · 05 · SUBTITLES" if live else "05 · LONG-FORM SUBTITLES · BROADCAST LOWER-THIRDS"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        '<div class="canvas-title">Documentary Subtitles & Act Billboards</div>'
        '<div class="canvas-copy">Generates clean 16:9 lower-third subtitles (Netflix/BBC style) and cinematic Act chapter billboards.</div></div></div>',
        unsafe_allow_html=True,
    )

    with st.container(key=f"{k_prefix}subs-toolbar"):
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button("Generate Broadcast Subtitles", type="primary", width="stretch", key=f"{k_prefix}gen-subs"):
                with st.spinner("Aligning word timings and building broadcast lower-third cues..."):
                    try:
                        from longform_subtitles import LongformSubtitleEngine
                        subs = LongformSubtitleEngine.generate(approved_script, approved_audio)
                        st.session_state[f"{prefix}subtitles_data"] = subs
                        st.session_state[f"{prefix}subtitles_error"] = ""
                        st.rerun()
                    except Exception as exc:
                        st.session_state[f"{prefix}subtitles_error"] = str(exc)
        with col_info:
            st.caption("Groups speech into natural human reading phrases (5–8 words) and adds chapter title overlays.")

    if st.session_state.get(f"{prefix}subtitles_error"):
        st.error(st.session_state[f"{prefix}subtitles_error"])

    sub_data = st.session_state.get(f"{prefix}subtitles_data")
    if not sub_data:
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Subtitle Cues", sub_data.get("cue_count", 0))
    m2.metric("Act Billboards", sub_data.get("acts_count", 0))
    m3.metric("Style", "Lower-Third Broadcast")
    m4.metric("Format", "16:9 Widescreen")

    with st.expander("📺 Cinematic Act Title Billboards", expanded=True):
        for bb in sub_data.get("act_billboards", []):
            st.markdown(f"**ACT {bb.get('act_number'):02d}:** `{bb.get('title')}` (Timestamp: {bb.get('start_time')}s)")

    with st.expander("📝 Lower-Third Subtitle Cue Preview (First 20 Phrases)", expanded=False):
        cues_preview = sub_data.get("cues", [])[:20]
        for c in cues_preview:
            st.text(f"[{c.get('start')}s - {c.get('end')}s] {c.get('text')}")

    st.markdown("---")
    app_col1, app_col2 = st.columns([2, 1])
    with app_col1:
        if st.button("Approve Subtitles for Long-form", type="primary", width="stretch", key=f"{k_prefix}approve-subs"):
            from longform_subtitles import LongformSubtitleEngine
            st.session_state[f"{prefix}approved_subtitles"] = LongformSubtitleEngine.approve(sub_data)
            if live:
                st.session_state.longform_live_stage = "06 · Renderer"
            else:
                st.session_state.longform_test_stage = "06 · Renderer"
            st.rerun()
    with app_col2:
        if st.session_state.get(f"{prefix}approved_subtitles"):
            st.success("✓ Subtitles Approved")


def render_longform_renderer(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_script = st.session_state.get(f"{prefix}approved_script")
    approved_audio = st.session_state.get(f"{prefix}approved_audio")
    approved_visuals = st.session_state.get(f"{prefix}approved_visuals")
    approved_subs = st.session_state.get(f"{prefix}approved_subtitles")

    missing = []
    if not approved_script: missing.append("02 Scriptwriter")
    if not approved_visuals: missing.append("03 Visuals")
    if not approved_audio: missing.append("04 Audio")
    if not approved_subs: missing.append("05 Subtitles")

    stage_title = "LONG-FORM · LIVE · 06 · RENDERER" if live else "06 · LONG-FORM RENDERER · 16:9 WIDESCREEN ENGINE"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        '<div class="canvas-title">Broadcast Documentary Rendering</div>'
        '<div class="canvas-copy">Assembles 1920×1080 30FPS video essay combining broadcast cards, Ken Burns photos, Act title billboards, lower-third subtitles, and master narration.</div></div></div>',
        unsafe_allow_html=True,
    )

    if missing:
        st.warning(f"Complete and approve earlier stages first. Missing: {', '.join(missing)}")
        return

    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        render_mode = st.pills("Render Mode", ["Fast Preview Clip (15s)", "Full Documentary (~8 Min)"], default="Fast Preview Clip (15s)", key=f"{k_prefix}render_mode") or "Fast Preview Clip (15s)"
    with col_cfg2:
        audio_profile = st.pills("Audio Profile", ["Clean Studio Master (Loudnorm)", "Dynamic Soundscape Bed"], default="Clean Studio Master (Loudnorm)", key=f"{k_prefix}audio_profile") or "Clean Studio Master (Loudnorm)"

    with st.container(key=f"{k_prefix}render-toolbar"):
        if st.button("Render 16:9 Documentary Video", type="primary", width="stretch", key=f"{k_prefix}run-render"):
            max_sec = 15.0 if "Preview" in render_mode else None
            out_dir = Path("output/live/longform_rendered") if live else Path("output/longform_rendered")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "documentary_master.mp4"
            with st.spinner("Rendering 1920×1080 30FPS broadcast documentary video..."):
                try:
                    from longform_renderer import LongformRenderer
                    rendered = LongformRenderer.render_video(
                        approved_script=approved_script,
                        approved_audio=approved_audio,
                        approved_visuals=approved_visuals,
                        subtitle_data=approved_subs,
                        output_path=out_file,
                        max_duration_seconds=max_sec,
                    )
                    st.session_state[f"{prefix}rendered_video"] = str(rendered)
                    st.session_state[f"{prefix}render_error"] = ""
                    st.rerun()
                except Exception as exc:
                    st.session_state[f"{prefix}render_error"] = str(exc)

    if st.session_state.get(f"{prefix}render_error"):
        st.error(st.session_state[f"{prefix}render_error"])

    vid_path = st.session_state.get(f"{prefix}rendered_video")
    if vid_path and Path(vid_path).exists():
        st.markdown("### Master 16:9 Video Player")
        st.video(vid_path)

        st.markdown("---")
        app_col1, app_col2 = st.columns([2, 1])
        with app_col1:
            if st.button("Approve Video for Long-form", type="primary", width="stretch", key=f"{k_prefix}approve-video"):
                st.session_state[f"{prefix}approved_video"] = vid_path
                if live:
                    st.session_state.longform_live_stage = "07 · Upload QC"
                else:
                    st.session_state.longform_test_stage = "07 · Upload QC"
                st.rerun()
        with app_col2:
            if st.session_state.get(f"{prefix}approved_video"):
                st.success("✓ Video Approved")


def render_longform_upload_qc(live: bool = False):
    prefix = "longform_live_" if live else "longform_"
    k_prefix = "longform-live-" if live else "longform-"
    approved_script = st.session_state.get(f"{prefix}approved_script")
    approved_topic = st.session_state.get(f"{prefix}approved_topic")
    approved_video = st.session_state.get(f"{prefix}approved_video")

    if not approved_script or not approved_topic or not approved_video:
        st.info("Render and approve the documentary video (06) first.")
        return

    from longform_uploader import LongformUploader
    package = LongformUploader.prepare_package(approved_script, approved_topic, approved_video)

    stage_title = "LONG-FORM · LIVE · 07 · PUBLISH PACKAGE" if live else "07 · YOUTUBE DOCUMENTARY PUBLISH PACKAGE"
    st.markdown(
        f'<div class="canvas-head"><div><div class="eyebrow">{stage_title}</div>'
        '<div class="canvas-title">Metadata Packaging & Upload Review</div>'
        '<div class="canvas-copy">Monetization-compliant packaging: timestamped chapters, research bibliography, and private review gate.</div></div></div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown("### Video Metadata Package")
        selected_title = st.selectbox("Video Title Candidate", package.get("title_candidates") or [package.get("title")], key=f"{k_prefix}upload_title")
        desc_text = st.text_area("YouTube Description (with Chapters & Sources)", package.get("description", ""), height=240, key=f"{k_prefix}upload_desc")
        pinned_c = st.text_input("Pinned Discussion Prompt", package.get("pinned_comment", ""), key=f"{k_prefix}upload_comment")

        privacy = st.pills("Upload Privacy Status", ["private", "unlisted", "public"], default="private", key=f"{k_prefix}privacy_status") or "private"

        if st.button("Upload Documentary to YouTube", type="primary", width="stretch", key=f"{k_prefix}upload-btn"):
            upload_pkg = dict(package)
            upload_pkg["title"] = selected_title
            upload_pkg["description"] = desc_text
            upload_pkg["pinned_comment"] = pinned_c
            with st.spinner("Connecting to YouTube API and uploading broadcast documentary..."):
                try:
                    res = LongformUploader.upload_to_youtube(upload_pkg, privacy_status=privacy)
                    st.session_state[f"{prefix}upload_result"] = res
                    st.session_state[f"{prefix}upload_error"] = ""
                    st.rerun()
                except Exception as exc:
                    st.session_state[f"{prefix}upload_error"] = str(exc)

        if st.session_state.get(f"{prefix}upload_error"):
            st.error(st.session_state[f"{prefix}upload_error"])

        if st.session_state.get(f"{prefix}upload_result"):
            up = st.session_state[f"{prefix}upload_result"]
            st.success(f"✓ Uploaded successfully! Video ID: `{up.get('video_id')}` (Status: {up.get('privacy_status')})")
            if up.get("video_url"):
                st.markdown(f"[Watch on YouTube]({up.get('video_url')})")

    with right:
        st.markdown("### Master Video Verification")
        st.video(approved_video)
        st.caption(f"File size: {round(Path(approved_video).stat().st_size / (1024*1024), 2)} MB · Resolution: 1920×1080 (16:9)")


def render_longform_test():
    stage_names = ["Topic Fetcher", "Scriptwriter", "Visuals", "Audio", "Subtitles", "Renderer", "Upload QC"]
    stage_idx = 0
    if st.session_state.longform_test_stage == "02 · Scriptwriter":
        stage_idx = 1
    elif st.session_state.longform_test_stage == "03 · Visuals":
        stage_idx = 2
    elif st.session_state.longform_test_stage == "04 · Audio":
        stage_idx = 3
    elif st.session_state.longform_test_stage == "05 · Subtitles":
        stage_idx = 4
    elif st.session_state.longform_test_stage == "06 · Renderer":
        stage_idx = 5
    elif st.session_state.longform_test_stage == "07 · Upload QC":
        stage_idx = 6
    _render_pipeline_progress(stage_names, stage_idx)

    if st.session_state.longform_test_stage == "01 · Topic Fetcher":
        render_longform_topic_fetcher(live=False)
    elif st.session_state.longform_test_stage == "02 · Scriptwriter":
        render_longform_scriptwriter(live=False)
    elif st.session_state.longform_test_stage == "03 · Visuals":
        render_longform_visuals(live=False)
    elif st.session_state.longform_test_stage == "04 · Audio":
        render_longform_audio(live=False)
    elif st.session_state.longform_test_stage == "05 · Subtitles":
        render_longform_subtitles(live=False)
    elif st.session_state.longform_test_stage == "06 · Renderer":
        render_longform_renderer(live=False)
    elif st.session_state.longform_test_stage == "07 · Upload QC":
        render_longform_upload_qc(live=False)


def render_longform_live():
    stage_names = ["Topic Fetcher", "Scriptwriter", "Visuals", "Audio", "Subtitles", "Renderer", "Upload QC"]
    stage = st.session_state.get("longform_live_stage") or "01 · Topic Fetcher"
    stage_idx = 0
    if stage == "02 · Scriptwriter":
        stage_idx = 1
    elif stage == "03 · Visuals":
        stage_idx = 2
    elif stage == "04 · Audio":
        stage_idx = 3
    elif stage == "05 · Subtitles":
        stage_idx = 4
    elif stage == "06 · Renderer":
        stage_idx = 5
    elif stage == "07 · Upload QC":
        stage_idx = 6

    upload_complete = stage_idx == 6 and bool(st.session_state.get("longform_live_upload_result"))
    _render_pipeline_progress(stage_names, stage_idx, complete_last=upload_complete)

    left, right = st.columns([1.4, .45], gap="large")
    with left:
        st.markdown(
            '<div class="live-product-head">'
            '<div><div class="eyebrow">LONG-FORM · LIVE PRODUCTION</div>'
            '<div class="live-product-title">8-Minute Documentary Studio</div>'
            '<div class="hero-subtitle">Broadcast 16:9 documentary production line with Chatterbox Turbo and monetization packaging.</div></div>'
            '<div class="live-status"><span></span> Live Production Active</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with right:
        controls = st.columns(2, gap="small")
        with controls[0]:
            if st.button("New Doc", key="longform-live-new", width="stretch"):
                _longform_live_reset_downstream()
                st.session_state.longform_live_stage = "01 · Topic Fetcher"
                st.rerun()
        with controls[1]:
            if st.button("Home", key="longform-live-home", width="stretch"):
                st.session_state.app_mode = "home"
                st.rerun()

    if stage == "01 · Topic Fetcher":
        render_longform_topic_fetcher(live=True)
    elif stage == "02 · Scriptwriter":
        render_longform_scriptwriter(live=True)
    elif stage == "03 · Visuals":
        render_longform_visuals(live=True)
    elif stage == "04 · Audio":
        render_longform_audio(live=True)
    elif stage == "05 · Subtitles":
        render_longform_subtitles(live=True)
    elif stage == "06 · Renderer":
        render_longform_renderer(live=True)
    elif stage == "07 · Upload QC":
        render_longform_upload_qc(live=True)


def render_otd_topic_fetcher():
    from datetime import date as dt_date
    from topic_fetcher import fetch_otd_topics

    if "otd_topics" not in st.session_state:
        st.session_state.otd_topics = []
    if "otd_selected" not in st.session_state:
        st.session_state.otd_selected = None
    if "otd_sport" not in st.session_state:
        st.session_state.otd_sport = "All Sports"
    if "otd_date" not in st.session_state:
        st.session_state.otd_date = dt_date.today()

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">01 · ON THIS DAY · HISTORICAL PRODUCTION</div>'
        '<div class="canvas-title">On This Day — Sports Milestones</div>'
        '<div class="canvas-copy">Select a verified historical sports milestone or anniversary from this calendar date.</div></div></div>',
        unsafe_allow_html=True,
    )

    with st.container(key="otd-toolbar"):
        col_date, col_sport, col_fetch, col_cnt = st.columns([1.2, 1.4, 1.2, 1.2], gap="small")
        with col_date:
            selected_date = st.date_input(
                "Calendar Date",
                value=st.session_state.otd_date,
                key="test-otd-date",
                label_visibility="collapsed",
            )
            st.session_state.otd_date = selected_date
        with col_sport:
            sport_choice = st.pills(
                "Sport",
                ["All Sports", "Cricket", "Other Sports"],
                default=st.session_state.otd_sport,
                key="test-otd-sport-choice",
                label_visibility="collapsed",
            ) or st.session_state.otd_sport
            st.session_state.otd_sport = sport_choice
        with col_fetch:
            fetch_clicked = st.button("Fetch OTD stories", type="primary", width="stretch", key="test-otd-fetch")
        with col_cnt:
            count = len(st.session_state.otd_topics)
            st.markdown(
                f'<div style="text-align:right;padding:.65rem .15rem;"><span class="badge">{count} stories</span></div>',
                unsafe_allow_html=True,
            )

    if fetch_clicked:
        sport_param = "cricket" if sport_choice == "Cricket" else "other" if sport_choice == "Other Sports" else "all"
        with st.spinner(f"Fetching historical sports milestones for {selected_date.strftime('%B %d')}…"):
            try:
                st.session_state.otd_topics = fetch_otd_topics(
                    date=selected_date,
                    sport=sport_param,
                    limit=20,
                )
            except Exception as exc:
                st.error(f"Error fetching historical stories: {exc}")
                st.session_state.otd_topics = []
        st.session_state.otd_selected = None
        st.session_state.selected_topic = None
        st.rerun()

    topics = st.session_state.otd_topics
    if not topics:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-title">No historical milestones loaded</div>'
            '<div class="empty-state-copy">Select a calendar date and fetch verified historical sports events to begin.</div></div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="section-head"><div><div class="eyebrow">HISTORICAL STORIES · {selected_date.strftime("%B %d").upper()}</div>'
        f'<div class="section-title">Verified anniversaries & milestones</div></div>'
        f'<div class="section-count">{len(topics)} available</div></div>',
        unsafe_allow_html=True,
    )

    for index, topic in enumerate(topics):
        left, right = st.columns([2.2, .4], gap="small")
        with left:
            st.markdown(
                f'<div class="topic-title">{topic.title}</div>'
                f'<div class="topic-meta">{topic.source}</div>',
                unsafe_allow_html=True,
            )
            if topic.description and topic.description != topic.title:
                st.caption(topic.description)
        with right:
            if st.button("Use story →", key=f"test-otd-use-{index}", width="stretch", type="primary" if index == 0 else "secondary"):
                st.session_state.topics = [topic]
                st.session_state.selected_topic = 0
                st.session_state.topic_desk_profile = "otd"
                st.session_state.test_pipeline_notice = {
                    "confirmed": "On This Day story confirmed",
                    "next": "Moving to Script.",
                }
                st.session_state.script_data = None
                st.session_state.approved_script = None
                st.session_state.audio_data = None
                st.session_state.approved_audio = None
                st.session_state.subtitle_data = None
                st.session_state.approved_subtitles = None
                st.session_state.visual_result = None
                st.session_state.visual_loaded_story = None
                st.session_state.visual_assignments = {}
                st.session_state.approved_visuals = None
                st.session_state.visuals_approved = False
                st.session_state.rendered_video_path = None
                st.session_state.upload_qc_approved = False
                st.session_state.upload_result = None
                st.session_state.upload_qc = None
                st.session_state.test_stage = "02 · Scriptwriter"
                st.rerun()


def render_topic_fetcher():
    desk_icons = {
        "Cricket India / Asia": "🏏",
        "Cricket Global": "🌐",
        "Niche Sports": "🏎️",
    }
    cur_desk = st.session_state.get("topic_desk", "Cricket India / Asia")
    icon = desk_icons.get(cur_desk, "📡")
    st.markdown(
        f'<div class="radar-banner">'
        f'<div>'
        f'<div style="font-size:0.65rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:var(--primary);">01 · STORY RADAR & DISCOVERY</div>'
        f'<div style="font-size:1.45rem; font-weight:850; letter-spacing:-0.03em; margin:2px 0 4px; color:var(--ink);">{icon} {cur_desk}</div>'
        f'<div style="font-size:0.8rem; color:var(--muted);">Autonomous multi-source story discovery and cluster deduplication.</div>'
        f'</div>'
        f'<div class="radar-chip">⚡ 72H LOOKBACK · ZERO COST</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    desk = st.pills(
        "Desk",
        list(profiles),
        default="Cricket India / Asia",
        key="topic_desk",
        label_visibility="collapsed",
    ) or "Cricket India / Asia"
    previous_desk = st.session_state.get("topic_desk_profile")
    if previous_desk and previous_desk != profiles[desk]:
        for key, value in {
            "topics": [], "topic_keyword": "", "selected_topic": None, "topic_open_tile": None, "script_data": None, "approved_script": None,
            "audio_data": None, "approved_audio": None, "subtitle_data": None, "approved_subtitles": None,
            "visual_result": None, "visual_loaded_story": None, "renderer_previews": None,
            "rendered_video_path": None, "upload_qc_approved": False, "upload_result": None,
            "upload_qc": None, "manual_visual_result": None, "real_image_result": None,
            "ai_image_result": None, "visual_crops": {},
        }.items():
            st.session_state[key] = value
    st.session_state.topic_desk_profile = profiles[desk]

    profile = profiles[desk]
    with st.container(key="topic-toolbar"):
        a, b, cnt = st.columns([1, .72, 1.6], gap="small")
        with a:
            fetch = st.button("Fetch current stories", type="primary", width="stretch")
        with b:
            more = st.button("Find 20 more", width="stretch")
        with cnt:
            topics = st.session_state.topics
            headline_count = sum(
                len(topic.group_members) if topic.group_members else 1
                for topic in topics
            )
            st.markdown(
                f'<div style="text-align:right;padding:.65rem .15rem;"><span class="badge">{len(topics)} tiles · {headline_count} headlines</span></div>',
                unsafe_allow_html=True,
            )

    keyword_search = False
    if profile in {"cricket_india_asia", "cricket_global"}:
        search_col, button_col = st.columns([3, 1], gap="small")
        with search_col:
            keyword = st.text_input(
                "Search by player, team, event or keyword",
                placeholder="e.g. Babar Azam, Asia Cup, record",
                key="topic_keyword",
                label_visibility="collapsed",
            ).strip()
        with button_col:
            keyword_search = st.button(
                "Search keyword",
                width="stretch",
                key="topic-keyword-search",
            )
    else:
        keyword = ""

    if fetch or more or keyword_search:
        if keyword_search and not keyword:
            st.warning("Enter a keyword first.")
        else:
            with st.spinner(
                "Searching targeted cricket stories…" if keyword_search
                else "Fetching current sports stories…"
            ):
                try:
                    existing_topics = list(st.session_state.topics)
                    from topic_fetcher import fetch_topics
                    new_topics = fetch_topics(
                        profile,
                        more=more and not keyword_search,
                        exclude_topics=existing_topics,
                        limit=20,
                        keyword=keyword if keyword_search else None,
                    )
                    if keyword_search:
                        keyword_members = tuple(
                            member
                            for topic in new_topics
                            for member in (topic.group_members or (topic,))
                        )
                        if keyword_members:
                            keyword_tile = replace(
                                keyword_members[0],
                                group_key=f"keyword:{keyword}",
                                group_members=keyword_members,
                            )
                            st.session_state.topics = existing_topics + [keyword_tile]
                        else:
                            st.session_state.topics = existing_topics
                    elif more:
                        st.session_state.topics = existing_topics + new_topics
                    else:
                        st.session_state.topics = new_topics
                except Exception as exc:
                    st.error(f"Failed to fetch stories: {exc}")

            st.session_state.selected_topic = None
            st.session_state.topic_open_tile = None
            st.session_state.script_data = None
            st.session_state.approved_script = None
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
            st.session_state.subtitle_data = None
            st.session_state.approved_subtitles = None
            st.session_state.visual_result = None
            st.session_state.visual_loaded_story = None
            st.session_state.visual_deleted = set()
            st.session_state.visual_assignments = {}
            st.session_state.approved_visuals = None
            st.session_state.visuals_approved = False

    topics = st.session_state.topics
    if not topics:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-title">No stories loaded</div><div class="empty-state-copy">Fetch the current story pool to start.</div></div>',
            unsafe_allow_html=True,
        )
        return

    selection = _render_topic_tiles(
        topics,
        st.session_state.selected_topic,
        columns=3,
        open_state_key="topic_open_tile",
        key_prefix="",
    )
    if selection:
        index, member, members = selection
        st.session_state.topics[index] = replace(
            member,
            group_key=topics[index].group_key,
            group_members=members,
        )
        st.session_state.selected_topic = index
        st.session_state.topic_open_tile = None
        st.session_state.test_stage = "02 · Scriptwriter"
        st.session_state.test_pipeline_notice = {
            "confirmed": "Story confirmed",
            "next": "Moving to Script.",
        }
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None
        st.session_state.renderer_previews = None
        st.session_state.rendered_video_path = None
        st.session_state.upload_qc_approved = False
        st.session_state.upload_result = None
        st.session_state.upload_qc = None
        st.session_state.upload_title_options = []
        st.session_state.upload_title_choice = 0
        st.session_state.upload_description = ""
        st.session_state.upload_hashtags = ""
        st.session_state.upload_comment = ""
        st.session_state.manual_visual_result = None
        st.session_state.real_image_result = None
        st.session_state.ai_image_result = None
        st.session_state.visual_result = None
        st.session_state.visual_loaded_story = None
        st.session_state.visual_crops = {}
        st.session_state.visual_deleted = set()
        st.session_state.visual_assignments = {}
        st.session_state.approved_visuals = None
        st.session_state.visuals_approved = False
        st.rerun()

    if st.session_state.selected_topic is not None:
        index = st.session_state.selected_topic
        if 0 <= index < len(topics):
            topic = topics[index]
            with st.container(key="selected-story-card"):
                left, right = st.columns([1.7, .45], gap="medium")
                with left:
                    st.markdown('<div class="eyebrow">SELECTED</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="selected-story-title">{topic.title}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="topic-meta">{topic.source or "Sports desk"} · {topic.published_at:%d %b}</div>', unsafe_allow_html=True)
                    if topic.description:
                        with st.expander("Story details", expanded=False):
                            st.write(topic.description)
                with right:
                    if topic.url:
                        st.link_button("Source ↗", topic.url, width="stretch")

def render_scriptwriter():
    from script_writer import apply_script_edits

    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first.")
        return
    selected_index=st.session_state.selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.topics):
        st.info("Select a story in the Story Desk first.")
        return
    topic=st.session_state.topics[selected_index]
    story_key = _live_story_key(topic)
    headline_toggle_key = f"test-headline-enabled-{story_key}"
    headline_text_key = f"test-script-headline-{story_key}"

    st.markdown(
        f'<div class="radar-banner">'
        f'<div>'
        f'<div style="font-size:0.65rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:var(--primary);">02 · BROADCAST PROMPTER & SCRIPT STUDIO</div>'
        f'<div style="font-size:1.35rem; font-weight:850; letter-spacing:-0.03em; margin:2px 0 4px; color:var(--ink);">{topic.title}</div>'
        f'<div style="font-size:0.78rem; color:var(--muted);">Continuous 20–30s broadcast news article · First slide &lt; 14 words</div>'
        f'</div>'
        f'<div class="radar-chip">PRO STUDIO ENGINE</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    universal_story = (
        st.session_state.get("test_production_line") in {"youtube_trends", "otd"}
        or st.session_state.get("topic_desk_profile") in {"niche_sports", "otd"}
    )
    search_query = (
        st.session_state.get("youtube_trend_search_query")
        if st.session_state.get("test_production_line") == "youtube_trends"
        else None
    )

    top_left, top_right=st.columns([1,.72],gap="medium")
    with top_left:
        language=st.pills("Language",["English","Hindi","Telugu"],default="English",key="script_language",label_visibility="collapsed") or "English"

    if st.session_state.get("test_universal_angle_story_key") != story_key:
        st.session_state.test_universal_angles = None
        st.session_state.test_universal_angle_source = None
        st.session_state.test_universal_angle_selected = 0
        st.session_state.test_universal_angle_custom = ""
        st.session_state.test_universal_angle_story_key = story_key

    if not st.session_state.get("test_universal_angles"):
        with top_right:
            if st.button("Generate script",type="primary",width="stretch",key="test-generate-script"):
                try:
                    with st.spinner("Reading the full story and finding the strongest angles…"):
                        from script_writer import ScriptWriter
                        desk_p = st.session_state.get("topic_desk_profile") or ("youtube_trends" if universal_story else "cricket_india_asia")
                        angle_result = ScriptWriter.suggest_angles(
                            _story_payload(topic),
                            profile=desk_p,
                            language=language.casefold(),
                            search_query=search_query or "",
                        )
                    st.session_state.test_universal_angles = angle_result["angles"]
                    st.session_state.test_universal_angle_source = angle_result["source_evidence"]
                    st.session_state.test_universal_angle_selected = 0
                    st.session_state.test_universal_angle_custom = ""
                    st.session_state.test_universal_angle_story_key = story_key
                except Exception as exc:
                    st.error(f"Scriptwriter failed: {type(exc).__name__}: {exc}")
    else:
        selected_angle = _render_universal_angle_picker(
            st.session_state.test_universal_angles,
            selected_key="test_universal_angle_selected",
            custom_key="test_universal_angle_custom",
            button_prefix=f"test-{story_key}",
        )
        if selected_angle:
            for key in (
                headline_toggle_key,
                headline_text_key,
                *(f"script-slide-{story_key}-{index}" for index in range(1, 7)),
            ):
                st.session_state.pop(key, None)
            try:
                with st.spinner("Writing the Short from the selected angle…"):
                    st.session_state.script_data = _script_for_topic(
                        topic,
                        st.session_state.get("topic_desk_profile") or "",
                        language.casefold(),
                        universal=universal_story,
                        angle=selected_angle,
                        research_source=st.session_state.test_universal_angle_source,
                        search_query=search_query,
                    )
            except Exception as exc:
                st.error(f"Scriptwriter failed: {type(exc).__name__}: {exc}")
            else:
                st.session_state.approved_script=None
                st.session_state.audio_data=None
                st.session_state.approved_audio=None
                st.session_state.subtitle_data=None
                st.session_state.approved_subtitles=None
                st.session_state.renderer_previews=None
                st.session_state.rendered_video_path=None
                st.session_state.upload_qc_approved=False
                st.session_state.upload_result=None
                st.session_state.upload_qc=None
                st.rerun()


    script=st.session_state.script_data
    if not script:
        return

    if str(script.get("story_angle") or "").strip():
        st.caption("Selected story angle: " + str(script.get("story_angle") or "").strip())
        if st.button(
            "Change angle and regenerate",
            width="stretch",
            key=f"test-change-angle-{story_key}",
        ):
            st.session_state.script_data = None
            st.session_state.approved_script = None
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
            st.session_state.subtitle_data = None
            st.session_state.approved_subtitles = None
            st.session_state.renderer_previews = None
            st.session_state.rendered_video_path = None
            st.session_state.upload_qc_approved = False
            st.session_state.upload_result = None
            st.session_state.upload_qc = None
            st.rerun()

    left,right=st.columns([1.5,.55],gap="large")
    with left:
        with st.container(key="script-editor"):
            delivery_p = str(script.get("delivery_profile") or "Broadcast Short")
            flow = script.get("flow_metrics") or {}
            flow_score = flow.get("flow_score") or 9.0
            
            # Compute live telemetry from current inputs in session state
            current_vo1 = st.session_state.get(f"script-slide-{story_key}-1", script.get("script", [{}])[0].get("voiceover", ""))
            s1_words_live = len(str(current_vo1).split()) if current_vo1 else 0
            
            total_words_live = sum(
                len(str(st.session_state.get(f"script-slide-{story_key}-{idx}", sc.get("voiceover", ""))).split())
                for idx, sc in enumerate(script.get("script", []), 1)
            )
            est_seconds_live = round(total_words_live / 2.5, 1) if total_words_live else 0.0

            st.markdown(
                f'<div class="prompter-flow-bar">'
                f'<div>'
                f'<span class="badge" style="background:var(--surface-soft); color:var(--ink-secondary); border:1px solid var(--line); margin-right:8px;">{delivery_p}</span>'
                f'<span style="font-size:0.8rem; font-weight:800; letter-spacing:0.02em;">⚡ Broadcast Flow: {flow_score}/10</span>'
                f'</div>'
                f'<div style="font-size:0.75rem; font-weight:750; color:var(--muted);">'
                f'{total_words_live} words · ~{est_seconds_live}s runtime (Lead: {s1_words_live}w)'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="mini-label">Opening Headline</div>',unsafe_allow_html=True)
            headline_enabled = st.toggle(
                "Use opening headline",
                value=st.session_state.get(headline_toggle_key, True),
                key=headline_toggle_key,
            )
            edited_headline=st.text_input(
                "Opening heading (3–4 words)",
                value=script.get("headline","") if headline_enabled else "",
                max_chars=48,
                key=headline_text_key,
                disabled=not headline_enabled,
                label_visibility="collapsed",
            )
            st.markdown('<div style="height:.4rem"></div>',unsafe_allow_html=True)
            quote = str(script.get("quote") or "").strip()
            quote_attribution = str(script.get("quote_attribution") or "").strip()
            if quote:
                st.markdown('<div class="mini-label">Direct Quote</div>',unsafe_allow_html=True)
                st.text(quote)
                if quote_attribution:
                    st.caption(f"— {quote_attribution}")

            scene_roles = {
                1: "THE LEAD HOOK (<14w)",
                2: "THE TURN / CAUSE",
                3: "STAKES & EVIDENCE",
                4: "THE KICKER / IMPACT",
                5: "OUTLOOK / STATUS",
                6: "CLOSING",
            }
            edited_voiceovers=[]
            for index,scene in enumerate(script.get("script",[]),1):
                raw_text = scene.get("voiceover","")
                cur_text = st.session_state.get(f"script-slide-{story_key}-{index}", raw_text)
                word_count = len(str(cur_text).split()) if cur_text else 0
                est_seconds = round(word_count / 2.5, 1) if word_count else 0.0
                role = scene.get("narrative_role") or scene_roles.get(index, f"SCENE {index}")

                if index == 1:
                    if word_count <= 13:
                        meter_badge = f'<span class="hook-meter-ok">✓ LEAD HOOK: {word_count}w (&lt;14w target)</span>'
                    elif word_count == 14:
                        meter_badge = f'<span class="hook-meter-warn">⚠️ LEAD HOOK: 14w (At threshold)</span>'
                    else:
                        meter_badge = f'<span class="hook-meter-bad">⛔ LEAD HOOK: {word_count}w (Shorten for retention)</span>'
                else:
                    meter_badge = f'<span style="font-size:0.72rem; font-weight:700; color:var(--muted); background:var(--surface-soft); padding:3px 8px; border-radius:6px; border:1px solid var(--line);">{word_count} words · ~{est_seconds}s</span>'

                st.markdown(
                    f'<div class="cue-card-header">'
                    f'<span class="cue-role-title">CUE {index} · {role}</span>'
                    f'{meter_badge}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                edited_voiceovers.append(st.text_area("Narration",value=scene.get("voiceover",""),height=105,key=f"script-slide-{story_key}-{index}",label_visibility="collapsed"))

            if st.button("Approve script",type="primary",width="stretch"):
                try:
                    from script_writer import ScriptWriter
                    desk_p = st.session_state.get("topic_desk_profile") or ("youtube_trends" if universal_story else "cricket_india_asia")
                    approved = ScriptWriter.apply_edits(
                        script,
                        edited_voiceovers,
                        headline=edited_headline if headline_enabled else "",
                        profile=desk_p,
                    )
                    approved["headline_enabled"] = bool(headline_enabled)
                    st.session_state.approved_script=approved
                    st.session_state.visuals_approved = False
                    st.session_state.approved_visuals = None
                    st.session_state.test_stage = "03 · Audio"
                    st.session_state.test_pipeline_notice = {
                        "confirmed": "Script QC confirmed",
                        "next": "Moving to Audio.",
                    }
                    st.session_state.audio_data=None
                    st.session_state.approved_audio=None
                    st.session_state.subtitle_data=None
                    st.session_state.approved_subtitles=None
                    st.session_state.upload_qc_approved=False
                    st.session_state.upload_result=None
                    st.session_state.rendered_video_path=None
                    st.session_state.upload_qc=None
                    for index in range(1,6):
                        st.session_state.pop(f"upload-title-{index}",None)
                    st.session_state.pop("upload_video_file",None)
                    st.session_state.upload_title_options=list(approved.get("titles") or [])
                    st.session_state.upload_title_choice=0
                    st.session_state.upload_description=str(approved.get("seo_description") or "")
                    st.session_state.upload_hashtags=" ".join(approved.get("hashtags") or [])
                    st.session_state.upload_comment=str(approved.get("comment") or "")
                except ValueError as exc:
                    st.error(str(exc))

    with right:
        st.markdown('<div class="inspector">',unsafe_allow_html=True)
        st.markdown('<div class="mini-label">EDITORIAL TELEPROMPTER</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="font-weight:800;line-height:1.35;margin:.25rem 0 .75rem; color:var(--ink);">{topic.title}</div>',unsafe_allow_html=True)
        scenes_count = len(script.get("script") or [])
        st.markdown('<div class="inspector-line"><span>Language</span><span class="inspector-value">'+str(script.get("language_used") or language).title()+'</span></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="inspector-line"><span>Scenes</span><span class="inspector-value">{scenes_count} cues</span></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="inspector-line"><span>Word count</span><span class="inspector-value">{total_words_live} words</span></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="inspector-line"><span>Est. Runtime</span><span class="inspector-value">~{est_seconds_live}s</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Target Cadence</span><span class="inspector-value">~150 WPM (20-30s target)</span></div>',unsafe_allow_html=True)
        if st.session_state.approved_script:
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);border:1px solid #86efac;">✓ Script Approved</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)

        st.markdown('<div class="teleprompter-article-view">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.65rem; font-weight:800; letter-spacing:0.1em; color:var(--primary); text-transform:uppercase; margin-bottom:8px;">CONTINUOUS SPOKEN BROADCAST ARTICLE</div>', unsafe_allow_html=True)
        article_parts = []
        for s_idx, sc in enumerate(script.get("script", []), 1):
            vo_text = st.session_state.get(f"script-slide-{story_key}-{s_idx}", sc.get("voiceover", "")).strip()
            if vo_text:
                if s_idx == 1:
                    article_parts.append(f'<span style="color:var(--primary); font-weight:800;">[LEAD]</span> {vo_text}')
                else:
                    article_parts.append(f'<span class="teleprompter-cue-separator">▸</span> {vo_text}')
        if article_parts:
            st.markdown(" ".join(article_parts), unsafe_allow_html=True)
        else:
            st.markdown("<em>Narration cues will display here as continuous text.</em>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        _render_packaging_deck_and_phone(
            script=script,
            story_title=topic.title,
            current_headline=edited_headline,
            current_vo1=current_vo1,
            headline_enabled=bool(headline_enabled),
        )

def _test_visual_slide_count() -> int:
    script = st.session_state.get("approved_script") or st.session_state.get("script_data")
    count = len(script.get("script") or []) if isinstance(script, dict) else 4
    return max(1, count)


def render_visuals_crawler():
    from visual_fetcher import crawl_visuals

    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first, then select a story for Visuals.")
        return

    selected_index = st.session_state.selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.topics):
        st.info("Choose a story in 01 · Topic Fetcher first.")
        return
    topic = st.session_state.topics[selected_index]

    approved_script = st.session_state.get("approved_script")
    story = _visual_story_for_topic(
        topic,
        approved_script
        if (
            isinstance(approved_script, dict)
            and str(approved_script.get("source_title") or "").strip() == topic.title.strip()
        )
        else None,
    )

    story_key = f"{selected_index}:{story['url']}:{story['title']}"

    if story_key != st.session_state.get("visual_loaded_story"):
        st.session_state.visual_result = None
        st.session_state.visual_crops = {}
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

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Scraped images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "auto-crawler", _test_visual_slide_count())



def _render_manual_crawler():
    from visual_fetcher import manual_crawl_visuals

    st.subheader("Manual Scraper")
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
            width="stretch",
        )

    if scrape:
        query = query.strip()
        if not query:
            st.warning("Enter a query first.")
        else:
            with st.spinner("Searching and scraping publisher pages…"):
                try:
                    st.session_state.manual_visual_result = manual_crawl_visuals(query)
                    st.session_state.visual_crops = {}
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

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Scraped images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "manual-crawler", _test_visual_slide_count())

def _render_manual_real_images():
    from visual_search import search_images

    st.subheader("Real Image Search")
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
            width="stretch",
        )

    if search:
        query = query.strip()
        if not query:
            st.warning("Enter a query first.")
        else:
            with st.spinner("Searching real-image sources…"):
                try:
                    st.session_state.real_image_result = search_images(query)
                    st.session_state.visual_crops = {}
                except Exception as exc:
                    st.session_state.real_image_result = {
                        "error": f"{type(exc).__name__}: {exc}"
                    }

    result = st.session_state.get("real_image_result") or {}
    if not result:
        return
    if result.get("error"):
        st.error(result["error"])
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

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Real images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "real-search", _test_visual_slide_count())

def _render_manual_ai_images():
    from visual_generator import generate_images

    st.subheader("AI Generation")
    providers_label = ["Pollinations.ai (Flux)"]
    if os.getenv("HF_TOKEN"):
        providers_label.append("Hugging Face")
    if os.getenv("CLOUDFLARE_API_TOKEN") and os.getenv("CLOUDFLARE_ACCOUNT_ID"):
        providers_label.append("Cloudflare Workers AI")
    st.caption(f"Manual query only. Active AI providers: {', '.join(providers_label)}.")

    with st.form("ai_image_form"):
        query = st.text_input(
            "Manual prompt",
            placeholder="e.g. Ben Stokes hitting a six in a packed stadium",
            key="ai_image_query",
        )
        generate = st.form_submit_button(
            "Generate images",
            type="primary",
            width="stretch",
        )

    if generate:
        query = query.strip()
        if not query:
            st.warning("Enter a prompt first.")
        else:
            with st.spinner("Generating images…"):
                try:
                    st.session_state.ai_image_result = generate_images(query)
                    st.session_state.visual_crops = {}
                except Exception as exc:
                    st.session_state.ai_image_result = {
                        "error": f"{type(exc).__name__}: {exc}"
                    }

    result = st.session_state.get("ai_image_result") or {}
    if not result:
        return
    if result.get("error"):
        st.error(result["error"])
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
        last_query = query if generate else str(result.get("query") or "").strip()
        if last_query:
            if st.button("Search Real Images for this query instead →", type="primary", key="ai-fallback-to-real-search"):
                from visual_search import search_images
                with st.spinner(f"Searching real photography for '{last_query}'…"):
                    try:
                        st.session_state.real_image_result = search_images(last_query)
                        st.session_state.visual_test_mode = "Option 3 · Real Image Search"
                        st.session_state.ai_image_result = None
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Search failed: {exc}")
        return

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Generated images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "ai-generation", _test_visual_slide_count())

def render_visuals():
    st.header("04 · Visuals")
    cricket_test = st.session_state.get("topic_desk_profile") in {"cricket_india_asia", "cricket_global"}
    youtube_trends_test = st.session_state.get("test_production_line") == "youtube_trends"
    visual_options = (
        YT_TRENDS_VISUAL_OPTIONS
        if youtube_trends_test
        else CRICKET_TEST_VISUAL_OPTIONS
        if cricket_test
        else VISUAL_OPTIONS
    )
    selected_option = st.session_state.get("visual_test_mode")
    if selected_option not in visual_options:
        selected_option = visual_options[0]
    mode = _render_visual_option_grid(
        visual_options,
        session_key="visual_test_mode",
        button_prefix="test-visual-source",
    )

    script = st.session_state.get("approved_script") or st.session_state.get("script_data")
    slide_count = len(script.get("script") or []) if isinstance(script, dict) else 4
    slide_count = max(1, slide_count)

    _render_visual_board(slide_count)

    assignments = st.session_state.get("visual_assignments") or {}
    ready = all(slide in assignments for slide in range(1, slide_count + 1))
    if st.session_state.visuals_approved:
        st.success("Visuals approved. The exact visual handoff is ready for Renderer.")
    elif ready:
        if st.button(
            f"Approve {slide_count} visuals",
            type="primary",
            width="stretch",
            key="test-approve-visuals",
        ):
            st.session_state.approved_visuals = [
                assignments[slide]
                for slide in range(1, slide_count + 1)
            ]
            st.session_state.visuals_approved = True
            st.session_state.test_stage = "05 · Subtitles"
            st.session_state.test_pipeline_notice = {
                "confirmed": "Visual QC confirmed",
                "next": "Moving to Subtitles.",
            }
            st.rerun()
    else:
        st.caption(
            f"{len(assignments)}/{slide_count} visuals attached. "
            "Choose a source below to browse, crop, and attach visuals."
        )

    st.divider()

    _render_two_pane_visual_workspace(mode, slide_count, live=False, polygon_flow=True)



def render_subtitles():
    from subtitles import generate_subtitles

    if not st.session_state.approved_script or not st.session_state.approved_audio:
        st.info("Approve the Scriptwriter and Audio handoffs first.")
        return

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">05 · SUBTITLES</div>'
        '<div class="canvas-title">Review captions</div>'
        '<div class="canvas-copy">Native Audio word timings are used directly; there is no second transcription pass.</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Generate subtitles",type="primary",width="stretch"):
        try:
            st.session_state.subtitle_data=generate_subtitles(st.session_state.approved_script,st.session_state.approved_audio)
            st.session_state.approved_subtitles=None
        except ValueError as exc:
            st.error(str(exc))
    subtitles=st.session_state.subtitle_data
    if not subtitles:
        return

    left,right=st.columns([1.55,.45],gap="large")
    with left:
        with st.container(key="subtitle-editor"):
            for index,cue in enumerate(subtitles["cues"],1):
                words=" ".join(word["text"] for word in cue["words"])
                st.markdown(
                    f'<div class="cue-row"><div class="cue-time">{cue["start"]:.2f}s<br>{cue["end"]:.2f}s</div><div class="cue-text">{words}</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>',unsafe_allow_html=True)
    with right:
        st.markdown('<div class="inspector">',unsafe_allow_html=True)
        st.markdown('<div class="mini-label">Caption set</div>',unsafe_allow_html=True)
        for label,value in [("Cues",len(subtitles["cues"])),("Language",subtitles["language"]),("Timing","Audio-native")]:
            st.markdown(f'<div class="inspector-line"><span>{label}</span><span class="inspector-value">{value}</span></div>',unsafe_allow_html=True)
        if st.button("Approve subtitles",type="primary",width="stretch"):
            st.session_state.approved_subtitles=dict(subtitles)
            st.session_state.test_stage = "06 · Renderer"
            st.session_state.test_pipeline_notice = {
                "confirmed": "Subtitle QC confirmed",
                "next": "Moving to Renderer.",
            }
            st.rerun()
        if st.session_state.approved_subtitles:
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);">Approved</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
def render_renderer_test():
    from renderer import render_production_video

    script = st.session_state.get("approved_script")
    audio = st.session_state.get("approved_audio")
    subtitles = st.session_state.get("approved_subtitles")
    visuals = st.session_state.get("approved_visuals")

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">06 · RENDER</div>'
        '<div class="canvas-title">Build the finished Short</div>'
        '<div class="canvas-copy">Renderer consumes the exact approved Scriptwriter, Audio, Subtitles and Visual handoffs.</div></div></div>',
        unsafe_allow_html=True,
    )

    missing = []
    if not isinstance(script, dict):
        missing.append("Scriptwriter")
    if not isinstance(audio, dict):
        missing.append("Audio")
    if not isinstance(subtitles, dict):
        missing.append("Subtitles")
    if not isinstance(visuals, list):
        missing.append("Visuals")

    if missing:
        st.info("Renderer is waiting for approval of: " + ", ".join(missing) + ".")
        return

    headline_enabled = bool(script.get("headline_enabled", True))
    headline_text = str(script.get("headline") or "").strip()
    selected_topic = st.session_state.get("selected_topic")
    topics = st.session_state.get("topics") or []
    source_label = "SPORTS DESK"
    if isinstance(selected_topic, int) and 0 <= selected_topic < len(topics):
        source_label = str(topics[selected_topic].source or "SPORTS DESK")

    video_path = st.session_state.get("rendered_video_path")
    audio_dur = float(audio.get("total_duration") or 0.0)
    scenes_count = len(script.get("script") or [])
    visual_count = len(visuals) if isinstance(visuals, list) else 0

    st.markdown(
        '<div style="background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:16px; margin-bottom:16px;">'
        '<div style="font-size:0.65rem; font-weight:800; letter-spacing:0.09em; color:var(--accent); text-transform:uppercase; margin-bottom:10px;">MASTER PRODUCTION SPECIFICATIONS</div>'
        '<div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px;">'
        '<div style="background:var(--surface-soft); padding:10px; border-radius:8px; border:1px solid var(--line);">'
        '<div style="font-size:0.65rem; color:var(--muted); font-weight:700;">RESOLUTION</div>'
        '<div style="font-family:var(--font-mono); font-size:0.85rem; font-weight:800; color:var(--ink); margin-top:2px;">1080×1920</div>'
        '<div style="font-size:0.62rem; color:var(--subtle);">9:16 Portrait</div>'
        '</div>'
        '<div style="background:var(--surface-soft); padding:10px; border-radius:8px; border:1px solid var(--line);">'
        '<div style="font-size:0.65rem; color:var(--muted); font-weight:700;">FRAMERATE</div>'
        '<div style="font-family:var(--font-mono); font-size:0.85rem; font-weight:800; color:var(--ink); margin-top:2px;">30.00 FPS</div>'
        '<div style="font-size:0.62rem; color:var(--subtle);">Constant Frame Rate</div>'
        '</div>'
        '<div style="background:var(--surface-soft); padding:10px; border-radius:8px; border:1px solid var(--line);">'
        '<div style="font-size:0.65rem; color:var(--muted); font-weight:700;">CODEC / AUDIO</div>'
        '<div style="font-family:var(--font-mono); font-size:0.85rem; font-weight:800; color:var(--ink); margin-top:2px;">H.264 / AAC</div>'
        '<div style="font-size:0.62rem; color:var(--subtle);">High Profile yuv420p</div>'
        '</div>'
        '<div style="background:var(--surface-soft); padding:10px; border-radius:8px; border:1px solid var(--line);">'
        '<div style="font-size:0.65rem; color:var(--muted); font-weight:700;">PLATFORM TARGET</div>'
        '<div style="font-family:var(--font-mono); font-size:0.85rem; font-weight:800; color:var(--success); margin-top:2px;">YT SHORTS</div>'
        '<div style="font-size:0.62rem; color:var(--subtle);">Compliant (&lt; 60s)</div>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap;">'
        f'<span style="font-size:0.75rem; font-weight:700; color:var(--success); background:var(--success-soft); padding:4px 10px; border-radius:8px; border:1px solid #86efac;">✓ Script ({scenes_count} scenes)</span>'
        f'<span style="font-size:0.75rem; font-weight:700; color:var(--success); background:var(--success-soft); padding:4px 10px; border-radius:8px; border:1px solid #86efac;">✓ Audio ({audio_dur:.1f}s master track)</span>'
        f'<span style="font-size:0.75rem; font-weight:700; color:var(--success); background:var(--success-soft); padding:4px 10px; border-radius:8px; border:1px solid #86efac;">✓ Subtitles (Word-level sync)</span>'
        f'<span style="font-size:0.75rem; font-weight:700; color:var(--success); background:var(--success-soft); padding:4px 10px; border-radius:8px; border:1px solid #86efac;">✓ Visuals ({visual_count} compositions locked)</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if video_path and Path(str(video_path)).is_file():
        st.video(str(video_path), width=520)
        st.caption("This is the current rendered Test handoff. Rebuild it after changing an approved upstream stage.")
    else:
        st.caption("All required handoffs are approved. Build the Short below.")

    if st.button(
        "Build final Short",
        type="primary",
        width="stretch",
        key="test-build-final-short",
    ):
        output = Path("output/test") / "rendered_short.mp4"
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            with st.spinner("Rendering the final Short…"):
                render_production_video(
                    script,
                    audio,
                    subtitles,
                    visuals,
                    output_path=output,
                    headline_text=headline_text,
                    headline_enabled=headline_enabled,
                    source_label=source_label,
                )
            st.session_state.rendered_video_path = str(output)
            st.session_state.upload_qc_approved = False
            st.session_state.upload_result = None
            st.session_state.upload_qc = None
            st.rerun()
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))



TITLE_OPTION_STYLES = (
    "SEO / Search",
    "Consequence / Why It Matters",
    "Curiosity",
)


def render_top5_renderer_test():
    from renderer import render_production_video

    script = st.session_state.get("test_top5_script_handoff")
    audio = st.session_state.get("test_top5_audio_handoff")
    visuals = st.session_state.get("test_top5_visual_handoff")

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">TOP-5 · 06 · RENDER</div>'
        '<div class="canvas-title">Build the finished Top-5 Short</div>'
        '<div class="canvas-copy">Renderer consumes the approved six-slide Scriptwriter, Audio and Visual handoffs. Top-5 skips Subtitles.</div></div></div>',
        unsafe_allow_html=True,
    )

    missing = []
    if not isinstance(script, dict):
        missing.append("Scriptwriter")
    if not isinstance(audio, dict):
        missing.append("Audio")
    if not isinstance(visuals, list) or len(visuals) != 6:
        missing.append("Visuals")
    if missing:
        st.info("Renderer is waiting for approval of: " + ", ".join(missing) + ".")
        return

    video_path = st.session_state.get("test_top5_rendered_video_path")
    if video_path and Path(str(video_path)).is_file():
        st.video(str(video_path), width=520)
        st.caption("This is the current rendered Top-5 Test handoff. Rebuild it after changing an approved upstream stage.")
    else:
        st.caption("All required Top-5 handoffs are approved. Build the six-slide Short below.")

    if st.button(
        "Build final Top-5 Short",
        type="primary",
        width="stretch",
        key="test-top5-build-final-short",
    ):
        output = Path("output/test") / "top5_rendered_short.mp4"
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            with st.spinner("Rendering the final Top-5 Short…"):
                render_production_video(
                    script,
                    audio,
                    None,
                    visuals,
                    output_path=output,
                    headline_enabled=False,
                )
            st.session_state.test_top5_rendered_video_path = str(output)
            st.session_state.test_top5_upload_qc_approved = False
            st.session_state.test_top5_upload_qc = None
            st.session_state.test_top5_upload_result = None
            st.session_state.test_stage = "07 · Upload QC"
            st.session_state.test_pipeline_notice = {
                "confirmed": "Top-5 Renderer QC confirmed",
                "next": "Moving to Upload QC.",
            }
            st.rerun()
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))


def render_top5_upload_qc():
    script = st.session_state.get("test_top5_script_handoff")
    slides = list(script.get("slides") or []) if isinstance(script, dict) else []

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">TOP-5 · 07 · UPLOAD QC</div>'
        '<div class="section-title">Final video and publish metadata</div></div>'
        '<div class="section-count">one approval</div>',
        unsafe_allow_html=True,
    )

    if not isinstance(script, dict) or len(slides) != 6:
        st.info("Approve the Top-5 Scriptwriter result first.")
        return

    video_path = st.session_state.get("test_top5_rendered_video_path")
    video_path = Path(video_path) if video_path else None
    if not video_path or not video_path.is_file():
        st.info("The rendered Top-5 video will appear here after Renderer approval.")
        return

    st.video(str(video_path), width=520)

    title = str(slides[0].get("headline") or "").strip()
    if not title:
        st.error("Top-5 Slide 1 does not contain a usable title.")
        return

    st.markdown("**Title**")
    st.write(title)
    st.caption("Top-5 uses the approved Slide 1 spoken headline as the YouTube title.")

    if not st.session_state.test_top5_upload_description:
        st.session_state.test_top5_upload_description = str(
            script.get("seo_description") or ""
        )
    if not st.session_state.test_top5_upload_hashtags:
        st.session_state.test_top5_upload_hashtags = " ".join(
            str(tag) for tag in (script.get("hashtags") or [])
        )
    if not st.session_state.test_top5_upload_comment:
        st.session_state.test_top5_upload_comment = str(script.get("comment") or "")

    st.text_area("Description", key="test_top5_upload_description", height=150)
    st.text_input("Hashtags", key="test_top5_upload_hashtags")
    st.text_area("Public comment", key="test_top5_upload_comment", height=100)

    if not st.session_state.test_top5_upload_qc_approved:
        if st.button(
            "Approve Upload QC",
            type="primary",
            width="stretch",
            key="test-top5-approve-upload-qc",
        ):
            st.session_state.test_top5_upload_qc = {
                "title": title,
                "description": st.session_state.test_top5_upload_description.strip(),
                "hashtags": st.session_state.test_top5_upload_hashtags.strip(),
                "comment": st.session_state.test_top5_upload_comment.strip(),
            }
            st.session_state.test_top5_upload_qc_approved = True
            st.session_state.test_top5_upload_result = None
            st.session_state.test_pipeline_notice = {
                "confirmed": "Top-5 Upload QC confirmed",
                "next": "Upload controls are now unlocked.",
            }
            st.rerun()
        return

    qc = st.session_state.test_top5_upload_qc or {}
    st.success("Metadata approved.")
    st.write(f"**Title:** {qc.get('title') or ''}")
    st.write(f"**Description:** {qc.get('description') or ''}")
    st.write(f"**Hashtags:** {qc.get('hashtags') or ''}")
    st.write(f"**Comment:** {qc.get('comment') or ''}")

    result = st.session_state.get("test_top5_upload_result")
    if result:
        st.success(
            f"Uploaded as {result.get('privacy_status') or result.get('requested_privacy')} · "
            f"{result.get('url')}"
        )
        if result.get("requested_privacy") == "public":
            if result.get("privacy_status") != "public":
                st.warning(
                    "YouTube accepted the upload but returned it as private, so the public comment was not added."
                )
            elif result.get("comment_posted"):
                st.success("Public upload comment added.")
            elif result.get("comment_error"):
                st.warning(
                    "The video was uploaded publicly, but YouTube did not accept the comment: "
                    + str(result["comment_error"])
                )
        st.link_button("Open YouTube video", result["url"], width="stretch")
        return

    st.subheader("Upload")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        public = st.button(
            "Upload Public",
            type="primary",
            width="stretch",
            key="test-top5-upload-public",
        )
    with col2:
        private = st.button(
            "Upload Private",
            width="stretch",
            key="test-top5-upload-private",
        )

    if not (public or private):
        return

    privacy = "public" if public else "private"
    try:
        with st.spinner(f"Uploading Top-5 video as {privacy}…"):
            from uploader import upload_video
            st.session_state.test_top5_upload_result = upload_video(
                video_path,
                qc.get("title", ""),
                qc.get("description", ""),
                qc.get("hashtags", ""),
                qc.get("comment", ""),
                privacy,
            )
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(str(exc))
        return
    st.rerun()


def render_upload_qc():
    st.header("07 · Upload QC")
    script = st.session_state.get("approved_script")
    if not isinstance(script, dict):
        st.info("Approve the Scriptwriter first.")
        return

    video_path = st.session_state.get("rendered_video_path")
    if video_path:
        video_path = Path(video_path)

    if not video_path or not video_path.is_file():
        uploaded = st.file_uploader(
            "Rendered video",
            type=["mp4", "mov", "m4v"],
            key="upload_video_file",
        )
        if uploaded is not None:
            upload_dir = Path("output/upload_qc")
            upload_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(uploaded.name).suffix.lower() or ".mp4"
            video_path = upload_dir / f"rendered_video{suffix}"
            video_path.write_bytes(uploaded.getbuffer())
            st.session_state.rendered_video_path = str(video_path)

    titles = list(st.session_state.get("upload_title_options") or script.get("titles") or [])
    if not titles:
        st.error("No Scriptwriter title candidates are available.")
        return

    metadata = _upload_metadata(script)
    if not str(st.session_state.get("upload_description") or "").strip():
        st.session_state.upload_description = metadata["description"]
    if not str(st.session_state.get("upload_hashtags") or "").strip():
        st.session_state.upload_hashtags = metadata["hashtags"]
    if not str(st.session_state.get("upload_comment") or "").strip():
        st.session_state.upload_comment = metadata["comment"]

    if video_path and video_path.is_file():
        st.video(str(video_path), width=520)
    else:
        st.info("Metadata is ready for QC. The rendered video will appear here after the Renderer hands it off.")

    if not st.session_state.upload_qc_approved:
        st.subheader("Metadata")
        st.caption("Edit everything you want. Approve once, then choose Public or Private upload.")

        edited_titles = []
        for index, title in enumerate(titles, 1):
            edited_titles.append(
                st.text_input(
                    f"Title {index} · {TITLE_OPTION_STYLES[index - 1]}",
                    value=title,
                    key=f"upload-title-{index}",
                    max_chars=100,
                )
            )
        st.session_state.upload_title_options = edited_titles

        choice = st.pills(
            "Title to upload",
            list(range(len(edited_titles))),
            default=min(
                int(st.session_state.upload_title_choice),
                len(edited_titles) - 1,
            ),
            format_func=lambda index: edited_titles[index],
            key="upload_title_choice",
        )
        if choice is None:
            choice = 0

        st.text_area(
            "Description",
            key="upload_description",
            height=150,
        )
        st.text_input(
            "Hashtags",
            key="upload_hashtags",
        )
        st.text_area(
            "Comment",
            key="upload_comment",
            height=100,
        )

        if st.button("Approve Upload QC", type="primary", width="stretch"):
            st.session_state.upload_qc_approved = True
            st.session_state.upload_result = None
            st.session_state.test_pipeline_notice = {
                "confirmed": "Upload QC confirmed",
                "next": "Upload controls are now unlocked.",
            }
            st.session_state.upload_qc = {
                "title": edited_titles[choice].strip(),
                "description": st.session_state.upload_description,
                "hashtags": st.session_state.upload_hashtags,
                "comment": st.session_state.upload_comment,
            }
            st.rerun()

        return

    qc = st.session_state.get("upload_qc") or {}
    st.subheader("Approved metadata")
    st.write(f"**Title:** {qc.get('title') or ''}")
    st.write(f"**Description:** {qc.get('description') or ''}")
    st.write(f"**Hashtags:** {qc.get('hashtags') or ''}")
    st.write(f"**Comment:** {qc.get('comment') or ''}")

    result = st.session_state.get("upload_result")
    if result:
        st.success(
            f"Uploaded as {result.get('privacy_status') or result.get('requested_privacy')} · "
            f"{result.get('url')}"
        )
        if result.get("requested_privacy") == "public":
            if result.get("privacy_status") != "public":
                st.warning(
                    "YouTube accepted the upload but returned it as private, so the public comment was not added."
                )
            elif result.get("comment_posted"):
                st.success("Public upload comment added.")
            elif result.get("comment_error"):
                st.warning(
                    "The video was uploaded publicly, but YouTube did not accept the comment: "
                    + result["comment_error"]
                )
        st.link_button("Open YouTube video", result["url"], width="stretch")
        return

    if not video_path or not video_path.is_file():
        st.caption("Upload choices become available after a rendered video is present.")
        return

    st.subheader("Upload")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        public = st.button(
            "Upload Public",
            type="primary",
            width="stretch",
        )
    with col2:
        private = st.button(
            "Upload Private",
            width="stretch",
        )

    if not (public or private):
        return

    privacy = "public" if public else "private"
    try:
        with st.spinner(f"Uploading video as {privacy}…"):
            from uploader import upload_video
            st.session_state.upload_result = upload_video(
                video_path,
                qc.get("title", ""),
                qc.get("description", ""),
                qc.get("hashtags", ""),
                qc.get("comment", ""),
                privacy,
            )
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(str(exc))
    else:
        st.rerun()

def render_audio():
    from audio import (
        CHATTERBOX_VOICE_REFERENCES,
        approve_audio,
        generate_audio,
        package_human_audio,
        resolve_voice,
    )

    script=st.session_state.approved_script
    if not script:
        st.info("Approve the Scriptwriter result first.")
        return

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">03 · AUDIO</div>'
        '<div class="canvas-title">Build the voice track</div>'
        '<div class="canvas-copy">Generate the approved narration voice and inspect each scene before handing it to Visuals.</div></div></div>',
        unsafe_allow_html=True,
    )
    left,right=st.columns([1.15,.85],gap="large")
    languages=["English","Hindi","Telugu"]
    stored=str(script.get("language_used") or "english").casefold()
    default_language=stored if stored in {"english","hindi","telugu"} else "english"
    with left:
        engine_choice = st.pills(
            "Voice Engine",
            ["Chatterbox Turbo (Voice Cloning)", "Edge-TTS Neural"],
            default="Chatterbox Turbo (Voice Cloning)",
            key="audio_engine_choice_v2",
        ) or "Chatterbox Turbo (Voice Cloning)"
        col_l, col_g = st.columns(2)
        with col_l:
            language=st.pills("Language",languages,default=default_language.title(),key="audio_language") or default_language.title()
        with col_g:
            gender=st.pills("Voice Gender",["Female","Male"],default="Female",key="audio_gender") or "Female"
        selected_voice = resolve_voice(language.casefold(), gender.casefold())
        is_cb = "Chatterbox" in engine_choice
        selected_reference_label = None
        selected_reference = None
        selected_reference_ready = True
        if is_cb:
            selected_reference_label = st.selectbox(
                "Narrator voice",
                list(CHATTERBOX_VOICE_REFERENCES),
                key="audio_chatterbox_voice_reference",
            )
            selected_reference = CHATTERBOX_VOICE_REFERENCES[selected_reference_label]
            selected_reference_ready = selected_reference.is_file()
            st.caption(
                f"{selected_reference_label}: "
                + (f"local reference ready ({selected_reference.name})" if selected_reference_ready
                   else f"missing {selected_reference.name} — place it in the factory root")
            )
        flag = "🇺🇸 / 🇬🇧" if language == "English" else "🇮🇳"
        if is_cb and language != "English":
            st.warning("Chatterbox Turbo supports English only. Select Edge-TTS Neural for Hindi or Telugu narration.")

        if "Chatterbox" in engine_choice:
            has_ref = bool(selected_reference_ready and selected_reference is not None)
            ref_info = (
                f"{selected_reference.name} conditioned"
                if has_ref
                else f"Missing {selected_reference.name if selected_reference is not None else 'voice reference'}"
            )
            st.markdown(
                f'<div style="background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin: 10px 0 12px 0;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                f'<span style="font-size:0.65rem; font-weight:800; letter-spacing:0.08em; color:var(--accent); text-transform:uppercase;">VOICE ENGINE · CHATTERBOX TURBO (VOICE CLONING)</span>'
                f'<span style="font-size:0.72rem; font-weight:700; color:var(--muted);">🎙️ {ref_info}</span>'
                f'</div>'
                f'<div style="font-size:0.88rem; font-weight:800; color:var(--ink);">ChatterboxTurboTTS Voice Cloning</div>'
                f'<div style="font-size:0.72rem; color:var(--subtle); margin-top:2px;">Script-led delivery cues · Reusable voice conditioning · Cached exact takes</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin: 10px 0 12px 0;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                f'<span style="font-size:0.65rem; font-weight:800; letter-spacing:0.08em; color:var(--accent); text-transform:uppercase;">VOICE ENGINE · NEURAL EDGE-TTS</span>'
                f'<span style="font-size:0.72rem; font-weight:700; color:var(--muted);">{flag} {language} {gender}</span>'
                f'</div>'
                f'<div style="font-size:0.88rem; font-weight:800; color:var(--ink);">{selected_voice}</div>'
                f'<div style="font-size:0.72rem; color:var(--subtle); margin-top:2px;">Native word-level timestamps · 24kHz HD Audio stream</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if st.button(
            "Generate audio",
            type="primary",
            width="stretch",
            disabled=(is_cb and language != "English") or (is_cb and not selected_reference_ready),
        ):
            selected=dict(script)
            selected["language_used"]=language.casefold()
            selected["voice_gender"]=gender.casefold()
            selected["voice"]="chatterbox" if is_cb else selected_voice
            selected["voice_engine"]="chatterbox" if is_cb else "edge"
            with st.spinner("Generating voiceover…"):
                try:
                    st.session_state.audio_data=generate_audio(
                        selected,
                        voice="chatterbox" if is_cb else selected_voice,
                        engine="chatterbox" if is_cb else "edge",
                        reference=selected_reference if is_cb else None,
                    )
                    st.session_state.approved_audio=None
                except (RuntimeError,ValueError) as exc:
                    st.error(str(exc)); st.session_state.audio_data=None; st.session_state.approved_audio=None
            st.session_state.subtitle_data=None
            st.session_state.approved_subtitles=None

        with st.expander("🎙️ Human voiceover / mic upload (per-scene override)", expanded=False):
            st.caption("Upload an MP3/WAV file to override TTS for any scene. Word timings will be synthesized linearly.")
            scenes_list = script.get("script") or []
            if scenes_list:
                scene_nums = [int(s.get("scene", idx + 1)) for idx, s in enumerate(scenes_list)]
                target_scene = st.selectbox("Select scene to override", scene_nums, key="human_audio_target_scene")
                uploaded_file = st.file_uploader("Upload audio file (.mp3, .wav)", type=["mp3", "wav"], key=f"human_audio_upload_{target_scene}")
                if uploaded_file is not None and st.button("Apply uploaded audio to scene", key=f"apply_uploaded_audio_{target_scene}"):
                    from pathlib import Path
                    out_dir = Path("output/audio_test")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    tmp_file = out_dir / f"human_input_{target_scene}.mp3"
                    with open(tmp_file, "wb") as f_out:
                        f_out.write(uploaded_file.getbuffer())
                    narration = ""
                    for s in scenes_list:
                        if int(s.get("scene", 0)) == target_scene:
                            narration = s.get("voiceover", "")
                            break
                    try:
                        packaged = package_human_audio(target_scene, tmp_file, narration, out_dir)
                        if st.session_state.audio_data and "scenes" in st.session_state.audio_data:
                            cur_scenes = list(st.session_state.audio_data["scenes"])
                            replaced = False
                            for i, sc in enumerate(cur_scenes):
                                if int(sc.get("scene", 0)) == target_scene:
                                    cur_scenes[i] = packaged
                                    replaced = True
                                    break
                            if not replaced:
                                cur_scenes.append(packaged)
                            cur_scenes.sort(key=lambda x: int(x.get("scene", 0)))
                            st.session_state.audio_data["scenes"] = cur_scenes
                            st.session_state.audio_data["total_duration"] = round(sum(float(s["duration"]) for s in cur_scenes), 3)
                        else:
                            st.session_state.audio_data = {
                                "language": language.casefold(),
                                "voice": "human_recorded",
                                "rate_percent": 0.0,
                                "pitch": "default",
                                "scenes": [packaged],
                                "total_duration": packaged["duration"],
                                "duration_corrected": False,
                            }
                        st.session_state.approved_audio = None
                        st.success(f"Scene {target_scene} replaced with human audio!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to package audio: {exc}")

        audio=st.session_state.audio_data
        if audio:
            for scene in audio["scenes"]:
                with st.container(key=f"audio-scene-{scene['scene']}"):
                    st.markdown(
                        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                        f'<span style="font-size:0.82rem; font-weight:800; color:var(--ink);">TRACK {scene["scene"]}</span>'
                        f'<span style="font-family:var(--font-mono); font-size:0.72rem; font-weight:700; color:var(--accent); background:var(--surface-soft); padding:2px 8px; border-radius:6px; border:1px solid var(--line);">{scene["duration"]:.2f}s · {len(scene["timings"])} cues</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.audio(
                        scene["path"],
                        format="audio/wav" if str(scene["path"]).lower().endswith(".wav") else "audio/mp3",
                    )
                    st.caption("🎙️ Human Audio" if scene.get("human_recorded") else ("⚡ Cached" if scene["from_cache"] else "✨ Fresh Neural TTS generation"))
            if st.button("Approve audio",type="primary",width="stretch"):
                try:
                    st.session_state.approved_audio=approve_audio(audio)
                    st.session_state.test_stage = "04 · Visuals"
                    st.session_state.test_pipeline_notice = {
                        "confirmed": "Audio QC confirmed",
                        "next": "Moving to Visuals.",
                    }
                    st.session_state.subtitle_data=None
                    st.session_state.approved_subtitles=None
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with right:
        with st.container(key="audio-inspector"):
            st.markdown('<div class="inspector">',unsafe_allow_html=True)
            st.markdown('<div class="mini-label">SOUNDBOARD INSPECTOR</div>',unsafe_allow_html=True)
            audio=st.session_state.audio_data
            if audio:
                correction="Speed corrected" if audio["duration_corrected"] else "No correction"
                duration_val = float(audio["total_duration"])
                compliance = "✓ Compliant (<58s)" if duration_val <= 58.0 else "⚠️ Near limit (>58s)"
                for label,value in [
                    ("Voice Talent",audio["voice"]),
                    ("Speed Rate",f'{audio["rate_percent"]:+.0f}%'),
                    ("Master Duration",f'{duration_val:.2f}s'),
                    ("Cadence Sync",correction),
                    ("Shorts Standard",compliance),
                ]:
                    st.markdown(f'<div class="inspector-line"><span>{label}</span><span class="inspector-value">{value}</span></div>',unsafe_allow_html=True)
                if st.session_state.approved_audio:
                    st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);border:1px solid #86efac;">✓ Audio Approved</span></div>',unsafe_allow_html=True)
            else:
                st.caption("Audio metrics will appear after generation.")
            st.markdown('</div>',unsafe_allow_html=True)

if st.session_state.app_mode == "home":
    _render_home()
elif st.session_state.app_mode == "test":
    _render_app_sidebar()
    if st.session_state.get("factory_format") == "long_form":
        render_longform_test()
    elif st.session_state.test_production_line is None:
        st.markdown(
            '<div class="live-product-head">'
            '<div><div class="eyebrow">TEST LAB</div>'
            '<div class="live-product-title">Choose a line.</div>'
            '<div class="hero-subtitle">Pick a production path.</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.space("small")
        choices = [
            (
                "test-line-deep-dive",
                "01 · DEEP-DIVE",
                "DEEP-DIVE",
                "One story, end to end.",
            ),
            (
                "test-line-top-5",
                "02 · TOP-5",
                "TOP-5",
                "Five cricket stories, one package.",
            ),
            (
                "test-line-otd",
                "03 · OTD",
                "ON THIS DAY",
                "A date-driven historical package.",
            ),
            (
                "test-line-youtube-trends",
                "04",
                "YT Trends",
                "Start from current YouTube search trends.",
            ),
        ]
        cols = st.columns(4, gap="small")
        for col, (key, eyebrow, title, copy) in zip(cols, choices):
            with col:
                with st.container(key=key):
                    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="choice-title">{title}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="choice-copy">{copy}</div>', unsafe_allow_html=True)
                    st.space("medium")
                    button_label = {
                        "01 · DEEP-DIVE": "Open Deep-Dive",
                        "02 · TOP-5": "Open Top-5",
                        "03 · OTD": "Open OTD",
                        "04": "Open YT Trends",
                    }[eyebrow]
                    if st.button(button_label, type="primary", width="stretch", key=f"{key}-button"):
                        st.session_state.test_production_line = {
                            "01 · DEEP-DIVE": "deep_dive",
                            "02 · TOP-5": "top_5",
                            "03 · OTD": "otd",
                            "04": "youtube_trends",
                        }[eyebrow]
                        if eyebrow in {"01 · DEEP-DIVE", "03 · OTD", "04"}:
                            st.session_state.test_stage = "01 · Topic Fetcher"
                        if eyebrow == "03 · OTD":
                            st.session_state.otd_topics = []
                            st.session_state.otd_selected = None
                            st.session_state.topics = []
                            st.session_state.selected_topic = None
                            st.session_state.topic_open_tile = None
                            st.session_state.topic_desk_profile = "otd"
                        if eyebrow == "04":
                            from topic_fetcher import fetch_youtube_search_trends
                            st.session_state.youtube_trend_results = []
                            st.session_state.youtube_trend_selected = None
                            st.session_state.youtube_trend_keyword = ""
                            st.session_state.youtube_trend_error = ""
                            st.session_state.topics = []
                            st.session_state.selected_topic = None
                            st.session_state.topic_open_tile = None
                            st.session_state.topic_desk_profile = None
                            try:
                                with st.spinner("Reading current YouTube search trends…"):
                                    st.session_state.youtube_trend_results = fetch_youtube_search_trends(limit=20)
                            except (RuntimeError, ValueError, OSError) as exc:
                                st.session_state.youtube_trend_error = str(exc)
                        st.session_state.test_pipeline_notice = None
                        st.rerun()
    elif st.session_state.test_production_line:
        line_name = {
            "deep_dive": "Deep-Dive",
            "top_5": "Top-5",
            "otd": "OTD",
            "youtube_trends": "YT Trends",
        }.get(
            st.session_state.test_production_line,
            str(st.session_state.test_production_line).replace("_", " ").title(),
        )
        stage = st.session_state.test_stage

        test_stage_labels = [item["label"] for item in STAGES]
        test_current_index = next(
            index for index, item in enumerate(STAGES)
            if item["key"] == stage
        )
        test_upload_complete = (
            test_current_index == len(STAGES) - 1
            and bool(st.session_state.upload_result)
        )
        _render_pipeline_progress(
            test_stage_labels,
            test_current_index,
            complete_last=test_upload_complete,
        )
        _render_pipeline_notice("test_pipeline_notice")

        if line_name == "YT Trends" and stage == "01 · Topic Fetcher":
            render_youtube_trends_topic_fetcher()
        elif line_name == "OTD" and stage == "01 · Topic Fetcher":
            render_otd_topic_fetcher()
        elif line_name in {"Deep-Dive", "YT Trends", "OTD"}:
            if stage == "01 · Topic Fetcher":
                render_topic_fetcher()
            elif stage == "02 · Scriptwriter":
                render_scriptwriter()
            elif stage == "03 · Audio":
                render_audio()
            elif stage == "04 · Visuals":
                render_visuals()
            elif stage == "05 · Subtitles":
                render_subtitles()
            elif stage == "06 · Renderer":
                render_renderer_test()
            elif stage == "07 · Upload QC":
                render_upload_qc()
        elif line_name == "Top-5" and stage == "01 · Topic Fetcher":
            st.markdown(
                '<div class="section-head"><div><div class="eyebrow">TOP-5 · 01 · TOPIC PRODUCTION</div>'
                '<div class="section-title">Select five cricket stories</div>'
                '<div class="canvas-copy">Use the existing Topic Fetcher, build the pool, then choose and order exactly five distinct stories.</div></div>'
                '<div class="section-count">0–5 selected</div></div>',
                unsafe_allow_html=True,
            )

            content_type = st.pills(
                "Content type",
                ["Cricket", "General News"],
                default=st.session_state.test_top5_content_type,
                key="test-top5-content-type",
                label_visibility="collapsed",
            ) or st.session_state.test_top5_content_type

            if content_type != st.session_state.test_top5_content_type:
                st.session_state.test_top5_content_type = content_type
                st.session_state.test_top5_topics = []
                st.session_state.test_top5_selected = []
                st.session_state.test_top5_topic_open_tile = None
                st.session_state.test_top5_handoff = None
                st.session_state.test_top5_script_data = None
                st.session_state.test_top5_script_handoff = None
                st.session_state.test_top5_audio_data = None
                st.session_state.test_top5_audio_handoff = None
                st.session_state.test_top5_visual_results = {}
                st.session_state.test_top5_visual_selected = {}
                st.session_state.test_top5_visual_previews = {}
                st.session_state.test_top5_visual_assignments = {}
                st.session_state.test_top5_manual_subject_cutouts = {}
                st.session_state.test_top5_visual_handoff = None
                st.session_state.test_top5_rendered_video_path = None
                st.session_state.test_top5_upload_qc_approved = False
                st.session_state.test_top5_upload_qc = None
                st.session_state.test_top5_upload_description = ""
                st.session_state.test_top5_upload_hashtags = ""
                st.session_state.test_top5_upload_comment = ""
                st.session_state.test_top5_upload_result = None

            if content_type == "General News":
                st.info("General News is reserved for a later Top-5 expansion. Cricket is the current active Topic Fetcher.")
            else:
                topics = st.session_state.test_top5_topics
                toolbar_left, toolbar_mid, toolbar_right = st.columns([1, 1, .8], gap="small")
                with toolbar_left:
                    fetch = st.button("Fetch current cricket stories", type="primary", width="stretch", key="test-top5-fetch")
                with toolbar_mid:
                    more = st.button("20 more articles", width="stretch", key="test-top5-more", disabled=not bool(topics))
                with toolbar_right:
                    st.markdown(
                        f'<div style="text-align:right;padding:.65rem .15rem;"><span class="badge">{len(topics)} stories</span></div>',
                        unsafe_allow_html=True,
                    )

                if fetch or more:
                    existing = list(topics) if more else []
                    exclude = existing
                    with st.spinner("Fetching current cricket stories…"):
                        try:
                            from topic_fetcher import fetch_top5_topics
                            new_topics = fetch_top5_topics(
                                more=more,
                                exclude_topics=exclude,
                                limit=20,
                            )
                            st.session_state.test_top5_topics = existing + new_topics
                        except Exception as exc:
                            st.error(f"Failed to fetch cricket stories: {exc}")
                    if not more:
                        st.session_state.test_top5_selected = []
                        st.session_state.test_top5_topic_open_tile = None
                        st.session_state.test_top5_handoff = None
                        st.session_state.test_top5_script_data = None
                        st.session_state.test_top5_script_handoff = None
                    st.rerun()

                topics = st.session_state.test_top5_topics
                selected = st.session_state.test_top5_selected

                if selected:
                    st.markdown(
                        f'<div class="section-head"><div><div class="eyebrow">TOP 5 SELECTION</div>'
                        f'<div class="section-title">{len(selected)} / 5 selected</div></div>'
                        f'<div class="section-count">order matters</div></div>',
                        unsafe_allow_html=True,
                    )

                    for slot, topic_index in enumerate(selected):
                        topic = topics[topic_index]
                        row = st.columns([.12, 1.55, .26, .26, .34], gap="small")
                        with row[0]:
                            st.markdown(f'<div class="topic-rank">#{slot + 1}</div>', unsafe_allow_html=True)
                        with row[1]:
                            st.markdown(
                                f'<div class="topic-title">{topic.title}</div>'
                                f'<div class="topic-meta">{topic.source or "Sports desk"}</div>',
                                unsafe_allow_html=True,
                            )
                        with row[2]:
                            if st.button("↑", key=f"test-top5-up-{topic_index}", disabled=slot == 0, width="stretch"):
                                selected[slot - 1], selected[slot] = selected[slot], selected[slot - 1]
                                st.session_state.test_top5_selected = selected
                                st.session_state.test_top5_handoff = None
                                st.session_state.test_top5_script_data = None
                                st.session_state.test_top5_script_handoff = None
                                st.session_state.test_top5_audio_data = None
                                st.session_state.test_top5_audio_handoff = None
                                st.session_state.test_top5_visual_results = {}
                                st.session_state.test_top5_visual_selected = {}
                                st.session_state.test_top5_visual_previews = {}
                                st.session_state.test_top5_visual_assignments = {}
                                st.session_state.test_top5_manual_subject_cutouts = {}
                                st.session_state.test_top5_visual_handoff = None
                                st.session_state.test_top5_rendered_video_path = None
                                st.session_state.test_top5_upload_qc_approved = False
                                st.session_state.test_top5_upload_qc = None
                                st.session_state.test_top5_upload_description = ""
                                st.session_state.test_top5_upload_hashtags = ""
                                st.session_state.test_top5_upload_comment = ""
                                st.session_state.test_top5_upload_result = None
                                st.rerun()
                        with row[3]:
                            if st.button("↓", key=f"test-top5-down-{topic_index}", disabled=slot == len(selected) - 1, width="stretch"):
                                selected[slot + 1], selected[slot] = selected[slot], selected[slot + 1]
                                st.session_state.test_top5_selected = selected
                                st.session_state.test_top5_handoff = None
                                st.session_state.test_top5_script_data = None
                                st.session_state.test_top5_script_handoff = None
                                st.session_state.test_top5_audio_data = None
                                st.session_state.test_top5_audio_handoff = None
                                st.session_state.test_top5_visual_results = {}
                                st.session_state.test_top5_visual_selected = {}
                                st.session_state.test_top5_visual_previews = {}
                                st.session_state.test_top5_visual_assignments = {}
                                st.session_state.test_top5_manual_subject_cutouts = {}
                                st.session_state.test_top5_visual_handoff = None
                                st.session_state.test_top5_rendered_video_path = None
                                st.session_state.test_top5_upload_qc_approved = False
                                st.session_state.test_top5_upload_qc = None
                                st.session_state.test_top5_upload_description = ""
                                st.session_state.test_top5_upload_hashtags = ""
                                st.session_state.test_top5_upload_comment = ""
                                st.session_state.test_top5_upload_result = None
                                st.rerun()
                        with row[4]:
                            if st.button("Remove", key=f"test-top5-remove-{topic_index}", width="stretch"):
                                selected.remove(topic_index)
                                st.session_state.test_top5_selected = selected
                                st.session_state.test_top5_handoff = None
                                st.session_state.test_top5_script_data = None
                                st.session_state.test_top5_script_handoff = None
                                st.session_state.test_top5_audio_data = None
                                st.session_state.test_top5_audio_handoff = None
                                st.session_state.test_top5_visual_results = {}
                                st.session_state.test_top5_visual_selected = {}
                                st.session_state.test_top5_visual_previews = {}
                                st.session_state.test_top5_visual_assignments = {}
                                st.session_state.test_top5_manual_subject_cutouts = {}
                                st.session_state.test_top5_visual_handoff = None
                                st.session_state.test_top5_rendered_video_path = None
                                st.session_state.test_top5_upload_qc_approved = False
                                st.session_state.test_top5_upload_qc = None
                                st.session_state.test_top5_upload_description = ""
                                st.session_state.test_top5_upload_hashtags = ""
                                st.session_state.test_top5_upload_comment = ""
                                st.session_state.test_top5_upload_result = None
                                st.rerun()

                    st.divider()

                if not topics:
                    st.markdown(
                        '<div class="empty-state"><div class="empty-state-title">No cricket stories loaded</div>'
                        '<div class="empty-state-copy">Fetch the current cricket story pool to start.</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="section-head"><div><div class="eyebrow">STORY POOL</div>'
                        '<div class="section-title">Available cricket stories</div></div>'
                        '<div class="section-count">select up to five</div></div>',
                        unsafe_allow_html=True,
                    )
                    for start in range(0, len(topics), 2):
                        row = st.columns(2, gap="medium")
                        for col, (index, tile) in zip(
                            row,
                            enumerate(topics[start:start + 2], start=start),
                        ):
                            members = tuple(sorted(
                                tile.group_members or (tile,),
                                key=lambda item: item.score,
                                reverse=True,
                            ))
                            if tile.group_key.startswith("keyword:"):
                                tile_title = tile.group_key.split(":", 1)[1].title()
                            elif tile.group_key.startswith("player:"):
                                tile_title = tile.group_key.split(":", 1)[1].title()
                            else:
                                tile_title = tile.title

                            with col:
                                with st.container(key=f"test-top5-topic-{index}"):
                                    is_open = st.session_state.get("test_top5_topic_open_tile") == index
                                    if st.button(
                                        f'{"▾" if is_open else "▸"}  {tile_title}',
                                        key=f"test-top5-topic-header-{index}",
                                        width="stretch",
                                        type="primary" if is_open else "secondary",
                                    ):
                                        st.session_state.test_top5_topic_open_tile = None if is_open else index
                                        st.rerun()

                                    if not is_open:
                                        continue

                                    for headline_index, member in enumerate(members):
                                        selected_here = (
                                            index in selected
                                            and topics[index].url == member.url
                                        )
                                        select_disabled = (
                                            index not in selected and len(selected) >= 5
                                        )
                                        with st.container(
                                            horizontal=True,
                                            vertical_alignment="center",
                                            horizontal_alignment="distribute",
                                            gap="small",
                                        ):
                                            st.markdown(
                                                f'<div class="topic-title">{member.title}</div>'
                                                f'<div class="topic-meta">{member.source or "Sports desk"} · {member.published_at:%d %b · %H:%M UTC}</div>',
                                                unsafe_allow_html=True,
                                            )
                                            if st.button(
                                                "Selected" if selected_here else "Choose",
                                                key=f"test-top5-select-{index}-{headline_index}",
                                                width="content",
                                                type="primary" if selected_here else "secondary",
                                                disabled=select_disabled,
                                            ):
                                                st.session_state.test_top5_topics[index] = replace(
                                                    member,
                                                    group_key=tile.group_key,
                                                    group_members=members,
                                                )
                                                if index not in selected:
                                                    selected.append(index)
                                                st.session_state.test_top5_selected = selected
                                                st.session_state.test_top5_topic_open_tile = None
                                                st.session_state.test_top5_handoff = None
                                                st.session_state.test_top5_script_data = None
                                                st.session_state.test_top5_script_handoff = None
                                                st.session_state.test_top5_audio_data = None
                                                st.session_state.test_top5_audio_handoff = None
                                                st.rerun()

                selected = st.session_state.test_top5_selected
                if len(selected) == 5:
                    if st.button("Approve Top-5 selection", type="primary", width="stretch", key="test-top5-approve"):
                        st.session_state.test_top5_handoff = [
                            {
                                "title": topics[index].title,
                                "url": topics[index].url,
                                "article": topics[index].description,
                                "source": topics[index].source,
                                "published_at": topics[index].published_at.isoformat(),
                            }
                            for index in selected
                        ]
                        st.session_state.test_top5_script_data = None
                        st.session_state.test_top5_script_handoff = None
                        st.session_state.test_top5_audio_data = None
                        st.session_state.test_top5_audio_handoff = None
                        st.session_state.test_stage = "02 · Scriptwriter"
                        st.session_state.test_pipeline_notice = {
                            "confirmed": "Top-5 selection confirmed",
                            "next": "Moving to Scriptwriter.",
                        }
                        st.rerun()

                if st.session_state.test_top5_handoff:
                    st.success("Top-5 selection approved. The five story URLs, titles and available article content are ready for the next stage.")
                    st.caption("The Scriptwriter will research and enrich each selected story URL when you generate the package.")
                    for number, article in enumerate(st.session_state.test_top5_handoff, 1):
                        st.markdown(
                            f'**#{number} · {article["title"]}**<br><span class="topic-meta">{article["url"]}</span>',
                            unsafe_allow_html=True,
                        )
        elif line_name == "Top-5" and stage == "02 · Scriptwriter":
            from script_writer import estimate_speech_seconds, generate_top5_script

            stories = list(st.session_state.get("test_top5_handoff") or [])
            st.markdown(
                '<div class="section-head"><div><div class="eyebrow">TOP-5 · 02 · SCRIPTWRITER</div>'
                '<div class="section-title">Write the six-slide package</div></div>'
                '<div class="section-count">5 stories → 6 slides</div></div>',
                unsafe_allow_html=True,
            )

            if len(stories) != 5:
                st.info("Approve exactly five stories in Top-5 Topic Production first.")
            else:
                st.caption(
                    "The writer researches the five selected stories, then produces one spoken "
                    "headline per slide and separate visual-only story copy."
                )

                if st.button("Generate Top-5 script", type="primary", width="stretch", key="test-top5-script-generate"):
                    with st.spinner("Researching the five stories and writing the six-slide package…"):
                        try:
                            result = generate_top5_script(stories)
                            st.session_state.test_top5_script_data = result
                            st.session_state.test_top5_script_handoff = None
                            st.session_state.test_top5_audio_data = None
                            st.session_state.test_top5_audio_handoff = None
                            for slide in result.get("slides") or []:
                                number = int(slide.get("slide_number") or 0)
                                st.session_state[f"test-top5-script-headline-{number}"] = str(slide.get("headline") or "")
                                st.session_state[f"test-top5-script-body-{number}"] = str(slide.get("body") or "")
                            st.session_state["test-top5-script-description"] = str(
                                result.get("seo_description") or ""
                            )
                            st.session_state["test-top5-script-hashtags"] = " ".join(
                                str(tag) for tag in (result.get("hashtags") or [])
                            )
                            st.session_state["test-top5-script-comment"] = str(
                                result.get("comment") or ""
                            )
                            st.rerun()
                        except (RuntimeError, ValueError) as exc:
                            st.error(str(exc))

                result = st.session_state.get("test_top5_script_data") or {}
                slides = list(result.get("slides") or [])

                if slides:
                    st.markdown(
                        '<div class="section-head"><div><div class="eyebrow">EDITORIAL QC</div>'
                        '<div class="section-title">Edit every headline and visual story</div></div>'
                        '<div class="section-count">manual approval</div></div>',
                        unsafe_allow_html=True,
                    )

                    for slide in slides:
                        number = int(slide.get("slide_number") or 0)
                        if number == 1:
                            st.markdown(
                                '<div class="mini-label">SLIDE 1 · PACKAGE OPENER · SPOKEN</div>',
                                unsafe_allow_html=True,
                            )
                            headline = st.text_area(
                                "Slide 1 headline",
                                key="test-top5-script-headline-1",
                                height=82,
                                max_chars=160,
                                label_visibility="collapsed",
                            )
                            st.caption(
                                f'{len(headline.split())} words · package opener · '
                                f'{estimate_speech_seconds(headline):.1f}s estimated speech'
                            )
                            st.text_area(
                                "Visual package body",
                                key="test-top5-script-body-1",
                                height=120,
                                max_chars=600,
                                label_visibility="collapsed",
                            )
                        else:
                            story = stories[number - 2]
                            st.markdown(
                                f'<div class="mini-label">SLIDE {number} · STORY {number - 1} · SPOKEN</div>'
                                f'<div class="topic-meta">{story.get("title") or "Selected story"}</div>',
                                unsafe_allow_html=True,
                            )
                            headline = st.text_area(
                                "Spoken headline",
                                key=f"test-top5-script-headline-{number}",
                                height=110,
                                max_chars=260,
                                label_visibility="collapsed",
                            )
                            st.caption(
                                f'{len(headline.split())} words · '
                                f'{estimate_speech_seconds(headline):.1f}s estimated speech · under 15s required'
                            )
                            st.text_area(
                                "Visual story body",
                                key=f"test-top5-script-body-{number}",
                                height=120,
                                max_chars=600,
                                label_visibility="collapsed",
                            )
                        st.divider()

                    st.markdown('<div class="mini-label">PUBLISH METADATA</div>', unsafe_allow_html=True)
                    st.text_area(
                        "Description",
                        key="test-top5-script-description",
                        height=110,
                        label_visibility="collapsed",
                    )
                    st.text_input(
                        "Hashtags",
                        key="test-top5-script-hashtags",
                        label_visibility="collapsed",
                    )
                    st.text_area(
                        "Public comment",
                        key="test-top5-script-comment",
                        height=90,
                        label_visibility="collapsed",
                    )

                    with st.expander("Visual handoff metadata", expanded=False):
                        for slide in slides:
                            number = int(slide.get("slide_number") or 0)
                            st.markdown(
                                f'**Slide {number}** · {slide.get("primary_entity") or "—"} · '
                                f'{slide.get("sport_or_topic_category") or "—"}'
                            )
                            st.caption(slide.get("visual_intent") or "")
                            st.code(slide.get("specific_search_prompt") or "")

                    if st.button("Approve Top-5 Script", type="primary", width="stretch", key="test-top5-script-approve"):
                        edited = {
                            "slides": [
                                {
                                    **slide,
                                    "headline": st.session_state.get(
                                        f"test-top5-script-headline-{int(slide.get('slide_number') or 0)}",
                                        "",
                                    ).strip(),
                                    "body": st.session_state.get(
                                        f"test-top5-script-body-{int(slide.get('slide_number') or 0)}",
                                        "",
                                    ).strip(),
                                }
                                for slide in slides
                            ],
                            "seo_description": st.session_state.get(
                                "test-top5-script-description", ""
                            ).strip(),
                            "hashtags": [
                                tag.strip()
                                for tag in st.session_state.get("test-top5-script-hashtags", "").split()
                                if tag.strip()
                            ],
                            "comment": st.session_state.get(
                                "test-top5-script-comment", ""
                            ).strip(),
                        }
                        st.session_state.test_top5_audio_data = None
                        st.session_state.test_top5_audio_handoff = None
                        st.session_state.test_top5_visual_results = {}
                        st.session_state.test_top5_visual_selected = {}
                        st.session_state.test_top5_visual_previews = {}
                        st.session_state.test_top5_visual_assignments = {}
                        st.session_state.test_top5_manual_subject_cutouts = {}
                        st.session_state.test_top5_visual_handoff = None
                        st.session_state.test_top5_rendered_video_path = None
                        st.session_state.test_top5_upload_qc_approved = False
                        st.session_state.test_top5_upload_qc = None
                        st.session_state.test_top5_upload_description = ""
                        st.session_state.test_top5_upload_hashtags = ""
                        st.session_state.test_top5_upload_comment = ""
                        st.session_state.test_top5_upload_result = None
                        st.session_state.test_stage = "03 · Audio"
                        st.session_state.test_pipeline_notice = {
                            "confirmed": "Top-5 Script QC confirmed",
                            "next": "Moving to Audio.",
                        }
                        st.session_state.test_top5_script_handoff = {
                            "schema": "final-shorts.top5-script.v1",
                            "slides": edited["slides"],
                            "seo_description": edited["seo_description"],
                            "hashtags": edited["hashtags"],
                            "comment": edited["comment"],
                            "stories": stories,
                            "provider_used": result.get("provider_used"),
                            "approved_for_audio": True,
                        }
                        st.rerun()

                    if st.session_state.get("test_top5_script_handoff"):
                        st.success("Top-5 Scriptwriter approved. The six-slide package is ready for the next stage.")
                        st.caption("Audio will use the six spoken slide headlines; the body copy is visual-only.")

        elif line_name == "Top-5" and stage == "03 · Audio":
            from audio import approve_top5_audio, generate_top5_audio, package_human_audio, resolve_voice

            handoff = st.session_state.get("test_top5_script_handoff")
            st.markdown(
                '<div class="section-head"><div><div class="eyebrow">TOP-5 · 03 · AUDIO</div>'
                '<div class="section-title">Build the six-line voice track</div></div>'
                '<div class="section-count">headlines only</div></div>',
                unsafe_allow_html=True,
            )

            if not handoff:
                st.info("Approve the Top-5 Scriptwriter result first.")
            else:
                st.caption(
                    "Top-5 Audio narrates only the six approved spoken headlines. "
                    "Visual story bodies are never sent to speech."
                )

                top5_languages = ["English", "Hindi", "Telugu"]
                stored_t5_lang = str(handoff.get("language_used") or "english").casefold()
                default_t5_lang = stored_t5_lang if stored_t5_lang in {"english", "hindi", "telugu"} else "english"
                t5_engine_choice = st.pills(
                    "Voice Engine",
                    ["Chatterbox Turbo (Voice Cloning)", "Edge-TTS Neural"],
                    default="Chatterbox Turbo (Voice Cloning)",
                    key="test_top5_audio_engine_choice_v2",
                ) or "Chatterbox Turbo (Voice Cloning)"
                col_t5_lang, col_t5_gender = st.columns(2)
                with col_t5_lang:
                    t5_language = st.pills("Language", top5_languages, default=default_t5_lang.title(), key="test_top5_audio_language") or default_t5_lang.title()
                with col_t5_gender:
                    t5_gender = st.pills("Voice Gender", ["Female", "Male"], default="Female", key="test_top5_audio_gender") or "Female"
                is_t5_chatterbox = "Chatterbox" in t5_engine_choice
                t5_voice = "chatterbox" if is_t5_chatterbox else resolve_voice(t5_language.casefold(), t5_gender.casefold())
                t5_reference = None
                t5_reference_ready = True
                if is_t5_chatterbox:
                    from audio import CHATTERBOX_VOICE_REFERENCES
                    t5_reference_label = st.selectbox(
                        "Narrator voice",
                        list(CHATTERBOX_VOICE_REFERENCES),
                        key="test_top5_chatterbox_voice_reference",
                    )
                    t5_reference = CHATTERBOX_VOICE_REFERENCES[t5_reference_label]
                    t5_reference_ready = t5_reference.is_file()
                    st.caption(
                        f"{t5_reference_label}: "
                        + (f"reference ready ({t5_reference.name})" if t5_reference_ready
                           else f"missing {t5_reference.name} — place it in the factory root")
                    )
                    if t5_language != "English":
                        st.warning("Chatterbox Turbo supports English only. Select Edge-TTS Neural for Hindi or Telugu narration.")
                else:
                    st.caption(f"Selected Voice: **{t5_voice}** ({t5_language} {t5_gender}) · native Edge-TTS")

                with st.expander("Spoken lines", expanded=True):
                    for slide in handoff.get("slides") or []:
                        number = int(slide.get("slide_number") or 0)
                        headline = str(slide.get("headline") or "").strip()
                        st.markdown(f"**Line {number}** · {headline}")

                if st.button(
                    "Generate Top-5 audio",
                    type="primary",
                    width="stretch",
                    key="test-top5-audio-generate",
                    disabled=(is_t5_chatterbox and t5_language != "English") or (is_t5_chatterbox and not t5_reference_ready),
                ):
                    with st.spinner("Generating the six spoken Top-5 lines…"):
                        try:
                            selected_t5 = dict(handoff)
                            selected_t5["language_used"] = t5_language.casefold()
                            selected_t5["voice_gender"] = t5_gender.casefold()
                            selected_t5["voice"] = t5_voice
                            selected_t5["voice_engine"] = "chatterbox" if is_t5_chatterbox else "edge"
                            st.session_state.test_top5_audio_data = generate_top5_audio(
                                selected_t5,
                                voice=t5_voice,
                                engine="chatterbox" if is_t5_chatterbox else "edge",
                                reference=t5_reference if is_t5_chatterbox else None,
                            )
                            st.session_state.test_top5_audio_handoff = None
                            st.rerun()
                        except (RuntimeError, ValueError) as exc:
                            st.session_state.test_top5_audio_data = None
                            st.session_state.test_top5_audio_handoff = None
                            st.error(str(exc))

                with st.expander("🎙️ Human voiceover / mic upload (per-line override)", expanded=False):
                    st.caption("Upload an MP3/WAV file to override TTS for any line. Word timings will be synthesized linearly.")
                    t5_slides = handoff.get("slides") or []
                    if t5_slides:
                        override_line_num = st.selectbox("Select line to override", list(range(1, 7)), key="test_top5_human_line_select")
                        t5_uploaded_file = st.file_uploader("Upload audio (.mp3, .wav)", type=["mp3", "wav"], key=f"test_top5_human_audio_{override_line_num}")
                        if t5_uploaded_file is not None and st.button("Apply human audio to line", key=f"test_top5_apply_human_{override_line_num}"):
                            from pathlib import Path
                            out_t5_dir = Path("output/audio_top5_test")
                            out_t5_dir.mkdir(parents=True, exist_ok=True)
                            temp_t5_path = out_t5_dir / f"human_input_line_{override_line_num}.mp3"
                            with open(temp_t5_path, "wb") as f_out:
                                f_out.write(t5_uploaded_file.getbuffer())
                            line_text = ""
                            for s in t5_slides:
                                if int(s.get("slide_number", 0)) == override_line_num:
                                    line_text = s.get("headline", "")
                                    break
                            try:
                                pkg = package_human_audio(override_line_num, temp_t5_path, line_text, out_t5_dir)
                                if st.session_state.test_top5_audio_data and "scenes" in st.session_state.test_top5_audio_data:
                                    curr = list(st.session_state.test_top5_audio_data["scenes"])
                                    for i, sc in enumerate(curr):
                                        if int(sc.get("scene", 0)) == override_line_num:
                                            curr[i] = pkg
                                            break
                                    st.session_state.test_top5_audio_data["scenes"] = curr
                                    st.session_state.test_top5_audio_data["total_duration"] = round(sum(float(sc["duration"]) for sc in curr), 3)
                                    st.session_state.test_top5_audio_handoff = None
                                    st.success(f"Line {override_line_num} overridden with human audio!")
                                    st.rerun()
                            except Exception as err:
                                st.error(f"Failed to package human audio: {err}")

                audio = st.session_state.get("test_top5_audio_data")
                if audio:
                    for scene in audio["scenes"]:
                        with st.container(key=f"test-top5-audio-scene-{scene['scene']}"):
                            st.markdown(
                                f'**Line {scene["scene"]}** '
                                f'<span class="topic-meta">· {scene["duration"]:.2f}s · '
                                f'{len(scene["timings"])} timings</span>',
                                unsafe_allow_html=True,
                            )
                            st.audio(
                    scene["path"],
                    format="audio/wav" if str(scene["path"]).lower().endswith(".wav") else "audio/mp3",
                )
                            st.caption("Human Audio" if scene.get("human_recorded") else ("Cached" if scene["from_cache"] else "Fresh TTS generation"))

                    st.caption(
                        f'Voice: {audio["voice"]} · Rate: {audio["rate_percent"]:+.0f}% · '
                        f'Total: {audio["total_duration"]:.2f}s · '
                        f'Longest line: {audio["max_scene_duration"]:.2f}s'
                    )

                    if st.button(
                        "Approve Top-5 audio",
                        type="primary",
                        width="stretch",
                        key="test-top5-audio-approve",
                    ):
                        try:
                            st.session_state.test_top5_audio_handoff = approve_top5_audio(audio)
                            st.session_state.test_stage = "04 · Visuals"
                            st.session_state.test_pipeline_notice = {
                                "confirmed": "Top-5 Audio QC confirmed",
                                "next": "Moving to Visuals.",
                            }
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

                if st.session_state.get("test_top5_audio_handoff"):
                    st.success("Top-5 Audio approved. All six spoken lines are ready for the next stage.")
        elif line_name == "Top-5" and stage == "04 · Visuals":
            from renderer import (
                build_top5_card_preview,
                build_manual_subject_cutout_preview,
            )
            from visual_fetcher import crawl_visuals, manual_crawl_visuals
            from visual_search import search_images
            from visual_generator import generate_images

            if "test_top5_visual_playground_headline" not in st.session_state:
                st.session_state.test_top5_visual_playground_headline = "TOP FIVE CRICKET STORIES YOU NEED TO KNOW TODAY"
            if "test_top5_visual_playground_body" not in st.session_state:
                st.session_state.test_top5_visual_playground_body = ""
            if "test_top5_visual_playground_image" not in st.session_state:
                st.session_state.test_top5_visual_playground_image = None
            if "test_top5_visual_playground_source" not in st.session_state:
                st.session_state.test_top5_visual_playground_source = "Test green canvas"
            if "test_top5_visual_playground_render" not in st.session_state:
                st.session_state.test_top5_visual_playground_render = None
            st.session_state.setdefault(
                "test_top5_visual_playground_option",
                TOP5_VISUAL_OPTIONS[2],
            )
            for key, default in (
                ("test_top5_visual_playground_url", ""),
                ("test_top5_visual_playground_query", ""),
                ("test_top5_visual_playground_quote", ""),
                ("test_top5_visual_playground_attribution", ""),
                ("test_top5_visual_playground_stats_query", ""),
            ):
                st.session_state.setdefault(key, default)

            st.markdown(
                '<div class="section-head"><div><div class="eyebrow">TOP-5 · 04 · VISUALS</div>'
                '<div class="section-title">Standalone Visual QC</div>'
                '<div class="canvas-copy">Test every Top-5 visual option independently. No Scriptwriter approval or earlier stage is required.</div></div>'
                '<div class="section-count">5 visual options</div></div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="mini-label">5 VISUAL OPTIONS</div>', unsafe_allow_html=True)
            visual_option = _render_visual_option_grid(
                TOP5_VISUAL_OPTIONS,
                session_key="test_top5_visual_playground_option",
                button_prefix="test-top5-playground-visual-source",
            )

            image_col, editor_col = st.columns([.85, 1.15], gap="large")
            with image_col:
                current_image = st.session_state.test_top5_visual_playground_image
                if current_image is None:
                    current_image = Image.new("RGB", (1080, 1920), (34, 122, 70))
                    current_source = "Test green canvas"
                else:
                    current_source = st.session_state.test_top5_visual_playground_source
                st.markdown('<div class="mini-label">CURRENT IMAGE</div>', unsafe_allow_html=True)
                st.image(current_image, width=320)
                st.caption(current_source)

            with editor_col:
                st.markdown('<div class="mini-label">APPROVED VISUAL COPY</div>', unsafe_allow_html=True)
                st.text_area(
                    "Headline",
                    key="test_top5_visual_playground_headline",
                    height=82,
                )
                if visual_option != "Option 5 · Card Studio":
                    st.text_area(
                        "Body",
                        key="test_top5_visual_playground_body",
                        height=140,
                    )

            assets = []
            if visual_option == "Option 1 · Automatic Scraper":
                url = st.text_input(
                    "Story URL",
                    key="test_top5_visual_playground_url",
                    placeholder="https://publisher.com/article",
                )
                if st.button("Run automatic scrape", type="primary", width="stretch", key="test-top5-playground-auto"):
                    url = url.strip()
                    if not url:
                        st.warning("Enter a story URL first.")
                    else:
                        with st.spinner("Scraping the supplied story URL…"):
                            try:
                                result = crawl_visuals({
                                    "url": url,
                                    "title": st.session_state.test_top5_visual_playground_headline,
                                    "description": st.session_state.test_top5_visual_playground_body,
                                    "specific_search_prompt": st.session_state.test_top5_visual_playground_headline,
                                })
                                st.session_state.test_top5_visual_playground_results = list(result.get("assets") or [])
                                error = str(result.get("error") or "").strip()
                                if error:
                                    st.error(error)
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_results = []
                                st.error(f"{type(exc).__name__}: {exc}")
                assets = list(st.session_state.get("test_top5_visual_playground_results") or [])

            elif visual_option == "Option 2 · Manual Scraper":
                query = st.text_input(
                    "Manual scrape query",
                    key="test_top5_visual_playground_crawler_query",
                    placeholder="Virat Kohli latest cricket news",
                )
                if st.button("Run manual scrape", type="primary", width="stretch", key="test-top5-playground-manual"):
                    query = query.strip()
                    if not query:
                        st.warning("Enter a query first.")
                    else:
                        with st.spinner("Searching and scraping publisher pages…"):
                            try:
                                result = manual_crawl_visuals(query)
                                st.session_state.test_top5_visual_playground_results = list(result.get("assets") or [])
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_results = []
                                st.error(f"{type(exc).__name__}: {exc}")
                assets = list(st.session_state.get("test_top5_visual_playground_results") or [])

            elif visual_option == "Option 3 · Manual Fetcher":
                query = st.text_input(
                    "Manual image query",
                    key="test_top5_visual_playground_search_query",
                    placeholder="Virat Kohli batting India cricket",
                )
                if st.button("Fetch images", type="primary", width="stretch", key="test-top5-playground-manual-fetch"):
                    query = query.strip()
                    if not query:
                        st.warning("Enter an image query first.")
                    else:
                        with st.spinner("Fetching manual image options…"):
                            try:
                                result = search_images(query)
                                st.session_state.test_top5_visual_playground_results = list(result.get("assets") or [])
                                errors = result.get("errors") or {}
                                if errors:
                                    st.caption("Some configured image sources failed; successful results are still shown.")
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_results = []
                                st.error(f"{type(exc).__name__}: {exc}")
                assets = list(st.session_state.get("test_top5_visual_playground_results") or [])

            elif visual_option == "Option 4 · AI Generation":
                providers_label = ["Pollinations.ai (Flux)"]
                if os.getenv("HF_TOKEN"):
                    providers_label.append("Hugging Face")
                if os.getenv("CLOUDFLARE_API_TOKEN") and os.getenv("CLOUDFLARE_ACCOUNT_ID"):
                    providers_label.append("Cloudflare Workers AI")
                st.caption(f"Manual prompt only. Active AI providers: {', '.join(providers_label)}.")
                prompt = st.text_area(
                    "AI image prompt",
                    key="test_top5_visual_playground_ai_query",
                    height=100,
                    placeholder="Virat Kohli in a packed cricket stadium, editorial sports photography",
                )
                if st.button("Generate images", type="primary", width="stretch", key="test-top5-playground-ai"):
                    prompt = prompt.strip()
                    if not prompt:
                        st.warning("Enter an image prompt first.")
                    else:
                        with st.spinner("Generating images…"):
                            try:
                                result = generate_images(prompt)
                                st.session_state.test_top5_visual_playground_results = list(result.get("assets") or [])
                                if not st.session_state.test_top5_visual_playground_results:
                                    st.warning("No configured AI provider returned an image.")
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_results = []
                assets = list(st.session_state.get("test_top5_visual_playground_results") or [])

            elif visual_option == "Option 5 · Card Studio":
                _render_card_studio(
                    top5=True,
                    current_image=current_image,
                    current_source=current_source,
                )

            if assets:
                st.markdown(
                    '<div class="section-head"><div><div class="eyebrow">IMAGE POOL</div>'
                    '<div class="section-title">Choose the source image</div></div>'
                    f'<div class="section-count">{len(assets)} images</div></div>',
                    unsafe_allow_html=True,
                )
                with st.container(height=520):
                    for start in range(0, len(assets), 4):
                        cols = st.columns(min(4, len(assets) - start), gap="small")
                        for offset, asset in enumerate(assets[start:start + 4]):
                            with cols[offset]:
                                index = start + offset
                                raw = asset.get("bytes")
                                source = str(asset.get("publisher") or asset.get("source") or asset.get("model") or "Web source").strip()
                                label = str(asset.get("article_title") or asset.get("title") or asset.get("model") or "Selected visual").strip()
                                asset_key = _visual_asset_key(f"playground-{visual_option}", index, asset)
                                cropped = st.session_state.test_top5_visual_crops.get(asset_key)
                                preview_source = cropped if cropped else raw
                                preview = _top5_fit_preview(preview_source)
                                if preview is not None:
                                    st.image(preview, width="stretch")
                                st.markdown(
                                    f'<div class="visual-source">{source}</div>'
                                    f'<div class="visual-detail">{label}</div>',
                                    unsafe_allow_html=True,
                                )
                                if cropped:
                                    st.markdown('<span class="visual-crop-label">CROP APPLIED</span>', unsafe_allow_html=True)
                                choose_col, crop_col = st.columns(2, gap="small")
                                with choose_col:
                                    if st.button(
                                        "Use this image",
                                        type="primary",
                                        width="stretch",
                                        key=f"test-top5-playground-use-{visual_option}-{index}",
                                    ):
                                        selected_bytes = bytes(cropped) if cropped else bytes(raw or b"")
                                        selected = _asset_to_image(selected_bytes)
                                        if selected is not None:
                                            st.session_state.test_top5_visual_playground_image = selected
                                            st.session_state.test_top5_visual_playground_source = source
                                            st.session_state.test_top5_visual_playground_render = None
                                            st.rerun()
                                        else:
                                            st.warning("This image could not be decoded.")
                                with crop_col:
                                    if st.button(
                                        "Crop / reposition",
                                        width="stretch",
                                        key=f"test-top5-playground-crop-{visual_option}-{index}",
                                    ):
                                        if isinstance(raw, (bytes, bytearray)):
                                            _crop_visual_dialog(asset_key, bytes(raw), label, crop_store="test_top5_visual_crops")
                                        else:
                                            st.warning("This image is not crop-ready.")

            if visual_option in TOP5_VISUAL_OPTIONS[:4] and current_image is not None:
                if st.button("Render current image with card typography", type="primary", width="stretch", key="test-top5-playground-render-current"):
                    try:
                        st.session_state.test_top5_visual_playground_render = build_top5_card_preview(
                            current_image,
                            st.session_state.test_top5_visual_playground_headline,
                            st.session_state.test_top5_visual_playground_body,
                            story_number=1,
                            total_stories=5,
                            source_label=current_source,
                        )
                    except (ValueError, OSError) as exc:
                        st.session_state.test_top5_visual_playground_render = None
                        st.error(str(exc))

            rendered = st.session_state.test_top5_visual_playground_render
            if rendered:
                st.markdown(
                    '<div class="section-head"><div><div class="eyebrow">RENDERED PREVIEW</div>'
                    '<div class="section-title">Exact current Top-5 visual</div></div>'
                    '<div class="section-count">1080 × 1920</div></div>',
                    unsafe_allow_html=True,
                )
                st.image(rendered, width=280)

            else:
                script = st.session_state.get("test_top5_script_handoff") or {}
                slides = list(script.get("slides") or [])
                stories = list(script.get("stories") or [])
                if len(slides) != 6:
                    st.info("Standalone Visual QC is active above. The six-slide production QC appears after the Top-5 Scriptwriter handoff is approved.")
                else:
                    st.markdown(
                        '<div class="section-head"><div><div class="eyebrow">TOP-5 · 04 · VISUALS</div>'
                        '<div class="section-title">Build and review all six slides</div>'
                        '<div class="canvas-copy">Every slide uses the approved Scriptwriter handoff. Choose from the same visual options available to Cricket, crop/reposition when needed, review the actual rendered slide, then approve all six for Renderer.</div></div>'
                        '<div class="section-count">6 slides · full visual QC</div></div>',
                        unsafe_allow_html=True,
                    )

                    assignments = st.session_state.test_top5_visual_assignments
                    st.caption(
                        f"{len(assignments)}/6 slides attached. The preview shown for each attached slide is the actual static 1080 × 1920 frame handed to Renderer."
                    )

                    slide_labels = [f"Slide {number}" for number in range(1, 7)]
                    active_label = st.pills(
                        "Top-5 slide",
                        slide_labels,
                        default=slide_labels[0],
                        key="test-top5-active-visual-slide",
                        label_visibility="collapsed",
                    ) or slide_labels[0]
                    active_slide = slide_labels.index(active_label) + 1
                    slide = slides[active_slide - 1]
                    headline = str(slide.get("headline") or "").strip()
                    body = str(slide.get("body") or "").strip()
                    visual_intent = str(slide.get("visual_intent") or "").strip()
                    specific_prompt = str(slide.get("specific_search_prompt") or "").strip()

                    st.markdown(
                        f'<div class="mini-label">SLIDE {active_slide} · '
                        f'{"PACKAGE OPENER" if active_slide == 1 else f"STORY {active_slide - 1}"} · APPROVED SCRIPT</div>',
                        unsafe_allow_html=True,
                    )
                    if active_slide > 1:
                        story = stories[active_slide - 2] if len(stories) >= active_slide - 1 else {}
                        st.markdown(
                            f'<div class="topic-meta">{story.get("title") or "Selected story"}</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(f"**{headline}**")
                    if body:
                        st.caption(f"Visual body: {body}")
                    if visual_intent:
                        st.caption(f"Visual intent: {visual_intent}")
                    if specific_prompt:
                        st.caption(f"Script visual search prompt: {specific_prompt}")

                    visual_option = _render_visual_option_grid(
                        TOP5_VISUAL_OPTIONS,
                        session_key="test_top5_visual_option",
                        button_prefix="test-top5-production-visual-source",
                    )

                    def _top5_asset_source(asset):
                        return str(
                            asset.get("publisher")
                            or asset.get("source")
                            or asset.get("model")
                            or "Web source"
                        ).strip() or "Web source"

                    def _top5_asset_label(asset):
                        return str(
                            asset.get("article_title")
                            or asset.get("title")
                            or asset.get("model")
                            or "Selected visual"
                        ).strip() or "Selected visual"

                    def _top5_store_assignment(
                        source_asset,
                        source_bytes,
                        result_key,
                        source,
                        label,
                        *,
                        card_type="editorial",
                        card_data=None,
                        preview_bytes=None,
                        headline_text=None,
                        body_text=None,
                        subject_cutout=False,
                        manual_subject_cutout=None,
                    ):
                        image = _asset_to_image(source_bytes)
                        if image is None:
                            st.warning("This visual could not be decoded as an image.")
                            return False

                        buffer = BytesIO()
                        image.save(buffer, format="JPEG", quality=94, optimize=True)
                        selected_bytes = buffer.getvalue()
                        selected_headline = str(headline_text if headline_text is not None else headline).strip()
                        selected_body = str(body_text if body_text is not None else body).strip()
                        story_number = 0 if active_slide == 1 else active_slide - 1
                        assignment = {
                            "asset_key": str(
                                source_asset.get("asset_key")
                                if isinstance(source_asset, dict) and source_asset.get("asset_key")
                                else f"top5-{active_slide}-{hashlib.sha1((label + source).encode('utf-8')).hexdigest()[:12]}"
                            ),
                            "result_key": result_key,
                            "source": source,
                            "label": label,
                            "bytes": selected_bytes,
                        }

                        if card_type == "manual-subject" and isinstance(card_data, dict):
                            assignment["manual_subject_cutout"] = dict(card_data)
                        elif card_type == "card-studio" and isinstance(card_data, dict):
                            assignment["card_studio"] = dict(card_data)
                        else:
                            assignment["top5_card"] = {
                                "headline": selected_headline,
                                "body": selected_body,
                                "story_number": story_number,
                                "total_stories": 5,
                                "language": str(script.get("language_used") or "english").casefold(),
                                "subject_cutout": bool(subject_cutout),
                            }

                        if preview_bytes is None and card_type == "editorial":
                            try:
                                preview_bytes = build_top5_card_preview(
                                    selected_bytes,
                                    selected_headline,
                                    selected_body,
                                    story_number=story_number,
                                    total_stories=5,
                                    source_label=source,
                                    subject_cutout=subject_cutout,
                                )
                            except Exception:
                                preview_bytes = None
                        elif preview_bytes is None and card_type == "manual-subject" and isinstance(card_data, dict):
                            try:
                                preview_bytes = build_manual_subject_cutout_preview(
                                    selected_bytes,
                                    str(card_data.get("headline") or selected_headline),
                                    mode=str(card_data.get("mode") or "negative-space"),
                                    text_polygon=card_data.get("text_polygon") or (),
                                    font_size=int(card_data.get("font_size") or 150),
                                    font=str(card_data.get("font") or "Barlow Condensed"),
                                    style=str(card_data.get("style") or "Crisp Outline"),
                                    polygon_flow=True,
                                )
                            except Exception:
                                preview_bytes = None

                        if preview_bytes:
                            assignment["preview_bytes"] = bytes(preview_bytes)
                        st.session_state.test_top5_visual_assignments[active_slide] = assignment
                        st.session_state.test_top5_visual_previews[active_slide] = bytes(preview_bytes or selected_bytes)
                        st.session_state.test_top5_visual_handoff = None
                        st.session_state.test_top5_rendered_video_path = None
                        return True

                    def _top5_render_asset_pool(assets, result_key, subject_cutout=False):
                        if not assets:
                            st.info("No images are currently available from this option.")
                            return
                        st.markdown(
                            f'<div style="display:flex;align-items:center;justify-content:space-between;margin:0.35rem 0 0.55rem 0;font-size:0.75rem;color:var(--muted);">'
                            f'<span><strong>{len(assets)} images in pool</strong> · scroll inside tray to browse</span>'
                            f'<span>Choose for slide {active_slide}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.container(height=520):
                            for start_index in range(0, len(assets), 4):
                                cols = st.columns(4, gap="small")
                                for offset, asset in enumerate(assets[start_index:start_index + 4]):
                                    index = start_index + offset
                                    with cols[offset]:
                                        raw = asset.get("bytes")
                                        source = _top5_asset_source(asset)
                                        label = _top5_asset_label(asset)
                                        asset_key = _visual_asset_key(result_key, index, asset)
                                        cropped = st.session_state.test_top5_visual_crops.get(asset_key)
                                        preview_bytes = cropped if cropped else raw
                                        preview = _top5_fit_preview(preview_bytes, 240, 360)
                                        with st.container(key=f"test-top5-visual-card-{active_slide}-{result_key}-{index}"):
                                            if preview is not None:
                                                st.image(preview, width="stretch")
                                            st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                                            if label:
                                                st.markdown(f'<div class="visual-detail">{label}</div>', unsafe_allow_html=True)
                                            if cropped:
                                                st.markdown('<span class="visual-crop-label">CROP APPLIED</span>', unsafe_allow_html=True)

                                            choose_col, crop_col = st.columns(2, gap="small")
                                            with choose_col:
                                                if st.button(
                                                    "Use this image",
                                                    type="primary",
                                                    width="stretch",
                                                    key=f"test-top5-use-{active_slide}-{result_key}-{index}",
                                                ):
                                                    working_bytes = bytes(cropped) if cropped else bytes(raw or b"")
                                                    _top5_store_assignment(
                                                        asset,
                                                        working_bytes,
                                                        result_key,
                                                        source,
                                                        label,
                                                        subject_cutout=subject_cutout,
                                                    )
                                                    st.rerun()
                                            with crop_col:
                                                if st.button(
                                                    "Crop / reposition",
                                                    width="stretch",
                                                    key=f"test-top5-crop-{active_slide}-{result_key}-{index}",
                                                ):
                                                    if isinstance(raw, (bytes, bytearray)):
                                                        _crop_visual_dialog(asset_key, bytes(raw), label, crop_store="test_top5_visual_crops")
                                                    else:
                                                        st.warning("This image is not crop-ready.")

                    def _top5_active_story_payload():
                        story_index = active_slide - 2
                        source_story = (
                            stories[story_index]
                            if 0 <= story_index < len(stories)
                            else (stories[0] if stories else {})
                        )
                        return {
                            "title": str(source_story.get("title") or "").strip(),
                            "description": str(source_story.get("description") or "").strip(),
                            "url": str(source_story.get("url") or "").strip(),
                            "source": str(source_story.get("source") or "").strip(),
                            "published_at": str(source_story.get("published_at") or "").strip(),
                            "primary_entity": str(slide.get("primary_entity") or "").strip(),
                            "specific_search_prompt": specific_prompt,
                            "visual_intent": visual_intent,
                        }

                    if visual_option == "Option 1 · Automatic Scraper":
                        result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        if not result or result.get("source") != "automatic":
                            st.caption(
                                "Automatic Scraper uses the approved story URL and the Scriptwriter's visual prompt. "
                                "For Slide 1, the first selected story is used as the crawl source because the opener has no single article URL."
                            )
                            if st.button(
                                "Run automatic scrape",
                                type="primary",
                                width="stretch",
                                key=f"test-top5-auto-run-{active_slide}",
                            ):
                                story_payload = _top5_active_story_payload()
                                if not story_payload.get("url"):
                                    st.warning("The selected story has no usable source URL for automatic scraping.")
                                else:
                                    with st.spinner("Scraping the approved story and related publisher pages…"):
                                        try:
                                            from visual_fetcher import crawl_visuals
                                            auto = crawl_visuals(story_payload)
                                            st.session_state.test_top5_visual_results[active_slide] = {
                                                "source": "automatic",
                                                "query": specific_prompt,
                                                "assets": list(auto.get("assets") or []),
                                                "error": str(auto.get("error") or ""),
                                            }
                                        except Exception as exc:
                                            st.session_state.test_top5_visual_results[active_slide] = {
                                                "source": "automatic",
                                                "query": specific_prompt,
                                                "assets": [],
                                                "error": f"{type(exc).__name__}: {exc}",
                                            }
                                    st.rerun()
                        if result.get("error"):
                            st.error(result["error"])
                        elif result:
                            st.caption(f'{len(result.get("assets") or [])} images returned by the automatic scraper.')
                            _top5_render_asset_pool(list(result.get("assets") or []), "auto")

                    if visual_option == "Option 2 · Manual Scraper":
                        st.caption("Same Manual Scraper used by Cricket: manual query → publisher-page search → scraped image pool.")
                        query = st.text_input(
                            "Manual query",
                            value=specific_prompt,
                            key=f"test-top5-manual-query-{active_slide}",
                        )
                        if st.button(
                            "Run manual scrape",
                            type="primary",
                            width="stretch",
                            key=f"test-top5-manual-run-{active_slide}",
                        ):
                            query = query.strip()
                            if not query:
                                st.warning("Enter a query first.")
                            else:
                                with st.spinner("Searching and scraping publisher pages…"):
                                    try:
                                        from visual_fetcher import manual_crawl_visuals
                                        result = manual_crawl_visuals(query)
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "manual",
                                            "query": query,
                                            "assets": list(result.get("assets") or []),
                                            "error": str(result.get("error") or ""),
                                        }
                                    except Exception as exc:
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "manual",
                                            "query": query,
                                            "assets": [],
                                            "error": f"{type(exc).__name__}: {exc}",
                                        }
                                    st.rerun()
                        result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        if result.get("source") == "manual":
                            if result.get("error"):
                                st.error(result["error"])
                            else:
                                st.caption(f'{len(result.get("assets") or [])} images returned by the Manual Scraper.')
                                _top5_render_asset_pool(list(result.get("assets") or []), "manual")

                    if visual_option == "Option 3 · Manual Fetcher":
                        st.caption("Manual image query → real-image provider results. This option only fetches the image pool.")
                        query = st.text_input(
                            "Manual image query",
                            value=specific_prompt,
                            key=f"test-top5-manual-fetch-query-{active_slide}",
                        )
                        if st.button(
                            "Fetch images",
                            type="primary",
                            width="stretch",
                            key=f"test-top5-manual-fetch-run-{active_slide}",
                        ):
                            query = query.strip()
                            if not query:
                                st.warning("Enter an image query first.")
                            else:
                                with st.spinner("Fetching manual image options…"):
                                    try:
                                        result = search_images(query)
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "manual-fetch",
                                            "query": query,
                                            "assets": list(result.get("assets") or []),
                                            "error": "",
                                        }
                                    except Exception as exc:
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "manual-fetch",
                                            "query": query,
                                            "assets": [],
                                            "error": f"{type(exc).__name__}: {exc}",
                                        }
                                st.rerun()
                        result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        if result.get("source") == "manual-fetch":
                            if result.get("error"):
                                st.error(result["error"])
                            else:
                                st.caption(f'{len(result.get("assets") or [])} images returned by the Manual Fetcher.')
                                _top5_render_asset_pool(list(result.get("assets") or []), "manual-fetch")

                    if visual_option == "Option 4 · AI Generation":
                        st.caption("Same AI Generation used by Cricket: manual prompt across the configured AI image providers.")
                        query = st.text_input(
                            "AI prompt",
                            value=specific_prompt,
                            key=f"test-top5-ai-query-{active_slide}",
                        )
                        if st.button(
                            "Generate images",
                            type="primary",
                            width="stretch",
                            key=f"test-top5-ai-run-{active_slide}",
                        ):
                            query = query.strip()
                            if not query:
                                st.warning("Enter an AI prompt first.")
                            else:
                                with st.spinner("Generating AI image options…"):
                                    try:
                                        from visual_generator import generate_images
                                        result = generate_images(query)
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "ai",
                                            "query": query,
                                            "assets": list(result.get("assets") or []),
                                            "error": str(result.get("error") or ""),
                                        }
                                    except Exception as exc:
                                        st.session_state.test_top5_visual_results[active_slide] = {
                                            "source": "ai",
                                            "query": query,
                                            "assets": [],
                                            "error": f"{type(exc).__name__}: {exc}",
                                        }
                                    st.rerun()
                        result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        if result.get("source") == "ai":
                            if result.get("error"):
                                st.error(result["error"])
                            else:
                                st.caption(f'{len(result.get("assets") or [])} AI images returned.')
                                _top5_render_asset_pool(list(result.get("assets") or []), "ai")

                    if visual_option == "Option 5 · Card Studio":
                        _render_card_studio(top5=True, active_slide=active_slide)

                    current_assignment = assignments.get(active_slide)
                    if current_assignment:
                        preview_bytes = current_assignment.get("preview_bytes") or current_assignment.get("bytes")
                        st.divider()
                        st.markdown('<div class="mini-label">CURRENT ATTACHMENT · ACTUAL RENDER</div>', unsafe_allow_html=True)
                        col_attach_prev, col_attach_info = st.columns([1, 1], gap="medium")
                        with col_attach_prev:
                            if preview_bytes:
                                st.image(preview_bytes, width=280)
                        with col_attach_info:
                            st.caption(
                                f'**Source:** {current_assignment.get("source") or "Visual"}\n\n'
                                f'**Label:** {current_assignment.get("label") or "Selected"}\n\n'
                                "This exact rendered frame will be handed to Renderer."
                            )
                            if st.button(
                                f"Clear attached slide {active_slide}",
                                width="stretch",
                                key=f"test-top5-clear-attached-{active_slide}",
                            ):
                                st.session_state.test_top5_visual_assignments.pop(active_slide, None)
                                st.session_state.test_top5_visual_previews.pop(active_slide, None)
                                st.session_state.test_top5_visual_handoff = None
                                st.session_state.test_top5_rendered_video_path = None
                                st.rerun()

                    st.divider()
                    st.markdown(
                        f'<div class="section-head"><div><div class="eyebrow">VISUAL HANDOFF</div>'
                        f'<div class="section-title">{len(assignments)}/6 slides ready</div></div>'
                        f'<div class="section-count">actual render previews</div></div>',
                        unsafe_allow_html=True,
                    )

                    board_cols = st.columns(3, gap="medium")
                    for number in range(1, 7):
                        with board_cols[(number - 1) % 3]:
                            item = assignments.get(number)
                            board_preview = item.get("preview_bytes") if item else None
                            with st.container(key=f"test-top5-final-board-{number}"):
                                st.markdown(f'<div class="eyebrow">SLIDE {number}</div>', unsafe_allow_html=True)
                                board_slide = slides[number - 1]
                                board_headline = str(board_slide.get("headline") or "").strip()
                                st.markdown(f"**{board_headline}**")
                                board_body = str(board_slide.get("body") or "").strip()
                                if board_body:
                                    st.caption(board_body)
                                if board_preview:
                                    st.image(board_preview, width="stretch")
                                    st.caption(item.get("source") or "Attached visual")
                                    if st.button(
                                        "Edit this slide",
                                        width="stretch",
                                        key=f"test-top5-final-board-edit-{number}",
                                    ):
                                        st.session_state["test-top5-active-visual-slide"] = f"Slide {number}"
                                        st.rerun()
                                else:
                                    st.markdown('<div class="empty-slot">NOT ATTACHED</div>', unsafe_allow_html=True)

                    if len(assignments) == 6:
                        if st.button(
                            "Approve Top-5 visuals",
                            type="primary",
                            width="stretch",
                            key="test-top5-approve-visuals",
                        ):
                            st.session_state.test_top5_visual_handoff = [
                                assignments[number] for number in range(1, 7)
                            ]
                            st.session_state.test_top5_rendered_video_path = None
                            st.session_state.test_top5_upload_qc_approved = False
                            st.session_state.test_top5_upload_qc = None
                            st.session_state.test_top5_upload_description = ""
                            st.session_state.test_top5_upload_hashtags = ""
                            st.session_state.test_top5_upload_comment = ""
                            st.session_state.test_top5_upload_result = None
                            st.session_state.test_stage = "06 · Renderer"
                            st.session_state.test_pipeline_notice = {
                                "confirmed": "Top-5 Visual QC confirmed",
                         
       "next": "Moving to Renderer.",
                            }
                            st.rerun()

        elif line_name == "Top-5" and stage == "06 · Renderer":
            render_top5_renderer_test()
        elif line_name == "Top-5" and stage == "07 · Upload QC":
            render_top5_upload_qc()
        else:
            stage_labels = {
                "01 · Topic Fetcher": "Topic Fetcher",
                "02 · Scriptwriter": "Scriptwriter",
                "03 · Audio": "Audio",
                "04 · Visuals": "Visuals",
                "05 · Subtitles": "Subtitles",
                "06 · Renderer": "Renderer",
                "07 · Upload QC": "Upload QC",
            }
            stage_label = stage_labels[stage]
            st.markdown(
                f'<div class="section-head"><div><div class="eyebrow">{line_name.upper()} · {stage.split(" · ")[0]}</div>'
                f'<div class="section-title">{stage_label}</div></div>'
                f'<div class="section-count">shared factory stage</div></div>',
                unsafe_allow_html=True,
            )
            st.info(
                f"{line_name} uses the existing {stage_label} stage. "
                "The line-specific behaviour is what we are designing in Test before moving it to Live."
            )
elif st.session_state.app_mode == "live":
    _render_app_sidebar()
    if st.session_state.get("factory_format") == "long_form":
        render_longform_live()
    else:
        render_live_dashboard()
