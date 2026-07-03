from services.firebase import db
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc)


def get_user_groups(uid: str) -> list:
    docs = db.collection("groups").where("members", "array_contains", uid).stream()
    result = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        result.append(d)
    return result


def get_group(group_id: str) -> dict | None:
    doc = db.collection("groups").document(group_id).get()
    if doc.exists:
        d = doc.to_dict()
        d["id"] = doc.id
        return d
    return None


def create_group(name: str, creator_uid: str) -> str:
    _, ref = db.collection("groups").add({
        "name": name.strip(),
        "members": [creator_uid],
        "created_by": creator_uid,
        "created_at": _now(),
    })
    return ref.id


def add_member_by_uid(group_id: str, uid: str):
    from google.cloud.firestore_v1 import ArrayUnion
    db.collection("groups").document(group_id).update({"members": ArrayUnion([uid])})


def get_expenses(group_id: str) -> list:
    docs = db.collection("groups").document(group_id).collection("expenses").stream()
    result = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        result.append(d)
    result.sort(key=lambda e: e.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return result


def add_expense(group_id: str, expense: dict) -> str:
    expense = dict(expense)
    expense["created_at"] = _now()
    _, ref = db.collection("groups").document(group_id).collection("expenses").add(expense)
    return ref.id


def delete_expense(group_id: str, expense_id: str):
    db.collection("groups").document(group_id).collection("expenses").document(expense_id).delete()


def get_settlements(group_id: str) -> list:
    docs = db.collection("groups").document(group_id).collection("settlements").stream()
    result = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        result.append(d)
    return result


def add_settlement(group_id: str, from_uid: str, to_uid: str, amount: float, note: str = "") -> str:
    _, ref = db.collection("groups").document(group_id).collection("settlements").add({
        "from_uid": from_uid,
        "to_uid": to_uid,
        "amount": amount,
        "note": note,
        "created_at": _now(),
    })
    return ref.id


def get_user_by_email(email: str) -> dict | None:
    docs = list(db.collection("users").where("email", "==", email.strip().lower()).limit(1).stream())
    return docs[0].to_dict() if docs else None


def get_user_names(uids: list) -> dict:
    names = {}
    for uid in uids:
        doc = db.collection("users").document(uid).get()
        names[uid] = doc.to_dict().get("name", uid[:8]) if doc.exists else uid[:8]
    return names
