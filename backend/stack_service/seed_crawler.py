# backend/stack_service/seed_crawler.py
"""
과거 경기 데이터 시딩 스크립트
Daum Sports에서 과거 KBO 경기 데이터를 수집하여 DB에 저장합니다.
최초 1회 또는 필요시에만 수동 실행합니다.

Daum Sports는 2007년부터 데이터를 제공하므로,
기본 수집 범위는 2007년 ~ 2025년입니다.

사용 예:
    python -m stack_service.seed_crawler                         # 2007~2025 전체 수집
    python -m stack_service.seed_crawler --dry-run                # 미리보기
    python -m stack_service.seed_crawler --start-year 2020        # 2020~2025만 수집
"""
import argparse
import sys
from datetime import date
from sqlalchemy import text

from config import engine
from services.crawler_service import CrawlerService

# Daum Sports가 제공하는 가장 오래된 연도
EARLIEST_YEAR = 2007
DEFAULT_END_YEAR = 2025


def seed_historical_data(start_year: int, end_year: int, dry_run: bool = False) -> int:
    """
    과거 경기 데이터를 Daum Sports에서 수집하여 DB에 저장합니다.
    월별로 각 월의 1일을 기준일로 요청합니다.

    Args:
        start_year: 수집 시작 연도 (예: 2007)
        end_year: 수집 종료 연도 (예: 2025)
        dry_run: True면 DB 저장 없이 수집 결과만 출력

    Returns:
        int: 저장된 경기 개수
    """
    total_count = 0
    for year in range(start_year, end_year + 1):
        for month in range(3, 12):
            target_date = date(year, month, 1)
            soup = CrawlerService._fetch_from_daum(target_date)
            if not soup:
                continue

            games = CrawlerService._parse_daum_rows(soup)
            for game in games:
                # 점수가 '-'인 경기(미경기)는 저장하지 않음
                if game["home_score"] == "-" or game["away_score"] == "-":
                    continue

                try:
                    home_score = int(game["home_score"])
                    away_score = int(game["away_score"])
                except ValueError:
                    continue

                # 승리팀 결정
                if home_score > away_score:
                    winning_team = game["home_team"]
                elif away_score > home_score:
                    winning_team = game["away_team"]
                else:
                    winning_team = "무승부"

                parsed = {
                    "game_id": game["game_id"],
                    "game_date": game["game_date"],
                    "home_team": game["home_team"],
                    "away_team": game["away_team"],
                    "home_score": home_score,
                    "away_score": away_score,
                    "winning_team": winning_team,
                    "is_postseason": game["is_postseason"],
                    "sort_text": game["sort_text"],
                }

                if dry_run:
                    print(f"  [DRY-RUN] {game['game_date']} {game['away_team']} vs {game['home_team']} ({home_score}-{away_score})")
                    total_count += 1
                else:
                    with engine.begin() as conn:
                        insert_query = text("""
                            INSERT INTO kbo_games (game_id, game_date, home_team, away_team, home_score, away_score, winning_team, is_postseason, sort_text)
                            VALUES (:game_id, :game_date, :home_team, :away_team, :home_score, :away_score, :winning_team, :is_postseason, :sort_text)
                            ON CONFLICT (game_id) DO NOTHING
                        """)
                        result = conn.execute(insert_query, parsed)
                        if result.rowcount > 0:
                            total_count += 1

        print(f"✅ {year}년 수집 완료. 현재 누적: {total_count}개")

    return total_count


def main():
    parser = argparse.ArgumentParser(
        description="Daum Sports에서 과거 KBO 경기 데이터를 수집하여 DB에 저장합니다."
    )
    parser.add_argument(
        "--start-year", type=int, default=EARLIEST_YEAR,
        help=f"수집 시작 연도 (기본값: {EARLIEST_YEAR}, Daum Sports 최초 제공 연도)"
    )
    parser.add_argument(
        "--end-year", type=int, default=DEFAULT_END_YEAR,
        help=f"수집 종료 연도 (기본값: {DEFAULT_END_YEAR})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="DB 저장 없이 수집 결과만 미리보기"
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"📡 과거 경기 데이터 수집 시작")
    print(f"   대상: {args.start_year}년 ~ {args.end_year}년")
    print(f"   모드: {'🔍 DRY-RUN (미리보기)' if args.dry_run else '💾 실제 저장'}")
    print(f"{'='*60}\n")

    count = seed_historical_data(args.start_year, args.end_year, args.dry_run)

    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"🔍 DRY-RUN 완료: 총 {count}개 경기 확인됨")
    else:
        print(f"🎉 수집 완료: 총 {count}개 경기 저장됨")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
