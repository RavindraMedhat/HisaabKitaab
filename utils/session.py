import streamlit as st
import json
from datetime import datetime, timedelta
import extra_streamlit_components as stx


def get_cookie_manager():
    return stx.CookieManager(key="hk_cm")


def save_login(user: dict):
    cm = get_cookie_manager()
    cm.set("hk_user", json.dumps(user), expires_at=datetime.now() + timedelta(days=7))
    st.session_state.user = user
    st.session_state.user_id = user["uid"]


def restore_login():
    if st.session_state.get("user"):
        return
    cm = get_cookie_manager()
    raw = cm.get("hk_user")
    if raw:
        try:
            user = json.loads(raw)
            st.session_state.user = user
            st.session_state.user_id = user["uid"]
        except Exception:
            pass


def clear_login():
    cm = get_cookie_manager()
    cm.delete("hk_user")
    st.session_state.user = None
    st.session_state.user_id = None
