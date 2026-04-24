# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

from config import ADMIN_MODE, CURRENT_DATE, SEASON_MODE
from services import (
    crawler_service, 
    feature_service, 
    model_service, 
    simulation_service, 
    ranking_service, 
    performance_service,
    admin_service
)

app = FastAPI(title="Laions V2 API", version="2.0.0")

# 1. CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Firebase 초기화 (Firestore 클라이언트 전역 공유)
# (참고: firebase_config.py에서 초기화 관리)

# 3. 서비스 라우터 등록
app.include_router(crawler_service.router)
app.include_router(feature_service.router)
app.include_router(model_service.router)
app.include_router(simulation_service.router)
app.include_router(ranking_service.router)
app.include_router(performance_service.router)
app.include_router(admin_service.router)

# 4. 시스템 상태 체크 API
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "admin_mode": ADMIN_MODE,
        "current_date": str(CURRENT_DATE),
        "season_mode": SEASON_MODE,
        "db_connected": True  # SQLAlchemy 엔진 연결 확인 로직 추가 가능
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)