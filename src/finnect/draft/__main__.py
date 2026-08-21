"""초안 집필 CLI (plan/16).

    uv run python -m finnect.draft --read-forms 20     # 양식 20개를 읽는다 (T-0063)
    uv run python -m finnect.draft --read-forms        # 전량
    uv run python -m finnect.draft --company c_dasiro --notice bizinfo:PBLN-000
    uv run python -m finnect.draft --company c_dasiro --notice bizinfo:PBLN-000 --workers 1
    uv run python -m finnect.draft --report            # 현황만

**둘 다 LLM 을 부른다**(ADR-0037). 키가 없으면 무엇이 없는지 말하고 멈춘다.
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from finnect import trace
from finnect.config import settings
from finnect.db import SessionFactory
from finnect.draft import service
from finnect.models import Document, DocumentItem, Draft, DraftItem, ItemNeed, ItemOverlap


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.draft", description="초안 집필")
    p.add_argument(
        "--read-forms", type=int, nargs="?", const=0, default=None, metavar="N",
        help="서술형 양식을 읽어 필요한 자리를 정한다. N 을 주면 N개만 (T-0063)",
    )
    p.add_argument("--company", metavar="ID", help="회사 식별자")
    p.add_argument("--notice", metavar="출처:공고번호", help="예: bizinfo:PBLN-000")
    p.add_argument("--redo", action="store_true", help="이미 한 것도 다시 한다")
    p.add_argument(
        "--workers", type=int, default=None, metavar="N",
        help=f"항목을 몇 개씩 동시에 쓰나. 기본 {settings.draft_workers} (T-0069)",
    )
    p.add_argument("--report", action="store_true", help="현황만 찍는다")
    args = p.parse_args(argv)

    if args.read_forms is not None:
        print(service.read_forms(limit=args.read_forms or None, redo=args.redo).line())
        print()
    elif args.company or args.notice:
        if not (args.company and args.notice):
            p.error("--company 와 --notice 를 같이 준다")
        if ":" not in args.notice:
            p.error("--notice 는 `출처:공고번호` 다. 예: bizinfo:PBLN-000")
        source, external_id = args.notice.split(":", 1)
        print(
            service.build_draft(
                args.company, source, external_id, redo=args.redo, workers=args.workers
            ).line()
        )
        print()
    elif not args.report:
        p.error("--read-forms 또는 --company 와 --notice, 아니면 --report")

    with SessionFactory() as s:
        print(render(s))
    # **데몬 스레드라 그냥 끝나면 큐에 남은 추적이 사라진다**(trace.py)
    if line := trace.flush():
        print(line)
    return 0


def render(s) -> str:  # noqa: ANN001 — Session
    narrative = s.scalar(
        select(func.count()).select_from(Document).where(Document.kind == "narrative")
    ) or 0
    items = s.scalar(
        select(func.count())
        .select_from(DocumentItem)
        .where(DocumentItem.input_kind == "narrative")
    ) or 0
    read = s.scalar(
        select(func.count(func.distinct(DocumentItem.document_id)))
        .where(DocumentItem.needs_decided_by.is_not(None))
    ) or 0
    needs = s.scalar(select(func.count()).select_from(ItemNeed)) or 0
    overlaps = s.scalar(select(func.count()).select_from(ItemOverlap)) or 0
    drafts = s.scalar(select(func.count()).select_from(Draft)) or 0
    rows = s.execute(
        select(DraftItem.status, func.count()).group_by(DraftItem.status)
    ).all()

    lines = [
        "[집필 현황]",
        f"  서술형 양식 {narrative:,} · 작성 항목 {items:,}",
        f"  읽은 양식 {read:,} · 필요한 자리 {needs:,} · 겹침 쌍 {overlaps:,}",
        f"  초안 {drafts:,}",
    ]
    if narrative == 0:
        # **없는 것이 정상이 아니다.** T-0036 이 돌아야 생긴다
        lines.append("    ← 서술형이 0건이다. `finnect.extract --classify` 가 먼저다")
    for status, n in sorted(rows, key=lambda x: -x[1]):
        lines.append(f"    {status:<10} {n:>6,}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
