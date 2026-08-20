import pytest

from app.features.quality import judge as judge_module
from app.features.quality.judge import JudgeVerdict


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
