"""첨부 내려받기와 해독 CLI.

    uv run python -m finnect.attach --limit 40      # 맛보기
    uv run python -m finnect.attach                 # 전량
    uv run python -m finnect.attach --redo          # 파서를 고쳤을 때. 파일은 다시 안 받는다
    uv run python -m finnect.attach --report        # 집계만. 아무것도 안 받는다

스케줄러도 잡 큐도 안 붙인다(plan/07 '안 하는 것'). 사람이 부를 때만 돈다.
"""

from __future__ import annotations

import argparse
import sys

from finnect.attach import kstartup, service
from finnect.db import SessionFactory
from finnect.models import Source


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.attach", description="첨부 내려받기와 해독")
    p.add_argument("--source", choices=[str(Source.BIZINFO), str(Source.KSTARTUP)], default=None)
    p.add_argument(
        "--limit", type=int, default=None, metavar="N", help="N건만 처리한다(맛보기)"
    )
    p.add_argument(
        "--redo",
        action="store_true",
        help="이미 처리한 것도 다시 해독한다. 디스크에 있는 파일은 다시 안 받는다",
    )
    p.add_argument(
        "--ocr",
        action="store_true",
        help="텍스트가 0자인 스캔본만 OCR 로 다시 본다(ADR-0030). 새로 받지 않는다",
    )
    p.add_argument(
        "--scrape-kstartup",
        action="store_true",
        help="K-Startup 상세 페이지에서 첨부 목록을 긁는다(plan/13). **파일은 안 받는다**",
    )
    p.add_argument("--report", action="store_true", help="집계만 찍는다")
    args = p.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        p.error("--limit 은 1 이상이어야 한다")

    if args.scrape_kstartup:
        r = kstartup.scrape(
            limit=args.limit,
            redo=args.redo,
            on_progress=lambda x: print(
                f"  … {x.done}/{x.total}건 · 첨부 {x.attachments}개 · "
                f"{x.seconds / 60:.1f}분",
                flush=True,
            ),
        )
        print()
        print(r.render())
        with SessionFactory() as s:
            c = kstartup.coverage(s)
            print(
                f"\n[K-Startup 첨부] 공고 {c['notices']:,}건 중 "
                f"{c['scraped']:,}건에 첨부 {c['attachments']:,}개"
            )
        return 0

    if args.ocr:
        r = service.ocr_pass(
            limit=args.limit,
            on_progress=lambda x: print(
                f"  … {x.done}/{x.total}건 · {x.pages}쪽 · "
                f"{x.seconds / 60:.1f}분 · 글자 나옴 {x.ok}",
                flush=True,
            ),
        )
        print()
        print(r.render())
        print()
    elif not args.report:
        report = service.run(limit=args.limit, redo=args.redo, source=args.source)
        print(report.render())
        print()

    with SessionFactory() as s:
        print(render_coverage(service.coverage(s)))
    return 0


def render_coverage(c: dict) -> str:
    lines = [
        "[해독 현황]",
        f"  첨부 {c['listed']:,}건 · URL {c['urls']:,} · 상태 행 {c['files']:,}",
    ]
    # 조용한 누락. 0이 아니면 아래 숫자를 믿으면 안 된다.
    missing = c["unaccounted"]
    lines.append(
        "  ✓ 조용한 누락 0건" if missing == 0 else f"  ⚠ 상태가 없는 첨부 {missing:,}건"
    )

    lines.append("")
    lines.append("  내려받기")
    for status, n in c["fetch"]:
        lines.append(f"    {status:<12} {n:>6,}")

    lines.append("")
    lines.append("  해독")
    for status, n in c["parse"]:
        lines.append(f"    {str(status or '미시도'):<12} {n:>6,}")

    lines.append("")
    lines.append(f"  {'포맷':<8} {'상태':<12} {'건수':>6}  평균 글자")
    for r in c["by_ext"]:
        chars = f"{r['avg_chars']:,}" if r["avg_chars"] else "—"
        lines.append(f"    {str(r['ext']):<8} {r['status']:<12} {r['count']:>6,}  {chars:>9}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
