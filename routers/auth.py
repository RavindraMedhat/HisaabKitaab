import re
import secrets
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from google.cloud.firestore_v1 import ArrayUnion

from services.firebase import db

router = APIRouter()

UPI_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")


def normalize_mobile(raw: str) -> str:
    """Indian mobile → 10 digits (accepts +91 / 0 prefixes, spaces, dashes)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) > 10:
        digits = digits[-10:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(400, "Enter a valid 10-digit mobile number")
    return digits


def connect_everyone(me: str):
    """Group-only app: every account is automatically friends with every other account."""
    others = {}
    my_friends = set()
    for d in db.collection("users").stream():
        data = d.to_dict() or {}
        if d.id == me:
            my_friends = set(data.get("friends", []))
        else:
            others[d.id] = set(data.get("friends", []))
    missing = [u for u in others if u not in my_friends]
    if missing:
        db.collection("users").document(me).set({"friends": ArrayUnion(missing)}, merge=True)
    for u, their in others.items():
        if me not in their:
            db.collection("users").document(u).set({"friends": ArrayUnion([me])}, merge=True)


class LoginBody(BaseModel):
    mobile: str
    password: str
    name: Optional[str] = None
    upi: Optional[str] = None


@router.post("/login")
async def login(body: LoginBody, request: Request):
    mobile = normalize_mobile(body.mobile)
    password = body.password or ""
    if len(password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    ref = db.collection("users").document(mobile)
    doc = ref.get()

    if doc.exists:
        user = doc.to_dict()
        stored = user.get("password")
        if stored is None:                      # account created before passwords existed
            ref.set({"password": password}, merge=True)
        elif not secrets.compare_digest(str(stored).encode(), password.encode()):
            raise HTTPException(401, "Wrong mobile number or password")
    else:
        name = (body.name or "").strip()
        if not name:
            return {"needs_name": True}
        if len(name) > 40:
            raise HTTPException(400, "Name must be 40 characters or fewer")
        upi = (body.upi or "").strip()
        if upi and not UPI_RE.match(upi):
            raise HTTPException(400, "That doesn't look like a UPI ID (example: name@oksbi)")
        user = {"uid": mobile, "name": name, "mobile": mobile, "upi": upi, "password": password}
        ref.set(user)

    connect_everyone(mobile)
    request.session["user"] = {"uid": user["uid"], "name": user["name"], "mobile": mobile}
    return {"ok": True}


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
