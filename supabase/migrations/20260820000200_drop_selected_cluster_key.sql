-- 20260820000000_create_monitoring_tables.sql는 selected_cluster_key(선택된 후보 자신의
-- 클러스터 키)도 저장하도록 만들어졌는데, 실제로 요청/응답 계약을 확정하는 과정에서 이걸
-- 채울 방법이 없다는 걸 발견했다 — shown_candidates에는 candidate_id/total_score/
-- component_scores만 담기로 확정했고(팀의 recruiting_roles 같은 원본 필드까지 후보마다
-- 매번 실어 보내게 하면 백엔드 계약이 불필요하게 커진다), 그 후보 자신의 클러스터 키를 계산할
-- 원본 필드가 없다.
--
-- "클러스터 X가 무엇을 골랐는가"라는 질문은 selected_candidate_id로 shown_candidates
-- jsonb에서 해당 항목을 찾아 component_scores를 보면 충분히 답할 수 있다(오프라인 배치가
-- 드물게 도는 구조라 조회 시점에 계산해도 성능 문제 없음) — 그래서 이 컬럼은 제거한다.
-- 아직 앱 코드와 연결되지 않아 실제 행이 없으므로 안전하게 지울 수 있다.

alter table cluster_selection_events
  drop column if exists selected_cluster_key;
