# backend/ranking_service.py
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy import create_engine, text
from auth_utils import verify_admin_api_key
import pandas as pd
import numpy as np
import os
import math
import random
import traceback

# config.py에서 핵심 설정값들을 가져옵니다.
from config import SEASON_MODE, ADMIN_MODE, CURRENT_YEAR, engine
from main import db_fs

# feature_service에서 ELO 계산 함수를 재사용하기 위해 가져옵니다.
from feature_service import calculate_elo_and_features

# .env 파일에서 관리자용 순위 생성 방식을 읽어옵니다.
ADMIN_POSTSEASON_RANKING_SOURCE = os.getenv("ADMIN_POSTSEASON_RANKING_SOURCE", "elo")

# --- FastAPI 라우터 및 Firestore 설정 ---
router = APIRouter()
if db_fs:
    from firebase_admin import firestore

# --- 헬퍼 함수 정의 ---

def _calculate_series_win_prob(team1_elo, team2_elo, num_games):
    """두 팀 간의 다전제 승리 확률을 몬테카를로 시뮬레이션으로 계산합니다."""
    team1_single_game_win_prob = 1 / (1 + math.pow(10, (team2_elo - team1_elo) / 400))
    
    simulations = 5000
    team1_series_wins = 0
    win_threshold = math.ceil(num_games / 2)

    for _ in range(simulations):
        team1_wins_in_series = 0
        team2_wins_in_series = 0
        for _ in range(num_games):
            if random.random() < team1_single_game_win_prob:
                team1_wins_in_series += 1
            else:
                team2_wins_in_series += 1
            
            if team1_wins_in_series >= win_threshold:
                team1_series_wins += 1
                break
            if team2_wins_in_series >= win_threshold:
                break
    
    return team1_series_wins / simulations


def _get_final_team_stats_from_db(year: int) -> pd.DataFrame:
    """
    [실서비스용] DB의 전체 경기 기록을 바탕으로, 시즌 종료 시점의
    모든 팀별 '실제 순위'와 상세 스탯(ELO 등)을 계산합니다.
    """
    print(f"🚀 [실서비스 모드] DB에서 {year}년 전체 경기 기록을 기반으로 최종 팀 스탯을 계산합니다.")
    
    query_all_games = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games
        WHERE EXTRACT(YEAR FROM game_date) = :year
        ORDER BY game_date ASC;
    """)
    with engine.connect() as conn:
        all_games_df = pd.read_sql(query_all_games, conn, params={"year": year})

    if all_games_df.empty:
        raise HTTPException(status_code=404, detail=f"{year}년 경기 데이터가 DB에 없습니다.")

    _, final_elos_dict = calculate_elo_and_features(all_games_df.copy())
    
    all_games_df['winner'] = np.where(all_games_df['home_score'] > all_games_df['away_score'], all_games_df['home_team'], all_games_df['away_team'])
    all_games_df.loc[all_games_df['home_score'] == all_games_df['away_score'], 'winner'] = None

    wins = all_games_df['winner'].value_counts().reset_index()
    wins.columns = ['team', 'wins']
    
    final_stats_df = pd.DataFrame(list(final_elos_dict.items()), columns=['team', 'elo'])
    final_stats_df = pd.merge(final_stats_df, wins, on='team', how='left').fillna(0)
    final_stats_df = final_stats_df.sort_values(by='wins', ascending=False).reset_index(drop=True)
    final_stats_df['rank'] = range(1, len(final_stats_df) + 1)
    
    final_stats_df['predicted_win'] = 0.5 
    return final_stats_df


def _get_final_elo_rankings_from_db(year: int) -> pd.DataFrame:
    """
    [관리자 모드용] DB의 전체 경기 기록을 바탕으로 시즌 종료 시점의
    '최종 ELO'를 계산하고, 이를 기반으로 순위를 생성합니다.
    """
    print(f"🧪 [관리자 모드] DB에서 {year}년 전체 경기 기록을 기반으로 최종 ELO 랭킹을 생성합니다.")
    
    query_all_games = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games
        WHERE EXTRACT(YEAR FROM game_date) = :year
        ORDER BY game_date ASC;
    """)
    with engine.connect() as conn:
        all_games_df = pd.read_sql(query_all_games, conn, params={"year": year})

    if all_games_df.empty:
        raise HTTPException(status_code=404, detail=f"{year}년 경기 데이터가 DB에 없습니다.")

    _, final_elos_dict = calculate_elo_and_features(all_games_df.copy())
    
    elo_rankings_df = pd.DataFrame(list(final_elos_dict.items()), columns=['team', 'elo'])
    elo_rankings_df = elo_rankings_df.sort_values(by='elo', ascending=False).reset_index(drop=True)
    elo_rankings_df['rank'] = range(1, len(elo_rankings_df) + 1)
    
    elo_rankings_df['predicted_win'] = 0.5 
    return elo_rankings_df

