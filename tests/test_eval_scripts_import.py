"""평가 스크립트는 import 단계에서 모듈 상수를 만든다 — 가중치 구성요소가 바뀌면(예: cf_affinity 추가)
실행하자마자 죽을 수 있어서, 네트워크 없이 import만 해 본다."""

import runpy
from pathlib import Path

import pytest

from app.evaluation.simulation import SIMULATED_TRUE_PREFERENCE_WEIGHTS
from app.features.user_to_team.scoring import WEIGHTS
from app.scoring.cluster_weights import adjust_weights

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.parametrize(
    "script",
    ["run_eval.py", "run_eval_on_llm_pool.py", "eval_ml_pretrain_weights.py", "run_cf_demo_eval.py"],
)
def test_eval_script_imports(script: str) -> None:
    runpy.run_path(str(_SCRIPTS / script), run_name="not_main")


def test_stress_test_lifts_reproduce_the_simulated_preference_exactly() -> None:
    lifts = runpy.run_path(str(_SCRIPTS / "run_eval.py"), run_name="not_main")["STRESS_TEST_LIFTS"]
    adjusted = adjust_weights(WEIGHTS, lifts)
    for name, weight in adjusted.items():
        assert weight == pytest.approx(SIMULATED_TRUE_PREFERENCE_WEIGHTS.get(name, 0.0))
