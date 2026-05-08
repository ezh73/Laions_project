# backend/stack_service/seed_model.py
"""
최초 모델 학습 스크립트 (1회성)
2021~2025년까지의 수집된 경기 데이터로 초기 LightGBM 모델을 학습합니다.

사용 예:
    cd backend
    python stack_service/seed_model.py

실행 순서:
    1. 피처 재구축 (FeatureService.build_all_features)
    2. 모델 학습 (ModelPipeline.run_pipeline)
    3. lgbm_kbo_predictor_tuned.pkl 파일 생성
"""
import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가 (stack_service에서 실행 시)
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config import engine
from services.feature_service import FeatureService
from services.model_service import ModelPipeline
from services.model_preprocessor import ModelPreprocessor
import joblib
import lightgbm as lgb
import pandas as pd
from sqlalchemy import text


def seed_initial_model():
    """
    최초 모델을 학습합니다.
    
    1. kbo_games 데이터를 기반으로 match_features 재구축
    2. 피처 + 정답 라벨로 LightGBM 모델 학습
    3. lgbm_kbo_predictor_tuned.pkl 저장
    """
    print(f"\n{'='*60}")
    print("🚀 최초 모델 학습 시작")
    print(f"{'='*60}\n")

    # Step 1: 피처 재구축
    print("[1/3] 🔧 피처 재구축...")
    try:
        feature_count = FeatureService.build_all_features()
        print(f"   ✅ 피처 재구축 완료: {feature_count}개 경기")
    except Exception as e:
        print(f"   ❌ 피처 재구축 실패: {e}")
        return False

    # Step 2: 모델 학습
    print("\n[2/3] 🤖 모델 학습...")
    try:
        ModelPipeline.run_pipeline()
        print(f"   ✅ 모델 학습 완료")
    except Exception as e:
        print(f"   ❌ 모델 학습 실패: {e}")
        return False

    # Step 3: 모델 파일 검증
    print("\n[3/3] ✅ 모델 파일 검증...")
    model_path = "lgbm_kbo_predictor_tuned.pkl"
    if os.path.exists(model_path):
        model_size = os.path.getsize(model_path)
        print(f"   ✅ 모델 파일 생성 확인: {model_path} ({model_size / 1024:.1f} KB)")
    else:
        print(f"   ❌ 모델 파일을 찾을 수 없음: {model_path}")
        return False

    print(f"\n{'='*60}")
    print("🎉 최초 모델 학습 완료!")
    print(f"{'='*60}")
    return True


if __name__ == "__main__":
    load_dotenv()
    success = seed_initial_model()
    if not success:
        print("🚨 모델 학습 실패")
        sys.exit(1)
