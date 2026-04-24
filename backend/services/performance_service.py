# backend/services/performance_service.py
from fastapi import APIRouter
from sqlalchemy import text
import pandas as pd
from config import engine, TABLE_AI_PREDICTIONS, TABLE_KBO_GAMES, CURRENT_DATE

router = APIRouter(prefix="/api/performance", tags=["ai performance"])

class PerformanceService:
    @staticmethod
    def get_ai_accuracy(limit: int = 10):
        """
        AI 예측(ai_predictions)과 실제 결과(kbo_games)를 조인하여 최근 N경기의 적중률을 계산합니다.
        """
        query = text(f"""
            SELECT 
                p.game_id, 
                p.game_date, 
                p.predicted_winner, 
                g.winning_team,
                p.prediction_prob
            FROM {TABLE_AI_PREDICTIONS} p
            JOIN {TABLE_KBO_GAMES} g ON p.game_id = g.game_id
            WHERE g.winning_team IS NOT NULL 
              AND g.winning_team != '무승부'
              AND p.game_date <= :today
            ORDER BY p.game_date DESC, p.game_id DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"limit": limit, "today": CURRENT_DATE})
            
        if df.empty:
            return {"accuracy": 0, "total_games": 0, "correct_predictions": 0, "recent_results": []}

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
            "recent_results": recent_highlights
        }

@router.get("/")
def api_ai_performance(limit: int = 10):
    """프론트엔드 대시보드용: 최근 AI 예측 적중률을 반환합니다."""
    stats = PerformanceService.get_ai_accuracy(limit)
    return {"status": "ok", "data": stats}