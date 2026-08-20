"""맞는 공고 고르기 CLI (plan/17).

    uv run python -m finnect.match --normalize 40 --dry   # ① 을 찍어만 본다 (LLM)
    uv run python -m finnect.match --normalize            # ① 열린 공고 전량 (LLM)
    uv run python -m finnect.match --company c_dasiro     # ②~⑤ · LLM 0회
    uv run python -m finnect.match --company c_dasiro --only 후보.txt
    uv run python -m finnect.match --report               # 퍼널만

**`--normalize` 만 LLM 을 부른다**(ADR-0037). 키가 없으면 무엇이 없는지 말하고 멈춘다.
`--company` 는 코드만 돌아서 키 없이도 된다 — 대신 정규화가 0건이면 전부
`확인 필요` 로 남고 추천이 빈다.
"""

from __future__ import annotations

import argparse
import pathlib

from finnect.match import service


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.match", description="맞는 공고 고르기")
    p.add_argument(
        "--normalize", type=int, nargs="?", const=0, default=None, metavar="N",
        help="공고를 정규화한다. N 을 주면 N건만 (T-0070 · LLM)",
    )
    p.add_argument("--company", metavar="ID", help="회사 식별자")
    p.add_argument(
        "--only", metavar="파일",
        help="후보를 이 목록으로 좁힌다. 한 줄에 공고번호 하나. "
             "고르는 규칙은 notice-filter/ 에 따로 산다",
    )
    p.add_argument("--redo", action="store_true", help="본문이 그대로여도 다시 뽑는다")
    p.add_argument("--dry", action="store_true", help="찍어만 보고 저장하지 않는다")
    p.add_argument(
        "--workers", type=int, default=None, metavar="N",
        help="공고를 몇 개씩 동시에 정규화하나. 기본은 설정값 (T-0070)",
    )
    p.add_argument("--report", action="store_true", help="퍼널만 찍는다")
    args = p.parse_args(argv)

    only = None
    if args.only:
        lines = pathlib.Path(args.only).read_text(encoding="utf-8").splitlines()
        only = {ln.strip() for ln in lines if ln.strip()}
        print(f"[목록] {args.only} 에서 공고번호 {len(only):,}개")

    if args.normalize is not None:
        rep = service.normalize(
            limit=args.normalize or None, redo=args.redo, dry=args.dry, only=only,
            workers=args.workers,
        )
        print(rep.line())
        print()
    elif args.company:
        rep = service.run(args.company, only=only, save=not args.dry)
        print(rep.line())
        print()
    elif not args.report:
        p.error("--normalize · --company · --report 중 하나를 준다")

    print(service.report())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
