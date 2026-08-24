"""적재 — 응답을 raw_fetch 에 남기고 출처 테이블에 upsert 한다."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from finnect.ingest.base import Adapter, NormalizedNotice
from finnect.models import Attachment, RawFetch

BATCH = 500


@dataclass(slots=True)
class IngestReport:
    source: str
    pages: int = 0
    items: int = 0
    inserted: int = 0
    changed: int = 0
    unchanged: int = 0
    skipped: int = 0  # 외부 ID 가 없어 못 넣은 것 — **사고다**
    filtered: int = 0  # 우리가 안 받기로 해서 뺀 것 — **정책이다**
    attachments: int = 0
    ratelimit_remaining: int | None = None
    unknown_fields: Counter = field(default_factory=Counter)
    expected: int | None = None  # 출처가 말한 총 건수. 진행률 표시용이다

    def render(self) -> str:
        lines = [
            f"[{self.source}] 응답 {self.pages}건 · 공고 {self.items:,}건",
            f"  신규 {self.inserted:,} · 변경 {self.changed:,} · 그대로 {self.unchanged:,}",
        ]
        if self.filtered:
            # 조용히 버리지 않는다. 코퍼스가 왜 이 크기인지는 이 줄이 유일한 단서다.
            lines.append(f"  솎아 낸 것 {self.filtered:,}건 (중분류)")
        if self.expected is not None and self.items < self.expected:
            # 맛보기 수집이든 사고든 여기서 드러난다. 건수만 보고 성공으로 읽지 않게.
            lines.append(f"  ⚠ 전량 {self.expected:,}건 중 {self.items:,}건만 받았다")
        if self.skipped:
            lines.append(f"  건너뜀 {self.skipped:,} (외부 ID 없음)")
        if self.attachments:
            lines.append(f"  첨부 {self.attachments:,}건")
        if self.ratelimit_remaining is not None:
            lines.append(f"  잔여 쿼터 {self.ratelimit_remaining:,}")
        if self.unknown_fields:
            # API 가 필드를 늘렸다. 조용히 넘기지 않는다.
            got = ", ".join(f"{k}({v:,})" for k, v in self.unknown_fields.most_common())
            lines.append(f"  ⚠ 처음 보는 필드 → extra 에 담음: {got}")
        return "\n".join(lines)


def run(
    adapter: Adapter,
    session: Session,
    on_page: Callable[[IngestReport], None] | None = None,
) -> IngestReport:
    """on_page 는 응답 한 건을 처리할 때마다 불린다.

    K-Startup 전량이 149회다. 화면에서 이걸 누르면 몇 분간 아무 표시가 없게 되므로
    중간 상태를 밖으로 낸다. **여기서 커밋하지 않는다.** 적재는 한 트랜잭션이다.
    """
    model = adapter.model  # type: ignore[attr-defined]
    pk = inspect(model).primary_key[0]
    report = IngestReport(source=adapter.source)

    # 기존 해시를 미리 읽는다. K-Startup 은 수정일시가 없어 이것으로만 변경을 판단한다.
    known: dict[str, str] = dict(
        session.execute(select(pk, model.content_hash)).all()  # type: ignore[arg-type]
    )

    to_write: list[tuple[NormalizedNotice, int]] = []
    seen_unchanged: list[str] = []

    for page in adapter.pages():
        raw = RawFetch(
            source=adapter.source,
            request_url=page.request_url,
            page=page.page,
            payload=page.payload,
            item_count=len(page.items),
            byte_size=page.byte_size,
            ratelimit_remaining=page.ratelimit_remaining,
        )
        session.add(raw)
        session.flush()  # raw.id 확보
        report.pages += 1
        report.items += len(page.items)
        if page.ratelimit_remaining is not None:
            report.ratelimit_remaining = page.ratelimit_remaining
        if page.total_count is not None:
            report.expected = page.total_count

        for item in page.items:
            if not adapter.keep(item):
                report.filtered += 1
                continue
            row = adapter.normalize(item)
            if row is None:
                report.skipped += 1
                continue
            for name in row.extra:
                report.unknown_fields[name] += 1

            prev = known.get(row.external_id)
            if prev is None:
                report.inserted += 1
                to_write.append((row, raw.id))
            elif prev != row.content_hash:
                report.changed += 1
                to_write.append((row, raw.id))
            else:
                report.unchanged += 1
                seen_unchanged.append(row.external_id)

            if len(to_write) >= BATCH:
                report.attachments += _flush(session, model, pk, to_write)
                to_write.clear()

        if on_page is not None:
            on_page(report)

    if to_write:
        report.attachments += _flush(session, model, pk, to_write)

    # 바뀌지 않은 것은 '최근에도 있었다'만 기록한다.
    for i in range(0, len(seen_unchanged), BATCH):
        chunk = seen_unchanged[i : i + BATCH]
        session.execute(update(model).where(pk.in_(chunk)).values(last_seen_at=func.now()))

    return report


def _flush(session: Session, model: Any, pk: Any, rows: list[tuple[NormalizedNotice, int]]) -> int:
    """신규·변경 행을 upsert 하고 첨부를 다시 깐다."""
    # 다중 행 INSERT 는 모든 행의 키가 같아야 한다. API 가 필드를 빠뜨리고 주는 건이 있으므로
    # 없는 컬럼은 None 으로 채운 템플릿에서 시작한다.
    # first_seen_at 은 서버 기본값에 맡긴다. 여기서 None 을 넣으면 기본값이 무시된다.
    template = {c.name: None for c in model.__table__.columns if c.name != "first_seen_at"}
    now = dt.datetime.now(dt.UTC)

    payload = []
    for row, raw_fetch_id in rows:
        values: dict[str, Any] = {**template, **row.columns}
        values.update(
            extra=row.extra,
            derived_apply_start=row.derived_apply_start,
            derived_apply_end=row.derived_apply_end,
            content_hash=row.content_hash,
            raw_fetch_id=raw_fetch_id,
            last_seen_at=now,
            changed_at=now,
        )
        payload.append(values)

    stmt = pg_insert(model).values(payload)
    updatable = {
        c.name: stmt.excluded[c.name]
        for c in model.__table__.columns
        if c.name not in (pk.name, "first_seen_at")
    }
    session.execute(stmt.on_conflict_do_update(index_elements=[pk], set_=updatable))

    # 첨부는 (source, external_id) 로 가리킨다. 갱신 시 통째로 다시 깐다.
    owners = [(r.source, r.external_id) for r, _ in rows if r.attachments]
    if owners:
        session.execute(
            delete(Attachment).where(
                Attachment.source == owners[0][0],
                Attachment.external_id.in_([e for _, e in owners]),
            )
        )
    inserted = [
        {
            "source": r.source,
            "external_id": r.external_id,
            "position": a.position,
            "kind": a.kind,
            "filename": a.filename,
            "ext": a.ext,
            "url": a.url,
        }
        for r, _ in rows
        for a in r.attachments
    ]
    if inserted:
        session.execute(pg_insert(Attachment), inserted)
    session.flush()
    return len(inserted)
