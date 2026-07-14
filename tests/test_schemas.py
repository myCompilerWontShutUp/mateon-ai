from app.schemas.llm_output import ProposalTextFields, RecommendationReasonText
from app.schemas.proposal import ProposalSchema
from app.schemas.team_extraction import TeamSoftFields

_FORBIDDEN_FIELD_MARKERS = ("_id", "score")


def test_llm_output_schemas_never_carry_ids_or_scores() -> None:
    for schema in (ProposalTextFields, RecommendationReasonText, TeamSoftFields):
        for field_name in schema.model_fields:
            assert not any(marker in field_name for marker in _FORBIDDEN_FIELD_MARKERS), (
                f"{schema.__name__}.{field_name} looks like an ID/score field — "
                "LLM structured output must be text-only, ids/scores are assembled by the server"
            )


def test_proposal_schema_does_carry_ids_and_scores() -> None:
    field_names = set(ProposalSchema.model_fields)
    assert {"user_id", "team_id", "sender_id", "receiver_id", "synergy_score"} <= field_names
