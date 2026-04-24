# backend/services/model_service.py
import os
import joblib
import pandas as pd
import lightgbm as lgb
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from config import engine, CURRENT_DATE, FEATURE_CONFIG, SEASON_MODE, TABLE_AI_PREDICTIONS, TABLE_KBO_SCHEDULE, TABLE_KBO_GAMES, TABLE_MATCH_FEATURES, get_season_mode
from auth_utils import verify_admin_api_key
from services.feature_service import FeatureService
from services.model_preprocessor import ModelPreprocessor

router = APIRouter(prefix="/api/model", tags=["model"])

MODEL_PATH = "lgbm_kbo_predictor_tuned.pkl"

class ModelService:
    _model = None

    @classmethod
    def get_model(cls):
        """지연 로딩(Lazy Loading) 방식으로 모델을 불러옵니다."""
        if cls._model is None:
            if os.path.exists(MODEL_PATH):
                cls._model = joblib.load(MODEL_PATH)
            else:
                print(f"⚠️ 모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
        return cls._model

    @classmethod
    def retrain_model(cls):
        """모델을 재학습하고 메모리의 모델 객체를 갱신합니다."""
        # 1. 피처 재구성(rebuild) 수행
        FeatureService.build_all_features()
        # 2. 모델 파이프라인(학습) 수행
        ModelPipeline.run_pipeline()
        # 3. 메모리의 모델 객체 갱신
        cls._model = joblib.load(MODEL_PATH)
        return True

    @classmethod
    def predict_all_games(cls):
        """저장된 모든 일정의 경기 승패를 예측합니다."""
        model = cls.get_model()
        if not model:
            return []

        # 1. 모든 일정 가져오기
        with engine.connect() as conn:
            query = text(f"""
                SELECT game_id, game_date, home_team, away_team 
                FROM {TABLE_KBO_SCHEDULE}
            """)
            schedules = pd.read_sql(query, conn)

        if schedules.empty:
            return []

        predictions = []
        for _, row in schedules.iterrows():
            gid, gdate, home, away = row['game_id'], row['game_date'], row['home_team'], row['away_team']
            
            # 2. 각 팀의 최신 피처 가져오기
            with engine.connect() as conn:
                f_query = text(f"""
                    SELECT * FROM {TABLE_MATCH_FEATURES} 
                    WHERE game_id = :gid
                """)
                features = pd.read_sql(f_query, conn, params={"gid": gid})

            if features.empty:
                continue

            # 3. 모델 입력 포맷팅
            X = ModelPreprocessor.preprocess_data(features)

            # 4. 예측 수행
            prob = model.predict_proba(X)[0] # [원정승 확률, 홈승 확률]
            home_win_prob = float(prob[1])
            predicted_winner = home if home_win_prob > 0.5 else away
            winner_prob = home_win_prob if home_win_prob > 0.5 else (1 - home_win_prob)

            # 5. DB 저장 (ai_predictions)
            with engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {TABLE_AI_PREDICTIONS} (game_id, game_date, predicted_winner, prediction_prob)
                    VALUES (:gid, :gdate, :winner, :prob)
                    ON CONFLICT (game_id) DO UPDATE SET
                        predicted_winner = EXCLUDED.predicted_winner,
                        prediction_prob = EXCLUDED.prediction_prob
                """), {"gid": gid, "gdate": gdate, "winner": predicted_winner, "prob": winner_prob})

            predictions.append({
                "game_id": gid,
                "home_team": home,
                "away_team": away,
                "predicted_winner": predicted_winner,
                "probability": round(winner_prob, 2)
            })

        return predictions

class ModelPipeline:
    @staticmethod
    def load_data_from_db():
        """DB에서 피처(match_features)와 정답 라벨(kbo_games의 경기 결과)을 조인하여 가져옵니다."""
        # 무승부는 모델 학습에 혼선을 주므로 제외합니다.
        query = text(f"""
            SELECT 
                m.game_id, m.game_date,
                m.home_team, m.away_team,
                m.home_elo, m.away_elo,
                m.home_form, m.away_form,
                m.home_streak, m.away_streak,
                m.home_pythagorean, m.away_pythagorean,
                m.home_recent_rd, m.away_recent_rd,
                m.home_matchup_rd, m.away_matchup_rd,
                m.season_matchup_count,
                m.rest_diff,
                CASE 
                    WHEN g.winning_team = m.home_team THEN 1
                    WHEN g.winning_team = m.away_team THEN 0
                END as home_team_win
            FROM {TABLE_MATCH_FEATURES} m
            JOIN {TABLE_KBO_GAMES} g ON m.game_id = g.game_id
            WHERE g.winning_team IS NOT NULL 
              AND g.winning_team != '무승부'
            ORDER BY m.game_date ASC, m.game_id ASC
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        if df.empty:
            raise ValueError("❌ 학습할 데이터가 DB에 없습니다.")
        
        return df

    @classmethod
    def run_pipeline(cls):
        # 1. 데이터 로드 및 전처리
        raw_df = cls.load_data_from_db()
        
        # 오프시즌 여부에 따른 데이터 범위 설정
        season_mode = get_season_mode()
        if season_mode != "offseason":
            # 2025년 시즌 데이터까지만 학습 (2026년 1월 1일 이전)
            df_to_train = raw_df[raw_df['game_date'] < datetime(2026, 1, 1).date()]
        else:
            # 오프시즌인 경우 전체 데이터 사용
            df_to_train = raw_df

        X_train = ModelPreprocessor.preprocess_data(df_to_train)
        y_train = df_to_train["home_team_win"]
        
        # 2. LightGBM 모델 세팅 및 학습
        model = lgb.LGBMClassifier(
            n_estimators=500,
            learning_rate=0.01,
            max_depth=4,
            num_leaves=16,
            min_child_samples=20,
            random_state=42,
            importance_type='gain'
        )
        
        model.fit(X_train, y_train)

        # 3. 모델 저장
        joblib.dump(model, MODEL_PATH)

@router.get("/all")
def get_all_predictions():
    """모든 경기에 대한 AI 예측 결과를 반환합니다."""
    preds = ModelService.predict_all_games()
    return {"status": "ok", "predictions": preds}

@router.post("/retrain")
def run_retrain():
    """모델을 재학습합니다."""
    ModelService.retrain_model()
    return {"status": "ok", "message": "모델 재학습 완료"}
