import hashlib
import json
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
import streamlit as st

load_dotenv()

from audio import approve_audio, generate_audio
from script_writer import apply_script_edits, write_script
from topic_fetcher import fetch_topics
from visual_fetcher import crawl_visuals, manual_crawl_visuals, ranked_visual_search
from visual_search import search_images
from visual_generator import generate_images
from renderer import HEADLINE_TEXT, FINAL_STYLE_NAME, build_preview_bundle, render_production_video
from subtitles import generate_subtitles
from uploader import upload_video

st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

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
  --bg:#f7f7f2;
  --surface:#ffffff;
  --surface-soft:#f0f1ec;
  --surface-accent:#edf3ef;
  --ink:#1c1d1a;
  --muted:#5f655e;
  --subtle:#5f655e;
  --line:#dfe2da;
  --line-strong:#bcc2b9;
  --primary:#2b5d50;
  --primary-hover:#21483e;
  --primary-soft:#eaf1ed;
  --success:#2f6b50;
  --success-soft:#edf5ef;
  --warning:#8a5b16;
  --warning-soft:#faf4e7;
  --danger:#a23b31;
  --danger-soft:#f9ecea;
  --shadow:0 1px 2px rgba(28,29,26,.05),0 8px 24px rgba(28,29,26,.04);
  --shadow-hover:0 10px 26px rgba(28,29,26,.08);
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
.block-container{max-width:1440px;padding:24px 32px 56px;}
h1,h2,h3,h4{color:var(--ink);letter-spacing:-.04em;}
h1{font-weight:850;} h2,h3{font-weight:800;}
p{color:var(--muted);}
[data-testid="stCaptionContainer"] p,[data-testid="stMarkdownContainer"] small{color:var(--muted)!important;}
button{transition:transform .14s ease,box-shadow .14s ease,border-color .14s ease,background .14s ease;}
[data-testid="stButton"]>button,[data-testid="stFormSubmitButton"]>button{
  min-height:42px;
  border-radius:11px;
  border:1px solid var(--line-strong);
  background:var(--surface);
  color:var(--ink);
  font-weight:750;
  box-shadow:0 2px 8px rgba(16,24,40,.03);
}
[data-testid="stButton"]>button:hover,[data-testid="stFormSubmitButton"]>button:hover{
  transform:translateY(-1px);
  border-color:var(--line-strong);
  box-shadow:0 6px 16px rgba(28,29,26,.07);
}
[data-testid="stButton"]>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primary"]{
  background:var(--primary);
  border-color:var(--primary);
  color:#fff;
  box-shadow:0 7px 18px rgba(43,93,80,.16);
}
[data-testid="stButton"]>button[kind="primary"]:hover,[data-testid="stFormSubmitButton"]>button[kind="primary"]:hover{
  background:var(--primary-hover);
  border-color:var(--primary-hover);
}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{
  background:var(--surface)!important;
  color:var(--ink)!important;
  border:1px solid var(--line-strong)!important;
  border-radius:11px!important;
  box-shadow:none!important;
}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{
  border-color:var(--primary)!important;
  box-shadow:0 0 0 3px rgba(43,93,80,.12)!important;
}
[data-testid="stFileUploaderDropzone"]{
  background:var(--surface)!important;
  border:1px dashed var(--line-strong)!important;
  border-radius:12px!important;
}
[data-testid="stPills"]{
  margin-bottom:.55rem;
  overflow-x:auto;
  scrollbar-width:none;
}
[data-testid="stPills"]::-webkit-scrollbar{display:none;}
[data-testid="stPills"] button{
  background:var(--surface)!important;
  color:var(--muted)!important;
  border:1px solid var(--line)!important;
  border-radius:999px!important;
  box-shadow:none!important;
  font-weight:700!important;
  white-space:nowrap;
  min-height:36px;
}
[data-testid="stPills"] button:hover{color:var(--ink)!important;border-color:var(--line-strong)!important;transform:none;}
[data-testid="stPills"] button[aria-pressed="true"]{
  background:var(--primary)!important;
  color:#fff!important;
  border-color:var(--primary)!important;
}
[data-testid="stExpander"]{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:14px;
  box-shadow:none;
  overflow:hidden;
}
[data-testid="stExpander"] summary{padding:.8rem .95rem;color:var(--ink);}
[data-testid="stMetric"]{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:12px;
  padding:.55rem .75rem;
  box-shadow:none;
}
.stProgress > div{background:var(--surface-soft);border-radius:999px;padding:2px;}
.stProgress > div > div{background:var(--primary);border-radius:999px;}
.pipeline-wrap{margin:18px 0 20px;padding:12px 13px 11px;background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:0 1px 2px rgba(28,29,26,.03);}
.pipeline-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px;}
.pipeline-meta-label{font-size:.62rem;font-weight:820;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.pipeline-meta-value{font-size:.7rem;font-weight:800;color:var(--ink);text-align:right;}
.pipeline-steps{display:flex;gap:7px;overflow-x:auto;padding:8px 0 1px;scrollbar-width:none;}
.pipeline-steps::-webkit-scrollbar{display:none;}
.pipeline-step{flex:1 0 112px;min-width:112px;padding:8px 9px;border:1px solid var(--line);border-radius:11px;background:var(--surface);}
.pipeline-step.complete{background:var(--success-soft);border-color:#b7d8c3;}
.pipeline-step.current{background:var(--primary-soft);border-color:#b9ccc4;}
.pipeline-step-number{font-size:.56rem;font-weight:820;letter-spacing:.08em;color:var(--subtle);}
.pipeline-step.current .pipeline-step-number,.pipeline-step.current .pipeline-step-label{color:var(--primary);}
.pipeline-step.complete .pipeline-step-number,.pipeline-step.complete .pipeline-step-label{color:var(--success);}
.pipeline-step-label{margin-top:3px;font-size:.68rem;font-weight:780;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pipeline-step-state{margin-top:3px;font-size:.56rem;font-weight:760;color:var(--subtle);text-transform:uppercase;letter-spacing:.05em;}
.pipeline-step.current .pipeline-step-state{color:var(--primary);}
.pipeline-step.complete .pipeline-step-state{color:var(--success);}
.handoff-card{display:flex;align-items:center;gap:10px;margin:0 0 18px;padding:10px 12px;background:var(--success-soft);border:1px solid #b7d8c3;border-radius:12px;}
.handoff-mark{flex:0 0 auto;width:23px;height:23px;display:grid;place-items:center;border-radius:50%;background:var(--success);color:#fff;font-size:.72rem;font-weight:900;}
.handoff-title{font-size:.72rem;font-weight:820;color:var(--ink);line-height:1.2;}
.handoff-copy{margin-top:2px;font-size:.64rem;color:var(--muted);line-height:1.25;}
[data-testid="stAudio"]{border-radius:10px;}
[data-testid="stVideo"]{border-radius:16px;overflow:hidden;}
.eyebrow,.mini-label{
  font-size:.62rem;
  font-weight:820;
  letter-spacing:.14em;
  text-transform:uppercase;
  color:var(--subtle);
}
.badge{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 8px;
  border-radius:999px;
  background:var(--surface-soft);
  border:1px solid var(--line);
  color:var(--muted);
  font-size:.62rem;
  font-weight:720;
  letter-spacing:.02em;
}
.st-key-workspace-nav{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:14px;
  padding:8px 10px;
  box-shadow:0 3px 14px rgba(28,29,26,.035);
}
.nav-brand{font-size:.98rem;font-weight:850;letter-spacing:-.025em;line-height:1.05;}
.nav-sub{font-size:.62rem;color:var(--muted);margin-top:2px;letter-spacing:.035em;}
.home-hero{
  padding:34px 2px 26px;
  max-width:900px;
}
.home-kicker{
  font-size:.64rem;
  font-weight:800;
  letter-spacing:.12em;
  text-transform:uppercase;
  color:var(--primary);
}
.home-title{
  font-size:clamp(2.8rem,6vw,5.4rem);
  font-weight:860;
  line-height:.95;
  letter-spacing:-.065em;
  max-width:900px;
  margin-top:8px;
}
.home-copy{
  max-width:520px;
  color:var(--muted);
  font-size:.94rem;
  line-height:1.4;
  margin-top:12px;
}
.st-key-landing-test,.st-key-landing-live{
  min-height:250px;
  border:1px solid var(--line);
  border-radius:18px;
  padding:20px;
  box-shadow:var(--shadow);
  display:flex;
  flex-direction:column;
  justify-content:space-between;
  background:var(--surface);
}
.st-key-landing-test:hover,.st-key-landing-live:hover{border-color:var(--line-strong);}
.workspace-index{font-size:.62rem;font-weight:800;color:var(--primary);letter-spacing:.09em;}
.workspace-name{font-size:3.1rem;font-weight:860;letter-spacing:-.06em;line-height:.9;margin:.55rem 0 .5rem;}
.workspace-desc{font-size:.83rem;color:var(--muted);line-height:1.35;max-width:420px;}
.home-card-top{display:flex;align-items:center;justify-content:space-between;gap:12px;}
.home-card-kind{font-size:.62rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
.canvas-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:18px;}
.canvas-title{font-size:1.7rem;font-weight:860;letter-spacing:-.045em;line-height:1.08;}
.canvas-copy{font-size:.78rem;color:var(--muted);max-width:700px;line-height:1.45;margin-top:5px;}
.section-head{
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:18px;
  margin:24px 0 12px;
}
.section-title{font-size:1.12rem;font-weight:820;letter-spacing:-.025em;color:var(--ink);}
.section-count{font-size:.62rem;font-weight:760;color:var(--subtle);letter-spacing:.06em;text-transform:uppercase;}
.st-key-topic-toolbar{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:14px;
  padding:7px 9px;
  margin-bottom:14px;
}
.topic-title{
  font-size:.96rem;
  line-height:1.24;
  font-weight:760;
  letter-spacing:-.018em;
  color:var(--ink);
  display:-webkit-box;
  -webkit-box-orient:vertical;
  -webkit-line-clamp:3;
  overflow:hidden;
  min-height:3.57em;
  margin:7px 0 6px;
}
.topic-meta{
  font-size:.66rem;
  color:var(--muted);
  line-height:1.25;
  margin-top:0;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-card-"]{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:16px;
  padding:13px 14px 12px;
  margin-bottom:10px;
  min-height:178px;
  box-shadow:0 1px 2px rgba(28,29,26,.03);
}
[data-testid="stVerticalBlock"] [class*="st-key-topic-card-"]:hover{
  border-color:var(--line-strong);
  box-shadow:var(--shadow);
}
.topic-card-state{
  display:flex;
  align-items:center;
  justify-content:space-between;
  min-height:14px;
}
.topic-state-label{
  font-size:.61rem;
  font-weight:800;
  letter-spacing:.04em;
  color:var(--primary);
}
.selected-story-title{
  font-size:1.08rem;
  font-weight:820;
  letter-spacing:-.025em;
  line-height:1.18;
  max-width:760px;
}
.st-key-selected-story-card{
  margin-top:18px;
  background:var(--surface);
  border:1px solid var(--primary);
  border-radius:16px;
  padding:15px 16px;
  box-shadow:0 4px 18px rgba(43,93,80,.06);
}
.st-key-script-editor,.st-key-subtitle-editor,.st-key-renderer-inspector,.st-key-audio-inspector{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:16px;
  padding:16px;
  box-shadow:var(--shadow);
}
.inspector{background:transparent;}
.inspector-line{
  display:flex;
  justify-content:space-between;
  gap:16px;
  padding:.56rem 0;
  border-bottom:1px solid var(--line);
  font-size:.72rem;
}
.inspector-line:last-child{border-bottom:0;}
.inspector-value{font-weight:760;color:var(--ink);text-align:right;}
.scene-label{font-size:.62rem;font-weight:820;letter-spacing:.11em;text-transform:uppercase;color:var(--subtle);margin:10px 0 5px;}
.cue-row{display:grid;grid-template-columns:72px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);}
.cue-time{font-variant-numeric:tabular-nums;font-size:.67rem;color:var(--subtle);}
.cue-text{font-size:.77rem;color:var(--ink);}
.media-surface{
  background:#0b1220;
  border-radius:16px;
  padding:10px;
  display:flex;
  justify-content:center;
  box-shadow:var(--shadow);
}
.live-product-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;}
.live-product-title{
  font-size:clamp(2.5rem,5vw,4.4rem);
  font-weight:860;
  letter-spacing:-.065em;
  line-height:.94;
  margin-top:6px;
}
.live-status{display:inline-flex;align-items:center;gap:7px;padding:6px 9px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--muted);font-size:.62rem;font-weight:750;white-space:nowrap;}
.live-status span{width:7px;height:7px;border-radius:50%;background:var(--success);box-shadow:0 0 0 4px var(--success-soft);}
.hero-subtitle{font-size:.82rem;color:var(--muted);max-width:600px;line-height:1.4;margin-top:5px;}
.st-key-live-choice-cricket,.st-key-live-choice-niche,.st-key-live-cricket-india,.st-key-live-cricket-global,
.st-key-live-line-deep-dive,.st-key-live-line-top-5,.st-key-live-line-otd{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:16px;
  padding:18px;
  min-height:190px;
  box-shadow:var(--shadow);
}
.st-key-live-choice-niche,.st-key-live-line-top-5,.st-key-live-line-otd{
  background:var(--surface);
  border-color:var(--line);
}
.choice-title{font-size:2.25rem;font-weight:850;letter-spacing:-.06em;line-height:.94;margin:.45rem 0;}
.choice-copy{font-size:.8rem;color:var(--muted);line-height:1.35;max-width:360px;}
.topic-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.topic-rank{font-size:.62rem;font-weight:820;letter-spacing:.1em;color:var(--primary);}
.empty-slot{
  min-height:260px;
  display:flex;
  align-items:center;
  justify-content:center;
  border:1px dashed var(--line-strong);
  border-radius:12px;
  color:var(--subtle);
  background:var(--surface-soft);
  font-size:.66rem;
  font-weight:800;
  letter-spacing:.1em;
}
.visual-source{font-size:.64rem;font-weight:780;color:var(--ink);margin-top:8px;}
.visual-detail{font-size:.63rem;color:var(--muted);line-height:1.35;margin-top:3px;}
.empty-state{padding:54px 18px;text-align:center;background:var(--surface);border:1px dashed var(--line-strong);border-radius:16px;box-shadow:none;}.empty-state-title{font-size:.9rem;font-weight:800;color:var(--ink);}.empty-state-copy{font-size:.72rem;color:var(--muted);margin-top:4px;}.visual-crop-label{display:inline-flex;margin-top:6px;padding:4px 7px;border-radius:999px;background:var(--success-soft);color:var(--success);font-size:.58rem;font-weight:820;letter-spacing:.06em;}
.crop-dialog-kicker{font-size:.62rem;font-weight:820;letter-spacing:.14em;color:var(--primary);text-transform:uppercase;}
.crop-dialog-title{font-size:1.2rem;font-weight:820;margin:4px 0 10px;letter-spacing:-.025em;}
@media(max-width:900px){
  .block-container{padding:18px 16px 44px;}
  .home-hero{padding:24px 0 20px;}
  .home-title{font-size:clamp(2.6rem,10vw,4.6rem);}
  .workspace-name{font-size:2.7rem;}
  .canvas-head{margin-bottom:14px;}
  .section-head{margin-top:18px;}
  .st-key-landing-test,.st-key-landing-live{min-height:230px;}
}
@media(max-width:640px){
  .block-container{padding-left:12px;padding-right:12px;}
  .st-key-workspace-nav{padding:8px;}
  [data-testid="stHorizontalBlock"]:has([class*="st-key-topic-card-"]),
  [data-testid="stHorizontalBlock"]:has(.st-key-landing-test){
    flex-direction:column!important;
    gap:10px!important;
  }
  [data-testid="stHorizontalBlock"]:has([class*="st-key-topic-card-"]) > div,
  [data-testid="stHorizontalBlock"]:has(.st-key-landing-test) > div{
    width:100%!important;
    flex:1 1 100%!important;
  }
  .home-copy{font-size:.86rem;}
  .home-title{font-size:clamp(2.45rem,13vw,3.7rem);}
  .canvas-title{font-size:1.35rem;}
  .choice-title{font-size:2rem;}
  .inspector-line{font-size:.7rem;}
  .cue-row{grid-template-columns:52px 1fr;gap:9px;}
  [data-testid="stHorizontalBlock"]{gap:10px;}
  .st-key-topic-toolbar{padding:6px 8px;}
  [data-testid="stVerticalBlock"] [class*="st-key-topic-card-"]{min-height:164px;padding:12px;}
  .topic-title{font-size:.94rem;-webkit-line-clamp:3;}
  .selected-story-title{font-size:1rem;}
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
if "test_pipeline_notice" not in st.session_state:
    st.session_state.test_pipeline_notice = None
if "renderer_previews" not in st.session_state:
    st.session_state.renderer_previews = None
if "visual_crops" not in st.session_state:
    st.session_state.visual_crops = {}
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
if "live_selected_topic" not in st.session_state:
    st.session_state.live_selected_topic = None
if "live_stage" not in st.session_state:
    st.session_state.live_stage = "01 · Story"
if "live_topics_profile" not in st.session_state:
    st.session_state.live_topics_profile = None
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
if "live_ranked_visual_result" not in st.session_state:
    st.session_state.live_ranked_visual_result = None
if "live_script_language" not in st.session_state:
    st.session_state.live_script_language = "english"
if "live_headline_enabled" not in st.session_state:
    st.session_state.live_headline_enabled = True
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
    try:
        if isinstance(value, Image.Image):
            return value.convert("RGB")
        if isinstance(value, (bytes, bytearray)):
            with Image.open(BytesIO(bytes(value))) as image:
                return image.convert("RGB")
    except (OSError, ValueError):
        return None
    return None


def _preview_image(asset):
    image = _asset_to_image(asset.get("bytes"))
    if image is None:
        return None
    image.thumbnail((960, 960), Image.Resampling.LANCZOS)
    return image


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
    image = _asset_to_image(image_bytes)
    if image is None:
        st.error("This visual could not be opened for cropping.")
        return

    st.markdown('<div class="crop-dialog-kicker">MANUAL CROP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="crop-dialog-title">{label}</div>', unsafe_allow_html=True)
    st.caption("9:16 crop · drag the frame to position it, or drag a corner to show more or less of the full image. The original visual stays untouched.")

    from streamlit_cropper import st_cropper

    store = st.session_state.setdefault(crop_store, {})
    cropped = st_cropper(
        image,
        realtime_update=True,
        default_coords=_largest_9x16_crop_coords(image),
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


def _render_visual_asset_grid(assets: list[dict], result_key: str):
    for start in range(0, len(assets), 3):
        cols = st.columns(3, gap="medium")
        for index, (col, asset) in enumerate(zip(cols, assets[start:start + 3]), start=start):
            with col:
                asset_key = _visual_asset_key(result_key, index, asset)
                with st.container(key=f"visual-card-{result_key}-{index}"):
                    preview = _preview_image(asset)
                    if preview is not None:
                        st.image(preview, width="stretch")
                    source = str(
                        asset.get("publisher")
                        or asset.get("source")
                        or asset.get("model")
                        or "Web source"
                    )
                    detail = str(
                        asset.get("article_title")
                        or asset.get("dimensions")
                        or (
                            f'{asset.get("width")}×{asset.get("height")}px'
                            if asset.get("width") and asset.get("height")
                            else ""
                        )
                    )
                    st.markdown(f'<div class="visual-source">{source}</div>', unsafe_allow_html=True)
                    if detail:
                        st.markdown(f'<div class="visual-detail">{detail}</div>', unsafe_allow_html=True)

                    cropped = st.session_state.visual_crops.get(asset_key)
                    if cropped:
                        st.markdown('<div class="visual-crop-label">CROP PREVIEW</div>', unsafe_allow_html=True)
                        crop_preview = _asset_to_image(cropped)
                        if crop_preview is not None:
                            st.image(crop_preview, width="stretch")

                    action_cols = st.columns(2, gap="small")
                    with action_cols[0]:
                        if st.button("Crop", key=f"crop-button-{asset_key}", width="stretch"):
                            raw = asset.get("bytes")
                            if isinstance(raw, (bytes, bytearray)):
                                _crop_visual_dialog(asset_key, bytes(raw), source)
                            else:
                                st.warning("This visual does not have a crop-ready image payload.")
                    with action_cols[1]:
                        source_url = str(asset.get("source_page_url") or "").strip()
                        if source_url:
                            st.link_button("Source ↗", source_url, width="stretch")
                        else:
                            st.markdown('<div class="visual-detail">No source link</div>', unsafe_allow_html=True)


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
            }[st.session_state.test_production_line]
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
        "live_ranked_visual_result": None,
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
    }.items():
        st.session_state[key] = value


def _live_story(topic) -> dict:
    return {
        "title": topic.title,
        "description": topic.description,
        "url": topic.url,
        "source": topic.source,
        "published_at": topic.published_at.isoformat(),
    }


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

    story = _live_story(topics[selected_index])
    script = write_script(
        story,
        language=st.session_state.get("live_script_language", "english"),
    )
    st.session_state.live_script_data = script
    st.session_state.live_script_error = ""
    st.session_state.live_upload_titles = list(script.get("titles") or [])
    st.session_state.live_upload_description = str(script.get("seo_description") or "")
    st.session_state.live_upload_hashtags = " ".join(
        str(item) for item in (script.get("hashtags") or [])
    )
    st.session_state.live_upload_comment = str(script.get("comment") or "")
    return script


def _live_scrape_automatic_visuals():
    selected_index = st.session_state.get("live_selected_topic")
    topics = st.session_state.get("live_topics") or []
    script = st.session_state.get("live_script_data")
    if selected_index is None or not 0 <= selected_index < len(topics):
        raise ValueError("No valid Live story is selected.")
    if not isinstance(script, dict):
        raise ValueError("Generate the Live Scriptwriter result before scraping visuals.")

    story = _live_story(topics[selected_index])
    scenes = script.get("script") or []
    first_scene = scenes[0] if scenes and isinstance(scenes[0], dict) else {}
    story["primary_entity"] = str(first_scene.get("primary_entity") or "").strip()
    story["specific_search_prompt"] = str(first_scene.get("specific_search_prompt") or "").strip()
    story["visual_intent"] = str(first_scene.get("visual_intent") or "").strip()
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

    audio = generate_audio(
        approved_script,
        output_dir="output/live/audio",
    )
    approved_audio = approve_audio(audio)
    subtitles = generate_subtitles(approved_script, approved_audio)

    st.session_state.live_audio_data = audio
    st.session_state.live_approved_audio = approved_audio
    st.session_state.live_subtitle_data = subtitles


def _live_fit_preview(value, width=360, height=640):
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


def _live_asset_key(result_key: str, index: int, asset: dict) -> str:
    return _visual_asset_key(f"live-{result_key}", index, asset)


def _live_delete_asset(result_key: str, index: int, asset: dict):
    asset_key = _live_asset_key(result_key, index, asset)
    st.session_state.live_visual_deleted.add(asset_key)
    for slide, assignment in list(st.session_state.live_visual_assignments.items()):
        if assignment.get("asset_key") == asset_key:
            del st.session_state.live_visual_assignments[slide]
    st.session_state.live_visual_crops.pop(asset_key, None)


def _live_attach_asset(result_key: str, index: int, asset: dict, slide: int):
    raw = asset.get("bytes")
    if not isinstance(raw, (bytes, bytearray)):
        st.warning("This visual has no usable image payload.")
        return

    asset_key = _live_asset_key(result_key, index, asset)
    cropped = st.session_state.live_visual_crops.get(asset_key)
    selected_bytes = bytes(cropped) if cropped else bytes(raw)
    st.session_state.live_visual_assignments[slide] = {
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
    st.session_state.live_visuals_approved = False


def _render_live_asset_pool(assets: list[dict], result_key: str, slide_count: int):
    visible_assets = [
        (index, asset)
        for index, asset in enumerate(assets)
        if _live_asset_key(result_key, index, asset)
        not in st.session_state.live_visual_deleted
    ]

    if not visible_assets:
        st.caption("No images are currently available from this option.")
        return

    for start in range(0, len(visible_assets), 3):
        cols = st.columns(3, gap="medium")
        for col, (index, asset) in zip(cols, visible_assets[start:start + 3]):
            with col:
                asset_key = _live_asset_key(result_key, index, asset)
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
                with st.container(key=f"live-visual-card-{result_key}-{index}"):
                    preview_bytes = st.session_state.live_visual_crops.get(asset_key)
                    preview = _live_fit_preview(
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
                                key=f"live-attach-slide-{asset_key}",
                            )
                            if st.button(
                                "Attach",
                                type="primary",
                                width="stretch",
                                key=f"live-attach-{asset_key}",
                            ):
                                _live_attach_asset(
                                    result_key,
                                    index,
                                    asset,
                                    selected_slide,
                                )
                                st.rerun()
                    with crop_col:
                        raw = asset.get("bytes")
                        if st.button(
                            "Crop",
                            width="stretch",
                            key=f"live-crop-{asset_key}",
                        ):
                            if isinstance(raw, (bytes, bytearray)):
                                _crop_visual_dialog(
                                    asset_key,
                                    bytes(raw),
                                    source,
                                    crop_store="live_visual_crops",
                                )
                            else:
                                st.warning("This visual does not have a crop-ready payload.")
                    with delete_col:
                        if st.button(
                            "Delete",
                            width="stretch",
                            key=f"live-delete-{asset_key}",
                        ):
                            _live_delete_asset(result_key, index, asset)
                            st.rerun()


def _render_live_visual_board(slide_count: int):
    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">VISUAL BOARD</div>'
        '<div class="section-title">Attach one visual to every slide</div></div>'
        f'<div class="section-count">{slide_count} slides required</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(slide_count, gap="small")
    for slide in range(1, slide_count + 1):
        with cols[slide - 1]:
            assignment = st.session_state.live_visual_assignments.get(slide)
            with st.container(key=f"live-slide-{slide}"):
                st.markdown(
                    f'<div class="eyebrow">SLIDE {slide}</div>',
                    unsafe_allow_html=True,
                )
                preview = (
                    _live_fit_preview(assignment["bytes"], 300, 533)
                    if assignment
                    else None
                )
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

    _render_live_visual_board(slide_count)
    assigned = len(st.session_state.live_visual_assignments)
    st.caption(
        f"{assigned}/{slide_count} slides attached. "
        "Attached images remain in their original pools until you delete them."
    )

    with st.expander("Option 1 · Automatic Scraper", expanded=True):
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
            _render_live_asset_pool(
                list(result.get("assets") or []),
                "auto",
                slide_count,
            )

    with st.expander("Option 2 · Manual Scraper", expanded=False):
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
            _render_live_asset_pool(
                list(result.get("assets") or []),
                "manual",
                slide_count,
            )

    with st.expander("Option 3 · Real Image Search", expanded=False):
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
            _render_live_asset_pool(
                list(result.get("assets") or []),
                "real",
                slide_count,
            )

    with st.expander("Option 4 · AI Generation", expanded=False):
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
            _render_live_asset_pool(
                list(result.get("assets") or []),
                "ai",
                slide_count,
            )

    with st.expander("Option 5 · Ranked Scene Search", expanded=False):
        st.caption("Runs the approved Scriptwriter scene searches together. This does not replace the automatic or manual scrapers.")
        script = st.session_state.get("live_approved_script")
        if not isinstance(script, dict):
            st.info("Approve the Live Scriptwriter result first.")
        else:
            selected_index = st.session_state.get("live_selected_topic")
            topics = st.session_state.get("live_topics") or []
            if selected_index is None or not 0 <= selected_index < len(topics):
                st.info("Choose a Live story first.")
            else:
                topic = topics[selected_index]
                ranked_story = _live_story(topic)
                ranked_story["script"] = script.get("script") or []
                run = st.button(
                    "Run ranked search",
                    type="primary",
                    width="stretch",
                    key="live-run-ranked-search",
                )
                if run:
                    with st.spinner("Running scene searches in parallel…"):
                        try:
                            st.session_state.live_ranked_visual_result = ranked_visual_search(ranked_story)
                        except Exception as exc:
                            st.session_state.live_ranked_visual_result = {
                                "error": f"{type(exc).__name__}: {exc}"
                            }
                result = st.session_state.get("live_ranked_visual_result") or {}
                if result.get("error"):
                    st.error(result["error"])
                elif result:
                    lanes = result.get("lanes") or []
                    for start in range(0, len(lanes), 3):
                        row = lanes[start:start + 3]
                        cols = st.columns(len(row), gap="medium")
                        for col, lane in zip(cols, row):
                            with col:
                                st.markdown(f'**Slide {lane["scene"]}**')
                                st.code(lane["query"])
                                st.caption(f'{len(lane.get("assets") or [])} ranked images')
                    st.caption(
                        f'{len(result.get("assets") or [])} unique images · '
                        f'{int(result.get("pages_scraped") or 0)} pages'
                    )
                    _render_live_asset_pool(
                        list(result.get("assets") or []),
                        "ranked",
                        slide_count,
                    )

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
                        render_production_video(
                            st.session_state.live_approved_script,
                            st.session_state.live_approved_audio,
                            st.session_state.live_subtitle_data,
                            assigned,
                            output_path=output,
                            headline_text=st.session_state.live_approved_script.get("headline", ""),
                            headline_enabled=st.session_state.live_headline_enabled,
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
    if not isinstance(script, dict) and not st.session_state.get("live_script_error"):
        with st.spinner("Writing the Short…"):
            try:
                script = _live_generate_script()
                st.rerun()
            except Exception as exc:
                st.session_state.live_script_error = f"{type(exc).__name__}: {exc}"
                st.rerun()

    if st.session_state.get("live_script_error"):
        if isinstance(script, dict):
            st.error(
                "Script approval failed: "
                + st.session_state.live_script_error
            )
            st.caption("Correct the highlighted edit and approve the script again.")
        else:
            st.error(
                "Scriptwriter failed: "
                + st.session_state.live_script_error
            )
            if st.button(
                "Retry Scriptwriter",
                type="primary",
                width="stretch",
                key="live-retry-script",
            ):
                selected_index = st.session_state.get("live_selected_topic")
                _live_reset_downstream()
                st.session_state.live_selected_topic = selected_index
                st.session_state.live_stage = "02 · Script"
                st.rerun()
            return

    if not isinstance(script, dict):
        st.info("Preparing the Scriptwriter stage…")
        return

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

    if not st.session_state.live_approved_script:
        if st.button(
            "Approve script and hand to Audio",
            type="primary",
            width="stretch",
            key="live-approve-script",
        ):
            try:
                approved = apply_script_edits(
                    script,
                    edited_voiceovers,
                    headline=edited_headline if st.session_state.live_headline_enabled else "",
                    validate=False,
                )
                approved["headline"] = (
                    str(edited_headline or "").strip()
                    if st.session_state.live_headline_enabled
                    else ""
                )
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

    if video_path.is_file():
        st.video(str(video_path), width=520)

    titles = list(
        st.session_state.live_upload_titles
        or script.get("titles")
        or []
    )
    if not titles:
        st.error("Scriptwriter did not return three title candidates.")
        return

    st.caption("Edit the three title candidates, choose the one to publish, then approve the metadata once.")
    edited_titles = []
    for index, title in enumerate(titles[:3], 1):
        edited_titles.append(
            st.text_input(
                f"Title option {index}",
                value=str(title),
                max_chars=100,
                key=f"live-upload-title-{story_id}-{index}",
            )
        )
    st.session_state.live_upload_titles = edited_titles

    choice = st.selectbox(
        "Title to publish",
        list(range(len(edited_titles))),
        index=min(
            int(st.session_state.live_upload_title_choice),
            len(edited_titles) - 1,
        ),
        format_func=lambda index: edited_titles[index] or f"Title option {index + 1}",
        key=f"live-upload-choice-{story_id}",
    )
    final_title_key = f"live-upload-final-title-{story_id}"
    if (
        choice != st.session_state.live_upload_title_choice
        or not str(st.session_state.get(final_title_key) or "").strip()
    ):
        st.session_state.live_upload_title_choice = choice
        st.session_state[final_title_key] = edited_titles[choice]

    st.text_input(
        "Final title",
        key=final_title_key,
        max_chars=100,
        help="Edit the selected title here. The exact value in this field becomes the YouTube title when you approve.",
    )
    st.caption("The Final title field is the value that will be published after Manual QC approval.")

    st.text_area(
        "Description",
        key=f"live-upload-description-{story_id}",
        value=st.session_state.live_upload_description,
        height=150,
    )
    st.text_input(
        "Hashtags",
        key=f"live-upload-hashtags-{story_id}",
        value=st.session_state.live_upload_hashtags,
    )
    st.text_area(
        "Public comment",
        key=f"live-upload-comment-{story_id}",
        value=st.session_state.live_upload_comment,
        height=100,
    )

    if not st.session_state.live_upload_qc_approved:
        if st.button(
            "Approve metadata",
            type="primary",
            width="stretch",
            key="live-approve-upload-qc",
        ):
            st.session_state.live_upload_description = st.session_state[
                f"live-upload-description-{story_id}"
            ]
            st.session_state.live_upload_hashtags = st.session_state[
                f"live-upload-hashtags-{story_id}"
            ]
            st.session_state.live_upload_comment = st.session_state[
                f"live-upload-comment-{story_id}"
            ]
            st.session_state.live_upload_qc = {
                "title": st.session_state[final_title_key].strip(),
                "description": st.session_state.live_upload_description,
                "hashtags": st.session_state.live_upload_hashtags,
                "comment": st.session_state.live_upload_comment,
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
        st.success(
            f"Upload successful · Video ID: \`{result.get('video_id')}\`"
        )
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

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        public = st.button(
            "Upload Public",
            type="primary",
            width="stretch",
            key="live-upload-public",
        )
    with col2:
        private = st.button(
            "Upload Private",
            width="stretch",
            key="live-upload-private",
        )

    if not (public or private):
        return

    privacy = "public" if public else "private"
    try:
        with st.spinner(f"Uploading video as {privacy}…"):
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
        ]
        cols = st.columns(3, gap="small")
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
                    }[eyebrow]
                    if st.button(button_label, type="primary", width="stretch", key=f"{key}-button"):
                        st.session_state.live_production_line = {
                            "01 · DEEP-DIVE": "deep_dive",
                            "02 · TOP-5": "top_5",
                            "03 · OTD": "otd",
                        }[eyebrow]
                        st.session_state.live_desk = None
                        st.session_state.live_cricket_profile = None
                        st.session_state.live_topics_profile = None
                        st.session_state.live_topics = []
                        st.rerun()
        return

    if st.session_state.live_production_line == "top_5":
        st.space("medium")
        st.markdown(
            '<div class="section-head"><div><div class="eyebrow">TOP-5 · WIP</div>'
            '<div class="section-title">Top 5 cricket stories of the day</div></div></div>',
            unsafe_allow_html=True,
        )
        st.info("This production line is reserved for the Top-5 design we are building next.")
        if st.button("← Back to production lines", key="live-back-from-top-5"):
            st.session_state.live_production_line = None
            st.session_state.live_desk = None
            st.rerun()
        return

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
        st.markdown('<div class="section-head"><div><div class="eyebrow">STORY DESK</div><div class="section-title">Choose your story</div></div><div class="section-count">select one to start production</div></div>', unsafe_allow_html=True)
        topics = st.session_state.live_topics
        for start in range(0, len(topics), 2):
            row = st.columns(2, gap="medium")
            for col, (index, topic) in zip(
                row,
                enumerate(topics[start:start + 2], start=start),
            ):
                with col:
                    with st.container(key=f"live-topic-{index}"):
                        st.markdown(
                            f'<div class="topic-top"><span class="topic-rank">STORY {index + 1:02d}</span></div>'
                            f'<div class="topic-title">{topic.title}</div>'
                            f'<div class="topic-meta">{topic.source or "Sports desk"} · {topic.published_at:%d %b · %H:%M UTC}</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button("Select story →", width="stretch", key=f"live-select-story-{index}"):
                            _live_start_story(index)
                            st.rerun()

        if st.button("Find 20 more unique stories", width="stretch", key="live-find-more"):
            with st.spinner("Searching for 20 additional unique stories…"):
                existing = list(st.session_state.live_topics)
                new_topics = fetch_topics(
                    st.session_state.live_topics_profile,
                    more=True,
                    exclude_topics=existing,
                    limit=20,
                )
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
            else:
                with st.spinner("Generating Audio and Subtitles…"):
                    try:
                        _live_generate_audio_and_subtitles()
                        st.session_state.live_stage = "04 · Visuals + Render"
                        st.session_state.live_pipeline_notice = {
                            "confirmed": "Audio + Subtitles ready",
                            "next": "Moving to Visuals + Render.",
                        }
                        st.rerun()
                    except (RuntimeError, ValueError, OSError) as exc:
                        st.session_state.live_handoff_error = str(exc)
                        st.rerun()
            if st.session_state.live_handoff_error:
                if st.button("Retry Audio / Subtitles", type="primary", key="live-retry-handoffs-stage"):
                    st.session_state.live_handoff_error = ""
                    st.session_state.live_approved_audio = None
                    st.session_state.live_subtitle_data = None
                    st.rerun()
            return
        st.success("Audio and subtitles are approved. Moving to Visuals.")
        st.session_state.live_stage = "04 · Visuals + Render"
        st.rerun()

    if st.session_state.live_stage == "04 · Visuals + Render":
        script = st.session_state.live_approved_script
        audio_ready = isinstance(st.session_state.live_approved_audio, dict)
        subtitle_ready = isinstance(st.session_state.live_subtitle_data, dict)
        if not audio_ready or not subtitle_ready:
            st.warning("Audio and subtitle handoffs are not ready yet.")
            return

        visual_result = st.session_state.get("live_visual_result")
        if visual_result is None:
            with st.spinner("Scraping automatic visuals from the approved Scriptwriter context…"):
                try:
                    _live_scrape_automatic_visuals()
                    st.rerun()
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
            "topics": [], "selected_topic": None, "script_data": None, "approved_script": None,
            "audio_data": None, "approved_audio": None, "subtitle_data": None, "approved_subtitles": None,
            "visual_result": None, "visual_loaded_story": None, "renderer_previews": None,
            "rendered_video_path": None, "upload_qc_approved": False, "upload_result": None,
            "upload_qc": None, "manual_visual_result": None, "real_image_result": None,
            "ai_image_result": None, "ranked_visual_result": None, "visual_crops": {},
        }.items():
            st.session_state[key] = value
    st.session_state.topic_desk_profile = profiles[desk]

    with st.container(key="topic-toolbar"):
        a,b,cnt=st.columns([1,.72,1.6],gap="small")
        with a:
            fetch=st.button("Fetch current stories",type="primary",width="stretch")
        with b:
            more=st.button("Find 20 more",width="stretch")
        with cnt:
            st.markdown(
                f'<div style="text-align:right;padding:.65rem .15rem;"><span class="badge">{len(st.session_state.topics)} stories</span></div>',
                unsafe_allow_html=True,
            )

    if fetch or more:
        with st.spinner("Fetching current sports stories…"):
            existing_topics=list(st.session_state.topics) if more else []
            new_topics=fetch_topics(profiles[desk],more=more,exclude_topics=existing_topics,limit=20)
            st.session_state.topics=existing_topics+new_topics if more else new_topics
        st.session_state.selected_topic=None
        st.session_state.script_data=None
        st.session_state.approved_script=None
        st.session_state.audio_data=None
        st.session_state.approved_audio=None
        st.session_state.subtitle_data=None
        st.session_state.approved_subtitles=None
        st.session_state.visual_result=None
        st.session_state.visual_loaded_story=None

    topics=st.session_state.topics
    if not topics:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-title">No stories loaded</div><div class="empty-state-copy">Fetch the current story pool to start.</div></div>',
            unsafe_allow_html=True,
        )
        return

    for start in range(0, len(topics), 3):
        row = st.columns(3, gap="small")
        for col, (index, topic) in zip(
            row,
            enumerate(topics[start:start + 3], start=start),
        ):
            with col:
                source = topic.source or "Sports desk"
                published = topic.published_at.strftime("%d %b")
                selected = index == st.session_state.selected_topic
                with st.container(key=f"topic-card-{index}"):
                    selected_label = (
                        '<span class="topic-state-label selected">Selected</span>'
                        if selected
                        else ""
                    )
                    st.markdown(
                        f'<div class="topic-card-state">'
                        f'<span class="topic-rank">STORY {index + 1:02d}</span>'
                        f'{selected_label}'
                        f'</div>'
                        f'<div class="topic-title">{topic.title}</div>'
                        f'<div class="topic-meta">{source} · {published}</div>',
                        unsafe_allow_html=True,
                    )
                    label = "Selected" if selected else "Select"
                    if st.button(label, key=f"topic-select-{index}", width="stretch"):
                        st.session_state.selected_topic = index
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
                        st.session_state.ranked_visual_result = None
                        st.session_state.visual_result = None
                        st.session_state.visual_loaded_story = None
                        st.session_state.visual_crops = {}
                        st.rerun()

    if st.session_state.selected_topic is not None:
        index=st.session_state.selected_topic
        if index < len(topics):
            topic=topics[index]
            with st.container(key="selected-story-card"):
                left,right=st.columns([1.7,.45],gap="medium")
                with left:
                    st.markdown('<div class="eyebrow">SELECTED</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="selected-story-title">{topic.title}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="topic-meta">{topic.source or "Sports desk"} · {topic.published_at:%d %b}</div>',unsafe_allow_html=True)
                    if topic.description:
                        with st.expander("Story details", expanded=False):
                            st.write(topic.description)
                with right:
                    if topic.url:
                        st.link_button("Source ↗",topic.url,width="stretch")
def render_scriptwriter():
    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first.")
        return
    selected_index=st.session_state.selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.topics):
        st.info("Select a story in the Story Desk first.")
        return
    topic=st.session_state.topics[selected_index]

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
            with st.spinner("Writing the Short…"):
                st.session_state.script_data=write_script({
                    "title":topic.title,"description":topic.description,"url":topic.url,"source":topic.source,
                },language=language.casefold())
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
            edited_headline=st.text_input("Opening heading (3–4 words)",value=script.get("headline",""),max_chars=48,key="script-headline",label_visibility="collapsed")
            st.markdown('<div style="height:.7rem"></div>',unsafe_allow_html=True)
            edited_voiceovers=[]
            for index,scene in enumerate(script.get("script",[]),1):
                st.markdown(f'<div class="scene-label">Scene {index}</div>',unsafe_allow_html=True)
                edited_voiceovers.append(st.text_area("Narration",value=scene.get("voiceover",""),height=105,key=f"script-slide-{index}",label_visibility="collapsed"))
            if st.button("Approve script",type="primary",width="stretch"):
                try:
                    approved=apply_script_edits(script,edited_voiceovers,headline=edited_headline)
                    st.session_state.approved_script=approved
                    st.session_state.test_stage = "03 · Audio"
                    st.session_state.test_pipeline_notice = {
                        "confirmed": "Script QC confirmed",
                        "next": "Moving to Audio.",
                    }
                    st.session_state.audio_data=None
                    st.session_state.approved_audio=None
                    st.session_state.renderer_previews=None
                    st.session_state.upload_qc_approved=False
                    st.session_state.upload_result=None
                    st.session_state.rendered_video_path=None
                    st.session_state.upload_qc=None
                    for index in range(1,4):
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
        st.markdown('<div class="mini-label">Story</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="font-weight:820;line-height:1.35;margin:.25rem 0 1rem;">{topic.title}</div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Language</span><span class="inspector-value">'+str(script.get("language_used") or language)+'</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Scenes</span><span class="inspector-value">'+str(len(script.get("script") or []))+'</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="inspector-line"><span>Word count</span><span class="inspector-value">'+str(script.get("word_count") or "")+'</span></div>',unsafe_allow_html=True)
        if st.session_state.approved_script:
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--ok-soft);color:var(--ok);">Approved</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
def render_visuals_crawler():
    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first, then select a story for Visuals.")
        return

    selected_index = st.session_state.selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.topics):
        st.info("Choose a story in 01 · Topic Fetcher first.")
        return
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
    _render_visual_asset_grid(assets, "auto-crawler")


