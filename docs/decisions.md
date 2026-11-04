# 기술적 의사결정 기록

발표 질의응답 대비용. 각자 담당 부분을 "무엇을 골랐나 → 왜 → 대안은 왜 안 했나" 순서로 짧게 적는다.

---

## 배포·인프라 (박수휘)

### 1. 앱 서버는 AWS EC2 + Docker Compose

- **결정**: EC2(Ubuntu 24.04, t3.small) 한 대에 Docker Compose로 `web`(Django)과 `nginx` 두 컨테이너를 띄운다.
- **이유**
  - 과제 목표가 "클라우드 활용 인프라 구축 및 배포"라서 서버를 직접 구성한다. 3차는 Railway·Vercel이 대신 해 줬다.
  - Docker로 묶어서 내 PC와 서버에서 똑같이 돌아간다. 로컬에서 먼저 검증하고 EC2에는 그대로 올린다.
  - t3.small(메모리 2GB): t2.micro(1GB)는 chromadb 등 패키지가 커서 빌드 중 메모리가 부족하다.
- **대안**: Elastic Beanstalk, ECS는 설정이 더 많고 하루 일정에 맞지 않는다. 수업에서 배운 EC2 + Docker Compose 방식을 따랐다.

### 2. DB는 RDS 대신 TiDB Cloud 유지

- **결정**: AWS RDS를 쓰지 않고 3차부터 쓰던 TiDB Cloud를 그대로 연결한다.
- **이유**
  - **벡터 검색**: 작품 임베딩을 `VECTOR(1536)` 칸에 저장하고 거리 검색을 한다. RDS MySQL은 벡터 타입·검색을 지원하지 않는다.
  - 데이터가 이미 적재되어 있다 (작품 276점, 문서 426건, 청크 1,775개). 옮기면 재적재·재임베딩이 필요하다.
  - Django는 `django-tidb`로 이미 연결했다. TiDB는 MySQL과 호환돼서 Django ORM을 그대로 쓴다.
- **역할 구분**: EC2는 앱을 **실행**하는 곳, RDS·TiDB는 데이터를 **저장**하는 곳이다. RDS만으로는 배포할 수 없다.

### 3. 화면과 API를 nginx 한 곳에서 같은 주소로 제공

- **결정**: nginx가 `/`는 Flutter 빌드 파일(HTML·CSS·JS)을 직접 주고, `/api`·`/admin`·`/mcp`는 Django로 넘긴다.
- **이유**
  - 3차는 프론트(Vercel)와 백엔드(Railway) 주소가 달라서 CORS 설정이 필요했다. 같은 주소로 합치면 CORS 문제가 사라진다.
  - 정적 파일은 nginx가 Django보다 훨씬 빠르게 준다. gzip 압축과 캐시도 nginx에서 처리한다.

### 4. 도슨트 스트리밍을 위해 nginx 버퍼링 끔, uvicorn(ASGI) 사용

- **결정**: nginx `/api` 경로에 `proxy_buffering off`, `proxy_read_timeout 300s`. Django는 Gunicorn(WSGI) 대신 uvicorn(ASGI)으로 실행한다.
- **이유**
  - 도슨트 답변은 SSE로 토큰을 하나씩 보낸다. nginx 기본값(버퍼링)이면 답변이 다 끝난 뒤 한꺼번에 화면에 뜬다.
  - 스트리밍 응답은 비동기 서버(ASGI)가 연결을 오래 붙잡아도 다른 요청을 막지 않는다.
- **검증**: 1초 간격으로 이벤트를 보내는 테스트 서버를 nginx 뒤에 붙여, 1초 간격 그대로 도착하는 것을 확인했다 (2026-11-04, 로컬 Docker).

### 5. Flutter는 서버가 아닌 로컬에서 빌드

- **결정**: `infra/build-frontend.sh`로 로컬에서 빌드하고 결과(`frontend/build/web`)만 EC2로 복사한다.
- **이유**: Flutter 웹 빌드는 메모리를 많이 써서 t3.small에서 실패하기 쉽다. 서버에는 Flutter를 설치하지 않는다.

### 6. 비밀값은 이미지·Git에 넣지 않음

- **결정**: `.env`, `*.pem`은 `.gitignore`와 `.dockerignore`에 모두 넣는다. 비밀값은 실행할 때 `env_file`로만 넣는다.
- **이유**: 이미지나 저장소에 한 번 들어간 키는 지워도 기록에 남는다.

### 7. CI는 GitHub Actions

- **결정**: `main`·`dev`로 push하거나 PR을 올리면 pytest, 배포 이미지 빌드, nginx 설정 검사를 자동으로 돌린다.
- **이유**: 세 명이 동시에 작업해서, 깨진 코드나 깨진 Docker 빌드가 `dev`에 들어가기 전에 막는다.

---

## Django 백엔드 (고태민)

- 왜 Django + Django Ninja인가:
- 왜 기존 테이블을 `inspectdb`로 가져왔나:

## LangGraph·검색 (차윤정)

- 왜 LangGraph인가:
- 왜 하이브리드 검색(BM25 + RRF)인가:
