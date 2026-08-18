"""제품 API. 사용자 앱(`web/`)이 이걸 부른다.

**admin 과 별개 프로세스다**(ADR-0023). 포트도 다르다 — admin 8000, 여기 8100.

    uv run uvicorn finnect.api.app:app --reload --port 8100
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from finnect.api import admin_service, service, wiki_service
from finnect.api.admin_schemas import (
    AdminAttachmentsOut,
    AdminIngestOut,
    AdminNoticeDetailOut,
    AdminNoticeListOut,
)
from finnect.api.schemas import NoticeDetailOut, NoticeDocumentsOut, NoticeListOut
from finnect.api.wiki_schemas import WikiOut
from finnect.db import SessionFactory

app = FastAPI(title="finnect API", docs_url="/docs", redoc_url=None)

# 로컬 개발용. Next.js dev 서버가 :3000 에서 뜬다.
# **원격 배포 때 다시 정한다** — ADR-0023 "안 정한 것".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/notices", response_model=NoticeListOut)
def notices(
    q: str = "",
    source: str = "",
    page: int = Query(1, ge=1),
    open_only: bool = True,
) -> NoticeListOut:
    """공고 목록.

    **기본이 `open_only=True` 다.** K-Startup 29,420건이 이미 마감된 과거 공고라
    그대로 쏟으면 화면이 아카이브가 된다. 끄면 전량이 나온다.
    """
    with SessionFactory() as s:
        return service.list_notices(s, q=q, source=source, page=page, open_only=open_only)


@app.get("/api/notices/{source}/{external_id}", response_model=NoticeDetailOut)
def notice(source: str, external_id: str) -> NoticeDetailOut:
    if source not in service.SOURCES:
        raise HTTPException(404, f"모르는 출처: {source}")
    with SessionFactory() as s:
        found = service.get_notice(s, source, external_id)
    if found is None:
        raise HTTPException(404, f"없는 공고: {source}/{external_id}")
    return found


@app.get("/api/notices/{source}/{external_id}/documents", response_model=NoticeDocumentsOut)
def notice_documents(source: str, external_id: str) -> NoticeDocumentsOut:
    """이 공고에 무슨 서류를 내야 하고, 그 안에 무엇을 써야 하는가(plan/11).

    **아직 칸 채우기 서식만 판정된다.** 서술형은 공고문의 절과 생김새가 같아 규칙이
    네 번 실패했고, T-0036 이 LLM 으로 가른다. 그때까지 그 구간은 `undecided` 로만 센다 —
    **모르는 것을 아는 척해서 공고문 목차를 작성 항목으로 내보내지 않는다.**
    """
    with SessionFactory() as s:
        found = service.notice_documents(s, source, external_id)
    if found is None:
        raise HTTPException(404, f"모르는 출처: {source}")
    return found


# --- 사업 위키 (S7) ---------------------------------------------------------
#
# **`company_id` 를 경로로 받는다.** 인증이 아직 없어서 세션에서 꺼낼 자리가 없다 —
# 지금은 부르는 쪽이 누구인지 말한다. 로그인이 붙으면 이 인자가 사라지고 세션이 대신한다.
#
# **격리가 이 인자 하나에 걸려 있다.** `wiki/storage.py` 와 `chunk.company_id` 가 같은
# 값을 쓰고, 서비스가 그 값으로만 조회한다. 지금 이 API 는 누구의 위키든 열어 준다.


@app.get("/api/wiki/{company_id}", response_model=WikiOut)
def wiki(company_id: str) -> WikiOut:
    """사업 위키 한 장.

    **위키가 없어도 200 이고 궤도 열다섯이 온다.** 빈 자리도 사실이라 화면이 무엇을
    물어야 하는지 알 수 있어야 한다(DESIGN.md §7-5). 404 는 회사가 없을 때가 아니라
    이 경로가 없을 때만 난다.

    **추출기가 아직 스텁이라 픽스처 밖 회사는 자리만 비어서 온다**(ADR-0031).
    응답의 `extractor` 가 무엇이 뽑았는지 말한다.
    """
    with SessionFactory() as s:
        return wiki_service.get_wiki(s, company_id)


@app.get("/api/wiki/{company_id}/markdown", response_class=PlainTextResponse)
def wiki_markdown(company_id: str) -> PlainTextResponse:
    """위키 전부를 마크다운 한 덩어리로.

    **저장된 파일을 읽는 것이 아니라 매번 만든다.** 마크다운은 저장소가 아니라 뷰다
    (plan/12 `구상도와의 차이`) — 사실이 `wiki_fact` 에 있는데 같은 내용을 마크다운으로도
    들고 있으면 둘 중 하나가 먼저 낡는다.

    노드마다 `.md` 파일로 떨어뜨리는 것(F1-6 밖으로 꺼내기)은 아직 없다.
    """
    with SessionFactory() as s:
        body = wiki_service.get_markdown(s, company_id)
    if body is None:
        raise HTTPException(404, f"아직 위키가 없어요: {company_id}")
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")


# --- 운영 화면 (ADR-0027) ---------------------------------------------------
#
# **전부 GET 이다.** 수집 실행은 여기 없다 — 응답보다 오래 사는 데몬 스레드라
# 서버리스 함수의 일이 아니고, 그 버튼은 로컬 CLI 에 남는다.
#
# 제품 경로와 접두사를 갈라 둔다(`/api/admin/`). 목적이 반대인 응답이라
# 한 이름 아래 섞이면 어느 쪽 계약인지 알 수 없다.


@app.get("/api/admin/notices", response_model=AdminNoticeListOut, tags=["admin"])
def admin_notices(
    source: str = "",
    q: str = "",
    sort: str = "deadline",
    page: int = Query(1, ge=1),
) -> AdminNoticeListOut:
    """운영 목록. **마감된 공고를 빼지 않는다** — 코퍼스 전량이 모집단이다."""
    with SessionFactory() as s:
        return admin_service.list_notices(s, source=source, q=q, sort=sort, page=page)


@app.get(
    "/api/admin/notices/{source}/{external_id}",
    response_model=AdminNoticeDetailOut,
    tags=["admin"],
)
def admin_notice(source: str, external_id: str) -> AdminNoticeDetailOut:
    """운영 상세. 출처가 준 컬럼을 **하나도 고르지 않고** 전부 낸다."""
    if source not in admin_service.MODELS:
        raise HTTPException(404, f"모르는 출처: {source}")
    with SessionFactory() as s:
        found = admin_service.get_notice(s, source, external_id)
    if found is None:
        raise HTTPException(404, f"없는 공고: {source}/{external_id}")
    return found


@app.get("/api/admin/attachments", response_model=AdminAttachmentsOut, tags=["admin"])
def admin_attachments() -> AdminAttachmentsOut:
    """해독 현황. **`unaccounted` 가 0인지가 첫 줄이다**(plan/07 검증)."""
    with SessionFactory() as s:
        return admin_service.attachments(s)


@app.get("/api/admin/ingest", response_model=AdminIngestOut, tags=["admin"])
def admin_ingest() -> AdminIngestOut:
    """수집 실행 기록. 읽기만 한다."""
    with SessionFactory() as s:
        return admin_service.ingest(s)
