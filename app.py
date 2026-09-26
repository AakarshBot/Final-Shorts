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
    {"key": "01 · Topic Fetcher", "number": "01", "icon": "", "label": "Topics", "desc": "Find the story"},
    {"key": "02 · Scriptwriter", "number": "02", "icon": "", "label": "Script", "desc": "Write the Short"},
    {"key": "03 · Audio", "number": "03", "icon": "", "label": "Audio", "desc": "Create voice"},
    {"key": "04 · Visuals", "number": "04", "icon": "", "label": "Visuals", "desc": "Source imagery"},
    {"key": "05 · Subtitles", "number": "05", "icon": "", "label": "Subs", "desc": "Build captions"},
    {"key": "06 · Renderer", "number": "06", "icon": "", "label": "Render", "desc": "Build video"},
    {"key": "07 · Upload QC", "number": "07", "icon": "", "label": "Upload", "desc": "Publish"},
]
st.markdown("""
<style>
:root{--bg:#f5f1e9;--surface:#fffdfa;--surface-2:#f1ece3;--ink:#211e1a;--muted:#756f65;--soft:#9a9388;--line:#e2dbd0;--line-strong:#d4ccbf;--accent:#b75a36;--accent-dark:#8f4226;--sage:#617565;--sage-soft:#e7eee8;--shadow:0 16px 44px rgba(52,43,34,.075);}
html,body,.stApp{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 8% 0%,rgba(183,90,54,.075),transparent 27%),radial-gradient(circle at 94% 8%,rgba(97,117,101,.065),transparent 23%),linear-gradient(180deg,#f8f5ef 0%,var(--bg) 100%);}
[data-testid="stHeader"]{background:transparent;} section[data-testid="stSidebar"]{display:none;} footer,#MainMenu{visibility:hidden;}
.block-container{max-width:1440px;padding:1.35rem 2rem 4rem;} h1,h2,h3,h4{color:var(--ink);letter-spacing:-.045em;} p,li{line-height:1.55;}
button{transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease,background .16s ease;} button:hover{transform:translateY(-1px);}
[data-testid="stButton"]>button,[data-testid="stFormSubmitButton"]>button,[data-testid="stDownloadButton"]>button{min-height:44px;border-radius:11px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font-weight:760;box-shadow:0 4px 14px rgba(52,43,34,.045);}
[data-testid="stButton"]>button:hover,[data-testid="stFormSubmitButton"]>button:hover{border-color:#c8beb0;box-shadow:0 9px 22px rgba(52,43,34,.075);}
[data-testid="stButton"]>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primary"]{background:var(--ink);color:#fffdfa;border-color:var(--ink);box-shadow:0 10px 24px rgba(33,30,26,.13);}
[data-testid="stButton"]>button[kind="primary"]:hover,[data-testid="stFormSubmitButton"]>button[kind="primary"]:hover{background:#35302a;border-color:#35302a;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stFileUploaderDropzone"]{background:rgba(255,253,250,.86)!important;border:1px solid var(--line-strong)!important;border-radius:11px!important;color:var(--ink)!important;}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 1px var(--accent)!important;}
[data-testid="stCaptionContainer"],.stCaption{color:var(--muted);} [data-testid="stAlert"]{border-radius:12px;}
[data-testid="stExpander"]{background:rgba(255,253,250,.92);border:1px solid var(--line);border-radius:15px;box-shadow:0 8px 26px rgba(52,43,34,.045);overflow:hidden;}
[data-testid="stExpander"] summary{padding:.85rem 1rem;color:var(--ink);} [data-testid="stExpander"] details{border:0!important;}
[data-testid="stPills"] button{background:rgba(255,253,250,.74)!important;border:1px solid var(--line)!important;border-radius:999px!important;color:var(--muted)!important;}
[data-testid="stPills"] button[aria-pressed="true"]{background:var(--ink)!important;border-color:var(--ink)!important;color:#fffdfa!important;}
.badge{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;background:var(--surface-2);border:1px solid var(--line);font-size:.64rem;font-weight:850;letter-spacing:.10em;text-transform:uppercase;color:var(--muted);}
.eyebrow,.home-kicker{color:var(--soft);font-size:.64rem;font-weight:850;letter-spacing:.17em;text-transform:uppercase;} .home-kicker{color:var(--accent-dark);}
.hero-title{font-size:clamp(2.65rem,5.1vw,5rem);line-height:.94;font-weight:900;letter-spacing:-.062em;margin:.15rem 0 0;max-width:940px;}
.hero-subtitle{color:var(--muted);font-size:1rem;line-height:1.55;max-width:720px;margin-top:.72rem;}
.home-note{display:flex;align-items:center;gap:.55rem;margin-top:1rem;color:var(--muted);font-size:.78rem;} .home-note-dot{width:7px;height:7px;border-radius:50%;background:var(--sage);}
.st-key-landing-test,.st-key-landing-live{min-height:420px;border-radius:24px;padding:30px;overflow:hidden;position:relative;border:1px solid var(--line);box-shadow:var(--shadow);}
.st-key-landing-test{background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(244,239,231,.95));}
.st-key-landing-live{background:radial-gradient(circle at 86% 8%,rgba(183,90,54,.11),transparent 22%),linear-gradient(135deg,#fffdfa 0%,#f7eee8 100%);}
.st-key-landing-test:before,.st-key-landing-live:before{content:"";position:absolute;left:30px;right:30px;top:0;height:3px;border-radius:999px;background:var(--ink);opacity:.9;} .st-key-landing-live:before{background:var(--accent);}
.st-key-landing-test button,.st-key-landing-live button{min-height:52px;border-radius:11px;}
.st-key-stage-shell{position:sticky;top:.65rem;z-index:30;background:rgba(255,253,250,.92);border:1px solid var(--line);border-radius:15px;padding:8px;backdrop-filter:blur(14px);box-shadow:0 12px 30px rgba(52,43,34,.07);}
.st-key-stage-content{background:rgba(255,253,250,.7);border:1px solid var(--line);border-radius:17px;padding:20px 22px 28px;margin-top:12px;box-shadow:var(--shadow);}
.st-key-stage-shell [data-testid="stButton"]>button{min-height:40px;border-radius:9px;font-size:.8rem;font-weight:850;} .st-key-stage-shell [data-testid="stButton"]>button[kind="primary"]{background:var(--ink);}
.stage-rail-label{font-size:.60rem;color:var(--soft);text-align:center;letter-spacing:.11em;text-transform:uppercase;margin-top:4px;} .stage-rail-line{height:1px;background:linear-gradient(90deg,transparent,var(--line-strong),transparent);margin:0 8% 4px;}
.live-glow{height:3px;border-radius:999px;background:var(--accent);box-shadow:0 3px 12px rgba(183,90,54,.2);}
.live-card{min-height:124px;border-radius:15px;border:1px solid var(--line);background:var(--surface);padding:18px;box-shadow:0 10px 30px rgba(52,43,34,.055);}
.live-card:hover{border-color:#cdc3b6;box-shadow:0 15px 34px rgba(52,43,34,.075);}
.muted{color:var(--muted);} .section-head{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin:.3rem 0 .95rem;} .section-title{font-size:1.38rem;font-weight:900;letter-spacing:-.038em;} .section-count{font-size:.63rem;color:var(--soft);letter-spacing:.12em;text-transform:uppercase;}
.card{background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:18px 20px;margin:10px 0;box-shadow:0 10px 28px rgba(52,43,34,.05);}
.topic-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;} .topic-rank{font-size:.60rem;color:var(--soft);font-weight:850;letter-spacing:.13em;text-transform:uppercase;} .topic-rating{display:none;}
.topic-selected{display:inline-flex;padding:4px 8px;border-radius:999px;background:var(--sage-soft);border:1px solid #d4e1d5;color:var(--sage);font-size:.57rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:9px;}
.topic-title{font-size:1.18rem;line-height:1.18;font-weight:860;letter-spacing:-.027em;margin:.12rem 0 .7rem;} .topic-meta{font-size:.69rem;color:var(--muted);line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
div[class*="st-key-topic-card-"]{background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:16px 16px 14px;min-height:168px;box-shadow:0 10px 28px rgba(52,43,34,.05);position:relative;overflow:hidden;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}
div[class*="st-key-topic-card-"]:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent);opacity:.2;} div[class*="st-key-topic-card-"]:hover{transform:translateY(-1px);border-color:#cfc5b8;box-shadow:0 16px 34px rgba(52,43,34,.075);} div[class*="st-key-topic-card-"] button{border-radius:9px;}
div[class*="st-key-selected-story-"]{background:linear-gradient(135deg,#fffdfa,#f4eee7);border:1px solid #dfd0c5;border-radius:15px;padding:18px 20px;box-shadow:0 12px 32px rgba(52,43,34,.055);}
div[class*="st-key-visual-card-"],div[class*="st-key-live-visual-card-"]{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px;box-shadow:0 9px 26px rgba(52,43,34,.05);overflow:hidden;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}
div[class*="st-key-visual-card-"]:hover,div[class*="st-key-live-visual-card-"]:hover{transform:translateY(-1px);border-color:#cfc5b8;box-shadow:0 14px 30px rgba(52,43,34,.075);} div[class*="st-key-visual-card-"] img,div[class*="st-key-live-visual-card-"] img{border-radius:9px;}
.visual-source{font-size:.64rem;font-weight:800;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;} .visual-detail{font-size:.60rem;color:var(--muted);line-height:1.35;}
.visual-crop-label{font-size:.55rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:var(--accent-dark);margin:.5rem 0 .25rem;} .crop-dialog-kicker{font-size:.65rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);} .crop-dialog-title{font-size:1.42rem;font-weight:900;letter-spacing:-.034em;margin-top:.15rem;}
div[class*="st-key-live-choice-"]{min-height:280px;border-radius:20px;padding:28px;overflow:hidden;position:relative;border:1px solid var(--line);background:linear-gradient(135deg,#fffdfa,#f6eee8);box-shadow:var(--shadow);}
div[class*="st-key-live-cricket-"]{min-height:200px;background:linear-gradient(145deg,#fffdfa,#f2eee6);}
div[class*="st-key-live-slide-"]{min-height:370px;border-radius:13px;border:1px solid var(--line);background:var(--surface);padding:11px;box-shadow:0 10px 28px rgba(52,43,34,.05);} div[class*="st-key-live-slide-"] img{border-radius:9px;}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:8px 12px;} .stProgress > div > div{background:var(--accent);}
@media (max-width:900px){.block-container{padding-left:1rem;padding-right:1rem;}.st-key-landing-test,.st-key-landing-live{min-height:360px;padding:24px;}.hero-title{font-size:3rem;}.topic-title{font-size:1.05rem;}.st-key-stage-shell{position:static;}}
</style>
""", unsafe_allow_html=True)

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "home"
if "test_stage" not in st.session_state:
    st.session_state.test_stage = "01 · Topic Fetcher"
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
        box_color="#8B5CF6",
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
                            st.markdown('<div class="visual-detail" style="padding-top:.45rem;">No source link</div>', unsafe_allow_html=True)


