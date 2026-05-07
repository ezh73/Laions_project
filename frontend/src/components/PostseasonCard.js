// src/components/PostseasonCard.js
// 포스트시즌 예측 카드 - PredictionCard를 재사용
// isPostseason=true 플래그만 전달하여 동일한 UI 사용
import PredictionCard from './PredictionCard';

export default function PostseasonCard({ user, prediction }) {
  return (
    <PredictionCard
      user={user}
      prediction={prediction}
      isPostseason={true}
    />
  );
}
