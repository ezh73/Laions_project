// src/api/quizApi.js
// 퀴즈 관련 API
import apiClient from './apiClient';

// 퀴즈 가져오기 (difficulty: easy / medium / hard, 생략 시 전체)
export const getQuiz = (difficulty) => {
    const params = {};
    if (difficulty) params.difficulty = difficulty;
    return apiClient.get('/api/quiz', { params });
};

// 퀴즈 정답 제출하기
export const submitQuiz = (userId, quizId, answer, displayName) => apiClient.post('/api/quiz/submit', null, {
    params: { user_id: userId, quiz_id: quizId, answer: answer, display_name: displayName }
});
