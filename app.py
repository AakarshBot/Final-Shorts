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
from visual_fetcher import crawl_visuals, manual_crawl_visuals
from visual_search import search_images
from visual_generator import generate_images
from renderer import HEADLINE_TEXT, FINAL_STYLE_NAME, build_preview_bundle
from subtitles import generate_subtitles
from uploader import upload_video

st.set_page_config(page_title="Final Shorts", page_icon="▣", layout="wide")

STAGES = [
    {"key": "01 · Topic Fetcher", "number": "01", "icon": "🗞️", "label": "Topics", "desc": "Find the story"},
    {"key": "02 · Scriptwriter", "number": "02", "icon": "✍️", "label": "Script", "desc": "Write the Short"},
    {"key": "03 · Audio", "number": "03", "icon": "🎙️", "label": "Audio", "desc": "Create voice"},
    {"key": "04 · Visuals", "number": "04", "icon": "🖼️", "label": "Visuals", "desc": "Source imagery"},
    {"key": "05 · Subtitles", "number": "05", "icon": "💬", "label": "Subs", "desc": "Build captions"},
    {"key": "06 · Renderer", "number": "06", "icon": "🎬", "label": "Render", "desc": "Build video"},
    {"key": "07 · Upload QC", "number": "07", "icon": "🚀", "label": "Upload", "desc": "Publish"},
]

