"""Solo Enterprise Agentgateway – UI theme injection."""

import streamlit as st

_SOLO_CSS = """
<style>
/* ─── Core palette ──────────────────────────────────────────────────────── */
:root {
  --bg-deepest:   #090c14;
  --bg-dark:      #0f1420;
  --bg-surface:   #141b2a;
  --bg-elevated:  #1a2235;
  --border:       #1e2840;
  --border-light: #253050;
  --text-primary: #dde3f0;
  --text-muted:   #7880a0;
  --text-dim:     #4a5270;
  --green:        #1dc98a;
  --green-glow:   rgba(29, 201, 138, 0.12);
  --purple:       #7c5cf6;
  --purple-glow:  rgba(124, 92, 246, 0.15);
  --purple-bg:    rgba(124, 92, 246, 0.10);
  --blue:         #3d7ef8;
  --blue-glow:    rgba(61, 126, 248, 0.12);
  --amber:        #f0a742;
  --red:          #e84444;
  --radius:       6px;
}

/* ─── App shell ─────────────────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"] {
  background-color: var(--bg-deepest) !important;
}

/* Header bar */
[data-testid="stHeader"] {
  background-color: var(--bg-dark) !important;
  border-bottom: 1px solid var(--border) !important;
}

/* Main content block */
[data-testid="block-container"] {
  background-color: var(--bg-deepest);
  padding-top: 1.5rem !important;
}

/* ─── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background-color: var(--bg-dark) !important;
  border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.25rem;
}

/* Sidebar nav items */
[data-testid="stSidebarNav"] a {
  color: var(--text-muted) !important;
  border-radius: var(--radius);
  transition: background 0.15s, color 0.15s;
}

[data-testid="stSidebarNav"] a:hover {
  background-color: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
}

[data-testid="stSidebarNav"] a[aria-current="page"] {
  background-color: var(--purple-bg) !important;
  color: var(--text-primary) !important;
  border-left: 2px solid var(--purple) !important;
}

/* Sidebar title */
[data-testid="stSidebar"] h1 {
  color: var(--green) !important;
  font-size: 0.95rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-weight: 600 !important;
  margin-bottom: 0.75rem !important;
}

/* ─── Typography ─────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2,
[data-testid="stMarkdown"] h3 {
  color: var(--text-primary) !important;
  font-weight: 600 !important;
  letter-spacing: -0.01em;
}

h1 { border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }

p, li, .stMarkdown p { color: var(--text-primary); }

/* Caption / small text */
.stCaption, [data-testid="stCaptionContainer"] p, small {
  color: var(--text-muted) !important;
}

/* Dividers */
hr, .stDivider {
  border-color: var(--border) !important;
}

/* ─── Buttons ────────────────────────────────────────────────────────────── */
.stButton > button {
  border-radius: var(--radius) !important;
  font-weight: 500 !important;
  font-size: 0.85rem !important;
  transition: all 0.15s ease !important;
}

/* Primary = solid green */
.stButton > button[kind="primary"] {
  background-color: var(--green) !important;
  color: #040609 !important;
  border: none !important;
}

.stButton > button[kind="primary"]:hover {
  background-color: #25e09a !important;
  box-shadow: 0 0 16px var(--green-glow) !important;
}

/* Secondary = outlined green */
.stButton > button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
  background-color: transparent !important;
  color: var(--green) !important;
  border: 1px solid var(--border-light) !important;
}

.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind="primary"]):hover {
  border-color: var(--green) !important;
  background-color: var(--green-glow) !important;
}

/* ─── Form inputs ────────────────────────────────────────────────────────── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox select,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-primary) !important;
  border-radius: var(--radius) !important;
}

.stTextInput input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus,
[data-testid="stTextInput"] input:focus {
  border-color: var(--green) !important;
  box-shadow: 0 0 0 2px var(--green-glow) !important;
}

/* Labels */
.stTextInput label,
.stTextArea label,
.stNumberInput label,
.stSelectbox label,
[data-testid="stWidgetLabel"] {
  color: var(--text-muted) !important;
  font-size: 0.8rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  font-weight: 500 !important;
}

/* Selectbox / dropdown */
[data-testid="stSelectbox"] > div > div {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text-primary) !important;
}

[data-testid="stSelectbox"] svg { color: var(--text-muted) !important; }

/* ─── Tabs ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important;
}

[data-testid="stTabs"] [role="tab"] {
  color: var(--text-muted) !important;
  border-radius: var(--radius) var(--radius) 0 0 !important;
  padding: 0.5rem 1.25rem !important;
  font-size: 0.85rem !important;
  font-weight: 500 !important;
  transition: color 0.15s !important;
}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--purple) !important;
  border-bottom: 2px solid var(--purple) !important;
  background: transparent !important;
}

[data-testid="stTabs"] [role="tab"]:hover {
  color: var(--text-primary) !important;
  background-color: var(--bg-elevated) !important;
}

/* Tab content */
[data-testid="stTabsContent"] {
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius) var(--radius);
  padding: 1rem;
  background-color: var(--bg-dark);
}

/* ─── Expanders ─────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background-color: var(--bg-dark) !important;
}

[data-testid="stExpander"] summary {
  color: var(--text-primary) !important;
  background-color: var(--bg-surface) !important;
  border-radius: var(--radius) !important;
  padding: 0.6rem 0.9rem !important;
}

[data-testid="stExpander"] summary:hover {
  background-color: var(--bg-elevated) !important;
}

[data-testid="stExpander"] summary svg {
  color: var(--green) !important;
}

/* ─── Metric widgets ─────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 0.75rem 1rem !important;
}

[data-testid="metric-container"] [data-testid="stMetricLabel"] {
  color: var(--text-muted) !important;
  font-size: 0.75rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-size: 1.6rem !important;
  font-weight: 600 !important;
}

[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {
  color: var(--green) !important;
}

/* ─── Code / pre ─────────────────────────────────────────────────────────── */
.stCodeBlock,
[data-testid="stCodeBlock"] {
  background-color: #070a12 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
}

[data-testid="stCode"] pre,
[data-testid="stCode"] code,
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] code,
.stCodeBlock pre,
.stCode pre {
  font-size: 14px !important;
}

code {
  background-color: var(--bg-surface) !important;
  color: var(--green) !important;
  padding: 0.1em 0.35em !important;
  border-radius: 3px !important;
  font-size: 0.88em !important;
}

/* ─── Alert / status boxes ──────────────────────────────────────────────── */
/* Success */
[data-testid="stAlert"][data-baseweb="notification"]:has([data-testid="stAlertContentSuccess"]),
div[data-testid="stNotificationContentSuccess"],
.stSuccess {
  background-color: rgba(29, 201, 138, 0.08) !important;
  border-left: 3px solid var(--green) !important;
  border-radius: var(--radius) !important;
}

/* Info */
[data-testid="stAlert"][data-baseweb="notification"]:has([data-testid="stAlertContentInfo"]),
.stInfo {
  background-color: var(--purple-bg) !important;
  border-left: 3px solid var(--purple) !important;
  border-radius: var(--radius) !important;
}

/* Warning */
.stWarning {
  background-color: rgba(240, 167, 66, 0.08) !important;
  border-left: 3px solid var(--amber) !important;
  border-radius: var(--radius) !important;
}

/* Error */
.stError {
  background-color: rgba(232, 68, 68, 0.08) !important;
  border-left: 3px solid var(--red) !important;
  border-radius: var(--radius) !important;
}

/* ─── Tables / DataFrames ────────────────────────────────────────────────── */
[data-testid="stTable"] table,
.stDataFrame {
  background-color: var(--bg-dark) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
}

[data-testid="stTable"] th {
  background-color: var(--bg-surface) !important;
  color: var(--text-muted) !important;
  font-size: 0.75rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  border-bottom: 1px solid var(--border) !important;
}

[data-testid="stTable"] td {
  color: var(--text-primary) !important;
  border-color: var(--border) !important;
}

[data-testid="stTable"] tr:hover td {
  background-color: var(--bg-elevated) !important;
}

/* ─── Spinner ────────────────────────────────────────────────────────────── */
.stSpinner > div {
  border-top-color: var(--green) !important;
}

/* ─── Checkbox / Radio ───────────────────────────────────────────────────── */
[data-testid="stCheckbox"] input:checked + span,
[data-testid="stRadio"] input:checked + span {
  background-color: var(--green) !important;
  border-color: var(--green) !important;
}

/* ─── Progress bar ───────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
  background-color: var(--green) !important;
}

/* ─── Hide deploy button ─────────────────────────────────────────────────── */
[data-testid="stHeaderActionButton"],
.stDeployButton,
.stAppDeployButton {
  display: none !important;
}

/* ─── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-deepest); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }
</style>
"""


def inject_theme() -> None:
    """Inject the Solo Enterprise Agentgateway dark theme CSS.

    Call this once per page. render_sidebar() calls it automatically,
    so only pages that skip render_sidebar() need to call this directly
    via setup_page().
    """
    st.markdown(_SOLO_CSS, unsafe_allow_html=True)


def setup_page() -> None:
    """Standard page setup for pages that don't use render_sidebar().

    Equivalent to the theme injection render_sidebar() performs.
    """
    inject_theme()
