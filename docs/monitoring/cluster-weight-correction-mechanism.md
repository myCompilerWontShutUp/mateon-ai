# 클러스터별 가중치 보정 — 구현 메커니즘

이 문서는 "클러스터별 가중치 보정"이 실제로 어떤 순서로 동작하는지, 코드 위치와 함께 정리한다.

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

2. **선택 이벤트 수집**
   - `cluster_selection_events` 테이블(Supabase)에서 읽는다. BE 연동 전까지는 실 데이터 대신
     합성 이벤트를 쓴다.
   - 이벤트 형태: `{"chooser_cluster_key": str, "selected_candidate_id": Any,
     "shown_candidates": [{"candidate_id": Any, "component_scores": {...}}, ...]}`

3. **lift 계산** (`compute_weight_lifts`, `app/scoring/cluster_weights.py`)
   ```
   lift = 선택된 후보들의 컴포넌트 평균 점수 − 보여준 후보 전체의 컴포넌트 평균 점수
   ```
   - 컴포넌트마다(`similarity`/`role_match`/`deficit_fit`/`beginner_fit`/`activity_style_match`)
     따로 계산한다.
   - **양수 lift만 유지한다** — 음수로 가중치를 깎지는 않는다. 명시적 배제 신호(예:
     `beginner_fit == 0.0`)는 이미 `PENALTY_RULES`(`app/scoring/engine.py`)가 별도로 처리하고
     있어서, 역할이 겹치지 않게 하기 위한 의도적 설계다.
   - 이벤트가 `min_events`(기본값 2) 미만인 클러스터는 통계적으로 불안정하다고 보고 건너뛴다.

4. **Supabase에 버전과 함께 저장** (`app/scoring/cluster_weight_store.py`의
   `write_cluster_lifts`, 테이블: `cluster_weight_config`)
   - 기존 활성 행은 지우지 않고 `is_active=false`로만 바꾼다.
   - 새로 계산한 값은 새 `version`으로 추가한다.
   - 이 덕분에 `is_active` 플래그 전환만으로 **코드 배포 없이 즉시 롤백**할 수 있다(실측 재현
     사례: [`cluster-weight-audit-trail-example.md`](cluster-weight-audit-trail-example.md)).

## B. 라이브 요청마다 — `app/features/user_to_team/recommend.py` (역방향은 `team_to_user/recommend.py`가 대칭)

5. 요청이 오면 그 유저(또는 팀)의 클러스터 키를 계산한다(4단계와 같은 함수 재사용).
6. `read_cluster_lifts()`가 Supabase에서 그 클러스터의 활성 lift를 조회한다.
   - `asyncio.to_thread`로 실행해 동기 Supabase 클라이언트가 이벤트 루프를 막지 않게 한다.
   - 조회가 실패하면 예외를 삼키고 빈 dict를 반환한다 — 기본 `WEIGHTS`로 안전하게 후퇴하므로,
     Supabase 장애가 추천 응답 자체를 막지 않는다.
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

- [`cluster-weight-audit-trail-example.md`](cluster-weight-audit-trail-example.md) — 실제
  Supabase 데이터로 재현한 계산·저장·롤백 전 과정
- [`hit-at-10-eval-report.md`](hit-at-10-eval-report.md) — 이 보정이 실제 추천 품질에 미치는
  영향을 측정한 평가 리포트
- [`selection-feedback-draft.md`](selection-feedback-draft.md) — 이 메커니즘이 요구하는 BE 쪽
  API 변경사항(`selection_context`) 정리
