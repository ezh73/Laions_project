// src/components/HistoryCard.js
// 오늘의 삼성 라이온즈 역사 섹션
// DB에 저장된 역사 데이터를 조회하여 출력합니다.
import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Alert,
} from '@mui/material';
import apiClient from '../api/apiClient';

export default function HistoryCard() {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await apiClient.get('/api/history/today');
        setHistory(response.data?.history || null);
      } catch (err) {
        // 히스토리 API가 아직 구현되지 않은 경우 조용히 넘어감
        if (err.response?.status !== 404) {
          console.error('Failed to fetch history:', err);
        }
        setHistory(null);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  if (loading) return null; // 로딩 중에는 표시하지 않음
  if (!history) return null; // 데이터가 없으면 표시하지 않음

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          📜 오늘의 삼성 라이온즈 역사
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {history.date_text} - {history.event}
        </Typography>
        {history.reference && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            출처: {history.reference}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
