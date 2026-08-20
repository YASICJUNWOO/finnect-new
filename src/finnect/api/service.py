"""조회.

정렬과 기본 필터가 ADR-0024(접수 기간 표현)를 그대로 구현한다.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Sequence

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from finnect.api.schemas import (
    AttachmentOut,
    DocumentItemOut,
    DocumentOut,
    NoticeDetailOut,
    NoticeDocumentsOut,
    NoticeListOut,
    NoticeOut,
)
from finnect.api.text import to_text
from finnect.attach import store
from finnect.models import (
    Attachment,
    AttachmentFile,
    Document,
    DocumentItem,
    DocumentKind,
    Source,
)
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


#: 공고문이 서류를 말하는 줄. 양식이 없을 때 이거라도 넘긴다.
_SUBMIT_HINT = re.compile(r"제출\s*서류|구비\s*서류|신청\s*서류|신청\s*시\s*제출")


def notice_documents(s: Session, source: str, external_id: str) -> NoticeDocumentsOut | None:
    """공고가 요구하는 서류와 그 안의 작성 항목(plan/11 T-0039).

    **공고와 문서를 잇는 표를 만들지 않았다.** `attachment → attachment_file → sha256`
    조인으로 푼다. 재수집이 `attachment` 를 갈아엎어도 조인이 다시 붙는다(ADR-0022).
    """
    if source not in SOURCES:
        return None

    rows = s.execute(
        select(Attachment, AttachmentFile, Document)
        .join(AttachmentFile, AttachmentFile.url == Attachment.url)
        .join(Document, Document.sha256 == AttachmentFile.sha256)
        .where(Attachment.source == source, Attachment.external_id == external_id)
        .order_by(Attachment.position, Document.seq)
    ).all()

    docs: list[DocumentOut] = []
    undecided = 0
    seen: set[int] = set()
    for att, _file, doc in rows:
        if doc.id in seen:
            continue
        seen.add(doc.id)
        if doc.kind == str(DocumentKind.UNKNOWN):
            undecided += 1
            continue
        if doc.kind == str(DocumentKind.NONE):
            continue

        items = s.scalars(
            select(DocumentItem)
            .where(DocumentItem.document_id == doc.id)
            .order_by(DocumentItem.ordinal)
        ).all()
        docs.append(
            DocumentOut(
                id=doc.id,
                title=doc.title,
                kind=doc.kind,
                decided_by=doc.decided_by,
                filename=att.filename,
                url=att.url,
                items=_tree(items),
            )
        )

    return NoticeDocumentsOut(
        source=source,
        external_id=external_id,
        documents=docs,
        submit_hint=_hints(s, source, external_id) if not docs else [],
        undecided=undecided,
    )


def _tree(rows: Sequence[DocumentItem]) -> list[DocumentItemOut]:
    """`parent_id` 로 트리를 세운다(plan/11 T-0037).

    **한 번에 다 받아서 메모리에서 잇는다.** 단마다 질의를 날리면 항목 199개짜리
    양식이 199번을 부른다.

    **가지에 쓰는 칸이 붙으면 안 된다.** 화면이 잎만 쓰는 자리로 세는데
    (`FormFill` 의 `leafKeys`) 자식을 안 내보내면 `2 추진배경 및 목표` 가 잎이 되고,
    거기 붙은 칸에 쓴 글은 어느 항목의 것도 아니게 된다.

    순서는 `ordinal` 이다 — 문서 안에서 한 번만 매겨지므로 형제끼리도 이 순서다.
    """
    kids: dict[int | None, list[DocumentItem]] = {}
    for r in rows:
        kids.setdefault(r.parent_id, []).append(r)

    def build(parent: int | None, depth: int) -> list[DocumentItemOut]:
        # 부모는 항상 자식보다 먼저 들어가므로(`extract/service.py` `_add_outline`)
        # 고리가 생길 수 없다. 그래도 막아 두는 이유는 여기가 API 라서다 — 고리
        # 하나가 응답을 못 끝내면 공고 상세가 통째로 안 뜬다.
        if depth > 10:
            return []
        return [
            DocumentItemOut(
                number=i.number,
                title=i.title,
                instruction=i.instruction,
                limit_text=i.limit_text,
                input_kind=i.input_kind,
                children=build(i.id, depth + 1),
            )
            for i in kids.get(parent, [])
        ]

    return build(None, 1)


def _hints(s: Session, source: str, external_id: str) -> list[str]:
    """양식이 없을 때 공고문에서 '무슨 서류를 내나' 만이라도 건진다.

    **빈손으로 보내지 않는다**(DESIGN.md §7-5). 층 1 은 공고문에 있다.
    """
    paths = s.scalars(
        select(AttachmentFile.text_path)
        .join(Attachment, Attachment.url == AttachmentFile.url)
        .where(
            Attachment.source == source,
            Attachment.external_id == external_id,
            AttachmentFile.text_path.is_not(None),
        )
        .limit(4)
    ).all()

    out: list[str] = []
    for p in paths:
        try:
            text = store.abs_path(p).read_text(errors="ignore")
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            line = re.sub(r"\s{2,}", " ", line.replace("\t", " ")).strip()
            if 6 <= len(line) <= 120 and _SUBMIT_HINT.search(line) and line not in out:
                out.append(line)
            if len(out) >= 4:
                return out
    return out
