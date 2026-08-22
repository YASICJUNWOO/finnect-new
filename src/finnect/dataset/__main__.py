"""데이터셋 CLI — 공고 코퍼스를 뜨고, 지우고, 솎는다.

    uv run python -m finnect.dataset --report                     현황만
    uv run python -m finnect.dataset --dump out/공고-백업.jsonl    되돌릴 수 있게 뜬다
    uv run python -m finnect.dataset --restore out/공고-백업.jsonl 되돌린다
    uv run python -m finnect.dataset --purge                      지울 것을 센다
    uv run python -m finnect.dataset --purge --yes                지운다
    uv run python -m finnect.dataset --prune 목록.txt --source bizinfo
    uv run python -m finnect.dataset --prune 목록.txt --source kstartup --sample 3 --yes

**수집을 안 한다.** 받는 일은 `finnect.ingest` 가 전량으로 하고, 무엇을 남길지는
`notice-filter/` 가 목록 파일로 정한다. 절차는 docs/dataset.md 에 있다.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from finnect.dataset import service, store
from finnect.dataset.tables import NOTICE_TABLES


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.dataset", description="공고 코퍼스 관리")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true", help="현황만 찍는다")
    g.add_argument("--dump", metavar="파일", help="공고·첨부를 JSONL 로 뜬다")
    g.add_argument("--restore", metavar="파일", help="백업을 되돌린다. 대상 표를 먼저 비운다")
    g.add_argument("--purge", action="store_true", help="공고·첨부를 통째로 비운다")
    g.add_argument("--prune", metavar="목록", help="목록에 없는 공고를 지운다")

    p.add_argument("--source", choices=sorted(NOTICE_TABLES), help="--prune 의 대상")
    p.add_argument(
        "--sample",
        type=int,
        default=1,
        metavar="N",
        help="번호를 N 으로 나눠 나머지 0 만 남긴다. 1 이면 전부. 멱등하다",
    )
    p.add_argument("--yes", action="store_true", help="실제로 지운다. 없으면 미리보기다")
    args = p.parse_args(argv)

    if args.sample < 1:
        p.error("--sample 은 1 이상이어야 한다")
    if args.prune and not args.source:
        p.error(
            "--prune 에는 --source 가 필요하다. "
            "두 출처의 공고번호가 같은 자릿수라 섞으면 틀린다"
        )

    if args.report:
        print("[현황]")
        print(service.counts().render())
        return 0

    if args.dump:
        print(store.dump(pathlib.Path(args.dump)).render())
        return 0

    if args.restore:
        path = pathlib.Path(args.restore)
        if not path.exists():
            print(f"백업이 없다 — {path}", file=sys.stderr)
            return 2
        print(store.restore(path).render())
        return 0

    if args.purge:
        print(purge_warning() if not args.yes else "", end="")
        print(service.purge(apply=args.yes).render())
        return 0

    return _prune(p, args)


def _prune(p: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    path = pathlib.Path(args.prune)
    if not path.exists():
        print(f"목록 파일이 없다 — {path}", file=sys.stderr)
        return 2
    try:
        keep = service.read_list(path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(f"[목록] {path} 에서 공고번호 {len(keep):,}개")
    rep = service.prune(args.source, keep, samples=args.sample, apply=args.yes)
    print(rep.render())
    return 0


def purge_warning() -> str:
    return (
        "기업마당 공고는 마감되면 API 에서 사라진다. 재수집으로 복구되지 않는다.\n"
        "지우기 전에 --dump 로 떠 둘 것.\n\n"
    )


if __name__ == "__main__":
    sys.exit(main())
