# backend/services/simulation_service.py
from fastapi import APIRouter
import pandas as pd
from sqlalchemy import text
from config import engine, TEAMS, FEATURE_CONFIG, TABLE_MATCH_FEATURES
from services.model_service import ModelService
from services.model_preprocessor import ModelPreprocessor

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

class SimulationService:
    @classmethod
    def get_season_projection(cls):
        """모든 팀 간의 가상 대진을 시뮬레이션하여 최종 기대 순위를 계산합니다."""
        model = ModelService.get_model()
        if not model:
            return []

        # 1. 각 팀의 '가장 최신' 전력 상태(ELO, Form 등) 가져오기
        latest_stats = []
        with engine.connect() as conn:
            for team in TEAMS:
                query = text(f"""
                    SELECT * FROM {TABLE_MATCH_FEATURES} 
                    WHERE home_team = :team OR away_team = :team
                    ORDER BY game_date DESC LIMIT 1
                """)
                res = conn.execute(query, {"team": team}).fetchone()
                if res:
                    # 해당 팀이 홈이었는지 원정이었는지에 따라 최신 스탯 추출
                    is_home = (res.home_team == team)
                    latest_stats.append({
                        "team": team,
                        "elo": res.home_elo if is_home else res.away_elo,
                        "form": res.home_form if is_home else res.away_form,
                        "streak": res.home_streak if is_home else res.away_streak,
                        "pyth": res.home_pythagorean if is_home else res.away_pythagorean,
                        "recent_rd": res.home_recent_rd if is_home else res.away_recent_rd
                    })

        if not latest_stats:
            return []

        stats_df = pd.DataFrame(latest_stats)
        
        # 2. 모든 팀 쌍(Pair)에 대한 가상 대진 생성 (총 90개 조합)
        virtual_matches = []
        for home in latest_stats:
            for away in latest_stats:
                if home['team'] == away['team']: continue
                
                virtual_matches.append({
                    "home_team": home['team'],
                    "away_team": away['team'],
                    "home_elo": home['elo'],
                    "away_elo": away['elo'],
                    "home_form": home['form'],
                    "away_form": away['form'],
                    "home_streak": home['streak'],
                    "away_streak": away['streak'],
                    "home_pythagorean": home['pyth'],
                    "away_pythagorean": away['pyth'],
                    "home_recent_rd": home['recent_rd'],
                    "away_recent_rd": away['recent_rd'],
                    "home_matchup_rd": 0.0,
                    "away_matchup_rd": 0.0,
                    "season_matchup_count": 0,
                    "rest_diff": 0 # 가상 대진이므로 휴식일 차이는 0으로 가정
                })

        v_df = pd.DataFrame(virtual_matches)
        
        # 3. 승률 예측 및 팀별 평균 기대 승률 계산
        X = ModelPreprocessor.preprocess_data(v_df)
        v_df['win_prob'] = model.predict_proba(X)[:, 1]
        
        # 각 팀이 홈/원정일 때의 모든 기대 승률을 평균내어 시즌 기대 승률 도출
        projection = v_df.groupby("home_team")['win_prob'].mean().reset_index()
        projection.columns = ['team', 'expected_win_rate']
        
        # 144경기 기준 예상 승수 계산
        projection['expected_wins'] = (projection['expected_win_rate'] * 144).round(1)
        projection = projection.sort_values(by="expected_win_rate", ascending=False).reset_index(drop=True)
        projection['predicted_rank'] = projection.index + 1

        return projection.to_dict(orient="records")

@router.get("/projection")
def get_projection():
    """AI가 예측한 시즌 최종 순위 리포트를 반환합니다."""
    result = SimulationService.get_season_projection()
    return {"status": "ok", "data": result}