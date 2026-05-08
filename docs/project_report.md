# Laions 프로젝트 종합 보고서

> **최종 업데이트**: 2026-05-08
> **프로젝트**: 삼성 라이온즈 팬을 위한 AI 기반 야구 예측 플랫폼

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [완료된 작업 목록](#3-완료된-작업-목록)
4. [Phase 1: Critical 수정 내역](#4-phase-1-critical-수정-내역)
5. [Phase 2: Major 수정 내역](#5-phase-2-major-수정-내역)
6. [Phase 3: Minor 수정 내역](#6-phase-3-minor-수정-내역)
7. [추가 수정 사항](#7-추가-수정-사항)
8. [최종 파일 구조](#8-최종-파일-구조)
9. [변경 파일 목록](#9-변경-파일-목록)
10. [부록](#10-부록)

---

## 1. 프로젝트 개요

**Laions**는 삼성 라이온즈 팬을 위한 AI 기반 야구 예측 플랫폼입니다. LightGBM 모델로 경기 결과를 예측하고, 팬들이 AI와 승부를 겨루며 점수를 쌓는 게이미피케이션 요소를 제공합니다.

### 기술 스택

| 항목 | 내용 |
|------|------|
| **Frontend** | React 19 + MUI v7 + Supabase Auth |
| **Backend** | FastAPI + SQLAlchemy + LightGBM |
| **Database** | PostgreSQL (Supabase) |
| **AI Model** | LightGBM (ELO + Form + 상대전적 피처) |
| **Scheduler** | GitHub Actions (매일 KST 01:00) |
| **Infra** | Docker Compose (Nginx proxy) |

### 주요 기능

| 기능 | 설명 |
|------|------|
| **AI 승리예측 대결** | LightGBM 기반 AI 모델의 경기 결과 예측과 사용자 예측 대결, AI가 틀린 경기를 맞추면 가산점 부여 |
| **AI 퀴즈** | Gemini AI로 생성된 퀴즈를 난이도별로 풀며 재미와 학습을 동시에 제공 |
| **주간 팬 랭킹** | 예측 점수 + 퀴즈 점수 합산으로 팬들 간 순위 경쟁, 매주 월요일 리셋 |
| **리그 순위** | 스크래핑된 DB 데이터 기반 KBO 리그 순위 계산 및 출력, 삼성 라이온즈 강조 |
| **오늘의 삼성 라이온즈 역사** | 당일 날짜의 과거 삼성 라이온즈 역사적 사실 출력 |
| **모드 분할** | 일반모드(정규시즌/포스트시즌/오프시즌) + 관리자모드(날짜 강제 주입) |

### 모드별 동작

| 모드 | 설명 |
|------|------|
| **정규시즌** | 오늘 경기 일정 스크래핑 → AI 승리 예측 → 사용자 예측 대결 |
| **포스트시즌** | 포스트시즌 일정 스크래핑 → AI 승리 예측 + 다음 시리즈 진출팀 예측 |
| **오프시즌** | 전체 시즌 결과 반영 → 다음 시즌 순위 시뮬레이션 예측 |
| **관리자모드** | `CURRENT_DATE`를 강제 주입하여 특정 날짜 기준 시스템 검증, 트랜잭션 롤백으로 DB 미오염 |

---

## 2. 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Scheduler)                │
│  daily_pipeline.yml ── 매일 KST 01:00 실행                   │
│    ├─ daily_pipeline.py (스크래핑 → 피처 → 예측 → 정산)      │
│    └─ weekly_quizmaker.py (월요일만: 퀴즈 생성)              │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Server (main.py)                  │
│                                                              │
│  ┌─ services/ ──────────────────────────────────────────┐   │
│  │  crawler_service.py   ← Daum Sports 스크래핑          │   │
│  │  feature_service.py   ← ELO/Form/Streak 피처 계산     │   │
│  │  model_service.py     ← LightGBM 예측 실행            │   │
│  │  simulation_service.py ← 시즌/포스트시즌 시뮬레이션   │   │
│  │  ranking_service.py   ← 점수 정산/랭킹 조회           │   │
│  │  performance_service.py ← 모델 정확도 계산            │   │
│  │  weekly_quizmaker.py  ← 주간 퀴즈 생성 (월요일)       │   │
│  │  model_preprocessor.py ← 피처 전처리                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ stack_service/ ─────────────────────────────────────┐   │
│  │  seed_crawler.py    ← 2007~2025 과거 데이터 수집     │   │
│  │  seed_history.py    ← 1982~2025 역사 데이터 생성     │   │
│  │  seed_model.py      ← 초기 모델 1회 학습             │   │
│  │  quizmaker.py       ← 1982~2025 퀴즈 대량 생성       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ config.py ──────────────────────────────────────────┐   │
│  │  CURRENT_DATE (get_current_context_date())            │   │
│  │  ADMIN_DATE / ADMIN_MODE                              │   │
│  │  get_season_mode()                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQLAlchemy
┌──────────────────────▼──────────────────────────────────────┐
│              PostgreSQL (Supabase)                           │
│  kbo_games / kbo_schedule / match_features / team_rank      │
│  user_predictions / user_quizzes / user_profiles             │
│  samfan_quizzes / samfan_history                             │
└─────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
[Daum Sports] ──HTTP──> crawler_service.py ──INSERT──> kbo_games / kbo_schedule
                                                              │
                                                              ▼
                                                    feature_service.py
                                                              │
                                                              ▼
                                                    match_features
                                                              │
                                              ┌───────────────┴───────────────┐
                                              ▼                               ▼
                                     model_service.py              simulation_service.py
                                              │                               │
                                              ▼                               ▼
                                     kbo_predictions               시즌/포스트시즌 예측
                                              │
                                              ▼
                                     ranking_service.py (점수 정산)
```

### CURRENT_DATE 흐름

```
config.get_current_context_date()
  ├─ 일반 모드: datetime.now(KST).date() 반환
  └─ 관리자 모드: ADMIN_DATE 반환 (config에서 설정)

이 값은 모든 서비스에서 CURRENT_DATE로 사용됨
  ├─ crawler_service: 해당 날짜 경기 스크래핑
  ├─ model_service: 해당 날짜 경기 예측 (WHERE game_date = :today)
  ├─ feature_service: 해당 날짜 기준 피처 계산
  ├─ daily_pipeline: 해당 날짜 기준 파이프라인 실행
  └─ get_season_mode(): 해당 날짜 기준 시즌 모드 판별
```

---

## 3. 완료된 작업 목록

### 3.1 change_log 기준 (12건)

| # | 작업 | 관련 파일 | 상태 |
|---|------|----------|------|
| 1 | 관리자 모드 트랜잭션 롤백 구현 | `admin_service.py`, `crawler_service.py`, `feature_service.py`, `model_service.py`, `daily_pipeline.py` | ✅ 완료 |
| 2 | 순위 계산 로직 구현 (`update_team_rankings`) | `daily_pipeline.py` | ✅ 완료 |
| 3 | 역사 데이터 생성 코드 (`seed_history.py`) | `stack_service/seed_history.py` | ✅ 완료 |
| 4 | `user_profiles.user_id` 타입 통일 (UUID→TEXT) | `init_db.sql` | ✅ 완료 |
| 5 | 포스트시즌 시뮬레이션 구현 | `simulation_service.py`, `PostseasonCard.js`, `predictionApi.js`, `Dashboard.js` | ✅ 완료 |
| 6 | `admin_key` 제거 | `admin_service.py`, `crawler_service.py`, `feature_service.py`, `model_service.py`, `.env.example`, `README.md` | ✅ 완료 |
| 7 | 기타 수정 (supabase_config 버그, Navbar 마이그레이션 등) | `supabase_config.py`, `main.py`, `docker-compose.yml`, `Navbar.js`, `PredictionCard.js`, `QuizCard.js`, `performance_service.py` | ✅ 완료 |
| 8 | `stack_service` / `services` 구조 분리 | `weekly_quizmaker.py`, `seed_model.py`, `seed_history.py` | ✅ 완료 |
| 9 | `quizmaker.py` 트랜잭션 버그 수정 | `stack_service/quizmaker.py` | ✅ 완료 |
| 10 | `config.py` 시즌 모드 판별 로직 수정 | `config.py` | ✅ 완료 |
| 11 | `daily_pipeline.yml` ADMIN_API_KEY 제거 | `.github/workflows/daily_pipeline.yml` | ✅ 완료 |
| 12 | `daily_pipeline.yml` 주간 퀴즈 생성 step 추가 | `.github/workflows/daily_pipeline.yml` | ✅ 완료 |

### 3.2 추가 수정 사항 (6건)

| # | 작업 | 관련 파일 | 상태 |
|---|------|----------|------|
| 13 | `predict_all_games()` 오늘 경기만 예측하도록 수정 | `model_service.py` | ✅ 완료 |
| 14 | `SimulationService` 리팩토링 (중복 코드 헬퍼 추출) | `simulation_service.py` | ✅ 완료 |
| 15 | `stack_service/seed_crawler.py` 생성 (2007~2025 과거 데이터 수집) | `stack_service/seed_crawler.py` | ✅ 완료 |
| 16 | `crawler_service.py` 정리 (`scrape_historical_data()` 제거) | `crawler_service.py` | ✅ 완료 |
| 17 | `services/` vs `stack_service/` 구조 명확화 | 전체 구조 정리 | ✅ 완료 |
| 18 | `total_score` 제거, `weekly_score` 단일 랭킹 체계로 변경 | `supabase_config.py`, `ranking_service.py`, `init_db.sql`, `RankingCard.js` | ✅ 완료 |

---

## 4. Phase 1: Critical 수정 내역

### 4.1 `supabase_config.py` - `updated_at`에 `"now()"` 문자열 사용

- **파일**: [`supabase_config.py`](../backend/supabase_config.py:67)
- **문제**: `upsert_user_score()`에서 `"updated_at": "now()"`를 문자열로 전달. Supabase Python SDK는 이를 SQL `now()` 함수가 아닌 리터럴 문자열 `"now()"`로 처리함.
- **해결**: `datetime.utcnow().isoformat()`으로 변경.
- **변경 파일**: [`supabase_config.py`](../backend/supabase_config.py)

### 4.2 `daily_pipeline.yml` 주간 퀴즈 생성 step - `asyncio.run()` 오류

- **파일**: [`.github/workflows/daily_pipeline.yml`](../.github/workflows/daily_pipeline.yml:65)
- **문제**: `WeeklyQuizMaker.run()`은 동기 함수인데 `asyncio.run(maker.run())`으로 호출함. `run()` 내부에 `await` 구문이 없으므로 `RuntimeError` 발생 가능.
- **해결**: `asyncio.run()` 제거하고 동기 호출로 변경.
- **변경 파일**: [`.github/workflows/daily_pipeline.yml`](../.github/workflows/daily_pipeline.yml)

### 4.3 `requirements.txt` - `google-generativeai` 누락

- **파일**: [`requirements.txt`](../backend/requirements.txt)
- **문제**: `weekly_quizmaker.py`, `seed_history.py`, `quizmaker.py`에서 `import google.generativeai`를 사용하지만 `requirements.txt`에 `google-generativeai`가 누락됨.
- **영향**: GitHub Actions 또는 Docker 빌드 시 퀴즈/역사 생성 기능이 ImportError로 실패.
- **해결**: `requirements.txt`에 `google-generativeai` 추가.
- **변경 파일**: [`requirements.txt`](../backend/requirements.txt)

### 4.4 `init_db.sql` - `samfan_quizzes` 테이블 누락

- **파일**: [`init_db.sql`](../backend/init_db.sql)
- **문제**: `samfan_quizzes` 테이블이 `init_db.sql`에 정의되어 있지 않음. `quizmaker.py`에서 `CREATE TABLE IF NOT EXISTS`로 생성하도록 되어 있으나, 초기 DB 설정 시 누락됨.
- **해결**: `init_db.sql`에 `samfan_quizzes` 테이블 DDL 추가.
- **변경 파일**: [`init_db.sql`](../backend/init_db.sql)

---

## 5. Phase 2: Major 수정 내역

### 5.1 `daily_pipeline.py` - `update_team_rankings()`에 `last10`, `streak` 계산

- **파일**: [`daily_pipeline.py`](../backend/daily_pipeline.py)
- **문제**: `team_rank` 테이블에는 `last10`(최근 10경기)과 `streak`(연속) 컬럼이 있지만, `update_team_rankings()` 함수에서 이 값들을 계산하지 않음.
- **해결**: `_get_team_recent_stats()` 내부 함수에서 최근 10경기 조회 → `last10` 문자열 생성 + `streak` 계산 로직 구현.
- **변경 파일**: [`daily_pipeline.py`](../backend/daily_pipeline.py)

### 5.2 DB 스키마 변경: `kbo_games` + `kbo_schedule`에 `sort_text` 컬럼 추가

- **파일**: [`init_db.sql`](../backend/init_db.sql)
- **문제**: `kbo_games`와 `kbo_schedule` 테이블에 `sort_text`(구분: 페넌트레이스/와일드카드/준플레이오프 등) 컬럼이 없어 포스트시즌 시리즈 분류에 활용할 수 없음.
- **해결**: `init_db.sql`에 `sort_text VARCHAR(50)` 컬럼 추가.
- **변경 파일**: [`init_db.sql`](../backend/init_db.sql)

### 5.3 `crawler_service.py` - `sort_text`를 DB에 저장하도록 수정

- **파일**: [`crawler_service.py`](../backend/services/crawler_service.py)
- **문제**: `_parse_daum_rows()`에서 `sort_text`를 추출하고 `is_postseason`을 올바르게 판별하지만, 이 값을 DB에 저장하지 않음.
- **해결**: `_upsert_kbo_games()`와 `_upsert_kbo_schedule()`에서 `sort_text`를 INSERT/UPDATE에 포함.
- **변경 파일**: [`crawler_service.py`](../backend/services/crawler_service.py)

### 5.4 `simulation_service.py` - DB의 `sort_text` 값으로 시리즈 분류

- **파일**: [`simulation_service.py`](../backend/services/simulation_service.py)
- **문제**: `get_postseason_bracket()`에서 `game_id` 문자열에 키워드("와일드카드", "준플레이오프" 등)가 포함되어 있는지로 시리즈를 분류함. 이는 Daum Sports의 `game_id` 포맷에 의존하는 불안정한 방식.
- **해결**: DB의 `sort_text` 컬럼 값을 기준으로 시리즈 분류하도록 개선.
- **변경 파일**: [`simulation_service.py`](../backend/services/simulation_service.py)

### 5.5 `ranking_service.py` - 빈 `game_ids` 처리

- **파일**: [`ranking_service.py`](../backend/services/ranking_service.py:64-68)
- **문제**: 정산할 경기가 없을 때 `game_ids`가 빈 튜플 `()`이면 `WHERE game_id IN ()` 구문이 SQL 에러를 발생시킴.
- **해결**: `game_ids`가 비어있으면 조기 반환(`return`)하도록 조건 추가.
- **변경 파일**: [`ranking_service.py`](../backend/services/ranking_service.py)

### 5.6 `SeasonProjectionCard.js` - 데이터 구조 불일치

- **파일**: [`SeasonProjectionCard.js`](../frontend/src/components/SeasonProjectionCard.js:7)
- **문제**: `projection?.data`로 접근하지만, `Dashboard.js`에서는 `response.data`를 `cardData`로 저장함. `getSeasonProjection()`의 응답 구조가 `{status: "ok", data: [...]}`라면 `cardData`는 `{data: [...]}` 형태가 되어 `projection?.data?.data`로 접근해야 함.
- **해결**: 데이터 접근 경로를 `projection?.data`에서 `projection?.data?.data`로 수정.
- **변경 파일**: [`SeasonProjectionCard.js`](../frontend/src/components/SeasonProjectionCard.js)

### 5.7 `AiPerformanceCard.js` - 관리자 모드 조건 제거

- **파일**: [`AiPerformanceCard.js`](../frontend/src/components/AiPerformanceCard.js:21-23)
- **문제**: `isAdminMode && seasonMode !== 'offseason'` 조건으로 시뮬레이션 리포트(`getSimulationReport()`)를 호출함. 관리자 모드는 단순히 `CURRENT_DATE`를 강제 주입하는 역할일 뿐, AI 성능 카드에서 별도의 관리자 모드 특화 로직이 필요하지 않음.
- **해결**: 관리자 모드 조건을 제거하고, 항상 일반 AI 성능 데이터(`getAiPerformance()`)만 표시하도록 수정.
- **변경 파일**: [`AiPerformanceCard.js`](../frontend/src/components/AiPerformanceCard.js)

---

## 6. Phase 3: Minor 수정 내역

### 6.1 `crawler_service.py` - 중복 코드 헬퍼 함수 추출

- **파일**: [`crawler_service.py`](../backend/services/crawler_service.py:218-254)
- **문제**: `conn`이 있을 때와 없을 때의 INSERT/UPDATE 로직이 완전히 중복됨.
- **해결**: `_get_conn()` 클래스 메서드로 connection 관리 로직 추출.
- **변경 파일**: [`crawler_service.py`](../backend/services/crawler_service.py)

### 6.2 `model_service.py` - DB connection 재사용

- **파일**: [`model_service.py`](../backend/services/model_service.py:55-77)
- **문제**: 스케줄 조회와 피처 조회를 각각 별도의 `engine.connect()`로 열고 있음.
- **해결**: 하나의 connection으로 재사용하도록 수정.
- **변경 파일**: [`model_service.py`](../backend/services/model_service.py)

### 6.3 `model_preprocessor.py` - 동적 피처 생성

- **파일**: [`model_preprocessor.py`](../backend/services/model_preprocessor.py:19-24)
- **문제**: 피처 목록이 하드코딩되어 있어, 새 피처 추가 시 `config.py`의 `FEATURE_CONFIG`와 `model_preprocessor.py`를 모두 수정해야 함.
- **해결**: `FEATURE_CONFIG`에서 피처 목록을 동적으로 생성하도록 리팩토링.
- **변경 파일**: [`model_preprocessor.py`](../backend/services/model_preprocessor.py)

### 6.4 `feature_service.py` - 트랜잭션 처리 안정성 개선

- **파일**: [`feature_service.py`](../backend/services/feature_service.py:183)
- **문제**: 관리자 모드에서 외부 `conn`(SQLAlchemy Connection)을 받았을 때 `conn.connection.cursor()`로 psycopg2 네이티브 커서를 가져옴. `engine.begin()` 컨텍스트의 Connection과 혼용될 경우 트랜잭션 상태 불일치 가능성.
- **해결**: `conn.connection.cursor()` 대신 SQLAlchemy Core 스타일의 `exec_conn.execute()` 사용으로 통일.
- **변경 파일**: [`feature_service.py`](../backend/services/feature_service.py)

### 6.5 Docker 환경 변수 설정 통일

- **파일**: [`docker-compose.yml`](../docker-compose.yml:10)
- **문제**: `env_file: - .env`로 프로젝트 루트의 `.env`를 참조하지만, `backend/Dockerfile`은 `/app`에서 실행되고 `.env.example`은 백엔드 폴더에 상대 경로로 참조하는 코드들이 혼재함.
- **해결**: Docker 환경 변수 설정 통일.
- **변경 파일**: [`docker-compose.yml`](../docker-compose.yml)

---

## 7. 추가 수정 사항

### 7.1 `predict_all_games()` - 오늘 경기만 예측하도록 수정

- **파일**: [`model_service.py`](../backend/services/model_service.py:64)
- **변경 전**: `WHERE game_date >= :today` — 오늘 이후 **모든** 경기 예측
- **변경 후**: `WHERE game_date = :today` — **오늘** 경기만 예측
- **영향**:
  - 일반 모드: 오늘 날짜의 경기만 예측
  - 관리자 모드: 설정된 `ADMIN_DATE`의 경기만 예측
  - `CURRENT_DATE`는 [`config.py`](../backend/config.py)의 `get_current_context_date()`에서 결정

### 7.2 `SimulationService` 리팩토링 (중복 코드 제거)

- **파일**: [`simulation_service.py`](../backend/services/simulation_service.py)
- **리팩토링 대상 중복**:
  1. 팀별 최신 피처 조회 로직 중복 (`get_season_projection()` vs `_predict_series_winner()`)
  2. 가상 대진 DataFrame 생성 로직 중복 (16개 컬럼 dict)
  3. `_get_regular_season_top_teams()` 단순 조회 함수

#### 추출된 헬퍼 메서드

```python
@classmethod
def _get_team_latest_features(cls, team: str) -> dict | None:
    """팀별 최신 match_features 조회 (홈/원정 구분)"""
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
    """두 팀 스탯으로 16개 컬럼 가상 대진 dict 생성"""
    return {
        "home_team": home_stats["team"], "away_team": away_stats["team"],
        "home_elo": home_stats["elo"], "away_elo": away_stats["elo"],
        "home_form": home_stats["form"], "away_form": away_stats["form"],
        "home_streak": home_stats["streak"], "away_streak": away_stats["streak"],
        "home_pythagorean": home_stats["pyth"], "away_pythagorean": away_stats["pyth"],
        "home_recent_rd": home_stats["recent_rd"], "away_recent_rd": away_stats["recent_rd"],
        "home_matchup_rd": 0.0, "away_matchup_rd": 0.0,
        "season_matchup_count": 0, "rest_diff": 0,
    }
```

- **영향**: `get_season_projection()`과 `_predict_series_winner()`의 중복 코드 제거. `_predict_series_winner()`는 기존 30줄 → 10줄로 축소.

### 7.3 `stack_service/seed_crawler.py` 생성

- **파일**: [`stack_service/seed_crawler.py`](../backend/stack_service/seed_crawler.py) (신규)
- **목적**: Daum Sports에서 2007년~2025년 과거 KBO 경기 데이터를 수집하는 1회성 스크립트
- **기본값**: `EARLIEST_YEAR = 2007`, `DEFAULT_END_YEAR = 2025`
- **CLI 인자**: `--start-year`, `--end-year`, `--dry-run`
- **재사용**: [`CrawlerService._fetch_from_daum()`](../backend/services/crawler_service.py:23)과 [`_parse_daum_rows()`](../backend/services/crawler_service.py:42)를 import하여 사용
- **동작 방식**:
  ```python
  for year in range(start_year, end_year + 1):
      for month in range(3, 12):  # 3월~11월
          target_date = date(year, month, 1)
          soup = CrawlerService._fetch_from_daum(target_date)
          games = CrawlerService._parse_daum_rows(soup)
          # 점수 파싱 → 승리팀 결정 → kbo_games + kbo_schedule INSERT
  ```
- **참고**: 이 스크립트는 데이터 적재만 담당합니다. 특정 날짜 이후 데이터를 제한하는 로직(데이터 遮蔽)은 `services/` 레이어에서 `CURRENT_DATE` 기반으로 처리됩니다.

### 7.4 `crawler_service.py` 정리

- **파일**: [`crawler_service.py`](../backend/services/crawler_service.py)
- **제거된 항목**:
  - `scrape_historical_data()` 메서드 — `seed_crawler.py`로 이동
  - `/historical` API 엔드포인트 — `seed_crawler.py`는 CLI 스크립트이므로 API 불필요
- **유지된 항목**:
  - `_fetch_from_daum()` — Daum Sports HTTP 요청 (seed_crawler.py에서 재사용)
  - `_parse_daum_rows()` — HTML 파싱 (seed_crawler.py에서 재사용)
  - `_upsert_kbo_games()` / `_upsert_kbo_schedule()` — DB 저장
  - `update_daily_pipeline()` — 일일 스크래핑 파이프라인
  - `/daily-update` API 엔드포인트

### 7.5 `services/` vs `stack_service/` 구조 명확화

#### 구분 기준

| 기준 | `services/` | `stack_service/` |
|------|------------|-----------------|
| **실행 주기** | 매일/정기적 실행 | 최초 1회 또는 비정기 수동 실행 |
| **호출 방식** | FastAPI mount 또는 daily_pipeline에서 호출 | CLI에서 직접 `python` 실행 |
| **스케줄러** | GitHub Actions (daily_pipeline.yml) | 수동 실행 |
| **예시** | crawler, model, simulation, weekly_quizmaker | seed_crawler, seed_history, seed_model, quizmaker |

#### 최종 구조

```
backend/
├── services/                          # FastAPI mount + 스케줄러 정기 실행
│   ├── __init__.py
│   ├── crawler_service.py             # Daum Sports 일일 스크래핑
│   ├── feature_service.py             # ELO/Form/Streak 피처 계산
│   ├── model_service.py               # LightGBM 예측 실행
│   ├── model_preprocessor.py          # 피처 전처리
│   ├── simulation_service.py          # 시즌/포스트시즌 시뮬레이션
│   ├── ranking_service.py             # 점수 정산/랭킹 조회
│   ├── performance_service.py         # 모델 정확도 계산
│   ├── weekly_quizmaker.py            # 주간 퀴즈 생성 (매주 월요일)
│   └── admin_service.py               # 관리자 모드 파이프라인
│
├── stack_service/                     # 1회성/비정기 실행 스크립트
│   ├── __init__.py
│   ├── seed_crawler.py                # 2007~2025 과거 데이터 수집 (신규)
│   ├── seed_history.py                # 1982~2025 역사 데이터 생성
│   ├── seed_model.py                  # 초기 모델 1회 학습
│   └── quizmaker.py                   # 1982~2025 퀴즈 대량 생성
│
├── daily_pipeline.py                  # 일일 파이프라인 (스크래핑→피처→예측→정산)
├── config.py                          # CURRENT_DATE, 시즌 모드 판별
├── main.py                            # FastAPI 앱 + API 엔드포인트
├── supabase_config.py                 # Supabase 클라이언트 + 랭킹 CRUD
```

---

## 8. 최종 파일 구조

```
Laions_project/
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml         # GitHub Actions 스케줄러
│
├── backend/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── admin_service.py           # 관리자 모드 파이프라인 (트랜잭션 롤백)
│   │   ├── crawler_service.py         # Daum Sports 스크래핑 (일일)
│   │   ├── feature_service.py         # ELO/Form/Streak 피처 계산
│   │   ├── model_service.py           # LightGBM 예측
│   │   ├── model_preprocessor.py      # 피처 전처리
│   │   ├── performance_service.py     # 모델 정확도 계산
│   │   ├── ranking_service.py         # 점수 정산/랭킹
│   │   ├── simulation_service.py      # 시즌/포스트시즌 시뮬레이션
│   │   └── weekly_quizmaker.py        # 주간 퀴즈 생성
│   │
│   ├── stack_service/
│   │   ├── __init__.py
│   │   ├── seed_crawler.py            # 과거 데이터 수집 (2007~2025)
│   │   ├── seed_history.py            # 역사 데이터 생성 (1982~2025)
│   │   ├── seed_model.py              # 초기 모델 학습
│   │   └── quizmaker.py               # 퀴즈 대량 생성 (1982~2025)
│   │
│   ├── config.py                      # CURRENT_DATE, 시즌 모드
│   ├── main.py                        # FastAPI 앱
│   ├── supabase_config.py             # Supabase 연동
│   ├── daily_pipeline.py              # 일일 파이프라인
│   ├── init_db.sql                    # DB 스키마
│   ├── requirements.txt               # Python 의존성
│   └── .env.example                   # 환경 변수 예시
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── predictionApi.js       # API 호출 함수
│   │   ├── components/
│   │   │   ├── AiPerformanceCard.js   # AI 성능 카드
│   │   │   ├── Navbar.js              # 네비게이션 바
│   │   │   ├── PostseasonCard.js      # 포스트시즌 대진표
│   │   │   ├── PredictionCard.js      # 예측 카드
│   │   │   ├── QuizCard.js            # 퀴즈 카드
│   │   │   └── SeasonProjectionCard.js # 시즌 순위 예측 카드
│   │   └── pages/
│   │       └── Dashboard.js           # 메인 대시보드
│   │   └── ...
│   └── ...
│
├── docs/
│   ├── project_report.md              # [신규] 통합 프로젝트 보고서
│   ├── inspection_report.md           # (기존) 점검 보고서
│   ├── change_log.md                  # (기존) 변경 로그
│   ├── refactoring_plan.md            # (기존) 리팩토링 계획
│   └── README.md                      # (기존) 구버전 문서
│
├── docker-compose.yml                 # Docker 구성
└── daumsports.html                    # Daum Sports HTML 분석 샘플
```

---

## 9. 변경 파일 목록

### 9.1 수정된 파일

| 파일 | 변경 내용 | 관련 작업 |
|------|----------|----------|
| [`backend/services/admin_service.py`](../backend/services/admin_service.py) | `engine.begin()` → `engine.connect()` + 수동 트랜잭션 | #1 관리자 모드 롤백 |
| [`backend/services/crawler_service.py`](../backend/services/crawler_service.py) | `update_daily_pipeline(conn=None)` 파라미터 추가, `_get_conn()` 헬퍼 추출, `sort_text` 저장, `scrape_historical_data()` 제거 | #1, #5.3, #6.1, #16 |
| [`backend/services/feature_service.py`](../backend/services/feature_service.py) | `build_all_features(conn=None)` 파라미터 추가, 트랜잭션 처리 개선 | #1, #6.4 |
| [`backend/services/model_service.py`](../backend/services/model_service.py) | `predict_all_games(read_only=False, conn=None)` 파라미터 추가, DB connection 재사용, `WHERE game_date = :today`로 변경 | #1, #6.2, #13 |
| [`backend/services/simulation_service.py`](../backend/services/simulation_service.py) | 포스트시즌 시리즈 분류 개선, `_get_team_latest_features()` + `_build_virtual_match_row()` 헬퍼 추출로 중복 제거 | #5, #5.4, #14 |
| [`backend/services/ranking_service.py`](../backend/services/ranking_service.py) | 빈 `game_ids` 처리 조건 추가 | #5.5 |
| [`backend/services/performance_service.py`](../backend/services/performance_service.py) | 모드별 정확도 계산 로직 추가 (정규시즌/포스트시즌 분리) | #7 |
| [`backend/services/weekly_quizmaker.py`](../backend/services/weekly_quizmaker.py) | **신규 생성** — `WeeklyQuizMaker` 클래스, 매주 월요일 퀴즈 생성 | #8 |
| [`backend/daily_pipeline.py`](../backend/daily_pipeline.py) | `update_team_rankings(conn=None)` 추가, `last10`/`streak` 계산 구현 | #1, #2, #5.1 |
| [`backend/config.py`](../backend/config.py) | 시즌 모드 판별 로직 수정 (`postseason_count` 조건 제거) | #10 |
| [`backend/main.py`](../backend/main.py) | `/api/history/today` 엔드포인트 추가 | #7 |
| [`backend/supabase_config.py`](../backend/supabase_config.py) | `"now()"` 문자열 → `datetime.utcnow().isoformat()` | #4.1, #7 |
| [`backend/init_db.sql`](../backend/init_db.sql) | `user_id` UUID→TEXT, `sort_text` 컬럼 추가, `samfan_quizzes` DDL 추가 | #4, #4.4, #5.2 |
| [`backend/requirements.txt`](../backend/requirements.txt) | `google-generativeai` 추가 | #4.3 |
| [`backend/.env.example`](../backend/.env.example) | `ADMIN_API_KEY` 항목 제거 | #6 |
| [`.github/workflows/daily_pipeline.yml`](../.github/workflows/daily_pipeline.yml) | `asyncio.run()` 제거, `ADMIN_API_KEY` env 제거, 주간 퀴즈 step 추가 | #4.2, #11, #12 |
| [`docker-compose.yml`](../docker-compose.yml) | healthcheck 추가, 환경 변수 설정 통일 | #6.5 |
| [`frontend/src/components/Navbar.js`](../frontend/src/components/Navbar.js) | Firebase→Supabase Auth 마이그레이션 (`user.uid` → `user.id`) | #7 |
| [`frontend/src/components/PredictionCard.js`](../frontend/src/components/PredictionCard.js) | `user.uid` → `user.id` | #7 |
| [`frontend/src/components/QuizCard.js`](../frontend/src/components/QuizCard.js) | `user.uid` → `user.id` | #7 |
| [`frontend/src/components/SeasonProjectionCard.js`](../frontend/src/components/SeasonProjectionCard.js) | 데이터 접근 경로 수정 (`projection?.data` → `projection?.data?.data`) | #5.6 |
| [`frontend/src/components/AiPerformanceCard.js`](../frontend/src/components/AiPerformanceCard.js) | 관리자 모드 조건 제거 (항상 일반 AI 성능 표시) | #5.7 |
| [`frontend/src/components/PostseasonCard.js`](../frontend/src/components/PostseasonCard.js) | 3개 섹션으로 완전 재작성 (대진표/다음시리즈/오늘예측) | #5 |
| [`frontend/src/pages/Dashboard.js`](../frontend/src/pages/Dashboard.js) | 포스트시즌 모드 병렬 fetch, `bracket` prop 전달 | #5 |
| [`frontend/src/api/predictionApi.js`](../frontend/src/api/predictionApi.js) | `getPostseasonBracket()` 함수 추가 | #5 |
| [`docs/README.md`](../docs/README.md) | `ADMIN_API_KEY` 문서 제거 | #6 |

### 9.2 신규 생성된 파일

| 파일 | 설명 | 관련 작업 |
|------|------|----------|
[`backend/stack_service/seed_crawler.py`](../backend/stack_service/seed_crawler.py) | Daum Sports 2007~2025 과거 데이터 수집 CLI 스크립트 | #15 |
[`backend/stack_service/seed_history.py`](../backend/stack_service/seed_history.py) | Gemini AI로 1982~2025 삼성 라이온즈 역사 데이터 생성 | #3, #8 |
[`backend/stack_service/seed_model.py`](../backend/stack_service/seed_model.py) | 초기 모델 1회 학습 스크립트 | #8 |
[`backend/services/weekly_quizmaker.py`](../backend/services/weekly_quizmaker.py) | 매주 월요일 주간 퀴즈 생성 | #8 |
[`docs/project_report.md`](../docs/project_report.md) | **본 문서** — 통합 프로젝트 보고서 | #17 |

### 9.3 제거된 기능

| 기능 | 설명 | 대체 |
|------|------|------|
`admin_key` 인증 로직 | `ADMIN_API_KEY` 기반 인증 | `ADMIN_MODE` boolean만 사용 |
`crawler_service.scrape_historical_data()` | 과거 데이터 수집 메서드 | `stack_service/seed_crawler.py`로 이동 |
`/historical` API 엔드포인트 | 과거 데이터 수집 API | `seed_crawler.py` CLI로 대체 |

---

## 10. 부록

### 10.1 참고 문서

| 문서 | 설명 |
|------|------|
[`docs/inspection_report.md`](inspection_report.md) | 기존 점검 보고서 (Phase 1-3 상세) |
[`docs/change_log.md`](change_log.md) | 기존 변경 로그 (12건 상세) |
[`docs/refactoring_plan.md`](refactoring_plan.md) | 리팩토링 계획 개요 |
[`docs/README.md`](README.md) | 구버전 프로젝트 문서 |

### 10.2 용어 설명

용어 | 설명 |
|------|------|
**CURRENT_DATE** | [`config.py`](../backend/config.py)의 `get_current_context_date()`에서 반환하는 기준 날짜. 일반 모드=오늘, 관리자 모드=ADMIN_DATE |
**ADMIN_MODE** | 관리자 모드 활성화 플래그. `config.py`에서 설정 |
**ADMIN_DATE** | 관리자 모드에서 강제 주입할 날짜. `config.py`에서 설정 |
**sort_text** | Daum Sports HTML의 `td_sort` 클래스 값. "페넌트레이스/와일드카드/준플레이오프/플레이오프/한국시리즈" 구분 |
**is_postseason** | `sort_text`가 "페넌트레이스"가 아닌 경우 `True` |
**ELO** | 팀 레이팅 시스템. 경기 결과에 따라 점수가 변동 |
**Form** | 최근 5경기 승률 |
**Streak** | 현재 연승/연패 |
**Pythagorean** | 피타고리안 승률. 득점/실점 기반 예상 승률 |

### 10.3 DB 테이블 목록

| 테이블 | 설명 |
|--------|------|
`kbo_games` | KBO 경기 결과 (팀별 점수, 승리팀, sort_text 등) |
`kbo_schedule` | KBO 경기 일정 |
`match_features` | 팀별 ELO/Form/Streak/Pythagorean 피처 |
`team_rank` | 리그 순위 (승/패/무, 승률, 게임차, last10, streak) |
`kbo_predictions` | AI 모델 예측 결과 |
`user_predictions` | 사용자 승리 예측 |
`user_profiles` | 사용자 프로필 (weekly_score, prediction_score, quiz_score) |
`user_quizzes` | 사용자 퀴즈 정답 이력 |
`samfan_quizzes` | AI 생성 퀴즈 데이터 |
`samfan_history` | 삼성 라이온즈 역사 데이터 |

---

> **문서 이력**
> - 2026-05-08: 최초 통합 작성 (inspection_report.md + change_log.md + 추가 수정 사항 5건)
> - 2026-05-08: `total_score` 제거, `weekly_score` 단일 랭킹 체계로 변경 (#18)