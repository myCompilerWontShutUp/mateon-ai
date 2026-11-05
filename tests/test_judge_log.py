import pytest

from app.features.quality import judge as judge_module
from app.features.quality.judge import JudgeVerdict

# autouse 픽스처가 is_sampled를 바꿔치기하기 전의 실제 함수.
_real_is_sampled = judge_module.is_sampled


@pytest.fixture(autouse=True)
def _always_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    """이 파일의 기록 검증 테스트는 표본 추출(Settings.judge_sample_rate)과 무관하게 항상 판정한다.
    표본 추출 자체는 맨 아래 테스트들이 따로 검증한다."""
    monkeypatch.setattr(judge_module, "is_sampled", lambda _rate: True)


class _FakeTable:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def insert(self, row: dict) -> "_FakeTable":
        self._sink["row"] = row
        return self

    def execute(self) -> None:
        return None


class _FakeClient:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def table(self, name: str) -> _FakeTable:
        self._sink["table"] = name
        return _FakeTable(self._sink)


async def test_judge_and_log_minimal_row_when_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: dict = {}
    monkeypatch.setattr(judge_module, "get_supabase_client", lambda: _FakeClient(sink))

    async def fake_judge(generation_prompt_name, context, output_text) -> JudgeVerdict:
        return JudgeVerdict(score=9, violations=[], explanation="문제없음")

    monkeypatch.setattr(judge_module, "judge", fake_judge)

    await judge_module.judge_and_log("user_to_team_proposal", "컨텍스트", "출력")

    row = sink["row"]
    assert sink["table"] == "judge_results"
    assert row["pipeline"] == "user_to_team_proposal"
    assert row["score"] == 9
    assert row["passes"] is True
    assert "input_context" not in row  # pass는 최소 기록


async def test_judge_and_log_detailed_row_when_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: dict = {}
    monkeypatch.setattr(judge_module, "get_supabase_client", lambda: _FakeClient(sink))

    async def fake_judge(generation_prompt_name, context, output_text) -> JudgeVerdict:
        return JudgeVerdict(score=1, violations=["ID 노출"], explanation="user_id가 텍스트에 노출됨")

    monkeypatch.setattr(judge_module, "judge", fake_judge)

    await judge_module.judge_and_log("recommendation_reason", "컨텍스트", "user_id 203는...")

    row = sink["row"]
    assert row["passes"] is False
    assert row["input_context"] == "컨텍스트"
    assert row["generated_output"] == "user_id 203는..."
    assert row["violations"] == ["ID 노출"]


async def test_judge_and_log_swallows_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_judge(generation_prompt_name, context, output_text) -> JudgeVerdict:
        raise RuntimeError("openai 호출 실패")

    monkeypatch.setattr(judge_module, "judge", fake_judge)

    # 예외가 밖으로 전파되면 안 된다 — fire-and-forget 계약.
    await judge_module.judge_and_log("recommendation_reason", "컨텍스트", "출력")


def test_is_sampled_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _real_is_sampled(1.0) is True
    assert _real_is_sampled(0.0) is False
    monkeypatch.setattr(judge_module.random, "random", lambda: 0.19)
    assert _real_is_sampled(0.2) is True
    monkeypatch.setattr(judge_module.random, "random", lambda: 0.21)
    assert _real_is_sampled(0.2) is False


def _record_judge_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """judge_and_log는 예외를 삼키므로, 가짜가 예외를 던지는 방식으로는 "불렸다"를 잡을 수 없다 —
    호출을 기록해서 검사한다."""
    calls: list[str] = []

    async def recording_judge(*_args) -> JudgeVerdict:
        calls.append("judge")
        return JudgeVerdict(score=9, violations=[], explanation="ok")

    def recording_client():
        calls.append("supabase")
        return _FakeClient({})

    monkeypatch.setattr(judge_module, "judge", recording_judge)
    monkeypatch.setattr(judge_module, "get_supabase_client", recording_client)
    return calls


async def test_unsampled_generation_is_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    """표본에 안 뽑히면 판정 모델도, Supabase도 부르지 않는다(비용 절감의 핵심)."""
    monkeypatch.setattr(judge_module, "is_sampled", lambda _rate: False)
    calls = _record_judge_calls(monkeypatch)

    await judge_module.judge_and_log("recommendation_reason", "컨텍스트", "출력")

    assert calls == []


@pytest.mark.parametrize(("rate", "expected"), [(0.0, []), (1.0, ["judge", "supabase"])])
async def test_sample_rate_setting_controls_judging(
    monkeypatch: pytest.MonkeyPatch, rate: float, expected: list[str]
) -> None:
    """설정값(JUDGE_SAMPLE_RATE)이 실제 표본 추출까지 이어지는지 — 0이면 안 하고 1이면 전수."""
    monkeypatch.setattr(judge_module, "is_sampled", _real_is_sampled)
    settings = judge_module.get_settings().model_copy(update={"judge_sample_rate": rate})
    monkeypatch.setattr(judge_module, "get_settings", lambda: settings)
    calls = _record_judge_calls(monkeypatch)

    await judge_module.judge_and_log("recommendation_reason", "컨텍스트", "출력")

    assert calls == expected
