"""운영 화면 조회 — 읽기만 한다.

**`attach.service` 는 임포트하지 않는다.** 그 모듈이 `httpx` 와 파서를 끌고 오는데,
집계 질의를 여기 다시 쓴 이유는 **`attach/service.py` 의 것과 결과가 같아야 해서다** —
어긋나면 로컬 `--report` 와 화면 숫자가 갈린다. `tests/test_admin_api.py` 가 그걸 잠근다.
(`requirements.txt` 가 그 모듈을 뺐다는 것은 ADR-0026 시절 얘기다 — ADR-0035 로 API 가
이 서버의 상시 프로세스로 내려오면서 그 제약은 없어졌지만, 정본과 갈리지 않아야 한다는
이유는 그대로 남는다.)

`ingest.runs` 도 안 쓴다. 거기 `reap()` 은 죽은 프로세스를 정리하는 **쓰기** 동작이고
읽기 경로가 그걸 할 이유가 없다. 실행 기록은 그냥 `ingest_run` 을 읽는다.
"""

from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finnect import fields
from finnect.api.admin_schemas import (
    AdminAttachmentOut,
    AdminAttachmentsOut,
    AdminIngestOut,
    AdminNoticeDetailOut,
    AdminNoticeListOut,
    AdminNoticeOut,
    AdminWikiCompanyOut,
    AdminWikiOut,
    ByExtOut,
    CoverageOut,
    FieldOut,
    IngestProgressOut,
    OcrOut,
    RawFetchOut,
    RunOut,
    SourceCardOut,
    StatusCountOut,
)
from finnect.config import settings
from finnect.ingest import jobs
from finnect.models import (
    Attachment,
    AttachmentFile,
    BizinfoNotice,
    Chunk,
    CompanyAccount,
    CompanyValue,
    Draft,
    IngestRun,
    KstartupNotice,
    NoticeFit,
    ParseStatus,
    RawFetch,
    Source,
    UserFile,
    WikiFact,
    WikiNode,
)
from finnect.sources import SOURCES
from finnect.views import Notice

#: admin 은 제품(20)보다 크다. 코퍼스를 훑는 화면이라 한 번에 많이 본다.
PAGE_SIZE = 50

#: 최근 실행 기록 몇 건까지. `ingest/runs.py` `RECENT_LIMIT` 과 같은 값이다.
RECENT_RUNS = 30

MODELS: dict[str, Any] = {
    str(Source.BIZINFO): BizinfoNotice,
    str(Source.KSTARTUP): KstartupNotice,
}

#: 제품 목록과 **정렬이 다르다.** 저기는 마감순 하나이고(ADR-0024) 여기는 셋을 고른다.
SORTS: dict[str, tuple[Any, str]] = {
    "deadline": (Notice.apply_end.asc().nullslast(), "마감 임박순"),
    "recent": (Notice.first_seen_at.desc(), "최근 수집순"),
    "title": (Notice.title.asc(), "이름순"),
}

# raw_fetch.payload 안에서 공고 배열이 어디 있고, 그 안의 자연키가 무엇인지.
# 봉투 형태는 ingest/envelope.py 가 정본이다.
RAW_ITEMS_KEY = {str(Source.BIZINFO): "jsonArray", str(Source.KSTARTUP): "data"}
RAW_PK = {str(Source.BIZINFO): "pblancId", str(Source.KSTARTUP): "pbanc_sn"}


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _text(value: Any) -> str | None:
    """화면에 낼 문자열. **None 과 빈 문자열을 구분한다** — 앞의 것은 null 로 뜬다."""
    return None if value is None else str(value)


