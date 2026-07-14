from app.features.user_to_team.template import compute_missing_fields, render_intent_embedding_text
from app.schemas.user_intent import UserIntentFields


def test_compute_missing_fields_all_present() -> None:
    fields = UserIntentFields(desired_roles=["BE"], experience_level="beginner")
    assert compute_missing_fields(fields) == []


def test_compute_missing_fields_reports_missing() -> None:
    fields = UserIntentFields()
    assert set(compute_missing_fields(fields)) == {"desired_roles", "experience_level"}


def test_render_is_deterministic_and_preserves_intro() -> None:
    fields = UserIntentFields(
        desired_roles=["BE"],
        skills=["React"],
        experience_level="beginner",
        activity_style="주 2회 오프라인",
    )
    intro = "저는 프론트엔드를 1년 해봤고 백엔드로 성장하고 싶습니다."

    first = render_intent_embedding_text(intro, fields)
    second = render_intent_embedding_text(intro, fields)

    assert first == second
    assert intro in first
    assert "BE" in first
