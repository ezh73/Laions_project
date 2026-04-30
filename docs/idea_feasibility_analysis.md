# idea.md 아이디어 구현 가능성 분석

> 분석일: 2026-04-30
> 기준: Laions_project 전체 코드베이스 (백엔드 + 프론트엔드 + DB 스키마)

---

## ⚠️ 중요: AI API 비용 상황

| API | 상태 | 비용 |
|-----|:----:|:----:|
| **Gemini 2.5 Flash** (현재 quizmaker 사용 중) | 무료 할당량 소멸 | **유료** |
| **DeepSeek Chat** (퀴즈 생성 대체 예정) | 저렴하지만 Web Search 없음 | 입력 $0.27/1M tokens, 출력 $1.10/1M tokens |
| **Tavily Search** (Web Search 대안) | 월 1000회 무료 | 초과 시 $0.10/검색 |

**결론**: Gemini 무료 할당량이 사라졌으므로, DeepSeek으로 퀴즈 생성기를 대체하는 기존 계획은 유효. 하지만 Web Search가 필요한 기능은 Tavily를 추가해야 하는데, 이는 또 다른 API 키와 비용 관리가 필요함.

---

## 아이디어 1: 연도별 삼성 라이온즈 순위 섹션

### 요약
1982~2025년까지의 삼성 라이온즈 역대 전력을 하나의 리그로 가정하고 시뮬레이션하여 파워지수 랭킹을 산출, Top 10을 프론트에 출력.

### 구현 가능성: ✅ 가능 (AI API 불필요)

#### 필요한 데이터
- **1982~2025년 삼성 라이온즈 전체 경기 데이터** (정규시즌 + 포스트시즌)
  - 현재 DB에는 `kbo_games` 테이블에 2021~2025년 데이터만 존재
  - 1982~2020년 데이터는 **별도 수집 필요**

#### 수집 방안
1. **KBO API 활용**: 현재 [`crawler_service.py`](backend/services/crawler_service.py:14)는 `koreabaseball.com` API 사용. 연도 파라미터만 변경하면 1982년부터 데이터 수집 가능 (`srIdList="0"`로 정규시즌 데이터)
2. **크롤링 검증 필요**: 1982~2000년 데이터는 KBO API가 지원하는 범위인지 확인 필요

#### 구현 방법
- **백엔드**: [`simulation_service.py`](backend/services/simulation_service.py:13)의 `get_season_projection()` 로직을 재사용. 연도별로 팀 데이터를 분리하여 각 연도의 삼성 라이온즈 전력(ELO, Form 등)을 산출한 후, 연도 간 가상 대진 시뮬레이션
- **프론트엔드**: 새로운 컴포넌트 `HistoricalPowerRankingCard` 생성, Top 10 테이블 표시

#### 난이도: 중간
- **AI API 불필요** — 추가 비용 없음
- 데이터 수집이 가장 큰 변수
- 시뮬레이션 로직은 기존 코드 재사용 가능

---

## 아이디어 2: 삼성 선수의 역대 순위

### 검토 결과: ❌ 제외 (단발성 콘텐츠)
- 한 번 구축하면 업데이트할 필요가 없는 정적 데이터
- 사용자가 매일 방문할 이유를 만들어주지 못함
- 수동 데이터셋 구축에 시간 대비 효과가 낮음

---

## 아이디어 3: 팬들과 AI가 선정하는 삼성 라이온즈 올스타

### 검토 결과: ❌ 제외 (단발성 콘텐츠)
- 아이디어 2와 동일한 이유로 단발성 콘텐츠
- 팬 투표 기능만 따로 구현해도 시즌 단위로만 운영 가능
- AI 선정은 데이터 부족 + 비용 문제

---

## 아이디어 4: 오늘의 역사 섹션

### 요약
삼성 라이온즈의 오늘 날짜 과거 기록 표시 (예: 2010년 4월 30일 팀 2만 안타 달성).

### 구현 가능성: ✅ 가능 (AI API 불필요) — **가장 추천**

#### 데이터 수집 방안

**추천: 수동 데이터셋 구축 (AI API 비용 0원)**

삼성 라이온즈의 주요 역사적 기록은 예상보다 많지 않습니다:
- 한국시리즈 우승: 1985, 2002, 2005, 2006, 2011, 2012, 2013, 2014 (총 8회)
- 영구결번: 10번 (양준혁), 36번 (이승엽)
- 주요 기록: 팀 2만 안타, 이승엽 40홈런(2002), 56홈런(2003), 최형우 끝내기 등
- 구단 창단: 1982년 2월

**예상 규모**: 약 50~80개의 이벤트면 1년 365일 중 많은 날을 커버 가능
- 하루에 여러 개의 이벤트가 있을 수 있음 (예: 10월 30일에는 여러 기록 존재)
- 이벤트가 없는 날은 "오늘은 특별한 기록이 없습니다" 메시지 표시

