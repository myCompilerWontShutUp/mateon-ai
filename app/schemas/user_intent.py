from pydantic import BaseModel, Field


class UserIntentExtractionRequest(BaseModel):
    self_introduction: str
    profile: dict = Field(default_factory=dict)
    conversation_answers: dict = Field(default_factory=dict)


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
    embedding_vector: list[float] | None = None
