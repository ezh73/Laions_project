# backend/services/crawler_service.py
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import text
import re
from bs4 import BeautifulSoup
from config import engine, CURRENT_DATE, TEAMS, TABLE_KBO_GAMES, TABLE_KBO_SCHEDULE
from auth_utils import verify_admin_api_key
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/crawler", tags=["crawler"])

KBO_API_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"

# KBO srId 정의 (0: 정규시즌, 3: 와일드카드, 4: 준플레이오프, 5: 플레이오프, 7: 한국시리즈)
REGULAR_SR_IDS = "0"
POSTSEASON_SR_IDS = "3,4,5,7,8"

class CrawlerService:
    @staticmethod
    def _fetch_from_kbo(year: int, month: int, sr_ids: str):
        params = {
            "leId": "1",
            "srIdList": sr_ids,
            "seasonId": str(year),
            "gameMonth": f"{month:02d}",
            "teamId": ""
        }
        try:
            resp = requests.get(KBO_API_URL, params=params, timeout=10)
            data = resp.json().get("rows", [])
            
            # 👇 이 줄을 추가해서 데이터가 실제로 오는지 확인합니다!
            if data:
                print(f"📡 {year}년 {month}월 데이터 수집 성공: {len(data)}건 (첫번째 데이터: {data[0]})")
            else:
                # 데이터가 아예 안 온다면 파라미터(srId) 문제일 수 있음
                print(f"❓ {year}년 {month}월 데이터가 비어있습니다.")
                
            return data
        except Exception as e:
            print(f"⚠️ KBO API 호출 오류 ({year}-{month}): {e}")
            return []
        
    @staticmethod
    def _parse_game_row(row, last_date=None, is_postseason=False):
        """병합된 셀(RowSpan)을 고려하여 하루 5경기를 모두 파싱합니다."""
        try:
            cells = row.get('row', [])
            # 데이터가 너무 적으면 무시
            if len(cells) < 7: return None, last_date

            # 1. Game ID 찾기 (정규식)
            gid = None
            for cell in cells:
                txt = cell.get('Text', '')
                match = re.search(r'gameId=([0-9A-Z]+)', txt)
                if match:
                    gid = match.group(1)
                    break
            
            if not gid: return None, last_date
            
            # 날짜 업데이트 (ID에서 추출하거나 이전 날짜 사용)
            current_date = datetime.strptime(gid[:8], "%Y%m%d").date()

            # 2. 팀명 및 점수가 들어있는 셀 찾기 
            # (날짜 셀 유무에 따라 인덱스가 2번 혹은 1번으로 바뀝니다)
            play_cell = None
            for cell in cells:
                if 'vs' in cell.get('Text', ''):
                    play_cell = cell.get('Text', '')
                    break
            
            if not play_cell: return None, current_date

            soup = BeautifulSoup(play_cell, 'lxml')
            spans = [s.get_text(strip=True) for s in soup.find_all('span') if s.get_text(strip=True)]
            if len(spans) < 2: return None, current_date
            
            raw_away, raw_home = spans[0], spans[-1]
            team_map = {"SK": "SSG", "넥센": "키움", "우리": "키움"}
            away_team = team_map.get(raw_away, raw_away)
            home_team = team_map.get(raw_home, raw_home)

            # 3. 점수 추출
            nums = re.findall(r'\d+', soup.get_text(strip=True))
            if len(nums) >= 2:
                away_score, home_score = int(nums[-2]), int(nums[-1])
            else:
                return None, current_date

            # 4. 필터링
            from config import TEAMS
            if away_team not in TEAMS or home_team not in TEAMS:
                return None, current_date

            parsed_data = {
                "game_id": gid, "game_date": current_date,
                "home_team": home_team, "away_team": away_team,
                "home_score": home_score, "away_score": away_score,
                "winning_team": home_team if home_score > away_score else (away_team if away_score > home_score else "무승부"),
                "is_postseason": is_postseason
            }
            return parsed_data, current_date
        except Exception:
            return None, last_date
        
    @classmethod
    def scrape_historical_data(cls, start_year: int, end_year: int):
        total_count = 0
        for year in range(start_year, end_year + 1):
            for month in range(3, 12):
                data = cls._fetch_from_kbo(year, month, "0,9,6")
                if not data: continue
                
                # 핵심: 날짜가 병합된 경우를 대비해 마지막 날짜를 기억합니다.
                last_seen_date = None 
                
                for row_data in data:
                    # 1. 파싱 함수에 마지막 날짜 정보를 함께 전달
                    parsed, last_seen_date = cls._parse_game_row(row_data, last_seen_date)
                    
                    if parsed:
                        with engine.begin() as conn:
                            insert_query = text(f"""
                                INSERT INTO {TABLE_KBO_GAMES} (game_id, game_date, home_team, away_team, home_score, away_score, winning_team, is_postseason)
                                VALUES (:game_id, :game_date, :home_team, :away_team, :home_score, :away_score, :winning_team, :is_postseason)
                                ON CONFLICT (game_id) DO NOTHING
                            """)
                            result = conn.execute(insert_query, parsed)
                            if result.rowcount > 0:
                                total_count += 1
            print(f"✅ {year}년 수집 완료. 현재 누적: {total_count}개")
        return total_count

    @classmethod
    def update_daily_pipeline(cls):
        """어제 경기 결과를 업데이트하고 오늘/내일 일정을 갱신합니다."""
        today = CURRENT_DATE
        yesterday = today - timedelta(days=1)
        
        sr_ids_all = f"{REGULAR_SR_IDS},{POSTSEASON_SR_IDS}"
        
        # 1. 어제 결과 업데이트 (kbo_games)
        rows = cls._fetch_from_kbo(yesterday.year, yesterday.month, sr_ids_all)
        updated_count = 0
        for r in rows:
            # sr_ids_all에 정규시즌 ID("0")만 있는지, 포스트시즌 ID도 포함되었는지 확인
            # "0"만 있으면 정규시즌, 그 외 ID가 포함되었으면 포스트시즌
            is_ps = (sr_ids_all != REGULAR_SR_IDS)
            game, _ = cls._parse_game_row(r, is_postseason=is_ps)
            if game and game['game_date'] == yesterday and game['winning_team']:
                with engine.begin() as conn:
                    conn.execute(text(f"""
                        INSERT INTO {TABLE_KBO_GAMES} (game_id, game_date, home_team, away_team, home_score, away_score, winning_team, is_postseason)
                        VALUES (:game_id, :game_date, :home_team, :away_team, :home_score, :away_score, :winning_team, :is_postseason)
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score,
                            winning_team = EXCLUDED.winning_team
                    """), game)
                    updated_count += 1

        # 2. 향후 일정 업데이트 (kbo_schedule)
        # 오늘 포함 향후 7일간의 일정을 긁어옴
        schedule_rows = cls._fetch_from_kbo(today.year, today.month, sr_ids_all)
        scheduled_count = 0
        for r in schedule_rows:
            is_ps = (sr_ids_all != REGULAR_SR_IDS)
            game, _ = cls._parse_game_row(r, is_postseason=is_ps)
            if game and game['game_date'] >= today:
                with engine.begin() as conn:
                    conn.execute(text(f"""
                        INSERT INTO {TABLE_KBO_SCHEDULE} (game_id, game_date, home_team, away_team, game_status, is_postseason)
                        VALUES (:game_id, :game_date, :home_team, :away_team, '예정', :is_postseason)
                        ON CONFLICT (game_id) DO NOTHING
                    """), game)
                    scheduled_count += 1
                    
        return {"updated_results": updated_count, "new_schedules": scheduled_count}

# --- API Endpoints ---

@router.post("/historical")
def api_scrape_historical(start_year: int, end_year: int, admin_key: str = Depends(verify_admin_api_key)):
    count = CrawlerService.scrape_historical_data(start_year, end_year)
    return {"status": "ok", "message": f"{count}개의 과거 경기 데이터가 저장되었습니다."}

@router.post("/daily-update")
def api_daily_update(admin_key: str = Depends(verify_admin_api_key)):
    result = CrawlerService.update_daily_pipeline()
    return {"status": "ok", "data": result}