# Laions 프로젝트 리팩토링 계획서

> 작성일: 2026-04-30
> 목적: 회사 사장님 시연을 위한 리팩토링 + Docker Compose 환경 구성
> 코드 분석 완료: 모든 backend/frontend/Docker 파일 대조 검증

---

## 1. 현재 상황

### 1.1 장비 구성 (Tailscale Mesh Network)

| 장비 | 역할 | 연휴 중 사용 가능? | OS |
|------|------|:---:|:---:|
| **회사 서버** | 최종 배포 대상 (앱 실행) | ❌ (다운 위험) | Linux |
| **내 개인 PC** | 리팩토링 작업 + 임시 테스트 | ✅ | - |
| **시연 PC** | 사장님 시연용 (브라우저 접속) | ❌ (회사) | Windows |

### 1.2 최종 시연 시나리오

```mermaid
flowchart LR
    subgraph 연휴중["연휴 중 - 내 PC 1대"]
        A[리팩토링 작업]
        B[Docker Compose 실행]
        C[localhost:3000 으로 테스트]
    end
    
    subgraph 연휴후["연휴 후 - 회사"]
        A -->|GitHub/USB/SCP| D[서버에 코드 복사]
        D --> E[서버: docker compose up -d]
        E -->|Tailscale IP| F[시연 PC: 브라우저 접속]
    end
```

### 1.3 핵심 요구사항

- **내 PC 1대**로 리팩토링 + 테스트 완료
- **서버에 코드만 복사**하면 추가 설정 없이 실행 가능
- **시연 PC**에서 Tailscale IP로 브라우저 접속

---

## 2. 현재 아키텍처 및 문제점

### 2.1 현재 아키텍처

```mermaid
flowchart TD
    Client[React Frontend :3000] -->|Firebase Auth| FA[Firebase Auth]
    Client -->|REACT_APP_API_BASE_URL| API[FastAPI Backend :8000]
    API --> PG[PostgreSQL - Docker 컨테이너]
    API --> FS[Firebase Firestore - 랭킹/점수]
    API --> Gemini[Gemini API - 퀴즈 생성]
    API --> Model[LightGBM Model]
    
    PG --> Tables[(kbo_games, match_features, ai_predictions,\nuser_rankings, user_predictions, user_quizzes,\nkbo_schedule, team_rank)]
    FS --> Collections[(users, weekly_ranking)]
```

### 2.2 기술 스택

| 계층 | 현재 | 리팩토링 후 (목표) |
|------|------|------|
| **Frontend** | React 19 + MUI 7 | React 19 + MUI 7 (유지) |
| **Backend** | FastAPI + SQLAlchemy | FastAPI + SQLAlchemy (유지) |
| **Database** | PostgreSQL (Docker) + Firebase Firestore | **Supabase** (단일화) |
| **Auth** | Firebase Auth | **Supabase Auth** |
| **AI Model** | LightGBM (ELO 기반 피처) | LightGBM (유지) |
| **퀴즈 생성** | Gemini API | **DeepSeek API** |
| **Infra** | Docker Compose | Docker Compose + **Nginx** |
| **Scheduler** | 미구현 | GitHub Actions (선택) |

### 2.3 현재 발견된 문제점

#### 문제 1: DB 연결 주소 (Docker 환경)
- `.env`에서 `DATABASE_URL=postgresql://user:pass@localhost:5432/laions_db`
- Docker 환경에서는 `localhost`가 아닌 컨테이너 이름 `db`를 사용해야 함
- **해결:** Supabase 전환으로 클라우드 DB 사용 → Docker 환경 문제 해소

#### 문제 2: 프론트엔드 API 호출 주소
- `apiClient.js`가 `REACT_APP_API_BASE_URL` 환경 변수 사용
- React는 빌드 타임에 환경 변수가 고정되어, 환경(내 PC/서버)이 바뀌면 재빌드 필요
- **해결:** Nginx 리버스 프록시 추가로 상대 경로(`/api/...`) 호출 가능하게 변경

#### 문제 3: Firebase + PostgreSQL 이중 저장소
- 경기 데이터: PostgreSQL
- 유저 점수/랭킹: Firebase Firestore
- **해결:** Supabase로 단일화

