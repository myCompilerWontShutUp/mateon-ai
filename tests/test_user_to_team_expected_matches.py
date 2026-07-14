import json
from pathlib import Path

from app.features.user_to_team.recommend import recommend_teams
from app.schemas.embedding import EmbeddingResult
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest
from app.schemas.user_intent import UserIntentExtractionResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_teams() -> dict[str, EmbeddingResult]:
    raw = json.loads((FIXTURES_DIR / "teams.json").read_text(encoding="utf-8"))
    return {team_id: EmbeddingResult(**payload) for team_id, payload in raw.items()}


def _load_users() -> dict[str, UserIntentExtractionResult]:
    raw = json.loads((FIXTURES_DIR / "users.json").read_text(encoding="utf-8"))
    return {key: UserIntentExtractionResult(**payload) for key, payload in raw.items()}


def _build_request(user: UserIntentExtractionResult, teams: dict[str, EmbeddingResult]) -> RecommendationRequest:
    return RecommendationRequest(
        query_embedding_vector=user.embedding_vector,
        query_metadata={
            "desired_roles": user.extracted.desired_roles,
            "skills": user.extracted.skills,
            "activity_style": user.extracted.activity_style,
            "experience_level": user.extracted.experience_level,
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=int(team_id),
                embedding_vector=team.embedding_vector,
                metadata=team.metadata,
            )
            for team_id, team in teams.items()
        ],
    )


def test_backend_expert_matches_fintech_team() -> None:
    teams = _load_teams()
    users = _load_users()

    response = recommend_teams(_build_request(users["backend_expert"], teams))

    # 핀테크 BE 팀 (Spring Boot/Kafka/Redis, 실무 경험 우대, 고강도)이 뚜렷한 1위여야 한다
    # (실제 임베딩 기준 1위 0.83 vs 2위 0.50 — 큰 격차로 확인됨).
    assert response.recommendations[0].candidate_id == 7


def test_frontend_beginner_matches_beginner_friendly_team() -> None:
    teams = _load_teams()
    users = _load_users()

    response = recommend_teams(_build_request(users["frontend_beginner"], teams))

    # 완전 초보자 FE 팀 (HTML/CSS/JS, 가벼운 강도)이 뚜렷한 1위여야 한다
    # (실제 임베딩 기준 1위 0.95 vs 2위 0.56 — 큰 격차로 확인됨).
    assert response.recommendations[0].candidate_id == 8
