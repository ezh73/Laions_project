# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import ADMIN_MODE, CURRENT_DATE, SEASON_MODE, engine
from services import (
    crawler_service,
    feature_service,
    model_service,
    simulation_service,
    ranking_service,
    performance_service,
    admin_service
)
from supabase_config import upsert_user_score

app = FastAPI(title="Laions V2 API", version="2.0.0")

# 1. CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 서비스 라우터 등록
app.include_router(crawler_service.router)
app.include_router(feature_service.router)
app.include_router(model_service.router)
app.include_router(simulation_service.router)
app.include_router(ranking_service.router)
app.include_router(performance_service.router)
app.include_router(admin_service.router)

# 3. 시스템 상태 체크 API
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "admin_mode": ADMIN_MODE,
        "current_date": str(CURRENT_DATE),
        "season_mode": SEASON_MODE,
        "db_connected": True
    }

# 4. 퀴즈 API (quizmaker.py로 미리 생성된 퀴즈를 DB에서 조회)
@app.get("/api/quiz")
def get_quiz(difficulty: str = None):
    """DB에서 랜덤으로 퀴즈 1개를 반환합니다. (difficulty: easy / medium / hard, 생략 시 전체)"""
    try:
        with engine.connect() as conn:
            if difficulty and difficulty.lower() in ("easy", "medium", "hard"):
                result = conn.execute(
                    text("SELECT id, question, options, difficulty, source_hint FROM samfan_quizzes WHERE difficulty = :diff ORDER BY RANDOM() LIMIT 1"),
                    {"diff": difficulty.lower()}
                ).fetchone()
            else:
                result = conn.execute(
                    text("SELECT id, question, options, difficulty, source_hint FROM samfan_quizzes ORDER BY RANDOM() LIMIT 1")
                ).fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="등록된 퀴즈가 없습니다.")
            return {
                "status": "ok",
                "quiz": {
                    "id": result[0],
                    "question": result[1],
                    "options": result[2],
                    "difficulty": result[3],
                    "source_hint": result[4]
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"퀴즈 조회 실패: {str(e)}")

@app.post("/api/quiz/submit")
def submit_quiz(user_id: str, quiz_id: int, answer: str, display_name: str = None):
    """사용자의 퀴즈 정답을 확인하고 점수를 부여합니다. (하루 최대 5회 제한)"""
    try:
        with engine.begin() as conn:
            # 하루 퀴즈 제한 확인 (user_quizzes 테이블)
            today_str = str(CURRENT_DATE)
            daily_count = conn.execute(
                text("SELECT COUNT(*) FROM user_quizzes WHERE user_id = :uid AND quiz_date = :today"),
                {"uid": user_id, "today": today_str}
            ).scalar() or 0
            
            DAILY_QUIZ_LIMIT = 5
            if daily_count >= DAILY_QUIZ_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail=f"오늘의 퀴즈는 최대 {DAILY_QUIZ_LIMIT}회까지 참여 가능합니다. (현재 {daily_count}회)"
                )
            
            result = conn.execute(
                text("SELECT correct_answer, difficulty FROM samfan_quizzes WHERE id = :id"),
                {"id": quiz_id}
            ).fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="퀴즈를 찾을 수 없습니다.")
            
            correct_answer = result[0]
            difficulty = result[1]
            is_correct = (answer.strip().lower() == correct_answer.strip().lower())
            
            # 점수 정책
            score_policy = {"easy": 5, "medium": 10, "hard": 20}
            earned_points = score_policy.get(difficulty, 5) if is_correct else 0
            
            # user_quizzes에 기록 (정답/오답 관계없이 참여 횟수로 기록)
            conn.execute(
                text("""
                    INSERT INTO user_quizzes (user_id, quiz_id, quiz_date, is_correct, score_earned)
                    VALUES (:uid, :qid, :today, :correct, :points)
                """),
                {
                    "uid": user_id,
                    "qid": quiz_id,
                    "today": today_str,
                    "correct": is_correct,
                    "points": earned_points
                }
            )
            
            # Supabase에 점수 반영 (Firestore 대체)
            if is_correct and earned_points > 0:
                nickname = display_name or user_id[:8]
                upsert_user_score(
                    user_id=user_id,
                    nickname=nickname,
                    score_earned=earned_points,
                    score_type="quiz_score"
                )
            
            return {
                "status": "ok",
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "earned_points": earned_points,
                "daily_count": daily_count + 1,
                "daily_limit": DAILY_QUIZ_LIMIT
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"정답 제출 실패: {str(e)}")


