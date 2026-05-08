# backend/services/admin_service.py
"""
관리자 모드 서비스 - 트랜잭션 롤백 방식

변경 사항:
1. ADMIN_MODE는 단순히 날짜를 강제 주입하는 역할만 수행
2. 모든 데이터는 단일 테이블(kbo_games 등)에 저장
3. 관리자 모드 파이프라인은 하나의 트랜잭션으로 모든 작업을 수행 후 ROLLBACK
4. 내부 서비스 함수들에 동일한 connection 객체를 주입하여 모두 같은 트랜잭션 내에서 실행

수정 내용 (2026-05-08):
- 기존 SAVEPOINT 방식은 engine.begin()이 종료 시 COMMIT하여 롤백이 무효화됨
- 내부 서비스 함수들이 각자 별도 engine.begin()으로 트랜잭션을 열어 SAVEPOINT 범위 밖에서 동작
- 해결: engine.connect() + 수동 BEGIN/ROLLBACK 사용, 모든 함수에 conn 주입
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import datetime
import pandas as pd

from config import engine, CURRENT_DATE, TEAMS, FEATURE_CONFIG
import config as config_module

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminService:
    @staticmethod
    def _apply_admin_date(target_date: str):
        """config 모듈에 관리자 날짜를 적용하고 이전 상태를 반환합니다."""
        previous = {
            "ADMIN_DATE_STR": getattr(config_module, "ADMIN_DATE_STR", None),
            "CURRENT_DATE": getattr(config_module, "CURRENT_DATE", None),
            "ADMIN_MODE": getattr(config_module, "ADMIN_MODE", False),
        }
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        config_module.ADMIN_DATE_STR = target_date
        config_module.CURRENT_DATE = parsed_date
        if not config_module.ADMIN_MODE:
            config_module.ADMIN_MODE = True
        return previous

    @staticmethod
    def _restore_admin_date(previous: dict):
        """config 모듈의 관리자 날짜를 이전 상태로 복원합니다."""
        config_module.ADMIN_DATE_STR = previous["ADMIN_DATE_STR"]
        config_module.CURRENT_DATE = previous["CURRENT_DATE"]
        config_module.ADMIN_MODE = previous["ADMIN_MODE"]

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
        하나의 트랜잭션으로 모든 작업을 수행한 후 ROLLBACK하여 DB 변경을 취소합니다.
        """
        previous_config = None
        try:
            # 1. 날짜 설정 및 이전 상태 저장
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            previous_config = AdminService._apply_admin_date(target_date)
            
            # 2. 시즌 모드 판별
            season_mode = config_module.get_season_mode()
            
            # 3. 하나의 트랜잭션으로 모든 작업 수행
            from services.crawler_service import CrawlerService
            from services.feature_service import FeatureService
            from services.model_service import ModelService
            from daily_pipeline import update_team_rankings
            
            with engine.connect() as conn:
                trans = conn.begin()  # 수동 트랜잭션 시작
                try:
                    print(f"🔁 [Admin] 트랜잭션 시작 (target_date: {target_date})")
                    
                    # 3a. 경기 데이터 스크래핑 (conn 주입)
                    print(f"\n[1/5] 📡 경기 데이터 스크래핑...")
                    scrape_result = CrawlerService.update_daily_pipeline(conn=conn)
                    print(f"   ✅ 스크래핑 완료: {scrape_result}")
                    
                    # 3b. 피처 재구축 (conn 주입)
                    print(f"\n[2/5] 🔧 피처 재구축...")
                    feature_count = FeatureService.build_all_features(conn=conn)
                    print(f"   ✅ 피처 재구축 완료: {feature_count}개 경기")
                    
                    # 3c. AI 예측 (conn 주입)
                    print(f"\n[3/5] 🤖 AI 예측 실행...")
                    predictions = ModelService.predict_all_games(conn=conn)
                    print(f"   ✅ AI 예측 완료: {len(predictions)}개 경기")
                    
                    # 3d. 리그 순위 업데이트 (conn 주입)
                    print(f"\n[4/5] 📊 리그 순위 업데이트...")
                    team_count = update_team_rankings(conn=conn)
                    print(f"   ✅ 리그 순위 업데이트 완료: {team_count}개 팀")
                    
                    # 3e. 모든 작업 완료 후 ROLLBACK
                    print(f"\n[5/5] ↩️ 트랜잭션 롤백...")
                    trans.rollback()
                    print(f"   ✅ 롤백 완료: 모든 DB 변경사항이 취소되었습니다.")
                    
                    result = {
                        "status": "ok",
                        "message": f"관리자 모드 파이프라인 실행 완료 (트랜잭션 롤백 적용)",
                        "target_date": target_date,
                        "season_mode": season_mode,
                        "scrape_result": scrape_result,
                        "feature_count": feature_count,
                        "prediction_count": len(predictions),
                        "team_rank_count": team_count,
                        "note": "모든 작업은 하나의 트랜잭션으로 수행된 후 ROLLBACK되었습니다. DB는 변경되지 않았습니다."
                    }
                    
                except Exception as inner_e:
                    trans.rollback()
                    print(f"   ❌ 파이프라인 실패로 롤백: {inner_e}")
                    result = {
                        "status": "error",
                        "message": f"파이프라인 실행 중 오류 발생, 트랜잭션 롤백됨: {str(inner_e)}",
                        "target_date": target_date
                    }
            
            return result
                    
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
        finally:
            # config 날짜 원복 (예외 발생 여부와 관계없이 항상 실행)
            if previous_config:
                AdminService._restore_admin_date(previous_config)
                print(f"   ✅ [Admin] config 상태가 원복되었습니다.")


# --- API Endpoints ---

@router.get("/date")
def get_date():
    """현재 날짜를 조회합니다."""
    return {"current_date": str(AdminService.get_current_date())}


@router.post("/date")
def set_date(new_date: str):
    """날짜를 설정합니다."""
    return AdminService.set_date(new_date)


@router.post("/pipeline")
def run_pipeline(
    target_date: str
):
    """
    관리자 모드 파이프라인을 실행합니다.
    하나의 트랜잭션으로 모든 작업을 수행한 후 ROLLBACK하여 DB 변경을 취소합니다.
    """
    return AdminService.run_admin_pipeline(target_date)
