// src/api/apiClient.js
// Axios 인스턴스 생성만 담당 (도메인별 API 모듈에서 이 인스턴스를 사용)
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
});

export default apiClient;