# 5. 사용자 예측 제출 API (user_predictions 테이블)
@app.get("/api/predict/today")
def get_today_predictions():
    """오늘 날짜의 AI 예측 결과를 반환합니다. (model_service.py의 /api/model/all 사용)"""
    try:
        from services.model_service import ModelService
        preds = ModelService.predict_all_games()
        return {"status": "ok", "predictions": preds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"예측 조회 실패: {str(e)}")

@app.post("/api/predict/user-choice")
def submit_user_prediction(user_id: str, game_id: str, predicted_winner: str):
    """사용자의 승리 예측을 DB에 저장합니다."""
    try:
        with engine.begin() as conn:
            # user_profiles 테이블에 사용자 정보가 없으면 자동 생성
            conn.execute(
                text("""
                    INSERT INTO user_profiles (user_id, nickname)
                    VALUES (:uid, :nick)
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {"uid": user_id, "nick": user_id[:8]}
            )
            # user_predictions 테이블에 예측 저장 (중복 시 업데이트)
            conn.execute(
                text("""
                    INSERT INTO user_predictions (user_id, game_id, predicted_winner)
                    VALUES (:uid, :gid, :winner)
                    ON CONFLICT (user_id, game_id)
                    DO UPDATE SET predicted_winner = :winner2, created_at = NOW()
                """),
                {"uid": user_id, "gid": game_id, "winner": predicted_winner, "winner2": predicted_winner}
            )
        return {"status": "ok", "message": "예측이 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"예측 저장 실패: {str(e)}")


# 6. 시뮬레이션 리포트 API
@app.get("/api/performance/simulation-report")
def get_simulation_report():
    """시뮬레이션 상세 리포트를 반환합니다."""
    try:
        from services.simulation_service import SimulationService
        projection = SimulationService.get_season_projection()
        if isinstance(projection, list):
            return {
                "status": "ok",
                "report": {
                    "projections": projection,
                    "summary": "시뮬레이션 완료",
                    "admin_mode": ADMIN_MODE,
                    "current_date": str(CURRENT_DATE)
                }
            }
        return {
            "status": "ok",
            "report": {
                "projections": projection.get("projections", []),
                "summary": projection.get("summary", "시뮬레이션 완료"),
                "admin_mode": ADMIN_MODE,
                "current_date": str(CURRENT_DATE)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시뮬레이션 리포트 생성 실패: {str(e)}")


# 7. 리그 순위 API (team_rank 테이블)
@app.get("/api/standings")
def get_standings():
    """KBO 리그 순위를 조회합니다. (team_rank 테이블)"""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT team_name, rank, games, wins, losses, draws, win_rate, game_gap, last10, streak FROM team_rank ORDER BY rank ASC")
            ).fetchall()
            standings = [
                {
                    "team_name": row[0],
                    "rank": row[1],
                    "games": row[2],
                    "wins": row[3],
                    "losses": row[4],
                    "draws": row[5],
                    "win_rate": float(row[6]) if row[6] else 0,
                    "game_gap": row[7],
                    "last10": row[8],
                    "streak": row[9]
                }
                for row in rows
            ]
            return {"status": "ok", "standings": standings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"순위 조회 실패: {str(e)}")


# 8. 오늘의 삼성 라이온즈 역사 API
@app.get("/api/history/today")
def get_today_history():
    """오늘 날짜의 삼성 라이온즈 역사를 반환합니다. (samfan_history 테이블)"""
    try:
        with engine.connect() as conn:
            # 오늘 날짜(MM-DD)와 일치하는 역사 데이터 조회
            today_mmdd = CURRENT_DATE.strftime("%m-%d")
            result = conn.execute(
                text("""
                    SELECT id, date_text, event, reference
                    FROM samfan_history
                    WHERE to_char(event_date, 'MM-DD') = :mmdd
                    ORDER BY RANDOM() LIMIT 1
                """),
                {"mmdd": today_mmdd}
            ).fetchone()
            
            if not result:
                return {"status": "ok", "history": None, "message": "오늘의 역사 데이터가 없습니다."}
            
            return {
                "status": "ok",
                "history": {
                    "id": result[0],
                    "date_text": result[1],
                    "event": result[2],
                    "reference": result[3]
                }
            }
    except Exception as e:
        # samfan_history 테이블이 아직 생성되지 않은 경우 404 반환
        print(f"⚠️ 역사 조회 중 오류: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="역사 데이터를 조회할 수 없습니다.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
