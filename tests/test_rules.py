from app.scoring.rules import activity_time_match_score


def test_activity_time_match_exact() -> None:
    assert activity_time_match_score("평일 저녁", "평일 저녁") == 1.0


def test_activity_time_match_mismatch() -> None:
    assert activity_time_match_score("평일 저녁", "주말") == 0.0


def test_activity_time_match_missing_info_is_neutral() -> None:
    assert activity_time_match_score(None, "주말") == 0.5
    assert activity_time_match_score("주말", None) == 0.5
