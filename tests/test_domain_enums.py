"""도메인 코드(공모전 도메인·역할·활동 방식·공모전 분류) 무결성 — FE·BE가 이 값을 그대로 따르므로
(2026-11-05) 깨지면 세 팀이 같이 깨진다."""

import re

import pytest
from pydantic import ValidationError

from app.schemas.activity import (
    ACTIVITY_STYLE_LABELS,
    ActivityStyle,
    activity_style_label,
    activity_style_prompt_listing,
)
from app.schemas.contest import CONTEST_CATEGORY_LABELS, ContestCategory, ContestField
from app.schemas.domain_doc import _DOMAIN_SOURCES, DOC_PATH, render_domain_doc
from app.schemas.role_codes import (
    CONTEST_FIELD_DOMAINS,
    EXPERIENCE_LEVEL_LABELS,
    FROZEN_ROLE_CODE_VALUES,
    ROLE_CODE_LABELS,
    ROLE_DOMAIN_LABELS,
    ROLE_DOMAINS,
    ExperienceLevel,
    RoleCode,
    RoleDomain,
    role_code_prompt_listing,
    role_label,
)
from app.schemas.team_extraction import TeamSoftFields
from app.schemas.user_intent import UserIntentFields


def test_every_role_code_has_a_label_and_a_domain() -> None:
    assert set(ROLE_CODE_LABELS) == set(RoleCode)
    assert set(ROLE_DOMAINS) == set(RoleCode)


def test_role_labels_are_unique() -> None:
    """라벨이 겹치면 같은 일을 두고 사용자·팀이 서로 다른 코드로 정규화될 수 있다."""
    labels = list(ROLE_CODE_LABELS.values())
    assert len(labels) == len(set(labels))


def test_frozen_role_code_values_still_exist() -> None:
    """BE 저장값·Supabase 클러스터 키가 이 문자열을 쓴다 — 이름을 바꾸거나 지우면 안 된다."""
    assert set(FROZEN_ROLE_CODE_VALUES) <= {role.value for role in RoleCode}


def test_every_domain_is_labeled_sourced_and_has_roles() -> None:
    assert set(ROLE_DOMAIN_LABELS) == set(RoleDomain)
    assert set(ROLE_DOMAINS.values()) == set(RoleDomain)
    # 도메인은 공모전 사이트 분류를 근거로 잡았다 — 근거 없는 도메인을 추가하지 않게 한다.
    assert set(_DOMAIN_SOURCES) == set(RoleDomain)


def test_non_it_domains_have_their_own_roles() -> None:
    """IT 역할만 있던 문제(2026-11-05) 재발 방지 — 예시로 요청받은 도메인의 대표 역할."""
    assert ROLE_DOMAINS[RoleCode.COOK_WESTERN] == RoleDomain.COOKING_FOOD
    assert ROLE_DOMAINS[RoleCode.COOK_CHINESE] == RoleDomain.COOKING_FOOD
    assert ROLE_DOMAINS[RoleCode.COOK_MENU_PLANNING] == RoleDomain.COOKING_FOOD
    assert ROLE_DOMAINS[RoleCode.LIT_NOVEL] == RoleDomain.LITERATURE
    assert ROLE_DOMAINS[RoleCode.POLICY_PROPOSAL] == RoleDomain.POLICY_SOCIETY
    assert ROLE_DOMAINS[RoleCode.ARCH_DESIGN] == RoleDomain.ARCHITECTURE
    assert ROLE_DOMAINS[RoleCode.MEDIA_JOURNALIST] == RoleDomain.MEDIA_CONTENT


def test_every_contest_field_points_to_role_domains() -> None:
    assert set(CONTEST_FIELD_DOMAINS) == set(ContestField)
    assert all(CONTEST_FIELD_DOMAINS[field] for field in ContestField)
    # 어느 분야에서도 보이지 않는 도메인이 있으면 FE가 그 역할들을 먼저 보여줄 일이 없다.
    reachable = {domain for domains in CONTEST_FIELD_DOMAINS.values() for domain in domains}
    assert reachable == set(RoleDomain)


