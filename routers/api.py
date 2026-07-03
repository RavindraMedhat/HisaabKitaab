from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from google.cloud.firestore_v1 import ArrayUnion, ArrayRemove

from services.firebase import db
from services.calculator import calc_my_balance, simplify_debts

router = APIRouter()

MAX_NAME   = 60
MAX_DESC   = 200
MAX_AMOUNT = 1_000_000   # ₹10 lakh hard cap


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
    out = {}
    for k, v in d.items():
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


def _get_expenses(group_id: str) -> list:
    docs = db.collection("groups").document(group_id).collection("expenses").stream()
    rows = [_ser({**doc.to_dict(), "id": doc.id}) for doc in docs]
    rows.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return rows


def _get_settlements(group_id: str) -> list:
    docs = db.collection("groups").document(group_id).collection("settlements").stream()
    rows = [_ser({**doc.to_dict(), "id": doc.id}) for doc in docs]
    rows.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return rows


def _resolve_names(uids: list) -> dict:
    names = {}
    for uid in uids:
        doc = db.collection("users").document(uid).get()
        names[uid] = doc.to_dict().get("name", uid[:8]) if doc.exists else uid[:8]
    return names


# #2/#3/#4 — membership + creator guards used across all write endpoints
def _check_member(gid: str, uid: str) -> dict:
    doc = db.collection("groups").document(gid).get()
    if not doc.exists:
        raise HTTPException(404, "Group not found")
    g = doc.to_dict()
    if uid not in g.get("members", []):
        raise HTTPException(403, "You are not a member of this group")
    return g


def _check_creator(gid: str, uid: str) -> dict:
    g = _check_member(gid, uid)
    if g.get("created_by") != uid:
        raise HTTPException(403, "Only the group creator can do this")
    return g


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    return _user(request)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(request: Request):
    uid   = _uid(request)
    gdocs = list(db.collection("groups").where("members", "array_contains", uid).stream())
    net   = 0.0
    items = []

    for gdoc in gdocs:
        gid  = gdoc.id
        g    = gdoc.to_dict()
        exps = _get_expenses(gid)
        sett = _get_settlements(gid)
        net += calc_my_balance(exps, sett, uid)
        for e in exps[:5]:
            items.append({**e, "type": "expense", "group_name": g.get("name", "")})
        for s in sett[:3]:
            items.append({**s, "type": "settlement", "group_name": g.get("name", "")})

    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    # Pending invite count for badge
    invite_count = len(list(
        db.collection("invites")
        .where("invited_uid", "==", uid)
        .where("status", "==", "pending")
        .stream()
    ))

    return {"net_balance": round(net, 2), "activity": items[:15], "uid": uid, "invite_count": invite_count}


# ── Invites ───────────────────────────────────────────────────────────────────
# #15 — members can only be added via an invite they must accept

@router.get("/invites")
async def get_invites(request: Request):
    uid  = _uid(request)
    docs = db.collection("invites").where("invited_uid", "==", uid).where("status", "==", "pending").stream()
    return [_ser({**doc.to_dict(), "id": doc.id}) for doc in docs]


@router.post("/invites/{invite_id}/accept")
async def accept_invite(invite_id: str, request: Request):
    uid = _uid(request)
    doc = db.collection("invites").document(invite_id).get()
    if not doc.exists:
        raise HTTPException(404, "Invite not found")
    inv = doc.to_dict()
    if inv.get("invited_uid") != uid:
        raise HTTPException(403, "This invite is not for you")
    if inv.get("status") != "pending":
        raise HTTPException(400, "Invite is no longer pending")

    db.collection("groups").document(inv["group_id"]).update({"members": ArrayUnion([uid])})
    db.collection("invites").document(invite_id).update({"status": "accepted"})
    return {"group_id": inv["group_id"], "group_name": inv["group_name"]}


