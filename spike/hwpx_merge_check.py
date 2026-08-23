"""세로 병합에서 값이 어긋나는지 잰다. **버리는 코드다.**

`_fold_spans` 가 **가로 병합만** 접는다. 세로로 병합된 칸은 행마다 되풀이되므로
라벨쌍이 행 수만큼 생기고, 값 자리 여럿이 **같은 물리 셀**을 가리킨다. 뒤에 쓴
값이 앞의 것을 덮으면 사용자는 엉뚱한 칸에 든 글을 보게 된다.

물어보는 것은 하나다. **이것이 변환본만의 일인가, hwpx 경로 전반의 일인가.**

`uv run python spike/hwpx_merge_check.py <파일.hwpx> [파일 …]`
"""

from __future__ import annotations

import sys
from pathlib import Path

from finnect.forms import open_form
from finnect.forms.base import _fold_spans


def value_slots(path: str) -> tuple[object, list]:
    """인접 규칙으로 고른 `(라벨, 값 칸)`. **빈칸 조건을 뺀 것이다.**"""
    form = open_form(path, "hwpx")
    by_row: dict[tuple[int, int, int], list] = {}
    for c in form.cells():
        by_row.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)
    out = []
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        run = _fold_spans(row)
        for i, c in enumerate(run[:-1]):
            if c.blank:
                continue
            out.append((c.text, run[i + 1].anchor))
    return form, out


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        raise SystemExit("hwpx 파일을 하나 이상 달라")

    tmp = Path("/tmp/병합확인.hwpx")
    tot_slots = tot_clash = 0
    for p in paths:
        try:
            form, slots = value_slots(p)
        except Exception as e:  # noqa: BLE001 — 스파이크다
            print(f"{Path(p).name:26} 못 열었다 — {type(e).__name__}")
            continue

        targets = slots[:40]
        for i, (_, a) in enumerate(targets):
            form.fill(a, f"값{i}")
        form.save(str(tmp))

        got = {str(c.anchor): c.text.strip() for c in open_form(str(tmp), "hwpx").cells()}
        clash = [
            (str(a), f"값{i}", got.get(str(a), "(없음)"))
            for i, (_, a) in enumerate(targets)
            if got.get(str(a)) != f"값{i}"
        ]
        tot_slots += len(targets)
        tot_clash += len(clash)
        mark = "" if not clash else f"  ← 어긋남 {len(clash)}"
        print(f"{Path(p).name:26} 값 자리 {len(targets):>3} · 살아남음 {len(targets) - len(clash):>3}{mark}")
        for a, want, real in clash[:3]:
            print(f"     {a:12} 기대 {want:<5} 실제 {real[:20]!r}")

    if tot_slots:
        print(
            f"\n합계 값 자리 {tot_slots} · 어긋남 {tot_clash}"
            f" ({100 * tot_clash / tot_slots:.1f}%)"
        )


if __name__ == "__main__":
    main()
