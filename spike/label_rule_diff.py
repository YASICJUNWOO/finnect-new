"""옛 규칙(오른쪽 첫 빈 칸)과 새 규칙(바로 오른쪽 칸)의 라벨쌍을 코퍼스로 비교한다.

**버리는 코드다**(`spike/`). plan/24 ② 의 대가를 숫자로 보려고 쓴 것이다.
"""

from __future__ import annotations

import sys
from collections import Counter

from sqlalchemy import func, select

from finnect.attach import store
from finnect.db import SessionFactory
from finnect.forms import SUPPORTED, label_targets, open_form
from finnect.forms.base import Cell
from finnect.models import AttachmentFile, Document


def old_targets(cells: list[Cell]) -> list[tuple[str, object]]:
    """옛 규칙 그대로. 오른쪽으로 훑어 **첫 빈 칸**을 잡는다."""
    by_row: dict[tuple[int, int, int], list[Cell]] = {}
    for c in cells:
        by_row.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)
    out: list[tuple[str, object]] = []
    seen: set[tuple[str, object]] = set()
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        for i, c in enumerate(row):
            if c.blank:
                continue
            nxt = next((n for n in row[i + 1 :] if n.blank), None)
            if nxt is None:
                continue
            pair = (c.text, nxt.anchor)
            if pair in seen:
                continue
            seen.add(pair)
            out.append(pair)
    return out


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    with SessionFactory() as s:
        rows = s.execute(
            select(Document.sha256, AttachmentFile.detected_ext, func.count(Document.id))
            .join(AttachmentFile, AttachmentFile.sha256 == Document.sha256)
            .where(AttachmentFile.detected_ext.in_(sorted(SUPPORTED)))
            .group_by(Document.sha256, AttachmentFile.detected_ext)
            .limit(limit)
        ).all()

    tally = Counter()
    moved_examples: list[str] = []
    for sha, ext, _ in rows:
        try:
            form = open_form(str(store.abs_path(store.rel_path(sha))), ext)
            cells = form.cells()
        except Exception as e:  # noqa: BLE001 — 실측 스크립트다
            tally["열지 못함"] += 1
            print(f"  ! {sha[:8]} {ext}: {type(e).__name__}", flush=True)
            continue

        old = {label: a for label, a in old_targets(cells)}
        new = {label: a for label, a in label_targets(cells)}
        tally["파일"] += 1
        tally[f"파일:{ext}"] += 1
        tally["옛 쌍"] += len(old)
        tally["새 쌍"] += len(new)

        for label, a in old.items():
            if label not in new:
                tally["잃음"] += 1
            elif new[label] != a:
                tally["좌표가 옮겨감"] += 1
                if len(moved_examples) < 12:
                    moved_examples.append(f"{sha[:8]} {ext} {label[:18]!r}: {a} → {new[label]}")
        for label in new:
            if label not in old:
                tally["새로 생김"] += 1

    print()
    for k in sorted(tally):
        print(f"{k:16} {tally[k]:,}")
    print()
    print("좌표가 옮겨간 예 (옛 규칙이 건너뛴 자리다):")
    for line in moved_examples:
        print("  ", line)


if __name__ == "__main__":
    main()
