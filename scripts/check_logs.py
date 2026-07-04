#!/usr/bin/env python3
"""
Check Firebase error logs for HisaabKitaab.

Usage:
    python scripts/check_logs.py           # last 20 errors
    python scripts/check_logs.py --limit 5
    python scripts/check_logs.py --tail    # poll every 10s for new errors
"""

import argparse
import os
import sys
import time
from datetime import timezone

# ── Bootstrap Firebase ────────────────────────────────────────────────────────
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")

import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    ))

db = firestore.client()


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_logs(limit: int = 20) -> list:
    docs = (
        db.collection("logs")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def fmt_log(doc: dict) -> str:
    ts       = doc.get("timestamp", "")
    msg      = doc.get("message", "")
    exc      = doc.get("exception", "")
    extra    = doc.get("extra", {})
    tb       = doc.get("traceback", "")

    lines = [
        f"\n{'─'*64}",
        f"  time : {ts}",
        f"  msg  : {msg}",
    ]
    if exc:
        lines.append(f"  exc  : {exc}")
    if extra:
        for k, v in extra.items():
            lines.append(f"  {k:<5}: {v}")
    if tb:
        # Show last 4 lines of traceback — most relevant
        tb_tail = "\n".join(tb.strip().splitlines()[-4:])
        lines.append(f"  trace:\n    {tb_tail.replace(chr(10), chr(10) + '    ')}")
    return "\n".join(lines)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_show(limit: int):
    logs = fetch_logs(limit)
    if not logs:
        print("No error logs found.")
        return
    print(f"Showing {len(logs)} most recent error(s):")
    for doc in logs:
        print(fmt_log(doc))
    print(f"\n{'─'*64}")


def cmd_tail():
    print("Tailing Firebase logs (Ctrl+C to stop)...\n")
    seen = set()
    while True:
        logs = fetch_logs(20)
        for doc in logs:
            if doc["id"] not in seen:
                seen.add(doc["id"])
                print(fmt_log(doc))
        time.sleep(10)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HisaabKitaab Firebase log viewer")
    parser.add_argument("--limit", type=int, default=20, help="Number of logs to show")
    parser.add_argument("--tail",  action="store_true",  help="Poll for new errors every 10s")
    args = parser.parse_args()

    try:
        if args.tail:
            cmd_tail()
        else:
            cmd_show(args.limit)
    except KeyboardInterrupt:
        print("\nStopped.")
