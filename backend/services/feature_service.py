# backend/services/feature_service.py
from fastapi import APIRouter, HTTPException, Depends
from datetime import date
import pandas as pd
import numpy as np
from sqlalchemy import text
from collections import deque
import math
import logging
import psycopg2.extras

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from config import engine, TEAMS, CURRENT_DATE
from auth_utils import verify_admin_api_key

router = APIRouter(prefix="/api/features", tags=["features"])

# --- 상수 정의 ---
K_FACTOR = 32
ELO_INITIAL = 1500

class FeatureService:
    @staticmethod
    def _calculate_pythagorean(runs_scored: int, runs_allowed: int) -> float:
        if runs_scored == 0 and runs_allowed == 0:
            return 0.500
        return (runs_scored ** 2) / ((runs_scored ** 2) + (runs_allowed ** 2))

    @staticmethod
    def _update_streak(current_streak: int, is_win: int) -> int:
        if is_win == 1: return current_streak + 1 if current_streak > 0 else 1
        elif is_win == 0: return current_streak - 1 if current_streak < 0 else -1
        else: return 0
    @staticmethod
    def _update_db_schema():
        """새로 추가된 피처 컬럼들을 DB에 반영합니다."""
        conn = engine.raw_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"ALTER TABLE match_features ADD COLUMN IF NOT EXISTS home_recent_rd FLOAT;")
                cursor.execute(f"ALTER TABLE match_features ADD COLUMN IF NOT EXISTS away_recent_rd FLOAT;")
                cursor.execute(f"ALTER TABLE match_features ADD COLUMN IF NOT EXISTS home_matchup_rd FLOAT;")
                cursor.execute(f"ALTER TABLE match_features ADD COLUMN IF NOT EXISTS away_matchup_rd FLOAT;")
                cursor.execute(f"ALTER TABLE match_features ADD COLUMN IF NOT EXISTS season_matchup_count INTEGER;")
                conn.commit()
        finally:
            conn.close()
    @classmethod
    def build_all_features(cls):
        """
        KBO 원천 데이터를 순회하며 모든 피처를 계산하고 DB에 저장합니다.
        """
        # 1. 데이터 로드: 날짜순으로 정렬하여 과거부터 현재까지 시뮬레이션
        query = text(f"""
            SELECT game_id, game_date, home_team, away_team, home_score, away_score, winning_team
            FROM kbo_games
            ORDER BY game_date ASC, game_id ASC
        """)
        with engine.connect() as conn:
            df_games = pd.read_sql(query, conn)

        if df_games.empty: return 0

        # 2. 상태 추적용 변수 초기화
        last_year = None
        
        # [전역 상태] 팀별 ELO, 최근 기록, 스트릭 등
        team_stats = {
            team: {
                'elo': ELO_INITIAL,
                'game_history': deque(maxlen=10), # Form 계산용 (최근 10경기)
                'recent_runs': deque(maxlen=5),   # Recent RD 계산용 (최근 5경기)
                'runs_scored': 0, 'runs_allowed': 0,
                'current_streak': 0,
                'last_game_date': None
            } for team in TEAMS
        }

        # [상대 전적 상태] 팀간 상대 득실 (시즌마다 리셋됨)
        matchup_stats = {
            team: {opp: {'scored': 0, 'allowed': 0, 'count': 0} 
                   for opp in TEAMS if opp != team}
            for team in TEAMS
        }

        # DB 스키마 업데이트
        cls._update_db_schema()

        final_features = []

        # 3. 경기 데이터 루프 (Replay)
        for i, (_, row) in enumerate(df_games.iterrows()):
            gdate = row['game_date']
            curr_year = gdate.year
            gid, home, away = row['game_id'], row['home_team'], row['away_team']
            h_score, a_score = row['home_score'], row['away_score']
            winner = row['winning_team']

            if home not in team_stats or away not in team_stats: continue

            # --- (A) 시즌 리셋 로직 ---
            if last_year is not None and curr_year != last_year:
                logger.info(f"🔄 {curr_year} 시즌 개막: 상대 전적 데이터를 리셋합니다.")
                for t in TEAMS:
                    for o in matchup_stats[t]:
                        matchup_stats[t][o] = {'scored': 0, 'allowed': 0, 'count': 0}
            last_year = curr_year

            home_stat, away_stat = team_stats[home], team_stats[away]

            # --- (B) 경기 시작 전 피처 계산 (AI가 보는 데이터) ---
            
            # 1. 상대 득실차 & 경기수 (시즌 리셋 반영됨)
            h_vs_a = matchup_stats[home][away]
            a_vs_h = matchup_stats[away][home]
            h_matchup_rd = (h_vs_a['scored'] - h_vs_a['allowed']) / h_vs_a['count'] if h_vs_a['count'] > 0 else 0.0
            a_matchup_rd = (a_vs_h['scored'] - a_vs_h['allowed']) / a_vs_h['count'] if a_vs_h['count'] > 0 else 0.0

            # 2. 최근 5경기 득실차 (Recent RD)
            h_recent_rd = sum(r['diff'] for r in home_stat['recent_runs']) / len(home_stat['recent_runs']) if home_stat['recent_runs'] else 0.0
            a_recent_rd = sum(r['diff'] for r in away_stat['recent_runs']) / len(away_stat['recent_runs']) if away_stat['recent_runs'] else 0.0

            # 3. 휴식일 계산
            h_rest = (gdate - home_stat['last_game_date']).days if home_stat['last_game_date'] else 3
            a_rest = (gdate - away_stat['last_game_date']).days if away_stat['last_game_date'] else 3

            feature_row = {
                'game_id': gid, 'game_date': gdate, 'home_team': home, 'away_team': away,
                'home_elo': home_stat['elo'], 'away_elo': away_stat['elo'],
                'home_form': round(sum(home_stat['game_history'])/len(home_stat['game_history']), 3) if home_stat['game_history'] else 0.5,
                'away_form': round(sum(away_stat['game_history'])/len(away_stat['game_history']), 3) if away_stat['game_history'] else 0.5,
                'home_streak': home_stat['current_streak'], 'away_streak': away_stat['current_streak'],
                'home_recent_rd': round(h_recent_rd, 3), 'away_recent_rd': round(a_recent_rd, 3),
                'home_matchup_rd': round(h_matchup_rd, 3), 'away_matchup_rd': round(a_matchup_rd, 3),
                'season_matchup_count': h_vs_a['count'],
                'rest_diff': min(max(h_rest - a_rest, -7), 7),
                'home_pythagorean': round(cls._calculate_pythagorean(home_stat['runs_scored'], home_stat['runs_allowed']), 3),
                'away_pythagorean': round(cls._calculate_pythagorean(away_stat['runs_scored'], away_stat['runs_allowed']), 3)
            }
            final_features.append(feature_row)

            # --- (C) 경기 결과 업데이트 (State Update) ---
            
            # 1. ELO 업데이트 (MOV 가중치 적용)
            score_diff = abs(h_score - a_score)
            mov_multiplier = math.log(score_diff + 1) * (2.2 / ((home_stat['elo'] - away_stat['elo']) * 0.001 + 2.2))
            
            expected_home = 1 / (1 + 10 ** ((away_stat['elo'] - home_stat['elo']) / 400))
            h_win_val = 1 if winner == home else (0.5 if winner == '무승부' else 0)
            
            elo_change = K_FACTOR * (h_win_val - expected_home) * mov_multiplier
            home_stat['elo'] += elo_change
            away_stat['elo'] -= elo_change

            # 2. 전역 지표 업데이트
            home_stat['recent_runs'].append({'diff': h_score - a_score})
            away_stat['recent_runs'].append({'diff': a_score - h_score})
            home_stat['game_history'].append(1 if h_win_val == 1 else 0)
            home_stat['current_streak'] = cls._update_streak(home_stat['current_streak'], 1 if winner == home else (0 if winner == away else -1))
            home_stat['last_game_date'] = gdate
            home_stat['runs_scored'] += h_score
            home_stat['runs_allowed'] += a_score

            # 3. 상대 전적 업데이트
            matchup_stats[home][away]['scored'] += h_score
            matchup_stats[home][away]['allowed'] += a_score
            matchup_stats[home][away]['count'] += 1
            matchup_stats[away][home]['scored'] += a_score
            matchup_stats[away][home]['allowed'] += h_score
            matchup_stats[away][home]['count'] += 1

        # 4. DB 저장 (DELETE FROM 사용: CASCADE 없이 안전하게 전체 삭제 후 재삽입)
        columns = list(final_features[0].keys())
        query = f"INSERT INTO match_features ({', '.join(columns)}) VALUES %s"
        values = [tuple(row[col] for col in columns) for row in final_features]

        conn = engine.raw_connection()
        try:
            with conn.cursor() as cursor:
                # TRUNCATE CASCADE 대신 DELETE 사용 (외래키 CASCADE 삭제 방지)
                cursor.execute(f"DELETE FROM match_features")
                psycopg2.extras.execute_values(cursor, query, values)
                conn.commit()
        finally:
            conn.close()
        
        return len(final_features)

# --- API Endpoints ---

@router.post("/rebuild")
def api_rebuild_features(admin_key: str = Depends(verify_admin_api_key)):
    """관리자용: 원천 데이터를 바탕으로 전체 구단의 피처를 재계산합니다."""
    try:
        count = FeatureService.build_all_features()
        return {"status": "ok", "message": f"{count}개의 경기 피처가 생성 및 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
