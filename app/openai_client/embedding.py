from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.openai_client.client import get_openai_client

_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


@retry(
    retry=retry_if_exception_type(_RETRYABLE_ERRORS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    client = get_openai_client()

    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        dimensions=settings.embedding_dimension,
    )
    return response.data[0].embedding