#### 문제 4: 관리자 모드 복잡성
- `ADMIN_MODE`에 따라 테이블명이 이원화 (`kbo_games` / `kbo_games_admin`)
- 모듈 레벨 변수로 관리되어 동적 변경 시 사이드 이펙트 위험
- **해결:** 관리자 모드는 날짜 주입만 담당하도록 단순화 (SAVEPOINT 방식)

#### 문제 5: 라우팅 구조 혼재
- `main.py`에 직접 API 엔드포인트 정의 (퀴즈, 예측, 순위)
- 일부는 서비스 파일에 `@router`로 정의
- **해결:** 모든 API를 서비스 라우터로 이동

#### 문제 6: ranking_service.py 버그
- `COLLECTION_USERS` 변수가 정의되지 않음 (142, 165번째 줄)
- **해결:** Supabase 전환 시 자연스럽게 수정

### 2.4 코드 레벨 검증 결과 (5개 버그 확인)

| # | 버그 | 위치 | 설명 | 해결 시점 |
|---|------|------|------|:---------:|
| B1 | `COLLECTION_USERS` NameError | [`ranking_service.py:142,165`](backend/services/ranking_service.py:142) | `_get_users_collection()` 함수는 있지만 `COLLECTION_USERS` 변수는 없음 | Step 2 |
| B2 | `team_rank_admin` DDL 누락 | [`main.py:234`](backend/main.py:234), [`init_db.sql`](backend/init_db.sql) | `team_rank_admin` 테이블 참조하지만 DDL 없음 | Step 3 |
| B3 | `weekly_score` 컬럼 누락 | [`init_db.sql:59-66`](backend/init_db.sql:59) | `user_rankings`에 `weekly_score` 컬럼 없음 | Step 1 |
| B4 | `admin_service.py` 직접 config 변조 | [`admin_service.py:28-29`](backend/services/admin_service.py:28) | `config_module.ADMIN_MODE = True` 직접 할당 | Step 1 |
| B5 | `quizmaker.py` 이중 DB 연결 | [`quizmaker.py:20`](backend/services/quizmaker.py:20) | `create_engine()` 별도 생성, FastAPI `get_db()` 미사용 | Step 1 |

---

## 3. 목표 아키텍처

```mermaid
flowchart TD
    Browser[브라우저 :3000] --> Nginx[Nginx 리버스 프록시 :3000]
    Nginx -->|/api/*| API[FastAPI Backend :8000]
    Nginx -->|/*| Static[React 정적 파일]
    API --> SupaDB[Supabase PostgreSQL - 클라우드]
    API --> SupaAuth[Supabase Auth]
    API --> DeepSeek[DeepSeek API - 퀴즈 생성]
    API --> Model[LightGBM Model]
    Client[React Frontend] -->|Supabase Auth JS| SupaAuth
```

### Supabase가 대체하는 것

| 현재 | Supabase |
|------|----------|
| PostgreSQL (Docker 컨테이너) | Supabase PostgreSQL (클라우드) |
| Firebase Auth | Supabase Auth |
| Firebase Firestore (유저 점수/랭킹) | Supabase DB (별도 테이블) |
| `firebase-credentials.json` | Supabase URL + anon key (2개) |

### Supabase 전환 후 docker-compose.yml

```yaml
services:
  nginx:           # 리버스 프록시 (포트 3000)
  backend:         # FastAPI (Supabase DB 연결)
  frontend:        # React 정적 파일 (Supabase Auth 사용)
```

**없어지는 것:**
- `db` 서비스 (PostgreSQL 컨테이너)
- `volumes: postgres_data`
- `healthcheck`
- `depends_on: db`
- Firebase 관련 환경 변수 6개
- `firebase-credentials.json` 파일

**추가되는 것:**
- `nginx` 서비스
- Supabase URL + anon key (2개 환경 변수)

---

## 4. 최적화된 5-Step 실행 계획

> **원래 29개 파일 → 최적화 후 26개 파일** (3개 중복 작업 제거)
> 각 Step은 독립적으로 테스트 가능