@router.post("/invites/{invite_id}/decline")
async def decline_invite(invite_id: str, request: Request):
    uid = _uid(request)
    doc = db.collection("invites").document(invite_id).get()
    if not doc.exists:
        raise HTTPException(404, "Invite not found")
    if doc.to_dict().get("invited_uid") != uid:
        raise HTTPException(403, "This invite is not for you")
    db.collection("invites").document(invite_id).update({"status": "declined"})
    return {"ok": True}


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/groups")
async def list_groups(request: Request):
    uid   = _uid(request)
    gdocs = db.collection("groups").where("members", "array_contains", uid).stream()
    out   = []
    for gdoc in gdocs:
        g    = _ser({**gdoc.to_dict(), "id": gdoc.id})
        exps = _get_expenses(gdoc.id)
        sett = _get_settlements(gdoc.id)
        g["my_balance"]   = calc_my_balance(exps, sett, uid)
        g["member_count"] = len(g.get("members", []))
        g["is_creator"]   = g.get("created_by") == uid
        out.append(g)
    return out


class GroupBody(BaseModel):
    name: str


@router.post("/groups", status_code=201)
async def create_group(body: GroupBody, request: Request):
    uid  = _uid(request)
    name = body.name.strip()
    # #6 — reject blank names; #10 — cap length
    if not name:
        raise HTTPException(400, "Group name cannot be empty")
    if len(name) > MAX_NAME:
        raise HTTPException(400, f"Group name must be {MAX_NAME} characters or fewer")

    _, ref = db.collection("groups").add({
        "name":       name,
        "members":    [uid],
        "created_by": uid,
        "created_at": _now(),
    })
    return {"id": ref.id, "name": name}


@router.get("/groups/{gid}")
async def get_group(gid: str, request: Request):
    uid = _uid(request)
    g   = _check_member(gid, uid)

    members    = g.get("members", [])
    names      = _resolve_names(members)
    exps       = _get_expenses(gid)
    sett       = _get_settlements(gid)
    my_balance = calc_my_balance(exps, sett, uid)
    raw_txns   = simplify_debts(exps, sett)

    transactions = [
        {"from_uid": t["from"], "from_name": names.get(t["from"], "?"),
         "to_uid":   t["to"],   "to_name":   names.get(t["to"],   "?"),
         "amount":   t["amount"]}
        for t in raw_txns
    ]
    member_list = [{"uid": m, "name": names.get(m, m[:8])} for m in members]

    return {
        "id": gid, "name": g["name"],
        "members": member_list, "expenses": exps, "settlements": sett,
        "my_balance": my_balance, "transactions": transactions,
        "uid": uid, "is_creator": g.get("created_by") == uid,
    }


# #19 — creator can delete a group only when all debts are settled
@router.delete("/groups/{gid}", status_code=204)
async def delete_group(gid: str, request: Request):
    uid = _uid(request)
    _check_creator(gid, uid)

    exps = _get_expenses(gid)
    sett = _get_settlements(gid)
    if simplify_debts(exps, sett):
        raise HTTPException(400, "Settle all debts before deleting the group")

    for sub in ("expenses", "settlements"):
        for doc in db.collection("groups").document(gid).collection(sub).stream():
            doc.reference.delete()
    db.collection("groups").document(gid).delete()


# #15/#17 — invite-only member addition; only creator can invite
class MemberBody(BaseModel):
    email: str


