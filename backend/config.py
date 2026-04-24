# backend/config.py
import os
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. 환경 변수 로드
load_dotenv()

# 2. 관리자 및 테스트 설정
ADMIN_MODE = os.getenv("ADMIN_MODE", "false").lower() in ["true", "1", "yes"]
ADMIN_DATE_STR = os.getenv("ADMIN_DATE") # 시연용 특정 날짜 (YYYY-MM-DD)

# 3. DB 연결 설정 (관리자 모드에 따른 분기)
if ADMIN_MODE:
    DATABASE_URL = os.getenv("ADMIN_DATABASE_URL")
    print("🧪 [Config] 관리자 모드: ADMIN_DATABASE_URL 연결")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")
    print("🚀 [Config] 실서비스 모드: DATABASE_URL 연결")

# 🚀 [추가] 모드별 동적 테이블명 설정
TABLE_KBO_GAMES = "kbo_games_admin" if ADMIN_MODE else "kbo_games"
TABLE_MATCH_FEATURES = "match_features_admin" if ADMIN_MODE else "match_features"
TABLE_AI_PREDICTIONS = "ai_predictions_admin" if ADMIN_MODE else "ai_predictions"
TABLE_KBO_SCHEDULE = "kbo_schedule_admin" if ADMIN_MODE else "kbo_schedule"

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 설정되어 있지 않습니다. .env 파일을 확인하세요.")

engine = create_engine(DATABASE_URL, client_encoding='utf8')

# 4. 시간 맥락 설정
def get_current_context_date():
    if ADMIN_MODE and ADMIN_DATE_STR:
        try:
            return datetime.strptime(ADMIN_DATE_STR, "%Y-%m-%d").date()
        except ValueError:
            return date.today()
    return date.today()

CURRENT_DATE = get_current_context_date()

# 5. KBO 도메인 상수 (전 구단 확장)
TEAMS = ['삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC']

# AI 모델 피처 정의
FEATURE_CONFIG = {
    "categorical": ["home_team", "away_team"], # 팀명 유지 시
    "numerical": [
        "home_elo", "away_elo", 
        "home_form", "away_form", 
        "home_streak", "away_streak",
        "home_pythagorean", "away_pythagorean",
        "home_recent_rd", "away_recent_rd",
        "rest_diff",
        # 🚀 추가된 피처들
        "home_matchup_rd",  # 
        "away_matchup_rd", 
        "season_matchup_count"
    ],
    "target": "home_team_win"
}
# 6. 데이터 기반 시즌 모드 결정 로직
def get_season_mode():
    """
    DB의 경기 데이터를 조회하여 현재 시즌의 상태를 판별합니다.
    """
    try:
        with engine.connect() as conn:
            # 1) 정규시즌 종료 여부 확인 (정규시즌 경기 720개 완료 여부)
            # sr_id=0은 정규시즌을 의미 (KBO 기준)
            res = conn.execute(text(f"""
                SELECT COUNT(*) FROM {TABLE_KBO_GAMES} 
                WHERE is_postseason = FALSE 
                AND EXTRACT(YEAR FROM game_date) = :year
                AND game_date <= :today
            """), {"year": CURRENT_DATE.year, "today": CURRENT_DATE}).scalar()
            
            print(f"DEBUG: {CURRENT_DATE.year}년 {CURRENT_DATE} 기준 정규시즌 경기 수: {res}")
            
            if res < 720:
                return "season"

            # 2) 포스트시즌 종료 여부 확인 (한국시리즈 우승팀 탄생 여부)
            # 포스트시즌 경기 중 어떤 팀이든 4승을 거뒀는지 확인
            # (실제로는 시리즈별 승수를 체크해야 하나, 시연용으로 한국시리즈 7차전 기간 등을 고려)
            ks_res = conn.execute(text(f"""
                SELECT winning_team, COUNT(*) as wins 
                FROM {TABLE_KBO_GAMES} 
                WHERE is_postseason = TRUE 
                AND EXTRACT(YEAR FROM game_date) = :year
                GROUP BY winning_team
                HAVING COUNT(*) >= 4
            """), {"year": CURRENT_DATE.year}).fetchone()

            if ks_res:
                return "offseason"
            
            return "postseason"
            
    except Exception as e:
        print(f"⚠️ 시즌 모드 판별 중 오류 발생 (기본값 'season' 사용): {e}")
        return "season"

SEASON_MODE = get_season_mode()
print(f"📅 현재 시스템 모드: {SEASON_MODE.upper()} (기준일: {CURRENT_DATE})")