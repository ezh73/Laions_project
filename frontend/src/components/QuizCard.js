// src/components/QuizCard.js
import React, {useState, useEffect, useCallback} from 'react';
import { Card, CardContent, Typography, Button, Box, CircularProgress, Alert, RadioGroup, FormControlLabel, Radio, FormControl, Chip, ToggleButtonGroup, ToggleButton } from '@mui/material';
import { getQuiz, submitQuiz } from '../api/quizApi';

const DIFFICULTY_LABELS = {
  easy: { label: '쉬움', color: 'success' },
  medium: { label: '중간', color: 'warning' },
  hard: { label: '어려움', color: 'error' }
};

const DAILY_QUIZ_LIMIT = 5;

export default function QuizCard({ user }) {
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [difficulty, setDifficulty] = useState(null);
  const [dailyCount, setDailyCount] = useState(0);

  const fetchNewQuiz = useCallback(async (selectedDifficulty) => {
    setLoading(true);
    setResult(null);
    setSelectedAnswer('');
    setQuiz(null);
    try {
      const diff = selectedDifficulty || difficulty;
      const response = await getQuiz(diff);
      // API 응답: {status: "ok", quiz: {id, question, options, difficulty, source_hint}}
      const quizData = response.data?.quiz || response.data;
      setQuiz(quizData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [difficulty]);

  useEffect(() => {
    fetchNewQuiz();
  }, [fetchNewQuiz]);

  const handleDifficultyChange = (event, newDifficulty) => {
    if (newDifficulty !== null) {
      setDifficulty(newDifficulty);
      fetchNewQuiz(newDifficulty);
    }
  };

  const handleSubmit = async () => {
    const userId = user.id || user.user?.id || user.uid;
    const displayName = user.displayName || user.user?.user_metadata?.full_name;
    if (!selectedAnswer) {
      setResult({ message: '답을 선택해주세요.', correct: false });
      return;
    }
    
    try {
      // API 응답의 quiz.id를 quiz_id로 사용
      const quizId = quiz.id || quiz.quiz_id;
      const response = await submitQuiz(userId, quizId, selectedAnswer, displayName);
      const data = response.data;
      if (data.is_correct) {
        setResult({ message: `정답입니다! ${data.earned_points}포인트 획득!`, correct: true });
      } else {
        setResult({ message: '오답입니다. 아쉽지만 다음 기회에!', correct: false });
      }
      // 서버에서 받은 daily_count로 업데이트
      if (data.daily_count !== undefined) {
        setDailyCount(data.daily_count);
      }
    } catch(err) {
      console.error("Quiz submission failed:", err.response ? err.response.data : err.message);
        const detail = err.response?.data?.detail || '정답 제출 중 서버에 문제가 발생했습니다.';
        setResult({ message: `오류: ${detail}`, correct: false });
    }
  };

  const currentDifficulty = quiz?.difficulty || difficulty;
  const diffInfo = DIFFICULTY_LABELS[currentDifficulty] || {};
  const remainingQuizzes = DAILY_QUIZ_LIMIT - dailyCount;

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h5">오늘의 삼성 퀴즈</Typography>
          <Chip
            label={`남은 횟수 ${remainingQuizzes}/${DAILY_QUIZ_LIMIT}`}
            color={remainingQuizzes > 0 ? 'primary' : 'error'}
            size="small"
            variant="outlined"
          />
        </Box>

        {/* 난이도 선택 토글 버튼 */}
        <ToggleButtonGroup
          value={difficulty}
          exclusive
          onChange={handleDifficultyChange}
          size="small"
          sx={{ mb: 2 }}
          disabled={loading || result !== null}
        >
          <ToggleButton value="easy">쉬움 (5P)</ToggleButton>
          <ToggleButton value="medium">중간 (10P)</ToggleButton>
          <ToggleButton value="hard">어려움 (20P)</ToggleButton>
        </ToggleButtonGroup>

        {loading ? <CircularProgress sx={{ mt: 2 }} /> : quiz && (
          <Box sx={{ mt: 2 }}>
            {/* 난이도 표시 칩 */}
            {diffInfo.label && (
              <Chip
                label={`난이도: ${diffInfo.label}`}
                color={diffInfo.color}
                size="small"
                sx={{ mb: 1 }}
              />
            )}
            <Typography variant="body1" sx={{ minHeight: '3em' }}>{quiz.question}</Typography>
            <FormControl sx={{ my: 1 }}>
              <RadioGroup value={selectedAnswer} onChange={(e) => setSelectedAnswer(e.target.value)}>
                {quiz.options.map((option, index) => (
                  <FormControlLabel key={index} value={option} control={<Radio size="small" />} label={option} disabled={result !== null} />
                ))}
              </RadioGroup>
            </FormControl>
            
            {result === null ? (
              <Button variant="contained" onClick={handleSubmit}>정답 제출</Button>
            ) : (
              <Box>
                <Alert severity={result.correct ? 'success' : 'error'}>{result.message}</Alert>
                {remainingQuizzes > 1 && (
                  <Button variant="contained" onClick={() => fetchNewQuiz()} sx={{ mt: 2 }}>
                    다른 문제 풀기
                  </Button>
                )}
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
