// src/components/SeasonProjectionCard.js
import React from 'react';
import { Card, CardContent, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Alert } from '@mui/material';

// 👈 projection 데이터를 props로 받습니다.
export default function SeasonProjectionCard({ projection }) {
    if (!projection || !projection.ranking_projection) {
        return <Alert severity="warning">시즌 예측 데이터를 불러올 수 없습니다.</Alert>;
    }

    return (
        <Card>
            <CardContent>
                <Typography variant="h5" sx={{ mb: 2 }}>
                    {projection.title || '⚾ 다음 시즌 최종 순위 예측'}
                </Typography>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>예상 순위</TableCell>
                                <TableCell>팀 이름</TableCell>
                                <TableCell>5강 진출 확률</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {/* 👈 백엔드 데이터 키에 맞게 수정 */}
                            {projection.ranking_projection.map((team, index) => (
                                <TableRow key={team.team}>
                                    <TableCell>{index + 1} (평균 {team.avg_rank.toFixed(1)}위)</TableCell>
                                    <TableCell>{team.team}</TableCell>
                                    <TableCell>{team.playoff_probability}%</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </CardContent>
        </Card>
    );
}