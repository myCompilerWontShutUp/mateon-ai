-- item-to-item 협업 필터링(CF)용 공모전 동시발생 행렬
--
-- 기존 테이블들과 같은 성격이다 — 도메인 데이터가 아니라 **배포와 무관한 주기로 갱신되는
-- 튜닝 설정값**이며(cluster_weight_config와 동일 범주), 계산은 오프라인 배치가 하고 라이브
-- 서버는 읽기만 한다. 무상태 원칙은 그대로 유지된다.
--
-- 여기 담기는 건 공모전 ID 쌍과 유사도 숫자뿐이라 개인정보가 없다 — judge_results의 30일
-- 자동 익명화 정책 대상이 아니다(원본 상호작용 이력은 백엔드가 소유하며, 배치는 그걸 읽어
-- 집계만 하고 이 테이블에는 개인 식별자를 남기지 않는다).

create table if not exists event_cooccurrence (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- 공모전 쌍. 대칭 관계라 (a,b)와 (b,a) 양쪽 다 저장한다 — 조회 시 한 방향만 보면 되도록
  -- 해서 라이브 읽기 경로를 단순하게 유지하기 위함이다.
  event_id bigint not null,
  related_event_id bigint not null,

  -- |users(a) ∩ users(b)| / sqrt(|users(a)| · |users(b)|), 항상 [0, 1].
  -- 인기 편향을 제거한 코사인 정규화 값이라 다른 컴포넌트 점수와 같은 스케일로 결합된다.
  similarity double precision not null check (similarity >= 0 and similarity <= 1),

  -- 어떤 배치 실행에서 나온 값인지 추적용 (예: 'offline_batch_real_20260901',
  -- 'offline_batch_synthetic_demo_20260901'). 실 데이터와 합성 데모를 구분할 수 있어야 한다.
  source text not null,

  -- cluster_weight_config와 같은 롤백 전략: 이전 버전을 지우지 않고 비활성화만 한다.
  version integer not null default 1,
  is_active boolean not null default true,

  constraint event_cooccurrence_not_self check (event_id <> related_event_id)
);

-- 라이브 읽기 경로가 항상 is_active로 필터링하므로 부분 인덱스로 충분하다.
create index if not exists event_cooccurrence_active_idx
  on event_cooccurrence (event_id)
  where is_active;

-- 같은 버전 안에서 같은 쌍이 중복 기록되는 걸 막는다.
create unique index if not exists event_cooccurrence_pair_version_idx
  on event_cooccurrence (event_id, related_event_id, version);

-- PostgREST 우발 노출 방지 — service_role은 RLS를 우회하므로 서버 접근에는 영향 없다.
alter table event_cooccurrence enable row level security;
