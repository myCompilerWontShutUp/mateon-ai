from app.features.contest_embedding.template import render_contest_embedding_text


def test_render_is_deterministic_for_same_input() -> None:
    a = render_contest_embedding_text("AI 해커톤", "대학생 대상 AI 서비스 개발 대회입니다.")
    b = render_contest_embedding_text("AI 해커톤", "대학생 대상 AI 서비스 개발 대회입니다.")
    assert a == b


def test_render_includes_title_and_description() -> None:
    text = render_contest_embedding_text("AI 해커톤", "대학생 대상 AI 서비스 개발 대회입니다.")
    assert "AI 해커톤" in text
    assert "대학생 대상 AI 서비스 개발 대회입니다." in text
