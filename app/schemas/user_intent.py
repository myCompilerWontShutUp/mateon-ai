from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import EmbeddingVector


class ConversationMessage(BaseModel):
    id: int
    # 추출 LLM이 짧고 모호한 답변(예: "없는거같아", "평범한거같은데")을 해석하려면 그 답이 어떤
    # 질문에 대한 것인지가 필요하다 — AI의 질문을 빼고 사용자 발화만 보내면 문맥이 사라져서
    # missing_fields가 영영 안 비는 문제가 실제로 있었다(2026-07-15). role을 넣어 AI의
    # assistant_message도 함께 재전송하게 한다. 기본값 user — 한 번에 끝나는 단문 자기소개처럼
    # 왕복이 없는 흔한 경우엔 매번 명시할 필요가 없다.
    role: Literal["user", "assistant"] = "user"
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
