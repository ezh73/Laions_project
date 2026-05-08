# backend/services/weekly_quizmaker.py
"""
주간 퀴즈 생성 서비스
매주 월요일 GitHub Actions에서 실행됩니다.
최근 1주일간의 삼성 라이온즈 경기 결과와 시즌 이슈를 반영한 퀴즈를 생성합니다.

사용 예:
    from services.weekly_quizmaker import WeeklyQuizMaker
    WeeklyQuizMaker.generate_weekly_quizzes()
"""
import os
import json
import random
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from sqlalchemy import text
from dotenv import load_dotenv
import google.generativeai as genai

from config import engine, CURRENT_DATE

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")


class WeeklyQuizMaker:
    """주간 퀴즈 생성기 - 최근 경기 데이터를 반영한 퀴즈 생성"""

    @staticmethod
    def _safe_parse_json(text_content: str):
        """JSON 배열 부분만 추출하여 파싱합니다."""
        match = re.search(r'\[.*\]', text_content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _get_recent_games_context(days: int = 7) -> str:
        """
        최근 N일간의 삼성 라이온즈 경기 결과를 조회하여 컨텍스트 문자열을 생성합니다.
        
        Args:
            days: 조회할 기간 (일)
        
        Returns:
            str: 최근 경기 요약 문자열
        """
        try:
            since_date = CURRENT_DATE - timedelta(days=days)
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT game_date, home_team, away_team, home_score, away_score, winning_team
                    FROM kbo_games
                    WHERE game_date >= :since
                      AND (home_team = '삼성' OR away_team = '삼성')
                    ORDER BY game_date DESC
                """), {"since": since_date}).fetchall()

            if not rows:
                return "최근 1주일간 삼성 라이온즈의 경기 결과가 없습니다."

            context_lines = ["[최근 1주일간 삼성 라이온즈 경기 결과]"]
            for r in rows:
                if r.winning_team == '삼성':
                    result = "승"
                elif r.winning_team and r.winning_team != '무승부':
                    result = "패"
                else:
                    result = "무"
                context_lines.append(
                    f"- {r.game_date}: {r.away_team} {r.away_score} vs {r.home_team} {r.home_score} ({result})"
                )
            return "\n".join(context_lines)
        except Exception as e:
            print(f"⚠️ 최근 경기 조회 중 오류: {e}")
            return ""

    @staticmethod
    def _get_season_standings_context() -> str:
        """현재 리그 순위 정보를 조회하여 컨텍스트를 생성합니다."""
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT team_name, rank, wins, losses, draws, win_rate
                    FROM team_rank
                    ORDER BY rank ASC
                """)).fetchall()

            if not rows:
                return ""

            context_lines = ["[현재 KBO 리그 순위]"]
            for r in rows:
                context_lines.append(
                    f"- {r.rank}위: {r.team_name} ({r.wins}승 {r.losses}패 {r.draws}무, 승률 {r.win_rate:.3f})"
                )
            return "\n".join(context_lines)
        except Exception as e:
            print(f"⚠️ 순위 조회 중 오류: {e}")
            return ""

    @classmethod
    def generate_weekly_quizzes(cls) -> list[dict] | None:
        """
        최근 경기 데이터를 기반으로 주간 퀴즈 3개(쉬움/보통/어려움)를 생성합니다.
        
        Returns:
            list[dict] | None: 생성된 퀴즈 리스트 또는 None
        """
        today_str = CURRENT_DATE.strftime("%Y년 %m월 %d일")
        recent_games = cls._get_recent_games_context()
        standings = cls._get_season_standings_context()

        print(f"🧠 주간 퀴즈 생성 중... (기준일: {today_str})", flush=True)

        prompt = f"""
        너는 삼성 라이온즈의 역사를 완벽하게 꿰뚫고 있는 KBO 데이터 전문가야.
        오늘은 {today_str}이고, 아래는 최근 경기 결과와 리그 순위야.

        {recent_games}

        {standings}

        위 최신 데이터를 참고하여, 2026년 현재 시즌의 삼성 라이온즈 관련 퀴즈를 
        [쉬움, 보통, 어려움] 난이도별로 각각 1문제씩 총 3개의 객관식(4지선다) 퀴즈를 출제해 줘.
        최근 경기 결과와 선수 활약을 반영한 문제를 우선적으로 출제하고, 
        필요시 삼성 라이온즈의 역사적 기록도 함께 활용해.

        [절대 지켜야 할 규칙]
        1. 정보의 정확성: KBO 공식 기록과 삼성 라이온즈 공식 구단 역사에 명확히 남아있는 사실(Fact)만 출제해.
        2. 할루시네이션 방지: `internal_verification` 필드에 정답을 증명할 수 있는 구체적인 공식 기록을 요약해서 적어.
        3. reference_keyword: 유저가 더 찾아볼 수 있도록 2~3단어 이내의 명사형 키워드를 적어줘.
        4. 난이도 기준:
           - "쉬움": 최근 활약 중인 선수 위주, 라팍 상식, 기본 기록
           - "보통": 시즌 주요 기록, 팀 성적, 선수별 시즌 성과
           - "어려움": 세부 스탯, 특정 상황 기록, 역대 기록과의 비교

        반드시 아래 JSON 형식의 배열로만 답변해.
        [
        {{
            "difficulty": "쉬움",
            "question": "퀴즈 질문",
            "correct_answer": "정답",
            "distractors": ["오답1", "오답2", "오답3"],
            "explanation": "정답 설명",
            "internal_verification": "검증 근거",
            "reference_keyword": "검색 키워드"
        }}
        ]
        """

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"   API 호출 시도 {attempt + 1}/{max_retries}...")
                response = gemini_model.generate_content(prompt)
                text_content = response.candidates[0].content.parts[0].text
                quizzes = cls._safe_parse_json(text_content)

                if quizzes and len(quizzes) == 3:
                    return quizzes
                print(f"   ⚠️ 퀴즈 개수 불일치 ({len(quizzes) if quizzes else 0}개), 재시도...")
            except Exception as e:
                print(f"   ❌ 시도 {attempt + 1} 실패: {e}")
                time.sleep(2)

        return None

    @classmethod
    def save_quizzes(cls, quizzes: list[dict]) -> int:
        """
        생성된 퀴즈를 DB에 저장합니다.
        
        Args:
            quizzes: 저장할 퀴즈 리스트
        
        Returns:
            int: 저장 성공한 퀴즈 개수
        """
        success_count = 0
        for q in quizzes:
            question = q.get("question")
            correct_answer = q.get("correct_answer")
            distractors = q.get("distractors", [])
            difficulty = q.get("difficulty")
            explanation = q.get("explanation")
            verification = q.get("internal_verification")
            ref_keyword = q.get("reference_keyword", "")

            # 나무위키 링크 생성
            ref_link = ""
            if ref_keyword:
                encoded_kw = urllib.parse.quote(ref_keyword)
                ref_link = f"https://namu.wiki/w/{encoded_kw}"

            # 중복 체크
            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM samfan_quizzes WHERE question = :q"),
                    {"q": question}
                ).fetchone()
                if exists:
                    print(f"   ⏭️ 중복 건너뜀: [{difficulty}] {question}")
                    continue

            options = [str(d) for d in (distractors[:3] + [correct_answer])]
            random.shuffle(options)

            quiz_data = {
                "question": question,
                "options": options,
                "correct_answer": str(correct_answer),
                "difficulty": difficulty,
                "explanation": explanation,
                "internal_verification": verification,
                "reference_link": ref_link
            }

            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO samfan_quizzes
                        (question, options, correct_answer, difficulty, explanation, internal_verification, reference_link)
                        VALUES (:question, :options, :correct_answer, :difficulty, :explanation, :internal_verification, :reference_link)
                    """), quiz_data)
                success_count += 1
                print(f"   ✅ [{difficulty}] {question}")
            except Exception as e:
                print(f"   ❌ DB 저장 실패: {e}")

        return success_count

    @classmethod
    def run(cls) -> dict:
        """
        주간 퀴즈 생성 파이프라인을 실행합니다.
        
        Returns:
            dict: 실행 결과 요약
        """
        print(f"\n{'='*60}")
        print(f"📅 주간 퀴즈 생성 시작 (기준일: {CURRENT_DATE})")
        print(f"{'='*60}\n")

        quizzes = cls.generate_weekly_quizzes()
        if not quizzes:
            print("🚨 퀴즈 생성 실패")
            return {"status": "error", "message": "퀴즈 생성 실패", "count": 0}

        saved = cls.save_quizzes(quizzes)
        print(f"\n🎉 주간 퀴즈 생성 완료: {saved}개 저장됨")

        return {"status": "ok", "message": f"{saved}개 퀴즈 저장 완료", "count": saved}


if __name__ == "__main__":
    load_dotenv()
    WeeklyQuizMaker.run()
