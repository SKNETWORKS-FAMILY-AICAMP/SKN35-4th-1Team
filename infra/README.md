# infra — 배포

```text
브라우저 → nginx (:80/:443, Flutter 정적 파일) ─/api, /admin, /mcp→ web (Django, uvicorn :8000) → TiDB · Chroma · OpenAI
```

| 파일 | 내용 |
| --- | --- |
| `Dockerfile.backend` | Django 이미지 (Python 3.12 + uv + uvicorn) |
| `docker-compose.yaml` | `web`(Django) + `nginx` |
| `nginx/default.conf` | 정적 파일 서빙, API 프록시, SSE 버퍼링 끔 |
| `build-frontend.sh` | Flutter Web 빌드 → `frontend/build/web` |

## 로컬 실행

레포 루트에서 실행한다. `.env`가 없어도 뜨지만 DB를 쓰는 API는 `.env`(TiDB·OpenAI·Chroma)가 있어야 한다.

```bash
./infra/build-frontend.sh
HTTP_PORT=8080 docker compose -f infra/docker-compose.yaml up -d --build
curl http://localhost:8080/api/health
```

- 화면: http://localhost:8080 · API 문서: http://localhost:8080/api/docs
- 서버 없이 화면만 보려면 `ARTLOG_DEMO=true ./infra/build-frontend.sh`
- 끄기: `docker compose -f infra/docker-compose.yaml down`
- 로그: `docker compose -f infra/docker-compose.yaml logs -f web`

## EC2 배포

1. EC2 생성: Ubuntu 24.04, t3.small 이상, 보안그룹 22(내 IP), 80, 443
2. 접속 후 Docker 설치

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu   # 다시 접속하면 sudo 없이 docker 사용
   ```

3. 코드와 비밀값 준비

   ```bash
   git clone <레포 주소> && cd SKN35-4th-1Team
   cp .env.example .env   # 실제 값 입력. DJANGO_DEBUG=false, DJANGO_ALLOWED_HOSTS=<도메인 또는 IP>
   ```

4. Flutter 빌드 결과 올리기 (EC2에서는 Flutter 빌드가 메모리 부족으로 실패하기 쉬워서 로컬에서 빌드 후 복사)

   ```bash
   # 로컬에서
   ./infra/build-frontend.sh
   rsync -az frontend/build/web/ ubuntu@<EC2>:SKN35-4th-1Team/frontend/build/web/
   ```

5. 실행: `docker compose -f infra/docker-compose.yaml up -d --build`

## HTTPS (도메인 연결 후)

```bash
docker run --rm -v "$PWD/infra/certbot/www:/var/www/certbot" -v "$PWD/infra/certbot/conf:/etc/letsencrypt" \
  certbot/certbot certonly --webroot -w /var/www/certbot -d <도메인> --email <이메일> --agree-tos -n
```

발급 후 `nginx/default.conf`에 443 서버 블록(`ssl_certificate /etc/letsencrypt/live/<도메인>/fullchain.pem`)을 추가하고, 80은 HTTPS로 리다이렉트한다. Django `.env`에 `CSRF_TRUSTED_ORIGINS=https://<도메인>`도 넣는다 (settings 반영 필요).

## 확인한 것 (2026-11-04, 로컬 Docker)

- `/api/health` 200, `/api/docs` 200, `/admin/` 302 (nginx → Django)
- `/`와 Flutter 경로(`/artworks/1`) 200, `main.dart.js` gzip 전송
- SSE: 1초 간격 이벤트가 nginx를 거쳐 1초 간격 그대로 도착 (버퍼링 없음)

## 남은 것

- `settings.py` 운영 설정: `STATIC_ROOT`(관리자 CSS), `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS` — 고태민과 협의 후
- HTTPS 443 서버 블록, CD 자동 배포
