from typing import TypeVar

from openai import APIConnectionError, APITimeoutError, BadRequestError, InternalServerError, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.openai_client.client import get_openai_client

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)

_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

# 400 중에서도 우리 설정(모델명·추론 강도) 때문에 거부된 경우. 업로드 엔드포인트는 OpenAI의 400을
# "파일을 처리할 수 없다"는 400으로 바꿔 돌려주는데, 설정 문제까지 그렇게 바꾸면 BE가 엉뚱하게 업로드
# 코드를 의심하게 된다 — 이런 경우는 서버 오류로 그대로 드러낸다.
_CONFIG_PARAMS = frozenset({"model", "reasoning_effort"})


def is_config_error(exc: BadRequestError) -> bool:
    return getattr(exc, "param", None) in _CONFIG_PARAMS


@retry(
    retry=retry_if_exception_type(_RETRYABLE_ERRORS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def extract_structured(
    messages: list[ChatCompletionMessageParam],
    response_model: type[ResponseModelT],
    model: str | None = None,
) -> ResponseModelT:
    settings = get_settings()
    client = get_openai_client()

    # 추론 강도는 생성 모델 호출(model 미지정)에만 적용한다 — 판정 모델은 모델마다 허용 값이
    # 달라 모델 기본값을 그대로 쓴다. 설정이 비어 있으면 아예 보내지 않는다(모델 기본값).
    extra: dict = {}
    if model is None and settings.openai_reasoning_effort:
        extra["reasoning_effort"] = settings.openai_reasoning_effort

    completion = await client.chat.completions.parse(
        model=model if model is not None else settings.openai_llm_model,
        messages=messages,
        response_format=response_model,
        **extra,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI response did not contain parsed structured output")
    return parsed
