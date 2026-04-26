// src/components/SeasonProjectionCard.js
import React from 'react';
import { Card, CardContent, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Alert } from '@mui/material';

export default function SeasonProjectionCard({ projection }) {
    // API 응답: {status: "ok", data: [{team, expected_win_rate, expected_wins, predicted_rank}, ...]}
    const rankings = projection?.data || [];

    if (!rankings || rankings.length === 0) {
        return <Alert severity="warning">시즌 예측 데이터를 불러올 수 없습니다.</Alert>;
    }

    return (
        <Card>
            <CardContent>
                <Typography variant="h5" sx={{ mb: 2 }}>
                    ⚾ 다음 시즌 최종 순위 예측
                </Typography>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 'bold' }}>예상 순위</TableCell>
                                <TableCell sx={{ fontWeight: 'bold' }}>팀 이름</TableCell>
                                <TableCell sx={{ fontWeight: 'bold' }}>예상 승률</TableCell>
                                <TableCell sx={{ fontWeight: 'bold' }}>예상 승수</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rankings.map((team, index) => (
                                <TableRow key={team.team}>
                                    <TableCell>{team.predicted_rank || index + 1}</TableCell>
                                    <TableCell>{team.team}</TableCell>
                                    <TableCell>{(team.expected_win_rate * 100).toFixed(1)}%</TableCell>
                                    <TableCell>{team.expected_wins}승</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </CardContent>
        </Card>
    );
}