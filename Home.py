import streamlit as st
from services.auth import get_login_url, handle_callback
from utils.session import restore_login, clear_login
from utils.ui import apply_styles

st.set_page_config(page_title="HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()
restore_login()

# Handle Google OAuth callback
query_params = st.query_params
if "code" in query_params and not st.session_state.get("user"):
    with st.spinner("Signing you in..."):
        handle_callback(query_params["code"])
    st.query_params.clear()
    st.rerun()

if not st.session_state.get("user"):
    st.markdown("<h1 style='text-align:center'>📒 HisaabKitaab</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Apka Hisaab, Apki Kitaab</p>", unsafe_allow_html=True)
    st.markdown("---")
    login_url = get_login_url()
    st.link_button("🔵  Sign in with Google", login_url, use_container_width=True)

else:
    user = st.session_state.user
    col1, col2 = st.columns([1, 4])
    with col1:
        if user.get("picture"):
            st.image(user["picture"], width=52)
    with col2:
        st.markdown(f"**{user['name']}**")
        st.caption(user["email"])

    st.markdown("---")
    st.page_link("pages/1_Groups.py",   label="👥  My Groups",   use_container_width=True)
    st.page_link("pages/2_Expenses.py", label="💸  Add Expense", use_container_width=True)
    st.page_link("pages/3_Balances.py", label="📊  Balances",    use_container_width=True)
    st.markdown("---")

    if st.button("Logout", use_container_width=True):
        clear_login()
        st.rerun()
