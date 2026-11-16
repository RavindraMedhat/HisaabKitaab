#!/usr/bin/env python3
"""Delete ALL Firestore data: users, groups (+subcollections), invites, expenses, settlements, logs.

Usage:  python scripts/wipe_all.py --yes
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
    n = 0
    for doc in coll.stream():
        for sub in doc.reference.collections():
            n += wipe(sub)
        doc.reference.delete()
        n += 1
    return n


if "--yes" not in sys.argv:
    sys.exit("Refusing to run without --yes")

# Always save a full copy first (outside the repo) so a wipe can be undone with scripts/restore_backup.py
home = os.path.expanduser("~/hisaabkitaab_backup")
os.makedirs(home, exist_ok=True)
copy = {c: {d.id: d.to_dict() for d in db.collection(c).stream()} for c in ("users", "expenses", "settlements", "logs")}
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for ext, writer in (("pickle", lambda f: pickle.dump(copy, f)), ("json", lambda f: f.write(json.dumps(copy, indent=2, default=str)))):
    path = f"{home}/before_wipe_{stamp}.{ext}"
    with open(path, "wb" if ext == "pickle" else "w") as f:
        writer(f)
    os.chmod(path, 0o600)
print("backup saved:", home, {k: len(v) for k, v in copy.items()})

for name in ("users", "groups", "invites", "expenses", "settlements", "meta", "logs"):
    print(f"{name}: deleted {wipe(db.collection(name))}")
