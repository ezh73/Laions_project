// src/components/SimulationResultCard.js
import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, Box, CircularProgress, Alert, Divider } from "@mui/material";
import { getSimulationReport } from "../api/apiClient";

const SimulationResultCard = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await getSimulationReport();
        setReport(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || "시뮬레이션 리포트를 불러올 수 없습니다.");
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, []);

  if (loading) {
    return (
      <Card><CardContent><CircularProgress /></CardContent></Card>
    );
  }

  if (error) {
    return (
      <Card><CardContent><Alert severity="warning">{error}</Alert></CardContent></Card>
    );
  }

  return (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          AI 예측 시뮬레이션 리포트
        </Typography>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          분석 기준일: {report.report_date}
        </Typography>
        <Divider sx={{ my: 2 }} />
        <Box textAlign="center">
          <Typography>
            총 분석 경기: <strong>{report.total_games}</strong> 경기
          </Typography>
          <Typography>
            AI 예측 성공: <strong>{report.correct_predictions}</strong> 경기
          </Typography>
          <Typography variant="h5" mt={1} color="primary.main">
            누적 정확도: <strong>{report.accuracy}%</strong>
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default SimulationResultCard;