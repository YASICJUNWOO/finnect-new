"""수집 CLI.

    uv run python -m finnect.ingest --source bizinfo
    uv run python -m finnect.ingest --source kstartup
    uv run python -m finnect.ingest --source kstartup --only-open   # 모집중 274건만
    uv run python -m finnect.ingest --source kstartup --limit 500   # 맛보기 500건

관리 화면의 수집 버튼과 **같은 경로**(`service.execute`)를 쓴다. 실행 기록도 같은 표에
남으므로 화면에서 CLI 실행이 보인다. 스케줄러와 잡 큐는 여전히 안 붙인다(plan/06 '안 하는 것').
"""

from __future__ import annotations

import argparse
import sys

from finnect.ingest.envelope import EnvelopeError
from finnect.ingest.service import execute
from finnect.models import Source


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.ingest", description="공고 목록 수집")
    p.add_argument(
        "--source",
        required=True,
        choices=[str(Source.BIZINFO), str(Source.KSTARTUP), "all"],
    )
    p.add_argument(
        "--only-open",
        action="store_true",
        help="K-Startup 모집중만. 검증된 서버측 필터(rcrt_prgs_yn=Y)를 쓴다",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="N건만 받는다(맛보기). 안 주면 전량. 잘렸다는 사실은 실행 기록에 남는다",
    )
    args = p.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        p.error("--limit 은 1 이상이어야 한다")

    targets = (
        [str(Source.BIZINFO), str(Source.KSTARTUP)] if args.source == "all" else [args.source]
    )

    for name in targets:
        try:
            report = execute(name, only_open=args.only_open, limit=args.limit, trigger="cli")
        except EnvelopeError as e:
            # 두 API 모두 실패를 HTTP 200 으로 준다. 0건 성공으로 넘기지 않는다.
            print(f"[{name}] 봉투 검증 실패 — {e}", file=sys.stderr)
            return 2
        print(report.render())

    return 0


if __name__ == "__main__":
    sys.exit(main())
