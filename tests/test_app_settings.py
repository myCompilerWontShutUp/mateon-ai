"""운영 설정 — 필수 값 검증, API 문서 노출 여부, 생성 모델 추론 강도(2026-11-05)."""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from openai import BadRequestError
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app
from app.openai_client import extraction as extraction_module
from app.schemas.llm_output import RecommendationReasonText

# 실제 .env와 무관하게 Settings를 만들 때 쓰는 필수 값(가짜).
_REQUIRED = {
    "openai_api_key": "sk-test",
    "internal_shared_secret": "secret",
    "openai_judge_model": "judge-model",
    "supabase_url": "https://example.supabase.co",
    "supabase_service_role_key": "service-role",
}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})


@pytest.mark.parametrize("field", sorted(_REQUIRED))
def test_blank_required_value_fails_at_startup(field: str) -> None:
    """.env.example을 복사하고 값을 안 채운 경우 — 빈 값이나 공백만 있는 값으로는 서버가 뜨면 안 된다."""
    with pytest.raises(ValidationError):
        _settings(**{field: ""})
    with pytest.raises(ValidationError):
        _settings(**{field: "   "})


def test_blank_env_var_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SHARED_SECRET", "")
    others = {k: v for k, v in _REQUIRED.items() if k != "internal_shared_secret"}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **others)


def test_reasoning_effort_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        _settings(openai_reasoning_effort="lowest")
    assert _settings(openai_reasoning_effort="low").openai_reasoning_effort == "low"
    # .env.example은 이 값을 비워서 내보낸다 — 빈 값은 "모델 기본값"이다.
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "")
    assert _settings().openai_reasoning_effort is None


def test_production_safe_defaults() -> None:
    settings = _settings()
    assert settings.api_docs_enabled is False
    assert settings.judge_sample_rate == 0.2
    assert settings.openai_reasoning_effort is None


async def test_empty_secret_header_is_rejected() -> None:
    app = create_app(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/contests/similarity-map", headers={"X-Internal-Secret": ""}, json={}
        )
    assert response.status_code == 401


def _bad_request(param: str | None) -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return BadRequestError(
        "bad request", response=httpx.Response(400, request=request), body={"param": param}
    )


def test_config_errors_are_told_apart_from_bad_uploads() -> None:
    assert extraction_module.is_config_error(_bad_request("reasoning_effort"))
    assert extraction_module.is_config_error(_bad_request("model"))
    assert not extraction_module.is_config_error(_bad_request(None))
    assert not extraction_module.is_config_error(_bad_request("messages"))


async def _get(app, path: str) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return (await client.get(path)).status_code


async def test_api_docs_are_hidden_unless_enabled() -> None:
    hidden = create_app(get_settings().model_copy(update={"api_docs_enabled": False}))
    shown = create_app(get_settings().model_copy(update={"api_docs_enabled": True}))

    assert await _get(hidden, "/docs") == 404
    assert await _get(hidden, "/openapi.json") == 404
    assert await _get(hidden, "/health") == 200
    assert await _get(shown, "/openapi.json") == 200
    # 계약 문서 생성(app.openapi())은 노출 여부와 무관하게 동작해야 한다.
    assert hidden.openapi()["paths"]


class _FakeCompletions:
    def __init__(self, sink: list[dict]) -> None:
        self._sink = sink

    async def parse(self, **kwargs):
        self._sink.append(kwargs)

        class _Message:
            parsed = RecommendationReasonText(reason="ok")

        class _Choice:
            message = _Message()

        class _Completion:
            choices = [_Choice()]

        return _Completion()


class _FakeClient:
    def __init__(self, sink: list[dict]) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(sink)})()


async def test_reasoning_effort_applies_only_to_the_generation_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    settings = get_settings().model_copy(update={"openai_reasoning_effort": "low"})
    monkeypatch.setattr(extraction_module, "get_settings", lambda: settings)
    monkeypatch.setattr(extraction_module, "get_openai_client", lambda: _FakeClient(calls))

    messages = [{"role": "user", "content": "hi"}]
    await extraction_module.extract_structured(messages, RecommendationReasonText)
    await extraction_module.extract_structured(messages, RecommendationReasonText, model="judge-model")

    assert calls[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in calls[1]


async def test_reasoning_effort_is_not_sent_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    settings = get_settings().model_copy(update={"openai_reasoning_effort": None})
    monkeypatch.setattr(extraction_module, "get_settings", lambda: settings)
    monkeypatch.setattr(extraction_module, "get_openai_client", lambda: _FakeClient(calls))

    await extraction_module.extract_structured([{"role": "user", "content": "hi"}], RecommendationReasonText)

    assert "reasoning_effort" not in calls[0]
