"""제품 API. 사용자 앱(`web/`)이 이걸 부른다.

**admin 과 별개 프로세스다**(ADR-0023). 포트도 다르다 — admin 8000, 여기 8100.

    uv run uvicorn finnect.api.app:app --reload --port 8100
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select

from finnect.api import admin_service, service, wiki_service
from finnect.api.admin_schemas import (
    AdminAttachmentsOut,
    AdminIngestOut,
    AdminNoticeDetailOut,
    AdminNoticeListOut,
)
from finnect.api.schemas import NoticeDetailOut, NoticeDocumentsOut, NoticeListOut
from finnect.api.wiki_schemas import ProgressOut, UploadOut, WikiOut
from finnect.config import settings
from finnect.db import SessionFactory
from finnect.ingest import jobs
from finnect.models import UserFile, UserFileStatus
from finnect.wiki import storage

app = FastAPI(title="finnect API", docs_url="/docs", redoc_url=None)

#: 토큰 없이 여는 경로. 살아 있는지만 답하고 아무것도 흘리지 않는다.
_OPEN = frozenset({"/healthz"})


@app.middleware("http")
async def require_token(request: Request, call_next):
    """토큰이 설정돼 있으면 요구한다(ADR-0035).

    **비어 있으면 아무것도 안 한다.** 로컬은 지금까지처럼 그냥 돌고, 배포 서버에서만
    켜진다 — 켜는 것을 잊는 쪽이 위험하지만, 로컬에서 토큰을 강제하면 테스트와
    `--reload` 가 전부 토큰을 들고 다녀야 해서 그 대가가 더 크다.

    **`compare_digest` 를 쓴다.** `==` 는 앞에서부터 비교하다 다른 글자에서 멈춰서
    맞은 글자 수가 응답 시간에 새어 나온다.

    **바이트로 바꿔 넣는다.** `compare_digest` 는 비ASCII 문자열을 받으면 `TypeError`
    를 내는데, 그러면 토큰에 한글 한 글자만 섞여도 **401 이 아니라 500 이 난다.**
    토큰은 환경변수라 그런 값이 실제로 들어올 수 있다. (다만 HTTP 헤더가 비ASCII 를
    못 실으므로 그런 토큰은 아무도 통과 못 한다 — 500 대신 401 로 막힐 뿐이다.)

    CORS 보다 **먼저 더한다.** Starlette 은 나중에 더한 미들웨어가 바깥이라, 이렇게
    해야 CORS 가 바깥에 서서 preflight 를 토큰 검사 전에 처리한다.
    """
    if settings.api_token and request.url.path not in _OPEN:
        sent = request.headers.get("x-finnect-token", "")
        if not secrets.compare_digest(sent.encode(), settings.api_token.encode()):
            # **무엇이 틀렸는지 나누지 않는다.** "헤더가 없다"와 "값이 다르다"를
            # 구분해 주면 그것 자체가 단서다.
            return JSONResponse({"detail": "토큰이 없거나 틀렸어요"}, status_code=401)
    return await call_next(request)


# 로컬 개발용. Next.js dev 서버가 :3000 에서 뜬다.
# **원격 배포 때 다시 정한다** — ADR-0023 "안 정한 것".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    # **POST 가 붙었다**(plan/15). 올리기 하나뿐이고 나머지는 전부 GET 이다.
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """살아 있나. **토큰 없이 열려 있다**(`_OPEN`).

    systemd 와 리버스 프록시가 물어보는 자리다. DB 를 건드리지 않는다 — DB 가 잠깐
    흔들릴 때 프로세스까지 재시작되면 복구가 더 느려진다.
    """
    return {"status": "ok"}


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


# --- 올리기와 진행 표시 (S1 · plan/15) --------------------------------------
#
# **여기가 이 API 의 유일한 쓰기 경로다.** 나머지는 전부 GET 이다.
#
# **못 쓰는 곳에서는 503 이다**(ADR-0034). 조건을 환경 이름으로 적지 않고 **실제로
# 써 볼 수 있는지**로 본다 — `data/user-files/` 는 로컬 디스크이고(ADR-0029) 읽기 전용
# 번들에서는 `put()` 이 터진다. 미리 안 물으면 사용자가 파일을 다 올린 뒤에 500 을 본다.
#
# ADR-0035 가 API 를 자체 서버로 내리면서 **지금은 이 가드가 안 걸린다.** 코드를 두는
# 것은 안전망이라서다 — 서버리스로 되돌아가거나 디스크가 차면 그때 이게 답한다.


#: 한 회사에 구축 하나. `ingest/jobs.py` 의 락을 그대로 쓴다 — **수집기가 아니라
#: 단일 실행 보장 프리미티브다**(그 모듈은 DB 도 네트워크도 모른다). 두 번 눌렀을 때
#: 두 번 도는 것이 여기서도 막아야 하는 사고다.
def _job_key(company_id: str) -> str:
    return f"wiki:{company_id}"


def _build(company_id: str, file_ids: list[int]) -> None:
    """받아 둔 파일을 읽고 위키를 세운다. **응답을 보낸 뒤 스레드에서 돈다.**

    파서를 여기서 임포트한다. 최상단에 두면 `import finnect.api.app` 이 pdfplumber 를
    끌고 오고 **로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정 · `tests/test_admin_api.py`).

    **파일마다 세션을 따로 연다**(F1-1-8). 하나가 터져 롤백될 때 앞의 것이 같이 날아가지
    않아야 한다. `wiki/service.ingest_files` 와 같은 이유이고 같은 모양이다.
    """
    from finnect.wiki import build
    from finnect.wiki import service as files

    for fid in file_ids:
        try:
            with SessionFactory() as s:
                uf = s.get(UserFile, fid)
                # 이미 누가 읽었으면 건드리지 않는다. 두 번 읽으면 청크가 두 벌이 된다.
                if uf is None or uf.status != UserFileStatus.UPLOADED:
                    continue
                files.decode(s, uf)
                s.commit()
        except Exception as e:  # noqa: BLE001 — 이 파일만 실패시키고 다음으로 간다
            with SessionFactory() as s:
                uf = s.get(UserFile, fid)
                if uf is not None:
                    uf.status = UserFileStatus.FAILED
                    uf.parse_error = f"{type(e).__name__}: {e}"
                    s.commit()

    # 사실 추출과 병합은 **전체를 봐야** 정해진다(`build.build_company`). 파일마다 돌리면
    # 어느 시점이 가장 늦은지 알 수 없어 충돌 판정이 깨진다.
    with SessionFactory() as s:
        build.build_company(s, company_id)
        s.commit()


@app.post("/api/wiki/{company_id}/files", response_model=UploadOut, status_code=202)
async def wiki_upload(
    company_id: str,
    files: Annotated[list[UploadFile], File(description="형식 구분 없이 여러 개")],
) -> UploadOut:
    """파일을 통째로 받는다(SPEC F1-1-1 · S1).

    **분류해서 올리라고 요구하지 않는다.** 못 읽는 포맷도 받아서 상태로 남긴다 —
    거절하면 사용자는 그 파일이 왜 안 쓰이는지 영영 모른다.

    **202 다.** 저장까지만 하고 답한다. 해독은 응답을 보낸 뒤 스레드가 하고, 화면은
    `GET /api/wiki/{company_id}/progress` 로 따라온다. 여기서 다 하고 답하면 OCR 이 걸린
    파일 하나에 요청이 몇 분씩 묶인다.
    """
    if not storage.writable():
        raise HTTPException(
            503,
            "이 서버는 파일을 못 받아요. 올리기는 로컬에서만 돼요 — docs/adr/0034 참고",
        )

    from finnect.wiki import service as user_files

    limit = settings.user_file_max_mb * 1024 * 1024
    received: list[int] = []
    duplicate = 0
    rejected: list[tuple[str, str]] = []

    for upload in files:
        name = (upload.filename or "").strip() or "이름없는파일"
        data = await upload.read()
        if not data:
            rejected.append((name, "빈 파일이에요"))
            continue
        if len(data) > limit:
            rejected.append((name, f"{settings.user_file_max_mb}MB 를 넘어요"))
            continue
        try:
            with SessionFactory() as s:
                uf, what = user_files.receive(s, company_id, data, name)
                s.commit()
                if what == "duplicate":
                    duplicate += 1
                else:
                    received.append(uf.id)
        except storage.IsolationError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:  # noqa: BLE001 — 이 파일만 거절하고 나머지는 받는다
            rejected.append((name, f"{type(e).__name__}: {e}"))

    # **새로 받은 것이 없어도 돌린다.** 추출기를 바꾼 뒤 다시 올린 경우가 그렇고,
    # 앞선 실행이 중간에 죽어 `uploaded` 로 남은 행도 여기서 이어받는다.
    pending = received or _stranded(company_id)
    launch = jobs.Launch(False, "읽을 파일이 없어요")
    if pending:
        launch = jobs.launch(_job_key(company_id), lambda: _build(company_id, pending))

    with SessionFactory() as s:
        progress = wiki_service.get_progress(
            s, company_id, running=jobs.running(_job_key(company_id))
        )

    return UploadOut(
        received=len(received),
        duplicate=duplicate,
        rejected=rejected,
        started=launch.started,
        reason=launch.reason,
        progress=progress,
    )


def _stranded(company_id: str) -> list[int]:
    """받아만 두고 못 읽은 파일. **프로세스가 죽으면 여기 남는다.**

    `jobs` 는 스케줄러가 아니라 락이라(ADR-0011 과 같은 성질) 실행이 죽으면 자국만 남는다.
    다시 올릴 때 이어받지 않으면 그 행은 영영 `uploaded` 에 갇힌다 — 같은 파일을 다시
    올려도 `duplicate` 로 튕겨서(`service.receive`) 고칠 길이 없다.
    """
    with SessionFactory() as s:
        return list(
            s.scalars(
                select(UserFile.id).where(
                    UserFile.company_id == company_id,
                    UserFile.status == UserFileStatus.UPLOADED,
                )
            )
        )


@app.get("/api/wiki/{company_id}/progress", response_model=ProgressOut)
def wiki_progress(company_id: str) -> ProgressOut:
    """구축 진행(SPEC F1-1-9 · S1). **파일별로 따로 말한다**(F1-1-8).

    **아무것도 안 올렸어도 200 이고 단계 다섯이 온다.** 처음 온 사람도 무엇이 일어날지
    먼저 볼 수 있어야 한다(DESIGN.md §7-5).

    응답의 `running` 이 화면에 "계속 물어볼지"를 말한다. 이 값 없이는 `chunked` 가
    "다음 차례"인지 "추출기가 몰라서 되돌아온 것"인지 구분되지 않는다 — `wiki/progress.py`.
    """
    with SessionFactory() as s:
        return wiki_service.get_progress(s, company_id, running=jobs.running(_job_key(company_id)))


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
