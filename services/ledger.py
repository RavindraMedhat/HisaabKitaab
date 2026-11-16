"""
Ledger: keeps *derived* data up to date so screens never recompute from raw history.

Canonical records (source of truth):
    expenses/{id}, settlements/{id}

Derived records (written together with the canonical one, in ONE atomic batch):
    meta/balances                           ONE doc: b[u][v] = how much v owes u (negative = u owes v). Whole gang in one read
    users/{u}/feed/{id}                     copy of every expense/settlement u is part of   → home feed, paginated
    users/{u}/pairs/{other}/items/{id}      copy of items that move money between u and other → friend history, paginated
    users/{u}/monthly/{YYYY-MM}             running totals for reports (spend, categories, tags, friends)

Everyone is everyone's friend, so there is no friends list: friends = all other users (cached in memory 60s).
Reads therefore cost: friends list = one doc for ALL balances, a feed page = `limit` docs, a report = one doc per month.
"""
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from google.cloud.firestore_v1 import Increment

from services.firebase import db
from services.calculator import expense_shares

# key, label, pattern
CATEGORIES = [
    ("food",      "Food",         r"dinner|lunch|breakfast|food|restaurant|biryani|pizza|burger|meal|thali|cafe|chai|tea|coffee|snack"),
    ("drinks",    "Drinks",       r"drink|beer|bar\b|pub|wine|alcohol|cocktail"),
    ("travel",    "Travel",       r"cab|uber|ola|taxi|auto|metro|bus|train|flight|ticket"),
    ("fuel",      "Fuel & tolls", r"petrol|diesel|fuel|toll|parking"),
    ("stay",      "Stay",         r"hotel|stay|room|resort|airbnb|hostel"),
    ("fun",       "Fun",          r"movie|show|entry|park|ride|game|party|birthday|garba"),
    ("groceries", "Groceries",    r"grocer|milk|veg|mart|bigbasket|blinkit|zepto"),
]
CATEGORY_LABELS = {k: label for k, label, _ in CATEGORIES} | {"other": "Other"}


def category_key(desc: str) -> str:
    for key, _, pat in CATEGORIES:
        if re.search(pat, desc or "", re.I):
            return key
    return "other"


# ── Refs ──────────────────────────────────────────────────────────────────────

def user_ref(uid):      return db.collection("users").document(uid)
def _u(uid):            return db.collection("users").document(uid)
def graph_ref():        return db.collection("meta").document("balances")
def feed_coll(u):       return _u(u).collection("feed")
def pair_coll(a, b):    return _u(a).collection("pairs").document(b).collection("items")
def feed_ref(u, id_):   return feed_coll(u).document(id_)
def pair_ref(a, b, i):  return pair_coll(a, b).document(i)
def month_ref(u, m):    return _u(u).collection("monthly").document(m)


