// src/components/RankingCard.js
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Typography } from '@mui/material';
import { getWeeklyRanking } from '../api/apiClient';

export default function RankingCard() {
  const [ranking, setRanking] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRanking = async () => {
      setLoading(true);
      try {
        const response = await getWeeklyRanking(5); // Top 5
        setRanking(response.data.ranking);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchRanking();
  }, []);

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          🏆 주간 팬 랭킹 Top 5
        </Typography>
        {loading ? <CircularProgress sx={{ mt: 2 }} /> : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>순위</TableCell>
                  <TableCell>유저 ID</TableCell>
                  <TableCell>주간 점수</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ranking.map((user, index) => (
                  <TableRow key={user.user_id}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell>{user.displayName || user.user_id.substring(0, 8)}</TableCell>
                    <TableCell>{user.weekly_score}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}