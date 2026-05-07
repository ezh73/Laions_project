// src/components/PredictionCard.js
// 정규시즌 & 포스트시즌 통합 예측 카드
// 전 경기 예측 결과를 리스트로 표시하고 사용자 예측을 받습니다.
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
} from '@mui/material';
import { submitUserPrediction } from '../api/predictionApi';

export default function PredictionCard({ user, prediction, isPostseason = false }) {
  const [messages, setMessages] = useState({});

  // API 응답: {status: "ok", predictions: [{game_id, home_team, away_team, predicted_winner, probability}, ...]}
  const games = prediction?.predictions || [];

  const handleUserPredict = async (gameId, predictedWinner) => {
    try {
      const response = await submitUserPrediction(user.uid, gameId, predictedWinner);
      setMessages(prev => ({
        ...prev,
        [gameId]: { type: 'success', text: response.data.message || '예측이 저장되었습니다.' }
      }));
    } catch (err) {
      console.error('Prediction submit failed:', err);
      const detail = err.response?.data?.detail || '예측을 전송할 수 없습니다.';
      setMessages(prev => ({
        ...prev,
        [gameId]: { type: 'error', text: `오류: ${detail}` }
      }));
    }
  };

  if (games.length === 0) {
    return (
      <Card>
        <CardContent>
          <Alert severity="warning">
            {isPostseason ? '포스트시즌' : '오늘의'} 예측 데이터를 불러오지 못했습니다.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
          {isPostseason ? '🏆 포스트시즌' : '⚾'} AI 예측 결과
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          총 {games.length}개 경기 예측
        </Typography>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>경기</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>AI 예측</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>확률</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>당신의 선택</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {games.map((game) => (
                <TableRow key={game.game_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {game.away_team} vs {game.home_team}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={game.predicted_winner}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {((game.probability || 0) * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      <Button
                        size="small"
                        variant={messages[game.game_id] ? 'outlined' : 'contained'}
                        color="primary"
                        onClick={() => handleUserPredict(game.game_id, game.home_team)}
                        disabled={!!messages[game.game_id]}
                        sx={{ minWidth: 60, fontSize: '0.7rem' }}
                      >
                        {game.home_team}
                      </Button>
                      <Button
                        size="small"
                        variant={messages[game.game_id] ? 'outlined' : 'contained'}
                        color="secondary"
                        onClick={() => handleUserPredict(game.game_id, game.away_team)}
                        disabled={!!messages[game.game_id]}
                        sx={{ minWidth: 60, fontSize: '0.7rem' }}
                      >
                        {game.away_team}
                      </Button>
                    </Box>
                    {messages[game.game_id] && (
                      <Alert
                        severity={messages[game.game_id].type}
                        sx={{ mt: 0.5, py: 0, fontSize: '0.75rem' }}
                      >
                        {messages[game.game_id].text}
                      </Alert>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Alert severity="info" sx={{ mt: 2 }}>
          <AlertTitle>AI의 예측 방식</AlertTitle>
          AI는 단순 통계 비교를 넘어, 과거 수백 경기의 패턴을 학습하여 팀의 컨디션·상대 전력 등을 종합 분석합니다.
          AI가 틀린 경기를 맞추면 더 높은 점수를 얻을 수 있습니다!
        </Alert>
      </CardContent>
    </Card>
  );
}
