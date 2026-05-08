# backend/services/ranking_service.py
"""
랭킹 서비스 - Supabase 기반으로 리팩토링
Firebase Firestore 의존성을 제거하고 Supabase(PostgreSQL)로 통합합니다.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import datetime, timedelta
import logging

from config import engine, CURRENT_DATE
from supabase_config import upsert_user_score, get_user_rankings, reset_weekly_scores

router = APIRouter(prefix="/api/ranking", tags=["ranking"])
logger = logging.getLogger(__name__)

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
        """
        AI 예측 결과와 비교하여 유저 점수를 정산합니다.
        Firestore 대신 Supabase user_profiles 테이블에 점수를 기록합니다.
        """
        with engine.connect() as conn:
            # 1. 경기 결과 + AI 예측 결과 한 번에 가져오기 (JOIN 사용)
            query = text(f"""
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
            if not game_ids:
                return {"status": "skipped", "message": "정산할 game_ids가 없습니다."}
            user_preds = conn.execute(text("""
                SELECT user_id, game_id, predicted_winner
                FROM user_predictions
                WHERE game_id IN :game_ids
            """), {"game_ids": game_ids}).fetchall()

            # 3. 점수 계산 로직 (AI vs 인간 대결 반영)
            user_points = {}
            for row in user_preds:
                truth = truth_table.get(row.game_id)
                if not truth:
                    continue

                # 유저가 맞췄을 경우
                if row.predicted_winner == truth["winner"]:
                    points = SCORE_POLICY["PREDICTION_BASE"]
                    # 🚀 [가산점] AI가 틀렸는데 유저가 맞췄다면?
                    if truth["ai_wrong"]:
                        points = SCORE_POLICY["PREDICTION_AI_UPSET"]
                    
                    user_points[row.user_id] = user_points.get(row.user_id, 0) + points

            # 4. Supabase에 점수 반영 (Firestore 대체)
            if user_points:
                for uid, points in user_points.items():
                    # user_profiles 테이블에서 닉네임 조회
                    nickname = conn.execute(
                        text("SELECT nickname FROM user_profiles WHERE user_id = :uid"),
                        {"uid": uid}
                    ).scalar() or uid[:8]
                    
                    upsert_user_score(
                        user_id=uid,
                        nickname=nickname,
                        score_earned=points,
                        score_type="prediction_score"
                    )

            return {"status": "ok", "updated_users": len(user_points)}

    @staticmethod
    def add_quiz_score(user_id: str, difficulty: str, nickname: str = "익명"):
        """난이도별 퀴즈 점수를 Supabase에 합산합니다."""
        points = SCORE_POLICY["QUIZ"].get(difficulty.lower(), 0)
        if points == 0:
            raise HTTPException(status_code=400, detail="잘못된 난이도 설정")

        success = upsert_user_score(
            user_id=user_id,
            nickname=nickname,
            score_earned=points,
            score_type="quiz_score"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="점수 저장에 실패했습니다.")
        
        return {"status": "ok", "earned_points": points}

    @staticmethod
    def reset_weekly_ranking():
        """주간 랭킹 초기화 (매주 월요일 0시 호출용)"""
        success = reset_weekly_scores()
        if not success:
            raise HTTPException(status_code=500, detail="주간 점수 초기화 실패")
        return {"status": "reset_done"}


# ============================================================
# API Endpoints
# ============================================================

@router.get("/top")
def get_top_ranking(limit: int = 10):
    """Supabase에서 주간 랭킹 상위 N명을 조회합니다. (weekly_score 기준)"""
    try:
        rankings = get_user_rankings(limit=limit, order_by="weekly_score")
        return {"status": "ok", "rankings": rankings}
    except Exception as e:
        logger.error(f"랭킹 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"랭킹 조회 실패: {str(e)}")
