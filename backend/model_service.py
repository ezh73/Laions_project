# backend/model_service.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text
import pandas as pd
import joblib
import os
from datetime import datetime, date
from dotenv import load_dotenv

# ⚙️ config.py에서 핵심 설정값들을 가져옵니다.
from config import ADMIN_MODE, CURRENT_DATE, SEASON_MODE, DATA_SOURCE

#  Firestore 클라이언트(db_fs)는 main.py에서 초기화된 후 사용됩니다.
# 아래 코드에서는 타입 힌팅 등을 위해 임포트하는 것처럼 처리할 수 있습니다.
try:
    from main import db_fs
except ImportError:
    db_fs = None

router = APIRouter()

MODEL_PATH = "lgbm_kbo_predictor_tuned.pkl"
model = None  # 전역 변수, main.py의 startup 이벤트에서 모델 파일이 로드됩니다.

# DB 연결 설정
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')


# ======================================================
# 💾 사용자 예측 저장 로직 (DB / CSV 분기)
# ======================================================

def _save_user_prediction_to_firestore(user_id: str, predicted_win: int):
    """[DB 모드] 사용자 예측 결과를 Firestore에 저장합니다."""
    if not db_fs:
        print("🔥 Firestore 클라이언트가 없어 예측을 저장할 수 없습니다.")
        return
    user_ref = db_fs.collection("users").document(user_id)
    user_ref.set({
        "last_prediction": predicted_win,
        "prediction_timestamp": datetime.utcnow()
    }, merge=True)

def _save_user_prediction_to_csv(user_id: str, predicted_win: int):
    """[CSV 모드] 사용자 예측 결과를 CSV 파일에 기록합니다."""
    print(f"💾 [CSV 모드] 사용자 예측 저장: {user_id} -> {'승리' if predicted_win == 1 else '패배'}")
    
    # 데모용 CSV 파일 경로 설정
    demo_data_dir = os.path.join(os.path.dirname(__file__), "demo", "data")
    csv_path = os.path.join(demo_data_dir, "demo_user_predictions.csv")
    
    # 데이터 디렉토리가 없으면 생성 (안정성 강화)
    os.makedirs(demo_data_dir, exist_ok=True)
    
    # 파일에 저장할 데이터 생성
    new_prediction = pd.DataFrame([{
        "user_id": user_id,
        "predicted_win": predicted_win,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }])
    
    # 파일이 없으면 헤더와 함께 새로 쓰고, 있으면 내용만 추가
    if not os.path.exists(csv_path):
        new_prediction.to_csv(csv_path, index=False, encoding='utf-8-sig')
    else:
        new_prediction.to_csv(csv_path, mode='a', header=False, index=False, encoding='utf-8-sig')

def save_user_prediction(user_id: str, predicted_win: int):
    """DATA_SOURCE 설정에 따라 적절한 저장 함수를 호출합니다."""
    if DATA_SOURCE == "csv":
        _save_user_prediction_to_csv(user_id, predicted_win)
    else:
        _save_user_prediction_to_firestore(user_id, predicted_win)


