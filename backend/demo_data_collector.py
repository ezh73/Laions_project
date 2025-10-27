# demo_data_collector.py (2022년~2025년 시즌 데이터 수집)

import requests
import json
import psycopg2
import pandas as pd
import time
from datetime import timedelta, date, datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, text

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

KBO_API_BASE_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
API_FIXED_PARAMS = {
    'leId': '1', 
    'srIdList': '0,9,6', # 정규 시즌 경기
    'seasonId': '', 
    'teamId': ''
}

DESTINATION_TABLE = "kbo_cleaned_games" 
SOURCE_TABLE = "kbo_raw_games_raw_json"

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return None

def fetch_json_by_month(game_month, year):
    params = API_FIXED_PARAMS.copy()
    params['gameMonth'] = str(game_month)
    params['seasonId'] = str(year)
    
    try:
        response = requests.get(KBO_API_BASE_URL, params=params, timeout=10)
        response.raise_for_status() 
        raw_data = response.json() 
        return raw_data
    except Exception as e:
        print(f"❌ {year}년 {game_month}월 API 호출 실패: {e}")
        return None

def insert_raw_json_data(game_month_int, json_data):
    # 🚨 SQLAlchemy를 사용한 안전한 UPSERT
    SQL_INSERT = f"""
        INSERT INTO {SOURCE_TABLE} (game_month, raw_json) 
        VALUES (:game_month, :raw_json)
        ON CONFLICT (game_month) DO UPDATE SET 
            raw_json = EXCLUDED.raw_json;
    """
    if not json_data or 'rows' not in json_data:
        return 0

    data = {
        'game_month': game_month_int, 
        'raw_json': json.dumps(json_data)
    }

    try:
        with engine.begin() as conn_sql:
            # 🚨 테이블 생성 시 PRIMARY KEY를 명확하게 지정
            conn_sql.execute(text(f"CREATE TABLE IF NOT EXISTS {SOURCE_TABLE} (game_month INTEGER PRIMARY KEY, raw_json TEXT NOT NULL);"))
            conn_sql.execute(text(SQL_INSERT), data)
        return 1
    except Exception as e:
        print(f"❌ Raw JSON 삽입 중 오류 발생: {e}")
        raise

def collect_raw_data_pipeline(years_to_scrape):
    

    total_months_collected = 0
    for year in years_to_scrape:
        print(f"\n--- ⚾️ {year}년 시즌 데이터 수집 시작 ---")
        for month in range(3, 12):
            game_month_int = int(f"{year}{str(month).zfill(2)}")
            
            time.sleep(0.5) 
            
            json_data = fetch_json_by_month(month, year)
            
            if json_data and json_data.get('rows'):
                try:
                    insert_raw_json_data(game_month_int, json_data)
                    total_months_collected += 1
                except Exception as e:
                    print(f"❌ 삽입 실패, Raw Data 수집 계속: {e}")
                    continue 
    
    return total_months_collected

def parse_schedule_json(monthly_json):
    cleaned_games_in_month = []
    game_rows = monthly_json.get('rows', [])
    
    for row_data in game_rows:
        try:
            cells = row_data.get('row', [])
            if len(cells) < 5: continue

            play_cell_html = next((cell.get('Text') for cell in cells if cell.get('Class') == 'play'), None)
            relay_cell_html = next((cell.get('Text') for cell in cells if cell.get('Class') == 'relay'), None)
            
            if not play_cell_html or not relay_cell_html: continue

            soup_relay = BeautifulSoup(relay_cell_html, 'html.parser')
            link_tag = soup_relay.find('a')
            if not link_tag: continue
                
            href = link_tag['href']
            
            game_id = href.split('gameId=')[1].split('&')[0]
            game_date_str = href.split('gameDate=')[1].split('&')[0]
            game_date = datetime.strptime(game_date_str, '%Y%m%d').date()

            soup_play = BeautifulSoup(play_cell_html, 'html.parser')
            spans = soup_play.find_all('span')
            
            away_team_name = spans[0].text
            home_team_name = spans[-1].text
            
            scores_text = soup_play.find('em').text
            if 'vs' not in scores_text: 
                continue 

            scores = scores_text.split('vs')
            away_score = int(scores[0].strip())
            home_score = int(scores[1].strip())
            
            winning_team = "무승부"
            if away_score > home_score: winning_team = away_team_name
            elif home_score > away_score: winning_team = home_team_name

            cleaned_games_in_month.append({
                "game_id": game_id, "game_date": game_date, "home_team": home_team_name,
                "away_team": away_team_name, "home_score": home_score,
                "away_score": away_score, "winning_team": winning_team
            })
        except Exception:
            continue
            
    return cleaned_games_in_month


def clean_and_insert_pipeline(total_months_collected):
    
    if total_months_collected == 0:
        print("⚠️ Raw Data가 없어 정제 과정을 건너뜁니다.")
        return 0
        
    cur_execute_count = 0
    all_cleaned_games = []

    # 🚨 SQLAlchemy를 사용하여 Raw JSON 데이터 로드
    q_raw = text(f"SELECT raw_json FROM {SOURCE_TABLE} ORDER BY game_month ASC;")
    with engine.connect() as conn_sql:
        raw_json_df = pd.read_sql(q_raw, conn_sql)
    
    raw_json_rows = raw_json_df['raw_json'].tolist()

    for raw_json_text in raw_json_rows:
        try:
            monthly_json = json.loads(raw_json_text)
            parsed_games = parse_schedule_json(monthly_json)
            all_cleaned_games.extend(parsed_games)
        except Exception as e:
            print(f"❌ JSON 파싱 및 정제 중 오류 발생: {e}")
            continue
    
    if not all_cleaned_games:
        return 0

    # 🚨 SQLAlchemy를 사용한 대량 삽입 (UPSERT 없음: ON CONFLICT DO NOTHING 사용)
    insert_query = f"""
        INSERT INTO {DESTINATION_TABLE} (game_id, game_date, home_team, away_team, home_score, away_score, winning_team)
        VALUES (
            :game_id, :game_date, :home_team, :away_team, :home_score, :away_score, :winning_team
        )
        ON CONFLICT (game_id) DO NOTHING;
    """
    
    with engine.begin() as conn_sql:
        cleaned_df = pd.DataFrame(all_cleaned_games)
        
        for _, row in cleaned_df.iterrows():
            conn_sql.execute(text(insert_query), row.to_dict())
            cur_execute_count += 1
    
    return cur_execute_count

def main_demo_collector():
    YEARS_TO_SCRAPE = [2022, 2023, 2024, 2025] 
    
    print("🚀 KBO 누적 데이터 수집 및 정제 파이프라인 시작...")
    
    months_collected = collect_raw_data_pipeline(YEARS_TO_SCRAPE)
    
    if months_collected > 0:
        try:
            inserted_rows = clean_and_insert_pipeline(months_collected)
            print(f"\n🎉 모든 누적 데이터 준비 완료! 총 {inserted_rows} 경기를 'kbo_cleaned_games'에 적재했습니다.")
        except Exception as e:
             print(f"❌ Final Clean & Insert Pipeline Failed: {e}")

    else:
        print("\n⚠️ 수집된 Raw 데이터가 없어 정제 과정을 건너뛰었습니다.")

if __name__ == "__main__":
    main_demo_collector()