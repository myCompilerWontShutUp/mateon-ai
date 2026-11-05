from app.schemas.activity import activity_style_label
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
        f"활동 목표: {fields.optional.activity_goal or '미상'}",
        # 코드(ONLINE)가 아니라 한글 라벨로 넣는다 — enum 도입 전 임베딩 텍스트도 한국어였어서,
        # BE에 저장된 옛 벡터와 새로 계산한 벡터의 표현 차이를 줄이기 위함.
        f"활동 방식: {activity_style_label(fields.activity_style) or '미정'}",
        f"경험 수준: {fields.experience_level or '미정'}",
        f"활동 시간: {fields.optional.activity_time or '미상'}",
    ]
    return "\n".join(lines)
