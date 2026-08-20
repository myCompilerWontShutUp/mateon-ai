from app.features.user_to_team.template import compute_missing_fields, render_intent_embedding_text
from app.schemas.user_intent import OptionalUserFields, UserIntentFields


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


def test_render_uses_misang_for_absent_optional_field() -> None:
    fields = UserIntentFields(desired_roles=["BE"], experience_level="beginner")

    rendered = render_intent_embedding_text("자기소개", fields)

    assert "활동 시간: 미상" in rendered


def test_render_includes_optional_activity_time_when_present() -> None:
    fields = UserIntentFields(
        desired_roles=["BE"],
        experience_level="beginner",
        optional=OptionalUserFields(activity_time="평일 저녁"),
    )

    rendered = render_intent_embedding_text("자기소개", fields)

    assert "활동 시간: 평일 저녁" in rendered


def test_optional_field_never_triggers_missing_fields() -> None:
    fields = UserIntentFields(desired_roles=["BE"], experience_level="beginner")
    assert fields.optional.activity_time is None
    assert compute_missing_fields(fields) == []
