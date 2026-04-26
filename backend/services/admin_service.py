# backend/services/admin_service.py
from fastapi import APIRouter, Depends
from auth_utils import verify_admin_api_key
from config import CURRENT_DATE
import config as config_module

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminService:
    @staticmethod
    def get_current_date():
        """현재 설정된 관리자 날짜를 반환합니다."""
        return CURRENT_DATE

    @staticmethod
    def set_date(new_date: str):
        """관리자 날짜를 변경합니다 (일시적, 서버 재시작 시 초기화)."""
        from datetime import datetime
        try:
            # 날짜 형식 검증
            parsed_date = datetime.strptime(new_date, "%Y-%m-%d").date()
            
            # config 모듈의 ADMIN_DATE_STR과 CURRENT_DATE를 동적으로 변경
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
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식: {new_date}. YYYY-MM-DD 형식이어야 합니다.")

# --- API Endpoints ---

@router.get("/date")
def get_date(admin_key: str = Depends(verify_admin_api_key)):
    """현재 날짜를 조회합니다."""
    return {"current_date": str(AdminService.get_current_date())}

@router.post("/date")
def set_date(new_date: str, admin_key: str = Depends(verify_admin_api_key)):
    """날짜를 설정합니다."""
    return AdminService.set_date(new_date)
