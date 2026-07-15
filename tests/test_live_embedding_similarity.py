"""실제 임베딩 API로 차원과 의미적 유사도가 말이 되는지 확인한다."""

import pytest

from app.core.config import get_settings
from app.openai_client.embedding import embed_text
from app.scoring.similarity import cosine_similarity


@pytest.mark.live
async def test_embedding_has_configured_dimension() -> None:
    vector = await embed_text("백엔드 개발자, Spring Boot와 Kafka 능숙")
    assert len(vector) == get_settings().embedding_dimension


@pytest.mark.live
async def test_similar_texts_are_more_similar_than_unrelated_texts() -> None:
    backend_user = await embed_text(
        "저는 백엔드 개발자입니다. Spring Boot와 PostgreSQL을 다룹니다."
    )
    backend_team = await embed_text(
        "백엔드 개발자를 모집합니다. Spring Boot와 PostgreSQL 경험자를 찾습니다."
    )
    design_team = await embed_text(
        "그래픽 디자이너를 모집합니다. Figma와 일러스트레이터 능숙자를 찾습니다."
    )

    sim_to_backend_team = cosine_similarity(backend_user, backend_team)
    sim_to_design_team = cosine_similarity(backend_user, design_team)

    assert sim_to_backend_team > sim_to_design_team, (
        f"백엔드 유저가 백엔드 팀({sim_to_backend_team:.3f})보다 "
        f"디자인 팀({sim_to_design_team:.3f})과 더 유사하게 나왔다"
    )
