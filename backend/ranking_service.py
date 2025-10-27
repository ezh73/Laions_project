# backend/ranking_service.py
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy import create_engine, text
from auth_utils import verify_admin_api_key
import pandas as pd
import numpy as np
import os, math, random
# ✅ config.py에서 시즌 모드를 직접 가져옵니다.
from config import SEASON_MODE, ADMIN_DATE
import traceback

router = APIRouter()

# Firebase / 모델 / 기능 모듈 불러오기
try:
    from main import db_fs, add_quiz_points, add_ai_game_points, get_user_snapshot
    from feature_service import calculate_elo_and_features
    from model_service import model # model_service에서 학습된 모델을 가져옵니다.
    TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']
except ImportError:
    # (기존 예외 처리 코드 유지)
    class FirestorePlaceholder:
        def collection(self, name): return self
        def document(self, doc_id): return self
        def get(self): return self
        def exists(self): return False
        def to_dict(self): return {}
        def stream(self): return iter([])
    db_fs = FirestorePlaceholder()
    def add_quiz_points(u, p): pass
    def add_ai_game_points(u, b, bo): pass
    def get_user_snapshot(u): return {}
    TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']
    model = None

# DB 설정
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')


# =============================================================
# ⚾️ 포스트시즌 시뮬레이션 헬퍼 함수 (신규 추가)
# =============================================================

def _predict_match_win_prob(team1_name, team2_name, all_teams_data, model_instance):
    """
    AI 모델을 사용하여 임의의 두 팀 간의 단일 경기에서 team1의 승리 확률을 예측합니다.
    """
    if model_instance is None:
        raise HTTPException(status_code=503, detail="AI 모델이 로드되지 않았습니다.")

    try:
        team1_stats = all_teams_data[all_teams_data['team'].str.lower() == team1_name.lower()].iloc[0]
        team2_stats = all_teams_data[all_teams_data['team'].str.lower() == team2_name.lower()].iloc[0]
    except IndexError:
        raise ValueError(f"{team1_name} 또는 {team2_name}의 데이터를 찾을 수 없습니다.")

    # model_service.py의 피처 생성 로직과 동일하게 구성
    X = pd.DataFrame([{
        "samsung_elo": team1_stats.get("elo", 1500),
        "opponent_elo": team2_stats.get("elo", 1500),
        "rest_diff": 0,
        "samsung_form": team1_stats.get("predicted_win", 0.5),
        "opponent_form": team2_stats.get("predicted_win", 0.5),
        "samsung_pythagorean": team1_stats.get("predicted_win", 0.5),
        "opponent_pythagorean": team2_stats.get("predicted_win", 0.5)
    }])
    
    # 모델을 사용해 team1의 승리 확률(proba[1]) 예측
    win_prob = model_instance.predict_proba(X)[0][1]
    return float(win_prob)

