-- init_db.sql
-- 🚀 Laions 백엔드 포트폴리오용 PostgreSQL 테이블 초기화 스크립트 (최종)

-- 1. 기존 테이블 정리
DROP TABLE IF EXISTS ai_predictions;
DROP TABLE IF EXISTS match_features;
DROP TABLE IF EXISTS game_results;
DROP TABLE IF EXISTS kbo_raw_games_raw_json;
DROP TABLE IF EXISTS kbo_cleaned_games; 
DROP TABLE IF EXISTS kbo_schedule; 

---------------------------------------------------------
-- 2. 서비스 운영 테이블
---------------------------------------------------------

-- 2.1. 경기 결과 저장 (시계열 피처 계산의 기반)
CREATE TABLE game_results (
    game_id TEXT PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    samsung_win INTEGER, -- 1=삼성 승리, 0=아님, NULL=삼성 경기 아니면
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2.2. 팀 순위표 (시뮬레이션 초기값 확보용)
CREATE TABLE team_rank (
    team_name TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    games INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    draws INTEGER NOT NULL,
    win_rate FLOAT NOT NULL,
    game_gap TEXT,
    last10 TEXT,
    streak TEXT,
    home_record TEXT,
    away_record TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2.3. 모델 입력용 피처 (7개 ELO/Form/Pythagorean 피처 확정)
CREATE TABLE match_features (
    game_id TEXT PRIMARY KEY, 
    game_date DATE NOT NULL,
    
    samsung_elo FLOAT,         
    opponent_elo FLOAT,      
    rest_diff INTEGER,       
    samsung_form FLOAT,      
    opponent_form FLOAT,     
    samsung_pythagorean FLOAT, 
    opponent_pythagorean FLOAT,
    
    samsung_win INTEGER, -- 실제 결과(라벨). 
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2.4. 모델 예측 저장
CREATE TABLE ai_predictions (
    game_id TEXT PRIMARY KEY,
    game_date DATE NOT NULL,
    predicted_win INTEGER NOT NULL,
    predicted_prob FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2.6. 잔여 경기 일정 (몬테카를로 시뮬레이션용)
CREATE TABLE kbo_schedule (
    game_id TEXT PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    game_status VARCHAR(50), 
    created_at TIMESTAMP DEFAULT NOW()
);


---------------------------------------------------------
-- 3. 데이터 수집/정제용 테이블
---------------------------------------------------------

-- 3.1. Raw JSON 저장 테이블 
CREATE TABLE kbo_raw_games_raw_json (
    game_month INTEGER PRIMARY KEY,
    raw_json TEXT NOT NULL
);

-- 3.2. 정제된 모든 경기 데이터 (ELO, Form 등 피처 계산의 기반)
CREATE TABLE kbo_cleaned_games (
    game_id VARCHAR(20) PRIMARY KEY, 
    game_date DATE NOT NULL,
    home_team VARCHAR(50) NOT NULL, 
    away_team VARCHAR(50) NOT NULL,
    home_score INT, 
    away_score INT, 
    winning_team VARCHAR(50)
);

-- init_db.sql 파일에 추가해두셔도 좋습니다.
CREATE TABLE IF NOT EXISTS season_projection_results (
    team_name TEXT PRIMARY KEY,
    predicted_rank FLOAT NOT NULL,
    playoff_probability FLOAT NOT NULL,
    updated_at TIMESTAMP
);