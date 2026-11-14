import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException
from pydantic import BaseModel

from services.firebase import db
from services import ledger
from services.ledger import all_users, friends_of, friend_doc, page, ser, invalidate_users, user_ref, feed_coll, pair_coll
from routers.auth import UPI_RE

router = APIRouter()

MAX_DESC   = 200
MAX_AMOUNT = 1_000_000   # ₹10 lakh hard cap
PAGE       = 15        # items per "Load more"
HOME_FEED  = 10        # items on first load of the home screen
TAG_RE     = re.compile(r"#([A-Za-z0-9_]{1,24})")


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


def _tags(*texts) -> list:
    seen = []
    for t in texts:
        for m in TAG_RE.findall(t or ""):
            m = m.lower()
            if m not in seen:
                seen.append(m)
    return seen[:8]


def _lim(limit: int) -> int:
    return max(1, min(limit, 50))



def _note(text) -> str:
    return (text or "").strip()[:200]


def _check_amount(amount: float):
    if amount <= 0:
        raise HTTPException(400, "Amount must be greater than 0")
    if amount > MAX_AMOUNT:
        raise HTTPException(400, f"Amount cannot exceed ₹{MAX_AMOUNT:,}")


def _sort_friends(friends: list) -> list:
    return sorted(friends, key=lambda f: (-abs(f["balance"]), f["name"].lower()))


def _totals(friends: list):
    owed = round(sum(f["balance"] for f in friends if f["balance"] > 0), 2)
    owe  = round(-sum(f["balance"] for f in friends if f["balance"] < 0), 2)
    return owed, owe


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(request: Request):
    u = _user(request)
    return {**u, "upi": all_users().get(u["uid"], {}).get("upi", "")}


class UpiBody(BaseModel):
    upi: str


@router.put("/me/upi")
def set_upi(body: UpiBody, request: Request):
    uid = _uid(request)
    upi = body.upi.strip()
    if upi and not UPI_RE.match(upi):
        raise HTTPException(400, "That doesn't look like a UPI ID (example: name@oksbi)")
    user_ref(uid).set({"upi": upi}, merge=True)
    invalidate_users()
    return {"upi": upi}


# ── Friends (= every other user) ──────────────────────────────────────────────

@router.get("/friends")
def list_friends(request: Request):
    return _sort_friends(friends_of(_uid(request)))


@router.get("/friends/{fid}")
def friend_detail(fid: str, request: Request, limit: int = PAGE):
    uid = _uid(request)
    friend = friend_doc(uid, fid)
    if not friend:
        raise HTTPException(404, "Person not found")
    items, nxt = page(pair_coll(uid, fid), _lim(limit), None)
    return {"friend": friend, "balance": friend["balance"], "items": items, "next_cursor": nxt, "uid": uid}


@router.get("/friends/{fid}/history")
def friend_history(fid: str, request: Request, cursor: str = "", limit: int = PAGE):
    items, nxt = page(pair_coll(_uid(request), fid), _lim(limit), cursor or None)
    return {"items": items, "next_cursor": nxt}


# ── Home feed ─────────────────────────────────────────────────────────────────

@router.get("/feed")
def feed(request: Request, cursor: str = "", limit: int = PAGE):
    items, nxt = page(feed_coll(_uid(request)), _lim(limit), cursor or None)
    return {"items": items, "next_cursor": nxt}


@router.get("/dashboard")
def get_dashboard(request: Request):
    uid     = _uid(request)
    friends = friends_of(uid)                      # balances are stored — no history scan
    owed, owe = _totals(friends)
    items, nxt = page(feed_coll(uid), HOME_FEED, None)
    return {"net_balance": round(owed - owe, 2), "owed": owed, "owe": owe,
            "friends": _sort_friends(friends), "items": items, "next_cursor": nxt, "uid": uid}


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
    _check_amount(body.amount)
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
    users = all_users()
    if any(p not in users for p in participants):
        raise HTTPException(400, "Everyone in an expense must be a member of the gang")
    fields = {
        "description": desc, "amount": amount, "paid_by": body.paid_by,
        "split_among": split, "participants": participants,
        "names": {p: users[p]["name"] for p in participants},
        "note": _note(body.note), "tags": _tags(desc, body.note),
    }
    if amounts:
        fields["split_amounts"] = amounts
    return fields


def _load_own(eid: str, uid: str) -> dict:
    doc = db.collection("expenses").document(eid).get()
    if not doc.exists or uid not in doc.to_dict().get("participants", []):
        raise HTTPException(404, "Expense not found")
    return doc.to_dict()


def _check_can_change(e: dict, uid: str):
    if e.get("created_by") != uid and e.get("paid_by") != uid:
        raise HTTPException(403, "Only the person who added or paid for this can change it")


@router.post("/expenses", status_code=201)
def add_expense(body: ExpenseBody, request: Request):
    uid = _uid(request)
    e = {**_validate_expense(body, uid), "created_by": uid, "created_at": _now()}
    eid = db.collection("expenses").document().id
    ledger.apply_expense(eid, None, e)
    return {"id": eid}


