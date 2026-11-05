"""추천 요청이 Supabase 설정값을 읽는 방식 — 방향별 보정값 키, 필요할 때만 하는 CF 조회, 조회 대기
상한(2026-11-05)."""

import time

import pytest

from app.features.team_to_user import recommend as team_to_user_recommend
from app.features.user_to_team import recommend as user_to_team_recommend
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest
from app.scoring import live_lookup

_DIM = 1536
_VECTOR = [1.0] + [0.0] * (_DIM - 1)

# 같은 "BE:unknown" 꼴이라도 방향이 다르면 다른 보정값이어야 한다.
_LIFTS = {
    "USER_TO_TEAM|BE:beginner": {"role_match": 0.3},
    "TEAM_TO_USER|BE:unknown": {"similarity": 0.9},
    "BE:beginner": {"deficit_fit": 0.7},  # 방향 없는 옛 키 — 더 이상 읽히면 안 된다
}


def _capture_lifts(monkeypatch: pytest.MonkeyPatch, module) -> list[dict]:
    captured: list[dict] = []

    def fake_adjust(weights: dict, lifts: dict) -> dict:
        captured.append(lifts)
        return weights

    monkeypatch.setattr(module, "read_cluster_lifts", lambda: _LIFTS)
    monkeypatch.setattr(module, "adjust_weights", fake_adjust)
    return captured


def _forbid_cooccurrence(monkeypatch: pytest.MonkeyPatch, module) -> None:
    def must_not_read(*_args):
        raise AssertionError("CF에 쓸 공모전 정보가 없는데 Supabase를 조회했다")

    monkeypatch.setattr(module, "read_cooccurrence", must_not_read)


async def test_user_to_team_reads_its_own_direction_lifts_and_skips_cf_without_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_lifts(monkeypatch, user_to_team_recommend)
    _forbid_cooccurrence(monkeypatch, user_to_team_recommend)

    request = RecommendationRequest(
        query_embedding_vector=_VECTOR,
        query_metadata={"desired_roles": ["BE"], "experience_level": "beginner"},
        # 후보 팀에 event_id가 있어도 사용자의 상호작용 이력이 없으면 CF를 계산할 수 없다.
        candidates=[CandidateEmbedding(candidate_id=1, embedding_vector=_VECTOR, metadata={"event_id": 300})],
    )

    await user_to_team_recommend.recommend_teams(request)

    assert captured == [{"role_match": 0.3}]


async def test_team_to_user_reads_its_own_direction_lifts_and_skips_cf_without_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_lifts(monkeypatch, team_to_user_recommend)
    _forbid_cooccurrence(monkeypatch, team_to_user_recommend)

    request = RecommendationRequest(
        query_embedding_vector=_VECTOR,
        # 팀 공모전(event_id)이 없으면 CF를 계산할 수 없다.
        query_metadata={"recruiting_roles": ["BE"]},
        candidates=[
            CandidateEmbedding(
                candidate_id=7, embedding_vector=_VECTOR, metadata={"interacted_event_ids": [100]}
            )
        ],
    )

    await team_to_user_recommend.recommend_users(request)

    assert captured == [{"similarity": 0.9}]


async def test_team_to_user_cf_uses_team_event_and_accepts_string_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[list] = []

    def fake_read(target_event_ids) -> dict:
        requested.append(list(target_event_ids))
        return {300: {100: 0.6}}

    monkeypatch.setattr(team_to_user_recommend, "read_cooccurrence", fake_read)

    request = RecommendationRequest(
        query_embedding_vector=_VECTOR,
        query_metadata={"recruiting_roles": ["BE"], "event_id": "300"},
        candidates=[
            CandidateEmbedding(
                candidate_id=7, embedding_vector=_VECTOR, metadata={"interacted_event_ids": ["100"]}
            ),
            CandidateEmbedding(candidate_id=8, embedding_vector=_VECTOR, metadata={}),
        ],
    )

    response = await team_to_user_recommend.recommend_users(request)

    assert requested == [[300]]
    scores = {item.candidate_id: item.component_scores["cf_affinity"] for item in response.recommendations}
    assert scores == {7: 0.6, 8: 0.0}


async def test_user_to_team_cf_reads_only_pairs_with_the_users_events(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[tuple] = []

    def fake_read(target_event_ids, related_event_ids=None) -> dict:
        requested.append((sorted(target_event_ids), sorted(related_event_ids)))
        return {300: {100: 0.6}}

    monkeypatch.setattr(user_to_team_recommend, "read_cooccurrence", fake_read)

    request = RecommendationRequest(
        query_embedding_vector=_VECTOR,
        query_metadata={"desired_roles": ["BE"], "interacted_event_ids": ["100"]},
        candidates=[
            CandidateEmbedding(candidate_id=1, embedding_vector=_VECTOR, metadata={"event_id": "300"}),
            CandidateEmbedding(candidate_id=2, embedding_vector=_VECTOR, metadata={}),
        ],
    )

    response = await user_to_team_recommend.recommend_teams(request)

    assert requested == [([300], [100])]
    scores = {item.candidate_id: item.component_scores["cf_affinity"] for item in response.recommendations}
    assert scores == {1: 0.6, 2: 0.0}


@pytest.mark.parametrize("direction", ["user_to_team", "team_to_user"])
async def test_a_hanging_lookup_does_not_hold_the_response(
    monkeypatch: pytest.MonkeyPatch, direction: str
) -> None:
    """Supabase가 응답 없이 멈춰도 추천은 기본 가중치로 바로 나간다."""
    module = user_to_team_recommend if direction == "user_to_team" else team_to_user_recommend
    monkeypatch.setattr(live_lookup, "LOOKUP_TIMEOUT_SECONDS", 0.05)

    def hanging_read(*_args) -> dict:
        time.sleep(0.5)
        return {"never": {"role_match": 1.0}}

    monkeypatch.setattr(module, "read_cluster_lifts", hanging_read)
    metadata_key = "desired_roles" if direction == "user_to_team" else "recruiting_roles"
    request = RecommendationRequest(
        query_embedding_vector=_VECTOR,
        query_metadata={metadata_key: ["BE"]},
        candidates=[CandidateEmbedding(candidate_id=1, embedding_vector=_VECTOR, metadata={})],
    )
    recommend = (
        user_to_team_recommend.recommend_teams
        if direction == "user_to_team"
        else team_to_user_recommend.recommend_users
    )

    started = time.perf_counter()
    response = await recommend(request)

    assert time.perf_counter() - started < 0.4
    assert [item.candidate_id for item in response.recommendations] == [1]
