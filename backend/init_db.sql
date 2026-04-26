-- init_db.sql

---------------------------------------------------------
-- 1. 핵심 운영 테이블
---------------------------------------------------------

-- 1.1. 통합 경기 데이터
CREATE TABLE kbo_games (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    winning_team VARCHAR(20), 
    is_postseason BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 1.2. 업그레이드된 피처 테이블 (Streak, Recent RD 추가)
CREATE TABLE match_features (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    home_elo FLOAT,
    away_elo FLOAT,
    home_form FLOAT,
    away_form FLOAT,
    home_streak INTEGER,       -- 👈 추가: 홈팀 연승(+) 연패(-)
    away_streak INTEGER,       -- 👈 추가: 원정팀 연승(+) 연패(-)
    home_pythagorean FLOAT,
    away_pythagorean FLOAT,
    home_recent_rd FLOAT,      -- 👈 추가: 홈팀 최근 5경기 평균 득실차
    away_recent_rd FLOAT,      -- 👈 추가: 원정팀 최근 5경기 평균 득실차
    rest_diff INTEGER,
    home_matchup_rd FLOAT,       -- 👈 추가: 홈팀의 원정팀 상대 누적 평균 득실차
    away_matchup_rd FLOAT,       -- 👈 추가: 원정팀의 홈팀 상대 누적 평균 득실차
    season_matchup_count INTEGER, -- 👈 추가: 이번 시즌 맞대결 횟수
    
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_game FOREIGN KEY (game_id) REFERENCES kbo_games(game_id) ON DELETE CASCADE
);

-- 1.3. AI 예측 결과
CREATE TABLE ai_predictions (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    predicted_winner VARCHAR(20) NOT NULL,
    prediction_prob FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

---------------------------------------------------------
-- 2. 유저 활동 및 랭킹 시스템 (신규)
---------------------------------------------------------

-- 2.1. 유저 프로필 및 통합 점수 (랭킹용)
CREATE TABLE user_rankings (
    user_id VARCHAR(50) PRIMARY KEY, -- Firebase UID
    nickname VARCHAR(50) NOT NULL,
    prediction_score INTEGER DEFAULT 0, -- 승리 예측으로 얻은 누적 점수
    quiz_score INTEGER DEFAULT 0,       -- 퀴즈로 얻은 누적 점수
    total_score INTEGER DEFAULT 0,      -- 합산 점수 (정렬 기준)
    last_updated TIMESTAMP DEFAULT NOW()
);

-- 2.2. 유저 승리 예측 기록 (기존 기능 보강)
CREATE TABLE user_predictions (
    user_id VARCHAR(50) NOT NULL,
    game_id VARCHAR(20) NOT NULL,
    predicted_winner VARCHAR(20) NOT NULL,
    is_correct BOOLEAN DEFAULT NULL, -- 경기 종료 후 정답 여부 업데이트용
    points_earned INTEGER DEFAULT 0, -- 이 예측으로 얻은 점수 (예: 맞히면 10점)
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES user_rankings(user_id) ON DELETE CASCADE
);

-- 2.3. 유저 퀴즈 참여 기록 (일일 제한 확인용)
CREATE TABLE user_quizzes (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    quiz_id INTEGER NOT NULL,        -- samfan_quizzes.id 참조
    quiz_date DATE NOT NULL,         -- 퀴즈를 푼 날짜 (일일 제한 확인용)
    is_correct BOOLEAN NOT NULL,     -- 정답 여부
    score_earned INTEGER NOT NULL,   -- 획득 점수
    taken_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_user_quiz FOREIGN KEY (user_id) REFERENCES user_rankings(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_user_quizzes_date ON user_quizzes(user_id, quiz_date);

---------------------------------------------------------
-- 3. 기타 일정 및 순위
---------------------------------------------------------

CREATE TABLE kbo_schedule (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    game_status VARCHAR(50), 
    is_postseason BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE team_rank (
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

-- 4. 인덱스 설정 (조회 속도 향상)
CREATE INDEX idx_game_date ON kbo_games(game_date);
CREATE INDEX idx_user_total_score ON user_rankings(total_score DESC);

-- 5. Admin 전용 테이블
CREATE TABLE kbo_games_admin (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    winning_team VARCHAR(20), 
    is_postseason BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE match_features_admin (
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
    CONSTRAINT fk_game_admin FOREIGN KEY (game_id) REFERENCES kbo_games_admin(game_id) ON DELETE CASCADE
);

CREATE TABLE ai_predictions_admin (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    predicted_winner VARCHAR(20) NOT NULL,
    prediction_prob FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE kbo_schedule_admin (
    game_id VARCHAR(20) PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(20) NOT NULL,
    away_team VARCHAR(20) NOT NULL,
    game_status VARCHAR(50), 
    is_postseason BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);