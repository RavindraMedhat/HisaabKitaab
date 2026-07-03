import streamlit as st
from utils.ui import apply_styles, bottom_nav, avatar
from utils.session import restore_login, clear_login

st.set_page_config(page_title="Account · HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()
restore_login()

if not st.session_state.get("user"):
    st.switch_page("Home.py")

user = st.session_state["user"]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hk-header">
  <div class="hk-header-title" style="font-size:1.1rem">Account</div>
</div>""", unsafe_allow_html=True)

# ── Profile card ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hk-group" style="margin-top:.75rem">
  <div class="hk-row" style="gap:1rem">
    <div style="position:relative">
      {"<img src='" + user['picture'] + "' width='52' height='52' style='border-radius:50%;object-fit:cover'>" if user.get("picture") else avatar(user["name"])}
    </div>
    <div>
      <div style="font-weight:800;font-size:1.05rem;color:#1C1C1E">{user["name"]}</div>
      <div style="font-size:.85rem;color:#8E8E93">{user["email"]}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── App info ──────────────────────────────────────────────────────────────────
st.markdown('<div class="hk-section">About</div>', unsafe_allow_html=True)
st.markdown("""
<div class="hk-group">
  <div class="hk-row" style="justify-content:space-between">
    <span style="color:#1C1C1E;font-weight:600">App</span>
    <span style="color:#8E8E93">HisaabKitaab</span>
  </div>
  <div class="hk-row" style="justify-content:space-between">
    <span style="color:#1C1C1E;font-weight:600">Version</span>
    <span style="color:#8E8E93">2.0</span>
  </div>
  <div class="hk-row" style="justify-content:space-between">
    <span style="color:#1C1C1E;font-weight:600">Login</span>
    <span style="color:#8E8E93">Google</span>
  </div>
</div>""", unsafe_allow_html=True)

# ── Sign out ──────────────────────────────────────────────────────────────────
st.markdown('<div class="hk-section"></div>', unsafe_allow_html=True)
st.markdown('<div style="padding:0 1rem">', unsafe_allow_html=True)
st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
if st.button("Sign out", key="signout"):
    clear_login()
    st.switch_page("Home.py")
st.markdown("</div></div>", unsafe_allow_html=True)

bottom_nav("account")
