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
import { submitUserPrediction } from '../api/predictionApi';

export default function PredictionCard({ user, prediction }) {
  const [message, setMessage] = useState('');

  // API 응답: {status: "ok", predictions: [{game_id, home_team, away_team, predicted_winner, probability}, ...]}
  // predictions 배열의 첫 번째 경기 데이터를 사용
  const games = prediction?.predictions || [];
  const firstGame = games.length > 0 ? games[0] : null;

  const handleUserPredict = async (predictedWinner) => {
    if (!firstGame) return;
    try {
      const response = await submitUserPrediction(user.uid, firstGame.game_id, predictedWinner);
      setMessage(response.data.message || '예측이 성공적으로 저장되었습니다.');
    } catch (err) {
      console.error('Prediction submit failed:', err);
      const detail = err.response?.data?.detail || '예측을 전송할 수 없습니다. 다시 시도해주세요.';
      setMessage(`오류: ${detail}`);
    }
  };

  if (!firstGame) {
    return <Alert severity="warning">예측 데이터를 불러오지 못했습니다.</Alert>;
  }

  return (
    <Card sx={{ display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
          AI 예측 결과
        </Typography>

        <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 2 }}>
          {firstGame.home_team} vs {firstGame.away_team}
        </Typography>

        <Typography variant="body1" sx={{ mb: 2 }}>
          {firstGame.home_team} 승리 확률:{' '}
          <strong>
            {((firstGame.probability || 0) * 100).toFixed(2)}%
          </strong>
        </Typography>

        <Alert severity="info">
          <AlertTitle>AI의 예측 방식</AlertTitle>
          AI는 단순 통계 비교를 넘어, 과거 수백 경기의 패턴을 학습하여 팀의 컨디션·상대 전력 등을 종합 분석합니다.
        </Alert>
      </CardContent>

      <Divider />

      <Box sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          당신의 예측은?
        </Typography>
        <Button
          variant="contained"
          color="primary"
          onClick={() => handleUserPredict(firstGame.home_team)}
          sx={{ mr: 1 }}
        >
          {firstGame.home_team} 승리
        </Button>
        <Button
          variant="contained"
          color="secondary"
          onClick={() => handleUserPredict(firstGame.away_team)}
        >
          {firstGame.away_team} 승리
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
