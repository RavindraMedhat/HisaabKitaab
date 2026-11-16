#!/usr/bin/env python3
"""Restore users, expenses and settlements from a backup made by wipe_all.py, then rebuild derived data.

Usage:  python scripts/restore_backup.py ~/hisaabkitaab_backup/before_wipe_YYYYMMDD_HHMMSS.pickle
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")

from services.firebase import db
from services.ledger import rebuild_all

if len(sys.argv) != 2:
    sys.exit(__doc__)
data = pickle.load(open(os.path.expanduser(sys.argv[1]), "rb"))
for coll in ("users", "expenses", "settlements"):
    for did, doc in data.get(coll, {}).items():
        db.collection(coll).document(did).set(doc)
    print("restored", coll, len(data.get(coll, {})))
print(rebuild_all())
