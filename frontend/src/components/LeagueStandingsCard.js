// src/components/LeagueStandingsCard.js
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Chip } from '@mui/material';
import { getStandings } from '../api/standingsApi';

const TEAM_COLORS = {
  '삼성': '#0055A5',
  'KIA': '#EA0029',
  'LG': '#C30452',
  'KT': '#000000',
  '두산': '#131230',
  'SSG': '#CE0E2D',
  '롯데': '#041E42',
  '한화': '#FF6600',
  '키움': '#820024',
  'NC': '#1D4E8F'
};

export default function LeagueStandingsCard() {
  const [standings, setStandings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchStandings = async () => {
      try {
        const response = await getStandings();
        setStandings(response.data?.standings || []);
      } catch (err) {
        console.error("Failed to fetch standings:", err);
        setError(err.response?.data?.detail || '순위를 불러올 수 없습니다.');
      } finally {
        setLoading(false);
      }
    };
    fetchStandings();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h5">KBO 리그 순위</Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}><CircularProgress /></Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h5">KBO 리그 순위</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>{error}</Typography>
        </CardContent>
      </Card>
    );
  }

  if (standings.length === 0) return null;

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" gutterBottom>KBO 리그 순위</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold', py: 0.5 }}>순위</TableCell>
                <TableCell sx={{ fontWeight: 'bold', py: 0.5 }}>팀</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>경기</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>승</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>패</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>무</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>승률</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 0.5 }}>게임차</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {standings.map((team) => (
                <TableRow
                  key={team.team_name}
                  sx={{
                    '&:last-child td, &:last-child th': { border: 0 },
                    backgroundColor: team.team_name === '삼성' ? 'rgba(0, 85, 165, 0.05)' : 'inherit'
                  }}
                >
                  <TableCell sx={{ py: 0.5 }}>
                    <Chip
                      label={team.rank}
                      size="small"
                      color={team.rank <= 3 ? 'primary' : team.rank <= 5 ? 'default' : 'default'}
                      variant={team.rank <= 3 ? 'filled' : 'outlined'}
                    />
                  </TableCell>
                  <TableCell sx={{ py: 0.5, fontWeight: team.team_name === '삼성' ? 'bold' : 'normal' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: '50%',
                          backgroundColor: TEAM_COLORS[team.team_name] || '#999',
                          display: 'inline-block'
                        }}
                      />
                      {team.team_name}
                    </Box>
                  </TableCell>
                  <TableCell align="center" sx={{ py: 0.5 }}>{team.games}</TableCell>
                  <TableCell align="center" sx={{ py: 0.5, color: 'success.main' }}>{team.wins}</TableCell>
                  <TableCell align="center" sx={{ py: 0.5, color: 'error.main' }}>{team.losses}</TableCell>
                  <TableCell align="center" sx={{ py: 0.5 }}>{team.draws}</TableCell>
                  <TableCell align="center" sx={{ py: 0.5 }}>{(team.win_rate * 100).toFixed(1)}%</TableCell>
                  <TableCell align="center" sx={{ py: 0.5 }}>{team.game_gap || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
}
