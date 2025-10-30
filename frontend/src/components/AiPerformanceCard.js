// src/components/AiPerformanceCard.js

import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, Box, CircularProgress, Alert } from "@mui/material";
import { getAiPerformance, getSimulationReport } from "../api/apiClient";

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
                // 1순위: 비시즌 모드일 경우, 관리자 모드 여부와 상관없이 무조건 일반 API 호출
                if (seasonMode === 'offseason') {
                    response = await getAiPerformance();
                } 
                // 2순위: 비시즌이 아닐 때만 관리자 모드 여부를 따짐
                else {
                    response = isAdminMode
                        ? await getSimulationReport()
                        : await getAiPerformance();
                }
                setPerformance(response.data);

            } catch (err) {
                console.error("AI Performance fetch error:", err);
                setError(err.response?.data?.detail || "서버 응답 오류");
            } finally {
                setLoading(false);
            }
        };

        // seasonMode 값이 정해진 후에 API를 호출하도록 함
        if (seasonMode) {
          fetchPerformance();
        }
    }, [isAdminMode, seasonMode]); // isAdminMode 또는 seasonMode가 바뀔 때마다 다시 실행

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
                    // 관리자 모드이면서 비시즌이 아닐 때 (시뮬레이션 리포트)
                    <Box textAlign="center" p={2}>
                        <Typography variant="body1" color="text.secondary">
                            모드: <strong>시뮬레이션 리포트</strong>
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            전체 경기: {performance.total_games}경기 중{" "}
                            {performance.correct_predictions}적중
                        </Typography>
                        <Typography variant="h5" color="primary" sx={{ mt: 1 }}>
                            <strong>{performance.accuracy?.toFixed(2)}%</strong>
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            ({performance.report_date} 기준)
                        </Typography>
                    </Box>
                ) : performance.mode === "offseason" ? (
                    // 비시즌 (일반 모드 또는 관리자 모드)
                    <Box textAlign="center" p={2}>
                        <Typography variant="body1" color="text.secondary">
                            모델명: <strong>{performance.model_name || "LightGBM (Tuned)"}</strong>
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            검증 기준 정확도: <strong>{performance.model_accuracy || 61.97}%</strong>
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            (시즌 종료 상태)
                        </Typography>
                    </Box>
                ) : (
                    // 시즌 중 / 포스트시즌 (일반 모드)
                    <Box textAlign="center" p={2}>
                        {/* 💡 시즌 첫날처럼 누적 데이터가 없을 때의 UI 처리 */}
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
                                  팀: <strong>{performance.team}</strong>
                                </Typography>
                                <Typography variant="body1" color="text.secondary">
                                  누적 정확도 ({performance.total_games}경기):{" "}
                                  <strong>{performance.total_accuracy?.toFixed(2)}%</strong>
                                </Typography>
                                <Typography variant="body1" color="text.secondary">
                                  최근 {performance.recent_games}경기 정확도:{" "}
                                  <strong>{performance.recent_accuracy?.toFixed(2)}%</strong>
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