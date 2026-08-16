"""수집 CLI.

    uv run python -m finnect.ingest --source bizinfo
    uv run python -m finnect.ingest --source kstartup
    uv run python -m finnect.ingest --source kstartup --only-open   # 모집중 274건만

버튼·스케줄러·잡 큐는 붙이지 않는다(plan/06 '안 하는 것').
"""

from __future__ import annotations

import argparse
import sys

import httpx

from finnect.db import session_scope
from finnect.ingest.bizinfo import BizinfoAdapter
from finnect.ingest.envelope import EnvelopeError
from finnect.ingest.kstartup import KstartupAdapter
from finnect.ingest.runner import run
from finnect.models import Source

UA = "finnect-ingest/0.1 (+https://github.com/joonoo3/finnect-new)"


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
    args = p.parse_args(argv)

    targets = (
        [str(Source.BIZINFO), str(Source.KSTARTUP)] if args.source == "all" else [args.source]
    )

    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True) as client:
        for name in targets:
            adapter = (
                BizinfoAdapter(client)
                if name == str(Source.BIZINFO)
                else KstartupAdapter(client, only_open=args.only_open)
            )
            try:
                with session_scope() as session:
                    report = run(adapter, session)
            except EnvelopeError as e:
                # 두 API 모두 실패를 HTTP 200 으로 준다. 0건 성공으로 넘기지 않는다.
                print(f"[{name}] 봉투 검증 실패 — {e}", file=sys.stderr)
                return 2
            print(report.render())

    return 0


if __name__ == "__main__":
    sys.exit(main())
