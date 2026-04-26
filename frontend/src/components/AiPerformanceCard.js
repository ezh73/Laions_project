// src/components/AiPerformanceCard.js

import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, Box, CircularProgress, Alert } from "@mui/material";
import { getAiPerformance, getSimulationReport } from "../api/performanceApi";

const AiPerformanceCard = ({ isAdminMode, seasonMode }) => {
    const [performance, setPerformance] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchPerformance = async () => {
            setLoading(true);
            setError(null);
            try {
                let response;
                if (seasonMode === 'offseason') {
                    response = await getAiPerformance();
                } else {
                    response = isAdminMode
                        ? await getSimulationReport()
                        : await getAiPerformance();
                }
                // API 응답 구조 통일: response.data 아래에 실제 데이터
                // getAiPerformance: {status: "ok", data: {accuracy, total_games, correct_predictions, recent_results}}
                // getSimulationReport: {status: "ok", report: {projections, summary, admin_mode, current_date}}
                const data = response.data?.data || response.data?.report || response.data;
                setPerformance(data);

            } catch (err) {
                console.error("AI Performance fetch error:", err);
                setError(err.response?.data?.detail || "서버 응답 오류");
            } finally {
                setLoading(false);
            }
        };

        if (seasonMode) {
          fetchPerformance();
        }
    }, [isAdminMode, seasonMode]);

    if (loading) {
        return (
            <Card sx={{ height: "100%" }}>
                <CardContent sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200 }}>
                    <CircularProgress />
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card sx={{ height: "100%" }}>
                <CardContent>
                    <Alert severity="error">{error}</Alert>
                </CardContent>
            </Card>
        );
    }

    if (!performance) return null;

    return (
        <Card sx={{ height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <CardContent>
                <Typography variant="h6" gutterBottom align="center">
                    🤖 AI 예측 정확도
                </Typography>
                
                {isAdminMode && seasonMode !== 'offseason' ? (
                    // 시뮬레이션 리포트 모드 (관리자)
                    <Box textAlign="center" p={2}>
                        <Typography variant="body1" color="text.secondary">
                            모드: <strong>시뮬레이션 리포트</strong>
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            {performance.summary || "시뮬레이션 완료"}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            ({performance.current_date || ""} 기준)
                        </Typography>
                    </Box>
                ) : (
                    // 일반 AI 성능 모드
                    <Box textAlign="center" p={2}>
                        {performance.total_games === 0 ? (
                            <>
                                <Typography variant="body1" color="text.secondary">
                                  <strong>아직 누적된 경기 기록이 없습니다.</strong>
                                </Typography>
                                <Typography variant="body1" color="text.secondary">
                                  모델 기본 정확도: <strong>61.97%</strong>
                                </Typography>
                            </>
                        ) : (
                            <>
                                <Typography variant="body1" color="text.secondary">
                                  누적 정확도 ({performance.total_games}경기):{" "}
                                  <strong>{performance.accuracy?.toFixed(1)}%</strong>
                                </Typography>
                                <Typography variant="body1" color="text.secondary">
                                  ({performance.correct_predictions}적중 / {performance.total_games}경기)
                                </Typography>
                            </>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};

export default AiPerformanceCard;
