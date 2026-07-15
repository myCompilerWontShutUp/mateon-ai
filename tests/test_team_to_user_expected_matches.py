import json
from pathlib import Path

from app.features.team_to_user.recommend import recommend_users
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


def _build_request(team: EmbeddingResult, users: dict[str, UserIntentExtractionResult]) -> RecommendationRequest:
    return RecommendationRequest(
        query_embedding_vector=team.embedding_vector,
        query_metadata={
            "recruiting_roles": team.metadata.get("recruiting_roles", []),
            "required_skills": team.metadata.get("required_skills", []),
            "activity_goal": team.metadata.get("activity_goal"),
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=idx,
                embedding_vector=user.embedding_vector,
                metadata={
                    "desired_roles": user.extracted.desired_roles,
                    "skills": user.extracted.skills,
                    "experience_level": user.extracted.experience_level,
                    "activity_goal": user.extracted.activity_goal,
                },
            )
            for idx, user in enumerate(users.values())
        ],
    )


def test_fintech_team_prefers_backend_expert_over_frontend_beginner() -> None:
    teams = _load_teams()
    users = _load_users()  # 순서: backend_expert=0, frontend_beginner=1

    response = recommend_users(_build_request(teams["7"], users))

    assert response.recommendations[0].candidate_id == 0


def test_beginner_club_team_prefers_frontend_beginner_over_backend_expert() -> None:
    teams = _load_teams()
    users = _load_users()

    response = recommend_users(_build_request(teams["8"], users))

    assert response.recommendations[0].candidate_id == 1
