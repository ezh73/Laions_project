# make_2025_demo_features.py (오직 2025년 데이터만 사용하는 최종 스크립트)
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import math
import numpy as np
from collections import deque

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')

K_FACTOR = 20
ELO_INITIAL = 1500
TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']

def calculate_samsung_features(games_df: pd.DataFrame) -> pd.DataFrame:
    """
    주어진 경기 데이터(2025년)를 기반으로 ELO 점수를 계산하고,
    오직 '삼성' 경기 데이터만 피처로 추출하여 올바르게 저장합니다.
    """
    team_stats = {
        team: {'elo': ELO_INITIAL, 'game_history': deque(maxlen=10),
               'runs_scored': 0, 'runs_allowed': 0}
        for team in TEAMS
    }
    final_features = []

    games_df = games_df.sort_values(by='game_date').reset_index(drop=True)

    print("--- ⚾️ 2025 시즌 시작! 모든 팀의 ELO 점수를 1500에서 계산 시작합니다. ---")

    for _, g in games_df.iterrows():
        home, away = g['home_team'], g['away_team']
        if home not in TEAMS or away not in TEAMS: continue
        
        home_score, away_score = g['home_score'], g['away_score']

        # 피처 계산을 위한 현재 스탯 확보
        home_elo_before = team_stats[home]['elo']
        away_elo_before = team_stats[away]['elo']
        home_form = np.mean(list(team_stats[home]['game_history'])) if team_stats[home]['game_history'] else 0.5
        away_form = np.mean(list(team_stats[away]['game_history'])) if team_stats[away]['game_history'] else 0.5
        
        home_rs, home_ra = team_stats[home]['runs_scored'], team_stats[home]['runs_allowed']
        away_rs, away_ra = team_stats[away]['runs_scored'], team_stats[away]['runs_allowed']
        home_pythagorean = (home_rs**2) / (home_rs**2 + home_ra**2) if (home_rs + home_ra) > 0 else 0.5
        away_pythagorean = (away_rs**2) / (away_rs**2 + away_ra**2) if (away_rs + away_ra) > 0 else 0.5

        # 삼성 경기일 때만 피처를 생성하고 저장
        if home == '삼성' or away == '삼성':
            is_samsung_home = (home == '삼성')
            
            samsung_elo = home_elo_before if is_samsung_home else away_elo_before
            opponent_elo = away_elo_before if is_samsung_home else home_elo_before
            samsung_form_val = home_form if is_samsung_home else away_form
            opponent_form_val = away_form if is_samsung_home else home_form
            samsung_pyth = home_pythagorean if is_samsung_home else away_pythagorean
            opponent_pyth = away_pythagorean if is_samsung_home else home_pythagorean
            
            samsung_win_flag = 1 if (is_samsung_home and home_score > away_score) or \
                                   (not is_samsung_home and away_score > home_score) else 0

            feature_row = {
                'game_id': g['game_id'], 'game_date': g['game_date'],
                'home_team': home, 'away_team': away,
                'samsung_elo': samsung_elo, 'opponent_elo': opponent_elo,
                'rest_diff': 0,
                'samsung_form': samsung_form_val, 'opponent_form': opponent_form_val,
                'samsung_pythagorean': samsung_pyth, 'opponent_pythagorean': opponent_pyth,
                'samsung_win': samsung_win_flag
            }
            final_features.append(feature_row)

        # ELO 및 통계 업데이트 (모든 경기에 대해 수행)
        actual_home_win = 1 if home_score > away_score else (0 if away_score > home_score else 0.5)
        expected_home_win = 1 / (1 + math.pow(10, (away_elo_before - home_elo_before) / 400))
        
        team_stats[home]['elo'] += K_FACTOR * (actual_home_win - expected_home_win)
        team_stats[away]['elo'] -= K_FACTOR * (actual_home_win - expected_home_win)
        
        team_stats[home]['runs_scored'] += home_score
        team_stats[home]['runs_allowed'] += away_score
        team_stats[home]['game_history'].append(actual_home_win)
        
        team_stats[away]['runs_scored'] += away_score
        team_stats[away]['runs_allowed'] += home_score
        team_stats[away]['game_history'].append(1 - actual_home_win)

    return pd.DataFrame(final_features)

def main():
    """DB에서 '2025년' 경기 데이터만 읽어와 demo_features.csv 파일을 생성합니다."""
    print("🚀 2025년 시연용 데모 피처 데이터 생성 시작...")
    
    # ✅ [핵심 수정] 오직 2025년 데이터만 불러오도록 쿼리 변경
    query = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games
        WHERE EXTRACT(YEAR FROM game_date) = 2025
        ORDER BY game_date ASC
    """)
    
    try:
        games_2025_df = pd.read_sql(query, engine)
        if games_2025_df.empty:
            print("⚠️ DB에 2025년 경기 데이터가 없습니다. 스크립트를 종료합니다.")
            return
        print(f"✅ DB에서 {len(games_2025_df)}개의 2025년 경기 데이터를 가져왔습니다.")
    except Exception as e:
        print(f"❌ DB 조회 중 오류 발생: {e}")
        return

    features_df = calculate_samsung_features(games_2025_df)
    print(f"✅ {len(features_df)}개의 삼성 경기 피처를 최종 생성했습니다.")

    # 파일을 backend/demo 폴더에 저장
    output_path = "demo_features.csv"
    
    # 데이터프레임을 지정된 경로에 CSV 파일로 저장합니다.
    features_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"🎉 성공! '{output_path}' 파일이 현재 경로에 생성/업데이트되었습니다.")
    
if __name__ == "__main__":
    main()