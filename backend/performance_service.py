# performance_service.py (AI 예측 성능 분석)
from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text
import pandas as pd
import os
from dotenv import load_dotenv
from config import ADMIN_MODE, CURRENT_DATE

router = APIRouter()

# DB 연결 엔진은 main.py에서 정의된 것을 외부에서 사용하도록 설정
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
engine = create_engine(DATABASE_URL, client_encoding='utf8')


@router.get("/ai/performance/samsung")
def api_ai_performance(limit_recent: int = 10):
    """
    삼성 경기 기준 AI 예측 적중률 계산.
    - 시즌 중: 정규시즌 데이터 기준
    - 포스트시즌: postseason 일정 존재 시 해당 모드 반환
    - 비시즌: 데이터 없음 시 모델 검증 정확도 표시
    """
    # 1️⃣ 기본 쿼리 (정규시즌 예측 성능)
    q = text("""
        SELECT
            p.game_id,
            p.game_date,
            p.predicted_win,
            g.samsung_win
        FROM ai_predictions p
        JOIN game_results g
          ON p.game_id = g.game_id
        WHERE g.home_team = '삼성' OR g.away_team = '삼성'
        ORDER BY p.game_date DESC
    """)

    try:
        df = pd.read_sql(q, engine)
    except Exception as e:
        return {
            "mode": "offseason",
            "team": "삼성 라이온즈",
            "error": f"DB 조회 오류: {e}",
            "model_name": "LightGBM (Tuned)",
            "model_accuracy": 61.97,
            "message": "데이터베이스를 조회할 수 없어 기본 모델 정보를 표시합니다.",
        }

    # 2️⃣ 포스트시즌 여부 감지
    postseason_q = text("""
        SELECT COUNT(*) as cnt
        FROM kbo_schedule
        WHERE season_stage = 'POSTSEASON'
    """)
    try:
        postseason_count = pd.read_sql(postseason_q, engine).iloc[0]["cnt"]
    except Exception:
        postseason_count = 0

    # 3️⃣ 데이터 없음 (비시즌)
    if df.empty:
        return {
            "mode": "offseason",
            "team": "삼성 라이온즈",
            "model_name": "LightGBM (Tuned)",
            "model_accuracy": 61.97,
            "message": "아직 예측 또는 경기 결과 데이터가 없어 모델 검증 성능을 표시합니다.",
            "data_source": "Validation (2015–2024)"
        }

    # 4️⃣ 결과 미기록 (아직 시즌 시작 전)
    df = df.dropna(subset=["samsung_win"]).copy()
    if df.empty:
        return {
            "mode": "offseason",
            "team": "삼성 라이온즈",
            "model_name": "LightGBM (Tuned)",
            "model_accuracy": 61.97,
            "message": "경기 결과가 기록되지 않아 모델 검증 성능을 표시합니다.",
            "data_source": "Validation (2015–2024)"
        }

    # 5️⃣ 포스트시즌 여부 결정
    mode = "postseason" if postseason_count > 0 else "season"

    # 6️⃣ 적중률 계산
    df["correct"] = (df["predicted_win"] == df["samsung_win"]).astype(int)
    total_games = len(df)
    total_correct = int(df["correct"].sum())
    total_acc = round((total_correct / total_games) * 100.0, 2)

    recent_df = df.head(limit_recent) if len(df) >= limit_recent else df.copy()
    recent_correct = int(recent_df["correct"].sum())
    recent_games = len(recent_df)
    recent_acc = round((recent_correct / recent_games) * 100.0, 2)

    # 7️⃣ 결과 반환
    return {
        "mode": mode,
        "team": "삼성 라이온즈",
        "total_games": total_games,
        "total_correct": total_correct,
        "total_accuracy": total_acc,
        "recent_games": recent_games,
        "recent_correct": recent_correct,
        "recent_accuracy": recent_acc,
        "data_source": "ai_predictions, game_results",
    }

@router.get("/ai/performance/simulation-report")
def api_get_simulation_report():
    """
    관리자 모드에서 생성된 예측 시뮬레이션 리포트(CSV)를 읽어 결과를 반환합니다.
    """
    if not ADMIN_MODE:
        raise HTTPException(status_code=403, detail="이 API는 관리자 모드에서만 사용할 수 있습니다.")

    # .env의 ADMIN_DATE를 기반으로 파일 이름 생성
    report_filename = f"2025_prediction_report_until_{CURRENT_DATE}.csv"
    # 이 스크립트는 backend/에 있고, 리포트 파일은 backend/demo/에 있습니다.
    report_path = os.path.join(os.path.dirname(__file__), "demo", report_filename)

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail=f"리포트 파일을 찾을 수 없습니다: {report_filename}. 먼저 시뮬레이션 스크립트를 실행해주세요."
        )

    try:
        df = pd.read_csv(report_path)
        
        # CSV 파일에서 요약 정보 계산
        total_games = len(df)
        correct_predictions = int(df['is_correct'].sum())
        accuracy = (correct_predictions / total_games) * 100 if total_games > 0 else 0

        return {
            "status": "ok",
            "report_date": str(CURRENT_DATE),
            "total_games": total_games,
            "correct_predictions": correct_predictions,
            "accuracy": round(accuracy, 2),
            "recent_predictions": df.tail(5).to_dict(orient="records") # 최근 5경기 결과도 함께 전달
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 파일을 읽는 중 오류 발생: {e}")