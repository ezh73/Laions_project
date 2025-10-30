// src/components/QuizCard.js
import React, {useState, useEffect} from 'react';
import { Card, CardContent, Typography, Button, Box, CircularProgress, Alert, RadioGroup, FormControlLabel, Radio, FormControl } from '@mui/material';
import { getQuiz, submitQuiz } from '../api/apiClient';

export default function QuizCard({ user }) {
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [result, setResult] = useState(null);

  const fetchNewQuiz = async () => {
    setLoading(true);
    setResult(null);
    setSelectedAnswer('');
    try {
      const response = await getQuiz();
      setQuiz(response.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNewQuiz();
  }, []);
  
  const handleSubmit = async () => {
    const userId = user.uid;
    const displayName = user.displayName;
    if (!selectedAnswer) {
      setResult({ message: '답을 선택해주세요.', correct: false });
      return;
    }
    
    try {
      const response = await submitQuiz(userId, quiz.quiz_id, selectedAnswer, displayName);
      if (response.data.correct) {
        setResult({ message: `정답입니다! ${response.data.gained_points}포인트 획득!`, correct: true });
      } else {
        setResult({ message: '오답입니다. 아쉽지만 다음 기회에!', correct: false });
      }
    } catch(err) {
      console.error("Quiz submission failed:", err.response ? err.response.data : err.message);
        const detail = err.response?.data?.detail || '정답 제출 중 서버에 문제가 발생했습니다.';
        setResult({ message: `오류: ${detail}`, correct: false });
    }
  };

  // ✅ [핵심 수정] Card의 sx 속성에서 height: '100%'를 제거했습니다.
  return (
    <Card>
      <CardContent>
        <Typography variant="h5">오늘의 삼성 퀴즈</Typography>
        {loading ? <CircularProgress sx={{ mt: 2 }} /> : quiz && (
          <Box sx={{ mt: 2 }}>
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
                <Button variant="contained" onClick={fetchNewQuiz} sx={{ mt: 2 }}>다른 문제 풀기</Button>
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}