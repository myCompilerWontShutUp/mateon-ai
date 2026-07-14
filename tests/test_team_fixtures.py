import json
from pathlib import Path

from app.core.config import get_settings
from app.schemas.embedding import EmbeddingResult
from tests.fixtures.team_definitions import TEAM_FIXTURES

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "teams.json"


def _load_fixtures() -> dict[str, EmbeddingResult]:
    raw = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return {team_id: EmbeddingResult(**payload) for team_id, payload in raw.items()}


def test_fixture_file_covers_all_defined_teams() -> None:
    fixtures = _load_fixtures()
    assert set(fixtures) == {str(team_id) for team_id in TEAM_FIXTURES}


def test_every_fixture_embedding_has_expected_dimension() -> None:
    settings = get_settings()
    fixtures = _load_fixtures()
    for team_id, result in fixtures.items():
        assert len(result.embedding_vector) == settings.embedding_dimension, team_id
        assert result.embedding_text.strip() != ""
