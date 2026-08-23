"""쿼리 공모전 1건 중심의 유사도 방사형 배치 — 순수 계산, OpenAI 호출 없음(임베딩 벡터는
BE가 요청에 실어 보낸다, 무상태 원칙). `scripts/generate_contest_similarity_visualization.py`
(테스트/시연용 프로토타입)에서 검증을 마친 알고리즘을 그대로 옮겼다 — 반지름·색을 절대
유사도(0~1)로 매핑하면 실제 유사도가 좁은 대역에 몰려 있을 때 대부분의 점이 바깥쪽에만 몰려
보이는 문제, 반지름 범위를 모든 점이 공유하면 유사도 낮은 점도 우연히 중앙 근처로 뽑히는 문제를
전부 실측으로 겪고 고친 결과다(2026-08-23).
"""

import math
import random

from app.schemas.contest import CONTEST_FIELD_LABELS, ContestField
from app.schemas.contest_similarity import (
    ContestSimilarityPoint,
    ContestSimilarityQueryEcho,
    ContestSimilarityReferenceRing,
    ContestSimilarityRequest,
    ContestSimilarityResponse,
)
from app.scoring.similarity import cosine_similarity

LAYOUT_RANDOM_SEED = 20260823
MAX_RADIUS = 12.0
MIN_RADIUS = 2.6  # 순위 1등(가장 유사)이어도 중앙과 이만큼은 항상 떨어짐
RADIAL_JITTER = 0.5  # 각 점의 반지름을 자기 순위가 정한 값 근처에서만 살짝 흔드는 폭
REFERENCE_PERCENTILES = (0.1, 0.3, 0.6, 0.9)


def _field_label(field_code: str | None) -> str | None:
    if field_code is None:
        return None
    try:
        return CONTEST_FIELD_LABELS[ContestField(field_code)]
    except ValueError:
        return field_code


async def compute_contest_similarity(request: ContestSimilarityRequest) -> ContestSimilarityResponse:
    scored = [
        (candidate, cosine_similarity(request.query.embedding_vector, candidate.embedding_vector))
        for candidate in request.candidates
    ]
    scored.sort(key=lambda pair: -pair[1])
    top = scored[: request.top_n]
    n = len(top)

    # 반지름은 절대 유사도가 아니라 **표시된 후보군 안에서의 순위 백분위**로 정한다 — 실제
    # 유사도가 좁은 대역에 몰려 있으면(실측: 0.25~0.62) 절대 척도 매핑은 대부분의 점을 바깥쪽
    # 절반에만 몰아넣는다. 1등은 항상 MIN_RADIUS, 꼴찌는 항상 MAX_RADIUS.
    rng = random.Random(LAYOUT_RANDOM_SEED)
    points: list[ContestSimilarityPoint] = []
    for rank, (candidate, sim) in enumerate(top):
        t = rank / (n - 1) if n > 1 else 0.0
        ideal_radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * t
        # 반지름을 자기 순위가 정한 값(ideal_radius) 근처에서만 좁게 흔든다 — 모든 점이 반지름
        # 범위를 공유하는(예: 공통 안쪽 경계를 가진 고리) 방식은 유사도 낮은 점도 우연히 중앙
        # 근처로 뽑힐 수 있어서 폐기했다(실측으로 발견·수정, CLAUDE.md 참고).
        r = max(0.3, ideal_radius + rng.uniform(-RADIAL_JITTER, RADIAL_JITTER))
        theta = rng.uniform(0, 2 * math.pi)
        points.append(
            ContestSimilarityPoint(
                id=candidate.id,
                title=candidate.title,
                organizer=candidate.organizer,
                category=candidate.category,
                field=candidate.field,
                field_label=_field_label(candidate.field),
                detail_url=candidate.detail_url,
                similarity=sim,
                rank_percentile=t,
                radius=ideal_radius,
                x=r * math.cos(theta),
                y=r * math.sin(theta),
            )
        )

    reference_rings: list[ContestSimilarityReferenceRing] = []
    if n > 0:
        for p in REFERENCE_PERCENTILES:
            idx = min(n - 1, int(round(p * (n - 1))))
            reference_rings.append(
                ContestSimilarityReferenceRing(
                    percentile=p,
                    similarity_at_percentile=top[idx][1],
                    radius=MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * p,
                )
            )

    return ContestSimilarityResponse(
        query=ContestSimilarityQueryEcho(
            id=request.query.id,
            title=request.query.title,
            organizer=request.query.organizer,
            category=request.query.category,
            field=request.query.field,
            field_label=_field_label(request.query.field),
            detail_url=request.query.detail_url,
        ),
        points=points,
        max_radius=MAX_RADIUS,
        min_radius=MIN_RADIUS,
        radial_jitter=RADIAL_JITTER,
        reference_rings=reference_rings,
        candidate_pool_total=len(request.candidates),
    )
