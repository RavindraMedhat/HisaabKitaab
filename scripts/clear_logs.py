#!/usr/bin/env python3
"""
Delete all documents from the Firebase logs collection.

Usage:
    python scripts/clear_logs.py
"""

import os

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")

import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    ))

db = firestore.client()

docs = list(db.collection("logs").stream())
if not docs:
    print("Logs collection is already empty.")
else:
    confirm = input(f"Delete {len(docs)} log document(s)? [y/N] ")
    if confirm.lower() == "y":
        for doc in docs:
            doc.reference.delete()
        print(f"Deleted {len(docs)} document(s).")
    else:
        print("Aborted.")
