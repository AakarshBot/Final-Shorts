from __future__ import annotations
import base64
import hashlib
import json
from io import BytesIO
from dataclasses import replace
from PIL import Image
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
import streamlit as st

load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)


st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

VISUAL_OPTIONS = (
    "Option 1 · Automatic Scraper",
    "Option 2 · Manual Scraper",
    "Option 3 · Real Image Search",
    "Option 4 · AI Generation",
    "Option 5 · Stats Card",
    "Option 6 · Quote Card",
)
CRICKET_TEST_VISUAL_OPTIONS = VISUAL_OPTIONS + ("Option 7 · Text Cutout",)
CRICKET_LIVE_VISUAL_OPTIONS = CRICKET_TEST_VISUAL_OPTIONS
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
    "Option 5 · Stats Card",
    "Option 6 · Quote Card",
    "Option 7 · Subject Cutout",
    "Option 8 · Body Card · WIP",
    "Option 9 · Manual Subject Cutout",
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
:root{
  --bg:#f3f2ed;
  --surface:#fffefa;
  --surface-raised:#ffffff;
  --surface-soft:#f7f6f1;
  --surface-selected:#eef3ef;
  --ink:#151713;
  --muted:#52574f;
  --subtle:#686e66;
  --line:#dddcd4;
  --line-strong:#bfc0b7;
  --primary:#171916;
  --primary-hover:#000000;
  --accent:#2f6255;
  --accent-soft:#eaf0ed;
  --success:#2f6b4f;
  --success-soft:#edf5ef;
  --warning:#8a5b16;
  --warning-soft:#faf4e7;
  --danger:#a23b31;
  --danger-soft:#faeeeb;
  --focus:#315f8e;
  --shadow:0 1px 2px rgba(21,23,19,.04),0 6px 20px rgba(21,23,19,.045);
  --shadow-hover:0 8px 24px rgba(21,23,19,.08);
}
html,body,.stApp{
  font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:var(--ink);
  background:var(--bg);
}
[data-testid="stAppViewContainer"]{background:var(--bg);}
[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{display:none!important;}
footer,#MainMenu{visibility:hidden;}
.block-container{max-width:1440px;padding:22px 30px 54px;}
h1,h2,h3,h4,h5,h6{color:var(--ink)!important;letter-spacing:-.035em;}
h1{font-weight:850;} h2,h3{font-weight:800;}
p{color:var(--muted);}
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] small{color:var(--muted)!important;}
[data-testid="stMarkdownContainer"] strong{color:var(--ink);}
button{font-family:inherit;transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease,background .12s ease;}
[data-testid="stButton"]>button,
[data-testid="stFormSubmitButton"]>button{
  min-height:42px;
  border-radius:10px!important;
  border:1px solid var(--line-strong)!important;
  background:var(--surface-raised)!important;
  color:var(--ink)!important;
  font-weight:760!important;
  box-shadow:0 1px 2px rgba(21,23,19,.03)!important;
}
[data-testid="stButton"]>button:hover,
[data-testid="stFormSubmitButton"]>button:hover{
  transform:translateY(-1px);
  border-color:#9fa197!important;
  background:#fff!important;
  box-shadow:0 5px 14px rgba(21,23,19,.07)!important;
}
[data-testid="stButton"]>button:focus-visible,
[data-testid="stFormSubmitButton"]>button:focus-visible{
  outline:2px solid var(--focus)!important;
  outline-offset:2px;
}
[data-testid="stButton"]>button[kind="primary"],
[data-testid="stButton"]>button[data-testid="baseButton-primary"],
[data-testid="stFormSubmitButton"]>button[kind="primary"],
[data-testid="stFormSubmitButton"]>button[data-testid="baseButton-primary"]{
  background:var(--primary)!important;
  border-color:var(--primary)!important;
  color:#ffffff!important;
  text-shadow:none!important;
  box-shadow:0 5px 14px rgba(21,23,19,.12)!important;
}
[data-testid="stButton"]>button[kind="primary"] *,
[data-testid="stButton"]>button[data-testid="baseButton-primary"] *,
[data-testid="stFormSubmitButton"]>button[kind="primary"] *,
[data-testid="stFormSubmitButton"]>button[data-testid="baseButton-primary"] *{
  color:#ffffff!important;
}
[data-testid="stButton"]>button[kind="primary"]:hover,
[data-testid="stButton"]>button[data-testid="baseButton-primary"]:hover,
[data-testid="stFormSubmitButton"]>button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"]>button[data-testid="baseButton-primary"]:hover{
  background:var(--primary-hover)!important;
  border-color:var(--primary-hover)!important;
  color:#fff!important;
}
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stFileUploader"] label{
  color:var(--ink)!important;
  font-weight:720!important;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [role="combobox"]{
  background:var(--surface-raised)!important;
  color:var(--ink)!important;
  border:1px solid var(--line-strong)!important;
  border-radius:10px!important;
  box-shadow:none!important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{color:#73786f!important;opacity:1;}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stSelectbox"] [role="combobox"]:focus{
  border-color:var(--ink)!important;
  box-shadow:0 0 0 2px rgba(49,95,142,.22)!important;
}
[data-testid="stFileUploaderDropzone"]{
  background:var(--surface-raised)!important;
  border:1px dashed var(--line-strong)!important;
  border-radius:12px!important;
}
[data-testid="stFileUploaderDropzone"] *{color:var(--muted);}
[data-testid="stPills"]{
  margin-bottom:.45rem;
  overflow-x:auto;
  scrollbar-width:none;
}
[data-testid="stPills"]::-webkit-scrollbar{display:none;}
[data-testid="stPills"] button{
  min-height:36px!important;
  padding:.35rem .8rem!important;
  background:var(--surface-raised)!important;
  color:var(--muted)!important;
  border:1px solid var(--line)!important;
  border-radius:999px!important;
  box-shadow:none!important;
  font-weight:720!important;
  white-space:nowrap;
}
[data-testid="stPills"] button:hover{
  color:var(--ink)!important;
  border-color:var(--line-strong)!important;
  background:var(--surface-raised)!important;
  transform:none;
}
[data-testid="stPills"] button[aria-pressed="true"]{
  background:var(--primary)!important;
  color:#ffffff!important;
  border-color:var(--primary)!important;
}
[data-testid="stPills"] button[aria-pressed="true"] *{color:#fff!important;}
[data-testid="stExpander"]{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:12px;
  box-shadow:none;
  overflow:hidden;
}
[data-testid="stExpander"] summary{
  padding:.78rem .9rem;
  color:var(--ink)!important;
  font-weight:720;
}
[data-testid="stMetric"]{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:12px;
  padding:.55rem .7rem;
  box-shadow:none;
}
.stProgress > div{
  background:#e4e3dc;
  border-radius:999px;
  padding:2px;
}
.stProgress > div > div{
  background:var(--primary);
  border-radius:999px;
  transition:width .35s ease;
}
[data-testid="stAudio"]{border-radius:10px;}
[data-testid="stVideo"]{border-radius:14px;overflow:hidden;}
.eyebrow,.mini-label{
  font-size:.61rem;
  font-weight:820;
  letter-spacing:.13em;
  text-transform:uppercase;
  color:var(--subtle);
}
.badge{
  display:inline-flex;
  align-items:center;
  gap:5px;
  padding:4px 8px;
  border-radius:999px;
  background:var(--surface-soft);
  border:1px solid var(--line);
  color:var(--muted);
  font-size:.61rem;
  font-weight:720;
}
.st-key-workspace-nav{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:12px;
  padding:8px 9px;
  box-shadow:0 2px 12px rgba(21,23,19,.035);
}
.nav-brand{font-size:.96rem;font-weight:850;letter-spacing:-.025em;line-height:1.05;color:var(--ink);}
.nav-sub{font-size:.61rem;color:var(--muted);margin-top:2px;letter-spacing:.025em;}
.home-hero{padding:30px 2px 23px;max-width:850px;}
.home-kicker{font-size:.62rem;font-weight:820;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);}
.home-title{
  font-size:clamp(2.65rem,5.6vw,5.15rem);
  font-weight:860;
  line-height:.94;
  letter-spacing:-.065em;
  max-width:850px;
  margin-top:7px;
  color:var(--ink);
}
.home-copy{max-width:500px;color:var(--muted);font-size:.91rem;line-height:1.4;margin-top:10px;}
.st-key-landing-test,.st-key-landing-live{
  min-height:238px;
  border:1px solid var(--line);
  border-radius:16px;
  padding:18px;
  box-shadow:var(--shadow);
  display:flex;
  flex-direction:column;
  justify-content:space-between;
  background:var(--surface-raised);
}
.st-key-landing-test:hover,.st-key-landing-live:hover{
  border-color:var(--line-strong);
  box-shadow:var(--shadow-hover);
}
.st-key-landing-test,.st-key-landing-live{
  position:relative;
  overflow:hidden;
}
.st-key-landing-test::before,.st-key-landing-live::before{
  content:"";
  position:absolute;
  inset:0 0 auto 0;
  height:3px;
  background:var(--accent);
}
.st-key-landing-live::before{background:var(--primary);}
.workspace-index{font-size:.61rem;font-weight:820;color:var(--accent);letter-spacing:.09em;}
.workspace-name{font-size:3rem;font-weight:860;letter-spacing:-.06em;line-height:.9;margin:.5rem 0 .45rem;color:var(--ink);}
.workspace-desc{font-size:.81rem;color:var(--muted);line-height:1.35;max-width:420px;}
.home-card-top{display:flex;align-items:center;justify-content:space-between;gap:12px;}
.home-card-kind{font-size:.6rem;font-weight:820;letter-spacing:.08em;text-transform:uppercase;color:var(--subtle);}
.canvas-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px;}
.canvas-title{font-size:1.62rem;font-weight:860;letter-spacing:-.045em;line-height:1.08;color:var(--ink);}
.canvas-copy{font-size:.77rem;color:var(--muted);max-width:700px;line-height:1.4;margin-top:5px;}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:22px 0 11px;}
.section-title{font-size:1.08rem;font-weight:820;letter-spacing:-.025em;color:var(--ink);}
.section-count{font-size:.6rem;font-weight:760;color:var(--subtle);letter-spacing:.055em;text-transform:uppercase;text-align:right;}
.st-key-topic-toolbar{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:12px;
  padding:6px 8px;
  margin-bottom:13px;
}
.topic-title{
  font-size:.94rem;
  line-height:1.23;
  font-weight:770;
  letter-spacing:-.018em;
  color:var(--ink);
  display:-webkit-box;
  -webkit-box-orient:vertical;
  -webkit-line-clamp:3;
  overflow:hidden;
  min-height:3.48em;
  margin:7px 0 6px;
}
.topic-meta{
  font-size:.65rem;
  color:var(--muted);
  line-height:1.25;
  margin-top:0;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
[data-testid="stVerticalBlock"] [class*="st-key-test-top5-topic-"],
[data-testid="stVerticalBlock"] [class*="st-key-live-topic-"]{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:14px;
  padding:12px 13px;
  margin-bottom:9px;
  min-height:174px;
  box-shadow:0 1px 2px rgba(21,23,19,.025);
}
[data-testid="stVerticalBlock"] [class*="st-key-test-top5-topic-"]:hover,
[data-testid="stVerticalBlock"] [class*="st-key-live-topic-"]:hover{
  border-color:var(--line-strong);
  box-shadow:var(--shadow);
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"]{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:14px;
  margin-bottom:9px;
  box-shadow:0 1px 2px rgba(21,23,19,.025);
  overflow:hidden;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"]:hover{
  border-color:var(--line-strong);
  box-shadow:var(--shadow);
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-header-"]{
  margin:0;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-header-"] [data-testid="stButton"]>button{
  min-height:62px!important;
  justify-content:flex-start!important;
  text-align:left!important;
  padding:.85rem 1rem!important;
  border:0!important;
  border-radius:0!important;
  background:transparent!important;
  color:var(--ink)!important;
  font-size:.84rem!important;
  line-height:1.25!important;
  font-weight:780!important;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-header-"] [data-testid="stButton"]>button:hover{
  background:var(--surface-soft)!important;
  border-color:transparent!important;
  box-shadow:none!important;
}
.topic-tile-meta{
  display:flex;
  justify-content:space-between;
  gap:10px;
  padding:0 0 8px;
  border-bottom:1px solid var(--line);
  font-size:.59rem;
  font-weight:750;
  color:var(--subtle);
  letter-spacing:.045em;
  text-transform:uppercase;
}
.topic-tile-meta .topic-rank{font-size:inherit;}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stHorizontalBlock"]{
  padding:9px 0;
  border-bottom:1px solid var(--line);
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stHorizontalBlock"]:last-child{
  border-bottom:0;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] .topic-title{
  min-height:0;
  margin:0 0 4px;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stButton"]>button{
  min-height:38px!important;
  padding:.35rem .72rem!important;
}

