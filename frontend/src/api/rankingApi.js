// src/api/rankingApi.js
// 백엔드 ranking_service.py + simulation_service.py 대응: 랭킹 관련 API
import apiClient from './apiClient';

// 전체 랭킹 가져오기 (weekly_score 기준)
export const getTopRanking = (limit = 10) => apiClient.get(`/api/ranking/top?limit=${limit}`);

// 시즌 순위 예측 결과 가져오기 (백엔드: GET /api/simulation/projection)
export const getSeasonProjection = () => apiClient.get('/api/simulation/projection');
