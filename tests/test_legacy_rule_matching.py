"""백엔드 원본(`EventMatchingService.matchInterestJob`)과 같은 결과가 나오는지 검증한다.

케이스 일부는 백엔드 원본 테스트(`EventMatchingServiceTest.InterestJobMatching`)와 같은 입력을 쓴다.
원본의 알려진 한계("AI"가 "email"에 걸리는 오탐 등)도 **고치지 않고 그대로 재현하는 게 정답**이다
— 비교군은 실제 기존 시스템이어야 한다.
"""

from app.evaluation.legacy_rule_matching import (
    interest_jobs_from_profile,
    legacy_relevance_score,
    legacy_rule_ranking,
    match_interest_job,
    team_search_text,
)


def test_exact_substring_scores_full_points() -> None:
    assert match_interest_job("백엔드 개발자", "백엔드 개발자 모집", 30) == 30


def test_match_is_case_insensitive() -> None:
    assert match_interest_job("Spring Boot", "spring boot 서버 개발", 30) == 30


def test_partial_token_match_scores_proportionally_with_integer_division() -> None:
    # "백엔드"만 걸리고 "개발자"는 없음 → 30 * 1 / 2 = 15
    assert match_interest_job("백엔드 개발자", "백엔드 인원 모집", 30) == 15
    # 3토큰 중 1개 → 20 * 1 / 3 = 6 (정수 나눗셈)
    assert match_interest_job("데이터 분석 전문가", "데이터 수집 팀", 20) == 6


def test_single_character_tokens_are_ignored() -> None:
    # "R"은 1글자라 부분 일치 대상에서 빠진다(통째 일치는 여전히 가능)
    assert match_interest_job("R 통계", "통계 분석", 30) == 15
    assert match_interest_job("R", "HR 담당", 30) == 30  # 통째 부분 문자열 일치


def test_blank_interest_job_scores_nothing() -> None:
    assert match_interest_job(None, "백엔드", 30) == 0
    assert match_interest_job("   ", "백엔드", 30) == 0


def test_reproduces_known_false_positive_ai_in_email() -> None:
    """원본 코드 주석에 기록된 오탐 — 고치지 않고 그대로 재현한다."""
    assert match_interest_job("AI", "문의는 email로 받습니다", 30) == 30


def test_reproduces_known_false_negative_synonym() -> None:
    """의미가 같아도 글자가 다르면 못 찾는다."""
    assert match_interest_job("서버 운영자", "백엔드 개발자를 모집합니다", 30) == 0


def test_primary_secondary_tertiary_weights() -> None:
    assert legacy_relevance_score(["백엔드", "디자인", "마케팅"], "백엔드 디자인 마케팅") == 60
    assert legacy_relevance_score(["없음", "없음", "마케팅"], "마케팅") == 10


def test_keywords_are_preferred_over_tech_field() -> None:
    assert interest_jobs_from_profile(["C++", "백엔드개발", "알고리즘", "로봇"], "통계") == [
        "C++",
        "백엔드개발",
        "알고리즘",
    ]


def test_falls_back_to_tech_field_items_when_keywords_are_empty() -> None:
    assert interest_jobs_from_profile([], "데이터 분석 · 통계학 · Python · R") == ["데이터 분석", "통계학", "Python"]
    assert interest_jobs_from_profile([], "[AI / LLM]\n- LLM·RAG 기반 질의응답") == ["AI", "LLM", "LLM"]
    assert interest_jobs_from_profile([], "") == []


def test_team_search_text_uses_korean_role_labels() -> None:
    text = team_search_text("핀테크 앱을 만듭니다", ["BE", "Design"], ["Spring Boot"])
    assert "백엔드 개발" in text and "디자인" in text and "Spring Boot" in text


def test_ranking_sorts_by_score_and_breaks_ties_reproducibly() -> None:
    team_texts = {1: "디자인 팀", 2: "백엔드 팀", 3: "마케팅 팀", 4: "백엔드 개발 팀"}
    ranked, scores = legacy_rule_ranking(["백엔드"], team_texts, tie_break_seed=7)

    assert scores == {1: 0, 2: 30, 3: 0, 4: 30}
    assert set(ranked[:2]) == {2, 4}
    assert ranked == legacy_rule_ranking(["백엔드"], team_texts, tie_break_seed=7)[0]


def test_ties_are_not_biased_toward_low_team_ids() -> None:
    """희망직무가 하나도 안 걸리면 전부 0점 — 이때 1위가 항상 1번 팀이면 안 된다."""
    team_texts = {team_id: "무관한 모집글" for team_id in range(1, 51)}
    firsts = {legacy_rule_ranking(["블록체인"], team_texts, tie_break_seed=seed)[0][0] for seed in range(20)}
    assert len(firsts) > 1
