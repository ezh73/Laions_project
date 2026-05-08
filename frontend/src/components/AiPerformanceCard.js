// src/components/AiPerformanceCard.js

import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, Box, CircularProgress, Alert } from "@mui/material";
import { getAiPerformance } from "../api/performanceApi";

const AiPerformanceCard = ({ seasonMode }) => {
    const [performance, setPerformance] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchPerformance = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await getAiPerformance();
                // API 응답 구조: response.data = {status: "ok", data: {accuracy, total_games, correct_predictions, recent_results}}
                const data = response.data?.data || response.data;
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
    }, [seasonMode]);

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
            </CardContent>
        </Card>
    );
};

export default AiPerformanceCard;
