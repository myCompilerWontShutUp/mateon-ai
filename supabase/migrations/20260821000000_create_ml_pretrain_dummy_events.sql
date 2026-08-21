-- ML 사전 구축(회귀/로지스틱 회귀 등 정식 모델) 실험 전용 더미 선택 이벤트 테이블.
--
-- **의도적으로 cluster_selection_events와 분리했다.** run_cluster_weight_batch.py의
-- _load_real_events()가 cluster_selection_events 테이블을 source 구분 없이 전부 "실 데이터"로
-- 취급한다(현재 구현 확인 완료, 2026-08-21) — 즉 더미 데이터를 그 테이블에 넣으면, 나중에 진짜
-- BE 연동 데이터가 들어와도 더미 행을 걸러낼 방법이 없어 영구히 섞여버린다. "실 데이터가
-- 들어오면 더미는 자동으로 버려진다"는 기존 설계(source 접두사 기반 자동 전환, 2번 항목)를
-- 깨지 않기 위해 이 테이블을 완전히 분리했다.
--
-- cluster_selection_events와 스키마는 유사하지만 더미 데이터 전용이며, 정식 클러스터 가중치
-- 보정 파이프라인(run_cluster_weight_batch.py)은 이 테이블을 절대 읽지 않는다 — 오직
-- ML 사전 구축 실험용 스크립트(scripts/train_cluster_weight_ml_pretrain.py)만 읽는다.

create table if not exists ml_pretrain_dummy_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  source text not null,  -- 예: "gpt-5.6-terra_pool", "eval_definitions_deterministic"
  chooser_cluster_key text not null,
  shown_candidates jsonb not null,  -- [{"candidate_id": .., "component_scores": {...}}, ...]
  selected_candidate_id bigint not null
);

comment on table ml_pretrain_dummy_events is
  'ML(로지스틱 회귀 등) 사전 구축·실험 전용 더미 선택 이벤트. cluster_selection_events와 완전히
   분리되어 있어 실 데이터 파이프라인에 영향을 주지 않는다. 실 데이터가 쌓이면 이 테이블은
   더 이상 참조되지 않고 자연스럽게 버려진다.';

create index if not exists idx_ml_pretrain_dummy_events_cluster
  on ml_pretrain_dummy_events (chooser_cluster_key);

alter table ml_pretrain_dummy_events enable row level security;
-- service_role만 쓰고 읽는다(다른 모니터링 테이블과 동일 패턴) — RLS는 PostgREST 우발 노출 방지용.