def _render_home():
    st.markdown('<div class="home-kicker">FINAL SHORTS · NEWSROOM</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">From story to Short.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">A focused workspace for finding the story, shaping the script and shipping the finished Short — without getting in the way.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="home-note"><span class="home-note-dot"></span><span>Test is the build lab. Live is the production room.</span></div>',
        unsafe_allow_html=True,
    )
    st.space("medium")
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="landing-test"):
            st.markdown('<div class="eyebrow">01 · BUILD LAB</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:3rem;font-weight:900;letter-spacing:-.05em;">TEST</div>', unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:1rem;color:#756f65;max-width:480px;">Inspect each production stage, test handoffs and tune the factory without touching a live upload.</div>',
                unsafe_allow_html=True,
            )
            st.space("medium")
            st.markdown('<span class="badge">7 stages</span> <span class="badge">manual review</span>', unsafe_allow_html=True)
            st.space("medium")
            if st.button("Open Test Lab  →", key="open-test", width="stretch"):
                st.session_state.app_mode = "test"
                st.rerun()
    with right:
        with st.container(key="landing-live"):
            st.markdown('<div class="eyebrow">02 · PRODUCTION</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:3rem;font-weight:900;letter-spacing:-.05em;">LIVE</div>', unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:1rem;color:#756f65;max-width:480px;">The production room for selecting a story, approving the handoffs and publishing the finished Short.</div>',
                unsafe_allow_html=True,
            )
            st.space("medium")
            st.markdown('<span class="badge">production</span> <span class="badge">public / private</span>', unsafe_allow_html=True)
            st.space("medium")
            if st.button("Open Live Control Room  →", key="open-live", width="stretch"):
                st.session_state.app_mode = "live"
                st.rerun()

