# mateon-ai

"Mate-On"(팀 매칭 서비스)의 AI 서버. 자연어 구조화, 임베딩 생성, 유사도·룰 기반 스코어링, 텍스트
생성(요약/동기/스카우트 메시지)을 담당하는 **완전 무상태(stateless) FastAPI 서비스**다.

- 데이터베이스를 갖지 않는다 — 임베딩 벡터를 포함한 모든 영속 데이터는 백엔드
  ([mateon-backend](https://github.com/eagleindesert/mateon-backend))가 저장·소유한다.
- 매 요청에 필요한 데이터(임베딩 벡터 포함)를 전부 받아서 계산만 하고 반환한다.
- 후보 선정(필터링)은 백엔드가 하고, AI 서버는 그 후보군 내에서의 재랭킹·조립만 담당한다.

## 기술 스택

- **Python 3.13**, [FastAPI](https://fastapi.tiangolo.com/) + [Pydantic v2](https://docs.pydantic.dev/)
- [uv](https://docs.astral.sh/uv/) — 패키지/환경 관리
- [OpenAI SDK](https://github.com/openai/openai-python) — `gpt-4.1-mini`(구조화 추출/텍스트 생성),
  `text-embedding-3-small`(임베딩, 1536차원)
- [tenacity](https://tenacity.readthedocs.io/) — OpenAI 호출 재시도
- [pytest](https://docs.pytest.org/) + [ruff](https://docs.astral.sh/ruff/) — 테스트/린트

## 시작하기

### 요구 사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- OpenAI API Key

### 설치

```bash
uv sync
```

### 환경 변수

`.env.example`을 복사해 `.env`를 만들고 값을 채운다.

```bash
cp .env.example .env
```

| 변수 | 설명 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_LLM_MODEL` | 구조화 추출/텍스트 생성 모델 (기본값 `gpt-4.1-mini`) |
| `OPENAI_EMBEDDING_MODEL` | 임베딩 모델 (기본값 `text-embedding-3-small`) |
| `INTERNAL_SHARED_SECRET` | 모든 엔드포인트가 요구하는 `X-Internal-Secret` 헤더 값 |

### 서버 실행

```bash
uv run uvicorn app.main:app --reload
```

기본값(`127.0.0.1`)은 이 컴퓨터에서만 접근 가능하다. 다른 컴퓨터(예: 백엔드 서버)에서 호출하게
하려면 모든 네트워크 인터페이스에 바인딩하고 방화벽에서 포트를 열어야 한다.

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

실행 후 아래에서 확인 가능:

- `GET /health` — 헬스체크
- `GET /docs` — Swagger UI (대화형 API 문서)
- `GET /openapi.json` — OpenAPI 스펙 원본

### 테스트

```bash
uv run pytest
```

기본 실행은 OpenAI 호출을 mock으로 대체한 단위 테스트만 돈다. 실제 API를 호출하는 e2e 테스트는
`@pytest.mark.live`로 분리되어 있어 기본 실행에서 제외된다. 역할 코드 정규화, LLM-as-judge
판별력, 임베딩 유사도가 실제로 말이 되는지는 아래로 따로 확인한다(비용 발생, 가끔만 실행):

```bash
uv run pytest -m live
```

### 린트

```bash
uv run ruff check .
```

## 프로젝트 구조

```
app/
  core/            # 설정(Settings), 프롬프트 로더
  api/             # 헬스체크, 내부 인증 의존성
  openai_client/   # OpenAI 호출 래퍼 (구조화 추출/임베딩, 재시도 포함)
  schemas/         # Pydantic 스키마 (요청 / LLM 출력 / 응답, 셋을 구분해서 관리)
  scoring/         # 코사인 유사도, Score Engine, 공통 룰 유틸
  features/
    team_embedding/    # 팀 임베딩 계산
    user_to_team/       # 제안(USER_TO_TEAM): 의도 추출, 추천, 제안 조립
    team_to_user/        # 역제안(TEAM_TO_USER): 추천, 제안 조립
    recommendation/       # 추천 이유 생성 (방향 공통)
prompts/           # LLM 시스템 프롬프트 (.txt, 코드와 분리 관리)
tests/             # pytest — 단위 테스트 + tests/fixtures/ 캐시된 실제 임베딩 데이터
scripts/           # 픽스처 생성 스크립트, LLM-as-judge 검증 스크립트
docs/              # 백엔드 연동용 API 계약 문서
```

## API 문서

- `docs/api-contract-draft.md` — 엔드포인트별 요청/응답 예시와 설계 배경 설명
- `docs/openapi.json` — 실제 구현에서 뽑은 OpenAPI 스펙 원본 (최종 계약 확정용)
- `docs/backend-integration-team-embedding.md`, `docs/backend-integration-user-to-team.md`,
  `docs/backend-integration-team-to-user.md` — 백엔드(Java/Spring Boot) 기준 실제 연동 코드 예시

## 시뮬레이션 UI

배포된(또는 로컬) 서버를 실제로 호출하면서 팀 임베딩 → 제안 → 역제안 전체 흐름을 눈으로 확인할
수 있는 Streamlit 앱이다. `docs/api-contract-draft.md`의 예시 값을 기본값으로 채워뒀다.

```bash
uv run streamlit run demo/app.py
```

브라우저가 열리면 사이드바에 Base URL과 `X-Internal-Secret`을 입력하고, 탭 순서(팀 임베딩 →
유저 의도 추출 → 제안/역제안)대로 버튼을 눌러보면 된다. AI 서버는 무상태라 이 화면이 "백엔드"
역할을 대신해서 계산된 임베딩 벡터를 세션 동안만 들고 있는다.

## 프롬프트 & 품질 검증

LLM 시스템 프롬프트는 코드에 하드코딩하지 않고 `prompts/*.txt`로 분리해 `app.core.prompts.
load_prompt()`로 읽는다. 생성된 텍스트(summary/message/reason)가 설계 원칙(사람에 대한 절대
평가 금지, ID/점수 미언급 등)을 지키는지는 아래 스크립트로 수동 점검할 수 있다.

```bash
uv run python scripts/judge_outputs.py
```

## 평가 픽스처 재생성

가상 팀/유저 fixture는 `tests/fixtures/*.json`에 캐싱되어 있어 평소 테스트는 API를 호출하지
않는다. 실제 API로 다시 생성하려면:

```bash
uv run python scripts/generate_team_fixtures.py
uv run python scripts/generate_user_fixtures.py
```

## 배포

이 서비스는 DB가 없는 완전 무상태 서버라, 어딘가에서 프로세스가 계속 떠 있고 환경변수만
안전하게 주입되면 배포가 끝난다. `Procfile`이 이미 있어 Railway/Render 같은 PaaS에 GitHub
저장소를 연결하기만 하면 자동으로 인식한다.

1. [Railway](https://railway.app) 또는 [Render](https://render.com)에서 GitHub 저장소
   (`mateon-ai`)를 연결한다.
2. 환경변수를 설정한다: `OPENAI_API_KEY`, `OPENAI_LLM_MODEL`, `OPENAI_EMBEDDING_MODEL`,
   `INTERNAL_SHARED_SECRET`(운영용으로 새로 생성 — 로컬 `.env` 값과 다르게 유지 권장).
3. 배포하면 **재시작해도 바뀌지 않는 영구 URL**이 발급된다 (예:
   `https://mateon-ai-production.up.railway.app`). 이 URL과 `INTERNAL_SHARED_SECRET`을
   백엔드 팀에 전달하면 된다.

로컬 개발 중 임시로 외부에 노출해서 테스트하고 싶을 때는 (URL이 재시작마다 바뀌어도 괜찮다면)
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)의
quick tunnel도 계정 없이 바로 쓸 수 있다:

```bash
cloudflared tunnel --url http://localhost:8000
```
