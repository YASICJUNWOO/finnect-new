"""낼 서류와 작성 항목 추출 CLI.

    uv run python -m finnect.extract --limit 40   # 맛보기
    uv run python -m finnect.extract              # 전량
    uv run python -m finnect.extract --redo       # 규칙을 고쳤을 때
    uv run python -m finnect.extract --report     # 집계만
    uv run python -m finnect.extract --classify 40 --dry   # 판정만 찍어 본다. 안 쓴다
    uv run python -m finnect.extract --classify            # unknown 에 종류를 붙인다 (LLM)
    uv run python -m finnect.extract --classify 30 --title-like 계획   # 표적을 좁혀 30개만

**`--classify` 만 네트워크를 쓴다**(ADR-0037). 나머지는 `finnect.attach` 가
뽑아 둔 텍스트만 읽는다.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from finnect import trace
from finnect.db import SessionFactory
from finnect.extract import service
from finnect.models import Document, DocumentItem


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.extract", description="낼 서류와 작성 항목")
    p.add_argument("--limit", type=int, default=None, metavar="N", help="N개 파일만(맛보기)")
    p.add_argument(
        "--redo",
        action="store_true",
        help="이미 한 것도 다시 판정한다. **그 파일에 쓴 초안이 지워진다**(FK CASCADE)",
    )
    p.add_argument("--report", action="store_true", help="집계만 찍는다")
    p.add_argument(
        "--classify", type=int, nargs="?", const=0, default=None, metavar="N",
        help="unknown 구간에 종류를 붙인다. N 을 주면 N개만 (LLM · ADR-0037)",
    )
    p.add_argument("--dry", action="store_true", help="--classify 와 함께. 찍기만 하고 안 쓴다")
    p.add_argument(
        "--title-like", metavar="말", default=None,
        help="구간 표지에 이 말이 든 것만 판정한다. **표본 고르기이고 판정 규칙이 아니다**",
    )
    args = p.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        p.error("--limit 은 1 이상이어야 한다")
    if args.dry and args.classify is None:
        p.error("--dry 는 --classify 와 같이 쓴다")

    if args.classify is not None:
        n = args.classify or None
        if args.dry:
            print("[판정 — 안 쓴다]")
        print(
            service.classify_unknown(
                limit=n, redo=args.redo, dry=args.dry, title_like=args.title_like
            ).line()
        )
        print()
        with SessionFactory() as s:
            print(render(s))
        if line := trace.flush():
            print(line)
        return 0

    if not args.report:
        print(service.run(limit=args.limit, redo=args.redo).line())
        print()

    with SessionFactory() as s:
        print(render(s))
    # **데몬 스레드라 그냥 끝나면 큐에 남은 추적이 사라진다**(trace.py)
    if line := trace.flush():
        print(line)
    return 0


def render(s) -> str:  # noqa: ANN001 — Session
    kinds = s.execute(
        select(Document.kind, func.count()).group_by(Document.kind).order_by(func.count().desc())
    ).all()
    docs = s.scalar(select(func.count()).select_from(Document)) or 0
    items = s.scalar(select(func.count()).select_from(DocumentItem)) or 0
    files = s.scalar(select(func.count(func.distinct(Document.sha256)))) or 0

    lines = [
        "[추출 현황]",
        f"  파일 {files:,} · 구간 {docs:,} · 항목 {items:,}",
        "",
        "  구간 종류",
    ]
    for kind, n in kinds:
        # unknown 은 '아직 안 갈랐다' 다. T-0036 이 채운다 — 실패가 아니다.
        note = "  ← T-0036(LLM) 이 채운다" if kind == "unknown" else ""
        lines.append(f"    {kind:<12} {n:>6,}{note}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