def test_prompt_listing_lists_every_code_exactly_once_by_domain() -> None:
    listing = role_code_prompt_listing()
    codes = re.findall(r"([A-Za-z0-9_]+)\(", listing)
    assert sorted(codes) == sorted(role.value for role in RoleCode)
    assert len(listing.splitlines()) == len(RoleDomain)


def test_role_label_passes_non_code_values_through() -> None:
    assert role_label("COOK_WESTERN") == "양식 요리"
    assert role_label("백엔드 개발자") == "백엔드 개발자"


def test_activity_style_labels_cover_every_code() -> None:
    assert set(ACTIVITY_STYLE_LABELS) == set(ActivityStyle)
    assert activity_style_prompt_listing() == "ONLINE(온라인), OFFLINE(오프라인), HYBRID(온·오프라인 병행)"


def test_activity_style_label_passes_legacy_free_text_through() -> None:
    assert activity_style_label("ONLINE") == "온라인"
    assert activity_style_label("주 2회 오프라인") == "주 2회 오프라인"
    assert activity_style_label(None) is None


def test_activity_style_no_longer_accepts_free_text() -> None:
    with pytest.raises(ValidationError):
        UserIntentFields(activity_style="주 2회 오프라인")
    with pytest.raises(ValidationError):
        TeamSoftFields(activity_style="체계적인 협업")


def test_experience_and_category_labels_cover_every_code() -> None:
    assert set(EXPERIENCE_LEVEL_LABELS) == set(ExperienceLevel)
    assert set(CONTEST_CATEGORY_LABELS) == set(ContestCategory)


def test_prompt_examples_only_reference_existing_role_codes() -> None:
    """프롬프트 예시('양식 요리' → COOK_WESTERN)가 없는 코드를 가리키면 LLM이 그 코드를 못 고르고
    엉뚱한 코드로 정규화한다 — 역할 코드를 바꿀 때 프롬프트 예시도 같이 고치게 강제한다."""
    from app.core.prompts import load_prompt

    allowed = {role.value for role in RoleCode}
    code = r"[A-Za-z][A-Za-z0-9_]*"
    for name in ("user_intent_extraction", "team_soft_fields_extraction", "role_code_rules"):
        # "→ BE, FE"처럼 화살표 뒤에 코드가 여러 개 올 수 있다. 뒤따르는 코드는 줄 끝·쉼표·괄호
        # 앞에서만 인정한다("→ PM, IT 서비스 팀의 ..."의 IT는 코드가 아니라 문장이다).
        groups = re.findall(rf"→ ({code}(?:, {code}(?=,|\)|$))*)", load_prompt(name), re.MULTILINE)
        referenced = {item for group in groups for item in group.split(", ")}
        assert referenced, f"{name}: 예시를 못 찾았다(패턴이 바뀌었으면 이 테스트도 고칠 것)"
        assert referenced <= allowed, f"{name}: 없는 역할 코드 {sorted(referenced - allowed)}"


def test_both_extractors_share_the_role_rules() -> None:
    """사용자·팀이 같은 표현을 같은 코드로 정규화해야 역할 일치도가 맞는다."""
    from app.core.prompts import load_prompt
    from app.features.team_embedding import extraction as team_extraction
    from app.features.user_to_team import extraction as user_extraction

    rules = load_prompt("role_code_rules")
    assert rules in user_extraction._SYSTEM_PROMPT
    assert rules in team_extraction._SYSTEM_PROMPT


def test_domain_doc_is_in_sync_with_code() -> None:
    assert DOC_PATH.read_text(encoding="utf-8") == render_domain_doc(), (
        "docs/domain-enums.md가 코드와 다르다 — scripts/generate_domain_doc.py로 다시 생성할 것"
    )
