# backend/stack_service/seed_history.py
# 삼성 라이온즈 역사 데이터 시드 스크립트 (1회 실행)
#
# Gemini API를 사용하여 1982년 창단부터 현재까지의
# 삼성 라이온즈 주요 역사적 사건 데이터를 생성하고
# samfan_history 테이블에 저장합니다.
#
# 사용 예:
#     python stack_service/seed_history.py

import os
import json
import re
import time
from datetime import datetime, date
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. 환경 설정 ---
# 프로젝트 루트의 .env 파일을 참조 (backend/stack_service/ → ../../ → 프로젝트 루트)
_env_path = os.path.join(os.path.dirname(__file__), "../../.env")
load_dotenv(dotenv_path=_env_path)
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DATABASE_URL or not GEMINI_API_KEY:
    raise RuntimeError("DATABASE_URL 또는 GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")

engine = create_engine(DATABASE_URL)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


# --- 2. JSON 파싱 ---
def safe_parse_json(text_content: str) -> list | None:
    """Gemini 응답에서 JSON 배열 부분만 추출하여 파싱합니다."""
    match = re.search(r'\[.*\]', text_content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# --- 3. 히스토리 데이터 생성 ---
def generate_history_batch(year: int) -> list[dict] | None:
    """특정 연도의 삼성 라이온즈 주요 사건을 생성합니다."""
    print(f"\n📅 {year}년 데이터 생성 중...", flush=True)

    prompt = f"""너는 삼성 라이온즈의 역사를 완벽하게 꿰뚫고 있는 KBO 데이터 전문가야.
    {year}년 삼성 라이온즈의 주요 사건(경기, 기록, 선수 이적, 수상 등)을 최대 10개까지 JSON 배열로 생성해 줘.

    [절대 지켜야 할 규칙]
    1. 정보의 정확성: KBO 공식 기록과 삼성 라이온즈 공식 구단 역사에 명확히 남아있는 교차 검증 가능한 사실(Fact)만 생성해. 추측, 루머는 절대 금지.
    2. 할루시네이션 방지: 각 이벤트의 `internal_verification` 필드에 해당 사실을 증명할 수 있는 구체적인 공식 기록(경기 날짜, 상대 팀, 기록 명칭 등)을 요약해서 적어.
    3. 다양한 카테고리: 정규시즌 경기, 포스트시즌, 선수 기록(홈런, 완봉승 등), 수상 내역, 구단 역사적 사건 등을 골고루 포함해.
    4. 중요한 사건 우선: 해당 연도에서 가장 의미 있고 팬들이 기억할 만한 사건을 우선적으로 선택해.
    5. 연도별 최소 기준:
       - 1982~1990: 창단 초기, 연간 3~5개
       - 1991~2000: 첫 우승 등, 연간 5~7개
       - 2001~2010: 왕조 전야, 연간 5~8개
       - 2011~2014: 통합 우승 왕조, 연간 8~10개
       - 2015~2020: 재건기, 연간 5~7개
       - 2021~2025: 최근, 연간 5~8개

    반드시 아래 JSON 형식의 배열로만 답변해:
    [
        {{
            "event_date": "YYYY-MM-DD",
            "date_text": "YYYY년 MM월 DD일",
            "event": "삼성 라이온즈의 주요 사건 설명 (50~120자)",
            "reference": "참고 링크 또는 출처 (예: 나무위키 키워드)",
            "internal_verification": "이 사실을 증명할 수 있는 구체적인 공식 기록 요약"
        }}
    ]

    중요: event_date는 반드시 실제 날짜여야 하며, 날짜를 특정할 수 없는 경우 해당 월의 1일로 설정해.
    {year}년에 해당하는 데이터만 생성하고, 다른 연도의 데이터는 절대 포함하지 마.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  API 호출 시도 {attempt + 1}/{max_retries}...", flush=True)
            response = model.generate_content(prompt)
            text_content = response.candidates[0].content.parts[0].text
            events = safe_parse_json(text_content)

            if events and len(events) > 0:
                print(f"  ✅ {len(events)}개 이벤트 생성됨", flush=True)
                return events
            else:
                print(f"  ⚠️ 생성된 이벤트가 없음, 재시도...", flush=True)
        except Exception as e:
            print(f"  ❌ 시도 {attempt + 1} 실패: {e}", flush=True)
            time.sleep(3)

    return None


# --- 4. DB 저장 ---
def save_history_events(events: list[dict]) -> int:
    """생성된 히스토리 이벤트를 samfan_history 테이블에 저장합니다."""
    saved_count = 0

    for ev in events:
        event_date_str = ev.get("event_date", "")
        date_text = ev.get("date_text", "")
        event_desc = ev.get("event", "")
        reference = ev.get("reference", "")
        verification = ev.get("internal_verification", "")

        # 필수 필드 검증
        if not event_date_str or not event_desc:
            print(f"  ⚠️ 필수 필드 누락, 건너뜀: {ev}", flush=True)
            continue

        # 중복 체크
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM samfan_history WHERE event_date=:d AND event=:e"),
                {"d": event_date_str, "e": event_desc}
            ).fetchone()
            if exists:
                print(f"  ⏭️ 중복 건너뜀: {event_date_str} - {event_desc[:30]}...", flush=True)
                continue

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO samfan_history (event_date, date_text, event, reference)
                        VALUES (:event_date, :date_text, :event, :reference)
                    """),
                    {
                        "event_date": event_date_str,
                        "date_text": date_text,
                        "event": event_desc,
                        "reference": reference
                    }
                )
            saved_count += 1
            print(f"  ✅ 저장: {event_date_str} - {event_desc[:40]}...", flush=True)
        except Exception as e:
            print(f"  ❌ DB 저장 실패 ({event_date_str}): {e}", flush=True)

    return saved_count


# --- 5. 메인 실행 ---
def main():
    print("=" * 60)
    print("🏟️  삼성 라이온즈 역사 데이터 시드 스크립트")
    print("=" * 60)

    # samfan_history 테이블이 없으면 생성
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS samfan_history (
                id SERIAL PRIMARY KEY,
                event_date DATE NOT NULL,
                date_text TEXT,
                event TEXT,
                reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
    print("✅ samfan_history 테이블 확인 완료")

    # 기존 데이터 확인
    with engine.connect() as conn:
        existing_count = conn.execute(
            text("SELECT COUNT(*) FROM samfan_history")
        ).scalar()
    print(f"📊 기존 데이터: {existing_count}개")

    if existing_count > 0:
        print("⚠️  이미 데이터가 존재합니다. 추가로 데이터를 생성하려면 계속 진행합니다.")
        print("    처음부터 다시 하려면 테이블을 비우고 실행하세요.")
        print("    (TRUNCATE samfan_history; 또는 DROP TABLE samfan_history;)")

    # 1982년부터 2025년까지 순차적으로 생성
    start_year = 1982
    end_year = 2025
    total_saved = 0

    for year in range(start_year, end_year + 1):
        events = generate_history_batch(year)
        if events:
            saved = save_history_events(events)
            total_saved += saved
            print(f"  → {year}년: {saved}개 저장 완료 (누적: {total_saved}개)", flush=True)
        else:
            print(f"  → {year}년: 데이터 생성 실패", flush=True)

        # API rate limiting 방지를 위한 지연
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"🏁 전체 완료! 총 {total_saved}개 이벤트 저장됨")
    print("=" * 60)


if __name__ == "__main__":
    main()
