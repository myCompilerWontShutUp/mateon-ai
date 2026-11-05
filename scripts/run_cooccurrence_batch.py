"""item-to-item CF 오프라인 배치 — 공모전 동시발생 행렬을 계산해 Supabase에 기록한다.

`run_cluster_weight_batch.py`와 완전히 같은 운영 방식이다: AI 서버 프로세스 안에서 돌지 않고
사람이 주기적으로 로컬에서 실행하며, 라이브 서버는 결과를 읽기만 한다.

**입력은 BE가 소유한 상호작용 이력이다.** AI 서버는 이 데이터를 저장하지 않으므로, BE의 내부
엔드포인트(`GET /api/internal/interactions`)에서 받아오거나 JSON 덤프 파일로 받는다. 파일 입력은
`--source-kind`로 실제 덤프(real)인지 합성(synthetic)인지 밝혀야 한다(API 입력은 생략하면 real). 합성
데이터는 계산 결과만 출력할 뿐 운영 표에 기록하지 않는다(2026-11-05 — 합성 데모 654행이 운영 표에
활성으로 남아 있던 일의 재발 방지). 한 번 실행 = 한 버전(스냅샷)이고, 계산 결과가 비면 현재 활성
버전을 그대로 둔다.

사용 예(입력·전환 플래그는 하나만 쓸 수 있다):
    uv run python scripts/run_cooccurrence_batch.py --interactions data/synthetic_interactions.json --source-kind synthetic
    uv run python scripts/run_cooccurrence_batch.py --api-url https://be.example.com/api/internal/interactions
    uv run python scripts/run_cooccurrence_batch.py --api-url ... --dry-run
    uv run python scripts/run_cooccurrence_batch.py --activate-version 3   # 버전 3으로 롤백
    uv run python scripts/run_cooccurrence_batch.py --deactivate-all       # CF 끄기
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949 대응
sys.stderr.reconfigure(encoding="utf-8")  # argparse 오류 메시지도 같은 이유

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.scoring.cooccurrence import build_cooccurrence  # noqa: E402
from app.scoring.cooccurrence_store import activate_version, deactivate_all, write_cooccurrence  # noqa: E402


def _load_from_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_from_api(url: str) -> list[dict]:
    """BE의 내부 엔드포인트에서 상호작용 이력을 받아온다(배치 전용, 라이브 경로 아님)."""
    settings = get_settings()
    response = httpx.get(
        url, headers={"X-Internal-Secret": settings.internal_shared_secret}, timeout=60.0
    )
    response.raise_for_status()
    payload = response.json()
    # BE가 {"data": [...]} 형태로 감싸 보낼 수도 있어 둘 다 받아준다.
    return payload["data"] if isinstance(payload, dict) else payload


def _summarize(interactions: list[dict], cooccurrence: dict[int, dict[int, float]]) -> None:
    users = {row["user_id"] for row in interactions}
    events = {row["event_id"] for row in interactions}
    per_user = Counter(row["user_id"] for row in interactions)
    multi_event_users = sum(1 for count in per_user.values() if count >= 2)
    pair_count = sum(len(neighbors) for neighbors in cooccurrence.values()) // 2

    print(f"  상호작용 {len(interactions)}건 / 사용자 {len(users)}명 / 공모전 {len(events)}개")
    print(f"  2개 이상 상호작용한 사용자: {multi_event_users}명 (동시발생에 실제로 기여하는 모집단)")
    print(f"  동시발생 쌍: {pair_count}개")
    if pair_count == 0:
        print("  ⚠ 쌍이 하나도 없다 — 아직 CF를 켤 만큼 데이터가 겹치지 않았다.")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--interactions", type=Path, help="상호작용 이력 JSON 파일 경로")
    mode.add_argument("--api-url", help="BE 내부 엔드포인트 URL")
    mode.add_argument("--activate-version", type=int, help="이 버전만 켜고 나머지는 끈다(롤백)")
    mode.add_argument("--deactivate-all", action="store_true", help="활성 동시발생 행을 전부 끈다(CF 끄기)")
    parser.add_argument(
        "--source-kind",
        choices=["real", "synthetic"],
        help="입력이 실제 BE 데이터인지 합성 데이터인지(파일 입력이면 필수, API 입력은 생략하면 real)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Supabase에 쓰지 않고 계산 결과만 출력"
    )
    args = parser.parse_args()

    if args.activate_version is not None or args.deactivate_all:
        # 전환은 운영 표를 바로 바꾼다 — "기록하지 않음"을 뜻하는 플래그와 섞이면 거부한다.
        if args.dry_run or args.source_kind:
            parser.error("--activate-version/--deactivate-all은 --dry-run, --source-kind와 함께 쓸 수 없다")
        if args.deactivate_all:
            print(f"event_cooccurrence 활성 행 {deactivate_all()}개를 껐다 — CF 신호 없이 동작한다.")
        else:
            activate_version(args.activate_version)
            print(f"event_cooccurrence 버전 {args.activate_version}로 전환 완료")
        return

    # 합성 데이터가 운영 표에 들어가 라이브 CF 신호로 읽히던 사고(2026-11-05 정리) 재발 방지 —
    # 파일 입력은 출처를 반드시 밝히게 하고, 합성 데이터는 계산 결과만 보여주고 기록하지 않는다.
    # API 입력도 --source-kind synthetic이면 따른다(스테이징 BE의 데모 데이터 등).
    if args.interactions:
        if args.source_kind is None:
            parser.error("--interactions를 쓰면 --source-kind real|synthetic을 함께 지정해야 한다")
        interactions = _load_from_file(args.interactions)
    else:
        interactions = _load_from_api(args.api_url)
    kind = args.source_kind or "real"

    cooccurrence = build_cooccurrence(interactions)
    _summarize(interactions, cooccurrence)

    if kind == "synthetic":
        print("합성 데이터 — 계산 결과만 보여주고 운영 표에는 기록하지 않는다.")
        return
    if args.dry_run:
        print("dry-run — Supabase에 기록하지 않는다.")
        return
    if not cooccurrence:
        print("기록할 동시발생 쌍이 없다 — 현재 활성 버전을 그대로 둔다.")
        return

    source = f"offline_batch_real_{date.today().isoformat()}"
    version = write_cooccurrence(cooccurrence, source=source)
    print(f"event_cooccurrence 버전 {version} 기록·전환 완료 (source={source}, 이전 버전은 비활성화만 됨)")


if __name__ == "__main__":
    main()
