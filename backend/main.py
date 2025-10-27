# backend/main.py
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import joblib
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime, date
from urllib.parse import urlparse
import pandas as pd
from typing import Generator
from fastapi.middleware.cors import CORSMiddleware

# 🧩 관리자모드 설정 로드
from config import ADMIN_MODE, ADMIN_DATE, CURRENT_DATE, SEASON_MODE

# --- 1. DB & Firebase 환경 설정 및 초기화 ---

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_PATH = "lgbm_kbo_predictor_tuned.pkl"

engine = None
if not DATABASE_URL:
    print("🚨 DATABASE_URL이 설정되지 않았습니다. DB 관련 기능이 작동하지 않습니다.")
else:
    engine = create_engine(DATABASE_URL, client_encoding='utf8')
    
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session() -> Generator:
    if not engine: raise RuntimeError("DB 연결 엔진이 준비되지 않았습니다.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Firebase 초기화 및 Firestore 클라이언트 정의
db_fs = None
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-credentials.json")
        initialize_app(cred)
    db_fs = firestore.client()
except Exception as e:
    print(f"🚨 Firebase 초기화 실패: {e}. 퀴즈/랭킹 기능이 작동하지 않습니다.")
    
# Firestore 유틸리티 함수
def add_quiz_points(user_id: str, points: int, display_name: str):
    if not db_fs: return
    user_ref = db_fs.collection("users").document(user_id)
    user_ref.set({
        "displayName": display_name,
        "quiz_score": firestore.Increment(points), 
        "total_score": firestore.Increment(points), 
        "weekly_score": firestore.Increment(points), 
        "updated_at": datetime.utcnow()
    }, merge=True)

def add_ai_game_points(user_id: str, base_points: int, bonus_points: int, display_name: str):
    if not db_fs: return
    total = base_points + bonus_points
    user_ref = db_fs.collection("users").document(user_id)
    user_ref.set({
        "displayName": display_name,
        "ai_score": firestore.Increment(total), 
        "total_score": firestore.Increment(total), 
        "weekly_score": firestore.Increment(total), 
        "updated_at": datetime.utcnow()
    }, merge=True)

def get_user_snapshot(user_id: str):
    if not db_fs: return {}
    snap = db_fs.collection("users").document(user_id).get()
    return snap.to_dict() if snap.exists else {}

def save_user_prediction_to_firestore(user_id: str, predicted_win: int):
    if not db_fs: return
    user_ref = db_fs.collection("users").document(user_id)
    user_ref.set({"last_prediction": predicted_win, "prediction_timestamp": datetime.utcnow()}, merge=True)

# DB 테이블 초기화 함수
def init_tables():
    if not engine: return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS game_results (
                    game_id TEXT PRIMARY KEY, game_date DATE NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
                    home_score INTEGER NOT NULL, away_score INTEGER NOT NULL, samsung_win INTEGER, created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS team_rank (
                    team_name TEXT PRIMARY KEY, rank INTEGER NOT NULL, games INTEGER NOT NULL, wins INTEGER NOT NULL,
                    losses INTEGER NOT NULL, draws INTEGER NOT NULL, win_rate FLOAT NOT NULL, game_gap TEXT,
                    last10 TEXT, streak TEXT, home_record TEXT, away_record TEXT, updated_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS kbo_cleaned_games (
                    game_id VARCHAR(20) PRIMARY KEY, game_date DATE NOT NULL, home_team VARCHAR(50) NOT NULL,
                    away_team VARCHAR(50) NOT NULL, home_score INT, away_score INT, winning_team VARCHAR(50)
                );
            """))
        print("✅ DB 테이블 초기화 완료.")
    except Exception as e:
        print(f"❌ DB 테이블 초기화 오류: {e}")

if not ADMIN_MODE:
    init_tables()
else:
    print("🧪 [관리자모드] DB 구조만 유지, 자동 초기화 루틴 비활성화됨")

# ---------------------------------------------------
# 2. 서비스 라우터 import 및 함수 대체
# ---------------------------------------------------
import model_service
import performance_service
from crawler_service import router as crawler_router, run_daily_crawl
from feature_service import router as feature_router, build_features
from model_service import router as model_router, api_predict_today
from ranking_service import router as ranking_router
from auth_utils import verify_admin_api_key

# model_service의 save_user_prediction 함수를 Firestore 저장 함수로 지정
model_service.save_user_prediction = save_user_prediction_to_firestore

# 퀴즈 및 관리자 라우터 정의
quiz_router = APIRouter(tags=["quiz"])
admin_router = APIRouter(tags=["admin"])

@quiz_router.get("/quiz")
def api_get_quiz():
    q = text("SELECT id, difficulty, question, options, source_hint FROM samfan_quizzes ORDER BY RANDOM() LIMIT 1")
    if not engine: raise HTTPException(status_code=500, detail="DB 연결 오류")
    df = pd.read_sql(q, engine)
    if df.empty: raise HTTPException(status_code=404, detail="퀴즈가 없습니다. DB를 채워주세요.")
    row = df.iloc[0].to_dict()
    return {"quiz_id": row["id"], "difficulty": row["difficulty"], "question": row["question"], "options": row["options"], "source_hint": row["source_hint"]}

@quiz_router.post("/quiz/submit")
def api_submit_quiz(user_id: str, quiz_id: int, answer: str, display_name: str):
    """사용자가 제출한 퀴즈 정답을 채점하고 점수를 부여합니다."""
    if not engine:
        raise HTTPException(status_code=500, detail="DB 연결 오류")

    # ✅ [핵심 수정] 'answer' 컬럼을 'correct_answer'로 변경했습니다.
    query = text("SELECT correct_answer, difficulty FROM samfan_quizzes WHERE id = :quiz_id")
    with engine.connect() as conn:
        quiz_data = conn.execute(query, {"quiz_id": quiz_id}).fetchone()

    if not quiz_data:
        raise HTTPException(status_code=404, detail="존재하지 않는 퀴즈 ID입니다.")

    correct_answer, difficulty = quiz_data # 이제 올바른 정답을 가져옵니다.

    # 정답을 비교하고 점수를 계산합니다.
    if answer.strip() == correct_answer.strip():
        points_map = {"쉬움": 5, "보통": 10, "어려움": 15}
        gained_points = points_map.get(difficulty, 10)
        
        if not ADMIN_MODE:
            add_quiz_points(user_id, gained_points, display_name)
        else:
            print(f"🧪 [관리자모드] 퀴즈 점수 부여 생략: {display_name}님 {gained_points}포인트")

        return {"correct": True, "gained_points": gained_points}
    else:
        return {"correct": False, "gained_points": 0}

# ---------------------------------------------------
# 3. FastAPI 앱 정의
# ---------------------------------------------------
app = FastAPI(
    title="Laions Backend (Final Portfolio)",
    description="삼성 라이온즈 팬 전용 AI 예측 / 퀴즈 / 랭킹 서비스 백엔드 (관리자모드 통합)",
    version="1.0.1",
    openapi_tags=[
        {"name": "admin", "description": "관리자 전용 API (API Key 필요)"}
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# 4. AI 모델 로드
# ---------------------------------------------------
@app.on_event("startup")
async def load_model_on_startup():
    print("서버 시작: AI 예측 모델 로드 중...")
    try:
        model_service.model = joblib.load(MODEL_PATH)
        print("✅ 서버 시작: AI 예측 모델 로드 완료.")
    except Exception as e:
        print(f"🚨 모델 로드 실패: {e}")

# ---------------------------------------------------
# 5. 관리자용 API
# ---------------------------------------------------
@admin_router.post("/admin/daily-pipeline")
def api_daily_pipeline(admin_key: str = Depends(verify_admin_api_key)):
    if not engine:
        raise HTTPException(status_code=500, detail="DB 연결 엔진이 준비되지 않았습니다.")

    if ADMIN_MODE:
        print("🧪 [관리자모드] daily_pipeline 시연용 모드 실행 (DB 미갱신)")
        return {
            "status": "ok (admin)",
            "message": f"시연모드 실행 — {ADMIN_DATE} 기준 시즌 모드: {SEASON_MODE}",
            "updated": False
        }

    print("\n--- 🚀 일일 데이터 정산 파이프라인 실행 시작 ---")
    crawl_res = run_daily_crawl()
    game_df = crawl_res.get("game_df")
    if game_df is None or game_df.empty:
        message = "어제 경기 결과가 없어 데이터 업데이트를 건너뜁니다."
        print(f"   -> {message}")
        return {"status": "ok", "message": message}

    try:
        feat_df = build_features()
        print(f"✅ 피처 생성 완료 ({len(feat_df)} rows)")
    except Exception as e:
        print(f"❌ 피처 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피처 생성 오류: {e}")

    print("✅ daily_pipeline 완료")
    return {"status": "ok", "message": "Daily pipeline executed successfully."}

def admin_reset_weekly_scores():
    if not db_fs:
        raise HTTPException(status_code=503, detail="Firestore 클라이언트를 사용할 수 없습니다.")

    users_ref = db_fs.collection("users")
    docs = users_ref.stream()
    
    reset_count = 0
    for doc in docs:
        doc.reference.update({"weekly_score": 0})
        reset_count += 1
        
    print(f"✅ 주간 점수 초기화 완료. 총 {reset_count}명의 사용자에게 적용되었습니다.")
    return {"reset_count": reset_count}

@admin_router.post("/admin/reset-weekly-scores")
def api_reset_weekly_scores(admin_key: str = Depends(verify_admin_api_key)):
    if ADMIN_MODE:
        print("🧪 [관리자모드] reset-weekly-scores는 실제 DB에 반영되지 않습니다.")
        return {"status": "ok (admin)", "message": "시연용 관리자모드 - 실제 DB 리셋 없음."}
    try:
        result = admin_reset_weekly_scores()
        return {"status": "ok", "message": f"Weekly scores reset complete. {result.get('reset_count', 0)} users affected."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weekly reset failed: {str(e)}")

@admin_router.post("/admin/simulate-game-result")
def api_simulate_game_result(
    game_id: str,
    samsung_actual_win: int,
    admin_key: str = Depends(verify_admin_api_key)
):
    if not engine:
        raise HTTPException(status_code=500, detail="DB 연결 엔진이 준비되지 않았습니다.")
    try:
        ai_predicted_prob = 0.5
        ai_predicted_win = 1 if ai_predicted_prob >= 0.5 else 0
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO ai_predictions (game_id, game_date, predicted_win, predicted_prob)
                VALUES (:game_id, :game_date, :predicted_win, :predicted_prob)
                ON CONFLICT (game_id) DO UPDATE SET predicted_win = EXCLUDED.predicted_win;
            """), {
                "game_id": game_id,
                "game_date": CURRENT_DATE,
                "predicted_win": ai_predicted_win,
                "predicted_prob": ai_predicted_prob
            })
            conn.execute(text("""
                INSERT INTO game_results (game_id, game_date, home_team, away_team, home_score, away_score, samsung_win)
                VALUES (:gid, :gdate, '삼성', '상대팀', 1, 0, :swin)
                ON CONFLICT (game_id) DO UPDATE SET samsung_win = EXCLUDED.samsung_win;
            """), {"gid": game_id, "gdate": CURRENT_DATE, "swin": samsung_actual_win})
        return {"status": "ok", "message": f"{game_id} 경기의 예측과 결과가 DB에 기록되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------
# 6. 라우터 등록
# ---------------------------------------------------
app.include_router(admin_router, prefix="/api")
app.include_router(quiz_router, prefix="/api")
app.include_router(crawler_router, prefix="/api", tags=["crawl / data"])
app.include_router(feature_router, prefix="/api", tags=["features"])
app.include_router(model_router, prefix="/api", tags=["model / prediction"])
app.include_router(performance_service.router, prefix="/api", tags=["ai performance"])
app.include_router(ranking_router, prefix="/api", tags=["ranking"])

# ---------------------------------------------------
# 7. 기본 API
# ---------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "admin_mode": ADMIN_MODE,
        "current_date": str(CURRENT_DATE),
        "season_mode": SEASON_MODE
    }

@app.get("/")
def root():
    return {
        "service": "Laions Backend (Final Portfolio)",
        "admin_mode": ADMIN_MODE,
        "current_date": str(CURRENT_DATE),
        "season_mode": SEASON_MODE,
        "team": "삼성 라이온즈 팬 서비스",
        "features": [
            "AI 경기 예측 (ELO, Form, Pythagorean 기반)",
            "몬테카를로 시즌/포스트시즌 순위 예측",
            "주간 랭킹 시스템",
            "일일 자동화 파이프라인 통합",
            "관리자모드 통합 (.env 기반)"
        ],
    }