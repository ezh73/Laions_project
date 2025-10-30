// src/components/SeasonProjectionCard.js
import React from 'react';
import { Card, CardContent, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Alert } from '@mui/material';

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
                                <TableCell sx={{ fontWeight: 'bold' }}>예상 순위</TableCell>
                                <TableCell sx={{ fontWeight: 'bold' }}>팀 이름</TableCell>
                                {/* ✨ [수정] 헤더를 '예상 성적'으로 변경 */}
                                <TableCell sx={{ fontWeight: 'bold' }}>예상 성적</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {projection.ranking_projection.map((team, index) => (
                                <TableRow key={team.team}>
                                    {/* ✨ [수정] 불필요한 평균 순위 텍스트 제거 */}
                                    <TableCell>{index + 1}</TableCell>
                                    <TableCell>{team.team}</TableCell>
                                    {/* ✨ [수정] '예상 승수'와 '예상 패수'를 함께 표시 */}
                                    <TableCell>{Math.round(team.avg_wins)}승 {Math.round(team.avg_losses)}패</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </CardContent>
        </Card>
    );
}