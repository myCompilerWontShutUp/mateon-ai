-- 모니터링·데이터 기반 가중치 보정 (CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 참고)
--
-- 이 스키마는 AI 서버의 도메인 데이터(팀/유저/임베딩/제안)를 저장하지 않는다 — 무상태 원칙은
-- 그대로 유지된다. 여기 담기는 건 (1) 어떤 응답에도 다시 읽혀 들어가지 않는 쓰기 전용
-- 텔레메트리(judge_results, cluster_selection_events), (2) 배포와 무관한 주기로 조정되는
-- 튜닝 설정(cluster_weight_config) 뿐이다.
--
-- 세 테이블 모두 AI 서버(service_role 키)만 쓰고 읽는다. anon/authenticated 역할에는 어떤
-- 권한도 주지 않으며, RLS를 켜두는 이유는 PostgREST가 우발적으로 테이블을 공개 노출하는 걸
-- 막기 위함이다(service_role은 RLS를 우회하므로 서버 쓰기에는 영향 없음).

create extension if not exists pgcrypto; -- gen_random_uuid() 용

-- updated_at을 자동 갱신하는 공용 트리거 함수
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================================
-- 1. judge_results — LLM-as-judge 판정 로그
-- ============================================================================
-- passes=true는 최소 기록(레코드 존재만 확인 가능), passes=false는 입력 프롬프트·추론 결과·
-- 위반 항목·판정 근거까지 상세 기록한다. 응답 경로를 막지 않는 fire-and-forget 비동기 쓰기로
-- 채워진다 — 이 테이블에 대한 쓰기 실패가 AI 서버의 정상 응답을 막아서는 안 된다.

create table if not exists judge_results (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- 어떤 생성 파이프라인을 판정했는지. 예: 'user_to_team_proposal', 'team_to_user_proposal',
  -- 'recommendation_reason'. 새 파이프라인이 늘어날 수 있어 CHECK 제약은 걸지 않는다.
  pipeline text not null,

  -- 판정에 쓴 judge 모델(예: 'gpt-5.4') — judge 모델을 나중에 또 바꿀 수 있으므로 매 레코드에
  -- 남겨 어떤 모델 기준 판정인지 추적 가능하게 한다.
  judge_model text not null,

  -- 0~10 정수 점수(소수점 없음, 10=환각·편향 없음, 0=위험 수준). passes는 임계값 기반 파생값이나
  -- 조회 편의를 위해 같이 저장한다.
  score smallint not null check (score between 0 and 10),
  passes boolean not null,

  -- 관련 proposal이 있으면 연결(느슨한 참조 — AI 서버가 FK로 강제하지 않음, proposal_id는
  -- 백엔드가 채번하므로 시점상 아직 없을 수도 있다).
  related_proposal_id bigint,

  -- passes=false일 때만 채운다. passes=true는 아래 네 필드를 모두 null로 둬서 저장량을 줄인다.
  input_context text,
  generated_output text,
  violations jsonb,        -- 문자열 배열, 예: ["절대평가 금지 위반", "ID 노출"]
  explanation text,

  -- 스키마 변경 없이 부가 정보를 남기고 싶을 때를 위한 여유 칸(예: 요청 ID, 지연시간 등).
  metadata jsonb not null default '{}'::jsonb
);

comment on table judge_results is
  'LLM-as-judge 판정 로그. passes=true는 최소 기록, false는 상세 기록. 쓰기 전용 텔레메트리 — 응답 경로에 다시 읽히지 않는다.';

create index if not exists idx_judge_results_created_at on judge_results (created_at desc);
create index if not exists idx_judge_results_pipeline_passes on judge_results (pipeline, passes);
create index if not exists idx_judge_results_related_proposal_id on judge_results (related_proposal_id)
  where related_proposal_id is not null;

alter table judge_results enable row level security;

-- ============================================================================
-- 2. cluster_selection_events — 실제 선택 피드백 (클러스터별 선호 데이터)
-- ============================================================================
-- "선택"은 수락이 아니라 제안을 보낸 시점 신호로 충분하다고 결정했다(CLAUDE.md 참고). 백엔드가
-- 기존 /proposals/user-to-team, /proposals/team-to-user 호출에 선택 당시 보여줬던 후보 목록을
-- 실어 보내면, AI 서버가 클러스터 키를 직접 계산해 이 테이블에 기록한다.
--
-- 클러스터 키는 비지도 학습 결과가 아니라 고정 ENUM 조합을 그대로 쓴 문자열이다
-- (예: 'BE:intermediate', 'FE:beginner') — 클러스터 정의가 바뀔 수 있으므로 원본 구조화
-- 필드(chooser_raw_fields)도 함께 보존해 필요하면 재계산할 수 있게 한다.

