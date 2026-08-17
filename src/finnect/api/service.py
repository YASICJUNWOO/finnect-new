"""조회.

정렬과 기본 필터가 ADR-0024(접수 기간 표현)를 그대로 구현한다.
"""

from __future__ import annotations

import datetime as dt
import math

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from finnect.api.schemas import AttachmentOut, NoticeDetailOut, NoticeListOut, NoticeOut
from finnect.api.text import to_text
from finnect.models import Attachment, AttachmentFile, Source
from finnect.views import Notice

PAGE_SIZE = 20

SOURCES = {str(Source.BIZINFO), str(Source.KSTARTUP)}

#: 마감 임박순. **네 줄이 ADR-0024 의 세 갈래를 만든다.**
#:   1. 날짜가 있는 것 — 가까운 마감부터
#:   2. 날짜가 없고 원문이 있는 것 — "예산 소진시까지" 등. 원문 사전순
#:   3. 둘 다 없는 것 — 맨 뒤
#: boolean 은 false < true 라 `is_(None)` 오름차순이 "값이 있는 것 먼저"가 된다.
ORDER = (
    Notice.apply_end.is_(None).asc(),
    Notice.apply_end.asc(),
    Notice.apply_period_raw.is_(None).asc(),
    Notice.apply_period_raw.asc(),
    # 같은 마감일이 수백 건이라 안정적인 꼬리가 없으면 페이지마다 순서가 흔들린다.
    Notice.source.asc(),
    Notice.external_id.asc(),
)


def _open_filter(today: dt.date):
    """**마감이 지난 것만 뺀다.**

    날짜가 없는 975건은 빼지 않는다. 마감했는지 알 수 없고 "예산 소진시까지"는
    열려 있을 가능성이 높다. **확인되지 않은 것을 마감으로 처리하지 않는다**(ADR-0024).
    """
    return or_(Notice.apply_end.is_(None), Notice.apply_end >= today)


def _days_left(end: dt.date | None, today: dt.date) -> int | None:
    return (end - today).days if end else None


def _files(s: Session, source: str, external_id: str) -> dict[str, AttachmentFile]:
    """공고 하나의 첨부별 해독 결과. **URL 로 맞춘다**(ADR-0022).

    `attach.service.per_notice` 와 같은 질의다. 거기 것을 안 쓰는 이유는 그 모듈이
    내려받기(httpx)와 파서를 함께 끌고 오기 때문이다. **읽기만 하는 API 가
    다운로더에 딸려 갈 이유가 없다.**
    """
    urls = list(
        s.scalars(
            select(Attachment.url).where(
                Attachment.source == source,
                Attachment.external_id == external_id,
                Attachment.url.is_not(None),
            )
        )
    )
    if not urls:
        return {}
    return {r.url: r for r in s.scalars(select(AttachmentFile).where(AttachmentFile.url.in_(urls)))}


def _counts(s: Session, rows: list[Notice]) -> dict[tuple[str, str], int]:
    """이 페이지 공고들의 첨부 수. 뷰에 상관 서브쿼리를 넣지 않는다."""
    if not rows:
        return {}
    keys = [(r.source, r.external_id) for r in rows]
    got = s.execute(
        select(Attachment.source, Attachment.external_id, func.count())
        .where(tuple_(Attachment.source, Attachment.external_id).in_(keys))
        .group_by(Attachment.source, Attachment.external_id)
    ).all()
    return {(a, b): c for a, b, c in got}


def _to_out(row: Notice, today: dt.date, attachment_count: int) -> NoticeOut:
    return NoticeOut(
        source=row.source,
        external_id=row.external_id,
        title=row.title,
        organization=row.organization,
        supervisor=row.supervisor,
        category=row.category,
        apply_start=row.apply_start,
        apply_end=row.apply_end,
        apply_period_raw=row.apply_period_raw,
        days_left=_days_left(row.apply_end, today),
        detail_url=row.detail_url,
        attachment_count=attachment_count,
    )


def list_notices(
    s: Session,
    *,
    q: str = "",
    source: str = "",
    page: int = 1,
    open_only: bool = True,
    today: dt.date | None = None,
) -> NoticeListOut:
    today = today or dt.date.today()

    where = []
    if source in SOURCES:
        where.append(Notice.source == source)
    if q.strip():
        where.append(Notice.title.ilike(f"%{q.strip()}%"))
    if open_only:
        where.append(_open_filter(today))

    total = s.scalar(select(func.count()).select_from(Notice).where(*where)) or 0
    rows = list(
        s.scalars(
            select(Notice)
            .where(*where)
            .order_by(*ORDER)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    )
    counts = _counts(s, rows)

    return NoticeListOut(
        items=[_to_out(r, today, counts.get((r.source, r.external_id), 0)) for r in rows],
        total=total,
        page=page,
        pages=max(1, math.ceil(total / PAGE_SIZE)),
        open_only=open_only,
    )


def get_notice(
    s: Session, source: str, external_id: str, *, today: dt.date | None = None
) -> NoticeDetailOut | None:
    today = today or dt.date.today()

    row = s.scalars(
        select(Notice).where(Notice.source == source, Notice.external_id == external_id)
    ).first()
    if row is None:
        return None

    attachments = list(
        s.scalars(
            select(Attachment)
            .where(Attachment.source == source, Attachment.external_id == external_id)
            .order_by(Attachment.position)
        )
    )
    # 해독 결과는 URL 로 맞춘다. attachment 는 재수집 때 지워지고 다시 깔린다(ADR-0022).
    files = _files(s, source, external_id)

    out = []
    for a in attachments:
        f = files.get(a.url) if a.url else None
        out.append(
            AttachmentOut(
                position=a.position,
                kind=a.kind,
                filename=a.filename,
                ext=a.ext,
                url=a.url,
                fetch_status=f.fetch_status if f else None,
                parse_status=f.parse_status if f else None,
                text_chars=f.text_chars if f else None,
                detected_ext=f.detected_ext if f else None,
            )
        )

    base = _to_out(row, today, len(attachments))
    return NoticeDetailOut(
        **base.model_dump(),
        summary=to_text(row.summary),
        attachments=out,
        decoded_count=sum(1 for a in out if a.parse_status == "ok"),
    )
