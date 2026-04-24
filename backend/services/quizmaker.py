print("Script started")
import os
import json
import random
import re
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. 환경 설정 ---
load_dotenv(dotenv_path=".env")
print("Load dotenv done")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"DATABASE_URL exists: {bool(DATABASE_URL)}")
print(f"GEMINI_API_KEY exists: {bool(GEMINI_API_KEY)}")

if not DATABASE_URL or not GEMINI_API_KEY:
    raise RuntimeError("DATABASE_URL 또는 GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")

engine = create_engine(DATABASE_URL)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- 2. JSON 파싱 ---
def safe_parse_json(text: str):
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None

# --- 3. 난이도 자동 보정 ---
def analyze_difficulty(question: str) -> str:
    q = question.lower()
    if any(x in q for x in ["몇", "언제", "최다", "누가", "첫", "처음"]):
        return "쉬움"
    elif any(x in q for x in ["시즌", "비교", "통산", "평균", "기록"]):
        return "보통"
    else:
        return "어려움"

# --- 4. 퀴즈 생성 ---
def create_quizzes_from_ai(topic: str, count: int) -> list[dict] | None:
    print(f"🧠 '{topic}' 주제로 퀴즈 {count}개 생성 중...", flush=True)
    prompt = f"""
너는 KBO 기록 전문가야.
"삼성 라이온즈"의 "{topic}"과 관련된 퀴즈를 {count}개 만들어줘.

⚾ 반드시 다음 규칙을 지켜:
1. 모든 내용은 KBO 공식 기록 기준으로 정확해야 해.
2. 추정, 루머, 팬 의견은 절대 포함하지 마.
3. 출력은 반드시 JSON 배열만.
4. 각 항목은 반드시 "question", "answer", "difficulty"를 포함해야 해.
5. 난이도 기준:
   - '쉬움': 누구나 아는 대표 기록 (홈런 수, 연도, 별명 등)
   - '보통': 시즌별/선수별 비교 문제
   - '어려움': 특정 경기, 세부 기록, 드문 상황 관련 문제

예시:
[
  {{"question": "이승엽의 KBO 통산 홈런 수는?", "answer": "467개", "difficulty": "쉬움"}},
  {{"question": "삼성 라이온즈가 첫 통합우승을 차지한 해는?", "answer": "2011년", "difficulty": "보통"}}
]
"""
    try:
        print("API 호출을 시도합니다...")
        response = model.generate_content(prompt)
        print("API 호출 성공!")
        text = response.candidates[0].content.parts[0].text
        quizzes = safe_parse_json(text)
        if quizzes and isinstance(quizzes, list):
            for q in quizzes:
                if not q.get("difficulty"):
                    q["difficulty"] = analyze_difficulty(q.get("question", ""))
            return quizzes
    except Exception as e:
        print(f"❌ 퀴즈 생성 실패: {e}")
    return None

# --- 5. 오답 생성 ---
def get_distractors_from_ai(question: str, correct_answer: str) -> list[str] | None:
    prompt = f"""
"{question}"의 정답은 "{correct_answer}"야.
이와 헷갈릴만한 오답 3개를 만들어줘.
오답은 같은 카테고리여야 해 (예: 연도, 선수명, 수치 등).
JSON 배열만 출력해줘.
"""
    try:
        response = model.generate_content(prompt)
        text = response.candidates[0].content.parts[0].text
        data = safe_parse_json(text)
        if data and isinstance(data, list) and len(data) >= 3:
            return data[:3]
    except Exception as e:
        print(f"   - ❗ 오답 생성 실패: {e}")
    return None

# --- 6. 메인 실행 ---
def main():
    search_topics = [
        "이승엽 통산 기록", "양준혁 통산 기록", "오승환 세이브 기록",
        "삼성 라이온즈 우승 연도", "삼성 라이온즈 역대 감독",
        "한국시리즈 명장면", "팀 최다 홈런 시즌", "역대 외국인 선수 활약"
    ]
    TARGET_QUIZ_COUNT = 5
    total_generated = 0

    for topic in search_topics:
        quiz_subjects = create_quizzes_from_ai(topic, TARGET_QUIZ_COUNT)
        if not quiz_subjects:
            print(f"⚠️ {topic} 주제에서 퀴즈 생성 실패.")
            continue

        for q in quiz_subjects:
            question = q.get("question")
            answer = q.get("answer")
            difficulty = q.get("difficulty", analyze_difficulty(question))

            if not question or not answer:
                continue

            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM samfan_quizzes WHERE question=:q"),
                    {"q": question}
                ).fetchone()
                if exists:
                    print(f"   - ⚠️ 중복된 문제: {question}")
                    continue

            distractors = get_distractors_from_ai(question, answer)
            if not distractors:
                continue

            # ✅ [핵심 수정] 모든 옵션을 문자열로 강제 변환하여 DB 저장 에러 방지
            options = [str(d) for d in (distractors + [answer])]
            random.shuffle(options)

            quiz_data = {
                "question": question,
                "options": options,
                "correct_answer": str(answer),
                "difficulty": difficulty,
                "source_hint": topic
            }

            try:
                with engine.connect() as conn:
                    stmt = text("""
                        INSERT INTO samfan_quizzes
                        (question, options, correct_answer, difficulty, source_hint)
                        VALUES (:question, :options, :correct_answer, :difficulty, :source_hint)
                    """)
                    conn.execute(stmt, quiz_data)
                    conn.commit()
                total_generated += 1
                print(f"   ✅ [{difficulty}] {question}")
            except Exception as e:
                print(f"   ❌ DB 저장 실패: {e}")

            time.sleep(1.2)

    print(f"\n🎉 총 {total_generated}개의 퀴즈를 DB에 저장했습니다.")

if __name__ == "__main__":
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS samfan_quizzes (
                id SERIAL PRIMARY KEY,
                question TEXT,
                options TEXT[],
                correct_answer TEXT,
                difficulty TEXT,
                source_hint TEXT
            );
        """))
        conn.commit()
    main()
