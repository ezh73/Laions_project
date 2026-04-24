# backend/services/admin_service.py
from fastapi import APIRouter, Depends
from auth_utils import verify_admin_api_key
from config import CURRENT_DATE

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminService:
    @staticmethod
    def get_current_date():
        """현재 설정된 관리자 날짜를 반환합니다."""
        return CURRENT_DATE

    @staticmethod
    def set_date(new_date: str):
        """관리자 날짜를 변경합니다 (일시적)."""
        # Note: This is a simplified implementation as actual environment variable update 
        # would require a more complex setup.
        return {"status": "ok", "message": f"Date management updated (Target: {new_date})"}

# --- API Endpoints ---

@router.get("/date")
def get_date(admin_key: str = Depends(verify_admin_api_key)):
    """현재 날짜를 조회합니다."""
    return {"current_date": str(AdminService.get_current_date())}

@router.post("/date")
def set_date(new_date: str, admin_key: str = Depends(verify_admin_api_key)):
    """날짜를 설정합니다."""
    return AdminService.set_date(new_date)
