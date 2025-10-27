// src/api/apiClient.js
import axios from 'axios';

// FastAPI 백엔드 서버 주소
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL, // 👈 수정: 환경 변수 사용
});

// AI 예측 결과 가져오기
export const getPrediction = () => apiClient.get('/api/predict/today');

// 전체 랭킹 가져오기
export const getTopRanking = (limit = 10) => apiClient.get(`/api/ranking/top?limit=${limit}`);

// 주간 랭킹 가져오기
export const getWeeklyRanking = (limit = 10) => apiClient.get(`/api/ranking/weekly?limit=${limit}`);

// 시즌 순위 예측 결과 가져오기
export const getSeasonProjection = () => apiClient.get('/api/ranking/season-projection');

// 퀴즈 가져오기
export const getQuiz = () => apiClient.get('/api/quiz');

// 퀴즈 정답 제출하기
export const submitQuiz = (userId, quizId, answer, displayName) => apiClient.post('/api/quiz/submit', null, {
    params: { user_id: userId, quiz_id: quizId, answer: answer, display_name: displayName }
});

// 사용자 예측 제출하기
export const submitUserPrediction = (userId, pick) => apiClient.post('/api/predict/user-choice', null, {
    params: { user_id: userId, pick_samsung_win: pick }
});

// AI 예측 성능 가져오기
export const getAiPerformance = () => apiClient.get('/api/ai/performance/samsung');

// ✅ 추가: 서버 상태(시즌 모드 포함) 확인용 API
export const getHealth = () => apiClient.get('/health');

export const getSimulationReport = () => apiClient.get('/api/ai/performance/simulation-report');