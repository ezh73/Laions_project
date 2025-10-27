# backend/crawler_service.py
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta, date
import requests
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from auth_utils import verify_admin_api_key
import os
import re
from config import ADMIN_MODE, CURRENT_DATE  # ✅ 추가

router = APIRouter()

# ✅ DB 설정
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')

KBO_GAMECENTER_URL = "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx"

# -----------------------------------------------------------
# 🧩 경기 결과 업데이트 (어제 경기 or 시연 날짜 기준)
# -----------------------------------------------------------
def _extract_yesterday_games(html: str, target_date: datetime) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    games = soup.find_all("div", class_="lineScore")

    rows = []
    for g in games:
        teams = g.find_all("strong", class_="team")
        scores = g.find_all("strong", class_="score")
        if len(teams) != 2 or len(scores) != 2:
            continue

        home_team = teams[0].get_text(strip=True)
        away_team = teams[1].get_text(strip=True)

        try:
            home_score = int(scores[0].get_text(strip=True))
            away_score = int(scores[1].get_text(strip=True))
        except ValueError:
            continue

        samsung_win = None
        if "삼성" in (home_team, away_team):
            if home_team == "삼성":
                samsung_win = 1 if home_score > away_score else 0
            else:
                samsung_win = 1 if away_score > home_score else 0

        game_date = target_date.date()
        game_id = f"{game_date.strftime('%Y%m%d')}_{home_team}_vs_{away_team}"

        rows.append({
            "game_id": game_id,
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "samsung_win": samsung_win,
            "created_at": datetime.utcnow()
        })

    return pd.DataFrame(rows)


def update_yesterday_results(test_date: date = None):
    """
    어제 경기 결과를 game_results 테이블에 upsert.
    ADMIN_MODE=True이면 test_date 또는 ADMIN_DATE 기준으로 작동.
    """
    target_date = test_date if test_date else (CURRENT_DATE - timedelta(days=1))

    print(f"📅 경기 결과 업데이트 기준일: {target_date} (ADMIN_MODE={ADMIN_MODE})")

    # 관리자모드면 DB에서 가져오고, 아니면 실제 크롤링 가능하도록 확장
    query = text("""
        SELECT game_id, game_date, home_team, away_team, home_score, away_score
        FROM kbo_cleaned_games WHERE game_date = :target_date
    """)
    with engine.connect() as conn:
        df_games = pd.read_sql(query, conn, params={"target_date": target_date})

    if df_games.empty:
        return pd.DataFrame()

    def get_samsung_win(row):
        if "삼성" not in (row['home_team'], row['away_team']):
            return None
        if row['home_team'] == "삼성":
            return 1 if row['home_score'] > row['away_score'] else 0
        else:
            return 1 if row['away_score'] > row['home_score'] else 0

    df_games['samsung_win'] = df_games.apply(get_samsung_win, axis=1)
    df_games['created_at'] = datetime.utcnow()

    with engine.begin() as conn:
        for _, row in df_games.iterrows():
            conn.execute(text("""
                INSERT INTO game_results (
                    game_id, game_date, home_team, away_team,
                    home_score, away_score, samsung_win, created_at
                ) VALUES (
                    :game_id, :game_date, :home_team, :away_team,
                    :home_score, :away_score, :samsung_win, :created_at
                ) ON CONFLICT (game_id) DO NOTHING;
            """), row.to_dict())

    return df_games


