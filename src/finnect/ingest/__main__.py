"""수집 CLI.

    uv run python -m finnect.ingest --source bizinfo    # 기본이 필터링된 수집이다
    uv run python -m finnect.ingest --source kstartup   # K-Startup 모집중만 (요청 1회)
    uv run python -m finnect.ingest --source all        # 둘 다
    uv run python -m finnect.ingest --source bizinfo --full     # 전량. 정본 절차용(docs/dataset.md)
    uv run python -m finnect.ingest --source kstartup --limit 500  # 맛보기 500건

**기본값이 2026-08-24 부터 필터링된 수집이다.** K-Startup 은 검증된 서버측 필터
(`cond[rcrt_prgs_yn::EQ]=Y` → 요청 1회 · 268건, 2026-08-24)로 모집중만 받고, 기업마당은
전량을 받되 계획서로 심사하지 않는 중분류 스무 개를 적재 직전에 뺀다(`ingest.mlsfc`).
첨부 해독·`--classify` 비용이 저장한 공고 수에 비례하는데, 마감 공고는 화면에 안 뜨고
그 중분류는 애초에 계획서를 안 받는다 — 근거는
`docs/adr/evidence/2026-08-16-목록-API-실측.md`.

**K-Startup 은 모집중만 받을 때 상세 페이지까지 이 명령 안에서 같이 긁는다**(2026-08-24).
배치가 300건 안팎이라 실측 0.38초/건 기준 2분 안이고, 끝나면 `attachment` 행까지 있다 —
따로 `attach --scrape-kstartup` 을 또 돌릴 필요가 없다. `--full` 에는 안 걸린다(전량이면
몇 시간짜리라 여기서 조용히 같이 돌면 안 된다). 이 경우는 여전히 손으로
`attach --scrape-kstartup` 을 돌린다(`docs/dataset.md`).

**`--full` 이 위 필터와 상세 긁기를 전부 끄고 옛 전량 동작으로 되돌린다.** `docs/dataset.md`
의 정본 절차(재수집·배포 DB 전량 동기화)가 이것을 쓴다. **필터링된 것이 진짜 모집단은
아니다** — K-Startup 은 274건 중 74건(27%)이 수집 뒤 며칠 새 마감됐다(플래그가 스냅샷이라
썩는다).

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
        "--full",
        action="store_true",
        help="필터를 안 쓴다. K-Startup 전량 · 기업마당 중분류 안 거름 (docs/dataset.md 정본 절차)",
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
            report = execute(
                name,
                only_open=not args.full,
                limit=args.limit,
                skip_mlsfc=not args.full,
                trigger="cli",
            )
        except EnvelopeError as e:
            # 두 API 모두 실패를 HTTP 200 으로 준다. 0건 성공으로 넘기지 않는다.
            print(f"[{name}] 봉투 검증 실패 — {e}", file=sys.stderr)
            return 2
        print(report.render())

    return 0


if __name__ == "__main__":
    sys.exit(main())
