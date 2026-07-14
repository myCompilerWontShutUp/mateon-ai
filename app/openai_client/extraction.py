from typing import TypeVar

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.openai_client.client import get_openai_client

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)

_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


@retry(
    retry=retry_if_exception_type(_RETRYABLE_ERRORS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def extract_structured(
    messages: list[ChatCompletionMessageParam],
    response_model: type[ResponseModelT],
) -> ResponseModelT:
    settings = get_settings()
    client = get_openai_client()

    completion = await client.chat.completions.parse(
        model=settings.openai_llm_model,
        messages=messages,
        response_format=response_model,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI response did not contain parsed structured output")
    return parsed
