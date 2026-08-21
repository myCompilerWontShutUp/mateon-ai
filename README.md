# mateon-ai

"Mate-On"(팀 매칭 서비스)의 AI 서버. 자연어 구조화, 임베딩 생성, 유사도·룰 기반 스코어링, 텍스트
생성(요약/동기/스카우트 메시지)을 담당하는 **완전 무상태(stateless) FastAPI 서비스**다.

- 데이터베이스를 갖지 않는다 — 임베딩 벡터를 포함한 모든 영속 데이터는 백엔드
  ([mateon-backend](https://github.com/eagleindesert/mateon-backend))가 저장·소유한다.
- 매 요청에 필요한 데이터(임베딩 벡터 포함)를 전부 받아서 계산만 하고 반환한다.
- 후보 선정(필터링)은 백엔드가 하고, AI 서버는 그 후보군 내에서의 재랭킹·조립만 담당한다.
- 예외적으로 Supabase를 하나 붙여 쓴다 — 다만 도메인 데이터(팀/유저/임베딩/제안)를
  저장·조회하는 용도가 아니라, 응답에 다시 읽혀 들어가지 않는 **쓰기 전용 로그**(judge 판정·
  선택 이벤트)와 배포와 무관한 주기로 조정되는 **튜닝 설정값**(클러스터별 가중치) 전용이다.
  자세한 경계는 아래 "모니터링·데이터 기반 가중치 보정" 참고.

## 기술 스택

- **Python 3.13**, [FastAPI](https://fastapi.tiangolo.com/) + [Pydantic v2](https://docs.pydantic.dev/)
- [uv](https://docs.astral.sh/uv/) — 패키지/환경 관리
- [OpenAI SDK](https://github.com/openai/openai-python) — `gpt-5.6-luna`(구조화 추출/텍스트 생성),
  `gpt-5.6-terra`(LLM-as-judge 판정, `OPENAI_JUDGE_MODEL`), `text-embedding-3-small`(임베딩,
  1536차원) *(2026-08-21 — 기존 `gpt-4.1-mini`/`gpt-5.6-luna` 조합에서 성능·속도·토큰 사용량
  개선을 위해 교체, 자세한 사유는 CLAUDE.md "## 모델 확정" 참고)*
- [tenacity](https://tenacity.readthedocs.io/) — OpenAI 호출 재시도
- [Supabase](https://supabase.com/)(`supabase-py`) — judge 판정 로그·선택 이벤트 기록(쓰기 전용),
  클러스터별 가중치 설정값 읽기 전용. 도메인 데이터 저장소가 아니다(아래 "모니터링·데이터 기반
  가중치 보정" 참고)
- [pytest](https://docs.pytest.org/) + [ruff](https://docs.astral.sh/ruff/) — 테스트/린트
- [Docker](https://www.docker.com/) — 백엔드 로컬 테스트·배포용 컨테이너 이미지(아래 "Docker로
  실행" 참고)
- **dev 전용**(프로덕션 이미지에서 제외): `numpy`/`umap-learn`(공모전 지형도 시각화),
  `scikit-learn`(`umap-learn`의 하위 의존성이자 ML 사전 구축 실험용), `matplotlib`(ML 실험
  결과 로컬 시각화)

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
| `OPENAI_LLM_MODEL` | 구조화 추출/텍스트 생성 모델 (기본값 `gpt-5.6-luna`) |
| `OPENAI_EMBEDDING_MODEL` | 임베딩 모델 (기본값 `text-embedding-3-small`) |
| `OPENAI_JUDGE_MODEL` | LLM-as-judge 전용 모델 (생성 모델과 분리, GPT-5 이상급 권장 — 기본값 없음, 미설정 시 시작 실패) |
| `INTERNAL_SHARED_SECRET` | 모든 엔드포인트가 요구하는 `X-Internal-Secret` 헤더 값 |
| `SUPABASE_URL` | 모니터링 전용 Supabase 프로젝트 URL (기본값 없음, 미설정 시 시작 실패) |
| `SUPABASE_SERVICE_ROLE_KEY` | 위 프로젝트의 service_role 키 (기본값 없음, 미설정 시 시작 실패) |
| `MAX_CONTEST_IMAGE_BYTES` | 공모전 이미지 업로드 크기 상한, bytes (기본값 10MB) |
| `MAX_PORTFOLIO_PDF_BYTES` | 포트폴리오 PDF 업로드 크기 상한, bytes (기본값 20MB) |
| `PORTFOLIO_PDF_MAX_PAGES` | 포트폴리오 PDF에서 Vision 모델로 넘길 최대 페이지 수 (기본값 15) |

`OPENAI_JUDGE_MODEL`/`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`는 도메인 매칭 기능과 무관하게
품질 모니터링·가중치 보정 전용이지만, 다른 필수값과 동일하게 기본값이 없다 — 미설정 시 조용히
넘어가지 않고 시작 시점에 바로 실패한다.

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
  core/            # 설정(Settings), 프롬프트 로더, background.py(fire-and-forget 비동기 태스크)
  api/             # 헬스체크, 내부 인증 의존성
  openai_client/   # OpenAI 호출 래퍼 (구조화 추출/임베딩, 재시도 포함)
  supabase_client/ # Supabase 클라이언트 래퍼 (모니터링 전용, 도메인 데이터 아님)
  schemas/         # Pydantic 스키마 (요청 / LLM 출력 / 응답, 셋을 구분해서 관리)
  scoring/         # 코사인 유사도, Score Engine, 공통 룰 유틸, cluster.py/cluster_weights.py/
                   #   cluster_weight_store.py(클러스터별 가중치 보정)
  evaluation/      # Hit@10/NDCG 평가용 순수 계산 모듈(metrics/scoring_arms/simulation) — 실제
                   #   프로덕션 스코어링 코드를 재사용, 평가 로직을 따로 재구현하지 않음.
                   #   ml_pretrain.py는 정식 ML(로지스틱 회귀) 사전 구축 실험 공유 로직
  features/
    team_embedding/    # 팀 임베딩 계산
    user_to_team/       # 제안(USER_TO_TEAM): 의도 추출, 추천, 제안 조립
    team_to_user/        # 역제안(TEAM_TO_USER): 추천, 제안 조립
    recommendation/       # 추천 이유 생성 (방향 공통)
    contest_extraction/    # 공모전 이미지 OCR+LLM 자동 입력
    portfolio_summary/      # 포트폴리오 PDF OCR+LLM 경력 요약
    quality/                # LLM-as-judge 판정 + 선택 이벤트 로그(둘 다 Supabase 쓰기 전용)
prompts/           # LLM 시스템 프롬프트 (.txt, 코드와 분리 관리)
tests/             # pytest — 단위 테스트 + tests/fixtures/ 실제 test_*.py가 로드하는 캐시 데이터
scripts/           # 픽스처 생성 스크립트, 평가/시각화 배치, LLM-as-judge 검증 스크립트
data/              # 스크립트 전용 원본/생성 데이터 (pytest가 로드하지 않음 — tests/fixtures와 구분)
docs/              # 백엔드 연동용 API 계약 문서, docs/monitoring/ 모니터링 관련 리포트·초안
supabase/          # 모니터링 테이블 SQL 마이그레이션 (judge_results/cluster_selection_events/
                   #   cluster_weight_config/ml_pretrain_dummy_events)
```

## API 문서

- `docs/api-contract-draft.md` — 엔드포인트별 요청/응답 예시와 설계 배경 설명
- `docs/openapi.json` — 실제 구현에서 뽑은 OpenAPI 스펙 원본 (최종 계약 확정용)
- `docs/backend-integration-team-embedding.md`, `docs/backend-integration-user-to-team.md`,
  `docs/backend-integration-team-to-user.md` — 백엔드(Java/Spring Boot) 기준 실제 연동 코드 예시
- `docs/monitoring/` — 모니터링·가중치 보정 관련 문서 모음(아래 "모니터링·데이터 기반 가중치
  보정" 섹션에서 각 문서를 따로 링크함)

## 시뮬레이션 UI

배포된(또는 로컬) 서버를 실제로 호출하면서 팀 임베딩 → 제안 → 역제안 전체 흐름을 눈으로 확인할
수 있는 Streamlit 앱이다. `docs/api-contract-draft.md`의 예시 값을 기본값으로 채워뒀다.

```bash
uv run streamlit run demo/app.py
```

브라우저가 열리면 사이드바에 Base URL과 `X-Internal-Secret`을 입력하고, 탭 순서(팀 임베딩 →
유저 의도 추출 → 제안/역제안)대로 버튼을 눌러보면 된다. AI 서버는 무상태라 이 화면이 "백엔드"
역할을 대신해서 계산된 임베딩 벡터를 세션 동안만 들고 있는다.

"2. 유저 의도 추출" 탭은 실제 채팅 시뮬레이터다 — 자기소개를 입력하고 "채팅 시작"을 누르면,
AI가 생성한 재진술/유도 질문(`assistant_message`)이 채팅 버블로 표시되고 하단 입력창으로 계속
답장하면서 대화가 이어진다. 재질문 문구를 프론트가 만들지 않고 AI 서버가 직접 생성한다는 걸
눈으로 확인할 수 있다.

## 프롬프트 & 품질 검증

LLM 시스템 프롬프트는 코드에 하드코딩하지 않고 `prompts/*.txt`로 분리해 `app.core.prompts.
load_prompt()`로 읽는다. 생성된 텍스트(summary/message/reason)가 설계 원칙(사람에 대한 절대
평가 금지, ID/점수 미언급 등)을 지키는지는 **LLM-as-judge**(`app/features/quality/judge.py`)가
판정한다. 두 가지 경로로 동작한다:

- **라이브 섀도 감사(자동)**: 제안/추천 이유 텍스트가 생성될 때마다 응답 경로를 막지 않는
  fire-and-forget으로 자동 판정하고 Supabase(`judge_results`)에 기록한다. `passes=true`는
  최소 기록만, `passes=false`는 입력·추론·위반 항목까지 상세 기록한다(30일 후 자동 익명화 —
  아래 섹션 참고). 사람이 직접 실행할 필요는 없다.
- **수동 스크립트**: 특정 시점에 표본을 골라 직접 점검하고 싶을 때 아래를 실행한다(같은
  `judge.py` 모듈을 얇게 감싼 CLI).

```bash
uv run python scripts/judge_outputs.py
```

## 모니터링·데이터 기반 가중치 보정 (Supabase)

핵심 서비스 계약(추천/제안 엔드포인트)은 여전히 완전 무상태다. 다만 "요청/응답이 도메인
데이터를 저장·조회하지 않는다"는 원칙에 대한 **의도적이고 좁은 예외**로, 다시 응답에 읽혀
들어가지 않는 쓰기 전용 텔레메트리(judge 판정 로그·선택 이벤트)와, 배포와 무관한 주기로
조정되는 튜닝 설정값(클러스터별 가중치)만 Supabase에 둔다. 자세한 설계 배경·의사결정 이력은
프로젝트 로컬 설계 문서에 있고(저장소에는 커밋되지 않음), 아래는 실행 방법과 산출물 문서
위주로 정리한다.

- **클러스터별 가중치 보정**: "클러스터"는 `RoleCode×ExperienceLevel`(유저)/
  `recruiting_roles×ContestField`(팀) 같은 고정 ENUM 조합 키다. 실제(또는 아직 BE 미연동
  구간에서는 합성) 선택 이벤트에서 클러스터별 lift를 계산해 `cluster_weight_config`에 버전과
  함께 기록하고(`is_active` 플래그로 롤백 가능), 라이브 추천 엔드포인트가 요청마다 이 값을
  읽어 `WEIGHTS`를 클러스터별로 미세 조정한다. 재계산은 온라인이 아니라 오프라인 배치다:

```bash
uv run python scripts/generate_eval_synthetic_selections.py   # BE 연동 전 합성 이벤트 생성
uv run python scripts/run_cluster_weight_batch.py              # 실 이벤트가 있으면 그걸 우선 사용
```

- **Hit@10/NDCG 평가**: 임베딩만 / 임베딩+메타데이터(프로덕션) / 임베딩+메타데이터+보정모델 /
  단순추론(LLM 직접 순위) 4종을 비교해 보정모델이 비용과 성능을 모두 잡는지 확인한다. 재현
  순서:

```bash
uv run python scripts/generate_eval_fixtures.py              # 팀·유저 50개씩, 실제 임베딩
uv run python scripts/generate_eval_ground_truth.py          # 상위 모델로 정답 라벨 생성
uv run python scripts/generate_eval_synthetic_selections.py
uv run python scripts/run_cluster_weight_batch.py
uv run python scripts/run_eval.py                            # 결과: docs/monitoring/hit-at-10-eval-report.md
```

  리포트의 핵심은 "보정모델이 프로덕션보다 점수가 높다"는 주장이 아니다 — 지금 데이터 규모에서는
  그 효과가 작고 통계적으로 약하다는 걸 리포트 자체가 정직하게 밝힌다. 대신 클러스터별 보정값이
  어디서 왔는지 끝까지 추적 가능하고, 잘못된 값이 들어가도 코드 배포 없이 즉시 롤백할 수 있다는
  걸 실제 데이터로 보여주는 게 핵심이다 — 재현 사례:
  [`docs/monitoring/cluster-weight-audit-trail-example.md`](docs/monitoring/cluster-weight-audit-trail-example.md).
- **BE 전달용 계약 초안**: 위 기능이 요구하는 API 변경사항(`selection_context` 필드 등)을
  한 문서로 모아둔 게
  [`docs/monitoring/selection-feedback-draft.md`](docs/monitoring/selection-feedback-draft.md)다.

## 픽스처·평가·시각화 스크립트

`scripts/`에 있는 로컬 생성 스크립트 전체 목록이다. 전부 실제 OpenAI API를 호출하므로(비용
발생) 결과는 `tests/fixtures/*.json` 또는 `data/*.json`에 캐싱해두고 평소 테스트/실행은 그
캐시를 읽는다 — 매번 다시 실행할 필요는 없다.

| 스크립트 | 용도 | 출력 |
|---|---|---|
| `generate_team_fixtures.py` / `generate_user_fixtures.py` | 정답 매칭 검증용 팀 10개·유저 fixture | `tests/fixtures/teams.json`, `users.json` |
| `generate_eval_fixtures.py` | Hit@10 평가용 팀·유저 50개씩(결정론적 생성) | `tests/fixtures/eval_teams.json`, `eval_users.json` |
| `generate_eval_ground_truth.py` | 평가용 정답 라벨(상위 모델) | `tests/fixtures/eval_ground_truth.json` |
| `generate_eval_synthetic_selections.py` | 클러스터 가중치 보정용 합성 선택 이벤트 | `tests/fixtures/eval_synthetic_selections.json` |
| `generate_eval_definitions_llm.py` | Hit@10 평가용 팀·유저 50개씩(`gpt-5.6-terra`로 생성, 결정론적 생성의 대안) | `data/eval_llm_generated_definitions_cache.json`(gitignore) |
| `run_eval_on_llm_pool.py` | 위 gpt-5.6-terra 풀로 `run_eval.py`와 동일 방식 재측정 | `docs/monitoring/hit-at-10-eval-report-llm-pool.md` |
| `run_cluster_weight_batch.py` | 클러스터별 가중치 lift 계산 후 Supabase 기록 | `cluster_weight_config`(Supabase) |
| `run_eval.py` | Hit@10/NDCG 4종 비교 리포트 생성 | `docs/monitoring/hit-at-10-eval-report.md` |
| `generate_contest_graph_visualization.py` | 공모전 임베딩을 PCA+UMAP으로 2차원 축소해 분야별 색칠 | `data/contest_graph_visualization.json`(+ 임베딩 캐시) |
| `train_cluster_weight_ml_pretrain.py` | 정식 ML(로지스틱 회귀) 사전 구축 — 혼합 데이터 학습 + 시각화 | `data/ml_pretrain_*.json`/`*.png`(gitignore) |
| `train_cluster_weight_ml_pretrain_gpt56terra.py` | 위와 동일, gpt-5.6-terra 데이터만(Supabase 저장분 재사용) | `data/ml_pretrain_weight_comparison_gpt56terra.png`(gitignore) |
| `eval_ml_pretrain_weights.py` | 학습된 ML 가중치를 실제 추천 스코어링에 꽂아 Hit@10/NDCG/선호 회복률 측정 | `data/ml_pretrain_weight_eval_report.md`(gitignore) |
| `judge_outputs.py` | LLM-as-judge 수동 점검 CLI | 콘솔 출력 |

`generate_eval_definitions_llm.py`부터 아래 ML 관련 스크립트까지는 `data/*.json`/`*.png` 산출물이
비결정론적(LLM 생성 또는 매 학습마다 값이 조금씩 달라짐)이라 `.gitignore` 대상이다 — 다른
캐시들과 달리 GitHub에는 올라가지 않는다.

## 실험: 정식 ML(로지스틱 회귀) 사전 구축 (2026-08-21)

클러스터별 가중치 보정(위 섹션)은 정식 ML이 아니라 "선택된 후보 평균 − 전체 평균"이라는 닫힌
형태 수식이다. "정식 ML로 미리 만들어둘 수 있는가"를 실제로 검증해본 실험이며, **결론은 지금은
휴리스틱을 유지하는 것**이다 — 근거를 아래에 그대로 남긴다.

**방식**: 후보를 "선택됨(1)/안됨(0)" 이진 라벨로 펼쳐 컴포넌트 점수(similarity/role_match/
deficit_fit/beginner_fit/activity_style_match)를 피처로 로지스틱 회귀(`LogisticRegressionCV`,
`class_weight='balanced'`, 같은 선택 세션 내 후보가 학습/검증에 걸쳐 섞이지 않도록
`GroupKFold`로 정규화 강도 C를 튜닝)를 학습한다. 더미 데이터(결정론적 50 + gpt-5.6-terra 50,
합 100건)로 학습했으므로 예측값 자체는 의미가 없고, 학습·서빙 파이프라인이 정상 작동하는지와
방법론에 따라 결과가 어떻게 달라지는지를 보는 게 목적이다.

**학습된 가중치 비교** (① 기본 WEIGHTS 고정 / ② 휴리스틱 보정 / ③ 로지스틱 회귀 학습):

| 컴포넌트 | ① 기본 | ② 휴리스틱(혼합 데이터) | ③ ML(혼합 데이터) | ③ ML(gpt-5.6-terra 전용) |
|---|---|---|---|---|
| similarity | 0.400 | 0.403 | 0.302 | 0.269 |
| role_match | 0.200 | 0.248 | 0.236 | 0.294 |
| deficit_fit | 0.150 | 0.141 | 0.136 | 0.226 |
| beginner_fit | 0.200 | 0.169 | 0.292 | 0.212 |
| activity_style_match | 0.050 | 0.039 | 0.034 | 0.000 |

**실제 추천 점수까지 측정**(같은 두 평가셋에 Hit@10/NDCG/선호 회복률 재적용, ③번 lift는
Supabase에 쓰지 않고 로컬 계산만 사용 — 감사 추적 문서가 참조하는 라이브 값 보존):

| 평가셋 | 비교군 | Hit@10 | NDCG@10(LLM 정답) | NDCG@10(선호) | 선호 회복률 |
|---|---|---|---|---|---|
| 결정론적 | ② 프로덕션(고정) | 1.000 | 0.997 | 0.995 | 0.780 |
| 결정론적 | ML(혼합 데이터 학습) | 1.000 | 0.998 | 0.995 | **0.820** |
| 결정론적 | ML(gpt-5.6-terra 전용) | 1.000 | 0.998 | 0.990 | 0.580 |
| gpt-5.6-terra | ② 프로덕션(고정) | 1.000 | 0.933 | 0.942 | 0.900 |
| gpt-5.6-terra | ML(혼합 데이터 학습) | 1.000 | 0.957 | 0.963 | **0.940** |
| gpt-5.6-terra | ML(gpt-5.6-terra 전용) | 1.000 | 0.974 | 0.978 | 0.920 |

*(2026-08-21 판정 모델을 `gpt-5.6-luna`→`gpt-5.6-terra`로 교체하면서 두 평가셋의 정답
라벨을 재생성했고, 이 표는 그 새 라벨 기준으로 다시 측정한 값이다 — 학습된 가중치 자체는
더미 이벤트 스냅샷에서 나온 값이라 안 바뀌었으므로 새 API 호출 없이 로컬 재계산만으로
갱신했다. 절대 수치는 다소 올랐지만 아래 해석은 이전과 동일하게 유지된다.)*

**해석**: 두 데이터 소스를 섞어 학습한 모델은 두 평가셋 모두에서 프로덕션을 앞섰지만(다양한
데이터로 학습 → 더 잘 일반화), gpt-5.6-terra 데이터만으로 학습한 모델은 자기 데이터와 비슷한
평가셋에서만 잘하고 결정론적 평가셋에서는 프로덕션보다 못했다(0.580) — 좁은 데이터로 학습한
전형적인 과적합이다. 이 문제는 ML만의 약점이 아니다 — 휴리스틱도 "50명 중 1~2건에서만 순위가
바뀐다"는 같은 소표본 취약성을 이미 보였다(Hit@10 리포트 참고). 즉 알고리즘을 바꿔도 근본
원인(데이터 부족)은 해결되지 않는데, ML은 해석 가능성만 잃고 학습 파이프라인·의존성·재학습
주기 같은 운영 부담을 늘린다 — **지금은 이득 없이 비용만 커서 휴리스틱을 유지한다.** 실 데이터가
쌓이면 같은 스크립트를 무료로 재실행해 재검토할 수 있는 상태로 남겨뒀다.

**Supabase 저장 시 주의**: 더미 선택 이벤트는 `cluster_selection_events`(실 데이터 전용)가
아니라 별도 테이블 `ml_pretrain_dummy_events`에 저장한다 — `run_cluster_weight_batch.py`가
`cluster_selection_events`를 source 구분 없이 전부 "실 데이터"로 취급하기 때문에, 더미를
거기 넣으면 나중에 실 데이터가 들어와도 걸러낼 방법이 없다. 이 테이블은 정식 클러스터 가중치
파이프라인에서 전혀 읽지 않는다 — `supabase/migrations/
20260821000000_create_ml_pretrain_dummy_events.sql`을 SQL Editor에서 적용해야 만들어진다.

## Docker로 실행 (백엔드 로컬 테스트용)

DB가 없는 무상태 서버라 이미지 하나만 뜨면 끝난다 — 별도 컨테이너(DB 등)를 같이 띄울 필요가
없어 `docker-compose.yml`은 두지 않았다.

```bash
docker build -t mateon-ai .
docker run -p 8000:8000 --env-file .env mateon-ai
```

`.env` 파일에 위 "환경 변수" 표의 값을 채워서 넘기면 된다 — 기본값 없는 필수 설정값은
미설정 시 컨테이너가 시작 시점에 바로 실패한다. `GET /health`는 인증 없이 컨테이너가 떴는지만
확인할 수 있고, 그 외 모든 엔드포인트는 `X-Internal-Secret` 헤더가 필요하다(`docs/api-contract-draft.md` 참고).

## 배포

이 서비스는 DB가 없는 완전 무상태 서버라, 어딘가에서 프로세스가 계속 떠 있고 환경변수만
안전하게 주입되면 배포가 끝난다. `Procfile`이 이미 있어 Railway/Render 같은 PaaS에 GitHub
저장소를 연결하기만 하면 자동으로 인식하고, `Dockerfile`도 있어 Docker 기반 배포를 지원하는
PaaS에서도 그대로 쓸 수 있다.

1. [Railway](https://railway.app) 또는 [Render](https://render.com)에서 GitHub 저장소
   (`mateon-ai`)를 연결한다.
2. 위 "환경 변수" 표 전체를 설정한다(`INTERNAL_SHARED_SECRET`은 운영용으로 새로 생성 — 로컬
   `.env` 값과 다르게 유지 권장).
3. 배포하면 **재시작해도 바뀌지 않는 영구 URL**이 발급된다 (예:
   `https://mateon-ai-production.up.railway.app`). 이 URL과 `INTERNAL_SHARED_SECRET`을
   백엔드 팀에 전달하면 된다.

로컬 개발 중 임시로 외부에 노출해서 테스트하고 싶을 때는 (URL이 재시작마다 바뀌어도 괜찮다면)
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)의
quick tunnel도 계정 없이 바로 쓸 수 있다:

```bash
cloudflared tunnel --url http://localhost:8000
```
