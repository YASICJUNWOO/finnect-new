"""관리 화면 — 수집한 공고를 눈으로 보는 곳.

운영 도구는 SPEC.md §6 범위 밖이다. 이 화면의 목적은 운영이 아니라
**L1 스키마 설계를 위한 코퍼스 관찰**이다. 그래서 상세는 출처가 준 컬럼을 전부 편다.
design/ 의 토큰·컴포넌트를 따르지 않는다. 제품 화면이 아니다.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from finnect.db import SessionFactory
from finnect.models import Attachment, BizinfoNotice, KstartupNotice, Source
from finnect.views import Notice

app = FastAPI(title="finnect 관리", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

PAGE_SIZE = 50

MODELS: dict[str, Any] = {
    str(Source.BIZINFO): BizinfoNotice,
    str(Source.KSTARTUP): KstartupNotice,
}

SORTS = {
    "deadline": (Notice.apply_end.asc().nullslast(), "마감 임박순"),
    "recent": (Notice.first_seen_at.desc(), "최근 수집순"),
    "title": (Notice.title.asc(), "이름순"),
}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/notices")


@app.get("/notices", response_class=HTMLResponse)
def notice_list(
    request: Request,
    source: str = "",
    q: str = "",
    sort: str = "deadline",
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    order, _ = SORTS.get(sort, SORTS["deadline"])

    where = []
    if source in MODELS:
        where.append(Notice.source == source)
    if q.strip():
        where.append(Notice.title.ilike(f"%{q.strip()}%"))

    with SessionFactory() as s:
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
            keys = [(r.source, r.external_id) for r in rows]
            got = s.execute(
                select(Attachment.source, Attachment.external_id, func.count())
                .where(Attachment.external_id.in_([k[1] for k in keys]))
                .group_by(Attachment.source, Attachment.external_id)
            ).all()
            counts = {(a, b): c for a, b, c in got}

        by_source = dict(
            s.execute(select(Notice.source, func.count()).group_by(Notice.source)).all()
        )

    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "rows": rows,
            "counts": counts,
            "total": total,
            "page": page,
            "pages": max(1, math.ceil(total / PAGE_SIZE)),
            "source": source,
            "q": q,
            "sort": sort,
            "sorts": {k: v[1] for k, v in SORTS.items()},
            "by_source": by_source,
        },
    )


@app.get("/notice/{source}/{external_id}", response_class=HTMLResponse)
def notice_detail(request: Request, source: str, external_id: str) -> HTMLResponse:
    model = MODELS.get(source)
    if model is None:
        return HTMLResponse(f"모르는 출처: {source}", status_code=404)

    with SessionFactory() as s:
        row = s.get(model, external_id)
        if row is None:
            return HTMLResponse(f"없는 공고: {source}/{external_id}", status_code=404)

        attachments = list(
            s.scalars(
                select(Attachment)
                .where(Attachment.source == source, Attachment.external_id == external_id)
                .order_by(Attachment.position)
            )
        )

        # API 가 준 컬럼과 우리가 붙인 컬럼을 갈라서 보여준다.
        api_fields, ours = [], []
        for col in model.__table__.columns:
            value = getattr(row, col.name, None)
            (api_fields if col.name in model.API_FIELDS else ours).append((col.name, value))

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "source": source,
            "external_id": external_id,
            "api_fields": api_fields,
            "ours": ours,
            "extra": row.extra or {},
            "attachments": attachments,
            "table": model.__tablename__,
        },
    )
