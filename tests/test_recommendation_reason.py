import pytest

from app.features.recommendation import reason as reason_module
from app.schemas.llm_output import RecommendationReasonText
from app.schemas.recommendation import RecommendationReasonRequest


async def test_generate_recommendation_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_structured(messages, response_model) -> RecommendationReasonText:
        return RecommendationReasonText(reason="BE 결핍을 보완할 수 있어 적합합니다.")

    monkeypatch.setattr(reason_module, "extract_structured", fake_extract_structured)

    request = RecommendationReasonRequest(
        candidate_summary="React/TypeScript 경험, 초보자",
        target_summary="커머스 플랫폼, BE 1명 결핍",
        score_context="유사도 높음, 역할 일치",
    )
    result = await reason_module.generate_recommendation_reason(request)

    assert result.reason == "BE 결핍을 보완할 수 있어 적합합니다."
