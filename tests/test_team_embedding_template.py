from app.features.team_embedding.template import compute_missing_fields, render_team_embedding_text
from app.schemas.contest import ContestField
from app.schemas.role_codes import RoleCode
from app.schemas.team_extraction import OptionalTeamFields, TeamEmbeddingRefreshRequest, TeamSoftFields


def _request(**overrides) -> TeamEmbeddingRefreshRequest:
    defaults = {
        "intro_text": "커머스 플랫폼을 만드는 4인 팀입니다. 현재 FE 2명, Design 1명으로 구성돼 있습니다.",
        "recruiting_roles": ["BE"],
        "required_skills": ["Spring Boot", "PostgreSQL"],
        "contest_field": "커머스",
    }
    defaults.update(overrides)
    return TeamEmbeddingRefreshRequest(**defaults)


def test_compute_missing_fields_all_present() -> None:
    soft_fields = TeamSoftFields(
        activity_goal="공모전 수상",
        activity_style="주 2회 오프라인",
        activity_intensity="high",
        beginner_friendly=True,
    )
    assert compute_missing_fields(soft_fields) == []


def test_compute_missing_fields_some_missing() -> None:
    soft_fields = TeamSoftFields(activity_goal="공모전 수상")
    missing = compute_missing_fields(soft_fields)
    assert set(missing) == {"activity_style", "activity_intensity", "beginner_friendly"}


def test_render_is_deterministic() -> None:
    request = _request()
    soft_fields = TeamSoftFields(
        activity_goal="공모전 수상",
        activity_style="주 2회 오프라인",
        activity_intensity="high",
        beginner_friendly=True,
        team_atmosphere="자유로운 분위기",
        recruiting_roles=[RoleCode.BE],
        contest_field=ContestField.MANAGEMENT_CONSULTING_MARKETING,
    )

    first = render_team_embedding_text(request, soft_fields)
    second = render_team_embedding_text(request, soft_fields)

    assert first == second
    assert "BE" in first
    assert "Spring Boot" in first
    assert "공모전 수상" in first
    assert "초보자 환영" in first


def test_render_handles_missing_soft_fields() -> None:
    request = _request()
    soft_fields = TeamSoftFields()

    rendered = render_team_embedding_text(request, soft_fields)

    assert "미정" in rendered
    assert "활동 시간: 미상" in rendered


def test_render_includes_optional_activity_time_when_present() -> None:
    request = _request()
    soft_fields = TeamSoftFields(optional=OptionalTeamFields(activity_time="주말"))

    rendered = render_team_embedding_text(request, soft_fields)

    assert "활동 시간: 주말" in rendered


def test_optional_field_never_triggers_missing_fields() -> None:
    soft_fields = TeamSoftFields(
        activity_goal="공모전 수상",
        activity_style="주 2회 오프라인",
        activity_intensity="high",
        beginner_friendly=True,
    )
    assert soft_fields.optional.activity_time is None
    assert compute_missing_fields(soft_fields) == []
