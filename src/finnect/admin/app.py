"""수집 실행 화면 — **로컬 전용이고 이제 이 하나만 남았다.**

2026-08-17 읽기 화면 넷은 Next.js(`web/app/admin/`)로 옮겼다([ADR-0027](
../../../docs/adr/0027-운영-화면을-nextjs로-옮긴다.md)). 배포본에서도 열려야 했고,
그 값들은 `GET /api/admin/*` 이 낸다.

**여기 남은 것은 옮길 수 없는 것 하나다.** 수집은 응답보다 오래 사는 데몬 스레드로 돈다 —
K-Startup 전량이 요청 149회다. 서버리스 함수가 할 일이 아니고, `jobs.py` 의 진행률은
수집을 돌리는 프로세스 안에서만 산다. 그래서 버튼과 진행률이 로컬에 남았다.

    uv run uvicorn finnect.admin.app:app --reload    # :8000

**읽기 화면을 여기 다시 만들지 않는다.** 같은 화면이 두 벌이 되면 갈리고, 갈린 것을
아무도 모른다. 공고 목록·상세·첨부 해독은 `web/app/admin/` 이 정본이다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from finnect.db import SessionFactory
from finnect.ingest import jobs, runs, service
from finnect.models import RunStatus
from finnect.views import Notice


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """기동 시 죽은 프로세스가 남긴 '수집 중' 자국을 정리한다.

    --reload 로 띄우면 파일을 고칠 때마다 프로세스가 갈린다. 돌던 수집은 거기서 끊기는데
    행은 RUNNING 인 채로 남아 화면에서 영원히 도는 것처럼 보인다.

    **이 정리가 배포본에 없는 이유이기도 하다.** 쓰기 동작이고, 읽기 경로가 할 일이 아니다.
    """
    try:
        reaped = runs.reap()
    except OperationalError as e:
        raise RuntimeError("DB 에 못 붙었다. `docker compose up -d db` 를 먼저 돌린다.") from e
    if reaped:
        print(f"[admin] 중단된 수집 {reaped}건을 정리했다")
    yield


app = FastAPI(title="finnect 수집", docs_url=None, redoc_url=None, lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _ts(value: Any) -> str:
    """timestamptz 는 UTC 로 온다. 읽는 사람 시간대로 돌려 놓는다."""
    return value.astimezone().strftime("%m-%d %H:%M") if value else ""


templates.env.filters["ts"] = _ts


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/ingest")


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
