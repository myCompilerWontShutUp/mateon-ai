from app.core.prompts import load_prompt

_PROMPT_NAMES = [
    "team_soft_fields_extraction",
    "user_intent_extraction",
    "user_to_team_proposal",
    "team_to_user_proposal",
    "recommendation_reason",
    "judge_generated_text",
]


def test_all_prompts_load_without_comment_lines() -> None:
    for name in _PROMPT_NAMES:
        prompt = load_prompt(name)
        assert prompt.strip() != ""
        assert "# schema:" not in prompt


def test_load_prompt_is_cached() -> None:
    assert load_prompt("recommendation_reason") is load_prompt("recommendation_reason")