create table if not exists cluster_selection_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  direction text not null check (direction in ('USER_TO_TEAM', 'TEAM_TO_USER')),

  -- proposal_id를 멱등키로 사용 — 백엔드의 웹훅 재시도가 중복 집계되지 않도록 UNIQUE 제약을 건다.
  proposal_id bigint not null unique,

  -- 고르는 쪽(USER_TO_TEAM이면 사용자, TEAM_TO_USER면 팀)의 클러스터 키와 원본 필드.
  chooser_cluster_key text not null,
  chooser_raw_fields jsonb not null,

  -- 그 순간 보여줬던 후보 전체 — [{"candidate_id": 17, "cluster_key": "...", "total_score": 0.9,
  -- "component_scores": {...}}, ...]. AI 서버가 상태를 못 가지므로 매번 통째로 재전송받는다.
  shown_candidates jsonb not null,

  -- 실제로 선택된(제안을 보낸) 후보.
  selected_candidate_id bigint not null,
  selected_cluster_key text not null

);

comment on table cluster_selection_events is
  '제안 시점의 "실제 선택" 피드백. 클러스터별 가중치 오프라인 재계산의 입력 데이터. proposal_id가 멱등키.';

create index if not exists idx_cluster_selection_events_chooser_cluster
  on cluster_selection_events (chooser_cluster_key, direction, created_at desc);
create index if not exists idx_cluster_selection_events_selected_cluster
  on cluster_selection_events (selected_cluster_key);

alter table cluster_selection_events enable row level security;

-- ============================================================================
-- 3. cluster_weight_config — 클러스터별 가중치/가산점 설정 (라이브 서버가 읽는 튜닝 설정)
-- ============================================================================
-- 가중치 재계산은 AI 서버 프로세스 안에서 돌지 않는다 — 별도 로컬 배치가 오프라인으로 계산해서
-- 이 테이블에 새 버전을 쓰고, 라이브 서버는 조회만 한다(cluster_key 기준). 갱신 주기는 앱 업데이트
-- 주기에 맞춰 1주~6개월.
--
-- 과거 버전을 삭제하지 않고 is_active로만 전환한다 — 재조정이 성능을 악화시켰을 때 이전 버전의
-- is_active를 다시 true로 돌리는 것만으로 롤백할 수 있게 하기 위함.

create table if not exists cluster_weight_config (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  cluster_key text not null,

  -- 조정 대상 컴포넌트. 기존 WEIGHTS의 5개(similarity/role_match/beginner_fit/deficit_fit/
  -- activity_style_match) 뿐 아니라, 이후 모니터링으로 늘어나는 선택 필드 가산점 이름도 여기
  -- 들어갈 수 있어 CHECK 제약을 걸지 않는다(예: 'activity_time_bonus').
  component text not null,

  -- 'override'는 해당 컴포넌트의 기본 가중치를 대체, 'bonus'는 기본 점수에 더해지는 가산점.
  weight_type text not null check (weight_type in ('override', 'bonus')),
  weight_value double precision not null,

  -- 이 값을 만든 오프라인 배치 실행을 추적하기 위한 표식(예: 'offline_batch_2026-09-01').
  source text not null,
  version integer not null,
  is_active boolean not null default true,
  notes text
);

comment on table cluster_weight_config is
  '클러스터별 가중치/가산점 설정. 라이브 서버는 읽기만 하고, 재계산은 별도 오프라인 배치가 담당. is_active 전환으로 롤백 가능.';

-- 클러스터+컴포넌트당 활성 버전은 하나만 허용.
create unique index if not exists uq_cluster_weight_config_active
  on cluster_weight_config (cluster_key, component)
  where is_active;

create index if not exists idx_cluster_weight_config_lookup
  on cluster_weight_config (cluster_key, component, is_active);

alter table cluster_weight_config enable row level security;

create trigger trg_cluster_weight_config_updated_at
  before update on cluster_weight_config
  for each row
  execute function set_updated_at();
