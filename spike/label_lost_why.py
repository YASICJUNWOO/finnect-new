"""새 규칙이 잃은 쌍의 **중간 칸**이 무엇이었는지 센다.

옛 규칙은 라벨과 빈 칸 사이를 건너뛰었다. 그 사이에 있던 것이 무엇인지가
「잃어도 되는 짝인가」를 정한다.

- 중간이 **다른 라벨**이면 그 빈 칸은 그 라벨의 값 자리다. 잃는 것이 맞다.
- 중간이 **안내문**이면 진짜 값 자리는 중간 칸이다. 잃는 것이 맞고, T-0153 이
  안내문 칸을 값 자리로 인정하면서 되찾는다.

**버리는 코드다**(`spike/`).
"""

from __future__ import annotations

import re
import sys
from collections import Counter

from sqlalchemy import func, select

from finnect.attach import store
from finnect.db import SessionFactory
from finnect.forms import SUPPORTED, label_targets, open_form
from finnect.forms.base import Cell
from finnect.models import AttachmentFile, Document

#: 안내문으로 보이는 모양. **판정용이 아니라 세는 용도다** — 제품 코드가 이걸로
#: 가르면 ADR-0060 결정 6 을 어긴다.
_PLACEHOLDER = re.compile(
    r"^[\s]*([0OoＯ○◯●□◇xX×\-.,/()]+|"
    r".*(?:yyyy|mm|dd|xxxx|@|기재|작성|예[):\s]|해당|선택|표기).*)[\s]*$",
    re.IGNORECASE,
)


def old_pairs(cells: list[Cell]) -> list[tuple[Cell, list[Cell], Cell]]:
    """옛 규칙의 짝을 `(라벨, 건너뛴 칸들, 값 칸)` 으로."""
    by_row: dict[tuple[int, int, int], list[Cell]] = {}
    for c in cells:
        by_row.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)
    out = []
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        for i, c in enumerate(row):
            if c.blank:
                continue
            rest = row[i + 1 :]
            j = next((k for k, n in enumerate(rest) if n.blank), None)
            if j is None:
                continue
            out.append((c, rest[:j], rest[j]))
    return out


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    with SessionFactory() as s:
        rows = s.execute(
            select(Document.sha256, AttachmentFile.detected_ext, func.count(Document.id))
            .join(AttachmentFile, AttachmentFile.sha256 == Document.sha256)
            .where(AttachmentFile.detected_ext.in_(sorted(SUPPORTED)))
            .group_by(Document.sha256, AttachmentFile.detected_ext)
            .limit(limit)
        ).all()

    tally = Counter()
    samples: dict[str, list[str]] = {"안내문": [], "다른 라벨": [], "판단 보류": []}

    for sha, ext, _ in rows:
        try:
            cells = open_form(str(store.abs_path(store.rel_path(sha))), ext).cells()
        except Exception:  # noqa: BLE001
            continue
        keep = {(label, a) for label, a in label_targets(cells)}
        for label_cell, skipped, value_cell in old_pairs(cells):
            if (label_cell.text, value_cell.anchor) in keep:
                continue  # 새 규칙도 잡는다
            tally["잃은 쌍"] += 1
            if not skipped:
                tally["중간 없음(병합 접힘)"] += 1
                continue
            mid = skipped[0].text
            kind = "안내문" if _PLACEHOLDER.match(mid) else "다른 라벨"
            # 중간 칸이 그 자체로 다음 빈 칸의 라벨인지 본다
            if kind == "다른 라벨" and (mid, value_cell.anchor) not in keep:
                kind = "판단 보류"
            tally[kind] += 1
            if len(samples[kind]) < 10:
                samples[kind].append(
                    f"{sha[:8]} {ext}  {label_cell.text[:14]!r} | [{mid[:24]}] | (빈칸)"
                )

    print()
    for k, v in tally.most_common():
        print(f"{k:22} {v:,}")
    print()
    for kind, lines in samples.items():
        print(f"── {kind}")
        for line in lines:
            print("   ", line)


if __name__ == "__main__":
    main()
