-- 20260820000000_create_monitoring_tables.sql는 이미 실제 Supabase 프로젝트에 적용됐으므로
-- 그 파일을 고치지 않고(적용된 마이그레이션은 히스토리를 다시 쓰지 않는다), 이 후속 마이그레이션으로
-- 정정한다.
--
-- 1) cluster_selection_events.proposal_id를 멱등키로 쓰려던 원래 설계는 애초에 동작할 수 없었다
--    — proposal_id는 백엔드가 /proposals/* 응답을 저장하면서 채번하므로, AI 서버가 이 요청을 받는
--    시점엔 아직 존재하지 않는다(닭이 먼저냐 달걀이 먼저냐). 백엔드가 요청 전용으로 새로 생성하는
--    idempotency_key(UUID)로 바꾸고, proposal_id는 참고용 느슨한 연결(nullable)로만 남긴다.
-- 2) judge_results의 PII 보존 정책(30일 후 자동 익명화)을 pg_cron으로 구현한다.

-- ============================================================================
-- 1. cluster_selection_events 멱등키 수정
-- ============================================================================
-- 이 테이블은 아직 앱 코드와 연결되지 않아 실제 행이 없다 — 그래서 컬럼을 NOT NULL로 바로
-- 추가해도 기존 행 위반 문제가 없다.

alter table cluster_selection_events
  drop constraint if exists cluster_selection_events_proposal_id_key;

alter table cluster_selection_events
  rename column proposal_id to related_proposal_id;

alter table cluster_selection_events
  alter column related_proposal_id drop not null;

alter table cluster_selection_events
  add column idempotency_key text not null;

alter table cluster_selection_events
  add constraint cluster_selection_events_idempotency_key_key unique (idempotency_key);

comment on column cluster_selection_events.idempotency_key is
  '백엔드가 이 요청 전용으로 새로 생성하는 UUID. proposal_id와 다르다 — 요청 시점엔 proposal_id가 아직 채번되기 전이라 멱등키로 쓸 수 없었다.';
comment on column cluster_selection_events.related_proposal_id is
  '나중에 백엔드가 채번한 proposal_id를 알게 되면 참고용으로만 채울 수 있는 느슨한 참조(선택, FK 강제 없음).';
comment on table cluster_selection_events is
  '제안 시점의 "실제 선택" 피드백. 클러스터별 가중치 오프라인 재계산의 입력 데이터. idempotency_key가 멱등키(백엔드가 요청마다 새로 생성).';

-- ============================================================================
-- 2. judge_results PII 자동 익명화 — 30일 보존 정책
-- ============================================================================
-- input_context/generated_output/violations/explanation은 passes=false일 때만 채워지는데,
-- 여기 사용자 입력 프롬프트(자기소개서 원문 등)가 그대로 담길 수 있다. 30일이 지나면 이 네
-- 필드만 NULL로 치환한다 — pipeline/judge_model/score/passes/created_at은 영구 보존해서
-- 장기 fail율 추이 모니터링은 계속 가능하게 둔다. cluster_selection_events는 ENUM 코드와
-- 점수만 담아 자유 텍스트가 없으므로 이 정책 대상이 아니다.
--
-- 30일은 조정 가능한 기본값이다 — 바꾸려면 cron.alter_job() 또는 아래 cron.schedule을
-- 새 간격으로 다시 실행하면 된다(동일 jobname이면 새로 만들지 않고 갱신한다, pg_cron 1.4+).

create extension if not exists pg_cron;

select cron.schedule(
  'redact-judge-results-pii',
  '0 18 * * *', -- 매일 UTC 18:00 (KST 03:00)
  $$
  update public.judge_results
  set input_context = null, generated_output = null, violations = null, explanation = null
  where created_at < now() - interval '30 days' and input_context is not null;
  $$
);
