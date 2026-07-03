import streamlit as st
from services.auth import get_login_url, handle_callback
from utils.session import restore_login
from utils.ui import apply_styles, STYLES

st.set_page_config(page_title="HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()

in_auth_flow = "code" in st.query_params or st.session_state.get("auth_code")
if not in_auth_flow:
    restore_login()

# Stage OAuth code to survive Streamlit's rerun-on-param-clear
if "code" in st.query_params and not st.session_state.get("auth_code"):
    st.session_state.auth_code = st.query_params["code"]
    st.query_params.clear()
    st.rerun()

if st.session_state.get("auth_code") and not st.session_state.get("user"):
    code = st.session_state.pop("auth_code")
    try:
        with st.spinner("Signing you in…"):
            handle_callback(code)
        st.switch_page("pages/1_Dashboard.py")
    except Exception as e:
        st.error(f"Sign-in failed — please try again. ({e})")

if st.session_state.get("user"):
    st.switch_page("pages/1_Dashboard.py")

# ── Login screen ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="min-height:48vh;display:flex;flex-direction:column;
            align-items:center;justify-content:center;padding:2rem 1.5rem 1rem;text-align:center">
  <div style="font-size:4.5rem;line-height:1;margin-bottom:1rem">📒</div>
  <div style="font-size:2.2rem;font-weight:900;color:#1C1C1E;
              letter-spacing:-0.04em;line-height:1.1">HisaabKitaab</div>
  <div style="font-size:0.9rem;color:#8E8E93;margin-top:.5rem;font-weight:500">
    Split expenses. Stay friends.
  </div>
</div>
""", unsafe_allow_html=True)

login_url = get_login_url()
st.markdown(f"""
<div style="padding:0 1rem 1rem">
  <a href="{login_url}" style="
      display:flex;align-items:center;justify-content:center;gap:.8rem;
      background:#fff;border:1.5px solid #E5E5EA;border-radius:11px;
      padding:.9rem 1.2rem;text-decoration:none;
      color:#1C1C1E;font-weight:700;font-size:.97rem;
      box-shadow:0 2px 10px rgba(0,0,0,.08);
      -webkit-tap-highlight-color:transparent;">
    <svg width="20" height="20" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.36-8.16 2.36-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
    Continue with Google
  </a>
</div>
<div style="text-align:center;font-size:.73rem;color:#8E8E93;padding:0 2rem">
  By continuing you agree to pay your friends back on time.
</div>
""", unsafe_allow_html=True)