**수집 출처**:
- 삼성 라이온즈 공식 홈페이지 역사관
- 나무위키 "삼성 라이온즈/역대 기록" 문서
- KBO 공식 기록실

#### DB 스키마

```sql
CREATE TABLE historical_events (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,          -- 실제 발생 날짜 (예: 2010-04-30)
    month_day VARCHAR(5) NOT NULL,      -- 월일 인덱스용 (예: '04-30')
    title VARCHAR(200) NOT NULL,        -- 이벤트 제목
    description TEXT,                   -- 상세 설명
    category VARCHAR(50),              -- '기록', '경기', '구단', '기타'
    reference_link TEXT,               -- 참고 링크 (나무위키 등)
    importance INTEGER DEFAULT 1,      -- 중요도 (1-5, 정렬용)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_historical_month_day ON historical_events(month_day);
```

#### 백엔드 API

```python
# backend/main.py에 추가
@app.get("/api/history/today")
def get_today_history():
    """오늘 날짜(월일)와 일치하는 삼성 라이온즈 역사적 이벤트를 반환합니다."""
    today_md = CURRENT_DATE.strftime("%m-%d")
    with engine.connect() as conn:
        events = conn.execute(
            text("""
                SELECT id, title, description, category, reference_link, importance
                FROM historical_events
                WHERE month_day = :md
                ORDER BY importance DESC, event_date DESC
                LIMIT 5
            """),
            {"md": today_md}
        ).fetchall()
        return {
            "status": "ok",
            "date": str(CURRENT_DATE),
            "events": [
                {
                    "id": e[0], "title": e[1], "description": e[2],
                    "category": e[3], "reference_link": e[4], "importance": e[5]
                }
                for e in events
            ]
        }
```

#### 프론트엔드 컴포넌트

```jsx
// frontend/src/components/TodayInHistoryCard.js
// Dashboard.js에 추가하여 좌측 열 또는 우측 열에 배치
// MUI Card로 디자인, 삼성 라이온즈 구단 색상 강조
// 이벤트가 없을 경우 "오늘은 특별한 기록이 없습니다" 메시지 표시
```

#### 난이도: 낮음
- **AI API 불필요** — 추가 비용 없음
- DB 테이블 1개 추가
- API 엔드포인트 1개 추가
- 프론트 컴포넌트 1개 추가
- 데이터셋 50~80개 수동 구축 (가장 시간이 걸리는 부분)

---

## 아이디어 5: AI가 뽑은 오늘의 키플레이어

### 검토 결과: ❌ 보류
- 선수 개인 스탯 데이터 없음
- 매일 LLM API 호출 필요 → 지속적인 비용 발생
- 할루시네이션 리스크

---

## 종합 평가 (최종)

| 아이디어 | 결정 | 사유 |
|----------|:----:|------|
| 1. 연도별 순위 | ✅ **진행** | AI API 불필요, 기존 코드 재사용 가능 |
| 2. 선수 역대 순위 | ❌ **제외** | 단발성 콘텐츠, 데이터 구축 대비 효과 낮음 |
| 3. 팬+AI 올스타 | ❌ **제외** | 단발성 콘텐츠, AI 선정은 데이터+비용 문제 |
| 4. 오늘의 역사 | ✅ **진행 (최우선)** | AI API 불필요, 난이도 낮음, 매일 방문 유도 |
| 5. AI 키플레이어 | ❌ **보류** | 데이터 부족 + 지속적 AI 비용 |

### 최종 추천

**AI API 비용을 고려한 현실적인 접근:**

1. **오늘의 역사 섹션 (아이디어 4)** — ✅ **최우선 추천**
   - AI API 불필요, 난이도 낮음
   - 수동 데이터셋 50~80개만 구축
   - 삼성 팬사이트 색깔을 가장 확실하게 살림
   - 매일 다른 내용 → 사용자 재방문 유도

2. **연도별 순위 (아이디어 1)** — ✅ **추천**
   - AI API 불필요, 기존 코드 재사용
   - KBO API로 데이터 수집 가능
   - 현재 시즌 파워지수는 모델이 실시간 계산

### 핵심 제언

- **DeepSeek은 퀴즈 생성용으로만 사용** (기존 리팩토링 계획 유지)
- Web Search가 필요한 기능은 비용/데이터 문제로 보류
- `idea.md`는 원본 보존, `plans/idea_feasibility_analysis.md`에서 최종 결정 사항 관리






# 중요 문제 발견
- 지금까지 사용하던 스크래핑 방식인 /ws/ 사용이 kbo robots.txt에서 허락하지 않는 방식임, 스크래핑 방식 자체를 전면 수정해야함