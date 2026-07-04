import traceback
from datetime import datetime, timezone


def log_error(message: str, exc: Exception = None, **extra):
    """Write a single error record to Firestore logs collection.
    Fire-and-forget — never raises, never slows down the caller."""
    try:
        from services.firebase import db
        doc = {
            "level":     "ERROR",
            "message":   str(message),
            "timestamp": datetime.now(timezone.utc),
        }
        if exc is not None:
            doc["exception"] = type(exc).__name__
            doc["traceback"] = traceback.format_exc()
        if extra:
            doc["extra"] = {k: str(v) for k, v in extra.items()}
        db.collection("logs").add(doc)
    except Exception:
        pass  # logging must never crash the app
