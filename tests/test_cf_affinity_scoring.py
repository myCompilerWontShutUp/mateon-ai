"""cf_affinity 도입이 기존 순위를 건드리지 않는다는 것과, 데이터가 있으면 실제로 동작한다는 것.

첫 번째 테스트가 이 설계의 핵심 안전 근거다 — `WEIGHTS`에 CF를 넣으면서 기존 5개를 균일하게
0.95배로 축소했기 때문에, CF 신호가 없으면 총점이 `0.95 × 기존 점수`라는 **단조 변환**이
되어 순위가 수학적으로 불변이다. "안전할 것이다"가 아니라 증명 가능하게 안전하다는 걸 코드로
고정해둔다.
"""

import pytest

from app.features.user_to_team import recommend as recommend_module
from app.features.user_to_team.recommend import recommend_teams
from app.features.user_to_team.scoring import PENALTY_RULES, WEIGHTS
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest
from app.scoring.engine import CandidateInput, rank

# cf_affinity 도입 이전의 가중치 — 이 테스트가 비교 기준으로 삼는 값이다.
LEGACY_WEIGHTS = {
    "similarity": 0.4,
    "role_match": 0.2,
    "deficit_fit": 0.15,
    "beginner_fit": 0.2,
    "activity_style_match": 0.05,
}

_DIM = 1536


def test_new_weights_are_the_legacy_ones_scaled_uniformly() -> None:
    """상대 비율이 보존됐는지 — 실측으로 튜닝한 beginner_fit 우위 구조가 유지되어야 한다."""
    for name, legacy in LEGACY_WEIGHTS.items():
        assert WEIGHTS[name] == pytest.approx(legacy * 0.95)

    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_ranking_is_unchanged_when_cf_has_no_data() -> None:
    """CF 신호가 0이면 순위가 기존 가중치 결과와 완전히 동일하다(단조 변환)."""
    candidates = [
        CandidateInput(
            candidate_id=1,
            raw_similarity=0.9,
            metadata_scores={
                "role_match": 1.0,
                "deficit_fit": 0.5,
                "activity_style_match": 1.0,
                "beginner_fit": 1.0,
            },
        ),
        CandidateInput(
            candidate_id=2,
            raw_similarity=0.7,
            metadata_scores={
                "role_match": 0.5,
                "deficit_fit": 1.0,
                "activity_style_match": 0.5,
                "beginner_fit": 1.0,
            },
        ),
        CandidateInput(
            candidate_id=3,
            raw_similarity=0.8,
            metadata_scores={
                "role_match": 1.0,
                "deficit_fit": 1.0,
                "activity_style_match": 0.0,
                "beginner_fit": 0.0,
            },
        ),
    ]
    legacy_order = [c.candidate_id for c in rank(candidates, LEGACY_WEIGHTS, PENALTY_RULES)]

    with_cf = [
        CandidateInput(
            candidate_id=c.candidate_id,
            raw_similarity=c.raw_similarity,
            metadata_scores={**c.metadata_scores, "cf_affinity": 0.0},
        )
        for c in candidates
    ]
    new_order = [c.candidate_id for c in rank(with_cf, WEIGHTS, PENALTY_RULES)]

    assert new_order == legacy_order


async def test_collaborative_signal_lifts_a_team_content_scoring_would_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF의 존재 이유 — 임베딩상 멀고 룰 점수도 동일해서 콘텐츠 기반으로는 구분할 수 없는
    후보를, "같은 사람들이 함께 봤다"는 신호만으로 끌어올린다."""

    requested_targets: list[set] = []

    def _cooccurrence(target_event_ids, related_event_ids=None) -> dict:
        # 후보 팀들의 공모전과 사용자가 본 공모전 사이의 쌍만 읽는다(표 전체를 읽지 않는다).
        requested_targets.append(set(target_event_ids))
        # 사용자가 본 공모전 100과, 후보 2번이 속한 공모전 300이 강하게 함께 소비된다.
        return {300: {100: 0.8}}

    monkeypatch.setattr(recommend_module, "read_cooccurrence", _cooccurrence)

    shared_metadata = {
        "recruiting_roles": ["BE"],
        "required_skills": ["Spring Boot"],
        "activity_style": "온라인",
        "beginner_friendly": True,
    }
    query_vector = [1.0] + [0.0] * (_DIM - 1)
    far_vector = [0.0, 1.0] + [0.0] * (_DIM - 2)

    request = RecommendationRequest(
        query_embedding_vector=query_vector,
        query_metadata={
            "desired_roles": ["BE"],
            "skills": ["Spring Boot"],
            "activity_style": "온라인",
            "experience_level": "beginner",
            "interacted_event_ids": [100],
        },
        candidates=[
            # 1번: 임베딩상 가깝지만 협업 신호는 없다.
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=query_vector,
                metadata={**shared_metadata, "event_id": 200},
            ),
            # 2번: 임베딩상 멀지만, 사용자가 본 공모전과 함께 소비되는 공모전의 팀이다.
            CandidateEmbedding(
                candidate_id=2,
                embedding_vector=far_vector,
                metadata={**shared_metadata, "event_id": 300},
            ),
        ],
    )

    response = await recommend_teams(request)

    assert requested_targets == [{200, 300}]
    scores = {item.candidate_id: item.component_scores for item in response.recommendations}
    assert scores[2]["cf_affinity"] == 0.8
    assert scores[1]["cf_affinity"] == 0.0
    # 콘텐츠 신호만 보면 2번이 유사도 0점으로 밀리지만, CF가 그 격차를 좁힌다.
    assert scores[2]["similarity"] == 0.0
