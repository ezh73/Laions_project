// src/components/PredictionCard.js
import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Box,
  Alert,
  Divider,
  AlertTitle,
} from '@mui/material';
import { submitUserPrediction } from '../api/apiClient';

// Dashboard로부터 user와 prediction 데이터를 props로 받습니다.
export default function PredictionCard({ user, prediction }) {
  const [message, setMessage] = useState('');

  // 사용자가 예측 버튼을 눌렀을 때 실행되는 함수
  const handleUserPredict = async (pick) => {
    try {
      const response = await submitUserPrediction(user.uid, pick);
      setMessage(response.data.message || '예측이 성공적으로 저장되었습니다.');
    } catch (err) {
      console.error('Prediction submit failed:', err);
      const detail = err.response?.data?.detail || '예측을 전송할 수 없습니다. 다시 시도해주세요.';
      setMessage(`오류: ${detail}`);
    }
  };

  // prediction 데이터가 없으면 오류 메시지를 표시합니다.
  if (!prediction) {
    return <Alert severity="warning">예측 데이터를 불러오지 못했습니다.</Alert>;
  }

  // ✅ [핵심 수정] Card의 sx 속성에서 height: '100%'를 제거했습니다.
  return (
    <Card sx={{ display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
          🤖 AI 예측 결과
        </Typography>

        {/* 경기 날짜와 대진을 표시하는 부분 */}
        <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 2 }}>
          {prediction.game_date} | {prediction.home_team} vs {prediction.away_team}
        </Typography>

        {/* AI가 예측한 삼성의 승리 확률 */}
        <Typography variant="body1" sx={{ mb: 2 }}>
          삼성 승리 확률:{' '}
          <strong>
            {(prediction.ai_predicted_prob * 100).toFixed(2)}%
          </strong>
        </Typography>

        <Alert severity="info">
          <AlertTitle>AI의 예측 방식</AlertTitle>
          AI는 단순 통계 비교를 넘어, 과거 수백 경기의 패턴을 학습하여 팀의 컨디션·상대 전력 등을 종합 분석합니다.
        </Alert>
      </CardContent>

      <Divider />

      {/* 사용자가 예측을 제출하는 영역 */}
      <Box sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          당신의 예측은?
        </Typography>
        <Button
          variant="contained"
          color="primary"
          onClick={() => handleUserPredict(1)} // 1: 승리
          sx={{ mr: 1 }}
        >
          삼성 승리
        </Button>
        <Button
          variant="contained"
          color="secondary"
          onClick={() => handleUserPredict(0)} // 0: 패배
        >
          삼성 패배
        </Button>
        {message && (
          <Alert severity="info" sx={{ mt: 2 }}>
            {message}
          </Alert>
        )}
      </Box>
    </Card>
  );
}