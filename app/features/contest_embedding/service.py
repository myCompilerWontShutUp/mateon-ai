from app.features.contest_embedding.template import render_contest_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.contest_embedding import ContestEmbeddingRefreshRequest, ContestEmbeddingResult


async def compute_contest_embedding(request: ContestEmbeddingRefreshRequest) -> ContestEmbeddingResult:
    embedding_text = render_contest_embedding_text(request.title, request.description)
    embedding_vector = await embed_text(embedding_text)
    return ContestEmbeddingResult(event_id=request.event_id, embedding_vector=embedding_vector)