def _stage_status(stage_key:str)->tuple[str,str]:
    checks={
        "01 · Topic Fetcher":"Topics" if st.session_state.topics else "Waiting",
        "02 · Scriptwriter":"Approved" if st.session_state.approved_script else "Waiting",
        "03 · Audio":"Approved" if st.session_state.approved_audio else "Waiting",
        "04 · Visuals":"Loaded" if st.session_state.visual_result else "Waiting",
        "05 · Subtitles":"Approved" if st.session_state.approved_subtitles else "Waiting",
        "06 · Renderer":"Preview" if st.session_state.renderer_previews else "Waiting",
        "07 · Upload QC":"Uploaded" if st.session_state.upload_result else "Waiting",
    }
    return ("ready",checks.get(stage_key,"Waiting"))

def _render_test_nav():
    home_col, title_col, status_col = st.columns([.14, 1, .28], gap="medium")
    with home_col:
        if st.button("←", key="test-home", width="stretch", help="Back to home"):
            st.session_state.app_mode = "home"
            st.rerun()
    with title_col:
        st.markdown('<div class="eyebrow">BUILD LAB</div>', unsafe_allow_html=True)
        st.markdown('<h1 style="margin:0;">Test workspace</h1>', unsafe_allow_html=True)
    with status_col:
        completed = sum(_stage_status(stage["key"])[1] != "Waiting" for stage in STAGES)
        st.markdown(
            f'<div style="text-align:right;padding-top:9px;"><span class="badge">{completed} / 7 stages active</span></div>',
            unsafe_allow_html=True,
        )
    st.space("small")
    with st.container(key="stage-shell"):
        nav_cols = st.columns(7, gap="small")
        for col, stage_info in zip(nav_cols, STAGES):
            with col:
                active = st.session_state.test_stage == stage_info["key"]
                clicked = st.button(
                    f'{stage_info["icon"]} {stage_info["number"]}',
                    key=f'stage-nav-{stage_info["number"]}',
                    type="primary" if active else "secondary",
                    width="stretch",
                    help=f'{stage_info["label"]} · {stage_info["desc"]}',
                )
                st.markdown(
                    f'<div class="stage-rail-label" style="color:{"#211e1a" if active else "#9a9388"};">{stage_info["label"]}</div>',
                    unsafe_allow_html=True,
                )
                if clicked:
                    st.session_state.test_stage = stage_info["key"]
                    st.rerun()
    st.markdown('<div class="stage-rail-line"></div>', unsafe_allow_html=True)

