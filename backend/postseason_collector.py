# postseason_collector.py (포스트시즌 일정 확보 - 최종 안정화)

import requests
import json
import psycopg2
import pandas as pd
import time
from datetime import datetime, date
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
import re # 🚨 정규 표현식 모듈 추가

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

DB_CONFIG = {}
if DATABASE_URL:
    result = urlparse(DATABASE_URL)
    DB_CONFIG["dbname"] = result.path[1:]
    DB_CONFIG["user"] = result.username
    DB_CONFIG["password"] = result.password
    DB_CONFIG["host"] = result.hostname
    DB_CONFIG["port"] = result.port
else:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")

# 🚨 DB 연결 엔진 정의
engine = create_engine(DATABASE_URL, client_encoding='utf8')

KBO_API_BASE_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetMonthSchedule"
POSTSEASON_SRIDLIST = '3,4,5,7' 

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return None

def fetch_postseason_json(year, game_month):
    """특정 연도/월의 포스트시즌 경기 데이터 JSON 전체를 반환합니다."""
    params = {
        'leId': '1', 
        'srIdList': POSTSEASON_SRIDLIST, 
        'seasonId': str(year), 
        'gameMonth': str(game_month) # 월별 파라미터 전달
    }
    
    try:
        response = requests.get(KBO_API_BASE_URL, params=params, timeout=10)
        response.raise_for_status() 
        raw_data = response.json() 
        return raw_data
    except Exception as e:
        print(f"❌ {year}년 {game_month}월 포스트시즌 API 호출 실패: {e}")
        return None

def parse_postseason_schedule(monthly_json, year, month):
    """
    KBO 캘린더 JSON 구조를 파싱하여 정제된 포스트시즌 일정 리스트를 반환합니다.
    (스코어 없는 '예정' 경기만 추출)
    """
    schedule_rows = []
    
    for row_obj in monthly_json.get('rows', []):
        for cell_obj in row_obj.get('row', []):
            
            html_content = cell_obj.get('Text')
            if not html_content: continue
            
            # 1. 스코어가 없는 '예정 경기' 텍스트 패턴 추출
            # 점수 패턴 (숫자 : 숫자)이 없고, 팀 이름 + 팀 이름 패턴이 있어야 함
            if re.search(r'\d+\s*:\s*\d+', html_content): 
                continue # 점수가 있으면 끝난 경기이므로 스킵
            
            # 2. HTML 태그 제거 및 텍스트 클리닝
            clean_text = re.sub(r'<[^>]+>', ' ', html_content).strip()
            
            # 3. 경기 날짜/ID 확보 (가장 안정적인 dayNum과 요청 월 사용)
            day_num_match = re.search(r'(\d+)', clean_text)
            if not day_num_match: continue
            day = int(day_num_match.group(1))
            
            # 4. 팀 이름 추출 (RegEx 매치)
            # 팀 이름은 '한화 : LG [잠실]' 또는 'LG vs 한화' 형태
            # 🚨 KBO 응답의 불규칙성을 고려하여 모든 구분자(: vs)를 허용
            team_match = re.search(r'([A-Z가-힣]+)\s+(?:vs|:)\s+([A-Z가-힣]+)', clean_text, re.IGNORECASE)
            
            if not team_match: 
                continue # 팀 매칭 패턴이 없으면 스킵

            # 그룹 추출: (팀 A, 팀 B)
            away_team_name = team_match.group(1).strip()
            home_team_name = team_match.group(2).strip()
            
            try:
                game_date = date(year, month, day)
                game_date_str = game_date.strftime('%Y%m%d')
                game_id = f"{game_date_str}_{away_team_name}_vs_{home_team_name}"
            except ValueError:
                continue

            schedule_rows.append({
                "game_id": game_id, "game_date": game_date, "home_team": home_team_name,
                "away_team": away_team_name, "game_status": "예정", "created_at": datetime.utcnow()
            })
            
    return schedule_rows

def main_postseason_collector(years_to_scrape):
    """
    지정된 연도의 포스트시즌 일정을 수집하고 kbo_schedule 테이블에 주입합니다.
    """
    total_games_injected = 0
    
    # 🚨 kbo_schedule 테이블의 이전 데이터를 삭제합니다.
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn_sql:
        conn_sql.execute(text("DELETE FROM kbo_schedule"))

    for year in years_to_scrape:
        print(f"\n--- ⚾️ {year}년 포스트시즌 일정 데이터 수집 시작 ---")
        
        for month in [10, 11]:
            
            time.sleep(1.0) 
            
            json_data = fetch_postseason_json(year, month)
            
            if json_data and json_data.get('rows'):
                schedule_rows = parse_postseason_schedule(json_data, year, month)
                df_schedule = pd.DataFrame(schedule_rows)
                
                if not df_schedule.empty:
                    try:
                        with engine.begin() as conn_sql:
                            df_schedule.to_sql("kbo_schedule", conn_sql, index=False, if_exists="append")
                        
                        total_games_injected += len(df_schedule)
                        print(f"    ✅ {year}년 {month}월 포스트시즌 일정 {len(df_schedule)}개 DB 주입 완료.")
                    except Exception as e:
                        print(f"❌ DB 삽입 오류: {e}")
                else:
                    print(f"    ⚠️ {year}년 {month}월 포스트시즌 일정 데이터가 없습니다.")

    print(f"\n✅ 전체 포스트시즌 일정 수집 완료! 총 {total_games_injected}개 일정 적재.")

if __name__ == "__main__":
    # 2025년 포스트시즌 일정을 확보한다고 가정
    main_postseason_collector([2025])