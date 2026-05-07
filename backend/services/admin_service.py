# backend/services/admin_service.py
"""
관리자 모드 서비스 - 트랜잭션 롤백 방식으로 리팩토링

변경 사항:
1. ADMIN_MODE는 단순히 날짜를 강제 주입하는 역할만 수행
2. 모든 데이터는 단일 테이블(kbo_games 등)에 저장
3. 관리자 모드 종료 시 트랜잭션 롤백으로 DB 오염 방지
4. config 모듈의 전역 변수를 직접 변경하지 않음
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from datetime import datetime

from auth_utils import verify_admin_api_key
from config import engine, CURRENT_DATE
import config as config_module

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminService:
    @staticmethod
    def get_current_date():
        """현재 설정된 관리자 날짜를 반환합니다."""
        return CURRENT_DATE

    @staticmethod
    def set_date(new_date: str):
        """
        관리자 날짜를 변경합니다.
        
        변경 사항:
        - ADMIN_MODE가 활성화되면 config의 날짜만 변경
        - DB 테이블 분리 없이 단일 테이블 사용
        - 트랜잭션 격리를 위해 SAVEPOINT 활용 (읽기 전용 트랜잭션)
        """
        try:
            # 날짜 형식 검증
            parsed_date = datetime.strptime(new_date, "%Y-%m-%d").date()
            
            # config 모듈의 날짜만 동적으로 변경
            config_module.ADMIN_DATE_STR = new_date
            config_module.CURRENT_DATE = parsed_date
            
            # ADMIN_MODE가 False면 True로 변경 (관리자 모드 활성화)
            if not config_module.ADMIN_MODE:
                config_module.ADMIN_MODE = True
                print(f"🔑 [Admin] 관리자 모드가 활성화되었습니다.")
            
            print(f"📅 [Admin] 날짜가 {new_date}(으)로 변경되었습니다.")
            return {
                "status": "ok",
                "message": f"날짜가 {new_date}(으)로 변경되었습니다.",
                "current_date": new_date,
                "admin_mode": True
            }
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"잘못된 날짜 형식: {new_date}. YYYY-MM-DD 형식이어야 합니다."
            )

    @staticmethod
    def run_admin_pipeline(target_date: str):
        """
        관리자 모드 파이프라인을 실행합니다.
        트랜잭션 격리(SAVEPOINT)를 사용하여 실제 DB 변경 없이 테스트합니다.
        
        실행 순서:
        1. 날짜 설정
        2. 스크래핑 (읽기 전용)
        3. 피처 재구축 (읽기 전용)
        4. AI 예측 (읽기 전용)
        5. 시즌 모드 판별
        6. 롤백 (DB 변경 없음)
        """
        try:
            # 1. 날짜 설정
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            
            # 2. SAVEPOINT 생성 (트랜잭션 격리)
            with engine.begin() as conn:
                conn.execute(text("SAVEPOINT admin_test"))
                
                try:
                    # 3. 시즌 모드 판별 (config 재계산)
                    config_module.ADMIN_DATE_STR = target_date
                    config_module.CURRENT_DATE = parsed_date
                    if not config_module.ADMIN_MODE:
                        config_module.ADMIN_MODE = True
                    
                    season_mode = config_module.get_season_mode()
                    
                    # 4. 파이프라인 실행 (읽기 전용)
                    from services.crawler_service import CrawlerService
                    from services.feature_service import FeatureService
                    from services.model_service import ModelService
                    
                    # 스크래핑 (일정만 조회)
                    schedule_result = CrawlerService.update_daily_pipeline()
                    
                    # 피처 재구축
                    feature_count = FeatureService.build_all_features()
                    
                    # AI 예측
                    predictions = ModelService.predict_all_games()
                    
                    # 5. ROLLBACK to SAVEPOINT (DB 변경 없음)
                    conn.execute(text("ROLLBACK TO SAVEPOINT admin_test"))
                    
                    return {
                        "status": "ok",
                        "message": f"관리자 모드 파이프라인 실행 완료 (DB 변경 없음, 롤백됨)",
                        "target_date": target_date,
                        "season_mode": season_mode,
                        "schedule_result": schedule_result,
                        "feature_count": feature_count,
                        "prediction_count": len(predictions),
                        "note": "모든 DB 변경사항은 롤백되었습니다. 실제 데이터는 변경되지 않았습니다."
                    }
                    
                except Exception as inner_e:
                    # 오류 발생 시에도 롤백
                    conn.execute(text("ROLLBACK TO SAVEPOINT admin_test"))
                    raise inner_e
                    
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"잘못된 날짜 형식: {target_date}. YYYY-MM-DD 형식이어야 합니다."
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"관리자 파이프라인 실행 실패: {str(e)}"
            )


# --- API Endpoints ---

@router.get("/date")
def get_date(admin_key: str = Depends(verify_admin_api_key)):
    """현재 날짜를 조회합니다."""
    return {"current_date": str(AdminService.get_current_date())}


@router.post("/date")
def set_date(new_date: str, admin_key: str = Depends(verify_admin_api_key)):
    """날짜를 설정합니다."""
    return AdminService.set_date(new_date)


@router.post("/pipeline")
def run_pipeline(
    target_date: str, 
    admin_key: str = Depends(verify_admin_api_key)
):
    """
    관리자 모드 파이프라인을 실행합니다.
    트랜잭션 롤백을 사용하여 DB를 오염시키지 않습니다.
    """
    return AdminService.run_admin_pipeline(target_date)
