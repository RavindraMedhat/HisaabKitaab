import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)
router = APIRouter()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _redirect_uri(request: Request) -> str:
    override = os.getenv("REDIRECT_URI")
    if override:
        return override
    # Render and most proxies set x-forwarded-proto; fall back to ENV check
    proto = request.headers.get("x-forwarded-proto") \
         or ("https" if os.getenv("ENV") == "production" else request.url.scheme)
    host  = request.headers.get("host", "localhost:7485")
    uri   = f"{proto}://{host}/auth/callback"
    import logging; logging.warning(f"[auth] redirect_uri={uri}")
    return uri


def _flow(redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


@router.get("/login")
async def login(request: Request):
    uri  = _redirect_uri(request)
    flow = _flow(uri)
    auth_url, state = flow.authorization_url(prompt="select_account")
    request.session["oauth_state"]  = state
    request.session["redirect_uri"] = uri
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    from services.logger import log_error

    if error or not code:
        log_error("OAuth callback rejected by Google", error=error, code_present=bool(code))
        return RedirectResponse("/?auth_error=1")

    expected = request.session.pop("oauth_state", None)
    if not expected or state != expected:
        log_error("OAuth state mismatch", expected_present=bool(expected), state_present=bool(state))
        return RedirectResponse("/?auth_error=1")

    try:
        uri  = request.session.pop("redirect_uri", None) or _redirect_uri(request)
        flow = _flow(uri)
        flow.fetch_token(code=code)

        info = id_token.verify_oauth2_token(
            flow.credentials.id_token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except Exception as e:
        log_error("OAuth token exchange failed", exc=e, redirect_uri=uri if 'uri' in dir() else "unknown")
        return RedirectResponse("/?auth_error=1")

    user = {
        "uid":     info["sub"],
        "name":    info.get("name", info["email"]),
        "email":   info["email"],
        "picture": info.get("picture", ""),
    }

    from services.firebase import db
    db.collection("users").document(user["uid"]).set(user, merge=True)

    request.session["user"] = user
    return RedirectResponse("/")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
