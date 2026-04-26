// src/api/systemApi.js
// 시스템 상태 관련 API (health, season mode)
// 백엔드 main.py health check 대응
import apiClient from './apiClient';

// 서버 상태(시즌 모드 포함) 확인용 API
export const getHealth = () => apiClient.get('/api/health');
