"""관리 화면 — 수집한 공고를 눈으로 보는 곳.

운영 도구는 SPEC.md §6 범위 밖이다. 이 화면의 목적은 운영이 아니라
**L1 스키마 설계를 위한 코퍼스 관찰**이다. 그래서 상세는 출처가 준 컬럼을 전부 편다.
design/ 의 토큰·컴포넌트를 따르지 않는다. 제품 화면이 아니다.
"""

from __future__ import annotations

import json
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from finnect import fields
from finnect.db import SessionFactory
from finnect.ingest import jobs, runs, service
from finnect.models import Attachment, BizinfoNotice, KstartupNotice, RawFetch, RunStatus, Source
from finnect.views import Notice


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """기동 시 죽은 프로세스가 남긴 '수집 중' 자국을 정리한다.

    --reload 로 띄우면 파일을 고칠 때마다 프로세스가 갈린다. 돌던 수집은 거기서 끊기는데
    행은 RUNNING 인 채로 남아 화면에서 영원히 도는 것처럼 보인다.
    """
    try:
        reaped = runs.reap()
    except OperationalError as e:
        raise RuntimeError("DB 에 못 붙었다. `docker compose up -d db` 를 먼저 돌린다.") from e
    if reaped:
        print(f"[admin] 중단된 수집 {reaped}건을 정리했다")
    yield


app = FastAPI(title="finnect 관리", docs_url=None, redoc_url=None, lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _ts(value: Any) -> str:
    """timestamptz 는 UTC 로 온다. 읽는 사람 시간대로 돌려 놓는다."""
    return value.astimezone().strftime("%m-%d %H:%M") if value else ""


templates.env.filters["ts"] = _ts

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

# raw_fetch.payload 안에서 공고 배열이 어디 있고, 그 안의 자연키가 무엇인지.
# 봉투 형태는 ingest/envelope.py 가 정본이다.
RAW_ITEMS_KEY = {str(Source.BIZINFO): "jsonArray", str(Source.KSTARTUP): "data"}
RAW_PK = {str(Source.BIZINFO): "pblancId", str(Source.KSTARTUP): "pbanc_sn"}


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _split_payload(payload: Any, source: str, external_id: str) -> tuple[str, str | None, int]:
    """응답 통째에서 봉투와 이 공고의 원문 item 을 갈라 낸다.

    payload 는 응답 한 건 전체다. 기업마당은 한 번에 1,538건이 들어와 3.67MB 라
    그대로 펴면 화면이 못 쓴다. 공고 배열은 봉투에서 빼고 이 공고 것만 꺼낸다.
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
            "nav": "notices",
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
        # 설명은 출처의 공식 문서에서 온다. 없으면 None 이고, 화면이 '문서에 없음'으로 적는다.
        api_fields, ours = [], []
        for col in model.__table__.columns:
            value = getattr(row, col.name, None)
            entry = (col.name, value, fields.describe(source, col.name))
            (api_fields if col.name in model.API_FIELDS else ours).append(entry)

        # 원문. 파싱한 컬럼과 나란히 놓고 무엇이 빠졌는지 눈으로 본다.
        raw = s.get(RawFetch, row.raw_fetch_id) if row.raw_fetch_id else None
        envelope = item = None
        siblings = 0
        if raw is not None:
            envelope, item, siblings = _split_payload(raw.payload, source, external_id)

    known, total = fields.coverage(source, [n for n, _, _ in api_fields])

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "nav": "notices",
            "source": source,
            "external_id": external_id,
            "api_fields": api_fields,
            "ours": ours,
            "extra": row.extra or {},
            "attachments": attachments,
            "table": model.__tablename__,
            "doc": fields.DOCS[source],
            "described": known,
            "described_total": total,
            "raw": raw,
            "raw_envelope": envelope,
            "raw_item": item,
            "raw_siblings": siblings,
        },
    )


@app.get("/ingest", response_class=HTMLResponse)
def ingest_page(request: Request, ok: int = -1, reason: str = "") -> HTMLResponse:
    with SessionFactory() as s:
        stored = dict(s.execute(select(Notice.source, func.count()).group_by(Notice.source)).all())

    last = runs.last_by_source()
    cards = [_card(info, stored.get(info.name, 0), last.get(info.name)) for info in service.SOURCES]

    return templates.TemplateResponse(
        request,
        "ingest.html",
        {
            "nav": "ingest",
            "cards": cards,
            "runs": runs.recent(),
            "busy": any(c["running"] for c in cards),
            "ok": ok,
            "reason": reason,
            "statuses": {str(v): v for v in RunStatus},
        },
    )


@app.post("/ingest/run/{source}")
async def ingest_start(request: Request, source: str, only_open: bool = False) -> RedirectResponse:
    """수집을 시작하고 목록으로 돌려보낸다. 응답을 붙잡고 기다리지 않는다.

    K-Startup 전량이 149회다. 요청 안에서 끝내려 하면 브라우저가 먼저 끊는다.
    """
    form = await request.form()
    try:
        limit = service.parse_limit(str(form.get("limit", "")))
    except ValueError as e:
        return RedirectResponse(f"/ingest?ok=0&reason={quote(str(e))}", status_code=303)

    result = service.launch(source, only_open=only_open, limit=limit, trigger="admin")
    scope = f"{limit:,}건" if limit else "전량"
    reason = result.reason or f"{source} {scope} 수집을 시작했다"
    # POST 뒤 303. 새로 고침으로 같은 수집이 다시 나가지 않게 한다.
    return RedirectResponse(
        f"/ingest?ok={int(result.started)}&reason={quote(reason)}", status_code=303
    )


def _card(info: service.SourceInfo, stored: int, last: Any) -> dict[str, Any]:
    """화면 카드 한 장. 다른 프로세스(CLI)에서 도는 것도 '수집 중'으로 친다."""
    elsewhere = runs.live(info.name)
    return {
        "info": info,
        "stored": stored,
        "last": last,
        "missing_key": service.missing_key(info.name),
        "running": jobs.running(info.name) or elsewhere is not None,
        # 진행률은 이 프로세스가 돌릴 때만 안다. CLI 실행은 건수를 실시간으로 못 본다.
        "progress": jobs.progress_of(info.name),
        "elsewhere": elsewhere if not jobs.running(info.name) else None,
    }