# --- API 엔드포인트 정의 ---

@router.get("/ranking/season-projection")
def api_get_season_projection():
    """
    시스템의 SEASON_MODE에 따라 적절한 예측 결과를 반환합니다.
    """
    try:
        # 1. 정규시즌 (season) 모드
        if SEASON_MODE == "season":
            return {
                "status": "info",
                "mode": "season",
                "message": "정규시즌 중에는 이 API 대신 '/api/predict/today'를 통해 오늘의 경기 예측을 확인하세요."
            }

        # 2. 포스트시즌 (postseason) 모드
        elif SEASON_MODE == "postseason":
            print("🔥 포스트시즌 모드 → 삼성의 단계별 진출 확률 계산")
            
            all_teams_data = None
            
            if ADMIN_MODE:
                if ADMIN_POSTSEASON_RANKING_SOURCE == "manual":
                    print("🧪 [관리자 모드] 수동 순위 파일(manual_rankings.csv)을 로드합니다.")
                    manual_path = os.path.join(os.path.dirname(__file__), "demo", "manual_rankings.csv")
                    if not os.path.exists(manual_path):
                        raise HTTPException(status_code=404, detail="수동 순위 파일(manual_rankings.csv)이 없습니다.")
                    all_teams_data = pd.read_csv(manual_path)
                    all_teams_data['elo'] = 1500
                    all_teams_data['predicted_win'] = 0.5
                else: 
                    print("🧪 [관리자 모드] DB에서 'ELO 기반 순위'를 생성합니다.")
                    all_teams_data = _get_final_elo_rankings_from_db(CURRENT_YEAR)
            else:
                print("🚀 [실서비스 모드] DB에서 '실제 승-패 기반 순위'를 가져옵니다.")
                all_teams_data = _get_final_team_stats_from_db(CURRENT_YEAR)

            sorted_teams = all_teams_data.sort_values(by='rank', ascending=True)
            postseason_teams = sorted_teams['team'].head(5).tolist()

            if "삼성" not in postseason_teams:
                return {
                    "status": "ok", "mode": "postseason",
                    "title": "😢 아쉬운 가을", "message": "삼성 라이온즈는 포스트시즌 진출에 실패했습니다."
                }

            samsung_stats = all_teams_data[all_teams_data['team'] == '삼성'].iloc[0]
            samsung_rank = int(samsung_stats['rank'])
            samsung_elo = samsung_stats['elo']

            probabilities = {}
            cumulative_prob = 1.0

            series_info = { 5: ('4위팀', 3), 4: ('3위팀', 3), 3: ('2위팀', 5), 2: ('1위팀', 7) }
            next_stage_names = { 5: '와일드카드 통과', 4: '준플레이오프 진출', 3: '플레이오프 진출', 2: '한국시리즈 우승' }
            
            current_rank = samsung_rank
            while current_rank > 1:
                opponent_rank = 5 if current_rank == 4 else (4 if current_rank == 5 else current_rank - 1)
                opponent_stats = all_teams_data[all_teams_data['rank'] == opponent_rank].iloc[0]
                opponent_elo = opponent_stats['elo']
                num_games = series_info[current_rank][1]
                
                win_prob = _calculate_series_win_prob(samsung_elo, opponent_elo, num_games)
                cumulative_prob *= win_prob
                
                stage_name = next_stage_names[current_rank]
                probabilities[stage_name] = round(cumulative_prob * 100, 2)
                
                if current_rank <= 2: break
                current_rank -= 1

            return {
                "status": "ok", "mode": "postseason",
                "title": f"🏆 {CURRENT_YEAR} 삼성 포스트시즌 여정 예측",
                "samsung_final_rank": samsung_rank,
                "samsung_journey_probability": { "start_elo": round(samsung_elo), "probabilities": probabilities }
            }

        # 3. 비시즌 (offseason) 모드
        else:
            print("🌙 비시즌 모드 → 다음 시즌 순위 예측 표시 (CSV 기반)")
            demo_path = os.path.join(os.path.dirname(__file__), "demo", "season_projection_demo.csv")
            if not os.path.exists(demo_path):
                raise HTTPException(status_code=404, detail="데모 파일(season_projection_demo.csv)이 없습니다.")

            df = pd.read_csv(demo_path)
            
            result_df = df.rename(columns={ "Team": "team", "AvgRank": "avg_rank", "predicted_wins": "avg_wins", "predicted_losses": "avg_losses" })
            result_df = result_df[["team", "avg_rank", "avg_wins", "avg_losses"]].copy()
            result_df = result_df.sort_values(by="avg_rank", ascending=True).reset_index(drop=True)

            return {
                "status": "ok", "mode": "offseason",
                "title": "🌙 다음 시즌 미리보기",
                "ranking_projection": result_df.to_dict(orient="records")
            }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"시즌 예측 처리 중 오류 발생: {str(e)}")