```mermaid
flowchart TD
    subgraph S1["Step 1: 핫픽스 (4 tasks)"]
        A["1.3 weekly_score 컬럼 추가"]
        B["1.4 admin_context.py 생성"]
        C["1.5 quizmaker router 통합"]
        D["1.6 requirements.txt 정리"]
    end
    subgraph S2["Step 2: Supabase (3 tasks)"]
        E["2.1 Supabase 프로젝트 설정"]
        F["2.2 백엔드 Supabase 연동"]
        G["2.3 프론트엔드 Supabase 연동"]
    end
    subgraph S3["Step 3: 관리자모드+전경기+순위 (4 tasks)"]
        H["3.1 SAVEPOINT 구현"]
        I["3.2+4.3 _admin 제거 + 순위 동적 계산"]
        J["3.3 프론트엔드 전 경기 표시"]
        K["3.4 포스트시즌 시뮬레이션"]
    end
    subgraph S4["Step 4: DeepSeek 교체 (2 tasks)"]
        L["4.1 Gemini→DeepSeek"]
        M["4.2 퀴즈 생성 API"]
    end
    subgraph S5["Step 5: 배포 (4 tasks)"]
        N["5.1 GitHub Actions"]
        O["5.2 Docker Compose + Nginx"]
        P["5.3 Nginx 설정"]
        Q["5.4 문서 업데이트"]
    end
    S1 --> S2 --> S3 --> S4 --> S5
```

### Step 간 의존성 분석 (제거/통합된 작업)

| 원래 작업 | 처리 | 사유 |
|-----------|:----:|------|
| ~~1.1 COLLECTION_USERS 버그 수정~~ | **제거** | Step 2에서 `ranking_service.py` Firestore 코드 전체 교체 시 자연 해결 |
| ~~1.2 team_rank_admin DDL 추가~~ | **제거** | Step 3에서 `_admin` 테이블 자체 제거 |
| ~~2.4 Docker Compose Firebase env 제거~~ | **Step 5로 이동** | Nginx 추가와 함께 한 번에 처리 |
| ~~3.2 + 4.3 분리~~ | **통합** | 같은 파일(`main.py`)을 함께 수정 |

---

## Step 1: 핫픽스 + 기반 정비

**목표**: 리팩토링의 기반이 되는 필수 작업만 수행

### Task 1.3: `weekly_score` 컬럼 추가
- **파일**: [`backend/init_db.sql`](backend/init_db.sql)
- **변경**: `user_rankings` 테이블에 `weekly_score INTEGER DEFAULT 0` 추가 (59행)
- **이유**: Supabase 마이그레이션 시에도 동일 스키마 필요

### Task 1.4: `admin_context.py` 생성 + `admin_service.py` 수정
- **파일**: 
  - [`backend/services/admin_context.py`](backend/services/admin_context.py) **신규** — `contextvars` 기반 admin_mode 관리
  - [`backend/services/admin_service.py`](backend/services/admin_service.py) 수정 — `config_module.ADMIN_MODE = True` 직접 할당 대신 `admin_context` 사용
  - [`backend/config.py`](backend/config.py) 수정 — `ADMIN_MODE` 플래그를 `admin_context` 기반으로 변경
- **이유**: Step 3의 SAVEPOINT 구현을 위한 선행조건

### Task 1.5: `quizmaker.py` FastAPI router 통합
- **파일**: 
  - [`backend/services/quizmaker.py`](backend/services/quizmaker.py) 수정 — standalone → FastAPI router, `get_db()` 사용, 별도 `create_engine()` 제거
  - [`backend/main.py`](backend/main.py) 수정 — quizmaker router 등록
- **이유**: Step 4의 DeepSeek 교체를 위한 선행조건

### Task 1.6: `requirements.txt`에 `openai` 추가
- **파일**: [`backend/requirements.txt`](backend/requirements.txt)
- **변경**: `openai` 추가 (Step 4에서 사용)

---

## Step 2: Supabase 마이그레이션

**목표**: Firebase Auth + Firestore를 Supabase로 완전 대체

