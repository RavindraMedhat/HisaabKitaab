import streamlit as st

_HOME_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12L12 3l9 9v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'
_GROUPS_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>'
_ACCOUNT_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'

STYLES = """
<style>
:root {
  --bg:      #F2F2F7;
  --surface: #FFFFFF;
  --ink:     #1C1C1E;
  --muted:   #8E8E93;
  --border:  #E5E5EA;
  --sep:     rgba(60,60,67,.1);
  --pos:     #34C759;
  --pos-lt:  #E3F9E8;
  --neg:     #FF6B2B;
  --neg-lt:  #FFF0E8;
  --r:       13px;
  --rsm:     9px;
}

*, *::before, *::after { box-sizing: border-box; }

.stApp { background: var(--bg) !important; }

.block-container {
  padding: 0 0 5.5rem !important;
  max-width: 430px !important;
  margin: 0 auto !important;
}

#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="collapsedControl"],
[data-testid="stDecoration"],
[data-testid="stHeader"] { display:none !important; }

[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

/* ── Buttons ── */
div.stButton > button {
  background: var(--neg) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--rsm) !important;
  min-height: 2.75rem !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  width: 100%;
  box-shadow: 0 2px 10px rgba(255,107,43,.28) !important;
  transition: opacity .13s !important;
}
div.stButton > button:hover { opacity:.88 !important; }

.btn-ghost div.stButton > button {
  background: var(--surface) !important;
  color: var(--ink) !important;
  border: 1.5px solid var(--border) !important;
  box-shadow: none !important;
}
.btn-ghost div.stButton > button:hover { background: var(--bg) !important; }

.btn-green div.stButton > button {
  background: var(--pos) !important;
  box-shadow: 0 2px 10px rgba(52,199,89,.28) !important;
}

/* ── Inputs ── */
.stTextInput input, .stNumberInput input, .stTextArea textarea {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--rsm) !important;
  font-size: 1rem !important;
  color: var(--ink) !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
  border-color: var(--neg) !important;
  box-shadow: 0 0 0 3px rgba(255,107,43,.12) !important;
}
.stSelectbox > div > div, .stMultiSelect > div > div {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--rsm) !important;
}
label[data-testid="stWidgetLabel"] p {
  font-size: 0.72rem !important;
  font-weight: 800 !important;
  color: var(--muted) !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
}
[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  overflow: hidden !important;
}
[data-testid="stAlert"] { border-radius: var(--rsm) !important; font-size:.88rem !important; }

/* ── HisaabKitaab components ── */

/* Page header */
.hk-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: .9rem 1rem .75rem;
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; gap: .7rem;
}
.hk-header-title { font-size: 1rem; font-weight: 800; color: var(--ink); flex: 1; }
.hk-back {
  width: 2rem; height: 2rem; border-radius: 50%;
  background: var(--bg); border: none; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 1rem; color: var(--neg); text-decoration: none;
  flex-shrink: 0;
}

/* Banner */
.hk-banner {
  margin: .75rem 1rem;
  padding: 1rem 1.1rem;
  border-radius: var(--r);
  display: flex; align-items: center; justify-content: space-between;
}
.hk-banner-pos { background: var(--pos-lt); }
.hk-banner-neg { background: var(--neg-lt); }
.hk-banner-nil { background: var(--surface); border: 1px solid var(--border); }

/* Card group (iOS table view) */
.hk-group {
  background: var(--surface);
  border-radius: var(--r);
  overflow: hidden;
  margin: 0 1rem .75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}
.hk-row {
  border-bottom: 1px solid var(--sep);
  padding: .85rem 1rem;
  display: flex; align-items: center; gap: .75rem;
}
.hk-row:last-child { border-bottom: none; }

/* Section label */
.hk-section {
  font-size: .68rem; font-weight: 800; color: var(--muted);
  letter-spacing: .1em; text-transform: uppercase;
  padding: .9rem 1rem .35rem;
}

/* Avatar */
.hk-av {
  width: 2.2rem; height: 2.2rem; border-radius: 50%;
  background: var(--neg-lt); color: var(--neg);
  font-weight: 800; font-size: .78rem;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0; letter-spacing: .02em;
}
.hk-av-pos { background: var(--pos-lt); color: var(--pos); }
.hk-av-nil { background: var(--bg); color: var(--muted); }

/* Amount text */
.hk-amt { font-variant-numeric: tabular-nums; font-weight: 800; }
.hk-pos { color: var(--pos); }
.hk-neg { color: var(--neg); }
.hk-ink { color: var(--ink); }
.hk-muted { color: var(--muted); font-size: .85rem; }

/* Pill badge */
.hk-pill {
  display: inline-block; padding: 2px 9px; border-radius: 20px;
  font-size: .72rem; font-weight: 800; letter-spacing: .02em; white-space: nowrap;
}
.hk-pill-pos { background: var(--pos-lt); color: var(--pos); }
.hk-pill-neg { background: var(--neg-lt); color: var(--neg); }
.hk-pill-nil { background: var(--bg); color: var(--muted); }

/* Bottom nav */
.hk-nav {
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 3.6rem;
  background: rgba(255,255,255,.96);
  backdrop-filter: blur(14px);
  border-top: 1px solid var(--border);
  display: flex; align-items: center;
  z-index: 9999;
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.hk-nav a {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 2px;
  text-decoration: none; color: var(--muted);
  font-size: .58rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  -webkit-tap-highlight-color: transparent;
  padding: .3rem 0;
}
.hk-nav a svg { width: 1.3rem; height: 1.3rem; }
.hk-nav a.on { color: var(--neg); }
.hk-nav .hk-add-wrap { flex: 1; display:flex; align-items:center; justify-content:center; }
.hk-add-btn {
  width: 2.8rem; height: 2.8rem; border-radius: 50%;
  background: linear-gradient(135deg,#FF6B2B,#FF9850);
  color: #fff; font-size: 1.6rem; font-weight: 300;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 14px rgba(255,107,43,.42);
  text-decoration: none; margin-top: -4px;
  -webkit-tap-highlight-color: transparent;
}

@media (prefers-reduced-motion:reduce) { * { transition:none !important; } }
</style>
"""


