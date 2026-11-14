#!/usr/bin/env python3
"""Delete ALL Firestore data: users, groups (+subcollections), invites, expenses, settlements, logs.

Usage:  python scripts/wipe_all.py --yes
"""
import os
import sys

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

for name in ("users", "groups", "invites", "expenses", "settlements", "meta", "logs"):
    print(f"{name}: deleted {wipe(db.collection(name))}")
