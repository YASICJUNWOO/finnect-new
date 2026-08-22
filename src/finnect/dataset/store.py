"""백업 — 공고 코퍼스를 파일로 뜨고 되돌린다.

**초기화 전에 반드시 뜬다.** 기업마당 공고는 마감되면 API 에서 사라지고 재수집으로
복구되지 않는다 — 08-16 스냅샷 1,538건 대 08-18 라이브 1,524건, 이틀에 14건이
소멸했다(`notice-filter/로직과근거.md` §12). 우리 DB 가 유일한 사본이라
백업 없는 `--purge` 는 되돌릴 수 없는 삭제다.

형식은 JSON Lines 다. 표 하나를 통째로 메모리에 올리지 않으려는 것이고,
줄 단위라 중간이 깨져도 앞부분은 살아 있다.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from finnect.dataset.tables import DUMPED, json_to_kwargs, row_to_json
from finnect.db import session_scope

__all__ = ["DumpReport", "dump", "restore"]

_BY_NAME = {m.__tablename__: m for m in DUMPED}


@dataclass(frozen=True)
class DumpReport:
    path: Path
    rows: dict[str, int]
    dropped: int = 0

    def render(self) -> str:
        total = sum(self.rows.values())
        lines = [f"[백업] {self.path}  행 {total:,}"]
        lines += [f"  {name:<18} {n:>7,}" for name, n in self.rows.items()]
        if self.dropped:
            lines.append(f"  모르는 키 버림 {self.dropped:,} (백업 이후 컬럼이 바뀌었다)")
        return "\n".join(lines)


def dump(path: Path) -> DumpReport:
    """공고 2표 + 첨부 2표를 JSONL 로 쓴다. 시각은 파일 첫 줄에만 있다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: Counter[str] = Counter()

    with path.open("w", encoding="utf-8") as f, session_scope() as s:
        head = {"kind": "header", "dumped_at": dt.datetime.now(dt.UTC).isoformat()}
        f.write(json.dumps(head, ensure_ascii=False) + "\n")
        for model in DUMPED:
            name = model.__tablename__
            for row in s.scalars(select(model)).yield_per(500):
                line = {"kind": "row", "table": name, "row": row_to_json(row)}
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                rows[name] += 1

    return DumpReport(path=path, rows=dict(rows))


def restore(path: Path) -> DumpReport:
    """백업을 되돌린다. **대상 표를 먼저 비운다** — 병합이 아니라 복원이다.

    부분 복원을 안 하는 이유는 `attachment` 가 재수집 때 통째로 갈리는 표라
    (`ingest/runner.py` `_flush`) 섞으면 어느 행이 언제 것인지 알 수 없어서다.
    """
    rows: Counter[str] = Counter()
    dropped = 0

    with session_scope() as s:
        for model in reversed(DUMPED):
            s.query(model).delete(synchronize_session=False)
        s.flush()

        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("kind") != "row":
                    continue
                model = _BY_NAME.get(rec["table"])
                if model is None:
                    dropped += 1
                    continue
                data = rec["row"]
                kwargs = json_to_kwargs(model, data)
                dropped += len(data) - len(kwargs)
                s.add(model(**kwargs))
                rows[rec["table"]] += 1

    return DumpReport(path=path, rows=dict(rows), dropped=dropped)
