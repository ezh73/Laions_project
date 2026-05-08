-- init_db.sql (Supabase PostgreSQL용)
-- Supabase SQL Editor에서 실행하세요.

---------------------------------------------------------
-- 1. 핵심 운영 테이블
---------------------------------------------------------

-- 1.1. 통합 경기 데이터
CREATE TABLE IF NOT EXISTS kbo_games (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    winning_team VARCHAR(20),
    is_postseason BOOLEAN DEFAULT FALSE,
    sort_text VARCHAR(20) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 1.2. 업그레이드된 피처 테이블 (Streak, Recent RD 추가)
CREATE TABLE IF NOT EXISTS match_features (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    home_elo FLOAT,
    away_elo FLOAT,
    home_form FLOAT,
    away_form FLOAT,
    home_streak INTEGER,
    away_streak INTEGER,
    home_pythagorean FLOAT,
    away_pythagorean FLOAT,
    home_recent_rd FLOAT,
    away_recent_rd FLOAT,
    rest_diff INTEGER,
    home_matchup_rd FLOAT,
    away_matchup_rd FLOAT,
    season_matchup_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_game FOREIGN KEY (game_id) REFERENCES kbo_games(game_id) ON DELETE CASCADE
);

-- 1.3. AI 예측 결과
CREATE TABLE IF NOT EXISTS ai_predictions (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    predicted_winner VARCHAR(20) NOT NULL,
    prediction_prob FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- game_date 기준 조회 성능을 위한 인덱스 (performance_service.py에서 자주 사용)
CREATE INDEX IF NOT EXISTS idx_ai_predictions_game_date ON ai_predictions(game_date);

---------------------------------------------------------
-- 2. 유저 활동 및 랭킹 시스템
-- supabase_config.py의 user_profiles 테이블과 동일한 구조
---------------------------------------------------------

-- 2.1. 유저 프로필 및 통합 점수 (랭킹용)
-- user_id는 Supabase Auth의 id를 TEXT로 저장 (UUID 자동 캐스팅 호환)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    nickname VARCHAR(50) NOT NULL,
    weekly_score INTEGER DEFAULT 0,
    prediction_score INTEGER DEFAULT 0,
    quiz_score INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2.2. 유저 승리 예측 기록
CREATE TABLE IF NOT EXISTS user_predictions (
    user_id TEXT NOT NULL,
    game_id VARCHAR(20) NOT NULL,
    predicted_winner VARCHAR(20) NOT NULL,
    is_correct BOOLEAN DEFAULT NULL,
    points_earned INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

-- 2.3. 유저 퀴즈 참여 기록 (일일 제한 확인용)
CREATE TABLE IF NOT EXISTS user_quizzes (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    quiz_id INTEGER NOT NULL,
    quiz_date DATE NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score_earned INTEGER NOT NULL,
    taken_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_quizzes_date ON user_quizzes(user_id, quiz_date);

---------------------------------------------------------
-- 3. 기타 일정 및 순위
---------------------------------------------------------

CREATE TABLE IF NOT EXISTS kbo_schedule (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    game_status VARCHAR(50),
    is_postseason BOOLEAN DEFAULT FALSE,
    sort_text VARCHAR(20) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS team_rank (
    team_name VARCHAR(20) PRIMARY KEY,
    rank INTEGER NOT NULL,
    games INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    draws INTEGER NOT NULL,
    win_rate FLOAT NOT NULL,
    game_gap VARCHAR(10),
    last10 VARCHAR(10),
    streak VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);

---------------------------------------------------------
-- 4. 삼성 라이온즈 역사 테이블
---------------------------------------------------------

CREATE TABLE IF NOT EXISTS samfan_history (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,          -- 실제 역사적 사건이 발생한 날짜
    date_text VARCHAR(100) NOT NULL,   -- 표시용 날짜 텍스트 (예: "2003년 10월 2일")
    event TEXT NOT NULL,               -- 역사적 사실 설명
    reference VARCHAR(255),            -- 출처
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_history_event_date ON samfan_history(event_date);

---------------------------------------------------------
-- 5. 삼성 라이온즈 퀴즈 테이블
---------------------------------------------------------

CREATE TABLE IF NOT EXISTS samfan_quizzes (
    id SERIAL PRIMARY KEY,
    question TEXT,
    options TEXT[],
    correct_answer TEXT,
    difficulty TEXT,
    explanation TEXT,
    internal_verification TEXT,
    reference_link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

---------------------------------------------------------
-- 6. 인덱스 설정 (조회 속도 향상)
---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_game_date ON kbo_games(game_date);
CREATE INDEX IF NOT EXISTS idx_user_weekly_score ON user_profiles(weekly_score DESC);
