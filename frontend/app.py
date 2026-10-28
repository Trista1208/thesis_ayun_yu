"""
Earlier Streamlit prototype. The demonstration to review is the React app in web/.

AYUN Longevity Clinic — Joule sport-prescription engine (Joule for AYUN)
Connects member health data to age/gender-stratified sport recommendations
and an AI sports-scientist chatbot.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load .env from project root
from pathlib import Path
_env_path = Path(_ROOT) / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from datetime import datetime as _dt
import streamlit as st

# Inject Streamlit secrets into os.environ (for Community Cloud deployment)
try:
    if hasattr(st, "secrets") and st.secrets.get("GITHUB_TOKEN"):
        os.environ.setdefault("GITHUB_TOKEN", str(st.secrets["GITHUB_TOKEN"]))
    if hasattr(st, "secrets") and st.secrets.get("APP_BASE_URL"):
        os.environ.setdefault("APP_BASE_URL", str(st.secrets["APP_BASE_URL"]))
    if hasattr(st, "secrets") and st.secrets.get("EXPERT_PASSWORD"):
        os.environ.setdefault("EXPERT_PASSWORD", str(st.secrets["EXPERT_PASSWORD"]))
    if hasattr(st, "secrets") and st.secrets.get("SUPABASE_URL"):
        os.environ.setdefault("SUPABASE_URL", str(st.secrets["SUPABASE_URL"]))
    if hasattr(st, "secrets") and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"):
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"]))
except Exception:
    pass

import base64
import importlib
import yaml
from backend.rules import recommendation_api
importlib.reload(recommendation_api)
from backend.rules.recommendation_api import (
    get_recommendations,
    PRIORITY_COLOUR,
    PRIORITY_EMOJI,
    RATING_COLOUR,
    RATING_EMOJI,
    _PARAM_LABELS,
    RecommendationResult,
)
from backend.rules.training_zones import zones_as_dict
from backend.ai import chatbot as cb
from backend.ai.ask_engine import ask_with_knowledge
from backend.ai.knowledge_pipeline import build_reviewed_recommendation_context, capture_from_doctor_review
from knowledge_ui import render_expert_qa_tab, render_knowledge_library_tab
from backend.auth import expert_auth
from backend.documents.pdf_extractor import extract_from_bytes, to_member_dict, SUPPORTED_EXTENSIONS, SUPPORTED_LABEL


_ICON_PATH       = os.path.join(_HERE, "assets", "ayun_icon.png")
_LOGO_PATH       = os.path.join(_HERE, "assets", "ayun_logo.png")
_LOGO_COLOR_PATH = os.path.join(_HERE, "assets", "ayun_logo_color.png")
_JOULE_LOGO_PATH = os.path.join(_HERE, "assets", "joule_logo.png")

def _logo_img_html(path: str, *, height: int = 36, alt: str = "AYUN", cls: str = "ayun-nav-logo") -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (
        f'<img src="data:image/png;base64,{b64}" alt="{alt}" '
        f'class="{cls}" style="height:{height}px;width:auto;" />'
    )

def _joule_mark_html(*, size: int = 36) -> str:
    if not os.path.exists(_JOULE_LOGO_PATH):
        return '<span class="brand-product-name">Joule</span>'
    with open(_JOULE_LOGO_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (
        f'<img src="data:image/png;base64,{b64}" alt="Joule" class="joule-mark-img" '
        f'style="height:{size}px;width:{size}px;object-fit:cover;border-radius:6px;" />'
    )

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Joule for AYUN · Sport Plan",
    page_icon=_JOULE_LOGO_PATH if os.path.exists(_JOULE_LOGO_PATH) else (
        _ICON_PATH if os.path.exists(_ICON_PATH) else "⚡"
    ),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand colour palette ───────────────────────────────────────────────────────
_GREEN        = "#2e7d52"    # AYUN primary
_GREEN_MID    = "#52a872"    # medium accent
_GREEN_DARK   = "#1a4d35"    # headings / dark
_GREEN_DEEP   = "#0f2e1e"    # sidebar deep bg
_GREEN_PANEL  = "#163d28"    # sidebar section dividers
_GREEN_LIGHT  = "#dff0e6"    # light tint (cards, borders)
_GREEN_XLIGHT = "#eef7f1"    # main content bg
_SIDEBAR_TEXT = "#d4edd9"    # light text on dark sidebar
_SIDEBAR_HEAD = "#7fcca0"    # section headers on sidebar

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* ══ HIDE TOP BLACK BAR (header, deploy, menu) — fully remove ═══════════ */
  /* Note: stToolbar/stHeader must stay visible — they contain the sidebar expand button */
  #MainMenu {{ visibility: hidden; }}
  .stDeployButton {{ display: none !important; }}
  footer {{ visibility: hidden; }}
  #stDecoration {{ display: none !important; height: 0 !important; min-height: 0 !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important; }}
  .stDecoration {{ display: none !important; height: 0 !important; min-height: 0 !important; overflow: hidden !important; }}
  /* Remove top gap — content starts from top */
  [data-testid="stAppViewContainer"] {{ padding-top: 0 !important; margin-top: 0 !important; }}
  [data-testid="stAppViewContainer"] > div {{ padding-top: 0 !important; margin-top: 0 !important; }}
  .block-container {{ padding-top: 1rem !important; padding-left: 1.25rem !important; padding-right: 1.5rem !important; max-width: 100%; }}

  /* ══ RADIO & SLIDER — green theme (override red) ═════════════════ */
  /* Radio circle only — no background on Male/Female labels */
  [data-baseweb="radio"] div[role="radio"][aria-checked="true"] > div:first-child,
  [data-baseweb="radio"] [aria-checked="true"] > div:first-child,
  .stRadio div[role="radio"] > div:first-child {{
    background: {_GREEN} !important;
    background-color: {_GREEN} !important;
    border-color: {_GREEN} !important;
  }}
  [data-baseweb="radio"] label,
  .stRadio label,
  .stRadio [data-baseweb="radio"] label,
  .stRadio [role="radiogroup"] > label,
  [data-baseweb="radio"] {{
    background: transparent !important;
    background-color: transparent !important;
  }}
  /* Radio labels — dark text, no background */
  .stRadio label,
  .stRadio span,
  .stRadio p {{
    color: #1a1a1a !important;
  }}
  /* Slider: valid range (filled, left of thumb) = green; remainder (right) = light red */
  [data-baseweb="slider"] > div > div:first-child,
  .stSlider [data-baseweb="slider"] > div > div:first-child {{
    background: #e8d4d4 !important;
    background-color: #e8d4d4 !important;
  }}
  [data-baseweb="slider"] > div > div:nth-child(2),
  .stSlider [data-baseweb="slider"] > div > div:nth-child(2) {{
    background: {_GREEN} !important;
    background-color: {_GREEN} !important;
  }}
  /* Slider thumb — green accent */
  .stSlider [data-baseweb="slider"] > div > div:last-child,
  input[type="range"]::-webkit-slider-thumb {{
    background: {_GREEN} !important;
    border-color: {_GREEN} !important;
  }}
  input[type="range"]::-moz-range-thumb {{
    background: {_GREEN} !important;
    border-color: {_GREEN} !important;
  }}
  input[type="range"]::-webkit-slider-runnable-track {{
    background: #e8d4d4 !important;
  }}
  input[type="range"]::-webkit-slider-thumb {{
    background: {_GREEN} !important;
  }}
  /* Slider value & labels — dark text for readability */
  .stSlider label,
  .stSlider p,
  .stSlider span,
  .stSlider [data-baseweb="slider"] + div,
  .stSlider [data-baseweb="slider"] ~ div {{
    color: #1a1a1a !important;
  }}

  /* ══ GLOBAL ══════════════════════════════════════════════════════ */
  .stApp {{ background-color: {_GREEN_XLIGHT}; }}
  p, span, li {{ color: #1a1a1a; }}
  h1, h2, h3  {{ color: {_GREEN_DARK}; }}
  h4, h5, h6  {{ color: {_GREEN}; }}

  /* ══ MAIN CONTENT AREA ══════════════════════════════════════════ */
  [data-testid="stMainBlockContainer"] {{
    background: {_GREEN_XLIGHT};
  }}

  /* Metric widgets */
  [data-testid="stMetricValue"] {{
    color: {_GREEN_DARK} !important; font-size:1.3rem; font-weight:700;
  }}
  [data-testid="stMetricLabel"] {{ color: #3a6b4a !important; }}
  [data-testid="stMetric"] {{
    background: #ffffff;
    border: 1px solid {_GREEN_LIGHT};
    border-radius: 10px;
    padding: 10px 14px !important;
  }}

  /* Tabs — full bar, no cut-off, aligned */
  [data-testid="stTabs"] {{
    background: #ffffff !important;
    border-radius: 14px;
    padding: 8px 4px 0 4px !important;
    box-shadow: 0 2px 12px rgba(30,80,50,0.07);
    border: 1px solid {_GREEN_LIGHT};
    overflow: visible !important;
    min-height: auto !important;
  }}
  [data-testid="stTabs"] > div {{
    overflow: visible !important;
  }}
  [data-testid="stTabsTabList"] {{
    background: transparent !important;
    border-bottom: 1px solid {_GREEN_LIGHT} !important;
    overflow: visible !important;
  }}
  [data-testid="stTabsTabLabel"] {{ color: {_GREEN} !important; font-weight:600; }}
  [data-baseweb="tab"][aria-selected="true"] {{
    border-bottom: 3px solid {_GREEN} !important;
  }}
  [data-testid="stTabContent"] {{
    background: #ffffff !important;
    border-radius: 0 0 14px 14px;
    padding: 20px !important;
    overflow: visible !important;
  }}

  /* Main content inputs (Personal Profile, Doctor Review) — light bg, dark text */
  [data-testid="stTabContent"] input,
  [data-testid="stTabContent"] textarea,
  [data-testid="stTabContent"] [data-baseweb="input"] input,
  [data-testid="stTabContent"] [data-baseweb="textarea"] textarea,
  [data-testid="stMainBlockContainer"] input,
  [data-testid="stMainBlockContainer"] textarea {{
    background: #ffffff !important;
    color: #1a1a1a !important;
    border: 1px solid {_GREEN_LIGHT} !important;
  }}
  [data-testid="stTabContent"] input::placeholder,
  [data-testid="stTabContent"] textarea::placeholder {{
    color: #6b7b6b !important;
  }}
  div[data-baseweb="select"] > div,
  div[data-baseweb="multiselect"] > div,
  [data-testid="stTabContent"] [data-baseweb="select"] > div,
  [data-testid="stTabContent"] [data-baseweb="multiselect"] > div {{
    background: #ffffff !important;
    color: #1a1a1a !important;
    border: 1px solid {_GREEN_LIGHT} !important;
  }}
  div[data-baseweb="select"] span,
  div[data-baseweb="select"] div,
  div[data-baseweb="multiselect"] span,
  div[data-baseweb="multiselect"] div,
  [data-testid="stTabContent"] [data-baseweb="select"] span,
  [data-testid="stTabContent"] [data-baseweb="select"] div,
  [data-testid="stTabContent"] [data-baseweb="multiselect"] span,
  [data-testid="stTabContent"] [data-baseweb="multiselect"] div {{
    color: #1a1a1a !important;
  }}

  /* Generate button */
  [data-testid="stBaseButton-primary"] {{
    background: linear-gradient(135deg, {_GREEN}, {_GREEN_DARK}) !important;
    border: none !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px;
    box-shadow: 0 3px 10px rgba(14,61,34,0.25) !important;
  }}
  [data-testid="stBaseButton-primary"]:hover {{
    background: {_GREEN_DARK} !important;
    box-shadow: 0 4px 14px rgba(14,61,34,0.35) !important;
  }}

  /* Secondary/default buttons (e.g. quick questions) — light bg, dark text */
  button[data-testid="stBaseButton-secondary"],
  [data-testid="stBaseButton-secondary"] {{
    background: #ffffff !important;
    color: #1a3d2a !important;
    border: 1px solid {_GREEN_LIGHT} !important;
  }}
  button[data-testid="stBaseButton-secondary"]:hover,
  [data-testid="stBaseButton-secondary"]:hover {{
    background: {_GREEN_LIGHT} !important;
    color: #1a3d2a !important;
    border-color: {_GREEN} !important;
  }}
  /* Fallback: buttons in tab content (e.g. quick questions) that aren't primary */
  [data-testid="stTabContent"] button:not([data-testid="stBaseButton-primary"]) {{
    background: #ffffff !important;
    color: #1a3d2a !important;
    border: 1px solid {_GREEN_LIGHT} !important;
  }}
  [data-testid="stTabContent"] button:not([data-testid="stBaseButton-primary"]):hover {{
    background: {_GREEN_LIGHT} !important;
    color: #1a3d2a !important;
  }}

  /* ══ SIDEBAR — ensure visible, never hidden ═══════════════════════════ */
  [data-testid="stSidebar"],
  section[data-testid="stSidebar"],
  [data-testid="stSidebar"] > div {{
    display: block !important;
    visibility: visible !important;
  }}
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {_GREEN_DEEP} 0%, {_GREEN_PANEL} 100%) !important;
    border-right: none !important;
    min-width: 180px !important;
    max-width: 240px !important;
  }}

  /* All sidebar text → light */
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] div,
  [data-testid="stSidebar"] small,
  [data-testid="stSidebar"] .stCaption {{ color: {_SIDEBAR_TEXT} !important; }}

  /* Sidebar section headers */
  .sidebar-header {{
    font-size:0.72rem; font-weight:700; text-transform:uppercase;
    letter-spacing:1.3px; margin:18px 0 6px 0;
    color: {_SIDEBAR_HEAD} !important;
  }}

  /* Sidebar inputs — white bg, dark readable text */
  [data-testid="stSidebar"] input,
  [data-testid="stSidebar"] select,
  [data-testid="stSidebar"] textarea {{
    background: rgba(255,255,255,0.93) !important;
    color: #1a3d2a !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 6px !important;
  }}
  [data-testid="stSidebar"] input::placeholder {{ color: #7aaa8a !important; }}

  /* Sidebar selectbox */
  [data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background: rgba(255,255,255,0.93) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
  }}
  [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] [data-baseweb="select"] span,
  [data-testid="stSidebar"] [data-baseweb="select"] div {{
    color: #1a3d2a !important;
  }}

  /* Sidebar toggle label */
  [data-testid="stSidebar"] [data-testid="stToggle"] label {{
    color: {_SIDEBAR_TEXT} !important;
    font-weight: 600;
  }}

  /* Sidebar number input +/- buttons */
  [data-testid="stSidebar"] button:not([data-testid="stBaseButton-primary"]) {{
    background: rgba(255,255,255,0.15) !important;
    color: #fff !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
  }}

  /* Sidebar divider */
  [data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.15) !important;
  }}

  /* ══ Protocol Library — wider tabs and export box ═══════════════════ */
  [data-testid="stTabs"] [data-baseweb="tab-list"] button {{
    padding: 10px 22px !important;
    min-width: 160px !important;
    font-size: 0.95rem !important;
  }}
  [data-testid="stExpander"] details summary {{
    padding: 14px 18px !important;
    font-size: 1.02rem !important;
  }}
  [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    padding: 20px 24px 24px 24px !important;
  }}

  /* Logo area */
  .ayun-logo-wrap {{
    padding: 14px 0 12px 0;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 10px;
  }}

  /* File uploader */
  [data-testid="stFileUploader"] {{
    background: rgba(255,255,255,0.08);
    border: 2px dashed rgba(127,204,160,0.6);
    border-radius: 10px;
    padding: 4px;
  }}
  [data-testid="stFileUploaderDropzone"] {{
    background: transparent !important;
    border: none !important;
    padding: 10px 8px !important;
  }}
  [data-testid="stFileUploaderDropzoneInstructions"] > div > span {{
    color: {_SIDEBAR_HEAD} !important;
    font-weight: 700 !important;
  }}
  [data-testid="stFileUploaderDropzoneInstructions"] > div > small {{
    color: {_SIDEBAR_TEXT} !important;
  }}
  [data-testid="stFileUploader"] button {{
    background: {_GREEN} !important;
    color: #fff !important;
    border: none !important;
  }}

  /* ══ RECOMMENDATION CARDS ════════════════════════════════════════ */
  .rule-card {{
    background: #ffffff;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(20,60,35,0.08);
  }}
  .rule-card strong {{ color: #111 !important; }}
  .rule-card-Critical {{ border-left: 5px solid #c0392b; }}
  .rule-card-High     {{ border-left: 5px solid #d35400; }}
  .rule-card-Medium   {{ border-left: 5px solid {_GREEN}; }}
  .rule-card-Low      {{ border-left: 5px solid {_GREEN_MID}; }}

  /* ══ BADGES — outline style, no solid background, single line ═════════ */
  .badge {{ border-radius:6px; padding:2px 10px;
            font-size:0.78rem; font-weight:700; white-space: nowrap;
            background: transparent !important; border: 1.5px solid;
            display: inline-block; margin-right: 12px; flex-shrink: 0; }}
  .badge-Critical {{ color:#c0392b !important; border-color:#c0392b !important; }}
  .badge-High     {{ color:#d35400 !important; border-color:#d35400 !important; }}
  .badge-Medium   {{ color:{_GREEN} !important; border-color:{_GREEN} !important; }}
  .badge-Low      {{ color:{_GREEN_MID} !important; border-color:{_GREEN_MID} !important; }}

  /* ══ RATING BARS ═════════════════════════════════════════════════ */
  .rating-bar-wrap {{ background:#d8ece0; border-radius:20px;
                      height:10px; overflow:hidden; }}
  .rating-bar      {{ height:10px; border-radius:20px; }}

  /* ══ EXPANDER (e.g. "Try unmeasured parameters") — light bg, dark text ═══ */
  [data-testid="stExpander"] {{
    background: #ffffff !important;
    border: 1px solid {_GREEN_LIGHT} !important;
    border-radius: 8px !important;
  }}
  .streamlit-expanderHeader,
  .streamlit-expanderHeader p,
  [data-testid="stExpander"] > details > summary,
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] summary p,
  [data-testid="stExpander"] [data-baseweb="accordion"] summary,
  [data-testid="stExpander"] [data-baseweb="accordion"] > div:first-child,
  [data-testid="stExpander"] > div > div:first-child,
  [data-testid="stExpander"] button[aria-expanded],
  [data-testid="stExpander"] [role="button"] {{
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #1a1a1a !important;
    border: none !important;
  }}
  .streamlit-expanderHeader,
  [data-testid="stExpander"] > details > summary,
  [data-testid="stExpander"] summary {{
    border-bottom: 1px solid {_GREEN_LIGHT} !important;
  }}
  .streamlit-expanderContent,
  [data-testid="stExpander"] [data-testid="stExpanderDetails"],
  [data-testid="stExpander"] [data-baseweb="accordion"] {{
    background: #ffffff !important;
    color: #1a1a1a !important;
  }}

  /* ══ CHAT ════════════════════════════════════════════════════════ */
  [data-testid="stChatMessage"] p {{ color: #1a1a1a !important; }}
  /* Chat input bar — light green (was dark/black) — hex values for reliability */
  .stChatFloatingInputContainer,
  .stChatInputContainer,
  .stChatInputContainer > div,
  .stChatFloatingInputContainer > div,
  [data-testid="stChatInput"],
  div[data-testid="stChatInput"],
  form[data-testid="stChatInput"],
  section[data-testid="stChatInput"] {{
    background: #dff0e6 !important;
    background-color: #dff0e6 !important;
    border: 1px solid #52a872 !important;
    border-color: #52a872 !important;
    outline: none !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(46,125,82,0.12) !important;
  }}
  [data-testid="stChatInput"] {{
    color: #1a1a1a !important;
    caret-color: #1a1a1a !important;
  }}
  [data-testid="stChatInput"] input,
  [data-testid="stChatInput"] textarea,
  [data-testid="stChatInput"] [data-baseweb="input"],
  [data-testid="stChatInput"] [data-baseweb="textarea"],
  [data-testid="stChatInput"] [data-baseweb="input"] input,
  [data-testid="stChatInput"] [data-baseweb="textarea"] textarea,
  div[data-testid="stChatInput"] input,
  div[data-testid="stChatInput"] textarea,
  .stChatInputContainer input,
  .stChatInputContainer textarea,
  .stChatFloatingInputContainer input,
  .stChatFloatingInputContainer textarea {{
    background: #ffffff !important;
    color: #1a1a1a !important;
    caret-color: #1a1a1a !important;
  }}
  [data-testid="stChatInput"] input::placeholder,
  [data-testid="stChatInput"] textarea::placeholder,
  div[data-testid="stChatInput"] input::placeholder,
  div[data-testid="stChatInput"] textarea::placeholder,
  .stChatInputContainer input::placeholder,
  .stChatInputContainer textarea::placeholder,
  .stChatFloatingInputContainer input::placeholder,
  .stChatFloatingInputContainer textarea::placeholder {{
    color: #6b7b6b !important;
  }}
  /* Chat send button — keep visible on light background */
  .stChatInputContainer button,
  .stChatFloatingInputContainer button,
  [data-testid="stChatInput"] button {{
    background: {_GREEN} !important;
    color: #ffffff !important;
    border: none !important;
  }}

  /* ══ PERSONAL PROFILE TAB ═══════════════════════════════════════ */
  .profile-section {{
    background: #ffffff;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    border: 1px solid {_GREEN_LIGHT};
    box-shadow: 0 2px 8px rgba(20,60,35,0.06);
  }}
  .profile-section-title {{
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: {_GREEN};
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid {_GREEN_LIGHT};
  }}
  .profile-saved-badge {{
    background: {_GREEN_LIGHT};
    color: {_GREEN_DARK};
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.82rem;
    font-weight: 600;
    display: inline-block;
  }}

  /* ══ DOCTOR REVIEW TAB ══════════════════════════════════════════ */
  .doctor-card {{
    background: #ffffff;
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 16px;
    border: 1px solid {_GREEN_LIGHT};
    box-shadow: 0 2px 8px rgba(20,60,35,0.06);
    overflow: visible !important;
    max-width: 100%;
  }}
  .doctor-card-Critical {{ border-left: 5px solid #c0392b; }}
  .doctor-card-High     {{ border-left: 5px solid #d35400; }}
  .doctor-card-Medium   {{ border-left: 5px solid {_GREEN}; }}
  .doctor-card-Low      {{ border-left: 5px solid {_GREEN_MID}; }}
  .doctor-signoff-box {{
    background: {_GREEN_LIGHT};
    border-radius: 12px;
    padding: 20px 24px;
    margin-top: 24px;
    border: 1px solid #b8dfc8;
  }}

  /* ══ ROLE MODE BANNER ═══════════════════════════════════════════ */
  .role-banner {{
    border-radius: 10px;
    padding: 10px 16px;
    margin: 0 0 12px 0;
    font-size: 0.92rem;
    font-weight: 600;
  }}
  .role-banner-expert {{
    background: #e8f4ec;
    border: 1px solid {_GREEN};
    color: {_GREEN_DARK};
  }}
  .role-banner-member {{
    background: #f0f7ff;
    border: 1px solid #90caf9;
    color: #1565c0;
  }}

  /* ══ AYUN WEBSITE-STYLE NAVBAR ═══════════════════════════════════════════ */
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) {{
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 1px 8px rgba(48,99,100,0.08);
    padding: 10px 20px 10px 22px !important;
    margin-bottom: 16px !important;
    border: 1px solid rgba(48,99,100,0.08);
    gap: 0 !important;
    align-items: center !important;
    min-height: 56px;
  }}
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) > [data-testid="stColumn"] {{
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 !important;
    gap: 0 !important;
  }}
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) > [data-testid="stColumn"]:first-child {{
    justify-content: flex-start;
  }}
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) > [data-testid="stColumn"]:last-child {{
    justify-content: flex-end;
  }}
  .ayun-nav-brand {{
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    gap: 14px;
    width: 100%;
  }}
  .ayun-nav-logo {{
    flex-shrink: 0;
    display: block;
  }}
  .ayun-nav-lockup {{
    display: flex;
    flex-direction: row;
    align-items: center;
  }}
  .sidebar-brand-lockup {{
    margin-bottom: 4px;
  }}
  .brand-title-row {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .joule-mark-img {{
    flex-shrink: 0;
    display: block;
  }}
  .brand-for {{
    font-family: Arial, sans-serif;
    font-size: 0.62rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #5a6356;
    line-height: 1;
  }}
  .sidebar-brand-for {{
    font-family: Arial, sans-serif;
    font-size: 0.58rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: {_SIDEBAR_HEAD};
    line-height: 1;
    margin: 0;
  }}
  .sidebar-brand-sub {{
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {_SIDEBAR_HEAD};
    font-weight: 600;
    margin: 6px 0 0 0;
  }}
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) button {{
    background: transparent !important;
    border: 1.5px solid #306364 !important;
    color: #306364 !important;
    border-radius: 50px !important;
    font-size: 0.84rem !important;
    padding: 8px 22px !important;
    white-space: nowrap !important;
    box-shadow: none !important;
  }}
  [data-testid="stHorizontalBlock"]:has(.ayun-nav-brand) button:hover {{
    background: #306364 !important;
    color: #ffffff !important;
  }}
</style>
""", unsafe_allow_html=True)

