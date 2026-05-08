# backend/supabase_config.py
"""
Supabase 클라이언트 설정 및 유틸리티 함수
Firebase Firestore를 Supabase(PostgreSQL)로 대체합니다.
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Supabase 클라이언트를 지연 로딩(Lazy Loading) 방식으로 반환합니다."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            print("⚠️ [Supabase] SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
            return None
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("🔥 [Supabase] 연결 성공")
        except Exception as e:
            print(f"⚠️ [Supabase] 연결 실패: {e}")
            return None
    return _supabase_client


def upsert_user_score(
    user_id: str,
    nickname: str,
    score_earned: int,
    score_type: str = "weekly_score"
) -> bool:
    """
    사용자 점수를 Supabase user_profiles 테이블에 UPSERT합니다.
    
    Args:
        user_id: Firebase UID 또는 Supabase Auth UID
        nickname: 사용자 닉네임
        score_earned: 추가할 점수
        score_type: 점수 타입 (weekly_score, prediction_score, quiz_score)
    
    Returns:
        성공 여부
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        # 기존 사용자 조회
        existing = client.table("user_profiles").select("*").eq("user_id", user_id).execute()
        
        if existing.data:
            # 기존 사용자: 점수 업데이트
            current = existing.data[0]
            from datetime import datetime
            now_iso = datetime.utcnow().isoformat()
            updates = {
                score_type: (current.get(score_type, 0) or 0) + score_earned,
                "updated_at": now_iso
            }
            # weekly_score는 score_type이 "weekly_score"일 때만 증가
            if score_type == "weekly_score":
                updates["weekly_score"] = (current.get("weekly_score", 0) or 0) + score_earned
            client.table("user_profiles").update(updates).eq("user_id", user_id).execute()
        else:
            # 신규 사용자: 프로필 생성
            new_profile = {
                "user_id": user_id,
                "nickname": nickname,
                score_type: score_earned,
                "weekly_score": score_earned if score_type == "weekly_score" else 0,
                "prediction_score": score_earned if score_type == "prediction_score" else 0,
                "quiz_score": score_earned if score_type == "quiz_score" else 0,
            }
            client.table("user_profiles").insert(new_profile).execute()
        
        return True
    except Exception as e:
        print(f"⚠️ [Supabase] 점수 업데이트 실패: {e}")
        return False


def get_user_rankings(limit: int = 10, order_by: str = "weekly_score"):
    """
    사용자 랭킹을 조회합니다.
    
    Args:
        limit: 조회할 상위 N명
        order_by: 정렬 기준 (weekly_score, prediction_score, quiz_score)
    
    Returns:
        랭킹 리스트
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        result = client.table("user_profiles") \
            .select("*") \
            .order(order_by, desc=True) \
            .limit(limit) \
            .execute()
        
        rankings = []
        for idx, row in enumerate(result.data):
            rankings.append({
                "rank": idx + 1,
                "user_id": row.get("user_id"),
                "nickname": row.get("nickname", "익명"),
                "weekly_score": row.get("weekly_score", 0) or 0,
                "prediction_score": row.get("prediction_score", 0) or 0,
                "quiz_score": row.get("quiz_score", 0) or 0,
            })
        return rankings
    except Exception as e:
        print(f"⚠️ [Supabase] 랭킹 조회 실패: {e}")
        return []


def reset_weekly_scores():
    """주간 점수를 초기화합니다. (매주 월요일 호출)"""
    client = get_supabase_client()
    if not client:
        return False

    try:
        # updated_at에 "now()" 문자열이 아닌 실제 DB now() 함수를 사용하기 위해
        # Supabase의 raw SQL 실행 기능을 활용
        from datetime import datetime
        now_iso = datetime.utcnow().isoformat()
        client.table("user_profiles") \
            .update({"weekly_score": 0, "updated_at": now_iso}) \
            .gte("weekly_score", 1) \
            .execute()
        return True
    except Exception as e:
        print(f"⚠️ [Supabase] 주간 점수 초기화 실패: {e}")
        return False
