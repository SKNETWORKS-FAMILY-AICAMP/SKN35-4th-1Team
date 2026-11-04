# 미술관 도슨트 (Docentalk) 4차 — 역할 분담 계획서

- 팀: SKN35 4th 1Team (3인)
- 일정: 2026-11-04(수) 오전·오후 → 11/05(목) 오전 최종 점검·마감
- 상세 계획: [docs/00_4차_계획정리.pdf](docs/00_4차_계획정리.pdf)

목차

1. [계획서 메인](#1-계획서-메인)
2. [날짜별 오전·오후 담당업무](#2-날짜별-오전오후-담당업무)
3. [진행상황](#3-진행상황)

---

## 1. 계획서 메인

### 1-1. 프로젝트 개요

3차 Docentalk(작품·생애 문서만 근거로 답하는 미술관 도슨트 챗봇)을 고도화한다. 기능은 3차 그대로 가져오고, 백엔드·답변 흐름·배포 구조를 바꾼다.

| 항목 | 내용 |
| --- | --- |
| 주제(과제 요구) | LLM을 연동한 내외부 문서 기반 질의응답 웹페이지 개발 |
| 내외부 문서 | 외부: 미술관·백과사전 등에서 수집한 공개 문서(작품 해설·작가 생애·비교 문서)<br>내부: 팀이 검수해 직접 작성한 보정문·보강문(`data/mappings/document_corrections.json`, `document_supplements.json`). 답변 시 보정문을 우선한다 |
| 개선 포인트 | 일반 답변과 스트리밍이 같은 그래프를 써서 동작이 어긋나지 않음, 3차 평가 피드백 반영(1-5), 자동 테스트(CI) |
| 범위 원칙 | 하루 일정이라 필수 산출물, 4차 목표, 3차 피드백만 한다. 나머지는 테스트 보고서에 "향후 과제"로 적는다 |

**4차 목표와 대응**

| 4차 목표 | 이번에 하는 것 | 담당 |
| --- | --- | --- |
| 요구사항 정리 및 화면 설계 | 요구사항 정의서(FR/NFR ID·우선순위), 화면설계서(화면 ID·구성·동작·연결 API) | 고태민, 박수휘 |
| Django 백엔드 | 프론트는 3차 Flutter Web을 그대로 쓴다(빌드 결과물 `build/web`이 HTML·CSS·JS이고 nginx가 정적 파일로 서빙). 백엔드는 FastAPI → Django + Django Ninja | 고태민 |
| LLM 연동 기능 | LangChain + LangGraph 그래프로 분류 → 검색 → 생성 → 검증 | 차윤정 |
| 클라우드 인프라 구축 및 배포 | AWS EC2 + Docker Compose + nginx + HTTPS, GitHub Actions CI | 박수휘 |

### 1-2. 역할 분담

| 담당 | 맡은 영역 | 책임 산출물 |
| --- | --- | --- |
| **고태민** | Django 이전 (FastAPI 라우트 → Django Ninja, SQLAlchemy → Django ORM, TiDB 연결, Firebase 토큰 검증, SSE 스트리밍) | `backend/config/`, `backend/{accounts,catalog,chat,library,documents}/`, 요구사항 정의서 |
| **차윤정** | LangGraph (분류 → 검색 → 생성 → 검증 그래프, 일반·스트리밍 통합, `refused` 수정), 평가 재실행 | `backend/llm/`, 테스트 계획 및 결과 보고서 |
| **박수휘** | AWS 배포 (Docker, nginx, HTTPS, EC2), CI, Flutter 빌드 연결 | `infra/`, `.github/workflows/`, 시스템 구성도, 화면설계서 |

### 1-3. 시스템 구성

```text
3차: Flutter Web(Vercel) → FastAPI(Railway) → Chroma + TiDB → OpenAI
4차: 브라우저 → nginx(EC2, HTTPS, Flutter 정적 파일) → Django(Gunicorn/Uvicorn, Docker) → LangGraph → Chroma Cloud + TiDB → OpenAI
```

| 단계 | 담당 |
| --- | --- |
| 1. API 라우팅·DB 연동·인증 (Django) | 고태민 |
| 2. 질문 분류 → 검색 → 생성 → 검증 (LangGraph) | 차윤정 |
| 3. 컨테이너·서버·HTTPS·CI (AWS) | 박수휘 |
| 4. 화면 (3차 Flutter Web 그대로, API 주소만 변경) | 박수휘 |
| 5. 평가 재실행·결과 정리 | 차윤정 |

| 구성 요소 | 선택 |
| --- | --- |
| 백엔드 | Python 3.12, uv, Django 6.0, Django Ninja, `django-tidb` |
| LLM 연동 | LangChain + **LangGraph**, OpenAI GPT 계열 |
| 임베딩 / 벡터 DB | text-embedding-3-small (1536차원) / Chroma Cloud |
| DB | TiDB Cloud |
| 인증 | Firebase Auth (서버는 ID 토큰만 검증, `firebase-admin`) |
| 화면 | Flutter Web (3차 배포본) |
| 배포 | AWS EC2 + Docker Compose + nginx + Let's Encrypt |
| CI | GitHub Actions (push 시 ruff + pytest) |

### 1-4. 필수 산출물

| 산출물 | 담당 | 비고 |
| --- | --- | --- |
| 요구사항 정의서 | 고태민 | 3차 README 기능 표에 FR/NFR ID와 우선순위 추가 |
| 화면설계서 | 박수휘 | `docs/readme-2026-10-15/` 캡처 기반, 화면 ID·구성·동작·연결 API |
| LLM 연동 웹 애플리케이션 | 전원 | 배포 주소로 시연 |
| 시스템 구성도 | 박수휘 | 1-3의 4차 구성을 mermaid로 |
| 테스트 계획 및 결과 보고서 | 차윤정 | 3차 기준 → 4차 개선 후 비교표 |
| 발표 자료 | 박수휘 | |

### 1-5. 3차 평가 피드백 반영

3차 평가서(10/18)에서 지적된 점을 4차에서 바로 고친다. 결과는 테스트 보고서 3차 → 4차 비교표에 넣는다.

| 3차 피드백 | 4차 조치 | 담당 |
| --- | --- | --- |
| 거절 상태값(`refused`) 정합성 75% | 서버가 출처 없음·"확인할 수 없" 문구를 보고 `refused=true`로 고치고, LangGraph 검증 노드에 넣는다 | 차윤정 |
| 청크 Recall@5 0.787, MRR 0.778, nDCG@5 0.751 | 한국어 BM25 + 벡터 검색을 RRF로 합치는 하이브리드 검색 (목표 0.85 / 0.80 / 0.80) | 차윤정 |
| 답변 거절 정책 일관성 | 범위 밖 판정을 그래프의 노드 하나로 모으고, 어느 단계에서 거절됐는지 응답 로그에 남긴다 | 차윤정 |
| 평가 문항 다양화 | 거절해야 할 질문 / 거절하면 안 되는 질문(과잉 거절) 문항을 추가하고 45문항과 함께 실행 | 차윤정, 고태민 |
| 검색 정확도·예외 처리 보완 (현직자 의견) | 헬스체크, 배포 환경 오류율·P95 측정 | 박수휘 |

### 1-6. 평가 기준 체크 (3차 평가표 기준)

| 평가 항목 | 배점 | 4차에서 보여 줄 것 |
| --- | ---: | --- |
| 기획 | 30 | 문제 정의(검증된 문서 기반 도슨트), 내외부 문서 정의(1-1), 모델·DB 선정 이유, 4차 목표·지표(3-3) |
| 산출물 | 40 | 필수 산출물 5종, 하이브리드 검색·LangGraph 동작, 배포 주소에서 화면·질의응답 정상 작동, Git 브랜치·PR 기록 |
| 발표·시연 | 30 | 구조와 LangGraph 흐름 설명, 배포 주소 실시연, 검색·답변 한계 설명, **기술적 의사결정 이유**, 역할 분담 |

**기술적 의사결정 기록** (발표 질의응답 대비, 각자 담당 부분을 한두 줄로 `docs/decisions.md`에 적는다)
- 왜 Django + Ninja인가 (과제 요구 + FastAPI 코드를 거의 그대로 옮길 수 있음) — 고태민
- 왜 LangGraph인가 (일반 답변·스트리밍 흐름 중복 제거, 흐름이 그림으로 나옴) — 차윤정
- 왜 하이브리드 검색·RRF인가 (고유명사·연도 질문에 벡터 검색이 약함) — 차윤정
- 왜 EC2 + Docker인가 (Railway·Vercel 대신 직접 인프라 구성, 같은 도메인이라 CORS 불필요) — 박수휘

### 1-7. 협업 규칙

- 브랜치: 담당자 브랜치(`TAEMIN`, `YOONJUNG`, `SOOHWI`) → `dev` → `main`
- 자기 브랜치에서 작업 후 `dev`로 PR, 다른 1명 확인 후 merge. `main` 직접 push 금지
- 작업 시작 전 `dev`를 받아와 충돌을 작게 유지
- **파일 담당**: `backend/` 앱·`config/`는 고태민, `backend/llm/`은 차윤정, `infra/`·`.github/`·`frontend/scripts/`·`docs/`는 박수휘
- **`pyproject.toml`, `uv.lock`, `backend/config/settings.py`는 셋 다 건드리므로** 고치기 전에 단톡에 알리고, 고친 뒤 바로 `dev`에 올린다
- API 키·DB 비밀번호·EC2 키(`.pem`)는 `.env`, GitHub Secrets, EC2 환경변수에만 둔다. 커밋 금지

---

## 2. 날짜별 오전·오후 담당업무

✅ 완료 · 🔄 진행 중 · 🔜 연기 · ⬜ 예정

### 11/04(수) 오전 — 기반 만들기

| 담당 | 오전 |
| --- | --- |
| **전원** | ✅ 최신 `dev` 받기, 역할·파일 담당 확인 |
| **고태민** | 🔄 **Django 버전 고정**: 지금 6.1.2가 깔려 있는데 `django-tidb`는 6.0까지만 지원 → `django>=6.0,<6.1` + `django-tidb` 추가<br>🔄 `DATABASES`를 sqlite → TiDB로 변경, `inspectdb`로 모델 뽑기 (`managed = False`로 기존 테이블 유지)<br>🔄 `app.models`·`app.schemas`·`app.db`·`app.core` import를 Django 쪽으로 바꾸기 시작 |
| **차윤정** | 🔄 `docent/service.py` `answer()` 흐름 정리 → 노드 목록 확정 (classify / retrieve / generate / validate)<br>🔄 LangGraph `StateGraph` 뼈대 작성, 노드에 기존 함수 감싸기<br>🔄 `refused` 수정: 출처 없음 또는 "확인할 수 없" 문구면 서버가 `refused=true`로 고치기 (`docent/grounding.py`) |
| **박수휘** | 🔄 `infra/` 작성: `Dockerfile`, `docker-compose.yml`, `nginx.conf`<br>🔄 EC2 생성, 보안그룹(22/80/443), Docker 설치<br>🔄 지금 있는 `/api/health`만으로 먼저 배포해 보기 |

### 11/04(수) 오후 — 기능 이전, 배포 연결

| 담당 | 오후 |
| --- | --- |
| **고태민** | ⬜ 3차 FastAPI 라우트 → Ninja 라우터 이전 (주소·응답 모양 3차와 동일)<br>⬜ Firebase ID 토큰 검증 연결<br>⬜ 채팅 SSE를 `StreamingHttpResponse`로 (이벤트 `token`·`replace`·`done` 유지)<br>⬜ Django Admin에 작품·문서 등록 |
| **차윤정** | ⬜ 일반 답변과 스트리밍이 같은 그래프 쓰게 연결 (`stream_mode="messages"`)<br>⬜ 고태민 채팅 API에 그래프 연결<br>⬜ 하이브리드 검색: kiwipiepy + `rank_bm25`로 BM25, 벡터 결과와 RRF로 합치기 (작가 별칭은 사용자 사전에)<br>⬜ 평가 재실행: `eval_retrieval.py` (벡터만 / +BM25 비교), `eval_docent.py` 45문항 |
| **고태민** (추가) | ⬜ 거절 / 과잉 거절 확인용 평가 문항 추가 (`backend/tests/questions/`) |
| **박수휘** | ⬜ HTTPS 적용 (도메인 + Let's Encrypt)<br>⬜ Flutter `API_BASE_URL` 변경 후 `flutter build web` → nginx 서빙<br>⬜ `settings.py` 운영 설정: `STATIC_ROOT`, `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`, gunicorn/uvicorn 의존성<br>⬜ `.github/workflows/ci.yml` (ruff + pytest)<br>⬜ 시스템 구성도, 화면설계서 작성 |

### 11/05(목) 오전 — 통합·최종 점검

| 담당 | 오전 |
| --- | --- |
| **전원** | ⬜ `dev` → `main` 통합, EC2에 최종본 배포<br>⬜ 시연 시나리오 한 번씩 돌려보기 (로그인 → 작품 → 채팅 → 출처 → 범위 밖 거절) |
| **고태민** | ⬜ 배포본 API 전체 확인 (401·대화 저장/복원·좋아요)<br>⬜ 발표 자료 마감 |
| **차윤정** | ⬜ 배포본으로 45문항 최종 실행<br>⬜ 테스트 보고서 마감 (3차 → 4차 비교표, 향후 과제) |
| **박수휘** | ⬜ 배포 후 응답 시간(P50/P95) 측정 → 보고서 전달 |

---

## 3. 진행상황

### 3-1. 필수 산출물

| 산출물 | 담당 | 상태 |
| --- | --- | --- |
| 요구사항 정의서 | 고태민 | ⬜ |
| 화면설계서 | 박수휘 | ⬜ |
| LLM 연동 웹 애플리케이션 | 전원 | ⬜ |
| 시스템 구성도 | 박수휘 | ⬜ |
| 테스트 계획 및 결과 보고서 | 차윤정 | ⬜ |
| 발표 자료 | 박수휘 | ⬜ |

### 3-2. 구조 변경 현황

| 항목 | 3차 | 4차 | 상태 |
| --- | --- | --- | --- |
| 백엔드 | FastAPI | Django + Ninja | ⬜ 빈 앱만 있음, 3차 import 정리 필요 |
| 답변 흐름 | if문 (일반·스트리밍 따로) | LangGraph 그래프 하나 | ⬜ |
| 배포 | Railway · Vercel | AWS EC2 + Docker + nginx | ⬜ |
| CI | 없음 | GitHub Actions | ⬜ |
| `refused` 정합성 | 6/8 (75%) | 목표 100% | ⬜ |
| 검색 | 벡터 검색만 | BM25 + 벡터 (RRF) | ⬜ |

### 3-3. 평가 비교 (테스트 보고서용)

| 지표 | 3차 | 4차 | 목표 |
| --- | ---: | ---: | ---: |
| `refused` 정합성 | 75% | | 100% |
| 종합 통과율 (45문항) | 95.6% | | 95% 이상 유지 |
| 문서 Hit@5 | 100% | | 100% 유지 |
| 청크 Recall@5 | 0.787 | | 0.85 |
| 청크 MRR | 0.778 | | 0.80 |
| 청크 nDCG@5 | 0.751 | | 0.80 |
| P95 응답 시간 | 5.9초 | | 10초 이하 |
