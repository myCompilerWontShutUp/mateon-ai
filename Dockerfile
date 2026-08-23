# 무상태 FastAPI 서버 — DB 없음, 실행에 필요한 건 프로세스 + 환경변수뿐이다.
# uv 공식 권장 패턴(레이어 캐싱을 위해 의존성 설치와 앱 코드 복사를 분리)을 따른다.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# 의존성 정의만 먼저 복사 — app/ 코드만 바뀌면 이 레이어는 캐시된다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 런타임에 실제로 필요한 것만 복사한다 — tests/scripts/docs 등은 이미지에 안 넣는다.
COPY app ./app
COPY prompts ./prompts
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# root로 돌릴 이유가 없다 — 쓰기 권한이 필요한 파일이 없는 무상태 서버.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# /health는 인증 불필요(app/api/router.py) — 컨테이너 자체가 뜨는지만 확인하는 용도.
# Railway 등 PaaS가 주입하는 $PORT를 읽어야 한다 — 하드코딩된 8000은 로컬에서만 맞고,
# 실제 배포 환경에서 Railway가 할당한 포트와 어긋나 502를 유발한다(2026-08-23 실측 발견).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')"]

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