def _render_ranked_visual_search():
    st.subheader("Ranked Scene Search")
    st.caption("Runs the approved Scriptwriter visual searches together. The existing scrapers remain unchanged.")

    approved_script = st.session_state.get("approved_script")
    if not isinstance(approved_script, dict):
        st.info("Approve the Scriptwriter first so each scene has a specific visual search prompt.")
        return
    if not st.session_state.topics or st.session_state.selected_topic is None:
        st.info("Select a story first.")
        return

    topic = st.session_state.topics[st.session_state.selected_topic]
    story = {
        "title": topic.title,
        "description": topic.description,
        "url": topic.url,
        "source": topic.source,
        "published_at": topic.published_at.isoformat(),
        "script": approved_script.get("script") or [],
    }

    if st.button("Run ranked search", type="primary", width="stretch", key="ranked-visual-search"):
        with st.spinner("Running scene searches in parallel…"):
            try:
                st.session_state.ranked_visual_result = ranked_visual_search(story)
                st.session_state.visual_crops = {}
            except Exception as exc:
                st.session_state.ranked_visual_result = {
                    "error": f"{type(exc).__name__}: {exc}"
                }

    result = st.session_state.get("ranked_visual_result") or {}
    if result.get("error"):
        st.error(result["error"])
        return
    if not result:
        return

    lanes = result.get("lanes") or []
    for start in range(0, len(lanes), 3):
        row = lanes[start:start + 3]
        cols = st.columns(len(row), gap="medium")
        for col, lane in zip(cols, row):
            with col:
                st.markdown(f'**Slide {lane["scene"]}**')
                st.code(lane["query"])
                st.caption(
                    f'{len(lane.get("assets") or [])} ranked images'
                    + (f' · {lane.get("visual_intent")}' if lane.get("visual_intent") else "")
                )

    assets = list(result.get("assets") or [])
    st.caption(
        f'{len(assets)} unique images in the combined ranked pool · '
        f'{int(result.get("pages_scraped") or 0)} pages scraped'
    )
    diagnostics = list(result.get("diagnostics") or [])
    with st.expander("Ranked search diagnostics", expanded=not bool(assets)):
        if diagnostics:
            st.code(json.dumps(diagnostics, indent=2, ensure_ascii=False), language="text")
        else:
            st.caption("No search diagnostics were returned.")

    if assets:
        st.markdown('<div class="section-head"><div><div class="eyebrow">RANKED MEDIA BOARD</div><div class="section-title">Combined visual candidates</div></div><div class="section-count">highest-scoring first</div></div>', unsafe_allow_html=True)
        _render_visual_asset_grid(assets, "ranked-search")
    else:
        st.warning("The ranked search returned no usable images.")


