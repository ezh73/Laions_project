# backend/database.py
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from config import engine

# 세션 생성기 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI의 Dependency Injection용 DB 세션 생성 함수입니다.
    사용이 끝나면 자동으로 세션을 닫아줍니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()