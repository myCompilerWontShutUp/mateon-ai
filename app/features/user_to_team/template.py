from app.schemas.user_intent import UserIntentFields

REQUIRED_FIELDS = ("desired_roles", "experience_level")


def compute_missing_fields(fields: UserIntentFields) -> list[str]:
    missing = []
    if not fields.desired_roles:
        missing.append("desired_roles")
    if fields.experience_level is None:
        missing.append("experience_level")
    return missing


def render_intent_embedding_text(conversation_text: str, fields: UserIntentFields) -> str:
    lines = [
        f"자기소개: {conversation_text}",
        f"희망 역할: {', '.join(fields.desired_roles) or '미정'}",
        f"스킬: {', '.join(fields.skills) or '미정'}",
        f"관심 분야: {', '.join(fields.interests) or '미정'}",
        f"활동 목표: {fields.activity_goal or '미정'}",
        f"활동 방식: {fields.activity_style or '미정'}",
        f"경험 수준: {fields.experience_level or '미정'}",
    ]
    return "\n".join(lines)