st.markdown("""
<style>
:root{--bg:#07090d;--panel:#0d1118;--panel-2:#111722;--text:#f5f7fb;--muted:#8791a2;--line:rgba(255,255,255,.095);--line-strong:rgba(255,255,255,.15);--violet:#8b5cf6;--cyan:#22d3ee;--pink:#f43f8a;}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 8% 0%,rgba(139,92,246,.11),transparent 28%),radial-gradient(circle at 92% 12%,rgba(34,211,238,.07),transparent 24%),linear-gradient(180deg,#090b10 0%,var(--bg) 58%,#06080b 100%);color:var(--text);}
[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{display:none;}
footer,#MainMenu{visibility:hidden;}
.block-container{max-width:1500px;padding:1rem 2rem 3.25rem;}
h1,h2,h3{letter-spacing:-.04em;}
button{transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease;}
button:hover{transform:translateY(-1px);}
.card{background:linear-gradient(145deg,rgba(255,255,255,.045),rgba(255,255,255,.015));border:1px solid var(--line);border-radius:16px;padding:20px;margin:10px 0;box-shadow:0 18px 48px rgba(0,0,0,.22);}
.badge{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:7px;background:rgba(255,255,255,.045);border:1px solid var(--line);font-size:.68rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase;color:#b8c0cc;}
.eyebrow{color:#788394;font-size:.67rem;font-weight:900;letter-spacing:.17em;text-transform:uppercase;}
.hero-title{font-size:clamp(2.6rem,5vw,5rem);line-height:.92;font-weight:950;letter-spacing:-.055em;margin:0;}
.hero-subtitle{color:#a7afbc;font-size:.98rem;line-height:1.55;max-width:660px;margin-top:.72rem;}
.st-key-landing-test,.st-key-landing-live{min-height:500px;border-radius:24px;padding:32px;overflow:hidden;position:relative;border:1px solid var(--line-strong);}
.st-key-landing-test{background:radial-gradient(circle at 78% 12%,rgba(255,255,255,.11),transparent 24%),repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 1px,transparent 1px 4px),linear-gradient(145deg,#3e444d,#20252b);box-shadow:inset 0 0 110px rgba(0,0,0,.22),0 26px 64px rgba(0,0,0,.26);}
.st-key-landing-live{background:radial-gradient(circle at 78% 15%,rgba(255,255,255,.18),transparent 20%),radial-gradient(circle at 16% 86%,rgba(34,211,238,.28),transparent 30%),linear-gradient(135deg,#21122f,#57205f 46%,#123a70);box-shadow:inset 0 0 130px rgba(244,63,138,.14),0 26px 70px rgba(75,42,140,.28);}
.st-key-landing-test:before,.st-key-landing-live:before{content:"";position:absolute;left:32px;right:32px;top:0;height:2px;background:linear-gradient(90deg,transparent,#fff,transparent);opacity:.35;}
.st-key-landing-live:before{background:linear-gradient(90deg,#f43f8a,#8b5cf6,#22d3ee);opacity:.95;box-shadow:0 0 24px rgba(139,92,246,.35);}
.st-key-landing-test button,.st-key-landing-live button{min-height:54px;border-radius:11px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;}
.st-key-landing-test button{background:rgba(8,10,14,.72);border-color:rgba(255,255,255,.20);}
.st-key-landing-test button:hover{border-color:rgba(255,255,255,.36);box-shadow:0 12px 28px rgba(0,0,0,.28);}
.st-key-landing-live button{background:linear-gradient(90deg,rgba(244,63,138,.92),rgba(139,92,246,.94));border-color:rgba(255,255,255,.24);box-shadow:0 10px 30px rgba(108,69,246,.20);}
.st-key-landing-live button:hover{box-shadow:0 14px 36px rgba(108,69,246,.34);}
.st-key-stage-shell{background:rgba(10,13,18,.82);border:1px solid var(--line);border-radius:16px;padding:10px 10px 5px;backdrop-filter:blur(18px);box-shadow:0 18px 46px rgba(0,0,0,.20);}
.st-key-stage-content{background:linear-gradient(145deg,rgba(255,255,255,.038),rgba(255,255,255,.010));border:1px solid var(--line);border-radius:16px;padding:18px 20px 26px;margin-top:12px;box-shadow:0 18px 48px rgba(0,0,0,.18);}
.st-key-stage-shell button{min-height:46px;border-radius:10px;font-size:.9rem;}
.stage-rail-label{font-size:.63rem;color:var(--muted);text-align:center;letter-spacing:.12em;text-transform:uppercase;margin-top:5px;}
.stage-rail-line{height:1px;background:linear-gradient(90deg,rgba(255,255,255,.13),rgba(255,255,255,.025));margin:0 8%;}
.live-glow{height:3px;border-radius:999px;background:linear-gradient(90deg,#f43f8a,#8b5cf6,#22d3ee);box-shadow:0 0 24px rgba(139,92,246,.32);}
.live-card{min-height:138px;border-radius:14px;border:1px solid rgba(255,255,255,.09);background:linear-gradient(145deg,rgba(255,255,255,.045),rgba(255,255,255,.012));padding:18px;box-shadow:0 14px 34px rgba(0,0,0,.14);}
.live-card:hover{border-color:rgba(139,92,246,.24);box-shadow:0 18px 42px rgba(0,0,0,.20);}
.muted{color:var(--muted);}
.section-head{display:flex;align-items:end;justify-content:space-between;margin:.35rem 0 1rem;}
.section-title{font-size:1.42rem;font-weight:950;letter-spacing:-.035em;}
.section-count{font-size:.68rem;color:#707b8b;letter-spacing:.13em;text-transform:uppercase;}
.topic-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.topic-rank{font-size:.66rem;color:#798494;font-weight:900;letter-spacing:.14em;text-transform:uppercase;}
.topic-rating{font-size:1.02rem;letter-spacing:.10em;color:#ffd35f;text-shadow:0 0 16px rgba(255,211,95,.13);}
.topic-title{font-size:1.34rem;line-height:1.08;font-weight:950;letter-spacing:-.032em;margin:.12rem 0 .8rem;min-height:2.2em;}
.topic-meta{font-size:.70rem;color:#7f8a9a;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.topic-selected{display:inline-flex;padding:4px 8px;border-radius:6px;background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.25);color:#71e8f7;font-size:.58rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;margin-bottom:9px;}
div[class*="st-key-topic-card-"]{background:linear-gradient(145deg,rgba(255,255,255,.050),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:16px;padding:16px 16px 14px;min-height:178px;box-shadow:0 14px 40px rgba(0,0,0,.17);position:relative;overflow:hidden;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}
div[class*="st-key-topic-card-"]:before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:linear-gradient(180deg,#f43f8a,#8b5cf6,#22d3ee);opacity:.28;}
div[class*="st-key-topic-card-"]:hover{transform:translateY(-2px);border-color:rgba(139,92,246,.30);box-shadow:0 20px 48px rgba(0,0,0,.23);}
div[class*="st-key-topic-card-"] button{border-radius:9px;font-weight:850;}
div[class*="st-key-selected-story-"]{background:linear-gradient(145deg,rgba(34,211,238,.075),rgba(139,92,246,.025));border:1px solid rgba(34,211,238,.20);border-radius:14px;padding:18px 20px;box-shadow:0 18px 48px rgba(0,0,0,.18);}
div[class*="st-key-visual-card-"]{background:linear-gradient(145deg,rgba(255,255,255,.048),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:14px;padding:10px;box-shadow:0 14px 38px rgba(0,0,0,.18);overflow:hidden;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}
div[class*="st-key-visual-card-"]:hover{transform:translateY(-2px);border-color:rgba(139,92,246,.32);box-shadow:0 20px 44px rgba(0,0,0,.23);}
div[class*="st-key-visual-card-"] img{border-radius:9px;}
.visual-source{font-size:.66rem;font-weight:850;color:#aab3c0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.visual-detail{font-size:.62rem;color:#707b89;line-height:1.35;}
.visual-crop-label{font-size:.58rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase;color:#8eeaf7;margin:.55rem 0 .3rem;}
.crop-dialog-kicker{font-size:.68rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#8894a6;}
.crop-dialog-title{font-size:1.45rem;font-weight:950;letter-spacing:-.035em;margin-top:.15rem;}
@media (max-width: 900px){.block-container{padding-left:1rem;padding-right:1rem}.st-key-landing-test,.st-key-landing-live{min-height:420px;padding:24px}.hero-title{font-size:3rem}.topic-title{font-size:1.15rem}}
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
def _crop_visual_dialog(asset_key: str, image_bytes: bytes, label: str):
    image = _asset_to_image(image_bytes)
    if image is None:
        st.error("This visual could not be opened for cropping.")
        return

    st.markdown('<div class="crop-dialog-kicker">MANUAL CROP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="crop-dialog-title">{label}</div>', unsafe_allow_html=True)
    st.caption("Free-size crop · drag the rectangle over the exact framing you want. The original visual stays untouched.")

    from streamlit_cropper import st_cropper

    cropped = st_cropper(
        image,
        realtime_update=True,
        box_color="#8B5CF6",
        aspect_ratio=None,
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
        st.caption("Saved as a review preview only. It does not replace the source asset.")
        if st.button("Save crop", type="primary", width="stretch"):
            buffer = BytesIO()
            cropped.convert("RGB").save(buffer, format="JPEG", quality=92, optimize=True)
            st.session_state.visual_crops[asset_key] = buffer.getvalue()
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
    st.markdown('<div class="eyebrow">FINAL SHORTS · CONTROL CENTER</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Make the next Short.</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Choose your workspace. Test is the build lab; Live is the production control room.</div>',unsafe_allow_html=True)
    st.space("medium")
    left,right=st.columns(2,gap="small")
    with left:
        with st.container(key="landing-test"):
            st.markdown('<div class="eyebrow">01 · BUILD LAB</div>',unsafe_allow_html=True)
            st.markdown('<div style="font-size:3.1rem;font-weight:900;letter-spacing:-.05em;">TEST</div>',unsafe_allow_html=True)
            st.markdown('<div style="font-size:1.05rem;color:#d6d9df;max-width:430px;">Inspect every stage, test handoffs, and tune the factory without touching production.</div>',unsafe_allow_html=True)
            st.space("large")
            st.markdown('<span class="badge">7 stages</span> <span class="badge">manual review</span>',unsafe_allow_html=True)
            st.space("large")
            if st.button("Open Test Lab  →",key="open-test",width="stretch"):
                st.session_state.app_mode="test"
                st.rerun()
    with right:
        with st.container(key="landing-live"):
            st.markdown('<div class="eyebrow">02 · PRODUCTION</div>',unsafe_allow_html=True)
            st.markdown('<div style="font-size:3.1rem;font-weight:900;letter-spacing:-.05em;">LIVE</div>',unsafe_allow_html=True)
            st.markdown('<div style="font-size:1.05rem;color:#f1eaf8;max-width:430px;">One clean control room for the real Shorts pipeline, from story selection through upload.</div>',unsafe_allow_html=True)
            st.space("large")
            st.markdown('<span class="badge">production</span> <span class="badge">public / private</span>',unsafe_allow_html=True)
            st.space("large")
            if st.button("Open Live Control Room  →",key="open-live",width="stretch"):
                st.session_state.app_mode="live"
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
    home_col,title_col,status_col=st.columns([.18,1,.38],gap="medium")
    with home_col:
        if st.button("← Home",key="test-home",width="stretch"):
            st.session_state.app_mode="home"
            st.rerun()
    with title_col:
        st.markdown('<div class="eyebrow">BUILD LAB</div>',unsafe_allow_html=True)
        st.markdown('<h1 style="margin:0;">TEST</h1>',unsafe_allow_html=True)
    with status_col:
        completed=sum(_stage_status(stage["key"])[1]!="Waiting" for stage in STAGES)
        st.markdown(f'<div style="text-align:right;"><span class="badge">{completed} / 7 active</span></div>',unsafe_allow_html=True)
    st.space("small")
    with st.container(key="stage-shell"):
        nav_cols=st.columns(7,gap="small")
        for col,stage_info in zip(nav_cols,STAGES):
            with col:
                active=st.session_state.test_stage==stage_info["key"]
                clicked=st.button(
                    f'{stage_info["icon"]} {stage_info["number"]}',
                    key=f'stage-nav-{stage_info["number"]}',
                    type="primary" if active else "secondary",
                    width="stretch",
                    help=f'{stage_info["label"]} · {stage_info["desc"]}',
                )
                st.markdown(
                    f'<div class="stage-rail-label" style="color:{"#f6f7fb" if active else "#7d8694"};">{stage_info["label"]}</div>',
                    unsafe_allow_html=True,
                )
                if clicked:
                    st.session_state.test_stage=stage_info["key"]
                    st.rerun()
    st.markdown('<div class="stage-rail-line"></div>',unsafe_allow_html=True)

def render_live_dashboard():
    st.markdown('<div class="eyebrow">PRODUCTION CONTROL ROOM</div>',unsafe_allow_html=True)
    left,right=st.columns([1,.32],gap="large")
    with left:
        st.markdown('<h1 style="margin:0;font-size:3.2rem;">LIVE</h1>',unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">A single production surface for the completed factory. The visual layer is ready; production orchestration remains separate from the stage implementations.</div>',unsafe_allow_html=True)
    with right:
        if st.button("← Home",key="live-home",width="stretch"):
            st.session_state.app_mode="home"
            st.rerun()
    st.space("small")
    st.markdown('<div class="live-glow"></div>',unsafe_allow_html=True)
    st.space("medium")
    story=(
        st.session_state.topics[st.session_state.selected_topic]
        if st.session_state.selected_topic is not None
        and 0 <= st.session_state.selected_topic < len(st.session_state.topics)
        else None
    )
    st.markdown('<div class="eyebrow">CURRENT PIPELINE</div>',unsafe_allow_html=True)
    cols=st.columns(4,gap="small")
    live_cards=[
        ("01","Story",story.title if story else "No story selected"),
        ("02","Script","Approved" if st.session_state.approved_script else "Waiting"),
        ("03","Audio","Approved" if st.session_state.approved_audio else "Waiting"),
        ("04","Media","Loaded" if st.session_state.visual_result else "Waiting"),
    ]
    for col,(number,label,value) in zip(cols,live_cards):
        with col:
            st.markdown(f'<div class="live-card"><div class="eyebrow">{number} · {label}</div><div style="font-size:1.12rem;font-weight:800;">{value}</div></div>',unsafe_allow_html=True)
    st.space("medium")
    st.markdown('<div class="eyebrow">FACTORY</div>',unsafe_allow_html=True)
    pipeline_cols=st.columns(7,gap="small")
    for col,stage_info in zip(pipeline_cols,STAGES):
        _,label=_stage_status(stage_info["key"])
        dot="●" if label!="Waiting" else "○"
        with col:
            st.markdown(f'<div class="live-card" style="min-height:120px;text-align:center;"><div style="font-size:1.8rem;">{stage_info["icon"]}</div><div class="eyebrow">{stage_info["number"]}</div><div style="font-weight:800;">{stage_info["label"]}</div><div class="muted">{dot} {label}</div></div>',unsafe_allow_html=True)
    st.space("medium")
    st.markdown('<div class="card"><div class="eyebrow">LIVE MODE</div><div style="font-size:1.1rem;font-weight:800;margin-bottom:.4rem;">Production orchestration is the next integration layer.</div><div class="muted">The completed function contracts are preserved. This control-room UI does not alter or duplicate those functions.</div></div>',unsafe_allow_html=True)


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
        st.caption("Optional headline enters from the left, then clears before subtitles appear.")

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