@router.post("/groups/{gid}/members")
async def invite_member(gid: str, body: MemberBody, request: Request):
    user = _user(request)
    uid  = user["uid"]
    g    = _check_creator(gid, uid)    # #17 — creator only

    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Enter a valid email address")

    docs = list(db.collection("users").where("email", "==", email).limit(1).stream())
    if not docs:
        raise HTTPException(404, "No HisaabKitaab account found for that email. Ask them to sign in first.")

    found     = docs[0].to_dict()
    found_uid = found["uid"]

    # #29 — can't invite yourself
    if found_uid == uid:
        raise HTTPException(400, "You are already a member of this group")

    # #16 — already a member
    if found_uid in g.get("members", []):
        raise HTTPException(409, f"{found.get('name', email)} is already a member")

    # Duplicate pending invite check
    existing = list(
        db.collection("invites")
        .where("group_id",    "==", gid)
        .where("invited_uid", "==", found_uid)
        .where("status",      "==", "pending")
        .limit(1).stream()
    )
    if existing:
        raise HTTPException(409, f"A pending invite for {found.get('name', email)} already exists")

    db.collection("invites").add({
        "group_id":       gid,
        "group_name":     g["name"],
        "invited_uid":    found_uid,
        "invited_name":   found.get("name", ""),
        "invited_by":     uid,
        "invited_by_name": user["name"],
        "status":         "pending",
        "created_at":     _now(),
    })
    return {"message": f"Invite sent to {found.get('name', email)}"}


# #20 — creator can remove a member only if they have no outstanding balance
@router.delete("/groups/{gid}/members/{member_uid}", status_code=204)
async def remove_member(gid: str, member_uid: str, request: Request):
    uid = _uid(request)
    g   = _check_creator(gid, uid)

    if member_uid == uid:
        raise HTTPException(400, "Use 'Leave group' to remove yourself")
    if member_uid not in g.get("members", []):
        raise HTTPException(404, "Member not in this group")

    exps = _get_expenses(gid)
    sett = _get_settlements(gid)
    if abs(calc_my_balance(exps, sett, member_uid)) > 0.01:
        raise HTTPException(400, "Settle this member's balance before removing them")

    db.collection("groups").document(gid).update({"members": ArrayRemove([member_uid])})


# #21 — any non-creator member can leave if their balance is zero
@router.post("/groups/{gid}/leave")
async def leave_group(gid: str, request: Request):
    uid = _uid(request)
    g   = _check_member(gid, uid)

    if g.get("created_by") == uid:
        raise HTTPException(400, "Group creator cannot leave — delete the group instead")

    exps = _get_expenses(gid)
    sett = _get_settlements(gid)
    if abs(calc_my_balance(exps, sett, uid)) > 0.01:
        raise HTTPException(400, "Settle your balance before leaving the group")

    db.collection("groups").document(gid).update({"members": ArrayRemove([uid])})
    return {"ok": True}


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseBody(BaseModel):
    description: str
    amount:      float
    paid_by:     str
    split_among: list[str]
    group_name:  Optional[str] = ""


def _validate_expense(body: ExpenseBody, members: list):
    desc = body.description.strip()
    if not desc:
        raise HTTPException(400, "Description cannot be empty")
    if len(desc) > MAX_DESC:
        raise HTTPException(400, f"Description must be {MAX_DESC} characters or fewer")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be greater than 0")
    if body.amount > MAX_AMOUNT:
        raise HTTPException(400, f"Amount cannot exceed ₹{MAX_AMOUNT:,}")
    # #9 — empty split_among
    if not body.split_among:
        raise HTTPException(400, "Select at least one person to split among")
    # #22 — deduplicate split_among silently
    split = list(dict.fromkeys(body.split_among))
    # #5 — paid_by must be a group member
    if body.paid_by not in members:
        raise HTTPException(400, "The payer must be a member of this group")
    # #5/#28 — all split_among must be group members with registered accounts
    invalid = [u for u in split if u not in members]
    if invalid:
        raise HTTPException(400, "All people in the split must be members of this group")
    return desc, round(body.amount, 2), split  # #27 — round to 2dp


@router.post("/groups/{gid}/expenses", status_code=201)
async def add_expense(gid: str, body: ExpenseBody, request: Request):
    uid = _uid(request)
    g   = _check_member(gid, uid)   # #2 — membership check

    desc, amount, split = _validate_expense(body, g.get("members", []))

    _, ref = db.collection("groups").document(gid).collection("expenses").add({
        "description": desc,
        "amount":      amount,
        "paid_by":     body.paid_by,
        "split_among": split,
        "group_id":    gid,
        "group_name":  body.group_name,
        "created_by":  uid,
        "created_at":  _now(),
    })
    return {"id": ref.id}