### Task 2.1: Supabase 프로젝트 설정
- Supabase 계정 생성 및 프로젝트 개설
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` 확보
- PostgreSQL 스키마 마이그레이션 (`init_db.sql` 기반)

### Task 2.2: 백엔드 Supabase 연동
- **신규**: [`backend/supabase_config.py`](backend/supabase_config.py) — Supabase 클라이언트 설정
- **수정**: [`backend/requirements.txt`](backend/requirements.txt) — `supabase-py` 추가, `firebase-admin` 제거
- **수정**: [`backend/services/ranking_service.py`](backend/services/ranking_service.py) — Firestore `_update_firestore_scores()` → Supabase PostgreSQL `user_rankings` 테이블 직접读写
- **수정**: [`backend/main.py`](backend/main.py) — `from firebase_config import db_fs` 등 Firebase 관련 코드 제거
- **삭제**: [`backend/firebase_config.py`](backend/firebase_config.py)

### Task 2.3: 프론트엔드 Supabase 연동
- **신규**: [`frontend/src/supabase.js`](frontend/src/supabase.js) — Supabase Auth 클라이언트
- **삭제**: [`frontend/src/firebase.js`](frontend/src/firebase.js)
- **수정**: 
  - [`frontend/src/App.js`](frontend/src/App.js) — `onAuthStateChangedListener` → Supabase `onAuthStateChange`
  - [`frontend/src/pages/LoginPage.js`](frontend/src/pages/LoginPage.js) — `loginWithGoogle` → Supabase OAuth
  - [`frontend/src/components/Navbar.js`](frontend/src/components/Navbar.js) — `logout` → Supabase `signOut`
  - [`frontend/package.json`](frontend/package.json) — `@supabase/supabase-js` 추가, `firebase` 제거

---

## Step 3: 관리자 모드 + 전 경기 예측 + 순위 계산

**목표**: 관리자 모드 SAVEPOINT 개선, 프론트엔드 전 경기 표시, 순위 동적 계산

### Task 3.1: SAVEPOINT 구현
- **파일**: [`backend/services/admin_context.py`](backend/services/admin_context.py) (Step 1.4에서 생성)
- **변경**: `begin_nested()`를 사용한 SAVEPOINT 롤백 구현
- 모든 서비스에서 `admin_context`를 사용하도록 일괄 적용

### Task 3.2: `_admin` 테이블 참조 제거 + KBO 순위 동적 계산 (통합)
- **파일**: 
  - [`backend/config.py`](backend/config.py) — `TABLE_*_ADMIN` 상수 제거
  - [`backend/main.py`](backend/main.py) — `_admin` 테이블 참조 제거 + `get_standings()`를 `team_rank` 테이블 조회 → `kbo_games` 기반 동적 계산으로 변경
- **변경**: SAVEPOINT 방식으로 대체되었으므로 테이블 분기 불필요

### Task 3.3: 프론트엔드 전 경기 표시
- **파일**: 
  - [`frontend/src/components/PredictionCard.js`](frontend/src/components/PredictionCard.js) — `games[0]` → `games` 배열 전체 매핑
  - [`frontend/src/components/PostseasonCard.js`](frontend/src/components/PostseasonCard.js) — 포스트시즌 브라켓 UI 구현

### Task 3.4: 포스트시즌 시뮬레이션 개선
- **파일**: [`backend/services/simulation_service.py`](backend/services/simulation_service.py)
- **변경**: 실제 포스트시즌 대진표 기반 시뮬레이션 추가

---

## Step 4: DeepSeek API 교체

**목표**: Gemini → DeepSeek API로 퀴즈 생성기 교체

### Task 4.1: DeepSeek API 연동
- **파일**: [`backend/services/quizmaker.py`](backend/services/quizmaker.py) (Step 1.5에서 router 변환 완료)
- **변경**: `google.generativeai` → `openai` 라이브러리로 교체
- DeepSeek API: `https://api.deepseek.com/v1`, 모델: `deepseek-chat`

```python
# quizmaker.py (DeepSeek API 버전)
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

def generate_daily_quizzes() -> list[dict] | None:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "KBO 야구 퀴즈를 JSON 배열로 생성해주세요."},
            {"role": "user", "content": "오늘 날짜의 KBO 퀴즈 5개를 생성해주세요."}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
```

### Task 4.2: 퀴즈 생성 API 엔드포인트 추가
- **파일**: [`backend/main.py`](backend/main.py)
- **변경**: `POST /api/quiz/generate` 엔드포인트 추가 (관리자 전용, 스케줄러에서 호출)

---

## Step 5: 스케줄러 + 배포 정리

**목표**: GitHub Actions + Docker/Nginx 최종 정리

