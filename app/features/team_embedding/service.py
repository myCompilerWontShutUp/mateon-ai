from app.features.team_embedding.extraction import extract_team_soft_fields
from app.features.team_embedding.template import compute_missing_fields, render_team_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.embedding import EmbeddingResult
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest


async def compute_team_embedding(request: TeamEmbeddingRefreshRequest) -> EmbeddingResult:
    soft_fields = await extract_team_soft_fields(request.intro_text)
    missing_fields = compute_missing_fields(soft_fields)
    embedding_text = render_team_embedding_text(request, soft_fields)
    embedding_vector = await embed_text(embedding_text)

    metadata = {
        "recruiting_roles": request.recruiting_roles,
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
