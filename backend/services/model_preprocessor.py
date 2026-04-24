# backend/services/model_preprocessor.py
import pandas as pd

class ModelPreprocessor:
    @staticmethod
    def preprocess_data(df):
        """
        학습 및 예측에 사용할 데이터 전처리를 수행합니다.
        """
        # 1. 기존 차이값 피처들
        df['elo_diff'] = df['home_elo'] - df['away_elo']
        df['form_diff'] = df['home_form'] - df['away_form']
        df['rd_diff'] = df['home_recent_rd'] - df['away_recent_rd']
        
        # 2. 추가: 상대 득실차의 차이 생성
        df['matchup_rd_diff'] = df['home_matchup_rd'] - df['away_matchup_rd']
        
        # 3. 최종 학습에 사용할 피처 선정
        features = [
            'elo_diff', 'form_diff', 'rd_diff', 
            'matchup_rd_diff',       # 올해 상성
            'season_matchup_count',  # 상성의 데이터 무게
            'home_streak', 'away_streak', 'rest_diff'
        ]
        
        return df[features]
