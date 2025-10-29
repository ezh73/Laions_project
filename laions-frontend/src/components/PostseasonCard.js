// src/components/PostseasonCard.js
import React from 'react';
import { Card, CardContent, Typography, Box, Alert, Stepper, Step, StepLabel, StepContent } from '@mui/material';

export default function PostseasonCard({ projection }) {
    // 데이터가 없거나, 메시지만 있는 경우 (예: 진출 실패)
    if (!projection || (!projection.samsung_journey_probability && !projection.message)) {
        return <Alert severity="warning">포스트시즌 예측 데이터를 불러올 수 없습니다.</Alert>;
    }

    const { title, message, samsung_journey_probability: journey } = projection;

    return (
        <Card>
            <CardContent>
                <Typography variant="h5" sx={{ mb: 2 }}>
                    {title || '🏆 포스트시즌 여정 예측'}
                </Typography>

                {/* 메시지가 있으면 메시지만 표시 (예: 진출 실패) */}
                {message && (
                    <Alert severity="info" sx={{ mt: 2 }}>{message}</Alert>
                )}

                {/* 포스트시즌 진출 확률 데이터가 있으면 단계별로 표시 */}
                {journey && journey.probabilities && (
                    <Box sx={{ mt: 3 }}>
                        <Stepper orientation="vertical">
                            {Object.entries(journey.probabilities).map(([step, probability]) => (
                                <Step key={step} active={true}>
                                    <StepLabel>
                                        <Typography variant="h6">{step}</Typography>
                                    </StepLabel>
                                    <StepContent>
                                        <Typography variant="h5" color="primary">
                                            {probability}%
                                        </Typography>
                                    </StepContent>
                                </Step>
                            ))}
                        </Stepper>
                    </Box>
                )}
            </CardContent>
        </Card>
    );
}