def _render_manual_crawler():
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
    _render_visual_asset_grid(assets, "manual-crawler")


def _render_manual_real_images():
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
    _render_visual_asset_grid(assets, "real-search")


def _render_manual_ai_images():
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
    _render_visual_asset_grid(assets, "ai-generation")


def render_visuals():
    st.header("04 · Visuals")
    mode = st.pills(
        "Visual test",
        [
            "Option 1 · Automatic Scraper",
            "Option 2 · Manual Scraper",
            "Option 3 · Real Image Search",
            "Option 4 · AI Generation",
            "Option 5 · Ranked Scene Search",
        ],
        default="Option 1 · Automatic Scraper",
        key="visual_test_mode",
        label_visibility="collapsed",
    ) or "Option 1 · Automatic Scraper"
    if mode.startswith("Option 1"):
        render_visuals_crawler()
    elif mode.startswith("Option 2"):
        _render_manual_crawler()
    elif mode.startswith("Option 3"):
        _render_manual_real_images()
    elif mode.startswith("Option 4"):
        _render_manual_ai_images()
    else:
        _render_ranked_visual_search()


def render_subtitles():
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
            st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--ok-soft);color:var(--ok);">Approved</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
def render_renderer_test():
    approved_script=st.session_state.get("approved_script")
    headline_text=(str(approved_script.get("headline") or "").strip() if isinstance(approved_script,dict) else "") or HEADLINE_TEXT

    st.markdown(
        '<div class="canvas-head"><div><div class="eyebrow">06 · RENDER</div>'
        '<div class="canvas-title">Preview the finished treatment</div>'
        '<div class="canvas-copy">Check the opening headline and final caption treatment before the production render.</div></div></div>',
        unsafe_allow_html=True,
    )
    left,right=st.columns([1.15,.85],gap="large")
    with left:
        st.markdown('<div class="media-surface">',unsafe_allow_html=True)
        previews=st.session_state.get("renderer_previews") or {}
        if previews.get("final") and Path(previews["final"]).exists():
            st.video(str(previews["final"]),width=380)
        elif previews.get("opening") and Path(previews["opening"]).exists():
            st.video(str(previews["opening"]),width=380)
        else:
            st.caption("Build a preview to see the video treatment.")
        st.markdown('</div>',unsafe_allow_html=True)
    with right:
        with st.container(key="renderer-inspector"):
            st.markdown('<div class="inspector">',unsafe_allow_html=True)
            st.markdown('<div class="mini-label">Treatment</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="inspector-line"><span>Opening</span><span class="inspector-value">{headline_text}</span></div>',unsafe_allow_html=True)
            st.markdown(f'<div class="inspector-line"><span>Style</span><span class="inspector-value">{FINAL_STYLE_NAME}</span></div>',unsafe_allow_html=True)
            st.markdown('<div class="inspector-line"><span>Captions</span><span class="inspector-value">Word highlight</span></div>',unsafe_allow_html=True)
            st.markdown('<div class="inspector-line"><span>Headline</span><span class="inspector-value">Enabled</span></div>',unsafe_allow_html=True)
            if st.button("Build preview",type="primary",width="stretch"):
                with st.spinner("Rendering preview…"):
                    try:
                        st.session_state.renderer_previews=build_preview_bundle(headline_enabled=True,headline_text=headline_text.strip() or HEADLINE_TEXT)
                    except (RuntimeError,ValueError) as exc:
                        st.error(str(exc))
            if previews:
                st.markdown('<div style="margin-top:.8rem;color:var(--muted);font-size:.72rem;">Preview bundle ready.</div>',unsafe_allow_html=True)
            st.markdown('</div>',unsafe_allow_html=True)
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

    if not str(st.session_state.get("upload_description") or "").strip():
        st.session_state.upload_description = str(script.get("seo_description") or "")
    if not str(st.session_state.get("upload_hashtags") or "").strip():
        st.session_state.upload_hashtags = " ".join(str(x) for x in (script.get("hashtags") or []))
    if not str(st.session_state.get("upload_comment") or "").strip():
        st.session_state.upload_comment = str(script.get("comment") or "")

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
                    f"Title option {index}",
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
                    st.markdown('<div style="margin-top:.8rem;"><span class="badge" style="background:var(--ok-soft);color:var(--ok);">Approved</span></div>',unsafe_allow_html=True)
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
        ]
        cols = st.columns(3, gap="small")
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
                    }[eyebrow]
                    if st.button(button_label, type="primary", width="stretch", key=f"{key}-button"):
                        st.session_state.test_production_line = {
                            "01 · DEEP-DIVE": "deep_dive",
                            "02 · TOP-5": "top_5",
                            "03 · OTD": "otd",
                        }[eyebrow]
                        if eyebrow == "01 · DEEP-DIVE":
                            st.session_state.test_stage = "01 · Topic Fetcher"
                        st.session_state.test_pipeline_notice = None
                        st.rerun()
    elif st.session_state.test_production_line:
        line_name = {
            "deep_dive": "Deep-Dive",
            "top_5": "Top-5",
            "otd": "OTD",
        }[st.session_state.test_production_line]
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

        if line_name == "Deep-Dive":
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
                st.session_state.test_top5_handoff = None
                st.session_state.test_top5_script_data = None
                st.session_state.test_top5_script_handoff = None
                st.session_state.test_top5_audio_data = None
                st.session_state.test_top5_audio_handoff = None
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
                        new_topics = fetch_topics(
                            "cricket_india_asia",
                            more=more,
                            exclude_topics=exclude,
                            limit=20,
                        )
                    st.session_state.test_top5_topics = existing + new_topics
                    if not more:
                        st.session_state.test_top5_selected = []
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
                        for col, (index, topic) in zip(row, enumerate(topics[start:start + 2], start=start)):
                            with col:
                                with st.container(key=f"test-top5-topic-{index}"):
                                    selected_here = index in selected
                                    label = "✓ Selected" if selected_here else "Select story"
                                    disabled = not selected_here and len(selected) >= 5
                                    st.markdown(
                                        f'<div class="topic-top"><span class="topic-rank">STORY {index + 1:02d}</span></div>'
                                        f'<div class="topic-title">{topic.title}</div>'
                                        f'<div class="topic-meta">{topic.source or "Sports desk"} · {topic.published_at:%d %b · %H:%M UTC}</div>',
                                        unsafe_allow_html=True,
                                    )
                                    if st.button(label, key=f"test-top5-select-{index}", width="stretch", disabled=disabled):
                                        if selected_here:
                                            selected.remove(index)
                                        else:
                                            selected.append(index)
                                        st.session_state.test_top5_selected = selected
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
                    st.caption("Article scraping is the next enrichment step and has not been added yet.")
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
                            st.session_state["test-top5-script-hashtags"] = " ".join(
                                str(tag) for tag in (result.get("hashtags") or [])
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
                                f'{len(headline.split())} words · maximum 14 words · '
                                f'{estimate_speech_seconds(headline):.1f}s estimated speech'
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
                                height=110,
                                max_chars=360,
                                label_visibility="collapsed",
                            )
                        st.divider()

                    st.markdown('<div class="mini-label">HASHTAGS</div>', unsafe_allow_html=True)
                    st.text_input(
                        "Hashtags",
                        key="test-top5-script-hashtags",
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
                            "hashtags": [
                                tag.strip()
                                for tag in st.session_state.get("test-top5-script-hashtags", "").split()
                                if tag.strip()
                            ],
                        }
                        valid, reason = validate_top5_script(edited, stories)
                        if not valid:
                            st.error(f"Edited Top-5 script failed validation: {reason}")
                        else:
                            st.session_state.test_top5_audio_data = None
                            st.session_state.test_top5_audio_handoff = None
                            st.session_state.test_stage = "03 · Audio"
                            st.session_state.test_pipeline_notice = {
                                "confirmed": "Top-5 Script QC confirmed",
                                "next": "Moving to Audio.",
                            }
                            st.session_state.test_top5_script_handoff = {
                                "schema": "final-shorts.top5-script.v1",
                                "slides": edited["slides"],
                                "hashtags": edited["hashtags"],
                                "stories": stories,
                                "provider_used": result.get("provider_used"),
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
                            st.session_state.test_pipeline_notice = {
                                "confirmed": "Top-5 Audio QC confirmed",
                                "next": "Ready for the next production stage.",
                            }
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

                if st.session_state.get("test_top5_audio_handoff"):
                    st.success("Top-5 Audio approved. All six spoken lines are ready for the next stage.")
                    st.caption("Each audio scene maps to the corresponding spoken headline; visual story bodies remain silent.")

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
