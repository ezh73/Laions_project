// src/pages/Dashboard.js
import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
import { getPrediction } from '../api/predictionApi';
import { getSeasonProjection } from '../api/rankingApi';
import useSystemMode from '../hooks/useSystemMode';
import '../App.css';

import PredictionCard from '../components/PredictionCard';
import RankingCard from '../components/RankingCard';
import QuizCard from '../components/QuizCard';
import SeasonProjectionCard from '../components/SeasonProjectionCard';
import AiPerformanceCard from '../components/AiPerformanceCard';
import PostseasonCard from '../components/PostseasonCard';
import LeagueStandingsCard from '../components/LeagueStandingsCard';

export default function Dashboard({ user }) {
    const { seasonMode, isAdminMode, loading: modeLoading, error: modeError } = useSystemMode();
    const [cardData, setCardData] = useState(null);
    const [dataLoading, setDataLoading] = useState(true);
    const [dataError, setDataError] = useState('');

    useEffect(() => {
        if (!seasonMode) return;

        const fetchCardData = async () => {
            setDataLoading(true);
            setDataError('');
            try {
                let response;
                // 정규시즌과 포스트시즌은 모두 경기 예측 데이터 사용 (동일 API)
                // 오프시즌만 시뮬레이션 순위 예측 데이터 사용
                if (seasonMode === 'offseason') {
                    response = await getSeasonProjection();
                } else {
                    response = await getPrediction();
                }
                setCardData(response.data);
            } catch (err) {
                console.error("Dashboard data fetch failed:", err);
                const detail = err.response?.data?.detail || "데이터를 불러오는 중 오류가 발생했습니다.";
                setDataError(detail);
            } finally {
                setDataLoading(false);
            }
        };

        fetchCardData();
    }, [seasonMode]);

    // 시스템 모드 로딩 중
    if (modeLoading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    }

    // 시스템 모드 에러
    if (modeError) {
        return <Alert severity="error" sx={{ mt: 2 }}>{modeError}</Alert>;
    }

    // 데이터 로딩 중
    if (dataLoading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    }

    // 데이터 에러
    if (dataError) {
        return <Alert severity="error" sx={{ mt: 2 }}>{dataError}</Alert>;
    }

    return (
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
            {/* --- 좌측 열 --- */}
            <Box sx={{ display: 'flex', flexDirection: 'column', flex: '2', gap: 3 }}>
                {seasonMode === 'season' && <PredictionCard user={user} prediction={cardData} />}
                {seasonMode === 'postseason' && <PostseasonCard user={user} prediction={cardData} />}
                {seasonMode === 'offseason' && <SeasonProjectionCard projection={cardData} />}
                
                <QuizCard user={user} />
            </Box>

            {/* --- 우측 열 --- */}
            <Box sx={{ display: 'flex', flexDirection: 'column', flex: '1', gap: 3 }}>
                <AiPerformanceCard isAdminMode={isAdminMode} seasonMode={seasonMode} />
                <RankingCard />
                <LeagueStandingsCard />
            </Box>
        </Box>
    );
}
