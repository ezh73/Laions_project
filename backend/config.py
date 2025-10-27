# backend/config.py
import os
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- 1. 환경 변수 로드 및 기본 설정 ---
load_dotenv()

DATA_SOURCE = os.getenv("DATA_SOURCE", "db")

# DB 연결 설정 (시즌 모드 자동 판별에 필요)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")

try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    print(f"🚨 DB 연결 실패: {e}. DB 조회 없이 날짜 기준으로만 동작합니다.")
    engine = None

TODAY = date.today()
CURRENT_YEAR = TODAY.year

# --- 2. DB 기반 시즌 모드 자동 판별 로직 ---

def is_regular_season_finished():
    """DB를 조회하여 모든 정규시즌 경기가 종료되었는지 확인합니다."""
    if engine is None:
        print("⚠️ DB에 연결할 수 없어 시즌 종료 여부를 확인할 수 없습니다. 시즌이 진행 중인 것으로 간주합니다.")
        return False  # DB 연결 실패 시, 안전하게 시즌 진행 중으로 처리

    try:
        # '경기전' 또는 '예정' 상태인 정규시즌 경기가 남아있는지 확인
        # (테이블/컬럼명은 실제 프로젝트에 맞게 수정 필요)
        query = text("SELECT COUNT(*) FROM kbo_schedule WHERE game_status IN ('경기전', '예정')")
        with engine.connect() as conn:
            remaining_games = conn.execute(query).scalar_one_or_none()
        
        # 남은 경기가 0이면 True (시즌 종료), 아니면 False (시즌 진행 중)
        return remaining_games == 0
    except Exception as e:
        print(f"⚠️ 시즌 종료 여부 확인 중 DB 오류: {e}. 안전하게 시즌 진행 중으로 처리합니다.")
        return False

def get_season_mode():
    """DB 상태와 현재 날짜를 종합하여 최적의 시즌 모드를 결정합니다."""
    # 1순위: DB에 남은 정규시즌 경기가 있다면, 무조건 'season' 모드
    if not is_regular_season_finished():
        return "season"

    # 2순위: 모든 정규시즌 경기가 끝났다면, 날짜로 포스트시즌/비시즌 구분
    # 포스트시즌 종료일을 11월 30일로 넉넉하게 설정
    postseason_end_date = date(CURRENT_YEAR, 11, 30)

    if TODAY <= postseason_end_date:
        return "postseason"  # 모든 경기가 끝났고, 아직 11월 30일 이전
    else:
        return "offseason"  # 모든 경기가 끝났고, 포스트시즌 기간도 지남

# --- 3. 관리자 모드 및 최종 설정값 결정 ---

# 자동 판별된 시즌 모드를 기본값으로 설정
SEASON_MODE = get_season_mode()

# .env 파일에서 관리자 설정값 읽기
ADMIN_MODE = os.getenv("ADMIN_MODE", "false").lower() in ["true", "1", "yes"]
ADMIN_OVERRIDE_MODE = os.getenv("ADMIN_OVERRIDE_MODE", None)

# 관리자 모드가 활성화되고, 덮어쓸 모드가 지정되어 있다면 최종 SEASON_MODE를 변경
if ADMIN_MODE and ADMIN_OVERRIDE_MODE in ["season", "postseason", "offseason"]:
    SEASON_MODE = ADMIN_OVERRIDE_MODE

# 관리자 시연용 날짜 설정 (기존 로직 유지)
_admin_date_raw = os.getenv("ADMIN_DATE")
ADMIN_DATE = None
if _admin_date_raw:
    try:
        ADMIN_DATE = datetime.strptime(_admin_date_raw, "%Y-%m-%d").date()
    except ValueError:
        print(f"⚠️ ADMIN_DATE 형식이 잘못되었습니다: {_admin_date_raw}. 실제 날짜를 사용합니다.")

CURRENT_DATE = ADMIN_DATE if ADMIN_MODE and ADMIN_DATE else TODAY

# --- 4. 디버그 정보 출력 ---
print("--- [Config Initialized] ---")
print(f"🔧 ADMIN_MODE: {ADMIN_MODE}")
if ADMIN_MODE:
    print(f"🕹️ ADMIN_OVERRIDE_MODE: {ADMIN_OVERRIDE_MODE}")
    print(f"📅 ADMIN_DATE: {ADMIN_DATE}")
    print(f"💾 DATA_SOURCE: {DATA_SOURCE}")
print(f"🕒 CURRENT_DATE: {CURRENT_DATE}")
print(f"🏟️ FINAL SEASON_MODE: {SEASON_MODE}")
print("----------------------------")