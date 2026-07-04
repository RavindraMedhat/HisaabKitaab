import os
import hashlib
import base64
import secrets
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

router = APIRouter()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _pkce_pair():
    verifier  = secrets.token_urlsafe(64)
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge


def _redirect_uri(request: Request) -> str:
    override = os.getenv("REDIRECT_URI")
    if override:
        return override
    proto = request.headers.get("x-forwarded-proto") \
         or ("https" if os.getenv("ENV") == "production" else request.url.scheme)
    host  = request.headers.get("host", "localhost:7485")
    return f"{proto}://{host}/auth/callback"


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
    uri               = _redirect_uri(request)
    flow              = _flow(uri)
    verifier, challenge = _pkce_pair()

    auth_url, state = flow.authorization_url(
        prompt="select_account",
        code_challenge=challenge,
        code_challenge_method="S256",
    )

    request.session["oauth_state"]    = state
    request.session["redirect_uri"]   = uri
    request.session["code_verifier"]  = verifier
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

    uri = "unknown"
    try:
        uri      = request.session.pop("redirect_uri", None)  or _redirect_uri(request)
        verifier = request.session.pop("code_verifier", None)
        flow     = _flow(uri)
        flow.fetch_token(code=code, code_verifier=verifier)

        info = id_token.verify_oauth2_token(
            flow.credentials.id_token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except Exception as e:
        log_error("OAuth token exchange failed", exc=e, redirect_uri=uri)
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
