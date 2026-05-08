# backend/services/simulation_service.py
from fastapi import APIRouter, HTTPException
import pandas as pd
from sqlalchemy import text
from config import engine, TEAMS, FEATURE_CONFIG, CURRENT_DATE
from services.model_service import ModelService
from services.model_preprocessor import ModelPreprocessor

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# 포스트시즌 시리즈 정의 (진행 순서)
POSTSEASON_SERIES = [
    {"key": "wildcard", "name": "와일드카드 결정전", "sort_key": 1},
    {"key": "semifinal", "name": "준플레이오프", "sort_key": 2},
    {"key": "final", "name": "플레이오프", "sort_key": 3},
    {"key": "ks", "name": "한국시리즈", "sort_key": 4},
]


class SimulationService:
    @classmethod
    def _get_team_latest_features(cls, team: str) -> dict | None:
        """
        특정 팀의 가장 최신 match_features 레코드를 조회합니다.

        Args:
            team: 팀명 (예: "삼성")

        Returns:
            dict: {"team": 팀명, "elo": ..., "form": ..., "streak": ..., "pyth": ..., "recent_rd": ...}
            또는 None (데이터 없음)
        """
        with engine.connect() as conn:
            res = conn.execute(text("""
                SELECT * FROM match_features
                WHERE home_team = :team OR away_team = :team
                ORDER BY game_date DESC LIMIT 1
            """), {"team": team}).fetchone()

        if not res:
            return None

        is_home = (res.home_team == team)
        return {
            "team": team,
            "elo": res.home_elo if is_home else res.away_elo,
            "form": res.home_form if is_home else res.away_form,
            "streak": res.home_streak if is_home else res.away_streak,
            "pyth": res.home_pythagorean if is_home else res.away_pythagorean,
            "recent_rd": res.home_recent_rd if is_home else res.away_recent_rd,
        }

    @staticmethod
    def _build_virtual_match_row(home_stats: dict, away_stats: dict) -> dict:
        """
        두 팀의 최신 스탯을 바탕으로 가상 대진 1행을 생성합니다.

        Args:
            home_stats: 홈팀 스탯 dict (_get_team_latest_features 반환값)
            away_stats: 원정팀 스탯 dict

        Returns:
            dict: ModelPreprocessor.preprocess_data()에 전달 가능한 1행 dict
        """
        return {
            "home_team": home_stats["team"],
            "away_team": away_stats["team"],
            "home_elo": home_stats["elo"],
            "away_elo": away_stats["elo"],
            "home_form": home_stats["form"],
            "away_form": away_stats["form"],
            "home_streak": home_stats["streak"],
            "away_streak": away_stats["streak"],
            "home_pythagorean": home_stats["pyth"],
            "away_pythagorean": away_stats["pyth"],
            "home_recent_rd": home_stats["recent_rd"],
            "away_recent_rd": away_stats["recent_rd"],
            "home_matchup_rd": 0.0,
            "away_matchup_rd": 0.0,
            "season_matchup_count": 0,
            "rest_diff": 0,
        }

    @classmethod
    def get_season_projection(cls):
        """모든 팀 간의 가상 대진을 시뮬레이션하여 최종 기대 순위를 계산합니다."""
        model = ModelService.get_model()
        if not model:
            return []

        # 1. 각 팀의 '가장 최신' 전력 상태(ELO, Form 등) 가져오기
        latest_stats = []
        for team in TEAMS:
            stats = cls._get_team_latest_features(team)
            if stats:
                latest_stats.append(stats)

        if not latest_stats:
            return []

        # 2. 모든 팀 쌍(Pair)에 대한 가상 대진 생성 (총 90개 조합)
        virtual_matches = []
        for home in latest_stats:
            for away in latest_stats:
                if home['team'] == away['team']:
                    continue
                virtual_matches.append(cls._build_virtual_match_row(home, away))

        v_df = pd.DataFrame(virtual_matches)

        # 3. 승률 예측 및 팀별 평균 기대 승률 계산
        X = ModelPreprocessor.preprocess_data(v_df)
        v_df['win_prob'] = model.predict_proba(X)[:, 1]

        # 각 팀이 홈/원정일 때의 모든 기대 승률을 평균내어 시즌 기대 승률 도출
        projection = v_df.groupby("home_team")['win_prob'].mean().reset_index()
        projection.columns = ['team', 'expected_win_rate']

        # 144경기 기준 예상 승수 계산
        projection['expected_wins'] = (projection['expected_win_rate'] * 144).round(1)
        projection = projection.sort_values(by="expected_win_rate", ascending=False).reset_index(drop=True)
        projection['predicted_rank'] = projection.index + 1

        return projection.to_dict(orient="records")

    @classmethod
    def get_postseason_bracket(cls):
        """
        포스트시즌 대진표와 각 시리즈의 진행 상황, AI 예측 결과를 반환합니다.

        Returns:
            dict: {
                "series": [
                    {
                        "key": "wildcard",
                        "name": "와일드카드 결정전",
                        "sort_key": 1,
                        "teams": ["팀A", "팀B"],
                        "games": [...],
                        "completed_games": 0,
                        "total_games": 1,
                        "winner": "팀A" or None,
                        "predicted_winner": "팀A" or None,
                        "status": "upcoming" | "in_progress" | "completed"
                    },
                    ...
                ],
                "next_series_prediction": {
                    "series_key": "semifinal",
                    "predicted_matchup": ["팀A", "팀C"],
                    "explanation": "..."
                }
            }
        """
        model = ModelService.get_model()
        if not model:
            return None

        with engine.connect() as conn:
            # 1. 포스트시즌 전체 경기 조회 (is_postseason = TRUE) - sort_text 포함
            rows = conn.execute(text("""
                SELECT game_id, game_date, home_team, away_team, home_score, away_score, winning_team, sort_text
                FROM kbo_games
                WHERE is_postseason = TRUE
                AND EXTRACT(YEAR FROM game_date) = :year
                ORDER BY game_date ASC
            """), {"year": CURRENT_DATE.year}).fetchall()

            # 2. kbo_schedule에서 예정된 포스트시즌 경기도 조회 - sort_text 포함
            sched_rows = conn.execute(text("""
                SELECT game_id, game_date, home_team, away_team, game_status, sort_text
                FROM kbo_schedule
                WHERE is_postseason = TRUE
                AND EXTRACT(YEAR FROM game_date) = :year
                ORDER BY game_date ASC
            """), {"year": CURRENT_DATE.year}).fetchall()

        # 3. 경기 데이터를 시리즈별로 분류
        # Daum Sports의 '구분' 컬럼(td_sort) 값을 DB sort_text에 저장하여 활용
        # sort_text 값: "페넌트레이스", "와일드카드", "준플레이오프", "플레이오프", "한국시리즈"

        all_games = {}
        for row in rows:
            all_games[row.game_id] = {
                "game_id": row.game_id,
                "game_date": str(row.game_date),
                "home_team": row.home_team,
                "away_team": row.away_team,
                "home_score": row.home_score,
                "away_score": row.away_score,
                "winning_team": row.winning_team,
                "sort_text": row.sort_text or "",
                "status": "completed"
            }

        for row in sched_rows:
            if row.game_id not in all_games:
                all_games[row.game_id] = {
                    "game_id": row.game_id,
                    "game_date": str(row.game_date),
                    "home_team": row.home_team,
                    "away_team": row.away_team,
                    "home_score": None,
                    "away_score": None,
                    "winning_team": None,
                    "sort_text": row.sort_text or "",
                    "status": "scheduled"
                }

        if not all_games:
            return None

        # 4. 시리즈 분류: DB sort_text(구분 컬럼) 값을 기준으로 분류
        # sort_text 값: "와일드카드" → wildcard, "준플레이오프" → semifinal,
        #               "플레이오프" → final, "한국시리즈" → ks
        series_map = {s["key"]: {"key": s["key"], "name": s["name"], "sort_key": s["sort_key"],
                                  "games": [], "teams": set()} for s in POSTSEASON_SERIES}

        # sort_text → series_key 매핑
        SORT_TEXT_TO_SERIES = {
            "와일드카드": "wildcard",
            "준플레이오프": "semifinal",
            "플레이오프": "final",
            "한국시리즈": "ks",
        }

        for gid, game in all_games.items():
            sort_text = game.get("sort_text", "")
            series_key = SORT_TEXT_TO_SERIES.get(sort_text)
            if series_key:
                series_map[series_key]["games"].append(game)
                series_map[series_key]["teams"].add(game["home_team"])
                series_map[series_key]["teams"].add(game["away_team"])
            else:
                # sort_text가 없거나 알 수 없는 값이면 game_id 키워드 기반 fallback
                gid_lower = gid.lower()
                assigned = False
                SERIES_KEYWORDS = {
                    "와일드카드": "wildcard", "wildcard": "wildcard",
                    "준플레이오프": "semifinal", "준PO": "semifinal",
                    "플레이오프": "final", "PO": "final",
                    "한국시리즈": "ks", "한국": "ks",
                }
                for keyword, sk in SERIES_KEYWORDS.items():
                    if keyword in gid_lower:
                        series_map[sk]["games"].append(game)
                        series_map[sk]["teams"].add(game["home_team"])
                        series_map[sk]["teams"].add(game["away_team"])
                        assigned = True
                        break
                if not assigned:
                    # fallback: 한국시리즈로 간주
                    series_map["ks"]["games"].append(game)
                    series_map["ks"]["teams"].add(game["home_team"])
                    series_map["ks"]["teams"].add(game["away_team"])

        # 5. 각 시리즈별 진행 상황 및 AI 예측 계산
        series_results = []
        for s in POSTSEASON_SERIES:
            key = s["key"]
            info = series_map[key]
            games = info["games"]
            teams = list(info["teams"])

            if not games:
                continue

            completed = [g for g in games if g["status"] == "completed"]
            scheduled = [g for g in games if g["status"] == "scheduled"]

            # 시리즈별 총 경기 수 (와일드카드: 최대 1경기, 준PO/PO: 최대 5경기, KS: 최대 7경기)
            if key == "wildcard":
                total_games = 1
            elif key == "ks":
                total_games = 7
            else:
                total_games = 5

            # 현재까지 승리한 팀 집계
            team_wins = {t: 0 for t in teams}
            for g in completed:
                if g["winning_team"] and g["winning_team"] != "무승부":
                    if g["winning_team"] in team_wins:
                        team_wins[g["winning_team"]] += 1

            # 시리즈 승자 결정 (필요 승수 달성 시)
            needed_wins = total_games // 2 + 1
            winner = None
            for t, w in team_wins.items():
                if w >= needed_wins:
                    winner = t
                    break

            # 시리즈 상태
            if winner:
                status = "completed"
            elif completed:
                status = "in_progress"
            else:
                status = "upcoming"

            # AI 예측: 아직 승자가 결정되지 않은 경우에만 예측
            predicted_winner = None
            if not winner and len(teams) >= 2:
                predicted_winner = cls._predict_series_winner(model, teams, games)

            series_results.append({
                "key": key,
                "name": s["name"],
                "sort_key": s["sort_key"],
                "teams": teams,
                "games": games,
                "completed_games": len(completed),
                "total_games": total_games,
                "winner": winner,
                "predicted_winner": predicted_winner,
                "status": status,
                "team_wins": team_wins,
            })

        # 6. 다음 시리즈 진출 예측
        next_series_prediction = cls._predict_next_series(series_results)

        return {
            "series": series_results,
            "next_series_prediction": next_series_prediction,
        }

    @classmethod
    def _predict_series_winner(cls, model, teams, games):
        """
        AI 모델로 특정 시리즈의 승자를 예측합니다.
        두 팀 간의 가상 대진을 생성하여 승률이 높은 팀을 반환합니다.
        """
        if len(teams) < 2:
            return None

        team_a, team_b = teams[0], teams[1]

        # 각 팀의 최신 피처 가져오기 (공통 헬퍼 사용)
        features_a = cls._get_team_latest_features(team_a)
        features_b = cls._get_team_latest_features(team_b)

        if not features_a or not features_b:
            return None

        # team_a를 홈, team_b를 원정으로 가정한 가상 대진 (공통 헬퍼 사용)
        virtual_match = pd.DataFrame([cls._build_virtual_match_row(features_a, features_b)])

        X = ModelPreprocessor.preprocess_data(virtual_match)
        prob = model.predict_proba(X)[0]  # [원정승 확률, 홈승 확률]
        home_win_prob = float(prob[1])

        if home_win_prob > 0.5:
            return {"team": team_a, "probability": round(home_win_prob, 3)}
        else:
            return {"team": team_b, "probability": round(1 - home_win_prob, 3)}

    @classmethod
    def _get_regular_season_top_teams(cls):
        """
        정규시즌 최종 순위 상위 5개 팀을 team_rank 테이블에서 조회합니다.
        Returns:
            dict: {"rank1": "팀명", "rank2": "팀명", ...}
        """
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT team_name, rank FROM team_rank
                    ORDER BY rank ASC LIMIT 5
                """)).fetchall()
                return {f"rank{row[1]}": row[0] for row in rows}
        except Exception:
            return {}

    @classmethod
    def _predict_next_series(cls, series_results):
        """
        현재 진행 상황을 바탕으로 다음 시리즈 진출팀을 예측합니다.
        """
        # 완료된 시리즈의 승자와 진행 중인 시리즈의 예측 승자를 조합
        advancement = {}
        for s in series_results:
            if s["winner"]:
                advancement[s["key"]] = s["winner"]
            elif s["predicted_winner"]:
                advancement[s["key"]] = s["predicted_winner"]["team"]

        # KBO 포스트시즌 진출 구조:
        # 정규시즌 1위 → 한국시리즈 직행
        # 정규시즌 2위 → 플레이오프 직행
        # 정규시즌 3위 → 준플레이오프 직행
        # 정규시즌 4위 → 와일드카드 (승자)
        # 정규시즌 5위 → 와일드카드 (패자, 4위와 1경기)
        #
        # 와일드카드 승자 → 준플레이오프 (3위와 대결)
        # 준플레이오프 승자 → 플레이오프 (2위와 대결)
        # 플레이오프 승자 → 한국시리즈 (1위와 대결)

        # 정규시즌 상위팀 정보 조회
        top_teams = cls._get_regular_season_top_teams()
        rank1 = top_teams.get("rank1", "1위팀")
        rank2 = top_teams.get("rank2", "2위팀")
        rank3 = top_teams.get("rank3", "3위팀")

        # 현재까지 확정된 진출팀
        wc_winner = advancement.get("wildcard")
        sf_winner = advancement.get("semifinal")
        final_winner = advancement.get("final")
        ks_winner = advancement.get("ks")

        # 다음 시리즈 예측 설명 생성
        predictions = []

        if wc_winner and not sf_winner:
            # 와일드카드 완료 → 준플레이오프 예측 (3위와 대결)
            predictions.append({
                "from_series": "wildcard",
                "to_series": "semifinal",
                "description": f"와일드카드 승자 {wc_winner}가 정규시즌 3위 {rank3}와 준플레이오프에서 맞붙습니다.",
                "predicted_matchup": [wc_winner, rank3],
            })

        if sf_winner and not final_winner:
            # 준플레이오프 완료 → 플레이오프 예측 (2위와 대결)
            predictions.append({
                "from_series": "semifinal",
                "to_series": "final",
                "description": f"준플레이오프 승자 {sf_winner}가 정규시즌 2위 {rank2}와 플레이오프에서 맞붙습니다.",
                "predicted_matchup": [sf_winner, rank2],
            })

        if final_winner and not ks_winner:
            # 플레이오프 완료 → 한국시리즈 예측 (1위와 대결)
            predictions.append({
                "from_series": "final",
                "to_series": "ks",
                "description": f"플레이오프 승자 {final_winner}가 정규시즌 1위 {rank1}과 한국시리즈에서 맞붙습니다.",
                "predicted_matchup": [final_winner, rank1],
            })

        return predictions


@router.get("/projection")
def get_projection():
    """AI가 예측한 시즌 최종 순위 리포트를 반환합니다."""
    result = SimulationService.get_season_projection()
    return {"status": "ok", "data": result}


@router.get("/postseason")
def get_postseason():
    """포스트시즌 대진표와 AI 예측 결과를 반환합니다."""
    try:
        result = SimulationService.get_postseason_bracket()
        if not result:
            return {"status": "ok", "data": None, "message": "포스트시즌 데이터가 없습니다."}
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포스트시즌 데이터 조회 실패: {str(e)}")
