# SKN35-4th-1Team · Docentalk 4차

3차 `SKN35-3rd-1Team` Docentalk을 고도화하는 프로젝트예요. 계획은 [docs/00_4차_계획정리.pdf](docs/00_4차_계획정리.pdf)에 있어요.

## 실행

```bash
cp .env.example .env
uv sync
cd backend && uv run python manage.py runserver
```

`http://localhost:8000/api/health` → `{"status": "ok"}`, API 문서는 `/api/docs`에서 볼 수 있어요.

## 구조

| 경로 | 내용 | 상태 |
|---|---|---|
| `backend/config/` | Django 설정, Ninja API (`api.py`) | 새로 만듦 |
| `backend/accounts` `catalog` `chat` `library` `documents` | Django 앱 | 빈 앱 |
| `backend/llm/{rag,docent,clients}` | 3차 RAG·도슨트·외부 연결 코드 | 복사함. `app.models`·`app.schemas`·`app.db`·`app.core`·FastAPI import를 Django로 옮겨야 함 |
| `backend/scripts/`, `backend/tests/` | 3차 전처리·평가 스크립트, 평가 문항·테스트 | 복사함. 위와 같은 import 정리 필요 |
| `frontend/` | 3차 Flutter Web (`lib`, `web`, `assets`, `public`) | 복사함. `API_BASE_URL`을 Django 주소로 바꿔서 빌드 |
| `data/` | 3차 수집·전처리 데이터 | 복사함 |
