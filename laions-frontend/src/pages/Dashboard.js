// src/pages/Dashboard.js
import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
// 필요한 API 함수들을 모두 가져옵니다.
import { getPrediction, getSeasonProjection, getHealth } from '../api/apiClient';

import PredictionCard from '../components/PredictionCard';
import RankingCard from '../components/RankingCard';
import QuizCard from '../components/QuizCard';
import SeasonProjectionCard from '../components/SeasonProjectionCard';
import AiPerformanceCard from '../components/AiPerformanceCard';
import SimulationResultCard from '../components/SimulationResultCard'; // 새로 만든 카드 import

export default function Dashboard({ user }) {
  const [seasonMode, setSeasonMode] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isAdminMode, setIsAdminMode] = useState(false); // ✅ 관리자 모드 상태 추가
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const smartFetchData = async () => {
      setLoading(true);
      setError('');
      try {
        // 1. health API로 시즌 모드와 관리자 모드 상태를 함께 확인합니다.
        const healthRes = await getHealth();
        const currentMode = healthRes.data.season_mode;
        const adminStatus = healthRes.data.admin_mode; // ✅ 관리자 모드 상태 가져오기
        
        setSeasonMode(currentMode);
        setIsAdminMode(adminStatus); // ✅ 관리자 모드 상태 설정

        // 2. 확인된 시즌 모드에 따라 필요한 API 딱 하나만 호출합니다.
        let response;
        if (currentMode === 'season' || currentMode === 'postseason') {
          response = await getPrediction();
        } else { // offseason
          response = await getSeasonProjection();
        }
        setCardData(response.data);

      } catch (err) {
        console.error("Dashboard data fetch failed:", err);
        const detail = err.response?.data?.detail || "데이터를 불러오는 중 오류가 발생했습니다.";
        setError(detail);
      } finally {
        setLoading(false);
      }
    };

    smartFetchData();
  }, []);

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
  }

  if (error) {
    return <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
      {/* --- 좌측 열 --- */}
      <Box sx={{ display: 'flex', flexDirection: 'column', flex: '2', gap: 3 }}>
        {(seasonMode === 'season' || seasonMode === 'postseason') && (
          <PredictionCard user={user} prediction={cardData} />
        )}
        {seasonMode === 'offseason' && (
          <SeasonProjectionCard projection={cardData} />
        )}
        <QuizCard user={user} />
      </Box>

      {/* --- 우측 열 --- */}
      <Box sx={{ display: 'flex', flexDirection: 'column', flex: '1', gap: 3 }}>
        {/* ✅ [핵심 수정] 관리자 모드 여부에 따라 다른 성능 카드를 보여줍니다. */}
        {isAdminMode ? <SimulationResultCard /> : <AiPerformanceCard />}
        <RankingCard />
      </Box>
    </Box>
  );
}