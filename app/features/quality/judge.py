import asyncio
import logging
import random

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.supabase_client.client import get_supabase_client

logger = logging.getLogger(__name__)

# 이 값 미만이면 fail로 간주한다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 5번).
PASS_THRESHOLD = 3


class JudgeVerdict(BaseModel):
    # 0~10 정수(소수점 없음). 10=환각·편향 없음, 0=위험한 수준.
    score: int = Field(ge=0, le=10)
    violations: list[str]
    explanation: str

    @property
    def passes(self) -> bool:
        return self.score >= PASS_THRESHOLD


async def judge(generation_prompt_name: str, context: str, output_text: str) -> JudgeVerdict:
    generation_prompt = load_prompt(generation_prompt_name)
    judge_system_prompt = load_prompt("judge_generated_text")
    prompt = (
        f"[생성 프롬프트]\n{generation_prompt}\n\n"
        f"[입력 컨텍스트]\n{context}\n\n"
        f"[생성된 텍스트]\n{output_text}"
    )
    settings = get_settings()
    return await extract_structured(
        messages=[
            {"role": "system", "content": judge_system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_model=JudgeVerdict,
        model=settings.openai_judge_model,
    )


def _write_judge_result(pipeline: str, verdict: JudgeVerdict, context: str, output_text: str) -> None:
    settings = get_settings()
    row: dict = {
        "pipeline": pipeline,
        "judge_model": settings.openai_judge_model,
        "score": verdict.score,
        "passes": verdict.passes,
    }
    if not verdict.passes:
        row.update(
            input_context=context,
            generated_output=output_text,
            violations=verdict.violations,
            explanation=verdict.explanation,
        )
    get_supabase_client().table("judge_results").insert(row).execute()


def is_sampled(rate: float) -> bool:
    """이번 생성물을 판정할지 무작위로 정한다. rate가 1.0 이상이면 항상, 0 이하이면 절대 판정."""
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return random.random() < rate


async def judge_and_log(pipeline: str, context: str, output_text: str) -> None:
    """생성 직후 fire-and-forget으로 호출한다 — 응답 경로를 막지 않고, 실패해도 삼킨다.

    전수가 아니라 Settings.judge_sample_rate 비율로만 판정한다(표본 감사). 판정 모델 호출 비용이
    생성 비용의 약 20배라서다 — 무작위 표본이라 judge_results의 실패율 추이는 그대로 추정된다.
    """
    if not is_sampled(get_settings().judge_sample_rate):
        return
    try:
        verdict = await judge(pipeline, context, output_text)
        # supabase-py 클라이언트는 동기라, 이벤트 루프를 막지 않게 스레드에서 실행한다.
        await asyncio.to_thread(_write_judge_result, pipeline, verdict, context, output_text)
    except Exception:
        logger.exception("judge_and_log 실패 (pipeline=%s)", pipeline)