### Task 5.1: GitHub Actions 워크플로우 생성
- **신규**: `.github/workflows/daily_pipeline.yml`
- 매일 KST 06:00 실행: 크롤링 → 피처 재구축 → 모델 재학습 → 전 경기 예측 → 퀴즈 생성 → 포인트 정산

```yaml
name: Daily KBO Pipeline

on:
  schedule:
    - cron: '0 21 * * *'  # KST 06:00 (UTC 21:00)
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run daily pipeline
        run: |
          docker-compose exec backend python -m services.crawler_service
          docker-compose exec backend python -m services.model_service
          docker-compose exec backend python -m services.quizmaker
          docker-compose exec backend python -m services.ranking_service
```

### Task 5.2: Docker Compose 최종 업데이트
- **파일**: [`docker-compose.yml`](docker-compose.yml)
- **변경**:
  - `db` 서비스 제거 (Supabase로 대체)
  - `nginx` 서비스 추가
  - Firebase env → Supabase/DeepSeek env로 교체
  - `frontend/Dockerfile`에서 `REACT_APP_API_BASE_URL` ARG 제거

### Task 5.3: Nginx 설정 파일 추가
- **신규**: `nginx/nginx.conf`
- **설정**: `/api/*` → 백엔드 프록시, `/*` → 프론트엔드 정적 파일

```nginx
server {
    listen 3000;
    
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### Task 5.4: 배포 문서 업데이트
- **파일**: [`docs/README.md`](docs/README.md)
- **변경**: 최신 설치/배포 가이드 (Supabase, DeepSeek, GitHub Actions 포함) — 리팩토링 완료 후 최종 정리

---

## 5. 변경 파일 전체 목록

### 신규 파일 (7개)
| 파일 | Step | 설명 |
|------|------|------|
| `backend/services/admin_context.py` | 1 | contextvars 기반 admin_mode 관리 |
| `backend/supabase_config.py` | 2 | Supabase 클라이언트 설정 |
| `frontend/src/supabase.js` | 2 | Supabase Auth 클라이언트 |
| `.github/workflows/daily_pipeline.yml` | 5 | 일일 파이프라인 |
| `nginx/nginx.conf` | 5 | Nginx 리버스 프록시 설정 |

### 수정 파일 (17개)
| 파일 | Step | 변경 내용 |
|------|------|-----------|
| `backend/init_db.sql` | 1 | `weekly_score` 컬럼 추가 |
| `backend/services/admin_service.py` | 1 | `admin_context` 사용으로 변경 |
| `backend/config.py` | 1,3 | `ADMIN_MODE` → `admin_context`, `_admin` 상수 제거 |
| `backend/services/quizmaker.py` | 1,4 | FastAPI router 변환 + Gemini→DeepSeek |
| `backend/main.py` | 1,2,3,4 | router 등록, Firestore 제거, `_admin` 제거, 순위 동적 계산, 퀴즈 생성 API |
| `backend/requirements.txt` | 1,2 | `openai` 추가, `supabase-py` 추가, `firebase-admin` 제거 |
| `backend/services/ranking_service.py` | 2 | Firestore → Supabase PostgreSQL |
| `frontend/src/App.js` | 2 | Supabase Auth로 변경 |
| `frontend/src/pages/LoginPage.js` | 2 | Supabase OAuth 로그인 |
| `frontend/src/components/Navbar.js` | 2 | Supabase 로그아웃 |
| `frontend/package.json` | 2 | `@supabase/supabase-js` 추가, `firebase` 제거 |
| `frontend/src/components/PredictionCard.js` | 3 | 다중 게임 표시 |
| `frontend/src/components/PostseasonCard.js` | 3 | 포스트시즌 브라켓 UI |
| `backend/services/simulation_service.py` | 3 | 포스트시즌 대진표 시뮬레이션 |
| `docker-compose.yml` | 5 | Firebase env→Supabase env, db 제거, nginx 추가 |
| `frontend/Dockerfile` | 5 | `REACT_APP_API_BASE_URL` ARG 제거 |
| `docs/README.md` | 5 | 최신 설치/배포 가이드 |

### 삭제 파일 (2개)
| 파일 | Step | 설명 |
|------|------|------|
| `backend/firebase_config.py` | 2 | Firebase 설정 파일 제거 |
| `frontend/src/firebase.js` | 2 | Firebase Auth 제거 |

---

## 6. 내 PC에서 실행하는 방법

### 6.1 사전 준비
1. **Docker Desktop** 설치 (Windows/Mac) 또는 Docker Engine (Linux)
2. **GitHub**에서 프로젝트 clone
3. **Supabase 계정** 생성 및 프로젝트 개설
4. **DeepSeek API 키** 확보

### 6.2 .env 파일 작성

```ini
# --- Supabase ---
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# --- Backend DB (Supabase) ---
DATABASE_URL=postgresql://user:pass@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres

