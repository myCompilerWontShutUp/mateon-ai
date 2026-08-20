from pydantic import BaseModel


class GroundTruthLabel(BaseModel):
    relevant_team_ids: list[int]
    rationale: str


class NaiveRankingResult(BaseModel):
    ranked_team_ids: list[int]
