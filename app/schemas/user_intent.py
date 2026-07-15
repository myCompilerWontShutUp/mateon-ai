from pydantic import BaseModel, Field

from app.schemas.common import EmbeddingVector


class ConversationMessage(BaseModel):
    id: int
    message: str


class UserIntentExtractionRequest(BaseModel):
    # 자기소개서든 재질문 답변이든 "사용자가 한 말"이라는 점에서 동일하므로 하나의 리스트로
    # 받는다 — 순서가 배열 순서로 자연히 보존되고, 재질문 흐름은 이 리스트에 답변을 계속
    # append해서 통째로 다시 보내는 방식으로 이어간다(무상태). 최소 1개 필요 — 챗봇 응답
    # 생성이 가장 최근 메시지를 참조하므로 빈 배열은 422로 막는다.
    messages: list[ConversationMessage] = Field(min_length=1)


class UserIntentFields(BaseModel):
    desired_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    activity_goal: str | None = None
    activity_style: str | None = None
    experience_level: str | None = None


class UserIntentExtractionResult(BaseModel):
    missing_fields: list[str]
    extracted: UserIntentFields
    embedding_text: str | None = None
    embedding_vector: EmbeddingVector | None = None
    # 챗봇 형태로 사용자에게 그대로 보여줄 문구 — 재진술 + (미완성이면) 유도 질문 /
    # (완성이면) 추천 시작 안내 / (답변이 엉뚱하면) 방어 문구. LLM이 생성하며, 프론트는 이
    # 텍스트를 그대로 표시하기만 하면 된다(질문 문구를 프론트가 직접 조립하지 않는다).
    assistant_message: str
