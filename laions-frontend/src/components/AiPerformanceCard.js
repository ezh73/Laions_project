// src/components/AiPerformanceCard.js

import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, Box, CircularProgress, Alert } from "@mui/material";
import { getAiPerformance } from "../api/apiClient"; // 👈 apiClient에서 함수 가져오기

const AiPerformanceCard = () => {
  const [performance, setPerformance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPerformance = async () => {
      try {
        const res = await getAiPerformance(); // 👈 apiClient 함수 사용
        setPerformance(res.data);
      } catch (err) {
        console.error("AI Performance fetch error:", err);
        setError(err.response?.data?.detail || "서버 응답 오류");
      } finally {
        setLoading(false);
      }
    };
    fetchPerformance();
  }, []);

  if (loading) {
    return (
      <Card sx={{ height: "100%" }}>
        <CardContent
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: 200,
          }}
        >
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
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
      }}
    >
      <CardContent>
        {/* 제목 */}
        <Typography variant="h6" gutterBottom align="center">
          🤖 AI 예측 정확도
        </Typography>

        {/* 시즌 상태별 부제 */}
        <Typography
          variant="subtitle2"
          color="text.secondary"
          gutterBottom
          align="center"
        >
          {performance.mode === "season" && "⚾ 정규시즌 예측"}
          {performance.mode === "postseason" && "🏆 포스트시즌 예측"}
          {performance.mode === "offseason" && "📈 내년 순위 예측"}
        </Typography>

        {/* 비시즌: 모델 학습 정확도 표시 */}
        {performance.mode === "offseason" ? (
          <Box textAlign="center" p={2}>
            <Typography variant="body1" color="text.secondary">
              모델명: <strong>{performance.model_name || "LightGBM (Tuned)"}</strong>
            </Typography>
            <Typography variant="body1" color="text.secondary">
              검증 기준 정확도:{" "}
              <strong>{performance.model_accuracy || 61.97}%</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              (데이터 없음 — 시즌 개막 전 상태)
            </Typography>
          </Box>
        ) : (
          // 시즌 중 / 포스트시즌: 실제 경기 예측 적중률 표시
          <Box textAlign="center" p={2}>
            <Typography variant="body1" color="text.secondary">
              팀: <strong>{performance.team}</strong>
            </Typography>
            <Typography variant="body1" color="text.secondary">
              전체 경기: {performance.total_games}경기 중{" "}
              {performance.total_correct}적중
            </Typography>
            <Typography variant="body1" color="text.secondary">
              누적 정확도:{" "}
              <strong>{performance.total_accuracy?.toFixed(2)}%</strong>
            </Typography>
            <Typography variant="body1" color="text.secondary">
              최근 {performance.recent_games}경기 정확도:{" "}
              <strong>{performance.recent_accuracy?.toFixed(2)}%</strong>
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default AiPerformanceCard;
