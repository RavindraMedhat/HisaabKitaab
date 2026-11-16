#!/usr/bin/env python3
"""Delete every expense, payment and everything derived from them — but KEEP the user accounts.

Removes: expenses, settlements, logs, meta/balances, and each user's feed / pairs / monthly (+ old balances) data.
Keeps:   users/{mobile} documents (name, mobile, UPI, password).
A full backup is saved to ~/hisaabkitaab_backup first (undo with scripts/restore_backup.py).

Usage:  python scripts/clear_entries.py --yes
"""
import json
import os
import pickle
import sys
from datetime import datetime

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))
db = firestore.client()


def wipe(coll):
    """Delete a collection and everything under it. list_documents() also returns 'placeholder' documents
    (ones that only exist because they hold a sub-collection), which stream() would silently skip."""
    n = 0
    for ref in coll.list_documents():
        for sub in ref.collections():
            n += wipe(sub)
        if ref.get().exists:
            ref.delete()
            n += 1
    return n


if "--yes" not in sys.argv:
    sys.exit("Refusing to run without --yes")

home = os.path.expanduser("~/hisaabkitaab_backup")
os.makedirs(home, exist_ok=True)
copy = {c: {d.id: d.to_dict() for d in db.collection(c).stream()} for c in ("users", "expenses", "settlements", "logs")}
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for ext in ("pickle", "json"):
    path = f"{home}/before_clear_{stamp}.{ext}"
    with open(path, "wb" if ext == "pickle" else "w") as f:
        pickle.dump(copy, f) if ext == "pickle" else f.write(json.dumps(copy, indent=2, default=str))
    os.chmod(path, 0o600)
print("backup saved:", home, {k: len(v) for k, v in copy.items()})

for name in ("expenses", "settlements", "logs", "meta", "groups", "invites"):
    print(f"{name}: deleted {wipe(db.collection(name))}")
for user in db.collection("users").stream():                 # keep the user doc, remove what hangs under it
    for sub in user.reference.collections():
        print(f"users/{user.id}/{sub.id}: deleted {wipe(sub)}")