# -----------------------------------------------------------
# ⚾️ 시즌 일정 갱신
# -----------------------------------------------------------
def update_remaining_schedule(year: int):
    """
    ADMIN_MODE=True → (테스트용) DB에서 복사
    ADMIN_MODE=False → (실제 서비스) KBO 웹 크롤링
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM kbo_schedule"))
        print("🧹 기존 kbo_schedule 데이터 삭제 완료")

    df_schedule = pd.DataFrame()

    if ADMIN_MODE:
        print(f"--- ⚾ [관리자모드] {year}년 시즌 일정 DB 복사 시작 ---")
        query = text("""
            SELECT game_id, game_date, home_team, away_team
            FROM kbo_cleaned_games WHERE EXTRACT(YEAR FROM game_date) = :year
        """)
        with engine.connect() as conn:
            df_schedule = pd.read_sql(query, conn, params={"year": year})
        df_schedule['game_status'] = '예정'
    else:
        print(f"--- ⚾ [실제모드] {year}년 KBO 공식 일정 크롤링 시작 ---")
        KBO_API_BASE_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetMonthSchedule"
        all_schedule_games = []
        for month in range(3, 12):
            params = {'leId': '1', 'srIdList': '0,9,6', 'seasonId': str(year), 'gameMonth': str(month).zfill(2)}
            try:
                response = requests.get(KBO_API_BASE_URL, params=params, timeout=10)
                monthly_json = response.json()
                if not monthly_json.get('rows'): continue

                for row_obj in monthly_json.get('rows', []):
                    for cell_obj in row_obj.get('row', []):
                        html_content = cell_obj.get('Text')
                        if not html_content or re.search(r'\d+\s*:\s*\d+', html_content): continue
                        clean_text = re.sub(r'<[^>]+>', ' ', html_content).strip()
                        day_match = re.search(r'^(\d+)', clean_text)
                        if not day_match: continue
                        team_match = re.search(r'([A-Z가-힣]+)\s+(?:vs|:)\s+([A-Z가-힣]+)', clean_text, re.IGNORECASE)
                        if not team_match: continue

                        try:
                            day = int(day_match.group(1))
                            away_team = team_match.group(1).strip()
                            home_team = team_match.group(2).strip()
                            game_date = date(year, month, day)
                            game_id = f"{game_date.strftime('%Y%m%d')}{away_team[:2]}{home_team[:2]}0"
                            all_schedule_games.append({
                                "game_id": game_id,
                                "game_date": game_date,
                                "home_team": home_team,
                                "away_team": away_team,
                                "game_status": "예정"
                            })
                        except ValueError:
                            continue
            except Exception:
                continue

        if all_schedule_games:
            df_schedule = pd.DataFrame(all_schedule_games)

    if not df_schedule.empty:
        df_schedule.to_sql("kbo_schedule", engine, if_exists="append", index=False)
        print(f"✅ {year}년 시즌 일정 {len(df_schedule)}개 DB 주입 완료")

    return df_schedule


# -----------------------------------------------------------
# 🕹️ 스케줄러용 통합 함수
# -----------------------------------------------------------
def run_daily_crawl():
    """스케줄러 파이프라인에서 호출할 전체 수집 루틴."""
    print(f"🚀 run_daily_crawl 시작 (ADMIN_MODE={ADMIN_MODE})")
    game_df = update_yesterday_results()
    schedule_df = update_remaining_schedule(CURRENT_DATE.year)
    return {
        "game_result_rows": len(game_df),
        "schedule_rows": len(schedule_df),
    }


# -----------------------------------------------------------
# 🧭 FastAPI 라우트
# -----------------------------------------------------------
@router.post("/admin/crawl")
def manual_crawl(admin_key: str = Depends(verify_admin_api_key)):
    """관리용: 강제로 수집 실행."""
    try:
        res = run_daily_crawl()
        return {"status": "ok", **res, "mode": "admin" if ADMIN_MODE else "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest-games")
def api_latest_games(limit: int = 5):
    """최근 경기 결과 조회."""
    query = text("""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, samsung_win
        FROM game_results
        ORDER BY game_date DESC, game_id DESC
        LIMIT :limit
    """)
    df = pd.read_sql(query, engine, params={"limit": limit})
    return df.to_dict(orient="records")


@router.post("/admin/update-schedule/{year}")
def manual_update_schedule(year: int, admin_key: str = Depends(verify_admin_api_key)):
    """관리용: 특정 연도의 전체 시즌 일정을 강제로 수집."""
    try:
        df = update_remaining_schedule(year)
        return {
            "status": "ok",
            "year": year,
            "mode": "admin (db_copy)" if ADMIN_MODE else "live (web_crawl)",
            "scheduled_games_count": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
