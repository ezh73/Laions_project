# backend/services/crawler_service.py
import requests
from datetime import datetime, timedelta, date
from sqlalchemy import text
from bs4 import BeautifulSoup
from config import engine, CURRENT_DATE, TEAMS
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/crawler", tags=["crawler"])

DAUM_SPORTS_URL = "https://sports.daum.net/schedule/kbo"

# Daum Sports td_sort 값 → 포스트시즌 여부 매핑
POSTSEASON_SORT_VALUES = {"와일드카드", "준플레이오프", "플레이오프", "한국시리즈"}

# User-Agent (크롤링 차단 방지)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


class CrawlerService:
    @staticmethod
    def _fetch_from_daum(target_date: date):
        """
        Daum Sports KBO 일정 페이지를 스크래핑합니다.
        ?date=YYYYMMDD 파라미터로 특정 날짜 기준 데이터를 가져옵니다.
        해당 월의 전체 일정이 포함되어 응답됩니다.
        """
        url = DAUM_SPORTS_URL
        params = {"date": target_date.strftime("%Y%m%d")}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            print(f"📡 Daum Sports 데이터 수집 성공 (기준일: {target_date})")
            return soup
        except Exception as e:
            print(f"⚠️ Daum Sports 스크래핑 오류 ({target_date}): {e}")
            return None

    @staticmethod
    def _parse_daum_rows(soup):
        """
        Daum Sports HTML에서 <tbody id="scheduleList">의 각 <tr>을 순회하며
        경기 데이터를 추출합니다.
        """
        games = []
        tbody = soup.select_one("#scheduleList")
        if not tbody:
            print("⚠️ #scheduleList 테이블을 찾을 수 없습니다.")
            return games

        for tr in tbody.select("tr"):
            try:
                game_date_str = tr.get("data-date", "")  # "20260501"
                if not game_date_str:
                    continue

                game_date = datetime.strptime(game_date_str, "%Y%m%d").date()

                # game_id 추출 (/match/80100662 → 80100662)
                link_tag = tr.select_one(".link_game")
                href = link_tag.get("href", "") if link_tag else ""
                game_id = href.replace("/match/", "") if "/match/" in href else ""
                if not game_id:
                    continue

                # 팀 정보
                home_team_el = tr.select_one(".team_home .txt_team")
                away_team_el = tr.select_one(".team_away .txt_team")
                home_team = home_team_el.get_text(strip=True) if home_team_el else ""
                away_team = away_team_el.get_text(strip=True) if away_team_el else ""

                # 유효한 팀명인지 확인
                if home_team not in TEAMS or away_team not in TEAMS:
                    continue

                # 점수
                home_score_el = tr.select_one(".team_home .num_score")
                away_score_el = tr.select_one(".team_away .num_score")
                home_score_text = home_score_el.get_text(strip=True) if home_score_el else "-"
                away_score_text = away_score_el.get_text(strip=True) if away_score_el else "-"

                # 경기 상태
                state_el = tr.select_one(".state_game")
                game_status = state_el.get_text(strip=True) if state_el else ""

                # 리그 구분 (포스트시즌 판별)
                sort_el = tr.select_one(".td_sort")
                sort_text = sort_el.get_text(strip=True) if sort_el else ""
                is_postseason = sort_text in POSTSEASON_SORT_VALUES

                # 시간
                time_el = tr.select_one(".td_time")
                game_time = time_el.get_text(strip=True) if time_el else ""

                # 구장
                area_el = tr.select_one(".td_area")
                venue = area_el.get_text(strip=True) if area_el else ""

                games.append({
                    "game_id": game_id,
                    "game_date": game_date,
                    "game_time": game_time,
                    "venue": venue,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score_text,
                    "away_score": away_score_text,
                    "game_status": game_status,
                    "is_postseason": is_postseason,
                    "sort_text": sort_text,
                })
            except Exception as e:
                print(f"⚠️ 행 파싱 중 오류: {e}")
                continue

        return games

    @classmethod
    def _get_conn(cls, conn=None):
        """외부 connection이 있으면 그대로, 없으면 engine.begin() 컨텍스트 매니저 반환."""
        if conn:
            return conn
        return engine.begin()

    @classmethod
    def _upsert_kbo_games(cls, exec_conn, game, home_score, away_score, winning_team):
        """kbo_games 테이블에 경기 결과를 UPSERT합니다."""
        exec_conn.execute(text("""
            INSERT INTO kbo_games (game_id, game_date, home_team, away_team, home_score, away_score, winning_team, is_postseason, sort_text)
            VALUES (:game_id, :game_date, :home_team, :away_team, :home_score, :away_score, :winning_team, :is_postseason, :sort_text)
            ON CONFLICT (game_id) DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                winning_team = EXCLUDED.winning_team,
                sort_text = EXCLUDED.sort_text
        """), {
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "home_score": home_score,
            "away_score": away_score,
            "winning_team": winning_team,
            "is_postseason": game["is_postseason"],
            "sort_text": game["sort_text"],
        })

    @classmethod
    def _upsert_kbo_schedule(cls, exec_conn, game):
        """kbo_schedule 테이블에 경기 일정을 UPSERT합니다."""
        exec_conn.execute(text("""
            INSERT INTO kbo_schedule (game_id, game_date, home_team, away_team, game_status, is_postseason, sort_text)
            VALUES (:game_id, :game_date, :home_team, :away_team, :game_status, :is_postseason, :sort_text)
            ON CONFLICT (game_id) DO UPDATE SET
                game_status = EXCLUDED.game_status,
                sort_text = EXCLUDED.sort_text
        """), {
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "game_status": game["game_status"],
            "is_postseason": game["is_postseason"],
            "sort_text": game["sort_text"],
        })

    @classmethod
    def update_daily_pipeline(cls, conn=None):
        """
        어제 경기 결과를 업데이트하고 오늘 이후 일정을 갱신합니다.
        Daum Sports에서 오늘 날짜 기준으로 데이터를 가져옵니다.
        
        Args:
            conn: 외부 트랜잭션 connection (관리자 모드용). None이면 자체 트랜잭션 사용.
        """
        today = CURRENT_DATE

        # 오늘 날짜 기준으로 데이터 요청 (해당 월 전체 일정이 응답됨)
        soup = cls._fetch_from_daum(today)
        if not soup:
            return {"error": "Daum Sports 데이터 수집 실패"}

        games = cls._parse_daum_rows(soup)

        updated_count = 0
        scheduled_count = 0

        for game in games:
            game_date = game["game_date"]

            # 1. kbo_games: 종료된 경기만 저장/업데이트
            if game["game_status"] == "종료" and game["home_score"] != "-":
                try:
                    home_score = int(game["home_score"])
                    away_score = int(game["away_score"])
                except ValueError:
                    continue

                if home_score > away_score:
                    winning_team = game["home_team"]
                elif away_score > home_score:
                    winning_team = game["away_team"]
                else:
                    winning_team = "무승부"

                if conn:
                    cls._upsert_kbo_games(conn, game, home_score, away_score, winning_team)
                else:
                    with engine.begin() as conn_inner:
                        cls._upsert_kbo_games(conn_inner, game, home_score, away_score, winning_team)
                updated_count += 1

            # 2. kbo_schedule: 오늘 이후 일정 저장/업데이트
            if game_date >= today:
                if conn:
                    cls._upsert_kbo_schedule(conn, game)
                else:
                    with engine.begin() as conn_inner:
                        cls._upsert_kbo_schedule(conn_inner, game)
                scheduled_count += 1

        return {"updated_results": updated_count, "new_schedules": scheduled_count}


# --- API Endpoints ---

@router.post("/daily-update")
def api_daily_update():
    result = CrawlerService.update_daily_pipeline()
    return {"status": "ok", "data": result}
