// src/pages/Dashboard.js
import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
import { getPrediction, getSeasonProjection, getHealth } from '../api/apiClient';
import '../App.css';

import PredictionCard from '../components/PredictionCard';
import RankingCard from '../components/RankingCard';
import QuizCard from '../components/QuizCard';
import SeasonProjectionCard from '../components/SeasonProjectionCard';
import AiPerformanceCard from '../components/AiPerformanceCard';
// 💡 [새 컴포넌트 추가] 포스트시즌 전용 카드를 가져옵니다.
import PostseasonCard from '../components/PostseasonCard';

export default function Dashboard({ user }) {
    const [seasonMode, setSeasonMode] = useState(null);
    const [cardData, setCardData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const smartFetchData = async () => {
            setLoading(true);
            setError('');
            try {
                // 1. health API로 시즌 모드를 먼저 확인합니다.
                const healthRes = await getHealth();
                const currentMode = healthRes.data.season_mode;
                setSeasonMode(currentMode);

                // 💡 [핵심 수정] 확인된 시즌 모드에 따라 올바른 API를 호출합니다.
                let response;
                if (currentMode === 'season') {
                    // 정규시즌 -> '오늘 경기 예측' API 호출
                    response = await getPrediction();
                } else { // 'postseason' 또는 'offseason'
                    // 포스트시즌/비시즌 -> '전체 여정/순위 예측' API 호출
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
                {/* 💡 [핵심 수정] 각 모드에 맞는 전용 카드를 보여줍니다. */}
                {seasonMode === 'season' && <PredictionCard user={user} prediction={cardData} />}
                {seasonMode === 'postseason' && <PostseasonCard projection={cardData} />}
                {seasonMode === 'offseason' && <SeasonProjectionCard projection={cardData} />}
                
                <QuizCard user={user} />
            </Box>

            {/* --- 우측 열 --- */}
            <Box sx={{ display: 'flex', flexDirection: 'column', flex: '1', gap: 3 }}>
                <AiPerformanceCard />
                <RankingCard />
            </Box>
        </Box>
    );
}