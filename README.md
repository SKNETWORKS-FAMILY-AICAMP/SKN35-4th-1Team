# SKN35-4th-1Team · Docentalk 4차

3차 `SKN35-3rd-1Team` Docentalk을 고도화하는 프로젝트예요. 계획은 [docs/00_4차_계획정리.pdf](docs/00_4차_계획정리.pdf)에 있어요.

## 실행

```bash
cp .env.example .env
uv sync
cd backend && uv run uvicorn config.asgi:application --reload
```

`http://localhost:8000/api/health` → `{"status": "ok"}`, API 문서는 `/api/docs`에서 볼 수 있어요. 채팅 스트리밍, MCP(`/mcp`), CORS는 ASGI에서 동작해서 `runserver`가 아니라 `uvicorn`으로 띄워요.

DB는 3차 데이터를 복사한 `4th_project`를 써요. `.env`의 `TIDB_DATABASE`를 `4th_project`로 두고, 3차 원본 `3rd_project`에는 `migrate`를 실행하지 않아요. Django 모델은 기존 테이블을 그대로 쓰는 `managed = False`예요.

## 구조

| 경로 | 내용 | 상태 |
|---|---|---|
| `backend/config/` | Django 설정, Ninja API (`api.py`), ASGI (`asgi.py`: Django + MCP + CORS) | 완료 |
| `backend/accounts` `catalog` `chat` `library` `documents` | Django 앱: API (`api.py`), 모델, Admin, 서비스, 저장소, 스키마 | 완료. DB 접근은 Django ORM |
| `backend/llm/{rag,docent,clients}` | RAG·LangGraph 도슨트·외부 연결 코드 | LangGraph 적용 |
| `backend/scripts/`, `backend/tests/` | 전처리·적재·평가 스크립트(`python -m scripts.x`), 평가 문항·테스트 | Django ORM으로 전환 |
| `frontend/` | 3차 Flutter Web (`lib`, `web`, `assets`, `public`) | 복사함. `API_BASE_URL`을 Django 주소로 바꿔서 빌드 |
| `data/` | 3차 수집·전처리 데이터 | 복사함 |
