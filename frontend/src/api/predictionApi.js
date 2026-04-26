// src/api/predictionApi.js
// 백엔드 model_service.py 대응: 예측 관련 API
import apiClient from './apiClient';

// AI 예측 결과 가져오기 (백엔드: GET /api/model/all)
export const getPrediction = () => apiClient.get('/api/model/all');

// 사용자 예측 제출하기 (전 구단 확장)
// 백엔드 user_predictions 테이블: user_id, game_id, predicted_winner
// TODO: 백엔드에 해당 엔드포인트 구현 후 경로 수정 필요
export const submitUserPrediction = (userId, gameId, predictedWinner) => apiClient.post('/api/predict/user-choice', null, {
    params: { user_id: userId, game_id: gameId, predicted_winner: predictedWinner }
});
