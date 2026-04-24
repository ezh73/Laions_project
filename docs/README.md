# Laions — 팬 참여형 AI 야구 예측 플랫폼

> "AI와 함께 즐기는 야구 — 팬들의 예측과 경쟁의 장"

-----

## 1\. 프로젝트 개요 (Overview)

기존 야구 포털은 경기 정보나 뉴스 등 일방적인 정보 제공에 그쳐 팬들의 참여가 제한적  
Laions는 이러한 문제를 해결하기 위해, AI를 단순한 예측 도구가 아닌 \*\*"함께 즐기는 경쟁 상대"\*\*로 제시하여   
팬들이 직접 예측하고, 배우고, 경쟁하는 새로운 경험을 제공하는 것을 목표로 함

-----

## 2\. 핵심 기능 (Features)

  * **AI 승리예측 대결:** LightGBM 기반의 AI 모델의 정규시즌의 경기결과 예측과 대결, AI를 이기면 가산점 부여
  * **AI 퀴즈:** Gemini API로 생성된 퀴즈를 풀며 재미와 학습을 동시에 얻는 참여형 콘텐츠
  * **주간 팬 랭킹:** 예측과 퀴즈 점수를 합산하여 팬들 간의 순위를 보여주는 게임화(Gamification) 요소
  * **정규시즌/포스트시즌/비시즌 모드:** 시즌 진행도에 따라 정규시즌 경기 예측, 포스트시즌 삼성라이온즈의 다음 시리즈 진출 확률 예측, 비시즌엔 이번시즌 성적을 기반으로 Monte Carlo 기법을 사용하여 다음시즌 순위 예측

-----

## 3\. 아키텍처 및 기술 스택 (Architecture & Tech Stack)

| 구분 | 기술 | 선택 이유 |
| :--- | :--- | :--- |
| **Frontend** | React + MUI | 컴포넌트 기반 구조로 유지보수 용이, 빠른 UI 구현 |
| **Backend** | FastAPI | Python AI 생태계와 자연스럽게 연결, 비동기 처리에 우수 |
| **Database** | PostgreSQL | 정형 데이터 관리에 안정적이며, Python과 호환성이 높음 |
| **AI Model** | LightGBM | ELO, 폼 등 수치형 피처 처리에 최적화되고 학습 속도가 빠름 |
| **Scheduler**| GitHub Actions | 서버 종료 시에도 매일 데이터 수집 및 예측 자동화 가능 |

-----



## 4. 설치 및 실행 (Setup)

본 프로젝트를 로컬 환경에서 실행하기 위해서는 프론트엔드와 백엔드를 각각 설정하고 실행해야 함.

---

### **1️⃣ Backend Server (첫 번째 터미널)**

1.  **프로젝트 클론 및 이동**
    ```bash
    git clone https://github.com/ezh73/Laions_project.git   
    cd Laions_project/backend
    ```

2.  **가상환경 생성 및 활성화**
    ```bash
    python -m venv venv

    # Windows PowerShell
    venv\Scripts\activate

    # macOS / Linux
    # source venv/bin/activate
    ```

3.  **의존성 패키지 설치**
    ```bash
    pip install -r requirements.txt
    ```

4.  **(중요) 환경 변수 및 인증 키 설정**
    프로젝트를 실행하려면 API 키와 데이터베이스 정보가 필요. `backend` 폴더 안에 아래의 두 파일을 직접 생성.

    **가. `.env` 파일 생성**
    `backend` 폴더에 `.env` 파일을 만들고, 아래 내용을 복사하여 자신의 키 값으로 채우기.
    ```ini
    # --- PostgreSQL 데이터베이스 연결 정보 ---
    DATABASE_URL="postgresql://user:password@localhost:5432/laions_db"

    # --- Google Gemini API 키 ---
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

    # --- 관리자 API 인증을 위한 비밀 키 ---
    ADMIN_API_KEY="YOUR_SECRET_ADMIN_KEY"

    # --- (선택) 관리자 모드 시뮬레이션 설정 ---
    ADMIN_MODE=true
    ADMIN_DATE=2025-10-29
    ADMIN_OVERRIDE_MODE=postseason
    ```

    **나. `firebase-credentials.json` 파일 생성**
    Firebase 프로젝트에서 서비스 계정 비공개 키를 다운로드한 후, 파일명을 `firebase-credentials.json`으로 변경하여 `backend` 폴더에 위치.

5.  **백엔드 서버 실행**
    ```bash
    uvicorn main:app --reload
    ```
    > 백엔드 서버가 `http://localhost:8000` 에서 실행.

6. **모델 pkl위치는 backend폴더 내**

---

### **2️⃣ Frontend Server (두 번째 터미널)**

1.  **프론트엔드 폴더로 이동 및 의존성 설치**
    ```bash
    cd ../frontend  
    npm install
    ```

2.  **프론트엔드 서버 실행**
    ```bash
    npm start
    ```
    > 웹 브라우저에서 `http://localhost:3000` 으로 접속하여 서비스를 확인.

-----
