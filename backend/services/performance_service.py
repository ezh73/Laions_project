# backend/services/performance_service.py
from fastapi import APIRouter, Query
from sqlalchemy import text
import pandas as pd
from config import engine, CURRENT_DATE, SEASON_MODE

router = APIRouter(prefix="/api/performance", tags=["ai performance"])

class PerformanceService:
    @staticmethod
    def get_ai_accuracy(limit: int = 10, season_mode: str = None):
        """
        AI 예측(ai_predictions)과 실제 결과(kbo_games)를 조인하여 적중률을 계산합니다.
        
        모드별 동작:
        - season (정규시즌): 최근 N경기 성적 (기본 10경기)
        - postseason (포스트시즌): 당해 정규시즌 전체 성적
        - offseason (오프시즌): 당해 정규시즌 + 포스트시즌 전체 성적
        """
        mode = season_mode or SEASON_MODE
        current_year = CURRENT_DATE.year
        
        if mode == "postseason":
            # 포스트시즌: 당해 정규시즌 전체 성적
            query = text(f"""
                SELECT
                    p.game_id,
                    p.game_date,
                    p.predicted_winner,
                    g.winning_team,
                    p.prediction_prob
                FROM ai_predictions p
                JOIN kbo_games g ON p.game_id = g.game_id
                WHERE g.winning_team IS NOT NULL
                  AND g.winning_team != '무승부'
                  AND g.is_postseason = FALSE
                  AND EXTRACT(YEAR FROM p.game_date) = :year
                  AND p.game_date <= :today
                ORDER BY p.game_date DESC, p.game_id DESC
            """)
            params = {"year": current_year, "today": CURRENT_DATE}
        elif mode == "offseason":
            # 오프시즌: 당해 정규시즌 + 포스트시즌 전체 성적
            query = text(f"""
                SELECT
                    p.game_id,
                    p.game_date,
                    p.predicted_winner,
                    g.winning_team,
                    p.prediction_prob
                FROM ai_predictions p
                JOIN kbo_games g ON p.game_id = g.game_id
                WHERE g.winning_team IS NOT NULL
                  AND g.winning_team != '무승부'
                  AND EXTRACT(YEAR FROM p.game_date) = :year
                  AND p.game_date <= :today
                ORDER BY p.game_date DESC, p.game_id DESC
            """)
            params = {"year": current_year, "today": CURRENT_DATE}
        else:
            # 정규시즌 (기본): 최근 N경기 성적
            query = text(f"""
                SELECT
                    p.game_id,
                    p.game_date,
                    p.predicted_winner,
                    g.winning_team,
                    p.prediction_prob
                FROM ai_predictions p
                JOIN kbo_games g ON p.game_id = g.game_id
                WHERE g.winning_team IS NOT NULL
                  AND g.winning_team != '무승부'
                  AND p.game_date <= :today
                ORDER BY p.game_date DESC, p.game_id DESC
                LIMIT :limit
            """)
            params = {"limit": limit, "today": CURRENT_DATE}
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
            
        if df.empty:
            return {
                "accuracy": 0,
                "total_games": 0,
                "correct_predictions": 0,
                "recent_results": [],
                "season_mode": mode
            }

        # 정답 여부 판별
        df['is_correct'] = df['predicted_winner'] == df['winning_team']
        
        total_games = len(df)
        correct_predictions = int(df['is_correct'].sum())
        accuracy_rate = round((correct_predictions / total_games) * 100, 1)

        # 프론트엔드 카드에 띄워줄 최근 5경기 하이라이트
        recent_highlights = df.head(5).to_dict(orient="records")

        return {
            "accuracy": accuracy_rate,
            "total_games": total_games,
            "correct_predictions": correct_predictions,
            "recent_results": recent_highlights,
            "season_mode": mode
        }

@router.get("/")
def api_ai_performance(
    limit: int = Query(10, description="최근 N경기 (정규시즌 모드에서만 사용)"),
    season_mode: str = Query(None, description="시즌 모드 강제 지정 (season/postseason/offseason)")
):
    """
    프론트엔드 대시보드용: AI 예측 적중률을 반환합니다.
    season_mode 파라미터로 모드별 성적을 조회할 수 있습니다.
    """
    stats = PerformanceService.get_ai_accuracy(limit, season_mode)
    return {"status": "ok", "data": stats}