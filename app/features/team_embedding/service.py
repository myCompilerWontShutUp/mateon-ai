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
    }

    return EmbeddingResult(
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
        metadata=metadata,
        missing_fields=missing_fields,
    )
