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


def lift_key(direction: str, cluster_key: str) -> str:
    """cluster_weight_config에 저장·조회할 때 쓰는 키 — 방향을 앞에 붙인다.

    사용자 키(역할:경험 수준)와 팀 키(역할:공모전 분야)는 둘째 자리가 비면 똑같이 "역할:unknown"이
    되어, 역제안(TEAM_TO_USER) 선택에서 나온 보정값이 제안(USER_TO_TEAM) 추천에 섞일 수 있었다
    (2026-11-05 수정). 선택 이벤트 표의 chooser_cluster_key는 그대로 두고(방향은 별도 컬럼),
    보정값을 계산·저장·조회할 때만 이 키를 쓴다.
    """
    return f"{direction}|{cluster_key}"
