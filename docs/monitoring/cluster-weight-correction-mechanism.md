# 클러스터별 가중치 보정 — 구현 메커니즘

이 문서는 "클러스터별 가중치 보정"이 실제로 어떤 순서로 동작하는지, 코드 위치와 함께 정리한다.
(2026-11-05 운영 정비 내용 반영)

## 이건 정식 ML이 아니다

회귀·그래디언트부스팅처럼 데이터로 파라미터를 학습(training)하는 모델이 아니다. **"선택된 후보의
평균 점수 − 보여준 후보 전체의 평균 점수"라는 닫힌 형태 수식 하나로 계산하는, 해석 가능한
휴리스틱**이다. 정식 ML 대신 이 방식을 택한 이유는 "왜 이 팀이 추천됐는가"를 항상 설명 가능하게
유지하기 위해서다 — 블랙박스 모델을 얹으면 이 설명력을 잃는다.

동작은 두 단계로 나뉜다: **A. 오프라인 배치**(사람이 주기적으로 실행)와 **B. 라이브 요청 처리**
(매 추천 요청마다 자동 실행)다.

## A. 오프라인 배치 — `scripts/run_cluster_weight_batch.py`

1. **클러스터 키 정의** (`app/scoring/cluster.py`)
   - `user_cluster_key(desired_roles, experience_level)` → `"{대표역할}:{경험수준}"`
   - `team_cluster_key(recruiting_roles, contest_field)` → `"{대표역할}:{공모전분야}"`
   - 비지도 학습으로 얻은 클러스터가 아니라, 고정 ENUM 조합을 그대로 키로 쓰는 순수 함수다.
     대표 코드(배열의 첫 번째 값)만 쓰는 이유는 다중 역할/다중 분야까지 키에 넣으면 조합 수가
     급증해 클러스터당 데이터가 더 희소해지기 때문이다.
   - 저장·조회하는 키에는 방향을 붙인다: `lift_key(direction, cluster_key)` →
     `"USER_TO_TEAM|BE:beginner"`. 사용자 키와 팀 키는 둘째 자리가 비면 똑같이 `"BE:unknown"`이 되어,
     방향을 안 붙이면 역제안 선택에서 나온 보정값이 제안 추천에 섞인다.

2. **선택 이벤트 수집**
   - Supabase `cluster_selection_events`의 **실제 선택 이벤트만** 읽는다. 배치가 이벤트의
     `direction`과 `chooser_cluster_key`를 합쳐 위 방향 키를 만든다.
   - 합성 이벤트(`tests/fixtures/eval_synthetic_selections.json`)는 `--synthetic-demo`로만 쓰고,
     계산 결과를 출력할 뿐 운영 표에 기록하지 않는다. 예전에는 실 이벤트가 없으면 합성 이벤트로
     자동 대체해 운영 표에 썼고, 그 값이 라이브 추천을 보정하고 있었다(2026-11-05 발견·정리).
   - 이벤트 형태: `{"chooser_cluster_key": str, "selected_candidate_id": Any,
     "shown_candidates": [{"candidate_id": Any, "component_scores": {...}}, ...]}`

3. **lift 계산** (`compute_weight_lifts`, `app/scoring/cluster_weights.py`)
   ```
   lift = 선택된 후보들의 컴포넌트 평균 점수 − 보여준 후보 전체의 컴포넌트 평균 점수
   ```
   - 컴포넌트마다(`similarity`/`role_match`/`deficit_fit`/`beginner_fit`/`activity_style_match`/
     `cf_affinity`) 따로 계산한다.
   - **양수 lift만 유지한다** — 음수로 가중치를 깎지는 않는다. 명시적 배제 신호(예:
     `beginner_fit == 0.0`)는 이미 `PENALTY_RULES`(`app/scoring/engine.py`)가 별도로 처리하고
     있어서, 역할이 겹치지 않게 하기 위한 의도적 설계다.
   - 이벤트가 `--min-events`(기본 20)보다 적은 클러스터는 건너뛴다. 몇 건짜리 lift는 잡음이다.
     함수 기본값 2는 평가 스크립트와 `--synthetic-demo`(합성 이벤트가 클러스터당 몇 건뿐)에서만 쓴다.

