from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamSoftFields

REQUIRED_SOFT_FIELDS = ("activity_goal", "activity_style", "activity_intensity", "beginner_friendly")


def compute_missing_fields(soft_fields: TeamSoftFields) -> list[str]:
    return [name for name in REQUIRED_SOFT_FIELDS if getattr(soft_fields, name) is None]


def render_team_embedding_text(
    request: TeamEmbeddingRefreshRequest, soft_fields: TeamSoftFields
) -> str:
    beginner_desc = (
        "초보자 환영" if soft_fields.beginner_friendly else "경험자 우대"
        if soft_fields.beginner_friendly is not None
        else "미정"
    )

    lines = [
        f"팀 소개: {request.intro_text}",
        f"모집 역할: {', '.join(request.recruiting_roles) or '미정'}",
        f"요구 스킬: {', '.join(request.required_skills) or '미정'}",
        f"활동 목표: {soft_fields.activity_goal or '미정'}",
        f"활동 방식: {soft_fields.activity_style or '미정'}",
        f"활동 강도: {soft_fields.activity_intensity or '미정'}",
        f"공모전 분야: {request.contest_field or '미정'}",
        f"초보자 가능 여부: {beginner_desc}",
        f"팀 분위기: {soft_fields.team_atmosphere or '미정'}",
    ]
    return "\n".join(lines)