# --- API Keys ---
DEEPSEEK_API_KEY=your-deepseek-key
ADMIN_API_KEY=your-admin-key

# --- Frontend (Supabase) ---
REACT_APP_SUPABASE_URL=https://your-project.supabase.co
REACT_APP_SUPABASE_ANON_KEY=your-anon-key
```

### 6.3 실행

```bash
# 1. Clone
git clone [repo-url] Laions_project
cd Laions_project

# 2. .env 파일 생성 (위 내용 참고)

# 3. 실행
docker compose up -d

# 4. 접속
# http://localhost:3000  ← 프론트엔드 (Nginx가 /api/*를 백엔드로 전달)
```

### 6.4 데이터 수집 및 모델 학습

```bash
# 크롤러 실행 (2021~2025년 데이터 수집)
curl -X POST "http://localhost:3000/api/crawler/historical?start_year=2021&end_year=2025" \
  -H "X-API-Key: your-admin-key"

# 피처 재구축
curl -X POST "http://localhost:3000/api/features/rebuild" \
  -H "X-API-Key: your-admin-key"

# 모델 학습
curl -X POST "http://localhost:3000/api/model/retrain"
```

---

## 7. 서버 배포 방법 (연휴 후)

```bash
# 1. 내 PC의 코드를 서버에 복사
# 방법 A: GitHub
git push origin main
# 서버에서: git pull origin main

# 방법 B: SCP
scp -r ./Laions_project user@server:/path/to/

# 방법 C: USB

# 2. 서버에서 실행
cd /path/to/Laions_project
docker compose up -d

# 3. 시연 PC에서 접속
# http://서버-Tailscale-IP:3000
```

---

## 8. Tailscale 네트워크 구성

```mermaid
flowchart TB
    subgraph Tailscale["🔗 Tailscale Mesh Network"]
        DevPC["내 개인 PC"]
        Server["회사 서버 (Linux)"]
        DemoPC["시연 PC (Windows)"]
    end

    DevPC <--> Server
    DemoPC <--> Server
    
    DevPC -->|"docker compose"| LocalApp["localhost:3000"]
    Server -->|"docker compose"| ServerApp["서버:3000"]
    DemoPC -->|"브라우저"| ServerApp
```

---

## 9. Supabase vs Firebase 비교

| 항목 | Firebase | Supabase |
|------|----------|----------|
| **DB** | Firestore (NoSQL) | PostgreSQL (SQL) |
| **Auth** | Firebase Auth | Supabase Auth |
| **가격** | 사용량 기반 | 사용량 기반 (유사) |
| **로컬 개발** | firebase emulator | Supabase CLI (local dev) |
| **Docker 필요** | ❌ (클라우드) | ❌ (클라우드) |
| **환경 변수** | 6개 + credentials.json | 2개 (URL + Key) |
| **SQL 쿼리** | ❌ (NoSQL) | ✅ (PostgreSQL) |
| **실시간 구독** | ✅ | ✅ |

---

## 10. 의사결정 기록

- **Docker Compose + Tailscale** 조합으로 환경 문제 해결 가능 확인
- **Nginx 리버스 프록시** 추가로 API 호출 주소 문제 해결
- **Supabase 전환**으로 DB + Auth + Firestore 단일화 (docker-compose 간소화)
- **Supabase와 Nginx는 별개의 문제** - Supabase를 써도 Nginx는 필요
- 리팩토링은 **내 PC에서 연휴 중** 진행, 완료 후 서버에 배포
- **Step 1.1, 1.2 제거**: 이후 Step에서 자연 해결되므로 불필요
- **Step 3.2 + 4.3 통합**: 같은 파일(`main.py`)을 함께 수정
