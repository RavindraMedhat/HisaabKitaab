import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

if not firebase_admin._apps:
    if "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
    else:
        cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred)

db = firestore.client()
