# auth_utils.py
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
if not ADMIN_API_KEY:
    print("경고: ADMIN_API_KEY가 설정되지 않았습니다. 관리자 엔드포인트가 보호되지 않습니다.")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_admin_api_key(api_key_header: str = Security(api_key_header)):
    """
    API Key를 검증하고, 실패 시 403 Forbidden 에러를 반환합니다.
    """
    if not ADMIN_API_KEY or api_key_header != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="관리자 권한이 필요합니다 (Invalid or missing X-API-Key)"
        )
    return api_key_header