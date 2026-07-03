import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

if not firebase_admin._apps:
    fc = os.getenv("FIREBASE_CREDENTIALS")
    if fc:
        # Cloud Run: full JSON stored as env var
        cred = credentials.Certificate(json.loads(fc))
    else:
        # Local dev: path to serviceAccountKey.json file
        cred = credentials.Certificate(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")
        )
    firebase_admin.initialize_app(cred)

db = firestore.client()