.topic-top{display:flex;align-items:center;justify-content:space-between;min-height:14px;}
.topic-rank{font-size:.6rem;font-weight:820;letter-spacing:.09em;color:var(--accent);}
.selected-story-title{font-size:1.05rem;font-weight:820;letter-spacing:-.025em;line-height:1.18;max-width:760px;color:var(--ink);}
.st-key-selected-story-card{
  margin-top:16px;
  background:var(--surface-raised);
  border:1px solid var(--accent);
  border-radius:14px;
  padding:14px 15px;
  box-shadow:0 3px 16px rgba(47,98,85,.055);
}
.st-key-script-editor,.st-key-subtitle-editor,.st-key-renderer-inspector,.st-key-audio-inspector{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:14px;
  padding:15px;
  box-shadow:var(--shadow);
}
.inspector{background:transparent;}
.inspector-line{
  display:flex;
  justify-content:space-between;
  gap:16px;
  padding:.55rem 0;
  border-bottom:1px solid var(--line);
  font-size:.71rem;
}
.inspector-line:last-child{border-bottom:0;}
.inspector-value{font-weight:760;color:var(--ink);text-align:right;}
.scene-label{font-size:.6rem;font-weight:820;letter-spacing:.1em;text-transform:uppercase;color:var(--subtle);margin:9px 0 5px;}
.cue-row{display:grid;grid-template-columns:72px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);}
.cue-time{font-variant-numeric:tabular-nums;font-size:.66rem;color:var(--subtle);}
.cue-text{font-size:.76rem;color:var(--ink);}
.media-surface{
  background:#11130f;
  border-radius:14px;
  padding:9px;
  display:flex;
  justify-content:center;
  box-shadow:var(--shadow);
}
.live-product-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;}
.live-product-title{
  font-size:clamp(2.45rem,4.8vw,4.15rem);
  font-weight:860;
  letter-spacing:-.065em;
  line-height:.94;
  margin-top:6px;
  color:var(--ink);
}
.live-status{
  display:inline-flex;
  align-items:center;
  gap:7px;
  padding:6px 9px;
  border:1px solid var(--line);
  border-radius:999px;
  background:var(--surface-raised);
  color:var(--muted);
  font-size:.61rem;
  font-weight:750;
  white-space:nowrap;
}
.live-status span{width:7px;height:7px;border-radius:50%;background:var(--success);box-shadow:0 0 0 4px var(--success-soft);}
.hero-subtitle{font-size:.8rem;color:var(--muted);max-width:600px;line-height:1.4;margin-top:5px;}
.st-key-live-choice-cricket,.st-key-live-choice-niche,.st-key-live-cricket-india,.st-key-live-cricket-global,
.st-key-live-line-deep-dive,.st-key-live-line-top-5,.st-key-live-line-otd{
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:14px;
  padding:17px;
  min-height:184px;
  box-shadow:var(--shadow);
}
.st-key-live-choice-cricket:hover,.st-key-live-choice-niche:hover,
.st-key-live-cricket-india:hover,.st-key-live-cricket-global:hover,
.st-key-live-line-deep-dive:hover,.st-key-live-line-top-5:hover,.st-key-live-line-otd:hover{
  border-color:var(--line-strong);
  box-shadow:var(--shadow-hover);
}
.choice-title{font-size:2.15rem;font-weight:850;letter-spacing:-.06em;line-height:.94;margin:.42rem 0 .45rem;color:var(--ink);}
.choice-copy{font-size:.78rem;color:var(--muted);line-height:1.35;max-width:360px;}
.empty-slot{
  min-height:230px;
  display:flex;
  align-items:center;
  justify-content:center;
  border:1px dashed var(--line-strong);
  border-radius:11px;
  color:var(--subtle);
  background:var(--surface-soft);
  font-size:.62rem;
  font-weight:800;
  letter-spacing:.09em;
}
.visual-source{font-size:.63rem;font-weight:780;color:var(--ink);margin-top:7px;}
.visual-detail{font-size:.62rem;color:var(--muted);line-height:1.35;margin-top:3px;}
.empty-state{padding:48px 16px;text-align:center;background:var(--surface-raised);border:1px dashed var(--line-strong);border-radius:14px;box-shadow:none;}
.empty-state-title{font-size:.88rem;font-weight:800;color:var(--ink);}
.empty-state-copy{font-size:.7rem;color:var(--muted);margin-top:4px;}
.visual-crop-label{display:inline-flex;margin-top:5px;padding:4px 7px;border-radius:999px;background:var(--success-soft);color:var(--success);font-size:.57rem;font-weight:820;letter-spacing:.055em;}
.crop-dialog-kicker{font-size:.61rem;font-weight:820;letter-spacing:.13em;color:var(--accent);text-transform:uppercase;}
.crop-dialog-title{font-size:1.18rem;font-weight:820;margin:4px 0 9px;letter-spacing:-.025em;color:var(--ink);}
.pipeline-wrap{
  margin:16px 0 18px;
  padding:12px 12px 10px;

.pipeline-wrap{
  position:relative;
}
.pipeline-step{
  transition:border-color .12s ease,background .12s ease,box-shadow .12s ease,transform .12s ease;
}
.pipeline-step:hover{
  border-color:var(--line-strong);
  transform:translateY(-1px);
}
.pipeline-step.current{
  box-shadow:0 0 0 2px var(--accent-soft);
}
.pipeline-step.complete{
  box-shadow:inset 3px 0 0 var(--success);
}
  background:var(--surface-raised);
  border:1px solid var(--line);
  border-radius:14px;
  box-shadow:0 1px 2px rgba(21,23,19,.03);
}
.pipeline-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:5px;}
.pipeline-meta-label{font-size:.6rem;font-weight:820;letter-spacing:.1em;text-transform:uppercase;color:var(--subtle);}
.pipeline-meta-value{font-size:.69rem;font-weight:800;color:var(--ink);text-align:right;}
.pipeline-steps{display:flex;gap:6px;overflow-x:auto;padding:7px 0 1px;scrollbar-width:none;}
.pipeline-steps::-webkit-scrollbar{display:none;}
.pipeline-step{flex:1 0 108px;min-width:108px;padding:7px 8px;border:1px solid var(--line);border-radius:10px;background:var(--surface);}
.pipeline-step.complete{background:var(--success-soft);border-color:#b8d6c3;}
.pipeline-step.current{background:var(--surface-selected);border-color:#aec4b9;}
.pipeline-step-number{font-size:.54rem;font-weight:820;letter-spacing:.07em;color:var(--subtle);}
.pipeline-step.current .pipeline-step-number,.pipeline-step.current .pipeline-step-label{color:var(--accent);}
.pipeline-step.complete .pipeline-step-number,.pipeline-step.complete .pipeline-step-label{color:var(--success);}
.pipeline-step-label{margin-top:3px;font-size:.66rem;font-weight:780;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pipeline-step-state{margin-top:3px;font-size:.55rem;font-weight:760;color:var(--subtle);text-transform:uppercase;letter-spacing:.045em;}
.pipeline-step.current .pipeline-step-state{color:var(--accent);}
.pipeline-step.complete .pipeline-step-state{color:var(--success);}
.handoff-card{
  display:flex;
  align-items:center;
  gap:10px;
  margin:0 0 16px;
  padding:10px 11px;
  background:var(--success-soft);
  border:1px solid #b8d6c3;
  border-radius:11px;
}
.handoff-mark{
  flex:0 0 auto;
  width:23px;
  height:23px;
  display:grid;
  place-items:center;
  border-radius:50%;
  background:var(--success);
  color:#fff;
  font-size:.71rem;
  font-weight:900;
}
.handoff-title{font-size:.71rem;font-weight:820;color:var(--ink);line-height:1.2;}
.handoff-copy{margin-top:2px;font-size:.63rem;color:var(--muted);line-height:1.25;}
@media(max-width:900px){
  .block-container{padding:17px 16px 44px;}
  .home-hero{padding:23px 0 19px;}
  .home-title{font-size:clamp(2.55rem,10vw,4.6rem);}
  .workspace-name{font-size:2.7rem;}
  .canvas-head{margin-bottom:13px;}
  .section-head{margin-top:18px;}
  .st-key-landing-test,.st-key-landing-live{min-height:220px;}
}
@media(max-width:640px){
  .block-container{padding:14px 11px 38px;}
  .st-key-workspace-nav{padding:8px;}
  .home-copy{font-size:.84rem;}
  .home-title{font-size:clamp(2.35rem,13vw,3.65rem);}
  .workspace-name{font-size:2.45rem;}
  .canvas-title{font-size:1.3rem;}
  .live-product-head{display:block;}
  .live-status{margin-top:12px;}
  .choice-title{font-size:1.9rem;}
  .section-head{align-items:flex-start;flex-direction:column;gap:4px;}
  .section-count{text-align:left;}
  [data-testid="stHorizontalBlock"]{gap:9px;}
  [data-testid="stHorizontalBlock"]:has([class*="st-key-test-top5-topic-"]),
  [data-testid="stHorizontalBlock"]:has([class*="st-key-live-topic-"]),
  [data-testid="stHorizontalBlock"]:has([class*="st-key-live-slide-"]){
    flex-direction:column!important;
    gap:9px!important;
  }
  [data-testid="stHorizontalBlock"]:has([class*="st-key-test-top5-topic-"])>div,
  [data-testid="stHorizontalBlock"]:has([class*="st-key-live-topic-"])>div,
  [data-testid="stHorizontalBlock"]:has([class*="st-key-live-slide-"])>div{
    width:100%!important;
    flex:1 1 100%!important;
  }
  [data-testid="stHorizontalBlock"]:has([class*="st-key-landing-test"]) ,
  [data-testid="stHorizontalBlock"]:has([class*="st-key-landing-live"]){
    flex-direction:column!important;
  }
  [data-testid="stVerticalBlock"] [class*="st-key-test-top5-topic-"],
  [data-testid="stVerticalBlock"] [class*="st-key-live-topic-"]{
    min-height:156px;
    padding:11px 12px;
  }
  .topic-title{font-size:.92rem;-webkit-line-clamp:3;}
  [data-testid="stVerticalBlock"] [class*="topic-tile-header-"] [data-testid="stButton"]>button{
    min-height:56px!important;
    padding:.75rem .82rem!important;
  }
  [data-testid="stVerticalBlock"] [class*="st-key-topic-tile-"] [data-testid="stButton"]>button{
    min-height:42px!important;
  }
  .selected-story-title{font-size:.98rem;}
  .pipeline-wrap{padding:10px 10px 9px;}
  .pipeline-meta{align-items:flex-start;}
  .pipeline-meta-value{max-width:56%;font-size:.65rem;}
  .pipeline-step{flex-basis:100px;min-width:100px;}
  .handoff-card{align-items:flex-start;}
  .handoff-title{font-size:.69rem;}
  .handoff-copy{font-size:.61rem;}
  [data-testid="stButton"]>button,[data-testid="stFormSubmitButton"]>button{min-height:44px!important;}
  [data-testid="stTextInput"] input,[data-testid="stSelectbox"] [role="combobox"]{min-height:44px!important;}
  [data-testid="stTextArea"] textarea{min-height:110px;}
  .cue-row{grid-template-columns:52px 1fr;gap:9px;}
  .inspector-line{font-size:.69rem;}
  .media-surface{padding:7px;border-radius:11px;}
}
</style>\n""", unsafe_allow_html=True)

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "home"
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
if "test_top5_visual_card_results" not in st.session_state:
    st.session_state.test_top5_visual_card_results = {}
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
if "youtube_trend_error" not in st.session_state:
    st.session_state.youtube_trend_error = ""
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None
if "topic_open_tile" not in st.session_state:
    st.session_state.topic_open_tile = None
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
if "stats_card_result" not in st.session_state:
    st.session_state.stats_card_result = None
if "stats_card_image_selection" not in st.session_state:
    st.session_state.stats_card_image_selection = None
if "stats_card_image_crop" not in st.session_state:
    st.session_state.stats_card_image_crop = None
if "stats_card_approved" not in st.session_state:
    st.session_state.stats_card_approved = False
if "quote_card_image_selection" not in st.session_state:
    st.session_state.quote_card_image_selection = None
if "quote_card_image_crop" not in st.session_state:
    st.session_state.quote_card_image_crop = None
if "quote_card_preview" not in st.session_state:
    st.session_state.quote_card_preview = None
if "quote_card_quote" not in st.session_state:
    st.session_state.quote_card_quote = ""
if "quote_card_attribution" not in st.session_state:
    st.session_state.quote_card_attribution = ""
if "quote_card_slide" not in st.session_state:
    st.session_state.quote_card_slide = 1

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
if "live_youtube_trend_error" not in st.session_state:
    st.session_state.live_youtube_trend_error = ""
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
if "live_stats_card_result" not in st.session_state:
    st.session_state.live_stats_card_result = None
if "live_stats_card_image_selection" not in st.session_state:
    st.session_state.live_stats_card_image_selection = None
if "live_stats_card_image_crop" not in st.session_state:
    st.session_state.live_stats_card_image_crop = None
if "live_stats_card_approved" not in st.session_state:
    st.session_state.live_stats_card_approved = False
if "live_quote_card_image_selection" not in st.session_state:
    st.session_state.live_quote_card_image_selection = None
if "live_quote_card_image_crop" not in st.session_state:
    st.session_state.live_quote_card_image_crop = None
if "live_quote_card_preview" not in st.session_state:
    st.session_state.live_quote_card_preview = None
if "live_quote_card_quote" not in st.session_state:
    st.session_state.live_quote_card_quote = ""
if "live_quote_card_attribution" not in st.session_state:
    st.session_state.live_quote_card_attribution = ""
if "live_quote_card_slide" not in st.session_state:
    st.session_state.live_quote_card_slide = 1
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


def _largest_9x16_crop_coords(image: Image.Image) -> tuple[int, int, int, int]:
    aspect = 9 / 16
    width = min(image.width, max(1, int(image.height * aspect)))
    height = min(image.height, max(1, int(width / aspect)))
    left = max(0, (image.width - width) // 2)
    top = max(0, (image.height - height) // 2)
    return (left, left + width, top, top + height)


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
):
    from PIL import Image, ImageFilter, ImageOps

    image = _asset_to_image(image_bytes)
    if image is None:
        st.error("This visual could not be opened for cropping.")
        return

    st.markdown('<div class="crop-dialog-kicker">MANUAL CROP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="crop-dialog-title">{label}</div>', unsafe_allow_html=True)
    st.caption("9:16 frame · drag the frame to reposition it, or drag a corner outward to zoom out and reveal more of the original. Any exposed area uses a blurred extension of the same image.")

    from streamlit_cropper import st_cropper

    canvas_width = max(image.width, int(round(image.height * 9 / 16)))
    canvas_height = int(round(canvas_width * 16 / 9))
    background = ImageOps.fit(
        image.convert("RGB"),
        (canvas_width, canvas_height),
        method=Image.Resampling.LANCZOS,
    ).filter(ImageFilter.GaussianBlur(radius=max(18, canvas_width // 55)))
    canvas = background.copy()
    offset_x = (canvas_width - image.width) // 2
    offset_y = (canvas_height - image.height) // 2
    canvas.paste(image.convert("RGB"), (offset_x, offset_y))

    default = _largest_9x16_crop_coords(image)
    default_coords = (
        offset_x + default[0],
        offset_x + default[1],
        offset_y + default[2],
        offset_y + default[3],
    )

    store = st.session_state.setdefault(crop_store, {})
    cropped = st_cropper(
        canvas,
        realtime_update=True,
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
        st.caption(f"{image.width} × {image.height}px")
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
        state["image_key"] = None

    for start in range(0, len(assets), 3):
        cols = st.columns(min(3, len(assets) - start), gap="medium")
        for col, asset in zip(cols, assets[start:start + 3]):
            with col:
                asset_key = str(asset["asset_key"])
                image = _asset_to_image(asset.get("bytes"))
                if image is not None:
                    preview = image.copy()
                    preview.thumbnail((300, 300), Image.Resampling.LANCZOS)
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
                    selected = asset_key == str(state.get("image_key") or "")
                    if st.button(
                        "Selected" if selected else "Select image",
                        type="primary" if selected else "secondary",
                        width="stretch",
                        key=f"{state_id}-select-{asset_key}",
                    ) and not selected:
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

    source_image = _asset_to_image(working_bytes)
    if source_image is None:
        st.error("The selected image could not be opened.")
        return

    if state["editor_image_digest"] != source_digest:
        preview_image = source_image.convert("RGB").resize((360, 640), Image.Resampling.LANCZOS)
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
            "Every option keeps the requested font size and uses the polygon as the actual text field. "
            "More lines are created as needed instead of shrinking the text."
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
                    selected = tuple(option["line_breaks"]) == tuple(state.get("line_breaks") or ())
                    if st.button(
                        "Selected" if selected else "Use this layout",
                        type="primary" if selected else "secondary",
                        width="stretch",
                        key=f"{state_id}-line-break-{option['index']}",
                    ):
                        state["line_breaks"] = tuple(option["line_breaks"])
                        selected_line_breaks = tuple(option["line_breaks"])
        state["layout_signature"] = layout_signature

    st.caption(
        "English only · Negative Space does not detect subjects · Behind Subject uses BiRefNet. "
        "Polygon is the full text field; larger text uses line breaks to fill it, while smaller text may sit centered. "
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

    if st.button("Render Now", type="primary", width="stretch", key=f"{state_id}-render"):
        try:
            config = {
                "headline": headline,
                "mode": selected_mode,
                "text_polygon": tuple(polygon_points),
                "font_size": font_size,
                "font": state["font"],
                "style": state["style"],
                "line_breaks": selected_line_breaks or None,
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
            )
            state["font_size"] = font_size
            state["rendered_config"] = config
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
                    st.session_state.test_top5_visual_card_results.pop(active_slide, None)
                    st.rerun()


def _stats_card_pool_entries(live: bool) -> list[tuple[str, int, dict, bytes, str]]:
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
            if not isinstance(raw, (bytes, bytearray)):
                continue
            if _asset_to_image(raw) is None:
                continue
            entries.append(
                (
                    asset_key,
                    index,
                    asset,
                    bytes(raw),
                    source_name,
                )
            )
    return entries


@st.dialog("Crop image for Stats Card", width="large")
def _stats_card_crop_dialog(image_bytes: bytes, live: bool):
    from PIL import Image, ImageFilter, ImageOps
    from stats_card import IMAGE_HEIGHT, WIDTH

    image = _asset_to_image(image_bytes)
    if image is None:
        st.error("This visual could not be opened for cropping.")
        return

    st.markdown('<div class="crop-dialog-kicker">STATS CARD CROP</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="crop-dialog-title">Set the image framing for the card</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Crop to the card image area. The frame keeps the exact {WIDTH} × {IMAGE_HEIGHT}px ratio. "
        "Drag the frame to reposition it or resize the corners."
    )

    from streamlit_cropper import st_cropper

    target_ratio = WIDTH / IMAGE_HEIGHT
    crop_aspect_ratio = (WIDTH, IMAGE_HEIGHT)
    canvas_width = max(image.width, int(round(image.height * target_ratio)))
    canvas_height = max(image.height, int(round(canvas_width / target_ratio)))
    background = ImageOps.fit(
        image.convert("RGB"),
        (canvas_width, canvas_height),
        method=Image.Resampling.LANCZOS,
    ).filter(ImageFilter.GaussianBlur(radius=max(18, canvas_width // 55)))
    canvas = background.copy()
    offset_x = (canvas_width - image.width) // 2
    offset_y = (canvas_height - image.height) // 2
    canvas.paste(image.convert("RGB"), (offset_x, offset_y))

    cropper_key = "live-stats-card-cropper" if live else "test-stats-card-cropper"
    cropped = st_cropper(
        canvas,
        realtime_update=True,
        aspect_ratio=crop_aspect_ratio,
        return_type="image",
        key=cropper_key,
        stroke_width=2,
        box_color="#4F46E5",
    )

    left, right = st.columns([1.2, .8], gap="large")
    with left:
        st.markdown('<div class="crop-dialog-kicker">PREVIEW</div>', unsafe_allow_html=True)
        st.image(cropped, width="stretch")
    with right:
        st.markdown('<div class="crop-dialog-kicker">SOURCE IMAGE</div>', unsafe_allow_html=True)
        st.caption(f"{image.width} × {image.height}px")
        st.markdown(
            '<div class="crop-dialog-kicker" style="margin-top:1rem;">CARD IMAGE</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"{WIDTH} × {IMAGE_HEIGHT}px")
        st.caption("This crop affects the Stats Card only; the normal visual crop is unchanged.")
        if st.button(
            "Apply crop for card",
            type="primary",
            width="stretch",
            key=f"{cropper_key}-apply",
        ):
            buffer = BytesIO()
            cropped.convert("RGB").resize(
                (WIDTH, IMAGE_HEIGHT),
                Image.Resampling.LANCZOS,
            ).save(buffer, format="JPEG", quality=94, optimize=True)
            crop_key = "live_stats_card_image_crop" if live else "stats_card_image_crop"
            result_key = "live_stats_card_result" if live else "stats_card_result"
            approved_key = "live_stats_card_approved" if live else "stats_card_approved"
            st.session_state[crop_key] = buffer.getvalue()
            st.session_state[result_key] = None
            st.session_state[approved_key] = False
            st.rerun()


def _render_stats_card(live: bool = False, slide_count: int = 0):
    from stats_card import StatsCardError, build_stats_card, build_test_stats_card, build_stats_card_preview

    state_key = "live_stats_card_result" if live else "stats_card_result"
    selection_key = "live_stats_card_image_selection" if live else "stats_card_image_selection"
    crop_key = "live_stats_card_image_crop" if live else "stats_card_image_crop"
    approved_key = "live_stats_card_approved" if live else "stats_card_approved"
    build_key = "live-stats-card-build" if live else "test-stats-card-build"

    st.subheader("Stats Card")
    st.caption(
        "Choose the image from the existing Manual QC pool, crop it for this card, "
        "then build and approve the completed card."
    )

    entries = _stats_card_pool_entries(live)
    if not entries:
        st.info(
            "Run one of the existing visual options first. "
            "Stats Card uses that existing image pool and does not run another image search."
        )
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">IMAGE POOL</div>'
        '<div class="section-title">Choose the player image</div></div>'
        '<div class="section-count">existing visuals only</div></div>',
        unsafe_allow_html=True,
    )

    current_selection = st.session_state.get(selection_key)
    for start_index in range(0, len(entries), 3):
        row = entries[start_index:start_index + 3]
        cols = st.columns(len(row), gap="medium")
        for col, (asset_key, index, asset, image_bytes, source_name) in zip(cols, row):
            with col:
                source = str(
                    asset.get("publisher")
                    or asset.get("source")
                    or asset.get("model")
                    or source_name
                )
                label = str(
                    asset.get("article_title")
                    or asset.get("model")
                    or source_name
                )
                with st.container(key=f"{build_key}-image-{asset_key}"):
                    preview = _asset_to_image(image_bytes)
                    if preview is not None:
                        preview.thumbnail((420, 420), Image.Resampling.LANCZOS)
                        st.image(preview, width="stretch")
                    st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                    if label:
                        st.markdown(f'<div class="visual-detail">{label}</div>', unsafe_allow_html=True)
                    selected = (
                        isinstance(current_selection, dict)
                        and current_selection.get("asset_key") == asset_key
                    )
                    if st.button(
                        "Selected" if selected else "Select image",
                        type="primary" if selected else "secondary",
                        width="stretch",
                        key=f"{build_key}-select-{asset_key}",
                    ):
                        st.session_state[selection_key] = {
                            "asset_key": asset_key,
                            "source": source,
                            "label": label,
                            "bytes": image_bytes,
                        }
                        st.session_state[crop_key] = None
                        st.session_state[state_key] = None
                        st.session_state[approved_key] = False
                        st.rerun()

    selected = st.session_state.get(selection_key)
    if not isinstance(selected, dict):
        return

    source_bytes = st.session_state.get(crop_key) or selected.get("bytes")
    if not isinstance(source_bytes, (bytes, bytearray)):
        st.error("The selected image is missing.")
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">CARD IMAGE</div>'
        '<div class="section-title">Crop the selected image for this card</div></div>'
        '<div class="section-count">1080 × 860 image area</div></div>',
        unsafe_allow_html=True,
    )
    crop_cols = st.columns([1, .42], gap="small")
    with crop_cols[0]:
        st.image(source_bytes, width=360)
    with crop_cols[1]:
        if st.button(
            "Crop for card",
            type="primary",
            width="stretch",
            key=f"{build_key}-crop",
        ):
            _stats_card_crop_dialog(bytes(source_bytes), live)
        if st.session_state.get(crop_key):
            st.markdown(
                '<span class="visual-crop-label">CARD CROP APPLIED</span>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Reset card crop",
                width="stretch",
                key=f"{build_key}-reset-crop",
            ):
                st.session_state[crop_key] = None
                st.session_state[state_key] = None
                st.session_state[approved_key] = False
                st.rerun()

    result = st.session_state.get(state_key)
    if isinstance(result, dict) and result:
        if result.get("error"):
            st.error(result["error"])
            if not live and st.button(
                "Research a different query",
                width="stretch",
                key=f"{build_key}-requery-error",
            ):
                st.session_state[state_key] = None
                st.session_state[approved_key] = False
                st.rerun()
            return
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">MANUAL QC</div>'
            '<div class="section-title">Review the completed Stats Card</div></div>'
            '<div class="section-count">approve this exact card</div></div>',
            unsafe_allow_html=True,
        )
        st.image(result["bytes"], width=360)
        st.caption(
            f'{result.get("label") or "Stats Card"} · '
            f'{result.get("source") or "Cricket data"}'
        )
        stats = result.get("stats") or {}
        if result.get("query"):
            st.code(result["query"])
        if stats.get("last_date"):
            st.caption(f"Data through {stats['last_date']}")
        elif stats.get("latest_date"):
            st.caption(f"Latest meeting: {stats['latest_date']}")
        if not live and result.get("plan"):
            plan = result["plan"]
            st.caption(
                "AI interpretation: "
                + str(plan.get("scope") or "").replace("_", " ")
                + " · "
                + str(plan.get("format") or "").upper()
            )
        if not live and st.button(
            "Research a different query",
            width="stretch",
            key=f"{build_key}-requery",
        ):
            st.session_state[state_key] = None
            st.session_state[approved_key] = False
            st.rerun()

        if not st.session_state.get(approved_key):
            if st.button(
                "Approve Stats Card",
                type="primary",
                width="stretch",
                key=f"{build_key}-approve",
            ):
                st.session_state[approved_key] = True
                st.rerun()
        else:
            st.success("Stats Card approved.")

        if not st.session_state.get(approved_key):
            return
        if slide_count <= 0:
            return

        if live:
            st.download_button(
                "Save Stats Card PNG",
                data=result["bytes"],
                file_name="stats-card.png",
                mime="image/png",
                width="stretch",
                key=f"{build_key}-download",
            )

        slide = st.selectbox(
            "Use Stats Card for slide",
            list(range(1, slide_count + 1)),
            key=f"{build_key}-slide",
        )
        if st.button(
            "Use Stats Card for this slide",
            type="primary",
            width="stretch",
            key=f"{build_key}-attach",
        ):
            card_key = hashlib.sha1(
                (str(result.get("path") or "") + str(result.get("query") or "")).encode("utf-8")
            ).hexdigest()[:12]
            assignment = {
                "asset_key": f"stats-card-{card_key}",
                "result_key": "stats-card",
                "card_layout": dict(result.get("layout") or {}),
                "source": f"Stats Card · {result.get('source') or 'TigZig / Cricsheet'}",
                "label": str(result.get("label") or "Stats Card"),
                "bytes": bytes(result["bytes"]),
            }
            assignments_key = "live_visual_assignments" if live else "visual_assignments"
            st.session_state[assignments_key][slide] = assignment
            if live:
                st.session_state.live_visuals_approved = False
            else:
                st.session_state.visuals_approved = False
                st.session_state.approved_visuals = None
            st.rerun()
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">CARD PREVIEW</div>'
        '<div class="section-title">Selected image + empty stats panel</div></div>'
        '<div class="section-count">1080 × 1920</div></div>',
        unsafe_allow_html=True,
    )
    st.image(build_stats_card_preview(bytes(source_bytes)), width=360)

    with st.form(f"{build_key}-query-form"):
        query = st.text_input(
            "Manual query",
            placeholder=(
                "e.g. MS Dhoni ODI stats · India vs Pakistan H2H stats · "
                "Virat Kohli's last 10 innings scores"
            ),
            key=f"{build_key}-query",
        )
        build = st.form_submit_button(
            "Build Stats Card",
            type="primary",
            width="stretch",
        )

    if not build:
        return

    query = query.strip()
    if not query:
        st.warning("Enter a stats query first.")
        return

    with st.spinner("Building the stats card from the cricket database…"):
        try:
            builder = build_stats_card if live else build_test_stats_card
            st.session_state[state_key] = builder(
                query,
                bytes(source_bytes),
            )
            st.session_state[approved_key] = False
            st.rerun()
        except (StatsCardError, OSError, RuntimeError) as exc:
            st.session_state[state_key] = {"error": str(exc)}
            st.rerun()




def _render_quote_card(live: bool = False, slide_count: int = 0):
    from renderer import build_quote_card_preview

    prefix = "live_" if live else ""
    script_key = f"{prefix}approved_script"
    selection_key = f"{prefix}quote_card_image_selection"
    crop_key = f"{prefix}quote_card_image_crop"
    preview_key = f"{prefix}quote_card_preview"
    quote_key = f"{prefix}quote_card_quote"
    attribution_key = f"{prefix}quote_card_attribution"
    slide_key = f"{prefix}quote_card_slide"

    script = st.session_state.get(script_key)
    if not isinstance(script, dict) and not live:
        script = st.session_state.get("script_data") or {}
    if not isinstance(script, dict):
        st.info("Approve the Scriptwriter result first.")
        return

    entries = _stats_card_pool_entries(live)
    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">QUOTE CARD</div>'
        '<div class="section-title">Use a quote as the visual treatment for one existing slide</div></div>'
        '<div class="section-count">existing visual pool</div></div>',
        unsafe_allow_html=True,
    )

    quote = str(st.session_state.get(quote_key) or "")
    attribution = str(st.session_state.get(attribution_key) or "")
    if quote:
        st.caption("Scriptwriter identified this quote from the research. Edit it before previewing if needed.")
    else:
        st.info("No quote was identified by the Scriptwriter for this story. Enter one only when the source supports it.")

    if not entries:
        st.info(
            "Run an existing visual option first. Quote Card uses that pool and does not run another image search."
        )
        return

    current_selection = st.session_state.get(selection_key)
    for start_index in range(0, len(entries), 3):
        row = entries[start_index:start_index + 3]
        cols = st.columns(len(row), gap="medium")
        for col, (asset_key, index, asset, image_bytes, source_name) in zip(cols, row):
            with col:
                source = str(
                    asset.get("publisher")
                    or asset.get("source")
                    or asset.get("model")
                    or source_name
                )
                label = str(
                    asset.get("article_title")
                    or asset.get("model")
                    or source_name
                )
                with st.container(key=f"{prefix}quote-card-image-{asset_key}"):
                    preview = _asset_to_image(image_bytes)
                    if preview is not None:
                        preview.thumbnail((420, 420), Image.Resampling.LANCZOS)
                        st.image(preview, width="stretch")
                    st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                    if label:
                        st.markdown(f'<div class="visual-detail">{label}</div>', unsafe_allow_html=True)
                    selected = (
                        isinstance(current_selection, dict)
                        and current_selection.get("asset_key") == asset_key
                    )
                    if st.button(
                        "Selected" if selected else "Select image",
                        type="primary" if selected else "secondary",
                        width="stretch",
                        key=f"{prefix}quote-card-select-{asset_key}",
                    ):
                        st.session_state[selection_key] = {
                            "asset_key": asset_key,
                            "source": source,
                            "label": label,
                            "bytes": image_bytes,
                        }
                        st.session_state[crop_key] = None
                        st.session_state[preview_key] = None
                        st.rerun()

    selected = st.session_state.get(selection_key)
    if not isinstance(selected, dict):
        return

    crop_store = st.session_state.get(
        "live_visual_crops" if live else "visual_crops"
    ) or {}
    source_bytes = crop_store.get(selected.get("asset_key")) or selected.get("bytes")
    if not isinstance(source_bytes, (bytes, bytearray)):
        st.error("The selected image is missing.")
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">QUOTE CONTENT</div>'
        '<div class="section-title">Edit the quote before rendering</div></div>'
        '<div class="section-count">one existing slide</div></div>',
        unsafe_allow_html=True,
    )
    text_col, attr_col = st.columns([1.65, .8], gap="medium")
    with text_col:
        quote = st.text_area(
            "Quote",
            value=quote,
            height=105,
            max_chars=500,
            key=quote_key,
        ).strip()
    with attr_col:
        attribution = st.text_input(
            "Attribution",
            value=attribution,
            max_chars=120,
            key=attribution_key,
        ).strip()

    scenes = script.get("script") or []
    available_slides = max(1, slide_count or len(scenes))
    default_slide = max(
        1,
        min(available_slides, int(st.session_state.get(slide_key) or 1)),
    )
    selected_slide = st.selectbox(
        "Use Quote Card for slide",
        list(range(1, available_slides + 1)),
        index=default_slide - 1,
        key=slide_key,
    )
    st.session_state[slide_key] = selected_slide

    crop_cols = st.columns([1, .42], gap="small")
    with crop_cols[0]:
        st.image(source_bytes, width=360)
    with crop_cols[1]:
        if st.button(
            "Crop / reposition",
            type="primary",
            width="stretch",
            key=f"{prefix}quote-card-crop-{selected.get('asset_key')}",
        ):
            _crop_visual_dialog(
                selected["asset_key"],
                bytes(selected.get("bytes") or b""),
                str(selected.get("source") or "Selected image"),
                crop_store="live_visual_crops" if live else "visual_crops",
            )
        if st.session_state.get(crop_key):
            st.markdown('<span class="visual-crop-label">CROP APPLIED</span>', unsafe_allow_html=True)

    if st.button(
        "Preview Quote Card",
        type="primary",
        width="stretch",
        key=f"{prefix}quote-card-preview-button",
    ):
        if not quote or not attribution:
            st.warning("Quote and attribution are required.")
        else:
            try:
                st.session_state[preview_key] = build_quote_card_preview(
                    bytes(source_bytes),
                    quote,
                    attribution,
                    source_label="SPORTS DESK",
                )
            except (ValueError, OSError) as exc:
                st.error(str(exc))

    preview_bytes = st.session_state.get(preview_key)
    if not preview_bytes:
        return

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">MANUAL QC</div>'
        '<div class="section-title">Quote Card preview</div></div>'
        '<div class="section-count">1080 × 1920</div></div>',
        unsafe_allow_html=True,
    )
    st.image(preview_bytes, width=420)
    st.caption(
        "The selected quote is visual-only on this slide; normal subtitles are suppressed for the Quote Card."
    )

    if st.button(
        f"Use Quote Card for slide {selected_slide}",
        type="primary",
        width="stretch",
        key=f"{prefix}quote-card-attach",
    ):
        assignment = {
            "asset_key": f"quote-card-{selected.get('asset_key')}",
            "result_key": "quote-card",
            "source": f"Quote Card · {attribution}",
            "label": quote,
            "bytes": bytes(source_bytes),
            "preview_bytes": bytes(preview_bytes),
            "quote_card": {
                "quote": quote,
                "attribution": attribution,
                "language": str(script.get("language_used") or "english"),
            },
        }
        assignments_key = "live_visual_assignments" if live else "visual_assignments"
        st.session_state[assignments_key][selected_slide] = assignment
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
    st.markdown(
        '<div class="home-hero">'
        '<div class="home-kicker">FINAL SHORTS</div>'
        '<div class="home-title">Editorial studio.</div>'
        '<div class="home-copy">Choose a workspace and start where you need to.</div>'
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
            st.markdown('<div><span class="badge">production</span> <span class="badge">public / private</span></div>', unsafe_allow_html=True)
            if st.button("Open Live", key="open-live", type="primary", width="stretch"):
                st.session_state.app_mode = "live"
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
        left, right = st.columns([1, .16], gap="small")
        with left:
            st.markdown(
                '<div class="nav-brand">FINAL SHORTS</div>'
                '<div class="nav-sub">Editorial production</div>',
                unsafe_allow_html=True,
            )
        with right:
            if st.button("Home", key="workspace-home", width="stretch"):
                st.session_state.app_mode = "home"
                st.rerun()

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

        if st.session_state.app_mode == "test" and st.session_state.test_production_line:
            line_name = {
                "deep_dive": "Deep-Dive",
                "top_5": "Top-5",
                "otd": "OTD",
                "youtube_trends": "YT Trends",
            }.get(
                st.session_state.test_production_line,
                str(st.session_state.test_production_line).replace("_", " ").title(),
            )
            st.markdown(
                f'<div class="nav-sub" style="margin-top:12px;">{line_name} · Test stages</div>',
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
                st.rerun()
            if st.button("← Production lines", key="test-back-to-lines", width="stretch"):
                st.session_state.test_production_line = None
                st.session_state.test_stage = "01 · Topic Fetcher"
                st.session_state.test_pipeline_notice = None
                st.rerun()


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
        "live_audio_data": None,
        "live_approved_audio": None,
        "live_subtitle_data": None,
        "live_handoff_error": "",
        "live_visual_result": None,
        "live_manual_visual_result": None,
        "live_real_image_result": None,
        "live_ai_image_result": None,
        "live_stats_card_result": None,
        "live_stats_card_image_selection": None,
        "live_stats_card_image_crop": None,
        "live_stats_card_approved": False,
        "live_quote_card_image_selection": None,
        "live_quote_card_image_crop": None,
        "live_quote_card_preview": None,
        "live_quote_card_quote": "",
        "live_quote_card_attribution": "",
        "live_quote_card_slide": 1,
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


def _script_for_topic(topic, profile: str, language: str) -> dict:
    from niche_sports_script_writer import write_niche_sports_script
    from script_writer import write_script

    writer = write_niche_sports_script if profile == "niche_sports" else write_script
    return writer(
        _story_payload(topic),
        language=language,
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
        row = st.columns(columns, gap="small")
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
                tile_title = tile.group_key.split(":", 1)[1].title()
            elif tile.group_key.startswith("player:"):
                tile_title = tile.group_key.split(":", 1)[1].title()
            else:
                tile_title = tile.title

            with col:
                with st.container(key=f"{key_prefix}topic-tile-{index}"):
                    is_open = st.session_state.get(open_state_key) == index
                    if st.button(
                        f'{"▾" if is_open else "▸"}  {tile_title}',
                        key=f"{key_prefix}topic-tile-header-{index}",
                        width="stretch",
                        type="primary" if is_open else "secondary",
                    ):
                        st.session_state[open_state_key] = None if is_open else index
                        st.rerun()

                    if not is_open:
                        continue

                    for headline_index, member in enumerate(members):
                        is_selected = (
                            selected_index == index
                            and topics[index].url == member.url
                        )
                        with st.container(
                            horizontal=True,
                            vertical_alignment="center",
                            horizontal_alignment="distribute",
                            gap="small",
                        ):
                            st.markdown(
                                f'<div class="topic-title">{member.title}</div>'
                                f'<div class="topic-meta">{member.source or "Sports desk"} · {member.published_at:%d %b}</div>',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "Selected" if is_selected else "Choose",
                                key=f"{key_prefix}topic-select-{index}-{headline_index}",
                                width="content",
                                type="primary" if is_selected else "secondary",
                            ):
                                selection = (index, member, members)
    return selection


def _live_start_story(index: int):
    _live_reset_downstream()
    st.session_state.live_selected_topic = index
    st.session_state.live_stage = "02 · Script"
    st.session_state.live_pipeline_notice = {
        "confirmed": "Story confirmed",
        "next": "Moving to Script.",
    }


def _live_generate_script():
    selected_index = st.session_state.get("live_selected_topic")
    topics = st.session_state.get("live_topics") or []
    if selected_index is None or not 0 <= selected_index < len(topics):
        raise ValueError("No valid Live story is selected.")

    topic = topics[selected_index]
    script = _script_for_topic(
        topic,
        st.session_state.get("live_topics_profile") or "",
        st.session_state.get("live_script_language", "english"),
    )
    st.session_state.live_script_data = script
    st.session_state.live_script_error = ""
    metadata = _upload_metadata(script)
    st.session_state.live_upload_titles = metadata["titles"]
    st.session_state.live_upload_description = metadata["description"]
    st.session_state.live_upload_hashtags = metadata["hashtags"]
    st.session_state.live_upload_comment = metadata["comment"]
    st.session_state.live_quote_card_quote = str(script.get("quote") or "")
    st.session_state.live_quote_card_attribution = str(
        script.get("quote_attribution") or ""
    )
    quote_slide = int(script.get("quote_slide") or 1)
    st.session_state.live_quote_card_slide = max(1, min(4, quote_slide))
    st.session_state.live_quote_card_image_selection = None
    st.session_state.live_quote_card_image_crop = None
    st.session_state.live_quote_card_preview = None
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

    from audio import approve_audio, generate_audio
    from subtitles import generate_subtitles

    audio = generate_audio(
        approved_script,
        output_dir="output/live/audio",
    )
    approved_audio = approve_audio(audio)
    subtitles = generate_subtitles(approved_script, approved_audio)

    st.session_state.live_audio_data = audio
    st.session_state.live_approved_audio = approved_audio
    st.session_state.live_subtitle_data = subtitles


def _fit_visual_preview(value, width=360, height=640):
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

    for start in range(0, len(visible_assets), 3):
        cols = st.columns(3, gap="medium")
        for col, (index, asset) in zip(cols, visible_assets[start:start + 3]):
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
                        preview_bytes if preview_bytes else asset.get("bytes")
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
                        '<div class="empty-slot">EMPTY</div>',
                        unsafe_allow_html=True,
                    )


def _render_live_visuals(slide_count: int):
    if st.session_state.live_visuals_approved:
        st.success("Visuals approved and final render completed.")
        st.caption("Visual review is complete. The dashboard has moved this production to Upload.")
        return

    visual_options = (
        CRICKET_LIVE_VISUAL_OPTIONS
        if st.session_state.get("live_topics_profile") in {"cricket_india_asia", "cricket_global"}
        else VISUAL_OPTIONS
    )
    if st.session_state.get("live_visual_option") not in visual_options:
        st.session_state.live_visual_option = visual_options[0]
    visual_option = st.pills(
        "Visual source",
        visual_options,
        default=st.session_state.live_visual_option,
        key="live_visual_option",
        label_visibility="collapsed",
    ) or visual_options[0]

    _render_visual_board(slide_count, live=True)

    assigned = len(st.session_state.live_visual_assignments)
    st.caption(
        f"{assigned}/{slide_count} slides attached. "
        "Attached images remain in their original pools until you delete them."
    )

    if visual_option == "Option 1 · Automatic Scraper":
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

    if visual_option == "Option 2 · Manual Scraper":
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

    if visual_option == "Option 3 · Real Image Search":
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

    if visual_option == "Option 4 · AI Generation":
        st.caption("Manual prompt only. Uses the configured AI image providers.")
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
            st.caption(f'{len(result.get("assets") or [])} images')
            _render_visual_asset_pool(
                list(result.get("assets") or []),
                "ai",
                slide_count,
                live=True,
            )

    if visual_option == "Option 7 · Text Cutout":
        entries = _stats_card_pool_entries(live=True)
        state = st.session_state.live_manual_subject_cutout
        assets = [
            {
                "asset_key": asset_key,
                "bytes": image_bytes,
                "source": source_name,
                "label": str(
                    asset.get("article_title")
                    or asset.get("model")
                    or source_name
                ),
            }
            for asset_key, _index, asset, image_bytes, source_name in entries
        ]
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TEXT CUTOUT</div>'
            '<div class="section-title">Manual Subject Cutout</div></div>'
            '<div class="section-count">Tested composition · Live</div></div>',
            unsafe_allow_html=True,
        )
        _render_manual_subject_cutout(
            state=state,
            assets=assets,
            crop_store=st.session_state.live_visual_crops,
            crop_store_name="live_visual_crops",
            state_id="live-cricket-manual-subject",
            default_headline=str(
                (st.session_state.get("live_approved_script") or {}).get("headline") or ""
            ),
            handoff="cricket",
            slide_count=slide_count,
            assignment_store=st.session_state.live_visual_assignments,
            approval_state="live_visuals_approved",
        )

    if visual_option == "Option 5 · Stats Card":
        _render_stats_card(live=True, slide_count=slide_count)

    if visual_option == "Option 6 · Quote Card":
        _render_quote_card(live=True, slide_count=slide_count)

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
                output = Path("output/live") / f"{story_id}.mp4"
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
                    st.session_state.live_rendered_video_path = str(output)
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


def _render_live_script():
    script = st.session_state.get("live_script_data")

    if not isinstance(script, dict):
        if st.button(
            "Retry Scriptwriter" if st.session_state.get("live_script_error") else "Generate Script",
            type="primary",
            width="stretch",
            key="live-generate-script",
        ):
            st.session_state.live_script_error = ""
            try:
                with st.spinner("Writing the Short…"):
                    _live_generate_script()
            except Exception as exc:
                st.session_state.live_script_error = f"{type(exc).__name__}: {exc}"
            st.rerun()
        if st.session_state.get("live_script_error"):
            st.error("Scriptwriter failed: " + st.session_state.live_script_error)
        else:
            st.info("Press Generate Script to start the Scriptwriter.")
        return

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

    edited_voiceovers = []
    for index, scene in enumerate(script.get("script") or [], 1):
        edited_voiceovers.append(
            st.text_area(
                f"Slide {index} narration",
                value=str(scene.get("voiceover") or ""),
                height=110,
                key=f"live-script-scene-{story_id}-{index}",
            )
        )

    if st.button(
        "Approve script and hand to Audio",
        type="primary",
        width="stretch",
        key="live-approve-script",
    ):
        try:
            if st.session_state.get("live_topics_profile") == "niche_sports":
                from niche_sports_script_writer import apply_niche_script_edits
                approved = apply_niche_script_edits(
                    script,
                    edited_voiceovers,
                    headline=edited_headline if st.session_state.live_headline_enabled else "",
                )
            else:
                from script_writer import apply_script_edits
                approved = apply_script_edits(
                    script,
                    edited_voiceovers,
                    headline=edited_headline if st.session_state.live_headline_enabled else "",
                    validate=True,
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
    if is_top5:
        script = st.session_state.live_top5_script_handoff
        slides = list(script.get("slides") or []) if isinstance(script, dict) else []
        title = str(slides[0].get("headline") or "").strip() if slides else ""
        if not isinstance(script, dict) or len(slides) != 6 or not title:
            st.info("Approve the Top-5 Scriptwriter result first.")
            return
        video_path = Path(st.session_state.live_rendered_video_path)
        story_id = "top5"
    else:
        video_path = Path(st.session_state.live_rendered_video_path)
        script = st.session_state.live_approved_script
        story = st.session_state.live_topics[st.session_state.live_selected_topic]
        story_id = _live_story_key(story)

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">UPLOAD QC</div>'
        '<div class="section-title">Final video and publish metadata</div></div>'
        '<div class="section-count">one approval</div>',
        unsafe_allow_html=True,
    )
    if not video_path.is_file():
        st.info("The rendered video is not available yet.")
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
    from queue import Empty, Queue
    import time

    from renderer import build_top5_card_preview
    from top5_script_writer import estimate_speech_seconds, generate_top5_script, validate_top5_script

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
                from topic_fetcher import fetch_top5_topics
                new_topics = fetch_top5_topics(more=more, exclude_topics=existing, limit=20)
            st.session_state.live_top5_topics = existing + new_topics
            st.session_state.live_top5_selected = [] if not more else st.session_state.live_top5_selected
            if not more:
                st.session_state.live_top5_topic_open_tile = None
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
            valid, reason = validate_top5_script(edited, stories)
            if not valid:
                st.error(f"Edited Top-5 script failed validation: {reason}")
            else:
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
            if st.button(
                "Generate Top-5 Audio",
                type="primary",
                width="stretch",
                key="live-top5-generate-audio",
            ):
                try:
                    with st.spinner("Generating the six spoken Top-5 lines…"):
                        audio = generate_top5_audio(handoff, output_dir="output/live/top5_audio")
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
                st.audio(scene["path"], format="audio/mp3")
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
            '<div class="section-title">Build and review all six slides</div></div>'
            '<div class="canvas-copy">Use the approved Scriptwriter handoff with Automatic Scraper, Manual Scraper, Real Image Search, AI Generation, Stats Card or Quote Card. Review the actual 1080 × 1920 card before approving.</div></div>',
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

        option = st.pills(
            "Visual source",
            VISUAL_OPTIONS,
            default=st.session_state.live_visual_option,
            key="live_visual_option",
            label_visibility="collapsed",
        ) or VISUAL_OPTIONS[0]

        if option == "Option 3 · Real Image Search":
            st.info("Option 3 · Real Image Search is WIP in the Top-5 pipeline.")
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

            for start in range(0, len(assets), 3):
                cols = st.columns(3, gap="medium")
                for offset, raw_asset in enumerate(assets[start:start + 3]):
                    index = start + offset
                    asset = dict(raw_asset)
                    asset_key = _visual_asset_key(f"live-{result_key}", index, asset)
                    cropped = st.session_state.live_visual_crops.get(asset_key)
                    source = str(asset.get("publisher") or asset.get("source") or asset.get("model") or "Web source").strip()
                    label = str(asset.get("article_title") or asset.get("title") or asset.get("model") or "Selected visual").strip()
                    preview = _fit_visual_preview(cropped if cropped else asset.get("bytes"), 300, 533)
                    with cols[offset]:
                        if preview is not None:
                            st.image(preview, width="stretch")
                        st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="visual-detail">{label}</div>', unsafe_allow_html=True)
                        if cropped:
                            st.markdown('<span class="visual-crop-label">CROP APPLIED</span>', unsafe_allow_html=True)
                        use_col, crop_col = st.columns(2, gap="small")
                        with use_col:
                            if st.button("Use this image", type="primary", width="stretch", key=f"live-top5-use-{active_slide}-{result_key}-{index}"):
                                selected_bytes = bytes(cropped) if cropped else bytes(asset.get("bytes") or b"")
                                st.session_state.live_visual_assignments[active_slide] = {
                                    "asset_key": asset_key,
                                    "result_key": result_key,
                                    "source": source,
                                    "label": label,
                                    "bytes": selected_bytes,
                                    "preview_bytes": build_top5_card_preview(
                                        selected_bytes, headline, body,
                                        story_number=story_number,
                                        total_stories=5,
                                        source_label=source,
                                        subject_cutout=False,
                                    ),
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
        elif option == "Option 5 · Stats Card":
            st.session_state.live_visual_result = st.session_state.live_top5_visual_results.get(story_number) or {"assets": []}
            st.session_state.live_manual_visual_result = st.session_state.live_top5_manual_visual_results.get(active_slide) or {}
            st.session_state.live_real_image_result = st.session_state.live_top5_real_image_results.get(active_slide) or {}
            st.session_state.live_ai_image_result = st.session_state.live_top5_ai_image_results.get(active_slide) or {}
            _render_stats_card(live=True, slide_count=6)
        else:
            st.session_state.live_visual_result = st.session_state.live_top5_visual_results.get(story_number) or {"assets": []}
            st.session_state.live_manual_visual_result = st.session_state.live_top5_manual_visual_results.get(active_slide) or {}
            st.session_state.live_real_image_result = st.session_state.live_top5_real_image_results.get(active_slide) or {}
            st.session_state.live_ai_image_result = st.session_state.live_top5_ai_image_results.get(active_slide) or {}
            _render_quote_card(live=True, slide_count=6)

        assignment = assignments.get(active_slide)
        if assignment:
            st.divider()
            st.markdown('<div class="mini-label">CURRENT ATTACHMENT · ACTUAL RENDER</div>', unsafe_allow_html=True)
            preview = assignment.get("preview_bytes") or assignment.get("bytes")
            if preview:
                st.image(preview, width=420)
            st.caption(f'{assignment.get("source") or "Visual"} · {assignment.get("label") or "Selected"}')
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
            output = Path("output/live/top5") / f"{key}.mp4"
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                with st.spinner("Rendering the final Top-5 Short…"):
                    render_production_video(
                        script, audio, None, visuals,
                        output_path=output,
                        headline_enabled=False,
                    )
                st.session_state.live_rendered_video_path = str(output)
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

    if st.session_state.live_production_line == "youtube_trends":
        render_youtube_trends_topic_fetcher(live=True)
        return

    if st.session_state.live_production_line == "top_5":
        return render_live_top5()


    if st.session_state.live_production_line == "otd":
        st.space("medium")
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">OTD · WIP</div>'
            '<div class="section-title">On This Day</div></div></div>',
            unsafe_allow_html=True,
        )
        st.info("This production line is reserved for the On This Day design we are building next.")
        if st.button("← Back to production lines", key="live-back-from-otd"):
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
                        from topic_fetcher import fetch_topics
                        st.session_state.live_topics = fetch_topics(
                            profile,
                            more=False,
                            exclude_topics=[],
                            limit=20,
                        )
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
                            from topic_fetcher import fetch_topics
                            st.session_state.live_topics = fetch_topics(
                                profile,
                                more=False,
                                exclude_topics=[],
                                limit=20,
                            )
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
                    from topic_fetcher import fetch_topics
                    st.session_state.live_topics = fetch_topics(
                        profile,
                        more=False,
                        exclude_topics=[],
                        limit=20,
                    )
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
        if not isinstance(st.session_state.live_approved_audio, dict) or not isinstance(st.session_state.live_subtitle_data, dict):
            if st.session_state.live_handoff_error:
                st.error(st.session_state.live_handoff_error)
            if st.button(
                "Retry Audio / Subtitles" if st.session_state.live_handoff_error else "Generate Audio + Subtitles",
                type="primary",
                width="stretch",
                key="live-generate-handoffs-stage",
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
        '<div class="canvas-copy">These are current YouTube search signals that already have relevant news published today.</div></div></div>',
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
                f'{" · BREAKOUT" if item["breakout"] else ""}'
                f'{" · autocomplete" if item["youtube_autocomplete"] else ""}</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f'Story subject: {item["keyword"]} · '
                f'Trend: {item["trend_query"]} · '
                f'{item["news_count"]} current '
                f'{"story" if item["news_count"] == 1 else "stories"}'
            )
            st.caption(item["hashtag"])
        with mid:
            st.caption(f'Story signal {item["score"]:.0f}')
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
                        with st.spinner(f'Searching today’s news for “{keyword}”…'):
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
                f'No news published today matched “{st.session_state[keyword_key]}”. Choose another trend.'
            )
        return

    keyword = st.session_state[keyword_key]
    st.divider()
    st.markdown(
        f'<div class="section-head"><div><div class="eyebrow">NEWS PUBLISHED TODAY</div>'
        f'<div class="section-title">{keyword}</div></div>'
        f'<div class="section-count">{len(topics)} headlines</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Only articles published today in the factory timezone are included.")

    if st.button(
        "Find 20 more from today",
        width="stretch",
        key=f"{button_prefix}more",
    ):
        with st.spinner(f'Finding more news published today for “{keyword}”…'):
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

def render_topic_fetcher():
    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">01 · STORY DESK</div>'
        '<div class="canvas-title">Story desk</div></div></div>',
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
            "stats_card_result": None, "stats_card_image_selection": None,
             "stats_card_image_crop": None, "stats_card_approved": False,
            "quote_card_image_selection": None,
            "quote_card_image_crop": None,
            "quote_card_preview": None,
            "quote_card_quote": "",
            "quote_card_attribution": "",
            "quote_card_slide": 1,
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
        st.session_state.stats_card_result = None
        st.session_state.stats_card_image_selection = None
        st.session_state.quote_card_image_selection = None
        st.session_state.quote_card_image_crop = None
        st.session_state.quote_card_preview = None
        st.session_state.quote_card_quote = ""
        st.session_state.quote_card_attribution = ""
        st.session_state.quote_card_slide = 1
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
        f'<div class="canvas-head"><div><div class="eyebrow">02 · SCRIPT</div>'
        f'<div class="canvas-title">Shape the Short</div>'
        f'<div class="canvas-copy">{topic.title}</div></div></div>',
        unsafe_allow_html=True,
    )
    top_left, top_right=st.columns([1,.72],gap="medium")
    with top_left:
        language=st.pills("Language",["English","Hindi","Telugu"],default="English",key="script_language",label_visibility="collapsed") or "English"
    with top_right:
        if st.button("Generate script",type="primary",width="stretch"):
            for key in (
                headline_toggle_key,
                headline_text_key,
                *(f"script-slide-{story_key}-{index}" for index in range(1, 7)),
            ):
                st.session_state.pop(key, None)
            with st.spinner("Writing the Short…"):
                st.session_state.script_data = _script_for_topic(
                    topic,
                    st.session_state.get("topic_desk_profile") or "",
                    language.casefold(),
                )
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

    script=st.session_state.script_data
    if not script:
        return

    left,right=st.columns([1.55,.55],gap="large")
    with left:
        with st.container(key="script-editor"):
            st.markdown('<div class="mini-label">Opening</div>',unsafe_allow_html=True)
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
            st.markdown('<div style="height:.7rem"></div>',unsafe_allow_html=True)
            quote = str(script.get("quote") or "").strip()
            quote_attribution = str(script.get("quote_attribution") or "").strip()
            if quote:
                st.markdown('<div class="mini-label">Quote</div>',unsafe_allow_html=True)
                st.text(quote)
                if quote_attribution:
                    st.caption(f"— {quote_attribution}")
            edited_voiceovers=[]
            for index,scene in enumerate(script.get("script",[]),1):
                st.markdown(f'<div class="scene-label">Scene {index}</div>',unsafe_allow_html=True)
                edited_voiceovers.append(st.text_area("Narration",value=scene.get("voiceover",""),height=105,key=f"script-slide-{story_key}-{index}",label_visibility="collapsed"))
            if st.button("Approve script",type="primary",width="stretch"):
                try:
                    if st.session_state.get("topic_desk_profile") == "niche_sports":
                        from niche_sports_script_writer import apply_niche_script_edits
                        approved = apply_niche_script_edits(
                            script,
                            edited_voiceovers,
                            headline=edited_headline if headline_enabled else "",
                        )
                    else:
                        approved = apply_script_edits(
                            script,
                            edited_voiceovers,
                            headline=edited_headline if headline_enabled else "",
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
                    st.session_state.quote_card_quote = str(approved.get("quote") or "")
                    st.session_state.quote_card_attribution = str(
                        approved.get("quote_attribution") or ""
                    )
                    quote_slide = int(approved.get("quote_slide") or 1)
                    st.session_state.quote_card_slide = max(1, min(4, quote_slide))
                    st.session_state.quote_card_image_selection = None
                    st.session_state.quote_card_image_crop = None
                    st.session_state.quote_card_preview = None
                except ValueError as exc:
                    st.error(str(exc))

    with right:
        st.markdown('<div class="inspector">',unsafe_allow_html=True)
        st.markdown('<div class="mini-label">Story</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="font-weight:820;line-height:1.35;margin:.25rem 0 1rem;">{topic.title}</div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Language</span><span class="inspector-value">'+str(script.get("language_used") or language)+'</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Scenes</span><span class="inspector-value">'+str(len(script.get("script") or []))+'</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Word count</span><span class="inspector-value">'+str(script.get("word_count") or "")+'</span></div>',unsafe_allow_html=True)
        if st.session_state.approved_script:
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);">Approved</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
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
                st.session_state.real_image_result = search_images(query)
                st.session_state.visual_crops = {}

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

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Real images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "real-search", _test_visual_slide_count())

def _render_manual_ai_images():
    from visual_generator import generate_images

    st.subheader("AI Generation")
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
            width="stretch",
        )

    if generate:
        query = query.strip()
        if not query:
            st.warning("Enter a prompt first.")
        else:
            with st.spinner("Generating images…"):
                st.session_state.ai_image_result = generate_images(query)
                st.session_state.visual_crops = {}

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

    st.markdown('<div class="section-head"><div><div class="eyebrow">MEDIA BOARD</div><div class="section-title">Generated images</div></div><div class="section-count">review / crop</div></div>', unsafe_allow_html=True)
    _render_visual_asset_pool(assets, "ai-generation", _test_visual_slide_count())

def render_visuals():
    st.header("04 · Visuals")
    cricket_test = st.session_state.get("topic_desk_profile") in {"cricket_india_asia", "cricket_global"}
    visual_options = CRICKET_TEST_VISUAL_OPTIONS if cricket_test else VISUAL_OPTIONS
    selected_option = st.session_state.get("visual_test_mode")
    if selected_option not in visual_options:
        selected_option = visual_options[0]
    mode = st.pills(
        "Visual test",
        visual_options,
        default=selected_option,
        key="visual_test_mode",
        label_visibility="collapsed",
    ) or visual_options[0]

    script = st.session_state.get("approved_script") or st.session_state.get("script_data")
    slide_count = len(script.get("script") or []) if isinstance(script, dict) else 4
    slide_count = max(1, slide_count)

    if mode.startswith("Option 1"):
        render_visuals_crawler()
    elif mode.startswith("Option 2"):
        _render_manual_crawler()
    elif mode.startswith("Option 3"):
        _render_manual_real_images()
    elif mode.startswith("Option 4"):
        _render_manual_ai_images()
    elif mode.startswith("Option 5"):
        _render_stats_card(live=False, slide_count=slide_count)
    elif mode.startswith("Option 6"):
        _render_quote_card(live=False, slide_count=slide_count)
    else:
        entries = _stats_card_pool_entries(live=False)
        state = st.session_state.manual_subject_cutout
        assets = [
            {
                "asset_key": asset_key,
                "bytes": image_bytes,
                "source": source_name,
                "label": str(
                    asset.get("article_title")
                    or asset.get("model")
                    or source_name
                ),
            }
            for asset_key, _index, asset, image_bytes, source_name in entries
        ]
        _render_manual_subject_cutout(
            state=state,
            assets=assets,
            crop_store=st.session_state.visual_crops,
            crop_store_name="visual_crops",
            state_id="test-cricket-manual-subject",
            default_headline=str((script or {}).get("headline") or ""),
            handoff="cricket",
            slide_count=slide_count,
            assignment_store=st.session_state.visual_assignments,
            approval_state="visuals_approved",
        )

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
        st.info(
            f"{len(assignments)}/{slide_count} visuals attached. "
            "Choose visuals above to build the Renderer handoff."
        )



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
            from subtitles import generate_subtitles
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
    from audio import approve_audio, generate_audio

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
        language=st.pills("Language",languages,default=default_language.title(),key="audio_language",label_visibility="collapsed") or default_language.title()
        st.markdown('<div class="mini-label" style="margin:.55rem 0;">VOICE</div>',unsafe_allow_html=True)
        st.caption("HYPE COMMENTATOR · female Indian voice · native Edge-TTS word timings")
        if st.button("Generate audio",type="primary",width="stretch"):
            selected=dict(script); selected["language_used"]=language.casefold()
            with st.spinner("Generating voiceover…"):
                try:
                    st.session_state.audio_data=generate_audio(selected)
                    st.session_state.approved_audio=None
                except (RuntimeError,ValueError) as exc:
                    st.error(str(exc)); st.session_state.audio_data=None; st.session_state.approved_audio=None
            st.session_state.subtitle_data=None
            st.session_state.approved_subtitles=None

        audio=st.session_state.audio_data
        if audio:
            for scene in audio["scenes"]:
                with st.container(key=f"audio-scene-{scene['scene']}"):
                    st.markdown(f'**Scene {scene["scene"]}** <span class="topic-meta">· {scene["duration"]:.2f}s · {len(scene["timings"])} timings</span>',unsafe_allow_html=True)
                    st.audio(scene["path"],format="audio/mp3")
                    st.caption("Cached" if scene["from_cache"] else "Fresh TTS generation")
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
            audio=st.session_state.audio_data
            if audio:
                correction="Speed corrected" if audio["duration_corrected"] else "No correction"
                for label,value in [("Voice",audio["voice"]),("Rate",f'{audio["rate_percent"]:+.0f}%'),("Duration",f'{audio["total_duration"]:.2f}s'),("Timing",correction)]:
                    st.markdown(f'<div class="inspector-line"><span>{label}</span><span class="inspector-value">{value}</span></div>',unsafe_allow_html=True)
                if st.session_state.approved_audio:
                    st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--success-soft);color:var(--success);">Approved</span></div>',unsafe_allow_html=True)
            else:
                st.caption("Audio metrics will appear after generation.")
            st.markdown('</div>',unsafe_allow_html=True)

if st.session_state.app_mode == "home":
    _render_home()
elif st.session_state.app_mode == "test":
    _render_app_sidebar()
    if st.session_state.test_production_line is None:
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
                        if eyebrow in {"01 · DEEP-DIVE", "04"}:
                            st.session_state.test_stage = "01 · Topic Fetcher"
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
        elif line_name in {"Deep-Dive", "YT Trends"}:
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
                st.session_state.test_top5_visual_card_results = {}
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
                        from topic_fetcher import fetch_top5_topics
                        new_topics = fetch_top5_topics(
                            more=more,
                            exclude_topics=exclude,
                            limit=20,
                        )
                    st.session_state.test_top5_topics = existing + new_topics
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
                                st.session_state.test_top5_visual_card_results = {}
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
                                st.session_state.test_top5_visual_card_results = {}
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
                                st.session_state.test_top5_visual_card_results = {}
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
            from top5_script_writer import estimate_speech_seconds, generate_top5_script, validate_top5_script

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
                        valid, reason = validate_top5_script(edited, stories)
                        if not valid:
                            st.error(f"Edited Top-5 script failed validation: {reason}")
                        else:
                            st.session_state.test_top5_audio_data = None
                            st.session_state.test_top5_audio_handoff = None
                            st.session_state.test_top5_visual_results = {}
                            st.session_state.test_top5_visual_selected = {}
                            st.session_state.test_top5_visual_previews = {}
                            st.session_state.test_top5_visual_assignments = {}
                            st.session_state.test_top5_visual_card_results = {}
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
            from audio import approve_top5_audio, generate_top5_audio

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
                ):
                    with st.spinner("Generating the six spoken Top-5 lines…"):
                        try:
                            st.session_state.test_top5_audio_data = generate_top5_audio(handoff)
                            st.session_state.test_top5_audio_handoff = None
                            st.rerun()
                        except (RuntimeError, ValueError) as exc:
                            st.session_state.test_top5_audio_data = None
                            st.session_state.test_top5_audio_handoff = None
                            st.error(str(exc))

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
                            st.audio(scene["path"], format="audio/mp3")
                            st.caption("Cached" if scene["from_cache"] else "Fresh TTS generation")

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
                build_quote_card_preview,
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
                '<div class="section-count">9 visual options</div></div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="mini-label">9 VISUAL OPTIONS</div>', unsafe_allow_html=True)
            visual_option = st.pills(
                "Visual source",
                TOP5_VISUAL_OPTIONS,
                key="test_top5_visual_playground_option",
                label_visibility="collapsed",
            ) or TOP5_VISUAL_OPTIONS[2]

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
                if visual_option not in {"Option 7 · Subject Cutout", "Option 9 · Manual Subject Cutout"}:
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
                    key="test_top5_visual_playground_query",
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
                    key="test_top5_visual_playground_query",
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
                prompt = st.text_area(
                    "AI image prompt",
                    key="test_top5_visual_playground_query",
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
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_results = []
                                st.error(f"{type(exc).__name__}: {exc}")
                assets = list(st.session_state.get("test_top5_visual_playground_results") or [])

            elif visual_option == "Option 5 · Stats Card":
                st.text_input(
                    "Stats-card query",
                    key="test_top5_visual_playground_stats_query",
                    placeholder="Virat Kohli last 10 ODI innings",
                )
                if st.button("Build Stats Card", type="primary", width="stretch", key="test-top5-playground-stats"):
                    query = st.session_state.test_top5_visual_playground_stats_query.strip()
                    if not query:
                        st.warning("Enter a stats query first.")
                    else:
                        with st.spinner("Building stats card…"):
                            try:
                                from stats_card import build_test_stats_card
                                result = build_test_stats_card(query, current_image)
                                st.session_state.test_top5_visual_playground_render = bytes(result.get("bytes") or b"")
                                st.session_state.test_top5_visual_playground_source = "Stats Card"
                            except Exception as exc:
                                st.session_state.test_top5_visual_playground_render = None
                                st.error(f"{type(exc).__name__}: {exc}")

            elif visual_option == "Option 6 · Quote Card":
                st.text_area(
                    "Quote",
                    key="test_top5_visual_playground_quote",
                    height=90,
                    placeholder="Enter the identified quote",
                )
                st.text_input(
                    "Attribution",
                    key="test_top5_visual_playground_attribution",
                    placeholder="Player / coach / official",
                )
                if st.button("Build Quote Card", type="primary", width="stretch", key="test-top5-playground-quote"):
                    quote = st.session_state.test_top5_visual_playground_quote.strip()
                    attribution = st.session_state.test_top5_visual_playground_attribution.strip()
                    if not quote or not attribution:
                        st.warning("Enter both the quote and attribution.")
                    else:
                        try:
                            st.session_state.test_top5_visual_playground_render = build_quote_card_preview(
                                current_image,
                                quote,
                                attribution,
                                source_label=current_source,
                            )
                            st.session_state.test_top5_visual_playground_source = "Quote Card"
                        except (ValueError, OSError) as exc:
                            st.session_state.test_top5_visual_playground_render = None
                            st.error(str(exc))

            elif visual_option == "Option 9 · Manual Subject Cutout":
                state = st.session_state.test_top5_manual_subject_playground
                image_buffer = BytesIO()
                current_image.convert("RGB").save(image_buffer, format="JPEG", quality=92, optimize=True)
                playground_bytes = image_buffer.getvalue()
                _render_manual_subject_cutout(
                    state=state,
                    assets=[{
                        "asset_key": f"top5-playground-{hashlib.sha1(playground_bytes).hexdigest()[:12]}",
                        "bytes": playground_bytes,
                        "source": current_source,
                        "label": "Current test image",
                    }],
                    crop_store=st.session_state.test_top5_visual_crops,
                    crop_store_name="test_top5_visual_crops",
                    state_id="test-top5-manual-subject-playground",
                    default_headline=st.session_state.test_top5_visual_playground_headline,
                )

            elif visual_option == "Option 8 · Body Card · WIP":
                st.info("Option 8 · Body Card is WIP. No Body Card renderer is active yet.")

            elif visual_option == "Option 7 · Subject Cutout":
                st.caption("Runs BiRefNet locally on the current image and uses the detected subject to drive headline placement and controlled occlusion.")
                if st.button("Render Subject Cutout", type="primary", width="stretch", key="test-top5-playground-subject"):
                    with st.spinner("Running local BiRefNet…"):
                        try:
                            st.session_state.test_top5_visual_playground_render = build_top5_card_preview(
                                current_image,
                                st.session_state.test_top5_visual_playground_headline,
                                st.session_state.test_top5_visual_playground_body,
                                story_number=1,
                                total_stories=5,
                                source_label=current_source,
                                subject_cutout=True,
                            )
                        except (ValueError, OSError, RuntimeError, ImportError) as exc:
                            st.session_state.test_top5_visual_playground_render = None
                            st.error(str(exc))

            if assets:
                st.markdown(
                    '<div class="section-head"><div><div class="eyebrow">IMAGE POOL</div>'
                    '<div class="section-title">Choose the source image</div></div>'
                    f'<div class="section-count">{len(assets)} images</div></div>',
                    unsafe_allow_html=True,
                )
                for start in range(0, len(assets), 3):
                    cols = st.columns(min(3, len(assets) - start), gap="medium")
                    for offset, asset in enumerate(assets[start:start + 3]):
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
                st.image(rendered, width=420)

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

                    visual_option = st.pills(
                        "Visual source",
                        TOP5_VISUAL_OPTIONS,
                        key="test_top5_visual_option",
                        label_visibility="collapsed",
                    ) or TOP5_VISUAL_OPTIONS[0]

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

                        if card_type == "quote" and isinstance(card_data, dict):
                            assignment["quote_card"] = dict(card_data)
                        elif card_type == "stats" and isinstance(card_data, dict):
                            assignment["card_layout"] = dict(card_data.get("layout") or {})
                        elif card_type == "manual-subject" and isinstance(card_data, dict):
                            assignment["manual_subject_cutout"] = dict(card_data)
                        else:
                            assignment["top5_card"] = {
                                "headline": selected_headline,
                                "body": selected_body,
                                "story_number": story_number,
                                "total_stories": 5,
                                "language": str(script.get("language_used") or "english").casefold(),
                                "subject_cutout": bool(subject_cutout),
                            }

                        if preview_bytes is None:
                            try:
                                if card_type == "editorial":
                                    preview_bytes = build_top5_card_preview(
                                        selected_bytes,
                                        selected_headline,
                                        selected_body,
                                        story_number=story_number,
                                        total_stories=5,
                                        source_label=source,
                                        subject_cutout=subject_cutout,
                                    )
                                elif card_type == "quote" and isinstance(card_data, dict):
                                    preview_bytes = build_quote_card_preview(
                                        selected_bytes,
                                        str(card_data.get("quote") or ""),
                                        str(card_data.get("attribution") or ""),
                                        source_label=source,
                                    )
                                elif card_type == "manual-subject" and isinstance(card_data, dict):
                                    preview_bytes = build_manual_subject_cutout_preview(
                                        selected_bytes,
                                        str(card_data.get("headline") or selected_headline),
                                        mode=str(card_data.get("mode") or "negative-space"),
                                        text_polygon=card_data.get("text_polygon") or (),
                                        font_size=int(card_data.get("font_size") or 150),
                                        font=str(card_data.get("font") or "Barlow Condensed"),
                                        style=str(card_data.get("style") or "Crisp Outline"),
                                    )
                            except (ValueError, OSError, RuntimeError, ImportError) as exc:
                                st.error(str(exc))
                                return False

                        if preview_bytes:
                            assignment["preview_bytes"] = bytes(preview_bytes)

                        st.session_state.test_top5_visual_assignments[active_slide] = assignment
                        st.session_state.test_top5_visual_previews[active_slide] = bytes(preview_bytes or selected_bytes)
                        st.session_state.test_top5_visual_handoff = None
                        st.session_state.test_top5_rendered_video_path = None
                        st.session_state.test_top5_visual_card_results.pop(active_slide, None)
                        return True

                    def _top5_render_asset_pool(assets, result_key, subject_cutout=False):
                        if not assets:
                            st.info("No images are currently available from this option.")
                            return
                        for start_index in range(0, len(assets), 3):
                            cols = st.columns(3, gap="medium")
                            for offset, (col, asset) in enumerate(zip(cols, assets[start_index:start_index + 3])):
                                index = start_index + offset
                                with col:
                                    raw = asset.get("bytes")
                                    source = _top5_asset_source(asset)
                                    label = _top5_asset_label(asset)
                                    asset_key = _visual_asset_key(result_key, index, asset)
                                    cropped = st.session_state.test_top5_visual_crops.get(asset_key)
                                    preview_bytes = cropped if cropped else raw
                                    preview = _top5_fit_preview(preview_bytes)
                                    if preview is not None:
                                        st.image(preview, width="stretch")
                                    st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
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
                                            st.session_state.test_top5_visual_card_results.pop(active_slide, None)
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

                    if visual_option == "Option 8 · Body Card · WIP":
                        st.info("Option 8 · Body Card is WIP. No Body Card renderer is active yet.")

                    if visual_option == "Option 7 · Subject Cutout":
                        image_result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        image_assets = list(image_result.get("assets") or [])
                        if not image_assets:
                            st.info(
                                "Run one of Options 1–4 for this slide first. Subject Cutout reuses the existing image pool and adds the foreground subject layer locally."
                            )
                        else:
                            st.caption(
                                "BiRefNet runs locally. The first use downloads the model once; later uses stay local and free."
                            )
                            _top5_render_asset_pool(
                                image_assets,
                                "subject-cutout",
                                subject_cutout=True,
                            )

                    if visual_option == "Option 9 · Manual Subject Cutout":
                        image_result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        image_assets = list(image_result.get("assets") or [])
                        if not image_assets:
                            st.info(
                                "Run one of Options 1–4 for this slide first. Manual Subject Cutout reuses the existing image pool and does not run another image search."
                            )
                        else:
                            manual_state = st.session_state.test_top5_manual_subject_cutouts.setdefault(active_slide, {})
                            manual_assets = [
                            {
                                "asset_key": _visual_asset_key(f"manual-subject-{active_slide}", index, asset),
                                "bytes": asset.get("bytes"),
                                "source": _top5_asset_source(asset),
                                "label": _top5_asset_label(asset),
                            }
                            for index, asset in enumerate(image_assets)
                            ]
                            _render_manual_subject_cutout(
                                state=manual_state,
                                assets=manual_assets,
                                crop_store=st.session_state.test_top5_visual_crops,
                                crop_store_name="test_top5_visual_crops",
                                state_id=f"test-top5-manual-subject-{active_slide}",
                                default_headline=headline,
                                handoff="top5",
                                active_slide=active_slide,
                            )

                    if visual_option in {"Option 5 · Stats Card", "Option 6 · Quote Card"}:
                        image_result = st.session_state.test_top5_visual_results.get(active_slide) or {}
                        image_assets = list(image_result.get("assets") or [])
                        if not image_assets:
                            st.info(
                                "Run one of Options 1–4 for this slide first. Stats Card and Quote Card reuse the existing image pool and do not run another image search."
                            )
                        else:
                            st.markdown(
                                '<div class="section-head"><div><div class="eyebrow">EXISTING IMAGE POOL</div>'
                                '<div class="section-title">Choose the image for this card</div></div>'
                                '<div class="section-count">reuse this slide pool</div></div>',
                                unsafe_allow_html=True,
                            )
                            choices = []
                            for index, asset in enumerate(image_assets):
                                asset_key = _visual_asset_key(f"top5-card-{active_slide}", index, asset)
                                source = _top5_asset_source(asset)
                                label = _top5_asset_label(asset)
                                choices.append((index, asset, asset_key, source, label))

                            card_choice_key = f"test-top5-card-choice-{active_slide}"
                            card_index = st.selectbox(
                                "Card image",
                                list(range(len(choices))),
                                index=min(int(st.session_state.get(card_choice_key) or 0), len(choices) - 1),
                                key=card_choice_key,
                                format_func=lambda i: choices[i][4][:80],
                            )
                            _, card_asset, card_asset_key, card_source, card_label = choices[card_index]
                            cropped = st.session_state.test_top5_visual_crops.get(card_asset_key)
                            card_source_bytes = bytes(cropped) if cropped else bytes(card_asset.get("bytes") or b"")
                            card_preview = _top5_fit_preview(card_source_bytes)
                            if card_preview is not None:
                                st.image(card_preview, width=300)
                            st.caption(f"{card_source} · {card_label}")

                            if st.button(
                                "Crop / reposition image",
                                width="stretch",
                                key=f"test-top5-card-crop-{active_slide}",
                            ):
                                _crop_visual_dialog(card_asset_key, bytes(card_asset.get("bytes") or b""), card_label, crop_store="test_top5_visual_crops")

                            if visual_option == "Option 5 · Stats Card":
                                from stats_card import StatsCardError, build_stats_card

                                query = st.text_input(
                                    "Stats query",
                                    placeholder="e.g. Virat Kohli ODI stats · India vs Pakistan H2H stats",
                                    key=f"test-top5-stats-query-{active_slide}",
                                )
                                if st.button(
                                    "Build Stats Card",
                                    type="primary",
                                    width="stretch",
                                    key=f"test-top5-stats-build-{active_slide}",
                                ):
                                    query = query.strip()
                                    if not query:
                                        st.warning("Enter a stats query first.")
                                    else:
                                        with st.spinner("Building the Stats Card…"):
                                            try:
                                                result = build_stats_card(query, card_source_bytes)
                                                st.session_state.test_top5_visual_card_results[active_slide] = {
                                                    "type": "stats",
                                                    "result": result,
                                                }
                                            except (StatsCardError, OSError, RuntimeError) as exc:
                                                st.session_state.test_top5_visual_card_results[active_slide] = {
                                                    "type": "stats",
                                                    "error": str(exc),
                                                }
                                        st.rerun()
                                card_result = st.session_state.test_top5_visual_card_results.get(active_slide) or {}
                                if card_result.get("error"):
                                    st.error(card_result["error"])
                                elif card_result.get("type") == "stats" and isinstance(card_result.get("result"), dict):
                                    result = card_result["result"]
                                    st.markdown('<div class="mini-label">RENDERED STATS CARD</div>', unsafe_allow_html=True)
                                    st.image(result["bytes"], width=420)
                                    st.caption(f'{result.get("label") or "Stats Card"} · {result.get("source") or "Cricket data"}')
                                    if st.button(
                                        f"Use Stats Card for slide {active_slide}",
                                        type="primary",
                                        width="stretch",
                                        key=f"test-top5-stats-use-{active_slide}",
                                    ):
                                        _top5_store_assignment(
                                            {"asset_key": f"stats-card-{active_slide}"},
                                            result["bytes"],
                                            "stats-card",
                                            f"Stats Card · {result.get('source') or 'Cricket data'}",
                                            str(result.get("label") or "Stats Card"),
                                            card_type="stats",
                                            card_data=result,
                                            preview_bytes=result["bytes"],
                                        )
                                        st.rerun()

                            else:
                                quote = st.text_area(
                                    "Quote",
                                    key=f"test-top5-quote-{active_slide}",
                                    height=105,
                                    max_chars=280,
                                )
                                attribution = st.text_input(
                                    "Attribution",
                                    key=f"test-top5-quote-attribution-{active_slide}",
                                    max_chars=120,
                                )
                                if st.button(
                                    "Preview Quote Card",
                                    type="primary",
                                    width="stretch",
                                    key=f"test-top5-quote-preview-{active_slide}",
                                ):
                                    quote = quote.strip()
                                    attribution = attribution.strip()
                                    if not quote or not attribution:
                                        st.warning("Quote and attribution are required.")
                                    else:
                                        try:
                                            preview = build_quote_card_preview(
                                                card_source_bytes,
                                                quote,
                                                attribution,
                                                source_label=card_source,
                                            )
                                            st.session_state.test_top5_visual_card_results[active_slide] = {
                                                "type": "quote",
                                                "quote": quote,
                                                "attribution": attribution,
                                                "source": card_source,
                                                "label": card_label,
                                                "preview": preview,
                                                "bytes": card_source_bytes,
                                            }
                                            st.rerun()
                                        except (ValueError, OSError) as exc:
                                            st.error(str(exc))
                                card_result = st.session_state.test_top5_visual_card_results.get(active_slide) or {}
                                if card_result.get("type") == "quote" and card_result.get("preview"):
                                    st.markdown('<div class="mini-label">RENDERED QUOTE CARD</div>', unsafe_allow_html=True)
                                    st.image(card_result["preview"], width=420)
                                    st.caption("Quote Card uses the approved image and replaces the normal Top-5 editorial text with the selected quote.")
                                    if st.button(
                                        f"Use Quote Card for slide {active_slide}",
                                        type="primary",
                                        width="stretch",
                                        key=f"test-top5-quote-use-{active_slide}",
                                    ):
                                        _top5_store_assignment(
                                            {"asset_key": f"quote-card-{active_slide}"},
                                            card_result["bytes"],
                                            "quote-card",
                                            f"Quote Card · {card_result['attribution']}",
                                            card_result["quote"],
                                            card_type="quote",
                                            card_data={
                                                "quote": card_result["quote"],
                                                "attribution": card_result["attribution"],
                                                "language": "english",
                                                "source_label": card_result["source"],
                                            },
                                            preview_bytes=card_result["preview"],
                                        )
                                        st.rerun()

                    current_assignment = assignments.get(active_slide)
                    if current_assignment:
                        preview_bytes = current_assignment.get("preview_bytes") or current_assignment.get("bytes")
                        st.divider()
                        st.markdown('<div class="mini-label">CURRENT ATTACHMENT · ACTUAL RENDER</div>', unsafe_allow_html=True)
                        if preview_bytes:
                            st.image(preview_bytes, width=420)
                        st.caption(
                            f'{current_assignment.get("source") or "Visual"} · '
                            f'{current_assignment.get("label") or "Selected"}'
                        )
                        st.caption("This exact rendered frame will be handed to Renderer.")
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
    render_live_dashboard()
