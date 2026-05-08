# backend/daily_pipeline.py
"""
일일 파이프라인 스크립트
GitHub Actions에서 매일 새벽 1시(KST)에 실행됩니다.

실행 순서:
1. 어제 경기 결과 스크래핑
2. 오늘 경기 일정 스크래핑
3. 피처 재구축
4. AI 예측 실행
5. 리그 순위 업데이트
6. 어제 예측 점수 정산
7. 주간 랭킹 초기화 (월요일)
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import text

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import engine, CURRENT_DATE, TEAMS
from services.crawler_service import CrawlerService
from services.feature_service import FeatureService
from services.model_service import ModelService
from services.ranking_service import RankingService


def update_team_rankings(conn=None):
    """
    kbo_games 데이터를 기반으로 리그 순위(team_rank)를 계산하여 업데이트합니다.
    
    Args:
        conn: 외부 트랜잭션 connection (관리자 모드용). None이면 자체 트랜잭션 사용.
    """
    print(f"\n[5/7] 📊 리그 순위 업데이트...")
    try:
        # 1. 각 팀별 승/패/무 집계
        standings_query = text("""
            SELECT
                team,
                COUNT(*) AS games,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws
            FROM (
                SELECT home_team AS team,
                       CASE
                           WHEN home_score > away_score THEN 'win'
                           WHEN home_score < away_score THEN 'loss'
                           ELSE 'draw'
                       END AS result
                FROM kbo_games
                WHERE winning_team IS NOT NULL
                UNION ALL
                SELECT away_team AS team,
                       CASE
                           WHEN away_score > home_score THEN 'win'
                           WHEN away_score < home_score THEN 'loss'
                           ELSE 'draw'
                       END AS result
                FROM kbo_games
                WHERE winning_team IS NOT NULL
            ) AS team_results
            GROUP BY team
        """)
        
        if conn:
            rows = conn.execute(standings_query).fetchall()
        else:
            with engine.connect() as read_conn:
                rows = read_conn.execute(standings_query).fetchall()
        
        if not rows:
            print("   ⚠️ 순위를 계산할 경기 데이터가 없습니다.")
            return 0
        
        # 2. 승률 계산 및 정렬
        team_data = []
        for row in rows:
            team = row[0]
            games = row[1] or 0
            wins = row[2] or 0
            losses = row[3] or 0
            draws = row[4] or 0
            win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
            team_data.append({
                "team": team,
                "games": games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate
            })
        
        # 승률 내림차순 정렬
        team_data.sort(key=lambda x: x["win_rate"], reverse=True)
        
        # 3. 게임차 계산 (1위 팀 기준)
        top_wins = team_data[0]["wins"] if team_data else 0
        top_losses = team_data[0]["losses"] if team_data else 0
        
        # 4. 각 팀별 최근 10경기 결과 및 연속 승/패 계산
        def _get_team_recent_stats(write_conn, team):
            """특정 팀의 최근 10경기 결과와 현재 연속 승/패를 조회합니다."""
            recent_games = write_conn.execute(text("""
                SELECT game_date, home_team, away_team, home_score, away_score
                FROM kbo_games
                WHERE (home_team = :team OR away_team = :team)
                  AND winning_team IS NOT NULL
                ORDER BY game_date DESC
                LIMIT 10
            """), {"team": team}).fetchall()
            
            if not recent_games:
                return "", ""
            
            # 최근 10경기 결과 문자열 (예: "승승패승무패승승승패")
            results = []
            for g in recent_games:
                if g.home_team == team:
                    if g.home_score > g.away_score:
                        results.append("승")
                    elif g.home_score < g.away_score:
                        results.append("패")
                    else:
                        results.append("무")
                else:  # away_team
                    if g.away_score > g.home_score:
                        results.append("승")
                    elif g.away_score < g.home_score:
                        results.append("패")
                    else:
                        results.append("무")
            
            last10 = "".join(results)
            
            # 연속 승/패 계산 (최신 경기부터)
            streak = ""
            if results:
                first_result = results[0]
                count = 0
                for r in results:
                    if r == first_result:
                        count += 1
                    else:
                        break
                streak = f"{count}{first_result}"
            
            return last10, streak
        
        # 5. team_rank 테이블 업데이트
        def _write_rankings(write_conn):
            write_conn.execute(text("DELETE FROM team_rank"))
            for rank, td in enumerate(team_data, 1):
                game_gap = round(((top_wins - td["wins"]) + (td["losses"] - top_losses)) / 2, 1)
                game_gap_str = "-" if rank == 1 else str(game_gap)
                
                last10, streak = _get_team_recent_stats(write_conn, td["team"])
                
                write_conn.execute(text("""
                    INSERT INTO team_rank (team_name, rank, games, wins, losses, draws, win_rate, game_gap, last10, streak)
                    VALUES (:team, :rank, :games, :wins, :losses, :draws, :win_rate, :game_gap, :last10, :streak)
                    ON CONFLICT (team_name) DO UPDATE SET
                        rank = EXCLUDED.rank,
                        games = EXCLUDED.games,
                        wins = EXCLUDED.wins,
                        losses = EXCLUDED.losses,
                        draws = EXCLUDED.draws,
                        win_rate = EXCLUDED.win_rate,
                        game_gap = EXCLUDED.game_gap,
                        last10 = EXCLUDED.last10,
                        streak = EXCLUDED.streak
                """), {
                    "team": td["team"],
                    "rank": rank,
                    "games": td["games"],
                    "wins": td["wins"],
                    "losses": td["losses"],
                    "draws": td["draws"],
                    "win_rate": round(td["win_rate"], 3),
                    "game_gap": game_gap_str,
                    "last10": last10,
                    "streak": streak
                })
        
        if conn:
            _write_rankings(conn)
        else:
            with engine.begin() as write_conn:
                _write_rankings(write_conn)
        
        print(f"   ✅ 리그 순위 업데이트 완료: {len(team_data)}개 팀")
        return len(team_data)
            
    except Exception as e:
        print(f"   ❌ 리그 순위 업데이트 실패: {e}")
        return 0


def run_daily_pipeline():
    """일일 파이프라인을 순차적으로 실행합니다."""
    today = CURRENT_DATE
    yesterday = today - timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"🚀 일일 파이프라인 시작 (기준일: {today})")
    print(f"{'='*60}\n")
    
    results = {}
    
    # Step 1: 경기 결과 및 일정 스크래핑
    print(f"\n[1/7] 📡 경기 데이터 스크래핑...")
    try:
        scrape_result = CrawlerService.update_daily_pipeline()
        results['scrape'] = scrape_result
        print(f"   ✅ 스크래핑 완료: {scrape_result}")
    except Exception as e:
        print(f"   ❌ 스크래핑 실패: {e}")
        results['scrape'] = {"error": str(e)}
    
    # Step 2: 피처 재구축
    print(f"\n[2/7] 🔧 피처 재구축...")
    try:
        feature_count = FeatureService.build_all_features()
        results['features'] = feature_count
        print(f"   ✅ 피처 재구축 완료: {feature_count}개 경기")
    except Exception as e:
        print(f"   ❌ 피처 재구축 실패: {e}")
        results['features'] = {"error": str(e)}
    
    # Step 3: AI 예측 실행
    print(f"\n[3/7] 🤖 AI 예측 실행...")
    try:
        predictions = ModelService.predict_all_games()
        results['predictions'] = len(predictions)
        print(f"   ✅ AI 예측 완료: {len(predictions)}개 경기")
    except Exception as e:
        print(f"   ❌ AI 예측 실패: {e}")
        results['predictions'] = {"error": str(e)}
    
    # Step 4: 어제 예측 점수 정산
    print(f"\n[4/7] 📊 점수 정산 ({yesterday})...")
    try:
        settle_result = RankingService.settle_daily_points(yesterday)
        results['settle'] = settle_result
        print(f"   ✅ 점수 정산 완료: {settle_result}")
    except Exception as e:
        print(f"   ❌ 점수 정산 실패: {e}")
        results['settle'] = {"error": str(e)}
    
    # Step 5: 리그 순위 업데이트
    team_count = update_team_rankings()
    results['standings'] = team_count
    
    # Step 6: 주간 랭킹 초기화 (월요일인 경우)
    if today.weekday() == 0:  # Monday
        print(f"\n[6/7] 🔄 주간 랭킹 초기화 (월요일)...")
        try:
            reset_result = RankingService.reset_weekly_ranking()
            results['weekly_reset'] = reset_result
            print(f"   ✅ 주간 랭킹 초기화 완료")
        except Exception as e:
            print(f"   ❌ 주간 랭킹 초기화 실패: {e}")
            results['weekly_reset'] = {"error": str(e)}
    else:
        print(f"\n[6/7] ⏭️ 주간 랭킹 초기화 스킵 (월요일 아님)")
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
