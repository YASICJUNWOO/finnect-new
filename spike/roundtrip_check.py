"""hwp → hwpx → hwp 왕복이 무엇을 잃는지 잰다. **버리는 코드다.**

`spike/hwp2hwpx_convert.py` 로 만든 `out/hwp-to-hwpx/*-보정.hwpx` 를
`hwpConverter` 가 `out/왕복-출력/` 에 되돌려 놓은 상태를 전제로 한다.

`uv run python spike/roundtrip_check.py`
"""

from __future__ import annotations

import difflib
from pathlib import Path

from finnect.attach import store
from finnect.attach.hwp import from_hwp
from finnect.forms import open_form

BACK = Path("out/왕복-출력")
SHAS = Path("/tmp/hwp-표본.txt")


def shape(path: str, ext: str) -> tuple[int, int] | None:
    try:
        cells = list(open_form(path, ext).cells())
    except Exception:  # noqa: BLE001 — 스파이크다
        return None
    return len({(c.anchor.section, c.anchor.table) for c in cells}), len(cells)


def main() -> None:
    shas = [s.strip() for s in SHAS.read_text().splitlines() if s.strip()]
    rows = []
    for sha in shas:
        back = BACK / f"{sha[:12]}-보정.hwp"
        if not back.exists():
            rows.append((sha[:12], "역변환 실패", None, None, None, None))
            continue

        src = store.abs_path(store.rel_path(sha))
        try:
            a, b = from_hwp(src), from_hwp(back)
        except Exception as e:  # noqa: BLE001
            rows.append((sha[:12], f"못 읽음 {type(e).__name__}", None, None, None, None))
            continue

        sa, sb = shape(str(src), "hwp"), shape(str(back), "hwp")
        la = [x.strip() for x in a.splitlines() if x.strip()]
        lb = [x.strip() for x in b.splitlines() if x.strip()]
        ratio = difflib.SequenceMatcher(None, la, lb).ratio()
        lost = [x for x in la if x not in lb]
        rows.append((sha[:12], "", sa, sb, ratio, len(lost)))

    print(f"{'파일':14}{'표·셀 (원본→왕복)':>26}{'줄 유사도':>10}{'사라진 줄':>10}")
    ok = same_shape = 0
    ratios = []
    total_lost = 0
    for sha, err, sa, sb, ratio, lost in rows:
        if err:
            print(f"{sha:14}{err:>26}")
            continue
        ok += 1
        ratios.append(ratio)
        total_lost += lost
        fmt = lambda s: f"{s[0]}·{s[1]}" if s else "안 열림"  # noqa: E731
        mark = "" if sa == sb else ("  ←어댑터가 못 엶" if sb is None else "  ←구조 다름")
        same_shape += int(sa == sb)
        print(
            f"{sha:14}{f'{fmt(sa)} → {fmt(sb)}':>26}"
            f"{ratio * 100:>9.1f}%{lost:>10}{mark}"
        )

    print(
        f"\n왕복 {ok}/{len(rows)} · 구조 같음 {same_shape}/{ok}"
        f" · 평균 줄 유사도 {100 * sum(ratios) / max(1, len(ratios)):.1f}%"
        f" · 사라진 줄 합계 {total_lost}"
    )


if __name__ == "__main__":
    main()