def list_notices(
    s: Session, *, source: str = "", q: str = "", sort: str = "deadline", page: int = 1
) -> AdminNoticeListOut:
    """운영 목록.

    **마감된 공고를 빼지 않는다.** 제품 목록은 기본이 `open_only=True` 인데 여기는
    코퍼스를 보는 화면이라 31,327건 전부가 모집단이다.
    """
    key = sort if sort in SORTS else "deadline"
    order, _ = SORTS[key]

    where = []
    if source in MODELS:
        where.append(Notice.source == source)
    if q.strip():
        where.append(Notice.title.ilike(f"%{q.strip()}%"))

    total = s.scalar(select(func.count()).select_from(Notice).where(*where)) or 0
    rows = list(
        s.scalars(
            select(Notice)
            .where(*where)
            .order_by(order)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    )

    # 첨부 수는 이 페이지 것만 따로 센다. 뷰에 상관 서브쿼리를 넣지 않는다.
    counts: dict[tuple[str, str], int] = {}
    if rows:
        got = s.execute(
            select(Attachment.source, Attachment.external_id, func.count())
            .where(Attachment.external_id.in_([r.external_id for r in rows]))
            .group_by(Attachment.source, Attachment.external_id)
        ).all()
        counts = {(a, b): c for a, b, c in got}

    by_source = dict(s.execute(select(Notice.source, func.count()).group_by(Notice.source)).all())

    return AdminNoticeListOut(
        items=[
            AdminNoticeOut(
                source=r.source,
                external_id=r.external_id,
                title=r.title,
                organization=r.organization,
                apply_end=r.apply_end,
                apply_period_raw=r.apply_period_raw,
                attachment_count=counts.get((r.source, r.external_id), 0),
                attachment_status=r.attachment_status,
                last_seen_at=r.last_seen_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        pages=max(1, math.ceil(total / PAGE_SIZE)),
        page_size=PAGE_SIZE,
        sort=key,
        sorts={k: v[1] for k, v in SORTS.items()},
        by_source=by_source,
    )


def _files(s: Session, source: str, external_id: str) -> dict[str, AttachmentFile]:
    """공고 하나의 첨부별 해독 결과. **URL 로 맞춘다**(ADR-0022)."""
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


def _split_payload(payload: Any, source: str, external_id: str) -> tuple[str, str | None, int]:
    """응답 통째에서 봉투와 이 공고의 원문 item 을 갈라 낸다.

    기업마당은 한 번에 1,538건이 들어와 3.67MB 다. 그대로 내면 화면이 못 쓴다.
    """
    if not isinstance(payload, dict):
        return _dump(payload), None, 0

    items_key = RAW_ITEMS_KEY.get(source)
    items = payload.get(items_key)
    items = items if isinstance(items, list) else []

    envelope = {k: v for k, v in payload.items() if k != items_key}
    pk = RAW_PK.get(source)
    mine = next((i for i in items if isinstance(i, dict) and str(i.get(pk)) == external_id), None)

    return _dump(envelope), (_dump(mine) if mine is not None else None), len(items)


def get_notice(s: Session, source: str, external_id: str) -> AdminNoticeDetailOut | None:
    """운영 상세. **뷰를 거치지 않고 출처별 표에서 직접 읽는다.**"""
    model = MODELS.get(source)
    if model is None:
        return None
    row = s.get(model, external_id)
    if row is None:
        return None

    api_fields: list[FieldOut] = []
    ours: list[FieldOut] = []
    for col in model.__table__.columns:
        entry = FieldOut(
            name=col.name,
            value=_text(getattr(row, col.name, None)),
            description=fields.describe(source, col.name),
        )
        if col.name in model.API_FIELDS:
            api_fields.append(entry)
        elif col.name != "extra":
            # extra 는 아래에서 따로 낸다. 두 번 내면 화면이 같은 값을 두 번 그린다.
            ours.append(entry)

    attachments = list(
        s.scalars(
            select(Attachment)
            .where(Attachment.source == source, Attachment.external_id == external_id)
            .order_by(Attachment.position)
        )
    )
    files = _files(s, source, external_id)

    out: list[AdminAttachmentOut] = []
    for a in attachments:
        f = files.get(a.url) if a.url else None
        contents = (f.contents or {}).get("files") if f else None
        out.append(
            AdminAttachmentOut(
                position=a.position,
                kind=a.kind,
                filename=a.filename,
                ext=a.ext,
                url=a.url,
                fetch_status=f.fetch_status if f else None,
                parse_status=f.parse_status if f else None,
                parser=f.parser if f else None,
                text_chars=f.text_chars if f else None,
                detected_ext=f.detected_ext if f else None,
                fetch_error=f.fetch_error if f else None,
                parse_error=f.parse_error if f else None,
                contents=[
                    str(c.get("name", "")) for c in contents if isinstance(c, dict)
                ]
                if isinstance(contents, list)
                else [],
            )
        )

    raw_out = None
    if row.raw_fetch_id:
        raw = s.get(RawFetch, row.raw_fetch_id)
        if raw is not None:
            envelope, item, siblings = _split_payload(raw.payload, source, external_id)
            raw_out = RawFetchOut(
                id=raw.id,
                request_url=raw.request_url,
                fetched_at=raw.fetched_at,
                page=raw.page,
                item_count=raw.item_count,
                byte_size=raw.byte_size,
                ratelimit_remaining=raw.ratelimit_remaining,
                envelope=envelope,
                item=item,
                siblings=siblings,
            )

    described, described_total = fields.coverage(source, [f.name for f in api_fields])
    doc = fields.DOCS[source]

    return AdminNoticeDetailOut(
        source=source,
        external_id=external_id,
        table=model.__tablename__,
        api_fields=api_fields,
        ours=ours,
        extra={k: str(v) for k, v in (row.extra or {}).items()},
        described=described,
        described_total=described_total,
        doc_label=doc.label,
        doc_url=doc.url,
        attachments=out,
        decoded_count=sum(1 for a in out if a.parse_status == "ok"),
        raw=raw_out,
    )


def attachments(s: Session) -> AdminAttachmentsOut:
    """해독 현황. **`attach/service.py` `coverage()` · `ocr_candidates()` 와 같은 질의다.**"""
    urls = (
        s.scalar(select(func.count(func.distinct(Attachment.url))).where(Attachment.url.is_not(None)))
        or 0
    )
    files = s.scalar(select(func.count()).select_from(AttachmentFile)) or 0

    fetch = s.execute(
        select(AttachmentFile.fetch_status, func.count())
        .group_by(AttachmentFile.fetch_status)
        .order_by(func.count().desc())
    ).all()
    parse = s.execute(
        select(AttachmentFile.parse_status, func.count())
        .group_by(AttachmentFile.parse_status)
        .order_by(func.count().desc())
    ).all()
    by_ext = s.execute(
        select(
            AttachmentFile.detected_ext,
            AttachmentFile.parse_status,
            func.count(),
            func.avg(AttachmentFile.text_chars),
        )
        .where(AttachmentFile.parse_status.is_not(None))
        .group_by(AttachmentFile.detected_ext, AttachmentFile.parse_status)
        .order_by(AttachmentFile.detected_ext, func.count().desc())
    ).all()

    coverage = CoverageOut(
        listed=s.scalar(select(func.count()).select_from(Attachment)) or 0,
        urls=urls,
        files=files,
        unaccounted=urls - files,
        fetch=[StatusCountOut(status=st, count=c) for st, c in fetch],
        parse=[StatusCountOut(status=st, count=c) for st, c in parse],
        by_ext=[
            ByExtOut(ext=e, status=st, count=c, avg_chars=int(a) if a else 0)
            for e, st, c, a in by_ext
        ],
    )

    images = ("png", "jpg", "gif")
    ocr = OcrOut(
        pdf_empty=s.scalar(
            select(func.count())
            .select_from(AttachmentFile)
            .where(
                AttachmentFile.detected_ext == "pdf",
                AttachmentFile.parse_status == str(ParseStatus.EMPTY),
            )
        )
        or 0,
        images=s.scalar(
            select(func.count())
            .select_from(AttachmentFile)
            .where(AttachmentFile.detected_ext.in_(images))
        )
        or 0,
        # 공고문 자리에 이미지가 붙은 것. 본문에 평가 정보가 0%라 통째로 안 보이는 공고다.
        image_notices=s.scalar(
            select(func.count())
            .select_from(Attachment)
            .join(AttachmentFile, AttachmentFile.url == Attachment.url)
            .where(Attachment.kind == "공고문", AttachmentFile.detected_ext.in_(images))
        )
        or 0,
    )

    return AdminAttachmentsOut(
        coverage=coverage, ocr=ocr, formats=sorted(settings.formats)
    )


def _run_out(r: IngestRun) -> RunOut:
    return RunOut(
        id=r.id,
        source=r.source,
        only_open=r.only_open,
        filter_name=r.filter_name,
        filtered=r.filtered,
        trigger=r.trigger,
        status=r.status,
        started_at=r.started_at,
        elapsed=r.elapsed,
        item_limit=r.item_limit,
        expected=r.expected,
        truncated=r.truncated,
        pages=r.pages,
        items=r.items,
        inserted=r.inserted,
        changed=r.changed,
        unchanged=r.unchanged,
        report=r.report,
        error=r.error,
        unknown_fields={k: int(v) for k, v in (r.unknown_fields or {}).items()},
    )


def ingest(s: Session) -> AdminIngestOut:
    """수집 기록과 지금 상태.

    **버튼은 여기 없다.** 실행은 `app.py` 의 `POST /api/admin/ingest/run/{source}` 다 —
    이 함수는 DB 를 몰라야 하는 읽기 전용 계약을 유지한다. `running`·`progress` 는
    DB 가 아니라 **이 프로세스의 메모리**(`ingest/jobs.py`)에서 온다(ADR-0065) — 그래서
    함수 이름은 그대로인데 더 이상 순수 조회는 아니다.
    """
    stored = dict(s.execute(select(Notice.source, func.count()).group_by(Notice.source)).all())

    recent = list(
        s.scalars(select(IngestRun).order_by(IngestRun.started_at.desc()).limit(RECENT_RUNS))
    )
    # 출처별 마지막 실행. **최근 목록에서 고르지 않는다** — 한 출처를 30번 연달아 돌리면
    # 다른 출처의 마지막 기록이 목록에서 밀려나 카드가 "안 돌렸다"로 거짓말을 한다.
    last: dict[str, IngestRun] = {}
    for info in SOURCES:
        found = s.scalars(
            select(IngestRun)
            .where(IngestRun.source == info.name)
            .order_by(IngestRun.started_at.desc())
            .limit(1)
        ).first()
        if found is not None:
            last[info.name] = found

    return AdminIngestOut(
        cards=[
            SourceCardOut(
                name=info.name,
                label=info.label,
                expected=info.expected,
                requests=info.requests,
                note=info.note,
                stored=stored.get(info.name, 0),
                last=_run_out(last[info.name]) if info.name in last else None,
                running=jobs.running(info.name),
                progress=_progress_out(jobs.progress_of(info.name)),
            )
            for info in SOURCES
        ],
        runs=[_run_out(r) for r in recent],
    )


def _progress_out(p: jobs.Progress | None) -> IngestProgressOut | None:
    if p is None:
        return None
    return IngestProgressOut(
        pages=p.pages, items=p.items, expected=p.expected, target=p.target,
        goal=p.goal, percent=p.percent,
        phase=p.phase, scraped=p.scraped, scrape_total=p.scrape_total,
    )


# ─── 위키 지우기 (ADR-0072) ─────────────────────────────────────────


def wikis(s: Session) -> AdminWikiOut:
    """위키가 서 있는 회사를 센다. **읽기만 한다** — 지우는 것은 `app.py` 의
    `POST /api/admin/wiki/purge/{company_id}` 다([ADR-0072](
    ../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).

    **표를 다섯 개 따로 센다.** 조인 하나로 묶으면 곱집합이 생겨 파일 7개 × 청크 40개가
    280 으로 나온다 — 화면에 서는 것이 전부 숫자라 그 고장이 그럴듯하게 보인다.
    회사 수가 두 자리라 질의 일곱 번이 비싸지 않다.

    **`company_account` 를 모수로 삼지 않는다.** `c_dasiro`·`c_narin` 은 CLI 로 만든
    회사라 그 표에 행이 없는데, **시연에서 실제로 지울 것이 그쪽이다.** 반대로 입장만
    하고 아무것도 안 올린 사람은 지울 것이 없어서 목록에 안 선다 — 모수는 **행이 있는
    쪽**이고 이름은 있으면 붙인다.

    **`drafts`·`fits` 는 안 지우는 것을 세는 칸이다.** 위키만 지우는 버튼이라 저 둘이
    남는데, 화면이 안 적으면 남은 것이 고장으로 읽힌다.
    """

    def tally(model: object) -> dict[str, int]:
        return dict(
            s.execute(
                select(model.company_id, func.count()).group_by(model.company_id)  # type: ignore[attr-defined]
            ).all()
        )

    files = tally(UserFile)
    chunks = tally(Chunk)
    facts = tally(WikiFact)
    values = tally(CompanyValue)
    nodes = tally(WikiNode)
    drafts = tally(Draft)
    fits = tally(NoticeFit)

    # **모수는 위키 쪽 다섯이다.** 초안과 판정만 남은 회사는 여기 안 선다 — 이 버튼이
    # 그 둘을 안 지우므로, 목록에 세워 두면 눌러도 아무 일도 안 일어난다.
    ids = set(files) | set(chunks) | set(facts) | set(values) | set(nodes)

    names = dict(s.execute(select(CompanyAccount.company_id, CompanyAccount.name)).all())
    uploaded = dict(
        s.execute(
            select(UserFile.company_id, func.max(UserFile.uploaded_at)).group_by(
                UserFile.company_id
            )
        ).all()
    )

    rows = [
        AdminWikiCompanyOut(
            company_id=cid,
            name=names.get(cid),
            files=files.get(cid, 0),
            chunks=chunks.get(cid, 0),
            facts=facts.get(cid, 0),
            values=values.get(cid, 0),
            nodes=nodes.get(cid, 0),
            uploaded_at=uploaded.get(cid),
            drafts=drafts.get(cid, 0),
            fits=fits.get(cid, 0),
        )
        for cid in ids
    ]
    # 최근에 올린 것이 위다. **시각이 없는 회사를 맨 뒤로 보낸다** — 사실만 남고 파일이
    # 지워진 상태라 방금 만진 것일 리가 없다. 같은 값이면 id 로 갈라 순서를 고정한다.
    rows.sort(key=lambda r: (r.uploaded_at is not None, r.uploaded_at, r.company_id), reverse=True)
    return AdminWikiOut(companies=rows)
