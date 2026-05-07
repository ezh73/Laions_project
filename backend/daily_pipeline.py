# backend/daily_pipeline.py
"""
일일 파이프라인 스크립트
GitHub Actions에서 매일 새벽 1시(KST)에 실행됩니다.

실행 순서:
1. 어제 경기 결과 스크래핑
2. 오늘 경기 일정 스크래핑
3. 피처 재구축
4. AI 예측 실행
5. 퀴즈 생성 (Gemini API)
6. 어제 예측 점수 정산
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import engine, CURRENT_DATE
from services.crawler_service import CrawlerService
from services.feature_service import FeatureService
from services.model_service import ModelService
from services.ranking_service import RankingService


def run_daily_pipeline():
    """일일 파이프라인을 순차적으로 실행합니다."""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"\n{'='*60}")
    print(f"🚀 일일 파이프라인 시작 (기준일: {today})")
    print(f"{'='*60}\n")
    
    results = {}
    
    # Step 1: 경기 결과 및 일정 스크래핑
    print(f"\n[1/5] 📡 경기 데이터 스크래핑...")
    try:
        scrape_result = CrawlerService.update_daily_pipeline()
        results['scrape'] = scrape_result
        print(f"   ✅ 스크래핑 완료: {scrape_result}")
    except Exception as e:
        print(f"   ❌ 스크래핑 실패: {e}")
        results['scrape'] = {"error": str(e)}
    
    # Step 2: 피처 재구축
    print(f"\n[2/5] 🔧 피처 재구축...")
    try:
        feature_count = FeatureService.build_all_features()
        results['features'] = feature_count
        print(f"   ✅ 피처 재구축 완료: {feature_count}개 경기")
    except Exception as e:
        print(f"   ❌ 피처 재구축 실패: {e}")
        results['features'] = {"error": str(e)}
    
    # Step 3: AI 예측 실행
    print(f"\n[3/5] 🤖 AI 예측 실행...")
    try:
        predictions = ModelService.predict_all_games()
        results['predictions'] = len(predictions)
        print(f"   ✅ AI 예측 완료: {len(predictions)}개 경기")
    except Exception as e:
        print(f"   ❌ AI 예측 실패: {e}")
        results['predictions'] = {"error": str(e)}
    
    # Step 4: 어제 예측 점수 정산
    print(f"\n[4/5] 📊 점수 정산 ({yesterday})...")
    try:
        settle_result = RankingService.settle_daily_points(
            datetime.strptime(yesterday, "%Y-%m-%d").date()
        )
        results['settle'] = settle_result
        print(f"   ✅ 점수 정산 완료: {settle_result}")
    except Exception as e:
        print(f"   ❌ 점수 정산 실패: {e}")
        results['settle'] = {"error": str(e)}
    
    # Step 5: 주간 랭킹 초기화 (월요일인 경우)
    if datetime.now().weekday() == 0:  # Monday
        print(f"\n[5/5] 🔄 주간 랭킹 초기화 (월요일)...")
        try:
            reset_result = RankingService.reset_weekly_ranking()
            results['weekly_reset'] = reset_result
            print(f"   ✅ 주간 랭킹 초기화 완료")
        except Exception as e:
            print(f"   ❌ 주간 랭킹 초기화 실패: {e}")
            results['weekly_reset'] = {"error": str(e)}
    else:
        print(f"\n[5/5] ⏭️ 주간 랭킹 초기화 스킵 (월요일 아님)")
        results['weekly_reset'] = "skipped"
    
    # 요약 출력
    print(f"\n{'='*60}")
    print(f"📋 파이프라인 실행 요약")
    print(f"{'='*60}")
    for step, result in results.items():
        status = "✅" if not isinstance(result, dict) or "error" not in result else "❌"
        print(f"   {status} {step}: {result}")
    print(f"{'='*60}\n")
    
    return results


if __name__ == "__main__":
    load_dotenv()
    run_daily_pipeline()