@router.post("/ranking/settle-latest-game")
def api_settle_latest_game(admin_key: str = Depends(verify_admin_api_key)):
    """가장 최근 경기 결과를 기준으로 사용자들의 예측을 정산하고 점수를 부여합니다."""
    if not db_fs:
        raise HTTPException(status_code=503, detail="Firestore 클라이언트를 사용할 수 없습니다.")

    # 1. DB에서 가장 최근에 끝난 삼성 경기의 실제 결과를 가져옵니다.
    query_latest_result = text("""
        SELECT game_id, samsung_win FROM game_results
        WHERE samsung_win IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 1;
    """)
    with engine.connect() as conn:
        latest_game = conn.execute(query_latest_result).fetchone()

    if not latest_game:
        raise HTTPException(status_code=404, detail="정산할 최근 경기 결과가 없습니다.")
    
    game_id, actual_samsung_win = latest_game

    # 2. DB에서 해당 경기에 대한 AI의 예측을 가져옵니다.
    query_ai_pred = text("SELECT predicted_win FROM ai_predictions WHERE game_id = :game_id")
    with engine.connect() as conn:
        ai_prediction = conn.execute(query_ai_pred, {"game_id": game_id}).scalar_one_or_none()

    # 3. Firestore에서 모든 사용자의 데이터를 가져옵니다.
    users_ref = db_fs.collection("users")
    docs = users_ref.stream()

    updated_users = []
    for doc in docs:
        user_data = doc.to_dict()
        user_id = doc.id
        user_prediction = user_data.get("last_prediction")
        display_name = user_data.get("displayName", "Unknown")

        if user_prediction is not None and user_prediction == actual_samsung_win:
            base_points = 20
            bonus_points = 10 if ai_prediction is not None and user_prediction != ai_prediction else 0
            
            # main.py의 함수를 직접 호출하는 대신, 여기서 바로 Firestore 업데이트 로직 실행
            total = base_points + bonus_points
            user_ref = db_fs.collection("users").document(user_id)
            user_ref.set({
                "ai_score": firestore.Increment(total),
                "total_score": firestore.Increment(total),
                "weekly_score": firestore.Increment(total),
                "updated_at": datetime.utcnow()
            }, merge=True)
            
            updated_users.append({ "user_id": user_id, "points_gained": total })

    return {
        "status": "ok",
        "settled_game_id": game_id,
        "actual_samsung_win": actual_samsung_win,
        "updated_users_count": len(updated_users),
        "updated_users": updated_users
    }