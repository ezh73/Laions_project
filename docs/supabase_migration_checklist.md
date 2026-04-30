# Supabase 마이그레이션 준비물 체크리스트

> 현재 프로젝트: Firebase Auth + Firestore + PostgreSQL (로컬)
> 목표: Supabase (Auth + PostgreSQL) 단일화

---

## 1. Supabase 계정 및 프로젝트 설정

### 1.1 Supabase 계정
- [ ] [supabase.com](https://supabase.com) 회원가입 (GitHub 계정으로 가능)
- [ ] **무료 티어**: PostgreSQL 500MB, Auth 50,000 users/month, 2GB bandwidth
  - 현재 규모에 충분하지만, 향후 확장 시 유료 플랜 고려

### 1.2 Supabase 프로젝트 생성
- [ ] 프로젝트명: `laions-fan-app` (또는 원하는 이름)
- [ ] Database password 설정 (안전하게 보관)
- [ ] Region: **Tokyo (ap-northeast-1)** — 한국에서 가장 가까움
- [ ] 생성 완료 후 대시보드 진입

### 1.3 발급받아야 할 키/URL (총 4개)

| 항목 | Supabase 대시보드 위치 | 용도 |
|------|----------------------|------|
| **Project URL** | Settings → API → Project URL | 백엔드 `SUPABASE_URL` |
| **anon/public key** | Settings → API → anon public | 프론트엔드 Supabase 클라이언트 |
| **service_role key** | Settings → API → service_role (⚠️ 비공개) | 백엔드 관리자 작업용 |
| **Database Connection String** | Settings → Database → Connection string → URI | 백엔드 `DATABASE_URL` (SQLAlchemy용) |

> **주의:** `service_role` 키는 RLS(Row-Level Security)를 우회하므로 절대 프론트엔드에 노출 금지

---

## 2. Supabase Auth 설정 (Google OAuth)

### 2.1 Google Cloud Console 준비
- [ ] [Google Cloud Console](https://console.cloud.google.com) 접속
- [ ] 프로젝트 생성 또는 기존 프로젝트 선택
- [ ] **OAuth 동의 화면** 설정 (External, 테스트용)
  - 필요한 Scope: `openid`, `email`, `profile`
- [ ] **사용자 인증 정보** → OAuth 2.0 클라이언트 ID 생성
  - 애플리케이션 유형: **웹 애플리케이션**
  - 승인된 리디렉션 URI: `https://[PROJECT_REF].supabase.co/auth/v1/callback`
    - `[PROJECT_REF]`는 Supabase 프로젝트 대시보드 URL에서 확인 가능

### 2.2 Supabase Auth Provider 등록
- [ ] Supabase 대시보드 → Authentication → Providers
- [ ] **Google** 활성화
- [ ] Client ID와 Client Secret 입력 (Google Cloud Console에서 발급)
- [ ] 저장

---

## 3. 데이터베이스 마이그레이션 준비

### 3.1 현재 DB 구조 분석 (완료)
현재 [`init_db.sql`](jihoon/old_project/Laions_project/backend/init_db.sql) 기준 테이블 목록:

| 테이블 | 마이그레이션 방식 |
|--------|------------------|
| `kbo_games` | 그대로 이관 |
| `match_features` | 그대로 이관 |
| `ai_predictions` | 그대로 이관 |
| `kbo_schedule` | 그대로 이관 |
| `user_rankings` | **`weekly_score` 컬럼 추가 필요** |
| `user_predictions` | 그대로 이관 |
| `user_quizzes` | 그대로 이관 |
| `samfan_quizzes` | 그대로 이관 |
| `team_rank` | 그대로 이관 (Phase 7에서 동적 계산으로 대체 예정) |
| `kbo_games_admin` | **삭제** (트랜잭션 롤백 방식으로 대체) |
| `match_features_admin` | **삭제** |
| `ai_predictions_admin` | **삭제** |
| `kbo_schedule_admin` | **삭제** |
| `scheduler_logs` | **신규 생성** (Phase 6) |

### 3.2 `user_rankings` 테이블 수정 사항
```sql
-- 현재: weekly_score 없음
CREATE TABLE user_rankings (
    user_id VARCHAR(50) PRIMARY KEY,
    nickname VARCHAR(50) NOT NULL,
    prediction_score INTEGER DEFAULT 0,
    quiz_score INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- 수정 후: weekly_score 추가
CREATE TABLE user_rankings (
    user_id VARCHAR(50) PRIMARY KEY,
    nickname VARCHAR(50) NOT NULL,
    prediction_score INTEGER DEFAULT 0,
    quiz_score INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    weekly_score INTEGER DEFAULT 0,    -- 👈 추가
    last_updated TIMESTAMP DEFAULT NOW()
);
```

### 3.3 데이터 이관 순서
1. Supabase SQL Editor에서 [`init_db.sql`](jihoon/old_project/Laions_project/backend/init_db.sql) 실행 (`_admin` 테이블 제외, `weekly_score` 추가)
2. 로컬 PostgreSQL에서 Supabase PostgreSQL으로 데이터 COPY
   ```bash
   # pg_dump로 특정 테이블만 덤프
   pg_dump -h localhost -U $DB_USER -d $DB_NAME \
     --data-only --table=kbo_games --table=match_features \
     --table=ai_predictions --table=kbo_schedule \
     --table=user_rankings --table=user_predictions \
     --table=user_quizzes --table=samfan_quizzes \
     --table=team_rank > laions_data.sql
   
   # Supabase DB에 임포트
   psql -h $SUPABASE_DB_HOST -U postgres -d postgres -f laions_data.sql
   ```

---

## 4. 백엔드 코드 변경 사항

### 4.1 제거할 파일
| 파일 | 이유 |
|------|------|
| [`backend/firebase_config.py`](jihoon/old_project/Laions_project/backend/firebase_config.py) | Firebase Firestore 의존성 제거 |
| `backend/firebase-credentials.json` | Firebase 서비스 계정 키 파일 |

### 4.2 수정할 파일
| 파일 | 변경 내용 |
|------|----------|
| [`backend/config.py`](jihoon/old_project/Laions_project/backend/config.py) | `DATABASE_URL` → Supabase PostgreSQL URL로 변경, `_admin` 테이블 분기 제거 |
| [`backend/database.py`](jihoon/old_project/Laions_project/backend/database.py) | Supabase 세션 관리로 변경 (선택 사항, SQLAlchemy 호환) |
| [`backend/main.py`](jihoon/old_project/Laions_project/backend/main.py) | `firebase_admin` import 제거, Firestore 참조 코드 제거 |
| [`backend/services/ranking_service.py`](jihoon/old_project/Laions_project/backend/services/ranking_service.py) | Firestore → Supabase PostgreSQL로 점수 저장 로직 변경 |
| [`backend/requirements.txt`](jihoon/old_project/Laions_project/backend/requirements.txt) | `firebase-admin` 제거, `supabase-py` 추가 |

### 4.3 생성할 파일
| 파일 | 용도 |
|------|------|
| [`backend/supabase_config.py`](jihoon/old_project/Laions_project/backend/supabase_config.py) | Supabase 클라이언트 초기화 (관리자 작업용) |

### 4.4 Supabase 클라이언트 초기화 예시
```python
# backend/supabase_config.py
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
```

---

## 5. 프론트엔드 코드 변경 사항

### 5.1 패키지 변경
```bash
npm uninstall firebase
npm install @supabase/supabase-js
```

### 5.2 제거할 파일
| 파일 | 이유 |
|------|------|
| [`frontend/src/firebase.js`](jihoon/old_project/Laions_project/frontend/src/firebase.js) | Firebase SDK 의존성 제거 |

### 5.3 생성할 파일
| 파일 | 용도 |
|------|------|
| [`frontend/src/supabase.js`](jihoon/old_project/Laions_project/frontend/src/supabase.js) | Supabase 클라이언트 초기화 (anon key 사용) |

### 5.4 Supabase 클라이언트 초기화 예시
```javascript
// frontend/src/supabase.js
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Google 로그인
export const loginWithGoogle = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
  });
  if (error) throw error;
  return data;
};

// 로그아웃
export const logout = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
};

// 인증 상태 변경 리스너
export const onAuthStateChangedListener = (callback) => {
  return supabase.auth.onAuthStateChange((event, session) => {
    callback(session?.user || null);
  }).data.subscription;
};
```

### 5.4 수정할 파일
| 파일 | 변경 내용 |
|------|----------|
| [`frontend/src/App.js`](jihoon/old_project/Laions_project/frontend/src/App.js) | `./firebase` → `./supabase` import 변경 |
| [`frontend/src/pages/LoginPage.js`](jihoon/old_project/Laions_project/frontend/src/pages/LoginPage.js) | Firebase → Supabase Auth 로그인으로 변경 |
| [`frontend/src/components/Navbar.js`](jihoon/old_project/Laions_project/frontend/src/components/Navbar.js) | Firebase `logout` → Supabase `logout` import 변경 |

---

## 6. 환경 변수 (.env) 변경

### 6.1 제거할 변수 (Firebase)
```
FIREBASE_API_KEY
FIREBASE_AUTH_DOMAIN
FIREBASE_PROJECT_ID
FIREBASE_STORAGE_BUCKET
FIREBASE_MESSAGING_SENDER_ID
FIREBASE_APP_ID
ADMIN_DATABASE_URL          # _admin DB 분기 제거
```

### 6.2 추가할 변수 (Supabase)
```
# Supabase
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:6543/postgres

# 프론트엔드
REACT_APP_SUPABASE_URL=https://[PROJECT_REF].supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

### 6.3 유지할 변수
```
ADMIN_API_KEY=your-admin-api-key
GEMINI_API_KEY=...           # Phase 5에서 DeepSeek API Key로 교체
```

---

## 7. Docker Compose 변경

### 7.1 제거할 서비스
```yaml
# docker-compose.yml에서 제거
services:
  db:                          # 👈 PostgreSQL 서비스 제거 (Supabase 사용)
    image: postgres:15-alpine
    ...
```

### 7.2 제거할 ARG (frontend Dockerfile)
```dockerfile
# frontend/Dockerfile에서 제거
ARG REACT_APP_FIREBASE_API_KEY
ARG REACT_APP_FIREBASE_AUTH_DOMAIN
ARG REACT_APP_FIREBASE_PROJECT_ID
ARG REACT_APP_FIREBASE_STORAGE_BUCKET
ARG REACT_APP_FIREBASE_MESSAGING_SENDER_ID
ARG REACT_APP_FIREBASE_APP_ID
```

### 7.3 추가할 ARG (frontend Dockerfile)
```dockerfile
ARG REACT_APP_SUPABASE_URL
ARG REACT_APP_SUPABASE_ANON_KEY
```

---

## 8. 전체 준비물 요약

### 계정/서비스
| 서비스 | 필요 항목 | 비용 |
|--------|----------|------|
| Supabase | 계정 + 프로젝트 | 무료 (500MB) |
| Google Cloud Console | OAuth 2.0 클라이언트 ID/Secret | 무료 |

### 키/시크릿 (총 6개)
| # | 키 이름 | 출처 | 보안 등급 |
|---|---------|------|----------|
| 1 | `SUPABASE_URL` | Supabase Settings → API | 공개 가능 |
| 2 | `SUPABASE_ANON_KEY` | Supabase Settings → API | 공개 가능 (프론트엔드) |
| 3 | `SUPABASE_SERVICE_ROLE_KEY` | Supabase Settings → API | **🔴 절대 비공개** |
| 4 | `DATABASE_URL` (Supabase) | Supabase Settings → Database | **🔴 비공개** |
| 5 | Google OAuth Client ID | Google Cloud Console | 공개 가능 |
| 6 | Google OAuth Client Secret | Google Cloud Console | **🔴 비공개** |

### 코드 변경 파일 (총 13개)
- **삭제:** 2개 (`firebase_config.py`, `firebase.js`, `firebase-credentials.json`)
- **생성:** 2개 (`supabase_config.py`, `frontend/src/supabase.js`)
- **수정:** 9개 (`config.py`, `database.py`, `main.py`, `ranking_service.py`, `requirements.txt`, `App.js`, `LoginPage.js`, `Navbar.js`, `docker-compose.yml`, `frontend/Dockerfile`, `.env`)

### 예상 작업 시간
- Supabase 계정/프로젝트 설정: **15분**
- Google OAuth 설정: **10분**
- DB 스키마 마이그레이션: **20분**
- 데이터 이관: **10분**
- 백엔드 코드 수정: **1-2시간**
- 프론트엔드 코드 수정: **1시간**
- 통합 테스트: **1시간**
- **총 예상: 약 4-5시간**
