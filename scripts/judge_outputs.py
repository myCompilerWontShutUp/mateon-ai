"""LLM-as-judge: 실제로 생성된 summary/message/reason이 CLAUDE.md 설계 원칙
(절대평가 금지, "이 팀/역할에 대한 적합도"로만 서술, ID/점수 미언급)을 지키는지 점검한다.

CI에는 연결되어 있지 않다 — 필요할 때 수동으로 실행한다: `python scripts/judge_outputs.py`
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from app.core.prompts import load_prompt  # noqa: E402
from app.features.recommendation.reason import generate_recommendation_reason  # noqa: E402
from app.features.team_to_user.proposal import assemble_team_to_user_proposal  # noqa: E402
from app.features.user_to_team.proposal import assemble_user_to_team_proposal  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402
from app.schemas.proposal import ProposalAssemblyRequest  # noqa: E402
from app.schemas.recommendation import RecommendationReasonRequest  # noqa: E402


class JudgeVerdict(BaseModel):
    passes: bool
    violations: list[str]
    explanation: str


async def judge(generation_prompt_name: str, context: str, output_text: str) -> JudgeVerdict:
    generation_prompt = load_prompt(generation_prompt_name)
    judge_system_prompt = load_prompt("judge_generated_text")
    prompt = (
        f"[생성 프롬프트]\n{generation_prompt}\n\n"
        f"[입력 컨텍스트]\n{context}\n\n"
        f"[생성된 텍스트]\n{output_text}"
    )
    return await extract_structured(
        messages=[
            {"role": "system", "content": judge_system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_model=JudgeVerdict,
    )


async def check(label: str, generation_prompt_name: str, context: str, output_text: str) -> bool:
    verdict = await judge(generation_prompt_name, context, output_text)
    status = "PASS" if verdict.passes else "FAIL"
    print(f"[{status}] {label}")
    print(f"  출력: {output_text}")
    if not verdict.passes:
        print(f"  위반: {verdict.violations}")
    print(f"  근거: {verdict.explanation}\n")
    return verdict.passes


async def main() -> None:
    results = []

    candidate_summary = "실무 3년차 백엔드 개발자, Spring Boot/Kafka 능숙, 핀테크 관심, 고강도 협업 선호"
    target_summary = "핀테크 가계부 서비스, BE 1명 결핍, Spring Boot/Kafka/Redis 요구, 주 4회 오프라인"

    # summary/message는 한 프롬프트가 같이 요구하는 한 쌍이므로 분리해서 판정하지 않는다 —
    # 따로 판정하면 "message가 없다"는 식의 오탐(false positive)이 나온다.
    proposal = await assemble_user_to_team_proposal(
        ProposalAssemblyRequest(
            user_id=203, team_id=7, sender_id=203, receiver_id=7, synergy_score=0.83,
            candidate_summary=candidate_summary, target_summary=target_summary,
        )
    )
    context = f"지원자 요약: {candidate_summary}\n팀 요약: {target_summary}"
    proposal_output = f"summary: {proposal.summary}\nmessage: {proposal.message}"
    results.append(await check("user-to-team proposal", "user_to_team_proposal", context, proposal_output))

    scout = await assemble_team_to_user_proposal(
        ProposalAssemblyRequest(
            user_id=203, team_id=7, sender_id=7, receiver_id=203, synergy_score=0.88,
            portfolio_role_fit_score=1.0,
            candidate_summary=candidate_summary, target_summary=target_summary,
        )
    )
    context = f"팀 요약: {target_summary}\n스카우트 대상 요약: {candidate_summary}"
    scout_output = f"summary: {scout.summary}\nmessage: {scout.message}"
    results.append(await check("team-to-user proposal", "team_to_user_proposal", context, scout_output))

    reason = await generate_recommendation_reason(
        RecommendationReasonRequest(
            candidate_summary=candidate_summary, target_summary=target_summary,
            score_breakdown={"similarity": 0.83, "role_match": 1.0, "deficit_fit": 1.0},
        )
    )
    context = f"후보 요약: {candidate_summary}\n대상 요약: {target_summary}"
    results.append(await check("recommendation.reason", "recommendation_reason", context, reason.reason))

    print(f"{sum(results)}/{len(results)} passed")


if __name__ == "__main__":
    asyncio.run(main())
