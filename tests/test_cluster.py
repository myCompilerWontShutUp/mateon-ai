from app.scoring.cluster import team_cluster_key, user_cluster_key


def test_user_cluster_key_combines_primary_role_and_experience() -> None:
    assert user_cluster_key(["BE", "FE"], "beginner") == "BE:beginner"


def test_user_cluster_key_handles_missing_fields() -> None:
    assert user_cluster_key([], None) == "unknown:unknown"


def test_team_cluster_key_combines_primary_role_and_contest_field() -> None:
    assert team_cluster_key(["BE"], "FINTECH") == "BE:FINTECH"


def test_team_cluster_key_handles_missing_contest_field() -> None:
    assert team_cluster_key(["FE"], None) == "FE:unknown"
