import os
import json
import random
import re
import time
import urllib.parse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

# --- 1. 환경 설정 ---
load_dotenv(dotenv_path=".env")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DATABASE_URL or not GEMINI_API_KEY:
    raise RuntimeError("DATABASE_URL 또는 GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")

engine = create_engine(DATABASE_URL)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- 2. JSON 파싱 ---
def safe_parse_json(text_content: str):
    # JSON 배열 부분만 추출
    match = re.search(r'\[.*\]', text_content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None

# --- 3. 퀴즈 생성 로직 ---
def generate_daily_quizzes() -> list[dict] | None:
    print("🧠 오늘의 삼성 라이온즈 퀴즈(하, 중, 상) 생성 중...", flush=True)
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    
    prompt = f"""
    너는 삼성 라이온즈의 역사를 완벽하게 꿰뚫고 있는 KBO 데이터 전문가야. 너는 1982년 KBO 출범부터 2025년까지 삼성 라이온즈의 모든 공식 기록과 역사를 정확히 알고 있고 2026년 현재 시즌({today_str} 기준) 경기 또한 매일 챙겨보며 분석하는 열성팬이기도 해.
    오늘의 삼성 라이온즈 팬들을 위해 [쉬움, 보통, 어려움] 난이도별로 각각 1문제씩 총 3개의 객관식(4지선다) 퀴즈를 출제해 줘.

    [절대 지켜야 할 규칙]
    1. 정보의 정확성: KBO 공식 기록과 삼성 라이온즈 공식 구단 역사에 명확히 남아있는 교차 검증 가능한 사실(Fact)만 출제해. 추측, 루머는 절대 금지, 블로그나 커뮤니티 같은 공신력 없는 자료도 참고하지 말것.
    2. 할루시네이션 방지: `internal_verification` 필드에 해당 문제의 정답을 증명할 수 있는 구체적인 공식 기록(연도, 상대 팀, 기록 명칭 등)을 요약해서 적어. 이 필드를 작성하면서 논리적 오류가 있다면 문제를 처음부터 다시 만들어.

    3. 더 알아보기 키워드: 유저가 정답에 대해 나무위키 등에서 더 찾아볼 수 있도록, 핵심 검색 키워드(선수명, 사건명 등)를 `reference_keyword` 필드에 적어줘, 키워드가 너무 길어지면 검색이 힘드니 2~3단어 이내의 명사형으로 작성해.

    4. 난이도별 명확한 맥락 기준 예시:
       - "쉬움": 삼성 라이온즈 최근 인기선수 위주(구자욱, 강민호 등), 라팍 관련 상식, 이승엽/양준혁 등 레전드의 가장 유명한 기록 등 (야구장 몇 번 가본 팬 수준), 선택지의 오답이 어렵지 않게 작성
       - "보통": 2011~2014 왕조 시절의 핵심 기록, 영구결번 선수 기록, 오랜 기간 삼성 라이온즈에서 활동한 프랜차이즈 스타의 기록 등 (꾸준히 응원한 팬 수준), 선택지의 오답은 정답과 헷갈릴 수 있게 작성
       - "어려움": 특정 연도의 세부 스탯, 1차 지명 신인, 과거 80~90년대 기록, 특이 상황에 대한 기록 등 (위키피디아를 찾아볼 골수팬 수준), 선택지의 오답은 매력적이고 논리적으로 정답과 헷갈리도록 어렵게 작성
       - 중복된 문제를 피하고 예시에 적힌 주제만이 아닌 투수/타자/팀기록/역사 등 다양한 카테고리를 골고루 다뤄줘.

    반드시 아래 JSON 형식의 배열로만 답변하고 아래 답변은 오답이 섞였으니 잘 검증하고 문제를 출제하도록 해.
    [
    {
        "difficulty": "어려움",
        "question": "2014년 한국시리즈 5차전에서 9회말 2아웃에 역전 끝내기 홈런을 친 삼성 라이온즈 선수는 누구일까요?",
        "correct_answer": "최형우",
        "distractors": ["이승엽", "박한이", "나바로"],
        "explanation": "2014년 넥센 히어로즈와의 한국시리즈 5차전, 1-2로 뒤진 9회말 2아웃 1,3루 상황에서 최형우 선수가 역전 끝내기 2루타(홈런 아님, 문제 자체가 함정일 경우 스스로 수정해야 함)를 쳤습니다.",
        "internal_verification": "2014년 KBO 한국시리즈 5차전 삼성 vs 넥센 경기 기록 (최형우 9회말 2타점 끝내기 2루타)",
        "reference_keyword": "2014년 한국시리즈 5차전"

    }
    ]
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"API 호출 시도 {attempt + 1}/{max_retries}...")
            response = model.generate_content(prompt)
            text_content = response.candidates[0].content.parts[0].text
            quizzes = safe_parse_json(text_content)
            
            if quizzes and len(quizzes) == 3:
                return quizzes
        except Exception as e:
            print(f"❌ 시도 {attempt + 1} 실패: {e}")
            time.sleep(2)
            
    return None

# --- 4. 메인 실행 및 DB 저장 ---
def main():
    quizzes = generate_daily_quizzes()
    if not quizzes:
        print("🚨 퀴즈 생성 실패")
        return

    success_count = 0
    for q in quizzes:
        question = q.get("question")
        correct_answer = q.get("correct_answer")
        distractors = q.get("distractors", [])
        difficulty = q.get("difficulty")
        explanation = q.get("explanation")
        verification = q.get("internal_verification")
        ref_keyword = q.get("reference_keyword", "")

        # 나무위키 링크 생성 로직
        ref_link = ""
        if ref_keyword:
            encoded_kw = urllib.parse.quote(ref_keyword)
            ref_link = f"https://namu.wiki/w/{encoded_kw}"

        # 중복 체크
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM samfan_quizzes WHERE question=:q"),
                {"q": question}
            ).fetchone()
            if exists: continue

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
            with engine.connect() as conn:
                stmt = text("""
                    INSERT INTO samfan_quizzes
                    (question, options, correct_answer, difficulty, explanation, internal_verification, reference_link)
                    VALUES (:question, :options, :correct_answer, :difficulty, :explanation, :internal_verification, :reference_link)
                """)
                conn.execute(stmt, quiz_data)
                conn.commit()
            success_count += 1
            print(f"   ✅ [{difficulty}] {question}")
        except Exception as e:
            print(f"   ❌ DB 저장 실패: {e}")

    print(f"\n🎉 {success_count}개 저장 완료.")

if __name__ == "__main__":
    # 테이블 생성 스키마 업데이트
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS samfan_quizzes (
                id SERIAL PRIMARY KEY,
                question TEXT,
                options TEXT[],
                correct_answer TEXT,
                difficulty TEXT,
                explanation TEXT,
                internal_verification TEXT,
                reference_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()
    main()