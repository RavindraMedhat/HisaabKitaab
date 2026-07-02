import streamlit as st


def apply_styles():
    st.markdown("""
    <style>
    /* ── Base mobile-first layout ── */
    .block-container {
        padding: 1.5rem 1rem 3rem !important;
        max-width: 480px !important;
    }

    /* ── Touch-friendly buttons ── */
    .stButton > button,
    .stLinkButton > a {
        min-height: 3rem !important;
        font-size: 1rem !important;
        border-radius: 0.6rem !important;
        font-weight: 500 !important;
    }

    /* ── Inputs ── */
    .stTextInput input,
    .stNumberInput input,
    .stSelectbox select {
        font-size: 1rem !important;
        min-height: 2.8rem !important;
    }

    /* ── Hide footer ── */
    footer { visibility: hidden; }

    /* ── Readable text on mobile ── */
    p, label, div[data-testid="stMarkdownContainer"] {
        font-size: 0.97rem !important;
    }

    /* ── Card-style expanders ── */
    .streamlit-expanderHeader {
        font-size: 1rem !important;
        font-weight: 600 !important;
    }

    /* ── Sidebar: full screen on mobile ── */
    @media (max-width: 640px) {
        section[data-testid="stSidebar"] {
            width: 85vw !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def require_login():
    """Call at top of every page. Redirects to login if not authenticated."""
    from utils.session import restore_login
    restore_login()
    if not st.session_state.get("user"):
        st.warning("Please sign in first.")
        st.page_link("Home.py", label="Go to Login", icon="🔑")
        st.stop()