def month_of(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


# ── Pure helpers (no I/O) ─────────────────────────────────────────────────────

def flat_effects(e: dict, sign: int) -> dict:
    """{(a, b): delta} to add to balances[a][b]; positive means b owes a more."""
    out = defaultdict(float)
    payer = e.get("paid_by")
    for q, share in expense_shares(e).items():
        if q != payer and share:
            out[(payer, q)] += sign * share
            out[(q, payer)] -= sign * share
    return out


def flat_stats(e: dict, p: str, sign: int) -> dict:
    """{path-tuple: delta} to add to p's monthly report doc for this expense."""
    mine = expense_shares(e).get(p, 0.0)
    out = defaultdict(float)
    out[("count",)] += sign
    out[("spend",)] += sign * mine
    if e.get("paid_by") == p:
        out[("paid",)] += sign * e["amount"]
    if mine > 0:
        out[("by_cat", category_key(e.get("description")))] += sign * mine
        for t in e.get("tags", []):
            out[("by_tag", t, "a")] += sign * mine
            out[("by_tag", t, "n")] += sign
    for q in e.get("participants", []):
        if q != p:
            out[("by_friend", "u" + q, "shared")] += sign * e["amount"]
            out[("by_friend", "u" + q, "n")] += sign
    return out


def _nest(flat: dict) -> dict:
    root: dict = {}
    for path, v in flat.items():
        v = round(v, 2)
        if abs(v) < 1e-9:
            continue
        node = root
        for k in path[:-1]:
            node = node.setdefault(k, {})
        node[path[-1]] = Increment(v)
    return root


def _merge(*flats) -> dict:
    out = defaultdict(float)
    for f in flats:
        for k, v in f.items():
            out[k] += v
    return out


def _delta(fn, old, new, *args) -> dict:
    """Change between two states of an expense: undo `old` (sign -1), apply `new` (sign +1)."""
    return _merge(*(fn(e, *args, s) for e, s in ((old, -1), (new, 1))
                    if e and (not args or args[0] in e["participants"])))


def _expense_targets(e: dict, eid: str) -> dict:
    payer = e["paid_by"]
    refs = {}
    for p in set(e["participants"]) | {e.get("created_by")} - {None}:     # the recorder sees it too
        refs[f"feed/{p}"] = feed_ref(p, eid)
    for q in e["participants"]:
        if q != payer:
            refs[f"pair/{payer}/{q}"] = pair_ref(payer, q, eid)
            refs[f"pair/{q}/{payer}"] = pair_ref(q, payer, eid)
    return refs


# ── Writes (each is one atomic batch) ─────────────────────────────────────────

def _add_balance_changes(batch, changes):
    """changes: iterable of ((a, b), delta) meaning b owes a `delta` more."""
    nested: dict = {}
    for (a, b), v in changes:
        v = round(v, 2)
        if abs(v) >= 0.005:
            nested.setdefault("u" + a, {})["u" + b] = Increment(v)
    if nested:
        batch.set(graph_ref(), {"b": nested}, merge=True)


def apply_expense(eid: str, old: dict | None, new: dict | None):
    """Move canonical + derived data from `old` state to `new` state (create: old=None, delete: new=None)."""
    batch = db.batch()
    ref = db.collection("expenses").document(eid)

    # canonical
    if new is None:
        batch.delete(ref)
    else:
        batch.set(ref, new)

    # balances
    eff = _delta(flat_effects, old, new)
    _add_balance_changes(batch, eff.items())

    # monthly report docs (month comes from created_at, which never changes)
    base = new or old
    month = month_of(base["created_at"])
    people = set((old or {}).get("participants", [])) | set((new or {}).get("participants", []))
    for p in people:
        nested = _nest(_delta(flat_stats, old, new, p))
        if nested:
            batch.set(month_ref(p, month), nested, merge=True)

    # feed + friend-history copies
    old_t = _expense_targets(old, eid) if old else {}
    new_t = _expense_targets(new, eid) if new else {}
    for key, r in old_t.items():
        if key not in new_t:
            batch.delete(r)
    if new:
        entry = {**new, "type": "expense", "id": eid}
        for r in new_t.values():
            batch.set(r, entry)

    batch.commit()


def _add_settlement(batch, sid: str, s: dict):
    f, t, amt = s["from_uid"], s["to_uid"], s["amount"]
    batch.set(db.collection("settlements").document(sid), s)
    _add_balance_changes(batch, [((t, f), -amt), ((f, t), amt)])

    month = month_of(s["created_at"])
    batch.set(month_ref(f, month), {"settled": Increment(amt)}, merge=True)
    batch.set(month_ref(t, month), {"received": Increment(amt)}, merge=True)

    entry = {**s, "type": "settlement", "id": sid,
             "from_name": s["names"].get(f, ""), "to_name": s["names"].get(t, "")}
    for r in (feed_ref(f, sid), feed_ref(t, sid), pair_ref(f, t, sid), pair_ref(t, f, sid)):
        batch.set(r, entry)


def apply_settlements(legs: list):
    """legs: [(sid, settlement dict), ...] — all recorded in ONE atomic batch."""
    batch = db.batch()
    for sid, s in legs:
        _add_settlement(batch, sid, s)
    batch.commit()


def apply_settlement(sid: str, s: dict):
    apply_settlements([(sid, s)])


# ── Reads ─────────────────────────────────────────────────────────────────────

_users_cache = {"t": 0.0, "users": {}}
_users_lock = threading.Lock()


def all_users() -> dict:
    """uid -> {name, mobile, upi}. Cached in memory for 60s (tiny gang, profiles rarely change).
    Only these three fields are fetched, so passwords never sit in server memory."""
    if time.time() - _users_cache["t"] > 60:
        with _users_lock:
            if time.time() - _users_cache["t"] > 60:     # another thread may have refreshed it
                users = {}
                for d in db.collection("users").select(["name", "mobile", "upi"]).stream():
                    x = d.to_dict() or {}
                    users[d.id] = {"uid": d.id, "name": x.get("name", d.id), "mobile": x.get("mobile", d.id), "upi": x.get("upi", "")}
                _users_cache.update(t=time.time(), users=users)
    return _users_cache["users"]


def invalidate_users():
    _users_cache["t"] = 0.0


def read_graph() -> dict:
    """{a: {b: amount}} — amount > 0 means b owes a. One read for the whole gang."""
    d = graph_ref().get()
    raw = (d.to_dict() or {}).get("b", {}) if d.exists else {}
    return {a[1:]: {b[1:]: round(float(v), 2) for b, v in row.items()} for a, row in raw.items()}


def friends_of(uid: str, graph: dict | None = None) -> list:
    """Every other user with their running balance to you (positive = they owe you)."""
    row = (graph if graph is not None else read_graph()).get(uid, {})
    return [{**u, "balance": row.get(k, 0.0)} for k, u in all_users().items() if k != uid]


def friend_doc(uid: str, other: str) -> dict | None:
    u = all_users().get(other)
    if not u or other == uid:
        return None
    return {**u, "balance": read_graph().get(uid, {}).get(other, 0.0)}


# ── Settle-up plan: fewest payments that clear everyone, along real debts ─────

def settle_plan(graph: dict) -> list:
    """Suggest payments such that everyone ends at zero.
    Each payment follows real debts, e.g. A owes B 500 and B owes C 400 → A pays B 100 and C 400.
    Returns [{"from", "to", "amount", "path": [uids]}]; `path` lists the hops the money is routed
    through (the first and last are payer and receiver; middle ones are people whose debts it clears)."""
    debts: dict = {}                      # debts[a][b] = a owes b
    net: dict = {}
    for a, row in graph.items():
        net[a] = round(sum(row.values()), 2)
        for b, v in row.items():
            if v < -0.005:
                debts.setdefault(a, {})[b] = -v

    plan = []
    for _ in range(200):                  # hard stop; real gangs need a handful
        debtor = min((u for u, n in net.items() if n < -0.005), key=lambda u: net[u], default=None)
        if debtor is None:
            break
        # breadth-first search along debts for the nearest person who is owed overall
        prev, queue, target = {debtor: None}, [debtor], None
        while queue and target is None:
            x = queue.pop(0)
            for y, amt in debts.get(x, {}).items():
                if amt > 0.005 and y not in prev:
                    prev[y] = x
                    if net.get(y, 0) > 0.005:
                        target = y
                        break
                    queue.append(y)
        if target is None:
            net[debtor] = 0.0             # leftover is a debt cycle; it cancels out
            continue
        path = [target]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        path.reverse()
        hops = list(zip(path, path[1:]))
        m = round(min(-net[debtor], net[target], *(debts[a][b] for a, b in hops)), 2)
        if m < 0.005:
            net[debtor] = 0.0
            continue
        for a, b in hops:
            debts[a][b] = round(debts[a][b] - m, 2)
        net[debtor] = round(net[debtor] + m, 2)
        net[target] = round(net[target] - m, 2)
        plan.append({"from": debtor, "to": target, "amount": m, "path": path})
    return plan


def ser(d: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}


def page(coll, limit: int, cursor: str | None):
    """Newest-first page of `coll` (ordered by created_at). Returns (items, next_cursor)."""
    q = coll.order_by("created_at", direction="DESCENDING")
    if cursor:
        snap = coll.document(cursor).get()
        if snap.exists:
            q = q.start_after(snap)
    docs = list(q.limit(limit + 1).stream())
    items = [ser({**d.to_dict(), "id": d.id}) for d in docs[:limit]]
    return items, (docs[limit - 1].id if len(docs) > limit else None)


# ── Rebuild everything derived from canonical records (migration / repair) ────

def _wipe_collection(coll):
    for d in coll.stream():
        d.reference.delete()


def rebuild_all() -> dict:
    users = {d.id: d.to_dict() for d in db.collection("users").stream()}

    # 1. clear derived data
    for uid in users:
        for sub in ("balances", "feed", "monthly"):          # "balances" = old per-user layout, cleaned up here
            _wipe_collection(_u(uid).collection(sub))
        for pdoc in _u(uid).collection("pairs").list_documents():
            _wipe_collection(pdoc.collection("items"))
            pdoc.delete()

    names = {u: d.get("name", u) for u, d in users.items()}

    graph_ref().delete()

    # 2. replay history
    exps = list(db.collection("expenses").stream())
    sets = list(db.collection("settlements").stream())
    for d in exps:
        e = d.to_dict()
        e["names"] = {p: names.get(p, p) for p in e.get("participants", [])}
        apply_expense(d.id, None, e)
    for d in sets:
        s = d.to_dict()
        s["names"] = {p: names.get(p, p) for p in (s["from_uid"], s["to_uid"])}
        apply_settlement(d.id, s)
    return {"users": len(users), "expenses": len(exps), "settlements": len(sets)}
