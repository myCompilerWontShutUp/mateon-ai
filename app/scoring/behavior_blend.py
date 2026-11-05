"""행동 이력 기반 쿼리 벡터 강화 — **협업 필터링이 아니다.**

사용자가 북마크/지원한 공모전들의 임베딩 평균(`behavior_embedding_vector`)을 이번 요청의
intent 임베딩과 섞어, "이 사용자가 실제로 관심을 보여온 방향"을 유사도 계산에 반영한다.
문헌 분류상 이건 **개인화된 콘텐츠 기반 필터링**(average pooling 기반 사용자 프로파일링)이며,
협업 신호는 전혀 들어 있지 않다 — 벡터의 출처가 `text-embedding-3-small`(제목/설명)이라
다른 사용자의 행동이 한 번도 개입하지 않기 때문이다. 협업 신호는 `app/scoring/cooccurrence.py`
쪽(item-to-item CF)이 담당한다.

**블렌딩 비율(α) 정책은 AI 서버가 소유한다** — BE는 벡터와 이력 건수만 보내고, "이력을 얼마나
믿을 것인가"는 여기서 결정한다(스코어링 정책을 한곳에 모아두는 기존 원칙 그대로).

α 곡선은 베이지안 축소(shrinkage)의 표준 형태인 `A / (A + n)`을 쓴다 — 이력이 적을수록
intent 쪽으로 강하게 쏠리고, 쌓일수록 행동 쪽 비중이 커지되 바닥(`ALPHA_FLOOR`)에서 멈춘다.
바닥을 두는 이유: 이 서비스에서 사용자는 **이번 검색의 의도를 직접 말로 진술한다**(채팅으로
희망 역할·스킬을 밝힘). 과거 행동이 그 명시적 진술을 덮어써서는 안 되므로, intent 비중이
절반 아래로 내려가지 않게 막는다.
"""

from app.schemas.common import EmbeddingVector

# α = SMOOTHING / (SMOOTHING + n) — n=0이면 1.0(현재 동작과 완전히 동일), n=5면 0.5.
SMOOTHING = 5.0
# intent가 최소 이만큼은 유지된다 — 명시적으로 말한 의도가 과거 행동에 묻히지 않게.
ALPHA_FLOOR = 0.5


def intent_weight(interaction_count: int) -> float:
    """이번 요청에서 intent 임베딩이 차지할 비중(α). 나머지 (1-α)가 행동 임베딩 몫이다."""
    if interaction_count <= 0:
        return 1.0
    return max(ALPHA_FLOOR, SMOOTHING / (SMOOTHING + interaction_count))


def blend_query_vector(
    intent_vector: EmbeddingVector,
    behavior_vector: EmbeddingVector | None,
    interaction_count: int,
) -> list[float]:
    """intent와 행동 벡터를 α로 가중 합산한다. 행동 벡터가 없거나 이력이 0건이면 intent를
    그대로 돌려준다 — BE가 이 필드를 안 보내는 동안(하위 호환) 기존과 100% 동일하게 동작한다.

    코사인 유사도는 스케일 불변이라 합산 후 정규화하지 않는다(OpenAI 임베딩은 이미 단위
    벡터라 두 단위 벡터의 볼록 결합이면 충분하다).
    """
    alpha = intent_weight(interaction_count)
    if behavior_vector is None or alpha >= 1.0:
        return list(intent_vector)

    return [alpha * i + (1.0 - alpha) * b for i, b in zip(intent_vector, behavior_vector, strict=True)]
