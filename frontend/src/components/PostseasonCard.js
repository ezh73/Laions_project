// src/components/PostseasonCard.js
// 포스트시즌 대진표 + 경기 예측 + 다음 시리즈 진출 예측 통합 카드
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
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { submitUserPrediction } from '../api/predictionApi';

// 시리즈별 색상 매핑
const SERIES_COLORS = {
  wildcard: { bg: '#e3f2fd', border: '#1565c0', label: '와일드카드 결정전' },
  semifinal: { bg: '#e8f5e9', border: '#2e7d32', label: '준플레이오프' },
  final: { bg: '#fff3e0', border: '#e65100', label: '플레이오프' },
  ks: { bg: '#fce4ec', border: '#c62828', label: '한국시리즈' },
};

export default function PostseasonCard({ user, prediction, bracket }) {
  const [messages, setMessages] = useState({});

  // prediction: AI 예측 결과 (getPrediction 응답)
  // bracket: 포스트시즌 대진표 데이터 (getPostseasonBracket 응답)
  const games = prediction?.predictions || [];
  const seriesList = bracket?.series || [];
  const nextSeriesPrediction = bracket?.next_series_prediction || [];

  const handleUserPredict = async (gameId, predictedWinner) => {
    try {
      const userId = user.id || user.user?.id || user.uid;
      const response = await submitUserPrediction(userId, gameId, predictedWinner);
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

  // 시리즈 상태 Chip 렌더링
  const renderStatusChip = (status) => {
    const statusMap = {
      completed: { label: '완료', color: 'success' },
      in_progress: { label: '진행 중', color: 'warning' },
      upcoming: { label: '예정', color: 'default' },
    };
    const info = statusMap[status] || { label: status, color: 'default' };
    return <Chip label={info.label} color={info.color} size="small" />;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* ===== 섹션 1: 포스트시즌 대진표 ===== */}
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            🏆 포스트시즌 대진표
          </Typography>

          {seriesList.length === 0 ? (
            <Alert severity="info">포스트시즌 대진표 데이터를 불러올 수 없습니다.</Alert>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2, alignItems: 'stretch' }}>
              {seriesList.map((series) => {
                const colors = SERIES_COLORS[series.key] || { bg: '#f5f5f5', border: '#9e9e9e', label: series.name };
                return (
                  <Box
                    key={series.key}
                    sx={{
                      flex: 1,
                      border: `2px solid ${colors.border}`,
                      borderRadius: 2,
                      bgcolor: colors.bg,
                      p: 2,
                      minWidth: { xs: '100%', md: 0 },
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: colors.border }}>
                        {colors.label}
                      </Typography>
                      {renderStatusChip(series.status)}
                    </Box>

                    {/* 시리즈 참가팀 */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      {series.teams.map((team, idx) => (
                        <React.Fragment key={team}>
                          <Chip
                            label={team}
                            size="small"
                            color={series.winner === team ? 'success' : 'default'}
                            variant={series.winner === team ? 'filled' : 'outlined'}
                          />
                          {idx < series.teams.length - 1 && (
                            <Typography variant="body2" color="text.secondary">vs</Typography>
                          )}
                        </React.Fragment>
                      ))}
                    </Box>

                    {/* 시리즈 진행 상황 */}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      {series.completed_games} / {series.total_games}경기 완료
                    </Typography>

                    {/* 팀별 승수 */}
                    {Object.keys(series.team_wins || {}).length > 0 && (
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                        {Object.entries(series.team_wins).map(([team, wins]) => (
                          <Chip
                            key={team}
                            label={`${team}: ${wins}승`}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.7rem' }}
                          />
                        ))}
                      </Box>
                    )}

                    {/* 시리즈 승자 */}
                    {series.winner && (
                      <Alert severity="success" sx={{ py: 0, fontSize: '0.8rem' }}>
                        ✅ <strong>{series.winner}</strong> 시리즈 승리!
                      </Alert>
                    )}

                    {/* AI 예측 (승자 미정 시) */}
                    {!series.winner && series.predicted_winner && (
                      <Alert severity="info" sx={{ py: 0, fontSize: '0.8rem' }}>
                        🤖 AI 예측: <strong>{series.predicted_winner.team}</strong> (확률: {(series.predicted_winner.probability * 100).toFixed(1)}%)
                      </Alert>
                    )}
                  </Box>
                );
              })}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* ===== 섹션 2: 다음 시리즈 진출 예측 ===== */}
      {nextSeriesPrediction.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              🔮 다음 시리즈 진출 예측
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {nextSeriesPrediction.map((pred, idx) => (
                <Alert key={idx} severity="info" icon={false} sx={{ fontSize: '0.9rem' }}>
                  <Typography variant="body2">
                    {pred.description}
                  </Typography>
                  {pred.predicted_matchup && pred.predicted_matchup.length > 0 && (
                    <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Typography variant="caption" color="text.secondary">예상 진출팀: </Typography>
                      {pred.predicted_matchup.map((team) => (
                        <Chip key={team} label={team} size="small" color="primary" variant="outlined" />
                      ))}
                    </Box>
                  )}
                </Alert>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* ===== 섹션 3: 오늘의 경기 승리 예측 ===== */}
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
            ⚾ 오늘의 경기 예측
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            총 {games.length}개 경기 예측
          </Typography>

          {games.length === 0 ? (
            <Alert severity="warning">오늘 예정된 포스트시즌 경기가 없습니다.</Alert>
          ) : (
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
          )}

          <Alert severity="info" sx={{ mt: 2 }}>
            <AlertTitle>AI의 예측 방식</AlertTitle>
            AI는 정규시즌 전체 경기를 학습하여 포스트시즌 각 시리즈의 승자를 예측합니다.
            AI가 틀린 경기를 맞추면 더 높은 점수를 얻을 수 있습니다!
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
}