# ── Session-state defaults ─────────────────────────────────────────────────────
_DEFAULTS = {
    # Demographics (always required)
    "in_age": 35,
    "in_sex": "Male",
    # Section toggles — False = "not measured, skip"
    "sec_dexa":     False,
    "sec_strength":  False,
    "sec_lower":     False,
    "sec_cpet":      False,
    "sec_rom":       False,
    "sec_blood":     False,
    "sec_genetics":  False,
    # Values — sensible mid-range defaults, only used when section is enabled
    "in_lmi":      18.0,  "in_almi":  8.0,   "in_fat":  18.0,
    "in_vfi":      0.0,   "in_bmd":    0.0,
    "in_biceps_r": 14.0,  "in_biceps_l": 13.0,
    "in_triceps_r":11.0,  "in_triceps_l":10.0,
    "in_grip_r":   44.0,  "in_grip_l":   43.0,
    "in_cmj":      30.0,  "in_ybal":     90.0,
    "in_vo2":      0.0,   "in_hrmax": 0,
    "in_vt1":      0,     "in_vt2":   0,
    "in_shoulder_r":170.0,"in_shoulder_l":168.0,
    "in_hip_r":    130.0, "in_hip_l":    128.0,
    "in_ldl":      2.8,   "in_hba1c":    5.2,
    "in_alat":     25.0,  "in_asat":     22.0, "in_ggt": 28.0,
    "in_bone_risk":"None",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Personal Profile session state ────────────────────────────────────────────
_PROFILE_DEFAULTS = {
    "profile_name":           "",
    "profile_goals":          [],
    "profile_activity_level": "Moderately Active",
    "profile_sport_prefs":    [],
    "profile_smoking_status": "Not specified",
    "profile_alcohol_use":    "Not specified",
    "profile_sleep_hours":    "Not specified",
    "profile_diet":           "",
    "profile_stress":         "Not assessed",
    "profile_depression":     "Not assessed",
    "profile_optimism":       "Not assessed",
    "profile_injuries":       "",
    "profile_extra_notes":    "",
}
for _k, _v in _PROFILE_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Playground session state ──────────────────────────────────────────────────
if "play_result"  not in st.session_state: st.session_state.play_result  = None
if "play_data"    not in st.session_state: st.session_state.play_data    = {}

# ── Doctor Review session state ───────────────────────────────────────────────
if "doctor_name"        not in st.session_state: st.session_state.doctor_name        = ""
if "doctor_edits"       not in st.session_state: st.session_state.doctor_edits       = {}
if "doctor_signed"      not in st.session_state: st.session_state.doctor_signed      = False
if "doctor_removed"     not in st.session_state: st.session_state.doctor_removed     = set()
if "doctor_custom_recs" not in st.session_state: st.session_state.doctor_custom_recs = []
if "user_role"          not in st.session_state: st.session_state.user_role          = "patient"
if "viewer_name"        not in st.session_state: st.session_state.viewer_name        = ""
if "knowledge_saved"    not in st.session_state: st.session_state.knowledge_saved    = False
if "assessment_id"      not in st.session_state: st.session_state.assessment_id      = None
if "member_pseudonym"   not in st.session_state: st.session_state.member_pseudonym   = ""
if "expert_authenticated" not in st.session_state: st.session_state.expert_authenticated = False
if "show_expert_login" not in st.session_state: st.session_state.show_expert_login = False


def _is_expert_mode() -> bool:
    return (
        st.session_state.get("user_role", "patient") == "doctor"
        and st.session_state.get("expert_authenticated", False)
    )


def _build_personal_context() -> str:
    """Build a text block from the Personal Profile tab for the LLM context."""
    parts = []
    name = st.session_state.get("profile_name", "").strip()
    if name:
        parts.append(f"Member name: {name}")
    geo = st.session_state.get("profile_geographic_area", "")
    geo_detail = st.session_state.get("profile_location_detail", "").strip()
    if geo and geo != "Not specified":
        location = f"{geo} ({geo_detail})" if geo_detail else geo
        parts.append(f"Geographic area: {location}")
    elif geo_detail:
        parts.append(f"Geographic area: {geo_detail}")
    health = st.session_state.get("profile_health_status", "")
    if health and health != "Not specified":
        parts.append(f"General health status: {health}")
    conditions = st.session_state.get("profile_existing_conditions", "").strip()
    if conditions:
        parts.append(f"Existing conditions / diagnoses: {conditions}")
    smoking = st.session_state.get("profile_smoking_status", "")
    if smoking and smoking != "Not specified":
        parts.append(f"Smoking status: {smoking}")
    alcohol = st.session_state.get("profile_alcohol_use", "")
    if alcohol and alcohol != "Not specified":
        parts.append(f"Alcohol use: {alcohol}")
    sleep = st.session_state.get("profile_sleep_hours", "")
    if sleep and sleep != "Not specified":
        parts.append(f"Typical sleep: {sleep}")
    diet = st.session_state.get("profile_diet", "").strip()
    if diet:
        parts.append(f"Diet / dietary notes: {diet}")
    goals = st.session_state.get("profile_goals", [])
    if goals:
        parts.append(f"Health goals: {', '.join(goals)}")
    activity = st.session_state.get("profile_activity_level", "")
    if activity and activity != "Not specified":
        parts.append(f"Current activity level: {activity}")
    prefs = st.session_state.get("profile_sport_prefs", [])
    if prefs:
        parts.append(f"Preferred activities: {', '.join(prefs)}")
    stress = st.session_state.get("profile_stress", "")
    if stress and stress != "Not assessed":
        parts.append(f"Stress level: {stress}")
    depression = st.session_state.get("profile_depression", "")
    if depression and depression != "Not assessed":
        parts.append(f"Depression level: {depression}")
    optimism = st.session_state.get("profile_optimism", "")
    if optimism and optimism != "Not assessed":
        parts.append(f"Optimism level: {optimism}")
    injuries = st.session_state.get("profile_injuries", "").strip()
    if injuries:
        parts.append(f"Injuries / limitations: {injuries}")
    notes = st.session_state.get("profile_extra_notes", "").strip()
    if notes:
        parts.append(f"Additional notes: {notes}")
    return "\n".join(parts)


def _build_personal_profile() -> dict:
    """Structured personal profile for database persistence."""
    return {
        "name": st.session_state.get("profile_name", "").strip(),
        "goals": st.session_state.get("profile_goals", []),
        "activity_level": st.session_state.get("profile_activity_level", ""),
        "sport_prefs": st.session_state.get("profile_sport_prefs", []),
        "geographic_area": st.session_state.get("profile_geographic_area", ""),
        "location_detail": st.session_state.get("profile_location_detail", "").strip(),
        "health_status": st.session_state.get("profile_health_status", ""),
        "existing_conditions": st.session_state.get("profile_existing_conditions", "").strip(),
        "smoking_status": st.session_state.get("profile_smoking_status", ""),
        "alcohol_use": st.session_state.get("profile_alcohol_use", ""),
        "sleep_hours": st.session_state.get("profile_sleep_hours", ""),
        "diet": st.session_state.get("profile_diet", "").strip(),
        "stress": st.session_state.get("profile_stress", ""),
        "depression": st.session_state.get("profile_depression", ""),
        "optimism": st.session_state.get("profile_optimism", ""),
        "injuries": st.session_state.get("profile_injuries", "").strip(),
        "notes": st.session_state.get("profile_extra_notes", "").strip(),
    }

if "result" not in st.session_state:
    st.session_state.result = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "_processed_ids" not in st.session_state:
    st.session_state._processed_ids = set()
if "_file_summaries" not in st.session_state:
    st.session_state._file_summaries = []   # list of (name, fields_count)
if "_extracted_vals" not in st.session_state:
    st.session_state._extracted_vals = {}   # key → value, from extraction only
if "_auto_generate" not in st.session_state:
    st.session_state._auto_generate = False

# Reset: must run before any widgets; triggered by Reset button in header
if st.session_state.pop("_pending_reset", False):
    for _k in list(st.session_state.keys()):
        if _k.startswith("play_"):
            del st.session_state[_k]
    st.session_state.result = None
    st.session_state.chat_history = []
    st.session_state._processed_ids = set()
    st.session_state._file_summaries = []
    st.session_state._extracted_vals = {}
    st.session_state._auto_generate = False
    st.session_state.doctor_edits = {}
    st.session_state.doctor_signed = False
    st.session_state.knowledge_saved = False
    st.session_state.doctor_removed = set()
    st.session_state.doctor_custom_recs = []
    st.session_state.doctor_name = ""
    st.session_state.knowledge_saved = False
    st.session_state.expert_authenticated = False
    st.session_state.show_expert_login = False
    st.session_state.user_role = "patient"
    st.session_state.play_result = None
    st.session_state.play_data = {}
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    for _k, _v in _PROFILE_DEFAULTS.items():
        st.session_state[_k] = _v
    st.rerun()

# Apply pending viewer name before sidebar widget (avoids StreamlitAPIException)
_pending_name = st.session_state.pop("_pending_viewer_name", None)
if _pending_name is not None:
    st.session_state.viewer_name = _pending_name

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="ayun-logo-wrap">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sidebar-brand-lockup">'
        f'<div class="brand-title-row">'
        f'{_joule_mark_html(size=32)}'
        f'<p class="sidebar-brand-for">for</p>'
        f'{_logo_img_html(_LOGO_PATH, height=26)}'
        f'</div>'
        f'<p class="sidebar-brand-sub">Sport Plan</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Role switcher + expert password gate ───────────────────────────────────
    st.markdown('<div class="sidebar-header">👤 Who is using the app?</div>',
                unsafe_allow_html=True)
    _role = st.session_state.get("user_role", "patient")
    _expert_ok = st.session_state.get("expert_authenticated", False)
    _rb1, _rb2 = st.columns(2)
    with _rb1:
        if st.button(
            "👤 Member",
            use_container_width=True,
            type="primary" if _role == "patient" and not _expert_ok else "secondary",
            key="role_btn_member",
        ):
            st.session_state.user_role = "patient"
            st.session_state.show_expert_login = False
            st.rerun()
    with _rb2:
        if st.button(
            "🩺 Expert",
            use_container_width=True,
            type="primary" if _is_expert_mode() else "secondary",
            key="role_btn_expert",
        ):
            if _expert_ok:
                st.session_state.user_role = "doctor"
                st.session_state.show_expert_login = False
            else:
                st.session_state.show_expert_login = True
            st.rerun()

    if st.session_state.get("show_expert_login") and not _expert_ok:
        st.caption("Enter your expert password below ↓")

    if _is_expert_mode():
        st.markdown(
            '<div style="background:#2e7d52;color:#fff;padding:8px 10px;border-radius:8px;'
            'text-align:center;font-weight:700;font-size:0.85rem;margin:6px 0;">'
            '🩺 EXPERT MODE ACTIVE</div>',
            unsafe_allow_html=True,
        )
        st.caption("Protocols · inbox · sign-off · knowledge")
        if st.button("Lock expert mode", key="expert_lock_btn", use_container_width=True):
            st.session_state.expert_authenticated = False
            st.session_state.user_role = "patient"
            st.session_state.show_expert_login = False
            st.rerun()
    elif st.session_state.get("show_expert_login"):
        st.markdown(
            '<div style="background:#e67e22;color:#fff;padding:8px 10px;border-radius:8px;'
            'text-align:center;font-weight:700;font-size:0.85rem;margin:6px 0;">'
            '🔒 EXPERT LOGIN REQUIRED</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#1565c0;color:#fff;padding:8px 10px;border-radius:8px;'
            'text-align:center;font-weight:700;font-size:0.85rem;margin:6px 0;">'
            '👤 MEMBER MODE ACTIVE</div>',
            unsafe_allow_html=True,
        )
        st.caption("Ask experts · AI assistant · view plan")
    _role_placeholder = "Your name (optional)" if not _is_expert_mode() else "Clinician name (recommended)"
    st.text_input(
        "Display name",
        placeholder=_role_placeholder,
        key="viewer_name",
    )
    st.text_input(
        "Research pseudonym (optional)",
        placeholder="Links visits to AYUN archive token",
        help="If set, assessments are linked to the same member row in Supabase.",
        key="member_pseudonym",
    )
    try:
        from backend.storage import ayun_db
        _db_label = ayun_db.backend_label()
        if _db_label == "supabase":
            st.caption("Database: Supabase connected")
        else:
            st.caption("Database: local JSON (set SUPABASE_* in .env for Postgres)")
    except Exception:
        pass

    # ── File Upload (multiple files) ──────────────────────────────────────────
    st.markdown('<div class="sidebar-header">📄 Load Member Reports</div>',
                unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "📄 Drag & drop or browse — PDF, TXT, Word, JSON",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        help=f"Upload one or more files ({SUPPORTED_LABEL}). Values merge automatically.",
    )

    # Reset button — clears all loaded files & extracted values
    if st.session_state._file_summaries:
        if st.button("🗑 Clear all files", use_container_width=True):
            st.session_state._processed_ids = set()
            st.session_state._file_summaries = []
            st.session_state._extracted_vals = {}
            st.session_state.result = None
            # Reset all section toggles and extracted values to defaults
            for _k, _v in _DEFAULTS.items():
                st.session_state[_k] = _v
            st.rerun()

    if uploaded_files:
        # Use "filename|size" as a stable key — id() changes on every rerun
        def _file_key(f) -> str:
            return f"{f.name}|{f.size}"

        new_files = [f for f in uploaded_files
                     if _file_key(f) not in st.session_state._processed_ids]

        if new_files:
            any_extracted = False
            for upload in new_files:
                fmt = upload.name.rsplit(".", 1)[-1].upper() if "." in upload.name else "file"
                with st.spinner(f"Reading {upload.name} — extracting all parameters…"):
                    extracted = extract_from_bytes(upload.read(), upload.name)

                real_warnings = [w for w in extracted.warnings
                                 if not w.startswith("_llm_")]
                if real_warnings:
                    for w in real_warnings:
                        st.warning(f"{upload.name}: {w}")
                    st.session_state._processed_ids.add(_file_key(upload))
                    continue
                if not extracted.fields_found:
                    st.warning(
                        f"{upload.name}: No values could be extracted. "
                        "The file may be image-based — please enter values manually."
                    )
                    st.session_state._processed_ids.add(_file_key(upload))
                    continue

                # ── Apply extracted values to session state ────────────────
                if extracted.age is not None:
                    st.session_state["in_age"] = extracted.age
                if extracted.sex:
                    st.session_state["in_sex"] = extracted.sex

                if any(v is not None for v in [
                        extracted.lmi, extracted.almi,
                        extracted.fat_percentage, extracted.visceral_fat,
                        extracted.bmd]):
                    st.session_state["sec_dexa"] = True
                if extracted.lmi is not None:
                    st.session_state["in_lmi"] = float(extracted.lmi)
                if extracted.almi is not None:
                    st.session_state["in_almi"] = float(extracted.almi)
                if extracted.fat_percentage is not None:
                    st.session_state["in_fat"] = float(extracted.fat_percentage)
                if extracted.visceral_fat is not None:
                    st.session_state["in_vfi"] = float(extracted.visceral_fat)
                if extracted.bmd is not None:
                    st.session_state["in_bmd"] = float(extracted.bmd)

                if any(v is not None for v in [
                        extracted.grip_r, extracted.grip_l,
                        extracted.biceps_r, extracted.biceps_l,
                        extracted.triceps_r, extracted.triceps_l]):
                    st.session_state["sec_strength"] = True
                if extracted.grip_r is not None:
                    st.session_state["in_grip_r"] = float(extracted.grip_r)
                if extracted.grip_l is not None:
                    st.session_state["in_grip_l"] = float(extracted.grip_l)
                if extracted.biceps_r is not None:
                    st.session_state["in_biceps_r"] = float(extracted.biceps_r)
                if extracted.biceps_l is not None:
                    st.session_state["in_biceps_l"] = float(extracted.biceps_l)
                if extracted.triceps_r is not None:
                    st.session_state["in_triceps_r"] = float(extracted.triceps_r)
                if extracted.triceps_l is not None:
                    st.session_state["in_triceps_l"] = float(extracted.triceps_l)

                if any(v is not None for v in [extracted.cmj, extracted.y_balance]):
                    st.session_state["sec_lower"] = True
                if extracted.cmj is not None:
                    st.session_state["in_cmj"] = float(extracted.cmj)
                if extracted.y_balance is not None:
                    st.session_state["in_ybal"] = float(extracted.y_balance)

                # Only enable CPET if VO2max was actually found — HR values alone
                # can be false positives from centile tables in DEXA reports
                if extracted.vo2max is not None:
                    st.session_state["sec_cpet"] = True
                    st.session_state["in_vo2"] = float(extracted.vo2max)
                if extracted.hr_max is not None:
                    st.session_state["in_hrmax"] = int(extracted.hr_max)
                if extracted.vt1 is not None:
                    st.session_state["in_vt1"] = int(extracted.vt1)
                if extracted.vt2 is not None:
                    st.session_state["in_vt2"] = int(extracted.vt2)

                if any(v is not None for v in [
                        extracted.shoulder_r, extracted.shoulder_l,
                        extracted.hip_r, extracted.hip_l]):
                    st.session_state["sec_rom"] = True
                if extracted.shoulder_r is not None:
                    st.session_state["in_shoulder_r"] = float(extracted.shoulder_r)
                if extracted.shoulder_l is not None:
                    st.session_state["in_shoulder_l"] = float(extracted.shoulder_l)
                if extracted.hip_r is not None:
                    st.session_state["in_hip_r"] = float(extracted.hip_r)
                if extracted.hip_l is not None:
                    st.session_state["in_hip_l"] = float(extracted.hip_l)

                if any(v is not None for v in [
                        extracted.ldl, extracted.hba1c,
                        extracted.alat, extracted.asat, extracted.ggt]):
                    st.session_state["sec_blood"] = True
                if extracted.ldl is not None:
                    st.session_state["in_ldl"] = float(extracted.ldl)
                if extracted.hba1c is not None:
                    st.session_state["in_hba1c"] = float(extracted.hba1c)
                if extracted.alat is not None:
                    st.session_state["in_alat"] = float(extracted.alat)
                if extracted.asat is not None:
                    st.session_state["in_asat"] = float(extracted.asat)
                if extracted.ggt is not None:
                    st.session_state["in_ggt"] = float(extracted.ggt)

                # Record extracted field → value for the preview panel
                _ev_map = {
                    "Age": extracted.age, "Sex": extracted.sex,
                    "LMI": extracted.lmi, "ALMI": extracted.almi,
                    "Fat %": extracted.fat_percentage,
                    "Visceral Fat": extracted.visceral_fat,
                    "Bone Density T/Z-score": extracted.bmd,
                    "Biceps R": extracted.biceps_r, "Biceps L": extracted.biceps_l,
                    "Triceps R": extracted.triceps_r, "Triceps L": extracted.triceps_l,
                    "Grip R": extracted.grip_r, "Grip L": extracted.grip_l,
                    "CMJ": extracted.cmj, "Y-Balance": extracted.y_balance,
                    "VO2max": extracted.vo2max, "HR max": extracted.hr_max,
                    "VT1": extracted.vt1, "VT2": extracted.vt2,
                    "Shoulder R": extracted.shoulder_r, "Shoulder L": extracted.shoulder_l,
                    "Hip R": extracted.hip_r, "Hip L": extracted.hip_l,
                    "LDL": extracted.ldl, "HbA1c": extracted.hba1c,
                    "ALAT": extracted.alat, "ASAT": extracted.asat,
                    "GGT": extracted.ggt,
                }
                for lbl, val in _ev_map.items():
                    if val is not None and val != "":
                        st.session_state._extracted_vals[lbl] = val

                st.session_state._processed_ids.add(_file_key(upload))
                if not any(s[0] == upload.name for s in st.session_state._file_summaries):
                    st.session_state._file_summaries.append(
                        (upload.name, len(extracted.fields_found))
                    )
                any_extracted = True

            if any_extracted:
                st.session_state._auto_generate = True
                st.rerun()

    # Show per-file extraction summary + what was filled
    for fname, fcount in st.session_state._file_summaries:
        fmt = fname.rsplit(".", 1)[-1].upper() if "." in fname else "FILE"
        st.success(f"✅ **{fname}** ({fmt}) — {fcount} fields extracted")

    # Show exactly what was extracted (not defaults) so user can verify
    if st.session_state._extracted_vals:
        with st.expander(
            f"📋 {len(st.session_state._extracted_vals)} values auto-filled — tap to verify",
            expanded=True,
        ):
            for lbl, val in st.session_state._extracted_vals.items():
                if isinstance(val, float):
                    st.markdown(f"• **{lbl}**: {val:.2f}".rstrip("0").rstrip("."))
                else:
                    st.markdown(f"• **{lbl}**: {val}")

    # ── Manual inputs ─────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-header">Demographics</div>', unsafe_allow_html=True)
    age = st.number_input("Age", min_value=18, max_value=99, step=1, key="in_age")
    sex = st.selectbox("Sex", ["Male", "Female"],
                       index=0 if st.session_state["in_sex"] == "Male" else 1)

    st.divider()
    st.caption(
        "📂 Upload all available reports above (DEXA, blood work, fitness test) "
        "— each file fills its own sections automatically. "
        "Toggle any remaining sections manually if needed."
    )

    # ── Body Composition (DEXA) ───────────────────────────────────────────────
    has_dexa = st.toggle("Body Composition (DEXA)", key="sec_dexa")
    if has_dexa:
        lmi  = st.number_input("Muscle Mass Index – LMI (kg/m²)", 0.0, 40.0, step=0.1,
                                format="%.1f", key="in_lmi")
        almi = st.number_input("ALMI (kg/m²)", 0.0, 15.0, step=0.1,
                                format="%.1f", key="in_almi")
        fat  = st.number_input("Body Fat (%)", 0.0, 60.0, step=0.1,
                                format="%.1f", key="in_fat")
        vfi  = st.number_input("Visceral Fat Volume (cm³)", 0.0, 20000.0, step=0.1,
                                format="%.1f", key="in_vfi")
        bmd  = st.number_input("Bone Density T/Z-score", -4.0, 4.0, step=0.1,
                                format="%.1f", key="in_bmd")
    else:
        lmi = almi = fat = vfi = bmd = None

    # ── Upper Body Strength ───────────────────────────────────────────────────
    has_strength = st.toggle("Upper Body Strength", key="sec_strength")
    if has_strength:
        biceps_r  = st.number_input("Biceps Strength Right (kg)",  0.0, 60.0, step=0.5,
                                     format="%.1f", key="in_biceps_r")
        biceps_l  = st.number_input("Biceps Strength Left (kg)",   0.0, 60.0, step=0.5,
                                     format="%.1f", key="in_biceps_l")
        triceps_r = st.number_input("Triceps Strength Right (kg)", 0.0, 60.0, step=0.5,
                                     format="%.1f", key="in_triceps_r")
        triceps_l = st.number_input("Triceps Strength Left (kg)",  0.0, 60.0, step=0.5,
                                     format="%.1f", key="in_triceps_l")
        grip_r    = st.number_input("Handgrip Right (kg)", 0.0, 100.0, step=0.5,
                                     format="%.1f", key="in_grip_r")
        grip_l    = st.number_input("Handgrip Left (kg)",  0.0, 100.0, step=0.5,
                                     format="%.1f", key="in_grip_l")
    else:
        biceps_r = biceps_l = triceps_r = triceps_l = grip_r = grip_l = None

    # ── Lower Body & Stability ────────────────────────────────────────────────
    has_lower = st.toggle("Lower Body & Stability", key="sec_lower")
    if has_lower:
        cmj  = st.number_input("Counter Movement Jump (cm)", 0.0, 80.0, step=0.5,
                                format="%.1f", key="in_cmj")
        ybal = st.number_input("Y-Balance Composite Score (%)", 0.0, 130.0, step=0.1,
                                format="%.1f", key="in_ybal")
    else:
        cmj = ybal = None

    # ── VO2max & CPET ─────────────────────────────────────────────────────────
    has_cpet = st.toggle("VO2max & CPET", key="sec_cpet")
    if has_cpet:
        vo2max = st.number_input("VO2max (ml/min/kg)", 0.0, 90.0, step=0.5,
                                  format="%.1f", key="in_vo2")
        hr_max = st.number_input("HR max (bpm)", 0, 220, step=1, key="in_hrmax")
        vt1    = st.number_input("HR at VT1 (bpm)", 0, 220, step=1, key="in_vt1")
        vt2    = st.number_input("HR at VT2 (bpm)", 0, 220, step=1, key="in_vt2")
    else:
        vo2max = hr_max = vt1 = vt2 = None

    # ── Range of Motion ───────────────────────────────────────────────────────
    has_rom = st.toggle("Range of Motion", key="sec_rom")
    if has_rom:
        shoulder_r = st.number_input("Shoulder Flexion Right (°)", 0.0, 200.0, step=1.0,
                                      format="%.0f", key="in_shoulder_r")
        shoulder_l = st.number_input("Shoulder Flexion Left (°)",  0.0, 200.0, step=1.0,
                                      format="%.0f", key="in_shoulder_l")
        hip_r      = st.number_input("Hip Flexion Right (°)", 0.0, 160.0, step=1.0,
                                      format="%.0f", key="in_hip_r")
        hip_l      = st.number_input("Hip Flexion Left (°)",  0.0, 160.0, step=1.0,
                                      format="%.0f", key="in_hip_l")
    else:
        shoulder_r = shoulder_l = hip_r = hip_l = None

    # ── Blood Biomarkers ──────────────────────────────────────────────────────
    has_blood = st.toggle("Blood Biomarkers", key="sec_blood")
    if has_blood:
        ldl   = st.number_input("LDL Cholesterol (mmol/L)", 0.0, 15.0, step=0.1,
                                  format="%.1f", key="in_ldl")
        hba1c = st.number_input("HbA1c (%)",                0.0, 15.0, step=0.1,
                                  format="%.1f", key="in_hba1c")
        alat  = st.number_input("ALAT / ALT (U/L)",         0.0, 500.0, step=1.0,
                                  format="%.0f", key="in_alat")
        asat  = st.number_input("ASAT / AST (U/L)",         0.0, 500.0, step=1.0,
                                  format="%.0f", key="in_asat")
        ggt   = st.number_input("GGT (U/L)",                0.0, 500.0, step=1.0,
                                  format="%.0f", key="in_ggt")
    else:
        ldl = hba1c = alat = asat = ggt = None

    # ── Genetics ──────────────────────────────────────────────────────────────
    has_genetics = st.toggle("Genetic Testing", key="sec_genetics")
    if has_genetics:
        bone_risk = st.selectbox(
            "Bone Health Genetic Risk",
            ["None", "Low", "Moderate", "High"],
            index=["None", "Low", "Moderate", "High"].index(
                st.session_state.get("in_bone_risk", "None")
            ),
            help="Predisposition to bone mass loss from genetic testing",
        )
    else:
        bone_risk = None

    run_btn = st.button("▶  Generate Recommendations", type="primary",
                        use_container_width=True)

# Auto-generate after a file upload (flag set during rerun cycle)
if st.session_state._auto_generate:
    st.session_state._auto_generate = False
    run_btn = True


# ── Assemble member dict ──────────────────────────────────────────────────────
# Values from disabled sections are already None (set in the sidebar else-branches).
member_data: dict = {
    # Demographics — always required
    "Demographic::Age":   age,
    "Demographic::Sex":   sex,
    # Body composition
    "Body Composition::Muscle Mass Index (LMI)":                   lmi,
    "Body Composition::ALMI":                                       almi,
    "Body Composition::Fat percentage":                             fat,
    "Body Composition::Visceral Fat Index (raw value from DEXA)":  vfi,
    "Body Composition::Bone mineral density":                       bmd,
    # Upper body strength
    "Physiological::Biceps Strength Rechts":                        biceps_r,
    "Physiological::Biceps Strength Links":                         biceps_l,
    "Physiological::Triceps Strength Rechts":                       triceps_r,
    "Physiological::Triceps Strength Links":                        triceps_l,
    "Physiological::Gripstrength Rechts":                           grip_r,
    "Physiological::Gripstrength Links":                            grip_l,
    # Lower body & stability
    "Physiological::Counter movement jump":                         cmj,
    "Physiological::Y-Balance Composite Score":                     ybal,
    # VO2max & CPET
    "Physiological::Vo2Max":                                        vo2max,
    "Physiological::HR max":                                        hr_max,
    "Physiological::HR at VT1":                                     vt1,
    "Physiological::HR at VT2":                                     vt2,
    # Range of motion
    "Physiological::Shoulder Flexion Right":                        shoulder_r,
    "Physiological::Shoulder Flexion Left":                         shoulder_l,
    "Physiological::Hip Flexion Right":                             hip_r,
    "Physiological::Hip Flexion Left":                              hip_l,
    # Blood biomarkers
    "Blood Biomarkers::LDL":                                        ldl,
    "Blood Biomarkers::HbA1c":                                      hba1c,
    "Blood Biomarkers::ALAT":                                       alat,
    "Blood Biomarkers::ASAT":                                       asat,
    "Blood Biomarkers::GGT":                                        ggt,
    # Genetics
    "Genetics::Bone Health Risk":   bone_risk if bone_risk and bone_risk != "None" else None,
}

if run_btn:
    with st.spinner("Evaluating health data…"):
        st.session_state.result = get_recommendations(
            member_data,
            personal_context=_build_personal_context(),
        )
    st.session_state.chat_history = []
    st.session_state.doctor_edits = {}
    st.session_state.doctor_signed = False
    st.session_state.knowledge_saved = False
    st.session_state.doctor_removed = set()
    st.session_state.doctor_custom_recs = []
    st.session_state.assessment_id = None
    try:
        from backend.storage import ayun_db
        if ayun_db.is_configured() and st.session_state.result:
            st.session_state.assessment_id = ayun_db.persist_assessment(
                member_data,
                st.session_state.result,
                personal_profile=_build_personal_profile(),
                pseudonym=st.session_state.get("member_pseudonym", ""),
            )
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

_nc1, _nc2 = st.columns([11, 2], gap="small")
with _nc1:
    st.markdown(
        f'<div class="ayun-nav-brand">'
        f'<div class="ayun-nav-lockup">'
        f'<div class="brand-title-row">'
        f'{_joule_mark_html(size=36)}'
        f'<span class="brand-for">for</span>'
        f'{_logo_img_html(_LOGO_COLOR_PATH, height=28)}'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with _nc2:
    if st.button("Reset session", key="btn_reset", use_container_width=True,
                 help="Start over — clear all data and recommendations"):
        st.session_state._pending_reset = True
        st.rerun()

result: RecommendationResult | None = st.session_state.result

# ── Expert login (main area — visible when Expert button clicked) ─────────────
if st.session_state.get("show_expert_login") and not st.session_state.get("expert_authenticated"):
    _lg1, _lg2, _lg3 = st.columns([1, 1.2, 1])
    with _lg2:
        st.markdown("### 🩺 Expert login")
        st.caption("Sign in with your AYUN clinician password to access protocols, sign-off, and inbox.")
        if not expert_auth.is_configured():
            st.error(
                "Expert login is not configured. Add `EXPERT_PASSWORD=...` to `.env` "
                "(local) or Railway Variables, then restart the app."
            )
        else:
            with st.form("expert_login_main", clear_on_submit=False):
                _expert_user = st.text_input(
                    "Clinician name",
                    value=st.session_state.get("viewer_name", ""),
                    placeholder="e.g. Manuel Burger",
                    key="expert_login_name",
                )
                _expert_pwd = st.text_input("Password", type="password", placeholder="Expert password")
                _lb1, _lb2 = st.columns(2)
                _do_login = _lb1.form_submit_button("Log in", type="primary", use_container_width=True)
                _do_cancel = _lb2.form_submit_button("Cancel", use_container_width=True)
            if _do_login:
                if expert_auth.verify(_expert_pwd):
                    if _expert_user.strip():
                        st.session_state._pending_viewer_name = _expert_user.strip()
                    st.session_state.expert_authenticated = True
                    st.session_state.user_role = "doctor"
                    st.session_state.show_expert_login = False
                    st.rerun()
                else:
                    st.error("Incorrect password. Please try again.")
            if _do_cancel:
                st.session_state.show_expert_login = False
                st.session_state.user_role = "patient"
                st.rerun()
    st.divider()

_is_expert = _is_expert_mode()
_role_name = (st.session_state.get("viewer_name") or "").strip()

if result is None and not _is_expert:
    st.info(
        f"👤 **Member mode**"
        + (f" — {_role_name}" if _role_name else "")
        + " · Open **Ask an Expert** to contact a clinician, **AI Assistant** for instant help"
    )
    st.info(
        "👈  **Only Age and Sex are required.** "
        "Toggle the data sections you have available in the sidebar — "
        "recommendations are generated from whatever is provided. "
        "Upload a member PDF to auto-fill values. "
        "If you don't see the sidebar, click the **>** arrow on the left edge to expand it."
    )
    st.stop()

if result is None and _is_expert:
    st.success(
        f"🩺 **Expert workspace**"
        + (f" — {_role_name}" if _role_name else "")
        + " · Answer tickets below, or load a member case in the sidebar to sign off recommendations"
    )
    _ex_inbox, _ex_signoff, _ex_protocol, _ex_knowledge = st.tabs([
        "🎫  Expert Inbox",
        "✏️  Expert Sign-off",
        "📚  Protocol Library",
        "📖  Knowledge",
    ])
    with _ex_inbox:
        render_expert_qa_tab(
            _GREEN,
            "doctor",
            st.session_state.viewer_name,
            member_snapshot={
                "age": member_data.get("Demographic::Age"),
                "sex": member_data.get("Demographic::Sex"),
            },
            chat_context="",
        )
    with _ex_signoff:
        st.subheader("✏️ Expert Sign-off")
        st.markdown(
            "Review and sign off on AI-generated recommendations **for a member case**."
        )
        st.info(
            "**Step 1** — In the sidebar, enter member demographics (and optional health data or PDF).\n\n"
            "**Step 2** — Click **Generate Recommendations**.\n\n"
            "**Step 3** — Return to this tab to edit priorities, add notes, export, and save to the knowledge base."
        )
        if st.button("I've loaded a member — generate recommendations", type="primary", key="expert_go_generate"):
            with st.spinner("Evaluating health data…"):
                st.session_state.result = get_recommendations(
                    member_data,
                    personal_context=_build_personal_context(),
                )
            st.rerun()
    with _ex_protocol:
        st.subheader("📚 Protocol Library")
        st.info(
            "Full protocol library (My protocols, All protocols, export) opens after you "
            "**generate recommendations** for a member case. Load member data in the sidebar first."
        )
    with _ex_knowledge:
        render_knowledge_library_tab(_GREEN, _GREEN_DARK, "doctor", st.session_state.viewer_name)
    st.stop()

if _is_expert:
    st.success(
        f"🩺 **Expert mode**"
        + (f" — {_role_name}" if _role_name else "")
        + " · Member case loaded — use **Expert Sign-off** to review, **Expert Inbox** for tickets"
    )
else:
    st.info(
        f"👤 **Member mode**"
        + (f" — {_role_name}" if _role_name else "")
        + " · Open **Ask an Expert** to contact a clinician, **AI Assistant** for instant help"
    )

if _is_expert:
    tab_rec, tab_profile, tab_ratings, tab_zones, tab_lib, tab_chat, tab_knowledge, tab_tickets, tab_doctor, tab_play = st.tabs([
        "📋  Recommendations",
        "👤  Personal Profile",
        "📊  Parameter Ratings",
        "❤️  Training Zones",
        "📚  Protocol Library",
        "💬  AI Assistant",
        "📖  Knowledge",
        "🎫  Expert Inbox",
        "✏️  Expert Sign-off",
        "🧪  Playground",
    ])
else:
    tab_rec, tab_profile, tab_ratings, tab_zones, tab_chat, tab_knowledge, tab_tickets, tab_play = st.tabs([
        "📋  Recommendations",
        "👤  Personal Profile",
        "📊  Parameter Ratings",
        "❤️  Training Zones",
        "💬  AI Assistant",
        "📖  Knowledge",
        "🎫  Ask an Expert",
        "🧪  Playground",
    ])
    tab_lib = None
    tab_doctor = None


# ────────────────────────────────────────────────────────────
# TAB 1 — Recommendations
# ────────────────────────────────────────────────────────────
def _fmt_age_group(raw: str) -> str:
    """Convert 'age_30_39' → 'Age 30-39'."""
    return raw.replace("age_", "Age ").replace("_", "-")

with tab_rec:
    triggered = result.triggered
    grp_label = (
        f"{result.sex_group.title()}, "
        f"{_fmt_age_group(result.age_group)}"
    )

    critical = sum(1 for r in triggered if r.priority == "Critical")
    high     = sum(1 for r in triggered if r.priority == "High")
    medium   = sum(1 for r in triggered if r.priority == "Medium")
    low      = sum(1 for r in triggered if r.priority == "Low")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Group", grp_label)
    col2.metric("🔴 Critical", critical)
    col3.metric("🟠 High", high)
    col4.metric("🔵 Medium", medium)
    col5.metric("🟢 Low", low)

    st.divider()

    if not triggered:
        st.success("✅ All measured values are within reference ranges for this age/gender group.")
    else:
        st.subheader(f"Triggered Recommendations ({len(triggered)})")
        for rec in triggered:
            p = rec.priority
            colour = PRIORITY_COLOUR.get(p, "#999")
            emoji  = PRIORITY_EMOJI.get(p, "")

            st.markdown(
                f"""
                <div class="rule-card rule-card-{p}">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                    <span class="badge badge-{p}">{emoji} {p.upper()}</span>
                    <strong style="font-size:1.05rem;color:#111;">{rec.title}</strong>
                  </div>
                  <div style="font-size:0.82rem;color:#888;margin-bottom:10px;">
                    Category: {rec.category}
                  </div>
                """,
                unsafe_allow_html=True,
            )
            for item in rec.action_items:
                st.markdown(
                    f'<p style="margin:4px 0 4px 12px;color:#333;">• {item}</p>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────
# TAB 2 — Personal Profile
# ────────────────────────────────────────────────────────────
with tab_profile:

    def _pf_row(label: str, desc: str, widget_fn, *args, **kwargs):
        """Render one profile row: description left, widget right."""
        _L, _R = st.columns([1, 1.8], gap="large")
        with _L:
            st.markdown(
                f'<p style="font-weight:600;color:{_GREEN_DARK};margin:0 0 2px 0;">'
                f'{label}</p>'
                f'<p style="font-size:0.82rem;color:#666;margin:0;">{desc}</p>',
                unsafe_allow_html=True,
            )
        with _R:
            widget_fn(*args, **kwargs)

    # Header
    st.markdown(
        f'<p style="color:#777;font-size:0.9rem;margin-bottom:18px;">'
        f'All fields are optional. Whatever you fill in is sent to the AI Sports Scientist '
        f'and included in the exported Doctor Review.</p>',
        unsafe_allow_html=True,
    )

    # ── Identity ──────────────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">👤 Identity</p>',
        unsafe_allow_html=True,
    )
    _pf_row(
        "Member Name", "Full name for the report",
        st.text_input, "", placeholder="e.g. Manuel Burger",
        key="profile_name", label_visibility="collapsed",
    )

    st.divider()

    # ── Location & Health ─────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">📍 Location & Health</p>',
        unsafe_allow_html=True,
    )
    _GEO_OPTIONS = [
        "Not specified", "Switzerland — urban", "Switzerland — rural / alpine",
        "Central Europe", "Northern Europe", "Southern Europe",
        "United Kingdom & Ireland", "North America", "Asia-Pacific", "Other",
    ]
    _pf_row(
        "Geographic Area", "Region for altitude, climate, and lifestyle context",
        st.selectbox, "", _GEO_OPTIONS,
        key="profile_geographic_area", label_visibility="collapsed",
    )
    _pf_row(
        "City / Region", "Optional detail (e.g. Zurich, Bernese Oberland)",
        st.text_input, "", placeholder="e.g. Zurich",
        key="profile_location_detail", label_visibility="collapsed",
    )
    _HEALTH_STATUS = [
        "Not specified",
        "Good health — no known conditions",
        "Generally healthy — minor issues only",
        "Managing chronic condition(s)",
        "Recovering from illness or injury",
    ]
    _pf_row(
        "General Health Status", "Overall health before lab checkup",
        st.selectbox, "", _HEALTH_STATUS,
        key="profile_health_status", label_visibility="collapsed",
    )
    _pf_row(
        "Existing Conditions",
        "Known diagnoses or chronic diseases (leave blank if none)",
        st.text_area, "",
        placeholder="e.g. Type 2 diabetes, hypertension, asthma",
        height=80, key="profile_existing_conditions", label_visibility="collapsed",
    )

    st.divider()

    # ── Lifestyle ─────────────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">🌙 Lifestyle</p>',
        unsafe_allow_html=True,
    )
    _SMOKING_OPTIONS = [
        "Not specified", "Non-smoker", "Former smoker", "Occasional smoker", "Daily smoker",
    ]
    _ALCOHOL_OPTIONS = [
        "Not specified", "None", "Occasional (social)",
        "1–3 drinks / week", "4–7 drinks / week", "More than 7 drinks / week",
    ]
    _SLEEP_OPTIONS = [
        "Not specified", "Less than 5 hours", "5–6 hours", "6–7 hours",
        "7–8 hours", "8–9 hours", "More than 9 hours",
    ]
    _pf_row(
        "Smoking Status", "Current or past tobacco use",
        st.selectbox, "", _SMOKING_OPTIONS,
        key="profile_smoking_status", label_visibility="collapsed",
    )
    _pf_row(
        "Alcohol Use", "Typical weekly alcohol intake",
        st.selectbox, "", _ALCOHOL_OPTIONS,
        key="profile_alcohol_use", label_visibility="collapsed",
    )
    _pf_row(
        "Typical Sleep", "Average hours of sleep per night",
        st.selectbox, "", _SLEEP_OPTIONS,
        key="profile_sleep_hours", label_visibility="collapsed",
    )
    _pf_row(
        "Diet / Dietary Notes",
        "Special diet, preferences, or restrictions (leave blank if none)",
        st.text_area, "",
        placeholder="e.g. Vegetarian, gluten-free, low carb, no dairy",
        height=80, key="profile_diet", label_visibility="collapsed",
    )

    st.divider()

    # ── Health Goals ──────────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">🎯 Health Goals</p>',
        unsafe_allow_html=True,
    )
    _GOAL_OPTIONS = [
        "Weight management", "Build muscle / hypertrophy",
        "Improve endurance & VO2max", "Reduce cardiovascular risk",
        "Improve bone health", "Reduce stress & mental wellbeing",
        "Improve sleep quality", "Longevity & disease prevention",
        "Improve mobility & flexibility", "Rehabilitation / recovery",
        "General wellbeing", "Athletic performance",
    ]
    _pf_row(
        "Health Goals", "What does the member want to achieve?",
        st.multiselect, "", _GOAL_OPTIONS,
        key="profile_goals", label_visibility="collapsed",
    )

    st.divider()

    # ── Activity & Sport ─────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">🏃 Activity & Sport</p>',
        unsafe_allow_html=True,
    )
    _pf_row(
        "Activity Level", "How active is the member currently?",
        st.selectbox, "",
        ["Not specified", "Sedentary (< 1h/week)", "Lightly Active (1–2h/week)",
         "Moderately Active (2–4h/week)", "Very Active (4–7h/week)", "Athlete (daily training)"],
        key="profile_activity_level", label_visibility="collapsed",
    )
    _SPORT_OPTIONS = [
        "Running / jogging", "Cycling", "Swimming", "Hiking",
        "Gym / weight training", "CrossFit / HIIT", "Yoga / Pilates",
        "Team sports (football, basketball…)", "Tennis / racket sports",
        "Dancing", "Martial arts", "Rowing", "Climbing", "Golf",
    ]
    _pf_row(
        "Sport Preferences", "Activities they enjoy or prefer",
        st.multiselect, "", _SPORT_OPTIONS,
        key="profile_sport_prefs", label_visibility="collapsed",
    )

    st.divider()

    # ── Mental Wellbeing ──────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">🧠 Mental Wellbeing</p>',
        unsafe_allow_html=True,
    )
    _mh_levels = ["Not assessed", "Low", "Moderate", "High", "Very High"]
    _mL, _mR = st.columns([1, 1.8], gap="large")
    with _mL:
        st.markdown(
            f'<p style="font-weight:600;color:{_GREEN_DARK};margin:0 0 2px 0;">Wellbeing Levels</p>'
            f'<p style="font-size:0.82rem;color:#666;margin:0;">From mental health questionnaire or self-report</p>',
            unsafe_allow_html=True,
        )
    with _mR:
        _w1, _w2, _w3 = st.columns(3)
        with _w1:
            st.selectbox("Stress",      _mh_levels, key="profile_stress")
        with _w2:
            st.selectbox("Depression",  _mh_levels, key="profile_depression")
        with _w3:
            st.selectbox("Optimism",    _mh_levels, key="profile_optimism")

    st.divider()

    # ── Injuries & Notes ─────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">⚠️ Injuries & Notes</p>',
        unsafe_allow_html=True,
    )
    _pf_row(
        "Injuries / Limitations",
        "Current injuries, chronic conditions, movements to avoid",
        st.text_area, "",
        placeholder="e.g. Left knee pain (meniscus), avoid overhead pressing",
        height=80, key="profile_injuries", label_visibility="collapsed",
    )
    _pf_row(
        "Additional Notes",
        "Any other context: lifestyle, diet, schedule, preferences",
        st.text_area, "",
        placeholder="e.g. Night-shift worker, vegetarian, prefers home workouts",
        height=80, key="profile_extra_notes", label_visibility="collapsed",
    )

    st.divider()

    # ── Status & Regenerate ───────────────────────────────────
    _ctx = _build_personal_context()
    _ctx_lines = len([l for l in _ctx.splitlines() if l.strip()]) if _ctx.strip() else 0
    _sL, _sR = st.columns([2, 1], gap="large")
    with _sL:
        if _ctx_lines:
            st.markdown(
                f'<span class="profile-saved-badge">'
                f'✅ {_ctx_lines} field{"s" if _ctx_lines != 1 else ""} filled — '
                f'AI Sports Scientist will use this</span>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("Fields above are all optional — recommendations work without them.")
    with _sR:
        if st.button("🔄 Update AI context", type="primary",
                     use_container_width=True):
            with st.spinner("Updating…"):
                from backend.rules.recommendation_api import get_recommendations as _gr
                st.session_state.result = _gr(
                    member_data, personal_context=_build_personal_context()
                )
                st.session_state.chat_history = []
                st.session_state.doctor_edits = {}
                st.session_state.doctor_signed = False
                st.session_state.knowledge_saved = False
                st.session_state.doctor_removed = set()
                st.session_state.doctor_custom_recs = []
            st.rerun()


# ────────────────────────────────────────────────────────────
# TAB 3 — Parameter Ratings
# ────────────────────────────────────────────────────────────
with tab_ratings:
    st.subheader("Parameter Ratings vs. Age & Gender Norms")
    st.caption(
        f"Compared against reference ranges for: "
        f"**{result.sex_group.title()}, "
        f"{_fmt_age_group(result.age_group)}**"
    )

    RATING_PCT = {
        "excellent":    100, "good": 75, "average": 55,
        "below_average": 35, "poor": 15, "elevated": 35, "high": 15,
    }

    has_data = False
    for rating in result.ratings:
        if rating.value is None:
            continue
        has_data = True
        label         = _PARAM_LABELS.get(rating.parameter, rating.parameter)
        colour        = RATING_COLOUR.get(rating.rating, "#aaa")
        emoji         = RATING_EMOJI.get(rating.rating, "⚪")
        pct           = RATING_PCT.get(rating.rating, 50)
        rating_display = rating.rating.replace("_", " ").title()

        st.markdown(
            f"""
            <div style="background:#fff;border-radius:10px;padding:14px 18px;
                        margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,0.07);">
              <div style="display:flex;justify-content:space-between;
                          align-items:baseline;margin-bottom:8px;">
                <strong style="color:#111;">{label}</strong>
                <span style="color:{colour};font-weight:700;font-size:0.9rem;">
                  {emoji} {rating_display}
                </span>
              </div>
              <div style="display:flex;align-items:center;gap:12px;">
                <div class="rating-bar-wrap" style="flex:1;">
                  <div class="rating-bar"
                       style="width:{pct}%;background:{colour};"></div>
                </div>
                <span style="font-size:1.05rem;font-weight:700;
                             color:#111;min-width:80px;text-align:right;">
                  {rating.value} {rating.unit}
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not has_data:
        st.info("No rated parameters — enter values in the sidebar.")


# ────────────────────────────────────────────────────────────
# TAB 4 — Training Zones
# ────────────────────────────────────────────────────────────
with tab_zones:
    zones = result.training_zones

    if zones is None:
        st.warning("⚠️ HR max is required to compute training zones. Enter it in the sidebar.")
    else:
        zd = zones_as_dict(zones)

        c1, c2, c3 = st.columns(3)
        c1.metric("HR max", f"{zones.hr_max} bpm")
        c2.metric("VT1 (aerobic threshold)", f"{zones.vt1} bpm")
        c3.metric("VT2 (anaerobic threshold)", f"{zones.vt2} bpm")
        st.caption(f"Source: {zd['source']}")
        st.divider()

        zone_colours = {
            "Zone 1 (Recovery)":     "#a8d5b5",
            "Zone 2 (Aerobic Base)": "#2e7d52",
            "Zone 3 (Tempo)":        "#f0a500",
            "Zone 4 (Threshold)":    "#d35400",
            "Zone 5 (Max Effort)":   "#a93226",
        }
        zone_desc = {
            "Zone 1 (Recovery)":
                "Easy active recovery. Promotes blood flow without stress.",
            "Zone 2 (Aerobic Base)":
                "Main endurance base. Builds mitochondria & fat oxidation. "
                "Target 75–80 % of weekly volume here.",
            "Zone 3 (Tempo)":
                "Comfortably hard. Improves lactate clearance. Use sparingly.",
            "Zone 4 (Threshold)":
                "VT2 region. Short intense intervals (1–8 min). 1–2× per week max.",
            "Zone 5 (Max Effort)":
                "All-out sprints. VO2max stimulation. Very limited volume.",
        }
        zone_purpose = {
            "Zone 1 (Recovery)":     "Recovery",
            "Zone 2 (Aerobic Base)": "Base / Endurance",
            "Zone 3 (Tempo)":        "Tempo",
            "Zone 4 (Threshold)":    "Threshold / HIIT",
            "Zone 5 (Max Effort)":   "VO2max Sprints",
        }

        for zname, zrange in zd["zones"].items():
            colour = zone_colours.get(zname, "#ccc")
            desc   = zone_desc.get(zname, "")
            purp   = zone_purpose.get(zname, "")
            st.markdown(
                f"""
                <div style="display:flex;align-items:stretch;margin-bottom:10px;
                            border-radius:10px;overflow:hidden;
                            box-shadow:0 1px 3px rgba(0,0,0,0.07);">
                  <div style="background:{colour};width:14px;flex-shrink:0;"></div>
                  <div style="background:#fff;flex:1;padding:10px 16px;">
                    <div style="display:flex;justify-content:space-between;
                                align-items:baseline;">
                      <strong style="color:#111;">{zname}</strong>
                      <span style="font-size:1.1rem;font-weight:700;
                                   color:{colour};">{zrange}</span>
                    </div>
                    <div style="font-size:0.82rem;color:#555;margin-top:3px;">
                      {desc}
                    </div>
                  </div>
                  <div style="background:#f5f5f5;padding:10px 16px;
                              display:flex;align-items:center;
                              font-size:0.8rem;color:#555;font-weight:600;
                              white-space:nowrap;">
                    {purp}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.info(
            "💡 Keep **80 % of weekly cardio in Zone 2**. Add 1–2 Zone 4 interval "
            "sessions per week once your aerobic base is established."
        )


# ────────────────────────────────────────────────────────────
# TAB 5 — Protocol & Quick Reference Library
# ────────────────────────────────────────────────────────────
_PROTOCOLS_YAML = Path(_ROOT) / "knowledge" / "protocols_quick_reference.yml"

if tab_lib is not None:
    with tab_lib:
        st.subheader("📚 Protocol & Quick Reference Library")
        st.caption(
            "Protocols are matched to your health data. **My protocols** shows only those relevant to your recommendations and ratings."
        )
    
        if not _PROTOCOLS_YAML.exists():
            st.warning(f"Protocol file not found: {_PROTOCOLS_YAML}")
            st.stop()
    
        with open(_PROTOCOLS_YAML, encoding="utf-8") as f:
            _protocols = yaml.safe_load(f)
    
        _cond_protocols = _protocols.get("condition_protocols", {})
        _train_templates = _protocols.get("training_templates", {})
        _mapping = _protocols.get("recommendation_mapping", {}) or {}
        _cat_map = _mapping.get("category_to_protocol", {}) or {}
        _kw_map = _mapping.get("title_keywords_to_protocol", {}) or {}
        _param_map = _mapping.get("parameter_to_protocol", {}) or {}
    
        def _protocol_keys_from_input() -> set:
            """Derive protocol keys from triggered recommendations and ratings (entry values)."""
            out = set()
            # From triggered recommendations
            for rec in result.triggered:
                cat = (rec.category or "").strip()
                if cat and cat in _cat_map:
                    out.add(_cat_map[cat])
                title = (rec.title or "").lower()
                for kw, pk in _kw_map.items():
                    if kw.lower() in title:
                        out.add(pk)
            # From ratings (elevated/poor/high → add protocol)
            _bad_ratings = {"elevated", "high", "poor", "below_average"}
            for r in result.ratings:
                if r.rating in _bad_ratings and r.parameter in _param_map:
                    out.add(_param_map[r.parameter])
            return out
    
        _auto_keys = _protocol_keys_from_input()
        _personal_keys = [k for k in _cond_protocols.keys() if k in _auto_keys]
        _all_keys = list(_cond_protocols.keys())
    
        def _lib_key(cond_key: str, field: str, template_key: str = "", prefix: str = "") -> str:
            pre = f"{prefix}_" if prefix else ""
            return f"lib_{pre}{cond_key}_{template_key}_{field}" if template_key else f"lib_{pre}{cond_key}_{field}"
    
        def _render_protocol_tabs(cond_keys: list, key_prefix: str = ""):
            """Render condition tabs and editable protocol content. key_prefix avoids duplicate widget keys across My/All tabs."""
            if not cond_keys:
                return
            _tab_objs = st.tabs([_cond_protocols[k].get("title", k) for k in cond_keys])
            for _tab_idx, _ckey in enumerate(cond_keys):
                with _tab_objs[_tab_idx]:
                    _p = _cond_protocols[_ckey]
                    _tr = _p.get("training", {}) or {}
                    _nf = _p.get("nutrition_focus", []) or []
                    _focus = _tr.get("focus", []) or []
                    _rel = _p.get("related_templates", []) or []
    
                    # ── Editable protocol section ──
                    st.markdown("**Protocol**")
                    _freq = st.text_input(
                        "Training frequency",
                        value=_tr.get("frequency", ""),
                        key=_lib_key(_ckey, "freq", prefix=key_prefix),
                    )
                    _intensity = st.text_input(
                        "Intensity",
                        value=_tr.get("intensity", ""),
                        key=_lib_key(_ckey, "intensity", prefix=key_prefix),
                    )
                    _duration = st.text_input(
                        "Duration",
                        value=_tr.get("duration", ""),
                        key=_lib_key(_ckey, "duration", prefix=key_prefix),
                    )
                    _focus_txt = st.text_area(
                        "Focus (one per line)",
                        value="\n".join(_focus),
                        height=80,
                        key=_lib_key(_ckey, "focus", prefix=key_prefix),
                    )
                    _nf_txt = st.text_area(
                        "Nutrition focus (one per line)",
                        value="\n".join(_nf),
                        height=80,
                        key=_lib_key(_ckey, "nutrition", prefix=key_prefix),
                    )
                    _recheck = st.text_input(
                        "Recheck interval",
                        value=_p.get("recheck_interval", ""),
                        key=_lib_key(_ckey, "recheck", prefix=key_prefix),
                    )
    
                    st.divider()
                    st.markdown("**Training templates for this condition**")
    
                    # ── Editable template cards (Streamlit widgets, no HTML blocks) ──
                    for _tk in _rel:
                        if _tk not in _train_templates:
                            continue
                        _t = _train_templates[_tk]
                        with st.expander(_t.get("title", _tk), expanded=True):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input(
                                    "Frequency",
                                    value=_t.get("frequency", ""),
                                    key=_lib_key(_ckey, "tfreq", _tk, prefix=key_prefix),
                                )
                                st.text_input(
                                    "Intensity",
                                    value=_t.get("intensity", ""),
                                    key=_lib_key(_ckey, "tintensity", _tk, prefix=key_prefix),
                                )
                            with c2:
                                st.text_input(
                                    "Duration",
                                    value=_t.get("duration", ""),
                                    key=_lib_key(_ckey, "tduration", _tk, prefix=key_prefix),
                                )
                                if _t.get("volume") or _t.get("rest"):
                                    st.text_input(
                                        "Volume / Rest",
                                        value=_t.get("volume", "") or _t.get("rest", ""),
                                        key=_lib_key(_ckey, "tvolrest", _tk, prefix=key_prefix),
                                    )
                            _ex = _t.get("exercises", _t.get("modalities", [])) or []
                            st.text_area(
                                "Exercises / modalities (one per line)",
                                value="\n".join(_ex),
                                height=80,
                                key=_lib_key(_ckey, "texercises", _tk, prefix=key_prefix),
                            )
    
        tab_my, tab_all, tab_export = st.tabs(["My protocols", "All protocols", "Export my personal protocol"])
    
        with tab_my:
            if _personal_keys:
                st.info(
                    f"Protocols matched to your entry values: **{', '.join(_cond_protocols[k].get('title', k) for k in _personal_keys)}**"
                )
                _render_protocol_tabs(_personal_keys, "my")
            else:
                st.info(
                    "No protocols match your recommendations or ratings yet. "
                    "Run recommendations with your health data first, or switch to **All protocols** to browse the full library."
                )
    
        with tab_all:
            _render_protocol_tabs(_all_keys, "all")
    
        with tab_export:
            st.markdown("**Build your personal protocol document** — start with protocols matched to your data, add sections from others, then export.")
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            _other_keys = [k for k in _all_keys if k not in _personal_keys]
            _selected_extra = st.multiselect(
                "Add sections from other protocols",
                options=_other_keys,
                default=[],
                format_func=lambda k: _cond_protocols[k].get("title", k),
                key="export_add_protocols",
                help="Select additional protocols to include in your export.",
            )
            _export_keys = list(dict.fromkeys(_personal_keys + _selected_extra))
            if not _export_keys:
                st.info("No protocols selected. Your personal protocols will be included by default. Add more above or run recommendations first.")
                _export_keys = list(_personal_keys) if _personal_keys else []
            if _export_keys:
                st.caption(f"Included: **{', '.join(_cond_protocols[k].get('title', k) for k in _export_keys)}**")
                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                with st.expander("📥 Export your protocol document", expanded=True):
                    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                    _ts = _dt.now().strftime("%Y%m%d_%H%M")
                    _base = f"ayun_personal_protocol_{_ts}"
                    _need_reportlab = _need_docx = False
                    _cpad_l, c1, c2, _cpad_r = st.columns([0.25, 1, 1, 0.25])
                    with c1:
                        try:
                            from backend.documents.report_generator import protocol_to_pdf
                            _pdf_bytes = protocol_to_pdf(_cond_protocols, _train_templates, _export_keys)
                            st.download_button(
                                "📥 Export as PDF",
                                data=_pdf_bytes,
                                file_name=f"{_base}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                        except Exception as e:
                            _need_reportlab = True
                            st.button("📥 Export as PDF", disabled=True, key="pdf_disabled", use_container_width=True)
                            if "reportlab" in str(e).lower() or "module" in str(e).lower():
                                pass
                            else:
                                st.caption(f"⚠️ {type(e).__name__}: {e}")
                    with c2:
                        try:
                            from backend.documents.report_generator import protocol_to_docx
                            _docx_bytes = protocol_to_docx(_cond_protocols, _train_templates, _export_keys)
                            st.download_button(
                                "📥 Export as Word",
                                data=_docx_bytes,
                                file_name=f"{_base}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                            )
                        except Exception as e:
                            _need_docx = True
                            st.button("📥 Export as Word", disabled=True, key="docx_disabled", use_container_width=True)
                            if "docx" not in str(e).lower() and "module" not in str(e).lower():
                                st.caption(f"⚠️ {type(e).__name__}: {e}")
                    if _need_reportlab or _need_docx:
                        _msgs = []
                        if _need_reportlab:
                            _msgs.append("**PDF:** `pip install reportlab`")
                        if _need_docx:
                            _msgs.append("**Word:** `pip install python-docx`")
                        st.caption("💡 " + " | ".join(_msgs))
                        st.caption("**Restart the Streamlit app** after installing (Ctrl+C, then `streamlit run app.py` again).")
                        with st.expander("Environment check"):
                            st.code(f"Python: {sys.executable}")
                            try:
                                import reportlab
                                st.success("reportlab: OK")
                            except ImportError as e:
                                st.error(f"reportlab: {e}")
    
    
    # ────────────────────────────────────────────────────────────
    # TAB 6 — AI Assistant (knowledge-grounded)
    # ────────────────────────────────────────────────────────────
with tab_chat:
    _role_label = "Member" if st.session_state.user_role == "patient" else "Clinician"
    st.subheader(f"💬 AI Assistant · {_role_label} mode")
    st.caption(
        "Ask about recommendations, training, or health goals. "
        "Answers combine your profile, rule-engine output, and validated clinician knowledge. "
        "Low-confidence questions are routed to **Expert Q&A** for doctor validation."
    )

    if not cb.is_configured():
        st.error(cb._deployment_hint() or "AI is not configured.")
        st.stop()

    # Build context: rule engine + optional clinician-reviewed layer
    _live_personal_ctx = _build_personal_context()
    _live_context = result.context_for_llm
    if _live_personal_ctx.strip() and _live_personal_ctx.strip() != result.personal_context.strip():
        _live_context += (
            "\n\n── PERSONAL PROFILE & GOALS (latest) ──────────────\n"
            + _live_personal_ctx
        )
    _reviewed_ctx = build_reviewed_recommendation_context(
        result.triggered,
        st.session_state.doctor_edits,
        st.session_state.doctor_removed,
        st.session_state.doctor_custom_recs,
    )
    if _reviewed_ctx:
        _live_context += "\n\n" + _reviewed_ctx

    _member_snap = {
        "age": member_data.get("Demographic::Age"),
        "sex": member_data.get("Demographic::Sex"),
        "name": st.session_state.get("profile_name", ""),
    }

    for msg in st.session_state.chat_history:
        role = msg["role"]
        avatar = "👤" if role == "user" else "🏃"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander("Sources"):
                    for c in msg["citations"]:
                        st.markdown(f"**[{c.get('index', '?')}]** {c.get('title', '')} — {c.get('locator', '')}")
            if msg.get("confidence"):
                st.caption(f"Confidence: {msg['confidence']}")

    if not st.session_state.chat_history:
        st.markdown(
            f'<p style="color:{_GREEN};font-weight:600;margin-bottom:6px;">'
            'Quick questions to get started:</p>',
            unsafe_allow_html=True,
        )
        quick_questions = [
            "What should I focus on first?",
            "Explain my training zones.",
            "Which recommendation is most urgent?",
            "How can I improve my VO2max?",
        ]
        cols = st.columns(len(quick_questions))
        for i, q in enumerate(quick_questions):
            if cols[i].button(q, key=f"qs_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": q})
                st.rerun()

    user_input = st.chat_input("Ask your sports scientist…")
    st.markdown("""
    <style>
    .stChatInputContainer, .stChatInputContainer > div,
    .stChatFloatingInputContainer, .stChatFloatingInputContainer > div,
    [data-testid="stChatInput"], [data-testid="stChatInput"] > div,
    form[data-testid="stChatInput"], form[data-testid="stChatInput"] > div {
      background: #dff0e6 !important;
      background-color: #dff0e6 !important;
      border: 1px solid #52a872 !important;
    }
    [data-testid="stChatInput"] input, [data-testid="stChatInput"] textarea,
    .stChatInputContainer input, .stChatInputContainer textarea {
      background: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.rerun()

    history = st.session_state.chat_history
    if history and history[-1]["role"] == "user":
        _last_q = history[-1]["content"]
        with st.chat_message("assistant", avatar="🏃"):
            placeholder = st.empty()
            try:
                _ask_resp = ask_with_knowledge(
                    question=_last_q,
                    member_context=_live_context,
                    messages=history[:-1],
                    viewer_role=st.session_state.user_role,
                    viewer_name=st.session_state.viewer_name,
                    member_snapshot=_member_snap,
                    auto_ticket=True,
                )
                placeholder.markdown(_ask_resp.answer)
                if _ask_resp.citations:
                    with st.expander("📎 Knowledge sources cited"):
                        for c in _ask_resp.citations:
                            st.markdown(f"**[{c['index']}]** {c['title']} ({c['kind']})")
                            st.caption(c.get("excerpt", "")[:200])
                st.caption(f"Confidence: {_ask_resp.confidence}")
                if _ask_resp.ticket_id:
                    st.info(f"Ticket `{_ask_resp.ticket_id}` created — a clinician can answer in **Expert Q&A**.")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": _ask_resp.answer,
                    "confidence": _ask_resp.confidence,
                    "citations": _ask_resp.citations,
                    "ticket_id": _ask_resp.ticket_id,
                })
            except Exception as exc:
                placeholder.error(f"⚠️ Error contacting AI: {exc}")
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": f"⚠️ Error: {exc}"}
                )
        st.rerun()


# ────────────────────────────────────────────────────────────
# TAB 7 — Knowledge Library
# ────────────────────────────────────────────────────────────
with tab_knowledge:
    render_knowledge_library_tab(_GREEN, _GREEN_DARK, st.session_state.user_role, st.session_state.viewer_name)


# ────────────────────────────────────────────────────────────
# TAB 8 — Expert Q&A
# ────────────────────────────────────────────────────────────
with tab_tickets:
    _ticket_ctx = result.context_for_llm if result else ""
    if _live_personal_ctx := _build_personal_context():
        _ticket_ctx += "\n\n── PERSONAL PROFILE ──\n" + _live_personal_ctx
    render_expert_qa_tab(
        _GREEN,
        st.session_state.user_role,
        st.session_state.viewer_name,
        member_snapshot={
            "age": member_data.get("Demographic::Age"),
            "sex": member_data.get("Demographic::Sex"),
            "name": st.session_state.get("profile_name", ""),
        },
        chat_context=_ticket_ctx,
    )


# ────────────────────────────────────────────────────────────
# Expert Sign-off (experts only — tab hidden for members)
# ────────────────────────────────────────────────────────────
if _is_expert and tab_doctor is not None:
    with tab_doctor:
        import json as _json

        st.subheader("✏️ Expert Sign-off & Review")
        st.caption(
            "Review the AI-generated recommendations, override priorities, "
            "add clinical notes, and export a signed report for the member's file."
        )
    
        _PRIORITY_OPTS = ["Critical", "High", "Medium", "Low"]
        _active_count  = len(result.triggered) - len(st.session_state.doctor_removed) \
                         + len(st.session_state.doctor_custom_recs)
    
        if not result.triggered and not st.session_state.doctor_custom_recs:
            st.info("✅ No triggered recommendations — member values are within reference ranges. "
                    "You can still add custom recommendations below.")
        else:
            st.markdown(
                f'<p style="color:{_GREEN};font-weight:600;margin-bottom:4px;">'
                f"{_active_count} active recommendation(s) — "
                f"edit any card, remove it, or add new ones before signing off.</p>",
                unsafe_allow_html=True,
            )
        st.divider()
    
        def _render_doc_card(key: str, default_title: str, default_priority: str,
                             default_items: str, default_category: str = "", is_custom: bool = False):
            """Render one editable doctor review card. Returns True if removed."""
            if key not in st.session_state.doctor_edits:
                st.session_state.doctor_edits[key] = {
                    "title":    default_title,
                    "priority": default_priority,
                    "items":    default_items,
                    "notes":    "",
                    "category": default_category,
                }
            _ed = st.session_state.doctor_edits[key]
            _p_init = _ed["priority"]
    
            st.markdown(
                f'<div class="doctor-card doctor-card-{_p_init}">',
                unsafe_allow_html=True,
            )
    
            # Title row: selectbox first so badge uses same value (no mismatch)
            _th1, _th2, _th3, _th4 = st.columns([0.35, 0.2, 2.2, 0.4], vertical_alignment="center")
            with _th1:
                _new_priority = st.selectbox(
                    "Priority", _PRIORITY_OPTS,
                    index=_PRIORITY_OPTS.index(_ed["priority"]),
                    key=f"{key}_prio",
                    label_visibility="collapsed",
                )
                st.session_state.doctor_edits[key]["priority"] = _new_priority
            with _th2:
                _p = _new_priority
                _emoji = PRIORITY_EMOJI.get(_p, "")
                st.markdown(
                    f'<span class="badge badge-{_p}">{_emoji} {_p.upper()}</span>',
                    unsafe_allow_html=True,
                )
            with _th3:
                _new_title = st.text_input(
                    "Title", value=_ed["title"],
                    placeholder="Recommendation title…",
                    key=f"{key}_title", label_visibility="collapsed",
                )
                st.session_state.doctor_edits[key]["title"] = _new_title
            with _th4:
                if st.button("✕ Remove", key=f"{key}_remove",
                             help="Remove this recommendation from the review"):
                    st.markdown('</div>', unsafe_allow_html=True)
                    return True   # signal to caller to remove
    
            if _ed.get("category"):
                st.markdown(
                    f'<div style="font-size:0.8rem;color:#888;margin:-6px 0 8px 0;">'
                    f'Category: {_ed["category"]}</div>',
                    unsafe_allow_html=True,
                )
    
            _new_items = st.text_area(
                "Action Items", value=_ed["items"],
                height=120, key=f"{key}_items",
            )
            st.session_state.doctor_edits[key]["items"] = _new_items
    
            _new_notes = st.text_area(
                "📝 Clinician Notes", value=_ed["notes"],
                height=70, key=f"{key}_notes",
                placeholder="Clinical observations, adjustments, patient-specific considerations…",
            )
            st.session_state.doctor_edits[key]["notes"] = _new_notes
            st.markdown('</div>', unsafe_allow_html=True)
            return False   # not removed
    
        # ── AI-generated recommendations ─────────────────────────
        for _i, _rec in enumerate(result.triggered):
            if _i in st.session_state.doctor_removed:
                continue
            _key = f"rec_{_i}"
            _removed = _render_doc_card(
                key=_key,
                default_title=_rec.title,
                default_priority=_rec.priority,
                default_items="\n".join(f"• {a}" for a in _rec.action_items),
                default_category=_rec.category,
            )
            if _removed:
                st.session_state.doctor_removed.add(_i)
                st.rerun()
    
        # ── Custom doctor-added recommendations ──────────────────
        _to_delete_custom = None
        for _ci, _crec in enumerate(st.session_state.doctor_custom_recs):
            _ckey = f"custom_{_ci}"
            _removed = _render_doc_card(
                key=_ckey,
                default_title=_crec.get("title", ""),
                default_priority=_crec.get("priority", "Medium"),
                default_items=_crec.get("items", ""),
                default_category="Custom",
                is_custom=True,
            )
            if _removed:
                _to_delete_custom = _ci
    
        if _to_delete_custom is not None:
            st.session_state.doctor_custom_recs.pop(_to_delete_custom)
            _ckey = f"custom_{_to_delete_custom}"
            st.session_state.doctor_edits.pop(_ckey, None)
            st.rerun()
    
        # ── Add custom recommendation ─────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("＋ Add Recommendation", use_container_width=True):
            st.session_state.doctor_custom_recs.append({
                "title":    "",
                "priority": "Medium",
                "items":    "",
            })
            st.rerun()
    
        # ── Sign-off & Export ─────────────────────────────────────
        st.divider()
        st.markdown(f'<div class="profile-section-title">Clinician Sign-off & Export</div>',
                    unsafe_allow_html=True)
    
        _so1, _so2 = st.columns([2, 1])
        with _so1:
            st.text_input("Clinician Name / ID", placeholder="Manuel Burger",
                          key="doctor_name")
        with _so2:
            _review_date = _dt.now().strftime("%Y-%m-%d")
            st.text_input("Review Date", value=_review_date, disabled=True)
    
        # Build export payload — only active (non-removed) AI recs + custom recs
        _ai_recs_export = [
            {
                "title":             st.session_state.doctor_edits.get(f"rec_{_i}", {}).get("title", _rec.title),
                "category":          _rec.category,
                "original_priority": _rec.priority,
                "reviewed_priority": st.session_state.doctor_edits.get(f"rec_{_i}", {}).get("priority", _rec.priority),
                "action_items":      st.session_state.doctor_edits.get(f"rec_{_i}", {}).get(
                                         "items", "\n".join(f"• {a}" for a in _rec.action_items)),
                "clinician_notes":   st.session_state.doctor_edits.get(f"rec_{_i}", {}).get("notes", ""),
                "source": "ai_generated",
            }
            for _i, _rec in enumerate(result.triggered)
            if _i not in st.session_state.doctor_removed
        ]
        _custom_recs_export = [
            {
                "title":             st.session_state.doctor_edits.get(f"custom_{_ci}", {}).get("title", ""),
                "category":          "Custom",
                "reviewed_priority": st.session_state.doctor_edits.get(f"custom_{_ci}", {}).get("priority", "Medium"),
                "action_items":      st.session_state.doctor_edits.get(f"custom_{_ci}", {}).get("items", ""),
                "clinician_notes":   st.session_state.doctor_edits.get(f"custom_{_ci}", {}).get("notes", ""),
                "source": "clinician_added",
            }
            for _ci in range(len(st.session_state.doctor_custom_recs))
        ]
    
        _export = {
            "_meta": {
                "exported_at": _dt.now().isoformat(),
                "reviewed_by": st.session_state.doctor_name or "Not signed",
                "review_date": _review_date,
                "app_version": "Joule for AYUN · Sport Plan v2",
            },
            "member": {
                "age":   member_data.get("Demographic::Age"),
                "sex":   member_data.get("Demographic::Sex"),
                "name":  st.session_state.get("profile_name", "") or None,
                "group": f"{result.sex_group.title()}, {result.age_group}",
            },
            "personal_profile": {
                "goals":          st.session_state.get("profile_goals", []),
                "activity_level": st.session_state.get("profile_activity_level", ""),
                "sport_prefs":    st.session_state.get("profile_sport_prefs", []),
                "stress":         st.session_state.get("profile_stress", ""),
                "depression":     st.session_state.get("profile_depression", ""),
                "optimism":       st.session_state.get("profile_optimism", ""),
                "injuries":       st.session_state.get("profile_injuries", ""),
                "notes":          st.session_state.get("profile_extra_notes", ""),
            },
            "parameter_ratings": [
                {"parameter": r.parameter, "value": r.value, "unit": r.unit, "rating": r.rating}
                for r in result.ratings if r.value is not None
            ],
            "recommendations": _ai_recs_export + _custom_recs_export,
        }
    
        _export_json = _json.dumps(_export, indent=2, ensure_ascii=False)
        _fname_base = (
            f"ayun_review_"
            f"{(st.session_state.get('profile_name') or 'member').replace(' ', '_').lower()}"
            f"_{_review_date}"
        )
    
        _dex1, _dex2 = st.columns(2)
        with _dex1:
            st.download_button(
                label="📥 Export as JSON",
                data=_export_json,
                file_name=f"{_fname_base}.json",
                mime="application/json",
                use_container_width=True,
            )
        with _dex2:
            try:
                from backend.documents.report_generator import doctor_review_to_pdf
                _pdf_bytes = doctor_review_to_pdf(_export)
                st.download_button(
                    label="📥 Export as PDF",
                    data=_pdf_bytes,
                    file_name=f"{_fname_base}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.download_button(
                    "📥 Export as PDF",
                    disabled=True,
                    use_container_width=True,
                    help="Install reportlab: pip install reportlab",
                )
    
        # ── Save to Knowledge Base (learning loop) ─────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="profile-section-title">Teach the AI — Knowledge Pipeline</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Save this reviewed case to the clinical knowledge base. "
            "Future patient and doctor questions will use these validated recommendations "
            "(inspired by institutional knowledge systems like SIX Atlas)."
        )
        _can_save_kb = bool(st.session_state.doctor_name.strip()) and (
            _ai_recs_export or _custom_recs_export
        )
        if st.button(
            "💾 Save reviewed case to Knowledge Base",
            disabled=not _can_save_kb,
            use_container_width=True,
            type="primary",
            key="btn_save_knowledge",
        ):
            _saved_nodes = capture_from_doctor_review(_export, st.session_state.doctor_name.strip())
            st.session_state.doctor_signed = True
            st.session_state.knowledge_saved = True
            try:
                from backend.storage import ayun_db
                if ayun_db.is_configured():
                    ayun_db.persist_expert_review(
                        st.session_state.get("assessment_id"),
                        st.session_state.doctor_name.strip(),
                        _export.get("recommendations", []),
                        export_meta=_export.get("_meta", {}),
                        knowledge_saved=True,
                    )
            except Exception:
                pass
            st.success(f"Saved **{len(_saved_nodes)}** knowledge node(s). The AI assistant will use them in future Q&A.")
            st.rerun()
        if not st.session_state.doctor_name.strip():
            st.caption("Enter clinician name above before saving to the knowledge base.")
        elif st.session_state.knowledge_saved:
            st.info("✅ This session's review has been saved to the knowledge base.")


# ────────────────────────────────────────────────────────────
# TAB 10 — Playground (What-If Scenarios)
# ────────────────────────────────────────────────────────────
with tab_play:
    from backend.rules.recommendation_api import get_recommendations as _play_get_rec

    # ── Parameter catalogue: (section, label, data_key, min, max, step, unit)
    # Full list of all numeric parameters — users can add any unmeasured one to the scenario
    _PLAY_PARAMS = [
        # Physical Performance
        ("💪 Physical Performance", "VO2max",               "Physiological::Vo2Max",                                       10.0,  85.0,  0.5,  "ml/min/kg"),
        ("💪 Physical Performance", "Grip Strength (R)",      "Physiological::Gripstrength Rechts",                           5.0,  80.0,  0.5,  "kg"),
        ("💪 Physical Performance", "Grip Strength (L)",      "Physiological::Gripstrength Links",                            5.0,  80.0,  0.5,  "kg"),
        ("💪 Physical Performance", "Counter Movement Jump",  "Physiological::Counter movement jump",                        5.0,  80.0,  0.5,  "cm"),
        ("💪 Physical Performance", "Y-Balance Score",        "Physiological::Y-Balance Composite Score",                     50.0, 120.0,  0.5,  "%"),
        ("💪 Physical Performance", "HR max",                 "Physiological::HR max",                                       120.0, 220.0, 1.0,  "bpm"),
        ("💪 Physical Performance", "HR at VT1",              "Physiological::HR at VT1",                                    95.0,  220.0, 1.0,  "bpm"),
        ("💪 Physical Performance", "HR at VT2",              "Physiological::HR at VT2",                                    100.0, 220.0, 1.0,  "bpm"),
        # Upper Body Strength
        ("💪 Upper Body Strength",   "Biceps Strength (R)",    "Physiological::Biceps Strength Rechts",                       0.0,  60.0,  0.5,  "kg"),
        ("💪 Upper Body Strength",   "Biceps Strength (L)",    "Physiological::Biceps Strength Links",                         0.0,  60.0,  0.5,  "kg"),
        ("💪 Upper Body Strength",   "Triceps Strength (R)",   "Physiological::Triceps Strength Rechts",                       0.0,  60.0,  0.5,  "kg"),
        ("💪 Upper Body Strength",   "Triceps Strength (L)",   "Physiological::Triceps Strength Links",                        0.0,  60.0,  0.5,  "kg"),
        # Body Composition
        ("🏋️ Body Composition",     "Body Fat %",            "Body Composition::Fat percentage",                            3.0,  50.0,  0.1,  "%"),
        ("🏋️ Body Composition",     "Visceral Fat",          "Body Composition::Visceral Fat Index (raw value from DEXA)",   0.0, 5100.0, 10.0, "cm³"),
        ("🏋️ Body Composition",     "LMI",                   "Body Composition::Muscle Mass Index (LMI)",                    5.0,  20.0,  0.1,  "kg/m²"),
        ("🏋️ Body Composition",     "ALMI",                 "Body Composition::ALMI",                                      3.0,  14.0,  0.1,  "kg/m²"),
        ("🏋️ Body Composition",     "BMD Z-score",           "Body Composition::Bone mineral density",                      -4.0,   4.0,  0.1,  "SD"),
        # Range of Motion
        ("🦵 Range of Motion",       "Shoulder Flexion (R)",   "Physiological::Shoulder Flexion Right",                      0.0,  200.0, 1.0,  "°"),
        ("🦵 Range of Motion",       "Shoulder Flexion (L)",   "Physiological::Shoulder Flexion Left",                        0.0,  200.0, 1.0,  "°"),
        ("🦵 Range of Motion",       "Hip Flexion (R)",        "Physiological::Hip Flexion Right",                             0.0,  160.0, 1.0,  "°"),
        ("🦵 Range of Motion",       "Hip Flexion (L)",        "Physiological::Hip Flexion Left",                              0.0,  160.0, 1.0,  "°"),
        # Blood Biomarkers
        ("🩸 Blood Biomarkers",      "LDL Cholesterol",       "Blood Biomarkers::LDL",                                       0.5,   8.0,  0.1,  "mmol/L"),
        ("🩸 Blood Biomarkers",      "HbA1c",                 "Blood Biomarkers::HbA1c",                                     3.0,  12.0,  0.1,  "%"),
        ("🩸 Blood Biomarkers",      "ALAT",                  "Blood Biomarkers::ALAT",                                      5.0,  200.0, 1.0,  "U/L"),
        ("🩸 Blood Biomarkers",      "ASAT",                 "Blood Biomarkers::ASAT",                                      5.0,  200.0, 1.0,  "U/L"),
        ("🩸 Blood Biomarkers",      "GGT",                   "Blood Biomarkers::GGT",                                       5.0,  200.0, 1.0,  "U/L"),
    ]

    def _play_safe_key(data_key: str) -> str:
        return "play_" + data_key.replace(" ", "_").replace(":", "_") \
                                  .replace("(", "").replace(")", "").replace("/", "_")

    _orig_sex = member_data.get("Demographic::Sex", "Male")
    _orig_age = member_data.get("Demographic::Age", 30)

    # Split params into those with real data and those without
    _has_data_params  = [p for p in _PLAY_PARAMS if member_data.get(p[2]) is not None]
    _no_data_params   = [p for p in _PLAY_PARAMS if member_data.get(p[2]) is None]

    # ── Header row ────────────────────────────────────────────
    _ph_l, _ph_r = st.columns([2, 1], gap="large")
    with _ph_l:
        st.markdown(
            f'<h3 style="margin:0 0 4px 0;color:{_GREEN_DARK};">🧪 What-If Playground</h3>'
            f'<p style="color:#777;font-size:0.88rem;margin:0;">Adjust any measured value '
            f'and run the analysis to see how recommendations change. '
            f'Nothing here affects the real report.</p>',
            unsafe_allow_html=True,
        )
    with _ph_r:
        if st.button("↺  Reset all sliders", use_container_width=True):
            for _k in list(st.session_state.keys()):
                if _k.startswith("play_"):
                    del st.session_state[_k]
            st.session_state.play_result = None
            st.rerun()

    st.divider()

    # ── Demographics row ─────────────────────────────────────
    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:1.2px;color:{_GREEN};margin-bottom:10px;">🧬 Demographics</p>',
        unsafe_allow_html=True,
    )
    _d1, _d2, _d3 = st.columns([1, 2, 1], gap="large")
    with _d1:
        _pg_sex_opts = ["Male", "Female"]
        _pg_sex_def  = _pg_sex_opts.index(_orig_sex.title()) if _orig_sex.title() in _pg_sex_opts else 0
        _pg_sex = st.radio("Sex", _pg_sex_opts, index=_pg_sex_def,
                           horizontal=True, key="play_sex")
    with _d2:
        _age_val = int(_orig_age) if _orig_age else 30
        st.markdown(f'<p style="margin:0 0 4px 0;font-weight:600;color:{_GREEN_DARK};">Age (yrs)</p>',
                    unsafe_allow_html=True)
        _pg_age  = st.slider("Age (yrs)", min_value=18, max_value=99,
                             value=_age_val, key="play_age",
                             help="Shifts the age-group bucket — different norms apply per decade",
                             label_visibility="collapsed")
    with _d3:
        # Show current age group
        _age_decades = [(18,29,"18–29"),(30,39,"30–39"),(40,49,"40–49"),
                        (50,59,"50–59"),(60,69,"60–69"),(70,79,"70–79"),(80,99,"80–99")]
        _cur_decade  = next((l for a,b,l in _age_decades if a <= _pg_age <= b), "—")
        _orig_decade = next((l for a,b,l in _age_decades if a <= int(_orig_age or 30) <= b), "—")
        _decade_changed = _cur_decade != _orig_decade
        st.markdown(
            f'<div style="padding-top:28px;font-size:0.82rem;color:#1a1a1a;">'
            f'Age group: <b style="color:{_GREEN_DARK if not _decade_changed else "#c0392b"};">'
            f'{_cur_decade}</b>'
            + (f' <span style="color:#c0392b;font-size:0.75rem;">(was {_orig_decade})</span>'
               if _decade_changed else "") +
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Sliders — only for parameters with actual data ────────
    if not _has_data_params:
        st.info("No numeric parameters are loaded yet — upload a member report first, "
                "then come back to play with the values.")
    else:
        _cur_section = None
        for _sec, _lbl, _key, _lo, _hi, _step, _unit in _has_data_params:
            if _sec != _cur_section:
                _cur_section = _sec
                st.markdown(
                    f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:1.2px;color:{_GREEN};margin:14px 0 8px 0;">{_sec}</p>',
                    unsafe_allow_html=True,
                )

            _orig_val = float(member_data[_key])
            _default  = float(min(max(_orig_val, _lo), _hi))
            _skey     = _play_safe_key(_key)

            _sl_col, _orig_col = st.columns([5, 1])
            with _sl_col:
                if _step == int(_step):
                    _pg_val = st.slider(f"{_lbl}  ({_unit})",
                                        min_value=int(_lo), max_value=int(_hi),
                                        value=int(_default), key=_skey)
                else:
                    _pg_val = st.slider(f"{_lbl}  ({_unit})",
                                        min_value=float(_lo), max_value=float(_hi),
                                        value=float(_default), step=float(_step), key=_skey)
            with _orig_col:
                _changed = abs(float(_pg_val) - _orig_val) > 1e-6
                st.markdown(
                    f'<div style="padding-top:28px;font-size:0.78rem;'
                    f'color:{"#e67e22" if _changed else "#aaa"};">'
                    f'{"→ " if _changed else ""}<b>{_orig_val:g}</b><br>'
                    f'<span style="font-size:0.7rem;color:#bbb;">original</span></div>',
                    unsafe_allow_html=True,
                )

    # ── Optional: hypothetical parameters (no real data) ─────
    if _no_data_params:
        with st.expander(
            f"➕  Try {len(_no_data_params)} unmeasured parameter(s)  "
            f"— enable any to add to the scenario"
        ):
            st.caption(
                "These parameters have no real data. "
                "Check the box next to a parameter to include a hypothetical value in the analysis."
            )
            for _sec, _lbl, _key, _lo, _hi, _step, _unit in _no_data_params:
                _skey      = _play_safe_key(_key)
                _en_key    = _skey + "_enabled"
                _enabled   = st.checkbox(f"Include  **{_lbl}**  ({_unit})", key=_en_key)
                if _enabled:
                    _default = float((_lo + _hi) / 2)
                    if _step == int(_step):
                        st.slider(f"{_lbl}", min_value=int(_lo), max_value=int(_hi),
                                  value=int(_default), key=_skey)
                    else:
                        st.slider(f"{_lbl}", min_value=float(_lo), max_value=float(_hi),
                                  value=float(_default), step=float(_step), key=_skey)

    st.divider()

    # ── Run button ────────────────────────────────────────────
    _run_clicked = st.button("🔬  Run What-If Analysis",
                             type="primary", use_container_width=True)

    if _run_clicked:
        _scenario = dict(member_data)
        # Always apply sex + age
        _scenario["Demographic::Sex"] = _pg_sex
        _scenario["Demographic::Age"] = _pg_age
        # Apply slider values only for params WITH original data
        for _sec, _lbl, _key, _lo, _hi, _step, _unit in _has_data_params:
            _skey = _play_safe_key(_key)
            if _skey in st.session_state:
                _scenario[_key] = st.session_state[_skey]
        # Apply hypothetical params only if explicitly enabled
        for _sec, _lbl, _key, _lo, _hi, _step, _unit in _no_data_params:
            _skey   = _play_safe_key(_key)
            _en_key = _skey + "_enabled"
            if st.session_state.get(_en_key) and _skey in st.session_state:
                _scenario[_key] = st.session_state[_skey]

        with st.spinner("Running scenario…"):
            st.session_state.play_result = _play_get_rec(_scenario)
            st.session_state.play_data   = _scenario

    # ── Results ───────────────────────────────────────────────
    _pr = st.session_state.play_result
    if _pr is None:
        st.markdown(
            f'<div style="text-align:center;padding:48px 20px;color:#ccc;">'
            f'<div style="font-size:3rem;">🔬</div>'
            f'<div style="margin-top:10px;font-size:0.95rem;color:#aaa;">'
            f'Move the sliders above, then click <b style="color:{_GREEN};">Run What-If Analysis</b>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        _orig_triggered_titles = {r.title for r in result.triggered}
        _play_triggered_titles = {r.title for r in _pr.triggered}
        _gained   = _play_triggered_titles - _orig_triggered_titles
        _resolved = _orig_triggered_titles - _play_triggered_titles
        _kept     = _orig_triggered_titles & _play_triggered_titles

        # Score cards
        st.markdown(
            f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:1.2px;color:{_GREEN};margin:20px 0 10px 0;">📊 Scenario Results</p>',
            unsafe_allow_html=True,
        )
        _sc1, _sc2, _sc3, _sc4 = st.columns(4)
        def _score_card(col, label, value, colour):
            col.markdown(
                f'<div style="background:{colour}14;border:1.5px solid {colour}33;'
                f'border-radius:12px;padding:14px 10px;text-align:center;">'
                f'<div style="font-size:1.8rem;font-weight:800;color:{colour};">{value}</div>'
                f'<div style="font-size:0.75rem;color:#666;margin-top:3px;">{label}</div></div>',
                unsafe_allow_html=True,
            )
        _score_card(_sc1, "Total flags",   len(_pr.triggered), "#2980b9")
        _score_card(_sc2, "✅ Resolved",   len(_resolved),     "#27ae60")
        _score_card(_sc3, "⚠️ New flags",  len(_gained),       "#e67e22")
        _score_card(_sc4, "↔ Unchanged",   len(_kept),         "#888888")

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        # Flags diff
        if _resolved:
            for _t in sorted(_resolved):
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'background:#f0fff4;border-left:4px solid #27ae60;'
                    f'padding:8px 14px;border-radius:6px;margin-bottom:5px;">'
                    f'<span style="color:#27ae60;font-size:1rem;">✓</span>'
                    f'<span style="color:#2d6a4f;font-size:0.88rem;text-decoration:line-through;">{_t}</span>'
                    f'<span style="margin-left:auto;font-size:0.75rem;color:#27ae60;font-weight:600;">RESOLVED</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if _gained:
            for _t in sorted(_gained):
                _gained_rec = next((r for r in _pr.triggered if r.title == _t), None)
                _prio = _gained_rec.priority if _gained_rec else "Medium"
                _pc   = PRIORITY_COLOUR.get(_prio, "#e67e22")
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'background:#fff8f0;border-left:4px solid {_pc};'
                    f'padding:8px 14px;border-radius:6px;margin-bottom:5px;">'
                    f'<span style="color:{_pc};font-size:1rem;">!</span>'
                    f'<span style="color:#7d3c00;font-size:0.88rem;">{_t}</span>'
                    f'<span style="margin-left:auto;font-size:0.75rem;color:{_pc};font-weight:600;">'
                    f'NEW · {_prio.upper()}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if not _resolved and not _gained and not _kept:
            st.success("No recommendations triggered in this scenario — all values within range.")
        elif not _resolved and not _gained:
            st.info(f"Same {len(_kept)} recommendation(s) as the original — try adjusting the sliders more.")

        # Rating changes — only show params that had original data
        _orig_rating_map = {r.parameter: r for r in result.ratings if r.value is not None}
        _play_rating_map = {r.parameter: r for r in _pr.ratings   if r.value is not None}
        # Only compare params that exist in BOTH original and scenario
        _compare_params  = sorted(set(_orig_rating_map) & set(_play_rating_map))

        if _compare_params:
            st.markdown(
                f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1.2px;color:{_GREEN};margin:20px 0 8px 0;">📈 Rating Changes</p>',
                unsafe_allow_html=True,
            )
            # Header row
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:4px 2px;'
                f'font-size:0.72rem;font-weight:700;color:#aaa;text-transform:uppercase;'
                f'letter-spacing:0.8px;border-bottom:2px solid #eee;margin-bottom:4px;">'
                f'<div style="flex:2;">Parameter</div>'
                f'<div style="flex:1.3;">Original</div>'
                f'<div style="flex:0.5;text-align:center;"></div>'
                f'<div style="flex:1.3;">Scenario</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _RATING_ORDER = ["excellent", "good", "average", "below_average",
                             "poor", "elevated", "high"]
            for _param in _compare_params:
                _or   = _orig_rating_map[_param]
                _nr   = _play_rating_map[_param]
                _lbl  = _PARAM_LABELS.get(_param, _param.split("::")[-1])
                _ov   = f"{_or.value:g} {_or.unit}".strip()
                _nv   = f"{_nr.value:g} {_nr.unit}".strip()
                _orat = _or.rating
                _nrat = _nr.rating
                _oc   = RATING_COLOUR.get(_orat, "#aaa")
                _nc   = RATING_COLOUR.get(_nrat, "#aaa")

                if _orat == _nrat:
                    _arrow, _acol, _abg = "↔", "#ccc", "#f7f7f7"
                else:
                    try:
                        _oi = _RATING_ORDER.index(_orat)
                        _ni = _RATING_ORDER.index(_nrat)
                        if _ni < _oi:
                            _arrow, _acol, _abg = "↑", "#27ae60", "#f0fff4"
                        else:
                            _arrow, _acol, _abg = "↓", "#c0392b", "#fff5f5"
                    except ValueError:
                        _arrow, _acol, _abg = "~", "#aaa", "#fafafa"

                _row_bg = _abg if _arrow != "↔" else "transparent"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;'
                    f'padding:7px 8px;border-radius:6px;margin-bottom:2px;'
                    f'background:{_row_bg};font-size:0.85rem;">'
                    f'<div style="flex:2;color:#333;font-weight:500;">{_lbl}</div>'
                    f'<div style="flex:1.3;color:{_oc};">{_ov} '
                    f'<span style="font-size:0.72rem;background:{_oc}18;border-radius:4px;'
                    f'padding:1px 5px;">{_orat.replace("_"," ")}</span></div>'
                    f'<div style="flex:0.5;text-align:center;font-size:1rem;'
                    f'font-weight:700;color:{_acol};">{_arrow}</div>'
                    f'<div style="flex:1.3;color:{_nc};">{_nv} '
                    f'<span style="font-size:0.72rem;background:{_nc}18;border-radius:4px;'
                    f'padding:1px 5px;">{_nrat.replace("_"," ")}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
