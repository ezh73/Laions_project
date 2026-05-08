# backend/services/model_preprocessor.py
import pandas as pd
from config import FEATURE_CONFIG

class ModelPreprocessor:
    # home_* / away_* 쌍으로 구성된 피처 → _diff 변환 규칙
    _DIFF_PAIRS = {
        "elo": ("home_elo", "away_elo"),
        "form": ("home_form", "away_form"),
        "rd": ("home_recent_rd", "away_recent_rd"),
        "matchup_rd": ("home_matchup_rd", "away_matchup_rd"),
    }

    @classmethod
    def _get_diff_features(cls):
        """FEATURE_CONFIG.numerical을 기반으로 _diff 피처 목록을 동적으로 생성합니다."""
        numerical = set(FEATURE_CONFIG.get("numerical", []))
        diff_features = []
        for diff_name, (home_col, away_col) in cls._DIFF_PAIRS.items():
            if home_col in numerical and away_col in numerical:
                diff_features.append(f"{diff_name}_diff")
        return diff_features

    @classmethod
    def _get_raw_features(cls):
        """FEATURE_CONFIG.numerical에서 _diff로 변환되지 않는 단일 컬럼 피처를 반환합니다."""
        numerical = set(FEATURE_CONFIG.get("numerical", []))
        # _diff 쌍에 포함된 home/away 컬럼 제외
        paired_cols = set()
        for home_col, away_col in cls._DIFF_PAIRS.values():
            paired_cols.add(home_col)
            paired_cols.add(away_col)
        return [col for col in numerical if col not in paired_cols]

    @classmethod
    def preprocess_data(cls, df):
        """
        학습 및 예측에 사용할 데이터 전처리를 수행합니다.
        FEATURE_CONFIG.numerical을 기반으로 동적으로 피처를 생성합니다.
        """
        # 1. home/away 쌍 피처 → _diff 차이값 생성
        for diff_name, (home_col, away_col) in cls._DIFF_PAIRS.items():
            if home_col in df.columns and away_col in df.columns:
                df[f"{diff_name}_diff"] = df[home_col] - df[away_col]

        # 2. 최종 학습에 사용할 피처 선정 (동적 생성)
        features = cls._get_diff_features() + cls._get_raw_features()
        
        # 3. df에 실제로 존재하는 컬럼만 필터링
        available = [f for f in features if f in df.columns]
        return df[available]
