# backend/firebase_config.py
import firebase_admin
from firebase_admin import credentials, firestore

db_fs = None
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-credentials.json")
        firebase_admin.initialize_app(cred)
    db_fs = firestore.client()
    print("🔥 [Firebase] Firestore 연결 성공")
except Exception as e:
    print(f"⚠️ [Firebase] Firestore 연결 실패: {e}")
