from app.features.team_embedding.template import compute_missing_fields, render_team_embedding_text
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamMember, TeamSoftFields


def _request(**overrides) -> TeamEmbeddingRefreshRequest:
    defaults = {
        "intro_text": "커머스 플랫폼을 만드는 4인 팀입니다.",
        "recruiting_roles": ["BE"],
        "required_skills": ["Spring Boot", "PostgreSQL"],
        "current_members": [TeamMember(role="FE", count=2), TeamMember(role="Design", count=1)],
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
