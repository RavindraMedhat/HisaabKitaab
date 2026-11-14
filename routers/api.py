import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from google.cloud import firestore
from google.cloud.firestore_v1 import ArrayUnion, ArrayRemove
from pydantic import BaseModel

from services.firebase import db
from services.calculator import expense_shares, pair_balances
from routers.auth import normalize_mobile, UPI_RE

router = APIRouter()

MAX_DESC   = 200
MAX_AMOUNT = 1_000_000   # ₹10 lakh hard cap
TAG_RE     = re.compile(r"#([A-Za-z0-9_]{1,24})")

CATEGORIES = [
    ("Food",          r"dinner|lunch|breakfast|food|restaurant|biryani|pizza|burger|meal|thali|cafe|chai|tea|coffee|snack"),
    ("Drinks",        r"drink|beer|bar\b|pub|wine|alcohol|cocktail"),
    ("Travel",        r"cab|uber|ola|taxi|auto|metro|bus|train|flight|ticket"),
    ("Fuel & tolls",  r"petrol|diesel|fuel|toll|parking"),
    ("Stay",          r"hotel|stay|room|resort|airbnb|hostel"),
    ("Fun",           r"movie|show|entry|park|ride|game|party|birthday|garba"),
    ("Groceries",     r"grocer|milk|veg|mart|bigbasket|blinkit|zepto"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _user(request: Request) -> dict:
    u = request.session.get("user")
    if not u:
        raise HTTPException(401, "Not authenticated")
    return u


def _uid(request: Request) -> str:
    return _user(request)["uid"]


def _ser(d: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}


def _tags(*texts) -> list:
    seen = []
    for t in texts:
        for m in TAG_RE.findall(t or ""):
            m = m.lower()
            if m not in seen:
                seen.append(m)
    return seen[:8]


def _category(desc: str) -> str:
    for name, pat in CATEGORIES:
        if re.search(pat, desc or "", re.I):
            return name
    return "Other"


def _user_doc(uid: str) -> dict:
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


def _profile(uid: str) -> dict:
    d = _user_doc(uid)
    return {"uid": uid, "name": d.get("name", uid), "mobile": d.get("mobile", uid), "upi": d.get("upi", "")}


def _my_expenses(uid: str) -> list:
    rows = [_ser({**d.to_dict(), "id": d.id})
            for d in db.collection("expenses").where("participants", "array_contains", uid).stream()]
    rows.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return rows


def _my_settlements(uid: str) -> list:
    rows = [_ser({**d.to_dict(), "id": d.id})
            for d in db.collection("settlements").where("participants", "array_contains", uid).stream()]
    rows.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return rows


def _names(rows: list) -> dict:
    ids = set()
    for r in rows:
        ids.update(r.get("participants", []))
    return {u: _profile(u)["name"] for u in ids}


def _friend_ids(uid: str) -> list:
    return _user_doc(uid).get("friends", [])


def _require_friend(uid: str, other: str):
    if other not in _friend_ids(uid):
        raise HTTPException(403, "That person is not in your friends list")


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    u = _user(request)
    return {**u, "upi": _user_doc(u["uid"]).get("upi", "")}


class UpiBody(BaseModel):
    upi: str


@router.put("/me/upi")
async def set_upi(body: UpiBody, request: Request):
    uid = _uid(request)
    upi = body.upi.strip()
    if upi and not UPI_RE.match(upi):
        raise HTTPException(400, "That doesn't look like a UPI ID (example: name@oksbi)")
    db.collection("users").document(uid).set({"upi": upi}, merge=True)
    return {"upi": upi}


# ── Friends ───────────────────────────────────────────────────────────────────

@router.get("/friends")
async def list_friends(request: Request):
    uid  = _uid(request)
    bals = pair_balances(_my_expenses(uid), _my_settlements(uid), uid)
    out  = []
    for fid in _friend_ids(uid):
        p = _profile(fid)
        p["balance"] = bals.get(fid, 0.0)
        out.append(p)
    out.sort(key=lambda f: (-abs(f["balance"]), f["name"].lower()))
    return out


class FriendBody(BaseModel):
    mobile: str


@router.post("/friends", status_code=201)
async def add_friend(body: FriendBody, request: Request):
    uid    = _uid(request)
    mobile = normalize_mobile(body.mobile)
    if mobile == uid:
        raise HTTPException(400, "That's your own number")
    doc = db.collection("users").document(mobile).get()
    if not doc.exists:
        raise HTTPException(404, "No HisaabKitaab account for that number yet. Ask them to open the app and sign in once.")
    db.collection("users").document(uid).set({"friends": ArrayUnion([mobile])}, merge=True)
    db.collection("users").document(mobile).set({"friends": ArrayUnion([uid])}, merge=True)
    return _profile(mobile)


@router.delete("/friends/{fid}", status_code=204)
async def remove_friend(fid: str, request: Request):
    uid = _uid(request)
    bals = pair_balances(_my_expenses(uid), _my_settlements(uid), uid)
    if abs(bals.get(fid, 0)) > 0.01:
        raise HTTPException(400, "Settle up before removing this friend")
    db.collection("users").document(uid).set({"friends": ArrayRemove([fid])}, merge=True)
    db.collection("users").document(fid).set({"friends": ArrayRemove([uid])}, merge=True)


@router.get("/friends/{fid}")
async def friend_detail(fid: str, request: Request):
    uid = _uid(request)
    _require_friend(uid, fid)
    exps = [e for e in _my_expenses(uid) if fid in e.get("participants", [])]
    sett = [s for s in _my_settlements(uid) if fid in s.get("participants", [])]
    bal  = pair_balances(exps, sett, uid).get(fid, 0.0)
    me   = _profile(uid)
    return {"friend": _profile(fid), "me": me, "balance": bal, "expenses": exps, "settlements": sett, "uid": uid,
            "names": {uid: me["name"], fid: _profile(fid)["name"]}}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(request: Request):
    uid  = _uid(request)
    exps = _my_expenses(uid)
    sett = _my_settlements(uid)
    bals = pair_balances(exps, sett, uid)
    owed = sum(v for v in bals.values() if v > 0)
    owe  = -sum(v for v in bals.values() if v < 0)
    names = {}
    def nm(u):
        if u not in names:
            names[u] = _profile(u)["name"]
        return names[u]
    items = [{**e, "type": "expense", "payer_name": nm(e.get("paid_by", ""))} for e in exps[:10]]
    for s in sett[:6]:
        items.append({**s, "type": "settlement", "from_name": nm(s["from_uid"]), "to_name": nm(s["to_uid"])})
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"net_balance": round(owed - owe, 2), "owed": round(owed, 2), "owe": round(owe, 2),
            "activity": items[:12], "uid": uid, "friend_count": len(_friend_ids(uid)),
            "names": _names(exps[:10])}


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseBody(BaseModel):
    description:   str
    amount:        float
    paid_by:       str
    split_among:   list[str]
    split_amounts: Optional[dict[str, float]] = None
    note:          Optional[str] = ""


def _validate_expense(body: ExpenseBody, uid: str):
    desc = body.description.strip()
    if not desc:
        raise HTTPException(400, "Description cannot be empty")
    if len(desc) > MAX_DESC:
        raise HTTPException(400, f"Description must be {MAX_DESC} characters or fewer")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be greater than 0")
    if body.amount > MAX_AMOUNT:
        raise HTTPException(400, f"Amount cannot exceed ₹{MAX_AMOUNT:,}")
    if not body.split_among:
        raise HTTPException(400, "Select at least one person to split among")

    amount = round(body.amount, 2)
    split  = list(dict.fromkeys(body.split_among))
    amounts = None
    if body.split_amounts:
        amounts = {u: round(a, 2) for u, a in body.split_amounts.items() if a and a > 0}
        if not amounts:
            raise HTTPException(400, "Enter an amount for at least one person")
        if abs(sum(amounts.values()) - amount) > 0.05:
            raise HTTPException(400, f"Split amounts add up to ₹{sum(amounts.values()):,.2f}, not ₹{amount:,.2f}")
        split = list(amounts.keys())

    participants = list(dict.fromkeys(split + [body.paid_by]))
    if uid not in participants:
        raise HTTPException(400, "You must be part of the expense (as payer or in the split)")
    friends = set(_friend_ids(uid)) | {uid}
    if any(p not in friends for p in participants):
        raise HTTPException(400, "Everyone in an expense must be you or one of your friends")
    return desc, amount, split, amounts, participants


@router.post("/expenses", status_code=201)
async def add_expense(body: ExpenseBody, request: Request):
    uid = _uid(request)
    desc, amount, split, amounts, parts = _validate_expense(body, uid)
    note = (body.note or "").strip()[:200]
    doc = {
        "description": desc, "amount": amount, "paid_by": body.paid_by,
        "split_among": split, "participants": parts, "note": note,
        "tags": _tags(desc, note), "created_by": uid, "created_at": _now(),
    }
    if amounts:
        doc["split_amounts"] = amounts
    _, ref = db.collection("expenses").add(doc)
    return {"id": ref.id}


def _own_expense(eid: str, uid: str):
    ref = db.collection("expenses").document(eid)
    doc = ref.get()
    if not doc.exists or uid not in doc.to_dict().get("participants", []):
        raise HTTPException(404, "Expense not found")
    e = doc.to_dict()
    if e.get("created_by") != uid and e.get("paid_by") != uid:
        raise HTTPException(403, "Only the person who added or paid for this can change it")
    return ref


@router.get("/expenses/{eid}")
async def get_expense(eid: str, request: Request):
    uid = _uid(request)
    doc = db.collection("expenses").document(eid).get()
    if not doc.exists or uid not in doc.to_dict().get("participants", []):
        raise HTTPException(404, "Expense not found")
    e = _ser({**doc.to_dict(), "id": doc.id})
    return {**e, "names": _names([e]), "friends": [_profile(f) for f in _friend_ids(uid)]}


@router.put("/expenses/{eid}")
async def edit_expense(eid: str, body: ExpenseBody, request: Request):
    uid = _uid(request)
    ref = _own_expense(eid, uid)
    desc, amount, split, amounts, parts = _validate_expense(body, uid)
    note = (body.note or "").strip()[:200]
    ref.update({
        "description": desc, "amount": amount, "paid_by": body.paid_by,
        "split_among": split, "participants": parts, "note": note, "tags": _tags(desc, note),
        "split_amounts": amounts if amounts else firestore.DELETE_FIELD,
        "updated_by": uid, "updated_at": _now(),
    })
    return {"ok": True}


@router.delete("/expenses/{eid}", status_code=204)
async def delete_expense(eid: str, request: Request):
    _own_expense(eid, _uid(request)).delete()


# ── Settlements ───────────────────────────────────────────────────────────────

class SettleBody(BaseModel):
    from_uid: str
    to_uid:   str
    amount:   float
    note:     Optional[str] = ""     # optional free text, hashtags become labels


@router.post("/settlements", status_code=201)
async def add_settlement(body: SettleBody, request: Request):
    uid = _uid(request)
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be greater than 0")
    if body.amount > MAX_AMOUNT:
        raise HTTPException(400, f"Amount cannot exceed ₹{MAX_AMOUNT:,}")
    if body.from_uid == body.to_uid or uid not in (body.from_uid, body.to_uid):
        raise HTTPException(403, "You can only record payments between you and a friend")
    other = body.to_uid if body.from_uid == uid else body.from_uid
    _require_friend(uid, other)

    bal = pair_balances(_my_expenses(uid), _my_settlements(uid), uid).get(other, 0.0)
    debt = -bal if body.from_uid == uid else bal   # what the payer actually owes
    if debt < 0.01:
        raise HTTPException(400, "Nothing is owed between you two right now")
    if round(body.amount, 2) > round(debt, 2):
        raise HTTPException(400, f"That's more than the ₹{debt:,.2f} owed")

    note = (body.note or "").strip()[:200]
    _, ref = db.collection("settlements").add({
        "from_uid": body.from_uid, "to_uid": body.to_uid, "amount": round(body.amount, 2),
        "participants": [body.from_uid, body.to_uid], "note": note, "tags": _tags(note),
        "created_by": uid, "created_at": _now(),
    })
    return {"id": ref.id}


# ── Insights ──────────────────────────────────────────────────────────────────

@router.get("/insights")
async def insights(request: Request, days: int = 0):
    uid  = _uid(request)
    exps = _my_expenses(uid)
    sett = _my_settlements(uid)
    if days > 0:
        cutoff = (datetime.now(timezone.utc).timestamp() - days * 86400)
        keep = lambda r: r.get("created_at") and datetime.fromisoformat(r["created_at"]).timestamp() >= cutoff
        exps = [e for e in exps if keep(e)]
        sett = [s for s in sett if keep(s)]

    by_cat, by_tag, by_month = defaultdict(float), defaultdict(lambda: [0.0, 0]), defaultdict(float)
    by_friend = defaultdict(lambda: {"shared": 0.0, "count": 0})
    my_spend = paid = 0.0
    biggest = []
    for e in exps:
        mine = expense_shares(e).get(uid, 0.0)
        my_spend += mine
        if e.get("paid_by") == uid:
            paid += e["amount"]
        if mine > 0:
            by_cat[_category(e.get("description"))] += mine
            for t in e.get("tags", []):
                by_tag[t][0] += mine
                by_tag[t][1] += 1
            by_month[(e.get("created_at") or "")[:7]] += mine
            biggest.append({"id": e["id"], "description": e["description"], "amount": round(mine, 2), "created_at": e.get("created_at")})
        for p in e.get("participants", []):
            if p != uid:
                by_friend[p]["shared"] += e["amount"]
                by_friend[p]["count"] += 1

    bals = pair_balances(exps, sett, uid)
    total = my_spend or 1
    friends = []
    for fid, v in by_friend.items():
        p = _profile(fid)
        friends.append({"uid": fid, "name": p["name"], "shared": round(v["shared"], 2), "count": v["count"], "balance": bals.get(fid, 0.0)})
    friends.sort(key=lambda f: -f["shared"])

    return {
        "my_spend": round(my_spend, 2), "paid": round(paid, 2),
        "owed": round(sum(v for v in bals.values() if v > 0), 2),
        "owe": round(-sum(v for v in bals.values() if v < 0), 2),
        "expense_count": len(exps),
        "settled": round(sum(s["amount"] for s in sett if s["from_uid"] == uid), 2),
        "received": round(sum(s["amount"] for s in sett if s["to_uid"] == uid), 2),
        "avg": round(my_spend / len(exps), 2) if exps else 0,
        "by_category": sorted(({"name": k, "amount": round(v, 2), "pct": round(v * 100 / total)} for k, v in by_cat.items()), key=lambda x: -x["amount"]),
        "by_tag": sorted(({"tag": k, "amount": round(v[0], 2), "count": v[1]} for k, v in by_tag.items()), key=lambda x: -x["amount"])[:12],
        "by_month": [{"month": m, "amount": round(by_month[m], 2)} for m in sorted(by_month)][-12:],
        "by_friend": friends[:10],
        "top_expenses": sorted(biggest, key=lambda x: -x["amount"])[:5],
    }
