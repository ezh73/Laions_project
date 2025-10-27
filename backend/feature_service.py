# backend/feature_service.py
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from auth_utils import verify_admin_api_key
from collections import deque
import os
from dotenv import load_dotenv
import math
from config import ADMIN_MODE, ADMIN_DATE, CURRENT_DATE  # ✅ 관리자모드 설정 불러오기

router = APIRouter()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')

# ELO/Form 계산 상수
K_FACTOR = 20
ELO_INITIAL = 1500
TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']


# =============================================================
# 1️⃣ ELO/Form/Pythagorean 계산 로직 (시즌 연속성 포함)
# =============================================================
def calculate_elo_and_features(all_games_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    team_stats = {
        team: {'elo': ELO_INITIAL, 'game_history': deque(maxlen=10),
               'runs_scored': 0, 'runs_allowed': 0}
        for team in TEAMS
    }

    final_features = []
    latest_game_year = None

    all_games_df = all_games_df.sort_values(by='game_date').reset_index(drop=True)
    all_games_df['result'] = 0.5
    all_games_df.loc[all_games_df['home_score'] > all_games_df['away_score'], 'result'] = 1
    all_games_df.loc[all_games_df['away_score'] > all_games_df['home_score'], 'result'] = 0

    for _, g in all_games_df.iterrows():
        current_year = g['game_date'].year

        # 🚨 시즌 경계 시 Form/Pythagorean 초기화, ELO 유지
        if latest_game_year is not None and current_year != latest_game_year:
            print(f"--- 🚨 {current_year} 시즌 시작! ELO 연속성 유지 ---")
            for team in TEAMS:
                team_stats[team]['runs_scored'] = 0
                team_stats[team]['runs_allowed'] = 0
                team_stats[team]['game_history'] = deque(maxlen=10)
        latest_game_year = current_year

        home, away = g['home_team'], g['away_team']
        home_score, away_score = g['home_score'], g['away_score']
        result = g['result']

        if home not in TEAMS or away not in TEAMS:
            continue

        home_elo_before = team_stats[home]['elo']
        away_elo_before = team_stats[away]['elo']

        # Form 계산
        home_form = np.mean(team_stats[home]['game_history']) if team_stats[home]['game_history'] else 0.5
        away_form = np.mean(team_stats[away]['game_history']) if team_stats[away]['game_history'] else 0.5

        # Pythagorean 계산
        home_RS, home_RA = team_stats[home]['runs_scored'], team_stats[home]['runs_allowed']
        away_RS, away_RA = team_stats[away]['runs_scored'], team_stats[away]['runs_allowed']

        home_pythagorean = (home_RS**2) / (home_RS**2 + home_RA**2) if home_RS + home_RA > 0 else 0.5
        away_pythagorean = (away_RS**2) / (away_RS**2 + away_RA**2) if away_RS + away_RA > 0 else 0.5

        rest_diff = 0

        # 삼성 관련 경기만 저장
        if home == '삼성' or away == '삼성':
            is_home = home == '삼성'
            feature_row = {
                'game_id': g['game_id'],
                'game_date': g['game_date'],
                'samsung_elo': home_elo_before if is_home else away_elo_before,
                'opponent_elo': away_elo_before if is_home else home_elo_before,
                'rest_diff': rest_diff,
                'samsung_form': home_form if is_home else away_form,
                'opponent_form': away_form if is_home else home_form,
                'samsung_pythagorean': home_pythagorean if is_home else away_pythagorean,
                'opponent_pythagorean': away_pythagorean if is_home else home_pythagorean,
                'samsung_win': 1 if (home_score > away_score and is_home)
                                or (away_score > home_score and not is_home) else 0
            }
            final_features.append(feature_row)

        # ELO 업데이트
        expected_home_win = 1 / (1 + math.pow(10, (away_elo_before - home_elo_before) / 400))
        actual_home_win = 1 if home_score > away_score else 0

        home_elo_after = home_elo_before + K_FACTOR * (actual_home_win - expected_home_win)
        away_elo_after = away_elo_before + K_FACTOR * ((1 - actual_home_win) - (1 - expected_home_win))

        # 통계 업데이트
        team_stats[home]['elo'] = home_elo_after
        team_stats[away]['elo'] = away_elo_after
        team_stats[home]['runs_scored'] += home_score
        team_stats[home]['runs_allowed'] += away_score
        team_stats[away]['runs_scored'] += away_score
        team_stats[away]['runs_allowed'] += home_score
        team_stats[home]['game_history'].append(actual_home_win)
        team_stats[away]['game_history'].append(1 - actual_home_win)

    final_elos = {team: stats['elo'] for team, stats in team_stats.items()}
    return pd.DataFrame(final_features), final_elos


# =============================================================
# 2️⃣ 피처 생성 함수 (관리자모드 적용)
# =============================================================
def build_features() -> pd.DataFrame:
    """
    전체 kbo_cleaned_games 기준으로 ELO/Form/Pythagorean 피처를 생성하고 DB에 반영.
    ADMIN_MODE=True일 경우 demo_features.csv를 사용합니다.
    """
    if ADMIN_MODE:
        print("🧪 [관리자모드] demo_features.csv 로드 중...")
        demo_path = "data/demo/demo_features.csv"
        if not os.path.exists(demo_path):
            raise HTTPException(status_code=404, detail="demo_features.csv 파일이 없습니다.")
        df_demo = pd.read_csv(demo_path)
        print(f"✅ Demo 피처 {len(df_demo)}건 로드 완료 ({ADMIN_DATE} 기준)")
        return df_demo

    query = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games
        ORDER BY game_date ASC;
    """)
    all_games_df = pd.read_sql(query, engine)
    if all_games_df.empty:
        raise HTTPException(status_code=404, detail="DB에 kbo_cleaned_games 데이터가 없습니다.")

    feat_df, _ = calculate_elo_and_features(all_games_df)
    feat_df = feat_df.fillna(np.nan).replace([np.inf, -np.inf], np.nan)

    with engine.begin() as conn:
        for _, row in feat_df.iterrows():
            q = text("""
                INSERT INTO match_features (
                    game_id, game_date, samsung_elo, opponent_elo, rest_diff,
                    samsung_form, opponent_form, samsung_pythagorean, opponent_pythagorean,
                    samsung_win, created_at
                ) VALUES (
                    :game_id, :game_date, :samsung_elo, :opponent_elo, :rest_diff,
                    :samsung_form, :opponent_form, :samsung_pythagorean, :opponent_pythagorean,
                    :samsung_win, NOW()
                )
                ON CONFLICT (game_id)
                DO UPDATE SET
                    samsung_elo = EXCLUDED.samsung_elo,
                    opponent_elo = EXCLUDED.opponent_elo,
                    rest_diff = EXCLUDED.rest_diff,
                    samsung_form = EXCLUDED.samsung_form,
                    opponent_form = EXCLUDED.opponent_form,
                    samsung_pythagorean = EXCLUDED.samsung_pythagorean,
                    opponent_pythagorean = EXCLUDED.opponent_pythagorean,
                    samsung_win = EXCLUDED.samsung_win,
                    created_at = NOW();
            """)
            conn.execute(q, row.to_dict())

    print(f"✅ 실제 모드 피처 {len(feat_df)}건 DB 반영 완료")
    return feat_df


# =============================================================
# 3️⃣ FastAPI 엔드포인트
# =============================================================

@router.get("/features/latest")
def api_latest_features(limit: int = 5):
    """match_features 최신 레코드 조회 (관리자모드면 demo 반환)"""
    if ADMIN_MODE:
        demo_path = "data/demo/demo_features.csv"
        if not os.path.exists(demo_path):
            raise HTTPException(status_code=404, detail="demo_features.csv 파일이 없습니다.")
        df_demo = pd.read_csv(demo_path).head(limit)
        return {
            "status": "ok (admin)",
            "data_retrieved_at": str(ADMIN_DATE),
            "features": df_demo.to_dict(orient="records")
        }

    q = text("SELECT * FROM match_features ORDER BY game_date DESC LIMIT :limit")
    df = pd.read_sql(q, engine, params={"limit": limit})
    return df.to_dict(orient="records")


@router.post("/admin/features/rebuild")
def api_rebuild_features(admin_key: str = Depends(verify_admin_api_key)):
    """관리자: 피처 재생성"""
    try:
        df = build_features()
        return {"status": "ok", "rows": len(df), "mode": "admin" if ADMIN_MODE else "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================
# 4️⃣ 호환용 헬퍼 함수 (기존 model_service 호환용)
# =============================================================
def get_latest_stats_for_team(team_name: str):
    """
    기존 model_service.py에서 호출하던 호환용 함수입니다.
    - 관리자모드면 demo_features.csv의 최신 데이터를 반환
    - 일반모드면 match_features 테이블에서 최신 데이터를 반환
    """
    if ADMIN_MODE:
        demo_path = "data/demo/demo_features.csv"
        if not os.path.exists(demo_path):
            raise HTTPException(status_code=404, detail="demo_features.csv 파일이 없습니다.")
        df_demo = pd.read_csv(demo_path)
        df_demo = df_demo.sort_values(by="game_date", ascending=False)
        latest = df_demo[df_demo["game_date"] == df_demo["game_date"].max()]
        return latest.to_dict(orient="records")

    q = text("""
        SELECT *
        FROM match_features
        WHERE game_date = (SELECT MAX(game_date) FROM match_features)
    """)
    df = pd.read_sql(q, engine)
    return df.to_dict(orient="records")