def apply_styles():
    st.markdown(STYLES, unsafe_allow_html=True)


def bottom_nav(active: str = ""):
    items = [
        ("home",    "/Dashboard",   _HOME_ICON,    "Home"),
        ("groups",  "/Groups",      _GROUPS_ICON,  "Groups"),
        ("add",     "/Add_Expense", None,           ""),
        ("account", "/Account",     _ACCOUNT_ICON, "Account"),
    ]
    nav_html = '<nav class="hk-nav">'
    for key, href, icon, label in items:
        if key == "add":
            on_cls = " on" if active == "add" else ""
            nav_html += (
                f'<div class="hk-add-wrap">'
                f'<a href="{href}" class="hk-add-btn{on_cls}" title="Add expense">+</a>'
                f'</div>'
            )
        else:
            cls = " on" if active == key else ""
            nav_html += f'<a href="{href}" class="{cls}">{icon}<span>{label}</span></a>'
    nav_html += "</nav>"
    st.markdown(nav_html, unsafe_allow_html=True)


def fmt_amount(amount: float) -> str:
    return f"₹{abs(amount):,.0f}" if abs(amount) == int(abs(amount)) else f"₹{abs(amount):,.2f}"


def balance_pill(amount: float) -> str:
    if amount > 0.01:
        return f'<span class="hk-pill hk-pill-pos">+{fmt_amount(amount)}</span>'
    if amount < -0.01:
        return f'<span class="hk-pill hk-pill-neg">−{fmt_amount(amount)}</span>'
    return '<span class="hk-pill hk-pill-nil">Settled</span>'


def balance_text(amount: float) -> str:
    if amount > 0.01:
        return f'<span class="hk-amt hk-pos">+{fmt_amount(amount)}</span>'
    if amount < -0.01:
        return f'<span class="hk-amt hk-neg">−{fmt_amount(amount)}</span>'
    return '<span class="hk-muted">All settled up</span>'


def avatar(name: str, style: str = "") -> str:
    initials = "".join(w[0].upper() for w in name.split() if w)[:2] or "?"
    cls = f"hk-av {style}".strip()
    return f'<div class="{cls}">{initials}</div>'


def require_login():
    from utils.session import restore_login
    restore_login()
    if not st.session_state.get("user"):
        apply_styles()
        st.markdown("""
        <div style="padding:2rem 1rem;text-align:center">
          <div style="font-size:2.5rem">📒</div>
          <div style="font-weight:800;font-size:1.1rem;margin:.5rem 0;color:#1C1C1E">Sign in to continue</div>
        </div>""", unsafe_allow_html=True)
        st.page_link("Home.py", label="Go to sign in →")
        st.stop()
