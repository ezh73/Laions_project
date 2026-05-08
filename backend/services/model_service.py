# backend/services/model_service.py
import os
import joblib
import pandas as pd
import lightgbm as lgb
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from config import engine, CURRENT_DATE, FEATURE_CONFIG, SEASON_MODE, get_season_mode
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
    def predict_all_games(cls, conn=None):
        """
        오늘 이후 경기의 승패를 예측합니다.
        
        Args:
            conn: 외부 트랜잭션 connection (관리자 모드용). None이면 자체 트랜잭션 사용.
        """
        model = cls.get_model()
        if not model:
            return []

        predictions = []

        # 1. 오늘(또는 관리자 모드 설정 날짜)의 일정 가져오기 + 각 경기 피처 조회 (단일 connection 재사용)
        with engine.connect() as read_conn:
            query = text(f"""
                SELECT game_id, game_date, home_team, away_team
                FROM kbo_schedule
                WHERE game_date = :today
                ORDER BY game_date ASC
            """)
            schedules = pd.read_sql(query, read_conn, params={"today": CURRENT_DATE})

            if schedules.empty:
                return []

            for _, row in schedules.iterrows():
                gid, gdate, home, away = row['game_id'], row['game_date'], row['home_team'], row['away_team']
                
                # 2. 각 팀의 최신 피처 가져오기 (같은 read_conn 재사용)
                f_query = text(f"""
                    SELECT * FROM match_features
                    WHERE game_id = :gid
                """)
                features = pd.read_sql(f_query, read_conn, params={"gid": gid})

                if features.empty:
                    continue

                # 3. 모델 입력 포맷팅
                X = ModelPreprocessor.preprocess_data(features)

                # 4. 예측 수행
                prob = model.predict_proba(X)[0] # [원정승 확률, 홈승 확률]
                home_win_prob = float(prob[1])
                predicted_winner = home if home_win_prob > 0.5 else away
                winner_prob = home_win_prob if home_win_prob > 0.5 else (1 - home_win_prob)

                # 5. DB 저장 (conn이 있을 때는 외부 트랜잭션 사용, 없으면 자체 트랜잭션)
                if conn:
                    conn.execute(text(f"""
                        INSERT INTO ai_predictions (game_id, game_date, predicted_winner, prediction_prob)
                        VALUES (:gid, :gdate, :winner, :prob)
                        ON CONFLICT (game_id) DO UPDATE SET
                            predicted_winner = EXCLUDED.predicted_winner,
                            prediction_prob = EXCLUDED.prediction_prob
                    """), {"gid": gid, "gdate": gdate, "winner": predicted_winner, "prob": winner_prob})
                else:
                    with engine.begin() as write_conn:
                        write_conn.execute(text(f"""
                            INSERT INTO ai_predictions (game_id, game_date, predicted_winner, prediction_prob)
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
            FROM match_features m
            JOIN kbo_games g ON m.game_id = g.game_id
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
        
        # 2. 학습 데이터 범위 설정 (전체 데이터 사용, 검증셋 분리 없음)
        #    - 모든 가용 데이터를 학습에 사용 (2021년 ~ 현재까지)
        #    - 검증셋을 분리하지 않는 이유: 더 많은 데이터로 모델 성능 향상
        #    - 필요 시 2020년 데이터를 검증셋으로 활용 가능
        current_year = CURRENT_DATE.year
        season_mode = get_season_mode()
        
        if season_mode == "offseason":
            # 오프시즌: 2021 ~ 당해 시즌 전체 데이터로 재학습
            df_to_train = raw_df[raw_df['game_date'].dt.year <= current_year]
            print(f"🔄 오프시즌 재학습: 2021~{current_year}년 데이터 ({len(df_to_train)}건)")
        else:
            # 시즌 중: 2021 ~ 현재까지 전체 데이터로 학습
            # (당해 시즌 데이터도 포함하여 더 많은 학습 데이터 확보)
            df_to_train = raw_df[raw_df['game_date'].dt.year <= current_year]
            print(f"🔄 시즌 중 학습: 2021~{current_year}년 전체 데이터 ({len(df_to_train)}건)")

        if df_to_train.empty:
            raise ValueError("❌ 학습할 데이터가 없습니다. 최소 2021년 이후 데이터가 필요합니다.")

        X_train = ModelPreprocessor.preprocess_data(df_to_train)
        y_train = df_to_train["home_team_win"]
        
        # 3. LightGBM 모델 세팅 및 학습
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

        # 4. 모델 성능 메트릭 로깅 (학습 데이터 기준)
        train_score = model.score(X_train, y_train)
        print(f"📊 모델 학습 정확도: {train_score:.4f}")
        
        # 5. 피처 중요도 출력
        feature_names = ModelPreprocessor.preprocess_data(df_to_train).columns.tolist()
        importances = model.feature_importances_
        for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
            print(f"   📌 {name}: {imp:.1f}")

        # 6. 모델 저장
        joblib.dump(model, MODEL_PATH)
        print(f"✅ 모델 저장 완료: {MODEL_PATH}")

@router.get("/all")
def get_all_predictions():
    """오늘 이후 경기에 대한 AI 예측 결과를 반환합니다."""
    preds = ModelService.predict_all_games()
    return {"status": "ok", "predictions": preds}

@router.post("/retrain")
def run_retrain():
    """모델을 재학습합니다."""
    ModelService.retrain_model()
    return {"status": "ok", "message": "모델 재학습 완료"}