def _calculate_series_win_prob(team1_name, team2_name, num_games, all_teams_data, model_instance, simulations=5000):
    """
    단일 경기 승률을 기반으로 몬테카를로 시뮬레이션을 실행하여,
    정해진 시리즈(num_games)에서 team1이 최종 승리할 확률을 계산합니다.
    """
    team1_total_series_wins = 0
    team1_single_game_win_prob = _predict_match_win_prob(team1_name, team2_name, all_teams_data, model_instance)

    for _ in range(simulations):
        team1_wins = 0
        team2_wins = 0
        win_target = (num_games // 2) + 1

        while team1_wins < win_target and team2_wins < win_target:
            if random.random() < team1_single_game_win_prob:
                team1_wins += 1
            else:
                team2_wins += 1
        
        if team1_wins == win_target:
            team1_total_series_wins += 1
            
    return team1_total_series_wins / simulations


# =============================================================
# 📊 시즌 예측 / 포스트시즌 예측 통합 API
# =============================================================

@router.get("/ranking/season-projection")
def api_get_season_projection():
    """
    시스템의 SEASON_MODE에 따라 적절한 예측 결과를 반환합니다.
    - season: 정규시즌 순위 예측
    - postseason: 삼성의 포스트시즌 단계별 진출 확률
    - offseason: 다음 시즌 순위 예측 (기존 로직 재활용)
    """
    try:
        # -------------------------------------------------
        # ⚾️ 1. 정규시즌 (season) 모드
        # -------------------------------------------------
        if SEASON_MODE == "season":
            print("🏟️ 정규시즌 모드 → season_projection_demo.csv 로드 중...")
            demo_path = os.path.join(os.path.dirname(__file__), "demo", "data", "demo", "season_projection_demo.csv")
            if not os.path.exists(demo_path):
                raise HTTPException(status_code=404, detail="데모 파일(season_projection_demo.csv)이 없습니다.")

            df = pd.read_csv(demo_path)
            df.rename(columns={"AvgRank": "avg_rank", "PlayoffProb": "playoff_prob", "Team": "team"}, inplace=True)
            df["playoff_probability"] = (df["playoff_prob"] * 100).round(1)
            df = df.sort_values(by="avg_rank", ascending=True).reset_index(drop=True)

            return {
                "status": "ok",
                "mode": "season",
                "title": "📊 정규시즌 순위 예측",
                "ranking_projection": df.to_dict(orient="records")
            }

        # -------------------------------------------------
        # 🔥 2. 포스트시즌 (postseason) 모드
        # -------------------------------------------------
        elif SEASON_MODE == "postseason":
            print("🔥 포스트시즌 모드 → 삼성의 단계별 진출 확률 계산")
            
            # --- 데이터 준비: 포스트시즌 진출팀의 최종 스탯 로드 ---
            demo_path = os.path.join(os.path.dirname(__file__), "demo", "data", "demo", "season_projection_demo.csv")
            if not os.path.exists(demo_path):
                raise HTTPException(status_code=404, detail="포스트시즌 팀 데이터 파일이 없습니다.")
            
            all_teams_data = pd.read_csv(demo_path)
            # 컬럼명 통일 (Team -> team)
            all_teams_data.rename(columns={"Team": "team"}, inplace=True, errors='ignore')

            # 정규시즌 순위대로 팀 이름 정렬 (예시: AvgRank 기준)
            sorted_teams = all_teams_data.sort_values(by='AvgRank', ascending=True)
            postseason_teams = sorted_teams['team'].head(5).tolist()

            if "삼성" not in postseason_teams:
                return {
                    "status": "ok", "mode": "postseason",
                    "title": "😢 아쉬운 가을",
                    "message": "삼성 라이온즈는 포스트시즌 진출에 실패했습니다."
                }
            
            samsung_rank_index = postseason_teams.index("삼성")
            
            # --- 단계별 확률 계산 ---
            probabilities = {}
            cumulative_prob = 1.0 

            # 1. 와일드카드 -> 준PO 진출
            if samsung_rank_index >= 2: # 3, 4, 5위
                opponent_map = {2: postseason_teams[4], 3: postseason_teams[4], 4: postseason_teams[3]} # 상대팀 매칭
                if samsung_rank_index in opponent_map:
                    opponent = opponent_map[samsung_rank_index]
                    series_win_prob = _calculate_series_win_prob("삼성", opponent, 3, all_teams_data, model)
                    cumulative_prob *= series_win_prob
                    probabilities["준플레이오프 진출"] = round(cumulative_prob * 100, 1)

            # 2. 준PO -> PO 진출
            if samsung_rank_index >= 1 and cumulative_prob > 0: # 2, 3, 4, 5위
                opponent = postseason_teams[1 if samsung_rank_index == 0 else 2] # 상대는 3위 또는 2위
                if "삼성" != opponent:
                    series_win_prob = _calculate_series_win_prob("삼성", opponent, 5, all_teams_data, model)
                    cumulative_prob *= series_win_prob
                    probabilities["플레이오프 진출"] = round(cumulative_prob * 100, 1)

            # 3. PO -> KS 진출
            if cumulative_prob > 0:
                opponent = postseason_teams[1] # 상대는 2위
                if "삼성" != opponent:
                    series_win_prob = _calculate_series_win_prob("삼성", opponent, 5, all_teams_data, model)
                    cumulative_prob *= series_win_prob
                    probabilities["한국시리즈 진출"] = round(cumulative_prob * 100, 1)

            # 4. KS -> 최종 우승
            if cumulative_prob > 0:
                opponent = postseason_teams[0] # 상대는 1위
                if "삼성" != opponent:
                    series_win_prob = _calculate_series_win_prob("삼성", opponent, 7, all_teams_data, model)
                    cumulative_prob *= series_win_prob
                    probabilities["최종 우승"] = round(cumulative_prob * 100, 1)

            return {
                "status": "ok", "mode": "postseason",
                "title": "🏆 삼성 라이온즈 포스트시즌 여정",
                "samsung_journey_probability": {
                    "start_rank": samsung_rank_index + 1,
                    "probabilities": probabilities
                }
            }

        # -------------------------------------------------
        # 🌙 3. 비시즌 (offseason) 모드
        # -------------------------------------------------
        else: # offseason
            print("🌙 비시즌 모드 → 다음 시즌 순위 예측 표시")
            demo_path = os.path.join(os.path.dirname(__file__), "demo", "data", "demo", "season_projection_demo.csv")
            if not os.path.exists(demo_path):
                raise HTTPException(status_code=404, detail="데모 파일(season_projection_demo.csv)이 없습니다.")

            df = pd.read_csv(demo_path)
            df.rename(columns={"AvgRank": "avg_rank", "PlayoffProb": "playoff_prob", "Team": "team"}, inplace=True)
            df["playoff_probability"] = (df["playoff_prob"] * 100).round(1)
            df = df.sort_values(by="avg_rank", ascending=True).reset_index(drop=True)

            return {
                "status": "ok",
                "mode": "offseason",
                "title": "🌙 다음 시즌 미리보기",
                "ranking_projection": df.to_dict(orient="records")
            }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"시즌 예측 처리 중 오류 발생: {str(e)}")