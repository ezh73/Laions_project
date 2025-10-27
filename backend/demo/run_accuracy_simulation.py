# backend/demo/run_accuracy_simulation.py (최종 코드)
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import math
import numpy as np
from collections import deque
import joblib
from datetime import datetime

# --- 1. 환경 설정 및 초기화 ---

# ✅ [핵심 1] 스크립트가 demo 폴더에 있으므로, 상위 폴더(../)의 .env를 찾아 로드합니다.
load_dotenv(dotenv_path=os.path.join("..", ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')

ADMIN_DATE_STR = os.getenv("ADMIN_DATE", datetime.now().strftime('%Y-%m-%d'))
try:
    TARGET_DATE = datetime.strptime(ADMIN_DATE_STR, "%Y-%m-%d").date()
except ValueError:
    raise ValueError("ADMIN_DATE 형식이 잘못되었습니다. 'YYYY-MM-DD' 형식으로 입력해주세요.")

# ✅ [핵심 2] 모델 파일이 현재 폴더(demo)에 있으므로, 경로 없이 파일 이름만 적습니다.
MODEL_PATH = "lgbm_kbo_predictor_tuned.pkl"

K_FACTOR = 20
ELO_INITIAL = 1500
TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']

# --- 2. 피처 생성 함수 (이전과 동일) ---
def calculate_samsung_features(games_df: pd.DataFrame) -> pd.DataFrame:
    """
    주어진 경기 데이터를 기반으로 ELO 점수를 순차적으로 계산하고,
    '삼성' 경기에 대한 피처만 추출하여 반환합니다.
    """
    team_stats = {
        team: {'elo': ELO_INITIAL, 'game_history': deque(maxlen=10),
               'runs_scored': 0, 'runs_allowed': 0}
        for team in TEAMS
    }
    final_features = []
    
    print("--- ⚾️ 2025 시즌 시뮬레이션 시작! (모든 팀 ELO 1500에서 시작) ---")

    for _, g in games_df.iterrows():
        home, away = g['home_team'], g['away_team']
        if home not in TEAMS or away not in TEAMS: continue
        
        home_score, away_score = g['home_score'], g['away_score']

        home_elo_before = team_stats[home]['elo']
        away_elo_before = team_stats[away]['elo']
        home_form = np.mean(list(team_stats[home]['game_history'])) if team_stats[home]['game_history'] else 0.5
        away_form = np.mean(list(team_stats[away]['game_history'])) if team_stats[away]['game_history'] else 0.5
        
        home_rs, home_ra = team_stats[home]['runs_scored'], team_stats[home]['runs_allowed']
        away_rs, away_ra = team_stats[away]['runs_scored'], team_stats[away]['runs_allowed']
        home_pythagorean = (home_rs**2) / (home_rs**2 + home_ra**2) if (home_rs + home_ra) > 0 else 0.5
        away_pythagorean = (away_rs**2) / (away_rs**2 + away_ra**2) if (away_rs + away_ra) > 0 else 0.5

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

# --- 3. 메인 실행 함수 ---
def main():
    """
    지정된 날짜까지의 2025년 시즌 삼성 경기 예측 정확도를 시뮬레이션합니다.
    """
    print(f"🚀 {TARGET_DATE}까지의 2025 시즌 예측 정확도 시뮬레이션을 시작합니다.")
    
    query = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games
        WHERE EXTRACT(YEAR FROM game_date) = 2025 AND game_date <= :target_date
        ORDER BY game_date ASC
    """)
    try:
        games_df = pd.read_sql(query, engine, params={"target_date": TARGET_DATE})
        if games_df.empty:
            print(f"⚠️ DB에 {TARGET_DATE}까지의 2025년 경기 데이터가 없습니다.")
            return
        print(f"✅ DB에서 {len(games_df)}개의 경기 데이터를 가져왔습니다.")
    except Exception as e:
        print(f"❌ DB 조회 중 오류 발생: {e}")
        return

    features_df = calculate_samsung_features(games_df)
    if features_df.empty:
        print("⚠️ 해당 기간에 삼성 경기가 없어 분석을 종료합니다.")
        return
    print(f"✅ {len(features_df)}개의 삼성 경기 피처를 생성했습니다.")

    try:
        model = joblib.load(MODEL_PATH)
        print(f"✅ AI 모델({MODEL_PATH})을 성공적으로 로드했습니다.")
    except FileNotFoundError:
        print(f"❌ AI 모델 파일({MODEL_PATH})을 찾을 수 없습니다.")
        return

    feature_columns = [
        'samsung_elo', 'opponent_elo', 'rest_diff',
        'samsung_form', 'opponent_form',
        'samsung_pythagorean', 'opponent_pythagorean'
    ]
    X = features_df[feature_columns]
    predictions = model.predict(X)
    print("✅ AI 예측을 완료했습니다.")

    results_df = features_df[['game_id', 'game_date', 'home_team', 'away_team', 'samsung_win']].copy()
    results_df['predicted_win'] = predictions
    results_df['is_correct'] = (results_df['samsung_win'] == results_df['predicted_win'])
    
    total_games = len(results_df)
    correct_predictions = results_df['is_correct'].sum()
    accuracy = (correct_predictions / total_games) * 100 if total_games > 0 else 0

    output_filename = f"2025_prediction_report_until_{TARGET_DATE}.csv"
    results_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print("\n--- 📊 최종 시뮬레이션 결과 📊 ---")
    print(f"  - 분석 기간: 2025년 시즌 시작 ~ {TARGET_DATE}")
    print(f"  - 총 삼성 경기 수: {total_games} 경기")
    print(f"  - AI 예측 성공: {correct_predictions} 경기")
    print(f"  - 누적 예측 정확도: {accuracy:.2f}%")
    print(f"🎉 상세 결과는 '{output_filename}' 파일에 저장되었습니다.")

if __name__ == "__main__":
    main()