def _live_story_key(topic) -> str:
    return hashlib.sha1(
        f"{topic.title}|{topic.url}".encode("utf-8")
    ).hexdigest()[:12]


def _live_reset_downstream():
    for key, value in {
        "live_selected_topic": None,
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
                        '<div style="min-height:260px;display:flex;align-items:center;'
                        'justify-content:center;border:1px dashed rgba(255,255,255,.12);'
                        'border-radius:10px;color:#657080;">EMPTY</div>',
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
    st.markdown('<div class="eyebrow">PRODUCTION CONTROL ROOM</div>',unsafe_allow_html=True)
    left,right=st.columns([1,.22],gap="large")
    with left:
        st.markdown('<h1 style="margin:0;font-size:3.2rem;">LIVE</h1>',unsafe_allow_html=True)
        st.markdown(
            '<div class="hero-subtitle">Choose a desk, choose a story, then move through the finished factory in one continuous production flow.</div>',
            unsafe_allow_html=True,
        )
    with right:
        controls = st.columns(2, gap="small")
        with controls[0]:
            if st.button("New Short", key="live-new-short", width="stretch"):
                _live_reset_downstream()
                st.session_state.live_desk = None
                st.session_state.live_cricket_profile = None
                st.session_state.live_topics = []
                st.session_state.live_topics_profile = None
                st.session_state.live_stage = "01 · Story"
                st.rerun()
        with controls[1]:
            if st.button("← Home",key="live-home",width="stretch"):
                st.session_state.app_mode="home"
                st.rerun()

    if st.session_state.live_desk is None:
        st.space("medium")
        st.markdown('<div class="section-head"><div><div class="eyebrow">START PRODUCTION</div><div class="section-title">Choose your sports desk</div></div></div>', unsafe_allow_html=True)
        left, right = st.columns(2, gap="small")
        with left:
            with st.container(key="live-choice-cricket"):
                st.markdown('<div class="eyebrow">01 · CRICKET</div>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:3rem;font-weight:900;letter-spacing:-.05em;">CRICKET</div>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:1.02rem;color:#f1eaf8;max-width:430px;">India / Asia stories and global cricket stories.</div>', unsafe_allow_html=True)
                st.space("medium")
                if st.button("Choose Cricket →", type="primary", width="stretch", key="live-choose-cricket"):
                    st.session_state.live_desk = "cricket"
                    st.rerun()
        with right:
            with st.container(key="live-choice-niche"):
                st.markdown('<div class="eyebrow">02 · NICHE SPORTS</div>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:3rem;font-weight:900;letter-spacing:-.05em;">NICHE</div>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:1.02rem;color:#f1eaf8;max-width:430px;">Tennis, badminton, motorsport, athletics, hockey, chess and more.</div>', unsafe_allow_html=True)
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
                    st.markdown(f'<div style="font-size:2.7rem;font-weight:900;letter-spacing:-.05em;">{title}</div>', unsafe_allow_html=True)
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
    live_stage_labels = ["STORY", "SCRIPT", "AUDIO + SUBS", "VISUALS + RENDER", "UPLOAD"]
    current_stage = live_stage_order.index(st.session_state.live_stage)

    stage_cols = st.columns(len(live_stage_order), gap="small")
    for stage_index, (label, stage_key) in enumerate(zip(live_stage_labels, live_stage_order)):
        with stage_cols[stage_index]:
            state_label = "✓ COMPLETE" if stage_index < current_stage else "● ACTIVE" if stage_index == current_stage else "LOCKED"
            st.markdown(
                f'<div class="live-card" style="min-height:72px;padding:12px 14px;">'
                f'<div class="eyebrow">0{stage_index + 1}</div>'
                f'<div style="font-size:.78rem;font-weight:900;letter-spacing:.04em;">{label}</div>'
                f'<div class="visual-detail">{state_label}</div></div>',
                unsafe_allow_html=True,
            )

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
                    rating = max(1, min(5, round(float(topic.score or 0.0) / 8.0 * 5.0)))
                    stars = "★" * rating + "☆" * (5 - rating)
                    with st.container(key=f"live-topic-{index}"):
                        st.markdown(
                            f'<div class="topic-top"><span class="topic-rank">STORY {index + 1:02d}</span><span class="topic-rating">{stars}</span></div>'
                            f'<div class="topic-title">{topic.title}</div>',
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
    st.header("01 · Topic Fetcher")
    desk = st.pills(
        "Desk",
        list(profiles),
        default="Cricket India / Asia",
        key="topic_desk",
        label_visibility="collapsed",
    ) or "Cricket India / Asia"
    previous_desk = st.session_state.get("topic_desk_profile")
    if previous_desk and previous_desk != profiles[desk]:
        st.session_state.topics = []
        st.session_state.selected_topic = None
        st.session_state.script_data = None
        st.session_state.approved_script = None
        st.session_state.audio_data = None
        st.session_state.approved_audio = None
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None
        st.session_state.visual_result = None
        st.session_state.visual_loaded_story = None
        st.session_state.renderer_previews = None
        st.session_state.rendered_video_path = None
        st.session_state.upload_qc_approved = False
        st.session_state.upload_result = None
        st.session_state.upload_qc = None
        st.session_state.manual_visual_result = None
        st.session_state.real_image_result = None
        st.session_state.ai_image_result = None
        st.session_state.visual_crops = {}
    st.session_state.topic_desk_profile = profiles[desk]
    col1, col2 = st.columns(2)
    with col1:
        fetch = st.button("Fetch topics", type="primary", width="stretch")
    with col2:
        more = st.button("Find 20 more", width="stretch")

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

    st.markdown(
        '<div class="section-head"><div><div class="eyebrow">STORY DESK</div><div class="section-title">Choose the next story</div></div><div class="section-count">'
        + f'{len(st.session_state.topics)} stories'
        + '</div></div>',
        unsafe_allow_html=True,
    )

    topics = st.session_state.topics
    for start in range(0, len(topics), 2):
        row = st.columns(2, gap="medium")
        for col, (index, topic) in zip(
            row,
            enumerate(topics[start:start + 2], start=start),
        ):
            with col:
                rating = max(
                    1,
                    min(
                        5,
                        round(float(topic.score or 0.0) / 8.0 * 5.0),
                    ),
                )
                stars = "★" * rating + "☆" * (5 - rating)
                source = topic.source or "Sports desk"
                published = topic.published_at.strftime("%d %b · %H:%M UTC")
                with st.container(key=f"topic-card-{index}"):
                    if index == st.session_state.selected_topic:
                        st.markdown('<div class="topic-selected">SELECTED</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'''
                        <div class="topic-top">
                            <span class="topic-rank">STORY {index + 1:02d}</span>
                            <span class="topic-rating" title="{rating}/5">{stars}</span>
                        </div>
                        <div class="topic-title">{topic.title}</div>
                        <div class="topic-meta">{source} · {published}</div>
                        ''',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Select story  →",
                        key=f"topic-select-{index}",
                        width="stretch",
                    ):
                        st.session_state.selected_topic = index
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

    if st.session_state.selected_topic is not None:
        index = st.session_state.selected_topic
        if index < len(st.session_state.topics):
            topic = st.session_state.topics[index]
            with st.container(key="selected-story-card"):
                st.markdown('<div class="eyebrow">SELECTED STORY</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:1.18rem;font-weight:900;letter-spacing:-.02em;">{topic.title}</div>', unsafe_allow_html=True)
                st.caption(topic.description or f"{topic.source} · {topic.published_at.strftime('%d %b · %H:%M UTC')}")
                if topic.url:
                    st.link_button("Open original story ↗", topic.url, width="stretch")


def render_scriptwriter():
    st.header("02 · Scriptwriter")

    if not st.session_state.topics:
        st.info("Run the Topic Fetcher first, then select a story here.")
        return

    selected_index = st.session_state.selected_topic
    if selected_index is None or not 0 <= selected_index < len(st.session_state.topics):
        st.info("Choose a story in 01 · Topic Fetcher first.")
        return
    topic = st.session_state.topics[selected_index]

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"**{topic.title}**")
    st.caption(topic.description or "The Topic Fetcher did not provide a longer description.")
    st.markdown("</div>", unsafe_allow_html=True)

    language = st.pills(
        "Language",
        ["English", "Hindi", "Telugu"],
        default="English",
        key="script_language",
        label_visibility="collapsed",
    ) or "English"

    if st.button("Generate script", type="primary", width="stretch"):
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
        st.session_state.subtitle_data = None
        st.session_state.approved_subtitles = None
        st.session_state.renderer_previews = None
        st.session_state.rendered_video_path = None
        st.session_state.upload_qc_approved = False
        st.session_state.upload_result = None
        st.session_state.upload_qc = None

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

    if st.button("Approve script", type="primary", width="stretch"):
        try:
            approved = apply_script_edits(
                script,
                edited_voiceovers,
                headline=edited_headline,
            )
            st.session_state.approved_script = approved
            st.session_state.audio_data = None
            st.session_state.approved_audio = None
            st.session_state.renderer_previews = None
            st.session_state.upload_qc_approved = False
            st.session_state.upload_result = None
            st.session_state.rendered_video_path = None
            st.session_state.upload_qc = None
            for index in range(1, 4):
                st.session_state.pop(f"upload-title-{index}", None)
            st.session_state.pop("upload_video_file", None)
            st.session_state.upload_title_options = list(approved.get("titles") or [])
            st.session_state.upload_title_choice = 0
            st.session_state.upload_description = str(approved.get("seo_description") or "")
            st.session_state.upload_hashtags = " ".join(approved.get("hashtags") or [])
            st.session_state.upload_comment = str(approved.get("comment") or "")
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_script:
        st.success("Script approved and stored as the handoff for Function 03 · Audio.")


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
    st.header("05 · Subtitles")
    st.caption("Build captions directly from the approved Scriptwriter text and native Audio word timings.")

    script = st.session_state.approved_script
    audio = st.session_state.approved_audio
    if not script or not audio:
        st.info("Approve the Scriptwriter and Audio handoffs first.")
        return

    if st.button("Generate subtitles", type="primary", width="stretch"):
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

    if st.button("Approve subtitles", type="primary", width="stretch"):
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

    if st.button("Build preview", type="primary", width="stretch"):
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
        st.caption("Optional headline enters from the left while spoken captions remain visible.")

    with right:
        st.markdown("**Final overlay**")
        if final and Path(final).exists():
            st.video(str(final), width=300)
        st.caption("Large bold captions · yellow active word · logo top-right · source bottom-right")



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

def render_audio():
    st.header("03 · Audio")

    script = st.session_state.approved_script
    if not script:
        st.info("Approve a Scriptwriter result first. Audio only accepts the approved narration handoff.")
        return

    languages = ["English", "Hindi", "Telugu"]
    stored = str(script.get("language_used") or "english").casefold()
    default_language = stored if stored in {"english", "hindi", "telugu"} else "english"
    language = st.pills(
        "Language",
        languages,
        default=default_language.title(),
        key="audio_language",
        label_visibility="collapsed",
    ) or default_language.title()
    st.caption("HYPE COMMENTATOR · female Indian voice · native Edge-TTS word timings")

    if st.button("Generate audio", type="primary", width="stretch"):
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

    if st.button("Approve audio", type="primary", width="stretch"):
        try:
            st.session_state.approved_audio = approve_audio(audio)
            st.session_state.subtitle_data = None
            st.session_state.approved_subtitles = None
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.approved_audio:
        st.success("Audio approved and stored as the handoff for Function 04 · Visuals.")

if st.session_state.app_mode == "home":
    _render_home()
elif st.session_state.app_mode == "test":
    _render_test_nav()
    with st.container(key="stage-content"):
        stage = st.session_state.test_stage
        stage_info = next(item for item in STAGES if item["key"] == stage)
        st.markdown(
            f'<div class="eyebrow">{stage_info["number"]} · {stage_info["label"]}</div>',
            unsafe_allow_html=True,
        )
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
elif st.session_state.app_mode == "live":
    render_live_dashboard()