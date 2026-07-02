import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from services.firebase import db
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _get_google_creds():
    if "google" in st.secrets:
        return st.secrets["google"]["client_id"], st.secrets["google"]["client_secret"]
    return os.getenv("GOOGLE_CLIENT_ID"), os.getenv("GOOGLE_CLIENT_SECRET")


def _get_redirect_uri() -> str:
    try:
        host = st.context.headers.get("Host", "localhost:7485")
        scheme = "https" if "localhost" not in host else "http"
        return f"{scheme}://{host}"
    except Exception:
        return "http://localhost:7485"


def get_google_flow():
    client_id, client_secret = _get_google_creds()
    redirect_uri = _get_redirect_uri()
    return Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def get_login_url() -> str:
    flow = get_google_flow()
    auth_url, state = flow.authorization_url(prompt="select_account")
    st.session_state.oauth_state = state
    return auth_url


def handle_callback(code: str):
    from utils.session import save_login
    flow = get_google_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    client_id, _ = _get_google_creds()

    info = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        client_id,
    )

    user = {
        "uid": info["sub"],
        "name": info.get("name", info["email"]),
        "email": info["email"],
        "picture": info.get("picture", ""),
    }

    db.collection("users").document(user["uid"]).set(user, merge=True)
    save_login(user)


def is_logged_in() -> bool:
    return st.session_state.get("user") is not None
