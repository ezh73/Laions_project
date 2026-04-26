// src/api/performanceApi.js
// 백엔드 performance_service.py 대응: AI 성능 관련 API
import apiClient from './apiClient';

// AI 예측 성능 가져오기 (백엔드: GET /api/performance/)
export const getAiPerformance = () => apiClient.get('/api/performance/');

// 시뮬레이션 리포트 가져오기 (관리자 모드)
// TODO: 백엔드에 해당 엔드포인트 구현 후 수정 필요
export const getSimulationReport = () => apiClient.get('/api/performance/simulation-report');
