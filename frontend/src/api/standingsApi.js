// src/api/standingsApi.js
// 리그 순위 관련 API
import apiClient from './apiClient';

// KBO 리그 순위 조회
export const getStandings = () => apiClient.get('/api/standings');
