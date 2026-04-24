# backend/services/ranking_service.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from datetime import datetime, timedelta
import logging

# Firestore 및 설정 로드
from firebase_config import db_fs
from firebase_admin import firestore
from config import engine, CURRENT_DATE, ADMIN_MODE
from auth_utils import verify_admin_api_key

router = APIRouter(prefix="/api/ranking", tags=["ranking"])
logger = logging.getLogger(__name__)

# 모드에 따른 컬렉션 분리
COLLECTION_USERS = "users_admin" if ADMIN_MODE else "users"

# --- 점수 정책 설정 (스케일링) ---
SCORE_POLICY = {
    "PREDICTION_BASE": 10,      # 기본 예측 성공
    "PREDICTION_AI_UPSET": 15,  # AI가 틀린 걸 유저가 맞춘 경우 (가산점)
    "QUIZ": {
        "easy": 5,
        "medium": 10,
        "hard": 20
    }
}

class RankingService:
    @staticmethod
    def settle_daily_points(target_date):
        """AI 예측 결과와 비교하여 유저 점수를 정산합니다."""
        if not db_fs: return {"status": "error", "message": "Firestore 연결 없음"}

        with engine.connect() as conn:
            # 1. 경기 결과 + AI 예측 결과 한 번에 가져오기 (JOIN 사용)
            query = text("""
                SELECT 
                    g.game_id, 
                    g.winning_team,
                    a.predicted_winner as ai_pick
                FROM kbo_games g
                LEFT JOIN ai_predictions a ON g.game_id = a.game_id
                WHERE g.game_date = :target_date 
                  AND g.winning_team IS NOT NULL 
                  AND g.winning_team != '무승부'
            """)
            results = conn.execute(query, {"target_date": target_date}).fetchall()
            
            if not results:
                return {"status": "skipped", "message": "정산할 결과 없음"}

            # 정답지 생성: {game_id: {"winner": "삼성", "ai_wrong": True/False}}
            truth_table = {}
            for r in results:
                truth_table[r.game_id] = {
                    "winner": r.winning_team,
                    "ai_wrong": r.ai_pick != r.winning_team
                }

            # 2. 유저들의 모든 예측 데이터 가져오기
            game_ids = tuple(truth_table.keys())
            user_preds = conn.execute(text("""
                SELECT user_id, game_id, predicted_winner 
                FROM user_predictions 
                WHERE game_id IN :game_ids
            """), {"game_ids": game_ids}).fetchall()

            # 3. 점수 계산 로직 (AI vs 인간 대결 반영)
            user_points = {}
            for row in user_preds:
                truth = truth_table.get(row.game_id)
                if not truth: continue

                # 유저가 맞췄을 경우
                if row.predicted_winner == truth["winner"]:
                    points = SCORE_POLICY["PREDICTION_BASE"]
                    # 🚀 [가산점] AI가 틀렸는데 유저가 맞췄다면?
                    if truth["ai_wrong"]:
                        points = SCORE_POLICY["PREDICTION_AI_UPSET"]
                    
                    user_points[row.user_id] = user_points.get(row.user_id, 0) + points

            # 4. Firestore 일괄 업데이트
            if user_points:
                cls._update_firestore_scores(user_points, "prediction")

            return {"status": "ok", "updated_users": len(user_points)}

    @staticmethod
    def add_quiz_score(user_id: str, difficulty: str):
        """난이도별 퀴즈 점수를 합산합니다."""
        points = SCORE_POLICY["QUIZ"].get(difficulty.lower(), 0)
        if points == 0:
            raise HTTPException(status_code=400, detail="잘못된 난이도 설정")

        # 🚀 공정성을 위해 유저당 하루 퀴즈 횟수 제한 로직을 여기에 추가할 수 있습니다.
        
        RankingService._update_firestore_scores({user_id: points}, "quiz")
        return {"status": "ok", "earned_points": points}

    @classmethod
    def _update_firestore_scores(cls, user_points_map, source_type):
        """Firestore에 주간 및 누적 점수를 반영합니다."""
        batch = db_fs.batch()
        for uid, points in user_points_map.items():
            user_ref = db_fs.collection(COLLECTION_USERS).document(uid)
            batch.set(user_ref, {
                "total_score": firestore.Increment(points),
                "weekly_score": firestore.Increment(points),
                f"{source_type}_score": firestore.Increment(points), # 점수 출처 기록
                "updated_at": datetime.utcnow()
            }, merge=True)
        batch.commit()

    @staticmethod
    def reset_weekly_ranking():
        """주간 랭킹 초기화 (매주 월요일 0시 호출용)"""
        users_ref = db_fs.collection(COLLECTION_USERS)
        docs = users_ref.where("weekly_score", ">", 0).stream()
        
        batch = db_fs.batch()
        for doc in docs:
            batch.update(doc.reference, {"weekly_score": 0})
        batch.commit()
        return {"status": "reset_done"}