4. **Supabase에 버전 스냅샷으로 저장** (`app/scoring/cluster_weight_store.py`의
   `write_cluster_lifts`, 공통 규칙은 `app/supabase_client/snapshots.py`, 테이블: `cluster_weight_config`)
   - 배치 한 번 = 버전 하나다. 새 버전을 꺼진 채로 넣고 → 이전 활성 행을 전부 끄고 → 새 버전을
     켠다. 새 배치에 없는 클러스터의 옛 lift도 같이 꺼진다. 도중에 실패해도 두 버전이 섞여 켜지지 않는다.
   - 이전 버전은 지우지 않으므로 `--activate-version N`(`activate_version()`)으로 **코드 배포 없이
     바로 롤백**할 수 있다. 합성 데이터 버전은 켜지지 않는다.
   - 계산 결과가 비면 현재 활성 버전을 그대로 둔다. 보정을 완전히 끄려면 `--deactivate-all`.
   - 합성 데이터 출처(source에 `synthetic`)는 기록 자체를 거부한다.

## B. 라이브 요청마다 — `app/features/user_to_team/recommend.py` (역방향은 `team_to_user/recommend.py`가 대칭)

5. 요청이 오면 그 유저(또는 팀)의 클러스터 키를 계산하고 방향을 붙인다(1단계와 같은 함수 재사용).
6. `read_cluster_lifts()`가 활성 lift 전체를 읽어 그 키의 값을 꺼낸다.
   - 결과를 `CONFIG_CACHE_SECONDS`(기본 60초) 동안 프로세스 안에 캐시한다. 만료된 순간 요청이
     겹치면 하나만 Supabase를 읽고 나머지는 직전 값을 쓴다.
   - 읽을 때 합성 데이터 출처의 행은 무시한다.
   - 읽기 전용 클라이언트는 타임아웃이 짧고(연결 2초·응답 3초, `app/supabase_client/client.py`),
     요청 단위로도 4초를 넘기면 기다리지 않는다(`app/scoring/live_lookup.py`).
   - 조회가 실패하면 직전 값(없으면 빈 dict → 기본 `WEIGHTS`)을 쓰고, 30초 동안은 다시 시도하지
     않는다. 그래서 Supabase가 멈춰도 추천 응답이 몇 초 넘게 묶이지 않는다.
7. `adjust_weights(WEIGHTS, lift)` (`app/scoring/cluster_weights.py`)
   ```
   raw_i = base_i × (1 + gain × lift_i)   (gain 기본값 1.0)
   최종 가중치 = raw_i × (기존 WEIGHTS 총합 / raw 총합)   # 총합을 1.0으로 재정규화
   ```
   - 컴포넌트 점수 자체는 건드리지 않고 가중치 비중만 재분배한다 — 점수에 직접 가산하는
     방식은 여러 후보가 동시에 1.0 상한에 부딪혀 변별력이 떨어지는 문제가 실측 확인돼 폐기했다
     (2026-08-20).
8. 이 조정된 가중치로 `rank()`(`app/scoring/engine.py`)를 실행해 최종 추천 순위를 산출한다.

## 요약

"학습"이 일어나는 지점은 없다. 실질적으로는 **3단계(lift 계산)의 뺄셈 한 번**이 이 시스템의
핵심이고, 나머지는 그 값을 저장·조회·가중치에 반영하는 배관(plumbing)이다. 그래서 "이 가중치는
어디서 왔는가"라는 질문에 항상 정확하고 재현 가능하게 답할 수 있다 — 이게 정식 ML 대신 이 방식을
택한 이유이자 이 시스템의 핵심 가치다.

## 관련 문서

- [`cluster-weight-audit-trail-example.md`](cluster-weight-audit-trail-example.md) — 2026-08-20에
  실제 Supabase 데이터로 재현한 계산·저장·롤백 과정(당시 기록이다 — 지금 배치는 합성 데이터를 운영
  표에 쓰지 않아 그대로는 재현되지 않는다)
- [`hit-at-10-eval-report.md`](hit-at-10-eval-report.md) — 이 보정이 추천 품질에 미치는 영향을
  합성 선택 이벤트로 측정한 평가 리포트
- [`selection-feedback-draft.md`](selection-feedback-draft.md) — 이 메커니즘이 요구하는 BE 쪽
  API(`POST /selection-events`) 정리
