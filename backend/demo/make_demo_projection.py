# make_demo_projection_fixed.py
import pandas as pd
import joblib
from sqlalchemy import create_engine, text
import os
import numpy as np

engine = create_engine(os.getenv("DATABASE_URL"))
model = joblib.load("lgbm_kbo_predictor_tuned.pkl")

# 1️⃣ 25시즌 경기 데이터 불러오기
df = pd.read_sql(text("""
    SELECT * FROM kbo_cleaned_games WHERE EXTRACT(YEAR FROM game_date) = 2025
"""), engine)

teams = sorted(df["home_team"].unique())
results = []

for team in teams:
    # 팀 스탯 계산
    games = df[(df["home_team"] == team) | (df["away_team"] == team)]
    if len(games) < 10:
        continue

    # 간단한 스탯 계산
    scored = (games.apply(lambda x: x["home_score"] if x["home_team"] == team else x["away_score"], axis=1)).sum()
    allowed = (games.apply(lambda x: x["away_score"] if x["home_team"] == team else x["home_score"], axis=1)).sum()
    form = ((games["home_team"] == team) & (games["home_score"] > games["away_score"]) |
            ((games["away_team"] == team) & (games["away_score"] > games["home_score"]))).rolling(10, min_periods=1).mean().iloc[-1]
    pyth = scored**2 / (scored**2 + allowed**2)
    elo = 1500 + (form - 0.5) * 400

    results.append({
        "team": team,
        "elo": elo,
        "form": form,
        "pyth": pyth
    })

team_df = pd.DataFrame(results)

# 2️⃣ 모든 팀 쌍 조합 생성 (시뮬레이션용)
pairs = []
for team in team_df.itertuples():
    for opp in team_df.itertuples():
        if team.team == opp.team:
            continue
        pairs.append({
            "samsung_elo": team.elo,
            "opponent_elo": opp.elo,
            "rest_diff": 0,
            "samsung_form": team.form,
            "opponent_form": opp.form,
            "samsung_pythagorean": team.pyth,
            "opponent_pythagorean": opp.pyth,
            "team": team.team,
            "opponent": opp.team
        })

pairs_df = pd.DataFrame(pairs)

# 3️⃣ 예측 수행
X = pairs_df[[
    "samsung_elo",
    "opponent_elo",
    "rest_diff",
    "samsung_form",
    "opponent_form",
    "samsung_pythagorean",
    "opponent_pythagorean"
]]
pairs_df["predicted_win"] = model.predict_proba(X)[:, 1]

# 4️⃣ 팀별 평균 승률 계산
summary = pairs_df.groupby("team")["predicted_win"].mean().reset_index()
summary["predicted_wins"] = (summary["predicted_win"] * 144).round(0)
summary["predicted_losses"] = 144 - summary["predicted_wins"]
summary["AvgRank"] = summary["predicted_win"].rank(ascending=False)
summary["PlayoffProb"] = (1 - (summary["AvgRank"] - 1) / len(summary))
summary["playoff_probability"] = summary["PlayoffProb"]

os.makedirs("data/demo", exist_ok=True)
summary.to_csv("data/demo/season_projection_demo.csv", index=False)
print("✅ 모델 기반 season_projection_demo.csv 생성 완료 (25시즌 → 26시즌 예측)")