# #25 — edit expense (creator or paid_by only)
@router.put("/groups/{gid}/expenses/{eid}")
async def edit_expense(gid: str, eid: str, body: ExpenseBody, request: Request):
    uid = _uid(request)
    g   = _check_member(gid, uid)

    exp_doc = db.collection("groups").document(gid).collection("expenses").document(eid).get()
    if not exp_doc.exists:
        raise HTTPException(404, "Expense not found")

    exp = exp_doc.to_dict()
    # #18 — only creator or paid_by can edit
    if exp.get("created_by") != uid and exp.get("paid_by") != uid:
        raise HTTPException(403, "Only the expense creator or payer can edit it")

    desc, amount, split = _validate_expense(body, g.get("members", []))

    db.collection("groups").document(gid).collection("expenses").document(eid).update({
        "description": desc,
        "amount":      amount,
        "paid_by":     body.paid_by,
        "split_among": split,
        "updated_by":  uid,
        "updated_at":  _now(),
    })
    return {"ok": True}


# #3/#18 — membership + creator/payer check on delete
@router.delete("/groups/{gid}/expenses/{eid}", status_code=204)
async def delete_expense(gid: str, eid: str, request: Request):
    uid = _uid(request)
    _check_member(gid, uid)

    exp_doc = db.collection("groups").document(gid).collection("expenses").document(eid).get()
    if not exp_doc.exists:
        raise HTTPException(404, "Expense not found")

    exp = exp_doc.to_dict()
    if exp.get("created_by") != uid and exp.get("paid_by") != uid:
        raise HTTPException(403, "Only the expense creator or payer can delete it")

    exp_doc.reference.delete()


# ── Settlements ───────────────────────────────────────────────────────────────

class SettleBody(BaseModel):
    from_uid: str
    to_uid:   str
    amount:   float
    note:     Optional[str] = ""


@router.post("/groups/{gid}/settlements", status_code=201)
async def add_settlement(gid: str, body: SettleBody, request: Request):
    uid = _uid(request)
    g   = _check_member(gid, uid)   # #4

    # #7 — amount > 0
    if body.amount <= 0:
        raise HTTPException(400, "Settlement amount must be greater than 0")
    if body.amount > MAX_AMOUNT:
        raise HTTPException(400, f"Amount cannot exceed ₹{MAX_AMOUNT:,}")

    # #8 — can't settle with yourself
    if body.from_uid == body.to_uid:
        raise HTTPException(400, "Cannot settle a debt with yourself")

    members = g.get("members", [])
    # #4 — both parties must be members
    if body.from_uid not in members or body.to_uid not in members:
        raise HTTPException(400, "Both parties must be members of this group")

    # Requester must be one of the two parties
    if uid not in (body.from_uid, body.to_uid):
        raise HTTPException(403, "You can only record settlements you are a party to")

    # #23/#24 — cap at actual debt; blocks over-settlement and duplicate settlement
    exps  = _get_expenses(gid)
    sett  = _get_settlements(gid)
    txns  = simplify_debts(exps, sett)
    debt  = next((t["amount"] for t in txns
                  if t["from"] == body.from_uid and t["to"] == body.to_uid), 0.0)

    if debt < 0.01:
        raise HTTPException(400, "No outstanding debt to settle between these two people")
    if round(body.amount, 2) > round(debt, 2):
        raise HTTPException(400, f"Cannot settle more than the actual debt of ₹{debt:,.2f}")

    _, ref = db.collection("groups").document(gid).collection("settlements").add({
        "from_uid":   body.from_uid,
        "to_uid":     body.to_uid,
        "amount":     round(body.amount, 2),
        "note":       (body.note or "").strip(),
        "created_by": uid,
        "created_at": _now(),
    })
    return {"id": ref.id}
