#!/usr/bin/env python3
"""Rebuild all derived data (balances, feeds, friend history, monthly reports)
from the canonical expenses/settlements. Safe to run any time.

Usage:  python scripts/rebuild_cache.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")

from services.ledger import rebuild_all

print(rebuild_all())