@router.get("/expenses/{eid}")
def get_expense(eid: str, request: Request):
    uid = _uid(request)
    e = ser({**_load_own(eid, uid), "id": eid})
    return {**e, "friends": [u for k, u in all_users().items() if k != uid]}


@router.put("/expenses/{eid}")
def edit_expense(eid: str, body: ExpenseBody, request: Request):
    uid = _uid(request)
    old = _load_own(eid, uid)
    _check_can_change(old, uid)
    old_wo_split = {k: v for k, v in old.items() if k != "split_amounts"}
    new = {**old_wo_split, **_validate_expense(body, uid), "updated_by": uid, "updated_at": _now()}
    ledger.apply_expense(eid, old, new)
    return {"ok": True}


@router.delete("/expenses/{eid}", status_code=204)
def delete_expense(eid: str, request: Request):
    uid = _uid(request)
    old = _load_own(eid, uid)
    _check_can_change(old, uid)
    ledger.apply_expense(eid, old, None)


# ── Settlements ───────────────────────────────────────────────────────────────

class SettleBody(BaseModel):
    from_uid: str
    to_uid:   str
    amount:   float
    note:     Optional[str] = ""     # optional free text, hashtags become labels


@router.post("/settlements", status_code=201)
def add_settlement(body: SettleBody, request: Request):
    uid = _uid(request)
    _check_amount(body.amount)
    if body.from_uid == body.to_uid or uid not in (body.from_uid, body.to_uid):
        raise HTTPException(403, "You can only record payments between you and a friend")
    other = body.to_uid if body.from_uid == uid else body.from_uid
    friend = friend_doc(uid, other)
    if not friend:
        raise HTTPException(404, "Person not found")

    bal  = friend["balance"]                         # stored: positive = they owe me
    debt = -bal if body.from_uid == uid else bal     # what the payer actually owes
    if debt < 0.01:
        raise HTTPException(400, "Nothing is owed between you two right now")
    if round(body.amount, 2) > round(debt, 2):
        raise HTTPException(400, f"That's more than the ₹{debt:,.2f} owed")

    note  = _note(body.note)
    users = all_users()
    sid   = db.collection("settlements").document().id
    ledger.apply_settlement(sid, {
        "from_uid": body.from_uid, "to_uid": body.to_uid, "amount": round(body.amount, 2),
        "participants": [body.from_uid, body.to_uid], "note": note, "tags": _tags(note),
        "names": {body.from_uid: users[body.from_uid]["name"], body.to_uid: users[body.to_uid]["name"]},
        "created_by": uid, "created_at": _now(),
    })
    return {"id": sid}


# ── Insights (reads one small doc per month) ──────────────────────────────────

def _months_back(n: int) -> str:
    now = _now()
    y, m = now.year, now.month - n
    while m < 1:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


@router.get("/insights")
def insights(request: Request, period: str = Query("all", alias="range")):
    uid  = _uid(request)
    docs = {d.id: d.to_dict() or {} for d in user_ref(uid).collection("monthly").stream()}      # one small doc per month

    months = {"month": [_months_back(0)], "3m": [_months_back(i) for i in range(3)]}.get(period) or sorted(docs)
    use = [docs[m] for m in months if m in docs]

    def total(key):
        return round(sum(float(d.get(key, 0)) for d in use), 2)

    cats, tags, fr = {}, {}, {}
    for d in use:
        for k, v in (d.get("by_cat") or {}).items():
            cats[k] = cats.get(k, 0) + float(v)
        for t, v in (d.get("by_tag") or {}).items():
            x = tags.setdefault(t, [0.0, 0])
            x[0] += float(v.get("a", 0)); x[1] += int(v.get("n", 0))
        for u, v in (d.get("by_friend") or {}).items():
            x = fr.setdefault(u[1:], [0.0, 0])
            x[0] += float(v.get("shared", 0)); x[1] += int(v.get("n", 0))

    friend_list = friends_of(uid)
    friends = {f["uid"]: f for f in friend_list}
    owed, owe = _totals(friend_list)
    spend = total("spend")
    count = int(round(total("count")))
    by_friend = sorted(
        ({"uid": u, "name": friends[u]["name"], "shared": round(v[0], 2), "count": v[1], "balance": friends[u]["balance"]}
         for u, v in fr.items() if u in friends and v[1] > 0),
        key=lambda f: -f["shared"])

    return {
        "my_spend": spend, "paid": total("paid"), "owed": owed, "owe": owe,
        "expense_count": count, "settled": total("settled"), "received": total("received"),
        "avg": round(spend / count, 2) if count else 0,
        "by_category": sorted(({"name": ledger.CATEGORY_LABELS.get(k, k.title()), "amount": round(v, 2),
                                "pct": round(v * 100 / spend) if spend else 0} for k, v in cats.items() if v > 0.005),
                              key=lambda x: -x["amount"]),
        "by_tag": sorted(({"tag": t, "amount": round(v[0], 2), "count": v[1]} for t, v in tags.items() if v[1] > 0),
                         key=lambda x: -x["amount"])[:12],
        "by_month": [{"month": m, "amount": round(float(docs[m].get("spend", 0)), 2)} for m in sorted(docs)][-12:],
        "by_friend": by_friend[:10],
    }
