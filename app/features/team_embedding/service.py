from app.features.team_embedding.extraction import extract_team_soft_fields
from app.features.team_embedding.template import compute_missing_fields, render_team_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.embedding import EmbeddingResult
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest


async def compute_team_embedding(request: TeamEmbeddingRefreshRequest) -> EmbeddingResult:
    soft_fields = await extract_team_soft_fields(
        request.intro_text, request.recruiting_roles, request.contest_field
    )
    missing_fields = compute_missing_fields(soft_fields)
    embedding_text = render_team_embedding_text(request, soft_fields)
    embedding_vector = await embed_text(embedding_text)

    metadata = {
        # 정규화된 값(RoleCode/ContestField)을 돌려준다 — 유저 인텐트 쪽 desired_roles와 같은
        # 어휘를 쓰게 되어 역할 일치도 스코어링(app/scoring/rules.py의 overlap_ratio)이
        # 문자열 표기 차이로 항상 0이 되는 문제를 막는다. required_skills는 열린 집합이라
        # 정규화 대상이 아니라 원문 그대로 echo한다.
        "recruiting_roles": soft_fields.recruiting_roles,
        "required_skills": request.required_skills,
        "activity_goal": soft_fields.activity_goal,
        "activity_style": soft_fields.activity_style,
        "beginner_friendly": soft_fields.beginner_friendly,
        # 선택 필드(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 4번) — 기본 스코어링에는
        # 영향 없고, /recommendations/*의 component_scores에 activity_time_match로만 노출된다.
        "activity_time": soft_fields.optional.activity_time,
        # 2026-08-20 추가 — 룰 스코어링에는 안 쓰인다(원래부터 유저 쪽에 대응 필드가 없어서
        # metadata에서 뺐던 이유는 그대로 유효). 다만 팀 클러스터 키(1번 항목,
        # `recruiting_roles × contest_field`)를 라이브 요청 경로에서 계산하려면 필요해서
        # 여기서는 노출한다 — BE가 /recommendations/team-to-user 호출 시 query_metadata에
        # 이 값을 안 실어 보내도 기존 흐름은 그대로 동작한다(클러스터 키가
        # "역할:unknown"으로 단순해질 뿐, 에러 없음).
        "contest_field": soft_fields.contest_field.value if soft_fields.contest_field else None,
    }

    return EmbeddingResult(
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
        metadata=metadata,
        missing_fields=missing_fields,
    )
