// src/utils/constants.js
// 백엔드 config.py와 대응되는 프론트엔드 상수 정의

// KBO 전체 구단 목록 (전 구단 확장 반영)
export const TEAMS = [
  '삼성', 'KIA', 'LG', 'KT', '두산', 'SSG', '롯데', '한화', '키움', 'NC'
];

// 시즌 모드
export const SEASON_MODES = {
  SEASON: 'season',
  POSTSEASON: 'postseason',
  OFFSEASON: 'offseason'
};

// API 엔드포인트 경로 (실제 백엔드 구현과 동기화)
export const API_ENDPOINTS = {
  HEALTH: '/api/health',
  PREDICTION_ALL: '/api/model/all',
  PREDICTION_USER_CHOICE: '/api/predict/user-choice',
  RANKING_TOP: '/api/ranking/top',
  RANKING_WEEKLY: '/api/ranking/weekly',
  SEASON_PROJECTION: '/api/simulation/projection',
  QUIZ: '/api/quiz',
  QUIZ_SUBMIT: '/api/quiz/submit',
  AI_PERFORMANCE: '/api/performance/',
  SIMULATION_REPORT: '/api/performance/simulation-report'
};

// 점수 정책 (백엔드 ranking_service.py와 일치)
export const SCORE_POLICY = {
  PREDICTION_BASE: 10,
  PREDICTION_AI_UPSET: 15,
  QUIZ: {
    easy: 5,
    medium: 10,
    hard: 20
  }
};
