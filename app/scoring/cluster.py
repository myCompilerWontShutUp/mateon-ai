# 클러스터는 비지도 학습 결과가 아니라 고정 ENUM 조합을 그대로 키로 쓴다(CLAUDE.md
# "## 모니터링·데이터 기반 가중치 보정" 2번 참고). 대표 코드(첫 번째 값)만 쓰는 이유는
# 다중 역할/다중 분야 조합까지 키에 넣으면 조합 수가 급증해 클러스터당 데이터가 더 희소해지기
# 때문이다 — 필요해지면 나중에 세분화한다.

_UNKNOWN = "unknown"


def user_cluster_key(desired_roles: list[str], experience_level: str | None) -> str:
    primary_role = desired_roles[0] if desired_roles else _UNKNOWN
    return f"{primary_role}:{experience_level or _UNKNOWN}"


def team_cluster_key(recruiting_roles: list[str], contest_field: str | None) -> str:
    primary_role = recruiting_roles[0] if recruiting_roles else _UNKNOWN
    return f"{primary_role}:{contest_field or _UNKNOWN}"