# ======================================================
# ⚙️ 예측에 필요한 피처(Feature) 생성
# ======================================================
def _get_features_for_next_game():
    """다음 예측 대상 경기의 피처를 생성합니다."""
    
    if ADMIN_MODE:
        print(f"🧪 [관리자모드] {CURRENT_DATE} 기준, demo_features.csv에서 다음 경기를 찾습니다.")
        
        features_path = os.path.join(os.path.dirname(__file__), "demo", "demo_features.csv")
        if not os.path.exists(features_path):
            raise HTTPException(status_code=404, detail="demo_features.csv 파일을 찾을 수 없습니다.")
        
        features_df = pd.read_csv(features_path)
        
        # ✅ [핵심 수정] 날짜 비교를 위해 양쪽 모두 'YYYY-MM-DD' 형태의 문자열로 변환합니다.
        features_df['game_date_str'] = pd.to_datetime(features_df['game_date']).dt.strftime('%Y-%m-%d')
        current_date_str = CURRENT_DATE.strftime('%Y-%m-%d')

        # 문자열로 날짜를 비교합니다.
        upcoming_games = features_df[features_df['game_date_str'] >= current_date_str].sort_values(by='game_date_str')
        
        if upcoming_games.empty:
            return None, None # 시연 날짜 이후 경기가 없으면 404를 반환하는 것이 맞습니다.

        next_game_row = upcoming_games.iloc[0]

        # 최종 경기 정보 및 모델 입력(X) 생성
        class NextGame:
            game_id = next_game_row['game_id']
            # 날짜 객체를 다시 변환해서 사용합니다.
            game_date = datetime.strptime(next_game_row['game_date_str'], '%Y-%m-%d').date()
            home_team = next_game_row['home_team']
            away_team = next_game_row['away_team']

        feature_columns = [
            'samsung_elo', 'opponent_elo', 'rest_diff',
            'samsung_form', 'opponent_form',
            'samsung_pythagorean', 'opponent_pythagorean'
        ]
        X = pd.DataFrame([next_game_row[feature_columns].to_dict()])

        print(f"🎯 [관리자모드] 다음 경기 구성 완료 → {NextGame.home_team} vs {NextGame.away_team} ({NextGame.game_date})")
        return NextGame, X
    # --------------------------------------------------------
    # 🚀 2. 실 서비스 모드 (ADMIN_MODE=False) - 신규 로직
    # --------------------------------------------------------
    else:
        print("🚀 [실서비스 모드] DB에서 다음 경기 정보를 조회합니다.")
        # 1. DB에서 아직 치르지 않은 삼성의 다음 경기를 찾습니다.
        query_next_game = text("""
            SELECT s.game_id, s.game_date, s.home_team, s.away_team
            FROM kbo_schedule s
            LEFT JOIN game_results g ON s.game_id = g.game_id
            WHERE (s.home_team = '삼성' OR s.away_team = '삼성')
              AND g.game_id IS NULL
              AND s.game_date >= :today
            ORDER BY s.game_date ASC
            LIMIT 1
        """)
        with engine.connect() as conn:
            next_game_row = conn.execute(query_next_game, {"today": date.today()}).fetchone()

        if not next_game_row:
            return None, None # 예측할 경기가 없으면 None 반환
        
        # 2. 다음 경기의 상대팀을 xác định합니다.
        opponent_team_name = next_game_row.away_team if next_game_row.home_team == '삼성' else next_game_row.home_team
        
        # 3. 예측에 필요한 최신 팀 스탯(ELO 등)을 DB 또는 데모 파일에서 가져옵니다.
        #    (여기서는 시연 데이터와 일관성을 위해 데모 CSV를 사용합니다)
        stat_source_path = os.path.join(os.path.dirname(__file__), "demo", "data", "demo", "season_projection_demo.csv")
        if not os.path.exists(stat_source_path):
             raise HTTPException(status_code=404, detail="팀 스탯 데이터 파일을 찾을 수 없습니다.")
        
        all_stats_df = pd.read_csv(stat_source_path)
        all_stats_df.columns = [c.strip().lower() for c in all_stats_df.columns]

        samsung_stats = all_stats_df[all_stats_df['team'] == '삼성'].iloc[0].to_dict()
        opponent_stats = all_stats_df[all_stats_df['team'] == opponent_team_name].iloc[0].to_dict()

        # 4. 모델 입력에 맞는 피처(X)를 생성합니다.
        X = pd.DataFrame([{
            "samsung_elo": samsung_stats.get("elo", 1500), "opponent_elo": opponent_stats.get("elo", 1500),
            "rest_diff": 0,
            "samsung_form": samsung_stats.get("predicted_win", 0.5), "opponent_form": opponent_stats.get("predicted_win", 0.5),
            "samsung_pythagorean": samsung_stats.get("predicted_win", 0.5), "opponent_pythagorean": opponent_stats.get("predicted_win", 0.5)
        }])

        print(f"🎯 [실서비스 모드] 다음 경기 구성 완료 → {next_game_row.home_team} vs {next_game_row.away_team} ({next_game_row.game_date})")
        return next_game_row, X

# ======================================================
# ⚙️ AI 예측 결과 저장 (실제 서비스용)
# ======================================================
def _save_ai_prediction(game_id: str, game_date, predicted_win: int, predicted_prob: float):
    """AI의 예측 결과를 DB에 저장합니다. 관리자 모드에서는 실행되지 않습니다."""
    if ADMIN_MODE:
        print(f"🧪 [관리자모드] AI 예측 결과 저장을 건너뜁니다 (game_id={game_id})")
        return
    # (실제 DB 저장 로직...)


# ======================================================
#  FastAPI 라우터 (API 엔드포인트)
# ======================================================
@router.get("/predict/today")
def api_predict_today():
    """오늘의 경기(또는 시연 기준일의 경기)를 예측하여 결과를 반환합니다."""
    next_game, X = _get_features_for_next_game()
    if next_game is None:
        raise HTTPException(status_code=404, detail="예측할 다음 경기가 없습니다.")

    global model
    if model is None:
        raise HTTPException(status_code=503, detail="AI 모델이 서버에 로드되지 않았습니다. 서버 시작 로그를 확인하세요.")

    try:
        pred_label = int(model.predict(X)[0])
        proba = model.predict_proba(X)[0]
        samsung_win_prob = float(proba[1])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"모델 예측 중 오류 발생: {e}")

    _save_ai_prediction(next_game.game_id, next_game.game_date, pred_label, samsung_win_prob)

    return {
        "game_id": next_game.game_id,
        "game_date": str(next_game.game_date),
        "home_team": next_game.home_team,
        "away_team": next_game.away_team,
        "ai_predicted_win": pred_label,
        "ai_predicted_prob": samsung_win_prob,
        "mode": SEASON_MODE,
        "current_date_context": str(CURRENT_DATE),
    }

@router.post("/predict/user-choice")
def api_user_prediction(user_id: str, pick_samsung_win: int):
    """사용자의 예측을 받아 저장합니다."""
    if pick_samsung_win not in (0, 1):
        raise HTTPException(status_code=400, detail="pick_samsung_win 값은 0(패배) 또는 1(승리)이어야 합니다.")
    
    try:
        save_user_prediction(user_id, pick_samsung_win)
        return {"status": "ok", "message": "예측이 성공적으로 저장되었습니다.", "user_pick": pick_samsung_win}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"예측 저장 중 오류 발생: {e}")