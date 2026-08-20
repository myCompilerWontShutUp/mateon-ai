from app.features.quality.judge import PASS_THRESHOLD, JudgeVerdict


def test_passes_true_at_threshold() -> None:
    verdict = JudgeVerdict(score=PASS_THRESHOLD, violations=[], explanation="")
    assert verdict.passes is True


def test_passes_false_below_threshold() -> None:
    verdict = JudgeVerdict(score=PASS_THRESHOLD - 1, violations=["절대평가"], explanation="")
    assert verdict.passes is False


def test_passes_true_at_max_score() -> None:
    verdict = JudgeVerdict(score=10, violations=[], explanation="")
    assert verdict.passes is True


def test_passes_false_at_min_score() -> None:
    verdict = JudgeVerdict(score=0, violations=["ID 노출"], explanation="")
    assert verdict.passes is False
