"""제품 API. 사용자 앱(`web/`)이 이걸 부른다.

**admin 과 별개 프로세스다**(ADR-0023). 포트도 다르다 — admin 8000, 여기 8100.

    uv run uvicorn finnect.api.app:app --reload --port 8100
"""

from __future__ import annotations

import base64
import binascii
import secrets
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from sqlalchemy import select

from finnect.api import account_service, admin_service, draft_service, service, wiki_service
from finnect.api.account_schemas import AccountIn, AccountOut
from finnect.api.admin_schemas import (
    AdminAttachmentsOut,
    AdminAttachOut,
    AdminIngestOut,
    AdminNoticeDetailOut,
    AdminNoticeListOut,
    AdminWikiOut,
    AttachProgressOut,
    IngestTriggerOut,
    JobOutcomeOut,
    WikiPurgeOut,
)
from finnect.api.schemas import (
    DraftItemEditIn,
    DraftItemOut,
    DraftOut,
    DraftStartOut,
    NoticeDetailOut,
    NoticeDocumentsOut,
    NoticeListOut,
    RecommendationsOut,
)
from finnect.api.wiki_schemas import ProfileOut, ProgressOut, UploadOut, WikiOut
from finnect.config import settings
from finnect.db import SessionFactory
from finnect.ingest import jobs
from finnect.models import (
    AttachmentFile,
    CompanyAccount,
    Document,
    UserFile,
    UserFileStatus,
)
from finnect.wiki import storage

app = FastAPI(title="finnect API", docs_url="/docs", redoc_url=None)

#: 토큰 없이 여는 경로. 살아 있는지만 답하고 아무것도 흘리지 않는다.
_OPEN = frozenset({"/healthz"})


#: 운영 경로. **접두사 하나로 판단한다** — 라우트마다 의존성을 다는 것과 달리
#: 새 경로를 더할 때 **잊을 수가 없다**. `tests/test_admin_auth.py` 가 그것을 잠근다.
_ADMIN_PREFIX = "/api/admin/"


@app.middleware("http")
async def require_admin(request: Request, call_next):
    """운영 경로에 HTTP Basic 을 건다([ADR-0067](
    ../../docs/adr/0067-운영-화면을-basic-으로-막는다.md)).

    **`require_token` 보다 안쪽이다.** 아래에서 먼저 더해서 그렇게 된다 — Starlette 은
    나중에 더한 것이 바깥이라 순서가 CORS → `require_token` → 여기 → 라우트다.
    바깥 문이 "이 API 에 말을 걸어도 되나"이고 여기가 "운영 자료를 봐도 되나"라,
    **토큰이 없는 요청은 Basic 창을 보기 전에 막힌다.**

    **설정이 비어 있으면 503 이다.** `api_token` 처럼 조용히 검사를 끄지 않는다 —
    이 경로는 사용자 것이 아니라서 잊고 비워 두면 닫히는 쪽이어야 한다
    (`ingest_trigger_token` 과 같은 규칙).

    **`WWW-Authenticate` 를 낸다.** 없으면 브라우저가 아이디·비밀번호를 물을 자리를
    모른다 — 화면(`web/proxy.ts`)이 같은 자격으로 같은 창을 띄운다.
    """
    if not request.url.path.startswith(_ADMIN_PREFIX):
        return await call_next(request)

    if not settings.admin_user or not settings.admin_password:
        return JSONResponse({"detail": "이 배포에 운영 자격이 설정돼 있지 않다"}, status_code=503)

    if not _basic_ok(request.headers.get("authorization", "")):
        # **무엇이 틀렸는지 나누지 않는다** — `require_token` 과 같은 이유다.
        return JSONResponse(
            {"detail": "운영 자격이 없거나 틀렸어요"},
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="finnect admin", charset="UTF-8"'},
        )
    return await call_next(request)


def _basic_ok(header: str) -> bool:
    """`Authorization: Basic <base64(user:pass)>` 를 대조한다.

    **둘 다 비교하고 중간에 안 빠져나온다.** 아이디에서 먼저 돌아서면 "그 아이디는
    있다"가 응답 시간에 새어 나온다.

    **비ASCII 와 깨진 base64 에서 500 이 나면 안 된다.** 값이 사람이 치는 것이라
    실제로 들어온다 — `require_token` 이 바이트로 바꿔 넣는 것과 같은 자리다.
    """
    scheme, _, raw = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        user, _, password = base64.b64decode(raw, validate=True).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    ok_user = secrets.compare_digest(user.encode(), settings.admin_user.encode())
    ok_password = secrets.compare_digest(password.encode(), settings.admin_password.encode())
    return ok_user and ok_password


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
    # **쓰기가 넷이다** — 올리기(plan/15) · 초안 만들기 · 초안 고치기(plan/21) ·
    # 수집 실행(ADR-0065). `PUT` 이 붙으면서 preflight 가 실제로 돈다.
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """살아 있나. **토큰 없이 열려 있다**(`_OPEN`).

    systemd 와 리버스 프록시가 물어보는 자리다. DB 를 건드리지 않는다 — DB 가 잠깐
    흔들릴 때 프로세스까지 재시작되면 복구가 더 느려진다.
    """
    return {"status": "ok"}


@app.get(
    "/api/companies/{company_id}/recommendations", response_model=RecommendationsOut
)
def recommendations(company_id: str) -> RecommendationsOut:
    """추천 세 건 (plan/17 T-0075).

    `DESIGN.md` §6.1 의 두 섹션 중 위쪽이다. 아래쪽(전체 공고 · 마감 임박순)은
    `/api/notices` 가 그대로 낸다 — **위키가 없어도 그쪽은 뜬다.**

    **404 를 내지 않는다.** 판정이 안 돌았으면 `computed: false` 로 답한다 —
    화면이 "아직 없어요" 와 "맞는 것이 없어요" 를 다르게 말해야 한다.
    """
    with SessionFactory() as s:
        return service.recommendations(s, company_id)


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
def notice(source: str, external_id: str, company: str = "") -> NoticeDetailOut:
    """공고 하나.

    **`company` 는 선택이다.** 주면 `fit`(왜 맞는지)이 같이 오고, 안 주면 `None`
    이라 화면이 그 자리를 안 그린다 — 인증이 없어서 부르는 쪽이 누구인지 말한다.

    **자격은 안 낸다**(ADR-0003). 못 넘는 공고는 목록에서 빠지는 것으로 이미
    답했고, 상세에 대조표를 두면 사용자에게 우리 일을 떠넘긴다.
    """
    if source not in service.SOURCES:
        raise HTTPException(404, f"모르는 출처: {source}")
    with SessionFactory() as s:
        found = service.get_notice(s, source, external_id, company_id=company)
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


#: 미리보기가 여는 포맷. **여기 없는 것은 안 내보낸다** — 뷰어가 못 여는 파일을
#: 굳이 흘려 보낼 이유가 없고, `zip` 은 안에 뭐가 들었는지 우리가 모른다.
_VIEWABLE: dict[str, str] = {
    "hwp": "application/x-hwp",
    "hwpx": "application/vnd.hancom.hwpx",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@app.get("/api/attachments/{sha256}/file")
def attachment_bytes(sha256: str) -> FileResponse:
    """첨부 원본 바이트. **미리보기(rhwp)가 이걸 읽는다.**

    파일은 이미 `data/attachments/<sha[:2]>/<sha>` 에 있는데 그걸 HTTP 로 내주는
    자리가 없었다. 브라우저는 디스크를 못 읽으므로 이 경로가 필요하다.

    **원본 URL(`attachment.url`)로 보내지 않는다.** 다른 출처라 CORS 에 막히고,
    그 URL 은 브라우저 UA·Referer 를 요구하며 **오류를 HTTP 200 + HTML 로 준다**
    (CLAUDE.md 함정). 오류 페이지가 hwp 로 둔갑해 뷰어에 들어간다.

    **sha256 을 반드시 검사한다.** 경로의 일부로 쓰이므로 `../` 가 섞이면 저장소
    밖 파일이 나간다. 64자 16진수만 통과시킨다.

    **DB 에 있는 첨부만 내보낸다.** 안 그러면 해시를 아는 사람이 저장소에 그 파일이
    있는지 물어볼 수 있는 창구가 된다.

    없을 때 404 와 503 을 가른다. **디렉터리 자체가 없으면 배포본에 디스크가 없는
    것**이고(ADR-0034 와 같은 자리), 디렉터리는 있는데 파일이 없으면 `--only` 로
    안 받아 둔 것이다. 둘을 같은 코드로 답하면 어느 쪽인지 못 가린다.
    """
    from finnect.attach import store

    if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
        raise HTTPException(400, "첨부 식별자가 sha256 이 아니에요")

    with SessionFactory() as s:
        row = s.scalars(
            select(AttachmentFile).where(AttachmentFile.sha256 == sha256).limit(1)
        ).first()
        if row is None:
            raise HTTPException(404, "모르는 첨부예요")
        ext = (row.detected_ext or "").lower()
        name = row.server_filename or f"{sha256[:12]}.{ext or 'bin'}"

    if ext not in _VIEWABLE:
        raise HTTPException(415, f"미리보기가 못 여는 포맷이에요: {ext or '모름'}")

    if not settings.attachment_dir.exists():
        raise HTTPException(503, "이 서버에는 첨부 원본이 없어요")

    path = store.abs_path(store.rel_path(sha256))
    if not path.is_file():
        raise HTTPException(404, "아직 안 받아 둔 첨부예요")

    return FileResponse(
        path,
        media_type=_VIEWABLE[ext],
        # **`inline` 이다.** 기본값(`attachment`)이면 미리보기를 누를 때마다 파일이
        # 내려받아진다 — 뷰어가 읽을 바이트를 주는 것이지 저장시키는 것이 아니다.
        content_disposition_type="inline",
        filename=name,
    )


@app.get("/api/notices/{source}/{external_id}/draft", response_model=DraftOut)
def notice_draft(source: str, external_id: str, company: str) -> DraftOut:
    """이 회사가 이 공고에 대해 쓴 초안 (plan/16 · F6).

    **없으면 빈 목록이고 404 가 아니다.** 아직 안 쓴 것과 쓸 수 없는 것을 화면이
    같은 자리에서 말해야 한다 — `pending_documents` 가 "서술형 양식은 있는데 초안이
    아직 없다" 를 센다.

    **읽기만 한다.** 만드는 것은 아래 `POST` 이고, 그쪽이 `finnect.draft` 를
    **함수 안에서** 임포트한다 — 이 모듈 최상단에 두면 `llm` 과 `httpx` 가 딸려 와
    읽기만 담은 배포본에서 죽는다(ADR-0054 결정 2).

    `running` 이 **「아직 안 눌렀다」와 「누르고 기다리는 중」을 가른다.** 이 값 없이
    빈 목록만 보면 화면이 둘을 같은 말로 그린다.

    `status` 여섯 중 **물어볼 자리는 `blank` 하나다**(F6-6). `no_needs` 는 상위
    묶음이고 `yielded` 는 다른 항목이 그 재료를 맡은 것이다 — 셋을 섞으면 화면이
    사용자에게 이미 아는 것을 묻는다.
    """
    if not company:
        raise HTTPException(400, "company 를 주세요")
    with SessionFactory() as s:
        return draft_service.notice_draft(
            s,
            company,
            source,
            external_id,
            running=jobs.running(_draft_key(company, source, external_id)),
        )


@app.get("/api/notices/{source}/{external_id}/documents/{document_id}/filled")
def filled_document(
    source: str, external_id: str, document_id: int, company: str
) -> FileResponse:
    """초안을 넣어 **채운 원본 파일** (plan/24 T-0155 · ADR-0060).

    레포 첫 줄이 「들어가면 문서가 이미 써져 있다」인데, 그 문서가 파일로 나가는
    자리다. 화면의 오른쪽 단이 원본 대신 이것을 연다.

    **저장하지 않는다.** 요청마다 만든다 — 초안이 바뀌면 파일이 낡고, 둘 중 어느
    쪽이 정본인지 정할 근거가 없다(위키 마크다운과 같은 자리). LLM 을 안 부르므로
    파일 하나를 여닫는 값이면 된다.

    **읽기라 쓰기 API 셋에 안 든다**(`tests/test_draft_start.py` 가 잠근 그 셋).
    이 경로는 아무것도 안 바꾼다.

    **못 채운 칸을 헤더로 같이 준다.** 조용히 남기면 사용자가 `000-0000-0000` 을
    그대로 제출한다 — hwp 는 안내문이 든 칸을 못 덮어써서 그 수가 많다.

    **`finnect.forms` 를 함수 안에서 임포트한다.** 최상단에 두면 `import
    finnect.api.app` 이 hwp 경로에서 JVM 을 끌고 온다(ADR-0034 와 같은 함정).
    """
    if not company:
        raise HTTPException(400, "company 를 주세요")

    import os
    import tempfile

    from finnect.forms import SUPPORTED, UnsupportedFormat
    from finnect.forms.base import FormsUnavailable
    from finnect.forms.service import fill_document

    with SessionFactory() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise HTTPException(404, "모르는 문서예요")
        ext = (
            s.scalar(
                select(AttachmentFile.detected_ext).where(
                    AttachmentFile.sha256 == doc.sha256
                )
            )
            or ""
        ).lower()
        if ext not in SUPPORTED:
            raise HTTPException(415, f"이 포맷은 아직 못 채워요: {ext or '모름'}")

        # **임시 파일에 쓴다.** 응답이 나간 뒤 지워도 되지만, `FileResponse` 가
        # 읽는 동안은 살아 있어야 해서 컨텍스트 매니저로 안 닫고 OS 에 맡긴다.
        fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
        os.close(fd)
        try:
            report = fill_document(
                s, company, source, external_id, document_id, tmp_path
            )
        except FileNotFoundError as e:
            raise HTTPException(404, "원본 파일이 이 서버에 없어요") from e
        except (UnsupportedFormat, FormsUnavailable) as e:
            raise HTTPException(415, str(e)) from e

    return FileResponse(
        tmp_path,
        media_type=_VIEWABLE.get(ext, "application/octet-stream"),
        content_disposition_type="inline",
        filename=f"{doc.title[:40]}.{ext}",
        headers={
            "X-Finnect-Filled": str(report.filled),
            "X-Finnect-Left": str(report.refused + report.no_anchor),
        },
    )


def _draft_key(company: str, source: str, external_id: str) -> str:
    """초안 락 키 (ADR-0054 결정 3·4).

    **`(회사, 공고)` 다.** 위키 빌드는 회사 단위로 잠그는데 저기는 사실이 회사
    하나의 표에 병합돼서다. 초안은 `draft` 유니크 키가 `(회사, 공고, 문서)` 라
    **같은 회사가 공고 둘을 같이 쓰는 것은 경합할 자리가 없다.**

    **`hash()` 를 안 쓴다.** `PYTHONHASHSEED` 가 프로세스마다 달라 둘 다 통과한다
    (plan/12 T-0094 가 밟은 함정).
    """
    return f"draft:{company}:{source}:{external_id}"


@app.post(
    "/api/notices/{source}/{external_id}/draft",
    response_model=DraftStartOut,
    status_code=202,
)
def start_draft(
    source: str, external_id: str, company: str, redo: bool = False
) -> DraftStartOut:
    """초안을 쓰기 시작한다 (plan/21 T-0121 · ADR-0054).

    **202 다.** 시작만 하고 답한다 — 항목 수십 개를 다 쓰고 답하면 요청이 몇 분씩
    묶인다. 올리기(`POST …/files`)와 같은 모양이고, 화면은 `GET …/draft` 의
    `running` 으로 따라온다.

    **`redo` 가 다시 쓰기다**(T-0161 · [ADR-0062](
    ../../../docs/adr/0062-다시-쓰기가-고친-글을-지우되-먼저-알린다.md)). 없으면 이미
    초안이 있는 양식을 **LLM 을 부르기 전에** 건너뛴다 — 그전에는 저장 직전에 걸러서
    배분과 집필을 다 부르고 결과를 버렸다. 있으면 그 양식의 항목을 지우고 다시 쓰는데
    **사람이 고친 글도 같이 사라진다.** 무엇이 사라지는지 말하는 것은 화면 몫이다.

    **경로가 안 늘어난다.** 쿼리 파라미터라 쓰기 API 는 여전히 셋이고
    `tests/test_draft_start.py` 가 잠근 목록이 그대로다.

    **거절이 오류가 아니다.** 이미 돌고 있으면 `started: false` 에 이유를 담아
    202 로 답한다. 409 로 올리면 화면이 오류 상태를 그리는데, 두 번 누른 사람에게
    보여 줄 것은 오류가 아니라 **지금 돌고 있다는 사실**이다.

    **503 을 안 낸다.** 올리기의 503 은 로컬 디스크가 없어서였다(ADR-0034). 초안은
    디스크를 안 쓰고 DB 와 LLM 만 쓴다 — 키가 없으면 `started: false` 에 그 이유가
    그대로 실린다. **조용히 빈 초안을 만들지 않는다.**
    """
    if not company:
        raise HTTPException(400, "company 를 주세요")
    if source not in service.SOURCES:
        raise HTTPException(404, f"모르는 출처: {source}")

    key = _draft_key(company, source, external_id)
    launch = jobs.launch(key, lambda: _write_draft(company, source, external_id, redo))

    with SessionFactory() as s:
        draft = draft_service.notice_draft(
            s, company, source, external_id, running=jobs.running(key)
        )
    return DraftStartOut(started=launch.started, reason=launch.reason, draft=draft)


def _write_draft(company: str, source: str, external_id: str, redo: bool = False) -> None:
    """스레드 안에서 도는 집필. **여기서만 `finnect.draft` 를 임포트한다.**

    최상단에 두면 `import finnect.api.app` 이 `llm` 을 끌고 오고, 그러면 로컬은
    통과하고 배포본만 죽는다 — `wiki.service` 를 함수 안에서 부르는 것과 같은
    이유다(ADR-0034 · CLAUDE.md 함정).
    """
    from finnect.draft import service as writer
    from finnect.trace import flush

    try:
        writer.build_draft(company, source, external_id, redo=redo)
    finally:
        # **데몬 스레드라 안 부르면 남은 추적이 사라진다**(ADR-0038 · CLI 와 같다).
        # `finally` 인 이유는 실패한 초안일수록 추적이 필요해서다.
        flush()


@app.put(
    "/api/notices/{source}/{external_id}/draft/items/{document_item_id}",
    response_model=DraftItemOut,
)
def edit_draft_item(
    source: str,
    external_id: str,
    document_item_id: int,
    body: DraftItemEditIn,
    company: str,
) -> DraftItemOut:
    """사람이 고친 글을 저장한다 (plan/21 T-0123 · ADR-0055).

    **`body` 를 안 덮는다.** 집필기의 출력은 그대로 두고 `edited_body` 에 얹는다 —
    되돌릴 자리가 남아야 하고, `draft_evidence` 의 문단 번호가 사람 편집을 따라
    어긋나면 안 된다.

    `text: null` 이 **되돌리기**다. 빈 문자열은 되돌리기가 아니라 일부러 비운
    것이라 그대로 저장한다.

    **404 를 낸다.** 조회와 반대다 — 저쪽은 「아직 없다」를 말해야 하지만 여기는
    없는 항목에 쓰라는 요청이라 원인이 요청 쪽에 있다.
    """
    if not company:
        raise HTTPException(400, "company 를 주세요")
    with SessionFactory() as s:
        try:
            out = draft_service.edit_item(
                s, company, source, external_id, document_item_id, body.text
            )
        except draft_service.ItemNotFound as e:
            raise HTTPException(404, str(e)) from e
        s.commit()
    return out


# --- 베타 입장 게이트 (ADR-0066) --------------------------------------------


@app.post("/api/account", response_model=AccountOut)
def account_enter(body: AccountIn) -> AccountOut:
    """이름과 비밀번호를 `company_id` 로 바꾼다.

    **`SPEC.md` §6 이 계정을 범위 밖에 두고 있고 이것이 그 예외다**(ADR-0066).
    베타 테스터가 여럿이 되면서 「누구의 위키인가」를 주소(`?company=`)로만 정하던 것이
    한계에 왔다 — 링크 하나가 파라미터를 빠뜨리면 남의 위키에 파일이 쌓인다.

    **가입과 로그인을 안 나눈다.** 처음 보는 이름이면 만들고 아는 이름이면 대조한다.

    **비밀번호가 틀린 것과 없는 이름을 구분해 주지 않는다** — 나누면 어떤 이름이
    이미 쓰이는지가 새어 나간다. `require_token` 이 "헤더가 없다" 와 "값이 다르다" 를
    안 가르는 것과 같은 이유다.
    """
    name = body.name.strip()
    if not name or not body.password:
        raise HTTPException(400, "회사 이름과 비밀번호를 둘 다 적어 주세요")

    with SessionFactory() as s:
        try:
            row = account_service.enter(s, name, body.password)
        except account_service.WrongPassword as e:
            raise HTTPException(401, "그 이름에 이 비밀번호가 아니에요") from e
        out = AccountOut(company_id=row.company_id, name=row.name)
        s.commit()
    return out


@app.get("/api/account/{company_id}", response_model=AccountOut)
def account_of(company_id: str) -> AccountOut:
    """발급된 키로 **입장 때 적은 이름**을 되찾는다.

    쓰는 자리는 지금 하나다 — S4 가 채운 양식을 `파일명_회사이름` 으로 내려받는다.
    파일이 사용자 디스크에 남으므로 `c_8f6d525e7b97` 이 아니라 사람이 적은 이름이라야
    한다.

    **새어 나가는 것이 없다.** `company_id` 를 아는 쪽은 이미 그 회사의 위키와 초안을
    통째로 열 수 있다(위 «사업 위키» 주석) — 이름은 그보다 적게 말한다.

    **모르는 키는 404 다.** 빈 이름을 돌려주면 부르는 쪽이 「이름이 없는 회사」와
    「없는 회사」를 못 가른다.
    """
    with SessionFactory() as s:
        row = s.scalars(
            select(CompanyAccount).where(CompanyAccount.company_id == company_id)
        ).one_or_none()
        if row is None:
            raise HTTPException(404, "모르는 회사예요")
        return AccountOut(company_id=row.company_id, name=row.name)


# --- 사업 위키 (S7) ---------------------------------------------------------
#
# **`company_id` 를 경로로 받는다.** 값을 정하는 것은 위의 입장 게이트이고, 여기까지
# 오는 길에 그 값이 쿠키에 실린다(`web/middleware.ts`). **그 쿠키가 세션이 아니다** —
# 이 API 는 여전히 부르는 쪽이 말하는 `company_id` 를 그대로 믿는다.
#
# **격리가 이 인자 하나에 걸려 있다.** `wiki/storage.py` 와 `chunk.company_id` 가 같은
# 값을 쓰고, 서비스가 그 값으로만 조회한다. 지금 이 API 는 누구의 위키든 열어 준다.


@app.get("/api/wiki/{company_id}", response_model=WikiOut)
def wiki(company_id: str) -> WikiOut:
    """사업 위키 한 장.

    **위키가 없어도 200 이고 카테고리 열이 온다**(ADR-0056). 빈 자리도 사실이라 화면이
    무엇을 물어야 하는지 알 수 있어야 한다(DESIGN.md §7-5). 404 는 회사가 없을 때가
    아니라 이 경로가 없을 때만 난다.

    **매칭 정보(트랙 B)는 여기 안 온다.** `/api/company/{company_id}` 가 그 자리다 —
    그래프와 회사 정보는 다른 화면이고 서로를 모른다.

    **추출기가 아직 스텁이라 픽스처 밖 회사는 자리만 비어서 온다**(ADR-0031).
    응답의 `extractor` 가 무엇이 뽑았는지 말한다.
    """
    with SessionFactory() as s:
        return wiki_service.get_wiki(s, company_id)


@app.get("/api/company/{company_id}", response_model=ProfileOut)
def company(company_id: str) -> ProfileOut:
    """회사 정보 한 장(트랙 B · ADR-0056 결정 1·5).

    **열다섯이 항상 온다.** 빈 칸이 물어볼 자리이고(ADR-0028), 질문이 고정이라 못 채운
    것을 셀 수 있다 — 트랙 A 는 정답지가 없어 이걸 못 한다.

    **그래프에 안 뜬다.** 자격 판별(M1)이 읽는 것과 사람이 읽는 위키는 다른 물건이다.
    """
    with SessionFactory() as s:
        return wiki_service.get_profile(s, company_id)


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
    #
    # **다른 프로세스가 같은 회사를 세우고 있으면 거절된다**(plan/12 T-0094). 해독은 이미
    # 끝났고 파일이 `chunked` 로 남아 있으므로 **다음 올리기나 `--build` 가 이어받는다** —
    # 스레드 밖으로 던지면 `jobs.launch` 가 트레이스백만 찍고 사용자는 이유를 못 본다.
    try:
        with SessionFactory() as s:
            build.build_company(s, company_id)
            s.commit()
    except build.BuildBusy as e:
        for fid in file_ids:
            with SessionFactory() as s:
                uf = s.get(UserFile, fid)
                if uf is not None and uf.status == UserFileStatus.CHUNKED:
                    uf.extract_error = str(e)
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
    # **시연이면 파일을 안 읽고 스냅샷을 앉힌다**(`wiki/demo.py`). 위키를 세우는 데 241초가
    # 걸려서 시연에서 못 기다리고, 미리 세워 두면 시작할 때 이미 노드가 서 있어 「던지면
    # 위키가 생긴다」를 못 보여 준다. 설정이 비어 있으면 아래가 평소대로 돈다.
    #
    # **`writable()` 앞에 둔다.** 시연은 디스크에 아무것도 안 쓰므로 그 가드가 필요 없다.
    if settings.demo_snapshot is not None:
        return _demo_upload(company_id, files)

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
                # **묶음이면 안쪽 파일이 각자 행을 갖는다**(T-0102). 그것들도 `pending`
                # 에 들어가야 뒤이어 도는 빌드가 읽는다 — 묶음 자신만 넣으면 안쪽이
                # `uploaded` 로 남아 다음 올리기까지 아무 일도 안 일어난다.
                for uf, what in user_files.receive_many(s, company_id, data, name):
                    if what == "duplicate":
                        duplicate += 1
                    elif uf.status != UserFileStatus.UNPACKED:
                        # 묶음 자신은 읽을 것이 없다. 넣으면 빌드가 헛돈다
                        received.append(uf.id)
                s.commit()
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


def _demo_upload(company_id: str, files: list[UploadFile]) -> UploadOut:
    """시연: 받은 파일을 **안 읽고** 떠 둔 위키를 그대로 앉힌다.

    **파일 내용을 안 본다.** 무엇을 던지든 나린데이터 위키가 선다 — 시연 중에 엉뚱한
    파일을 골라 빈 화면이 나오는 것을 막으려는 것이고, `DEMO_PICKS` 가 회사를 안 보는
    것과 같은 이유다.

    **`started` 가 거짓이다.** 뒤에서 도는 것이 없으므로 화면이 진행을 물으러 오면 안
    된다 — 이미 다 끝난 상태를 응답에 실어 보낸다.

    스냅샷을 못 읽으면 **500 으로 터뜨린다.** 시연 설정이 켜졌는데 파일이 없는 것은 설정
    실수이고, 조용히 빈 위키로 넘어가면 화면이 "사실을 못 뽑았어요" 를 말한다.
    """
    from finnect.wiki import demo

    assert settings.demo_snapshot is not None  # noqa: S101 — 부르는 자리가 이미 확인했다
    try:
        snap = demo.read(settings.demo_snapshot)
    except demo.SnapshotError as e:
        raise HTTPException(500, str(e)) from e

    with SessionFactory() as s:
        demo.put(s, company_id, snap)
        s.commit()

    with SessionFactory() as s:
        progress = wiki_service.get_progress(s, company_id, running=False)

    return UploadOut(
        received=len(files),
        duplicate=0,
        rejected=[],
        started=False,
        reason="떠 둔 위키를 그대로 앉혔어요",
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


# --- 운영 화면 (ADR-0027 · 실행은 ADR-0065 · 0071 · 0072) --------------------
#
# **조회 여섯은 GET 이고 쓰기가 셋이다** — 수집 실행 · 첨부 받기 · 위키 지우기.
# ADR-0027 은 실행을 "서버리스가 데몬 스레드를 못 돌린다"는 이유로 로컬 CLI 에만
# 남겼는데, ADR-0035 로 이 API 자체가 서버리스에서 이 서버의 상시 프로세스로
# 내려오면서 그 전제가 없어졌다. `jobs.py` 의 락과 진행 상태가 이 프로세스
# 안에 그대로 산다 — 배포본이 자기 자신을 궁금해할 수 있게 됐다.
#
# **셋째는 성질이 다르다.** 앞의 둘은 시작하는 일이고(202 · `started`) 위키 지우기는
# **되돌릴 수 없이 지우는 일**이다(200 · 거절이 409). ADR-0072 결정 6 이 그 자리다.
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
    """수집 실행 기록과 지금 진행 상태."""
    with SessionFactory() as s:
        return admin_service.ingest(s)


def _require_trigger_token(request: Request) -> None:
    """실행 버튼을 눌러도 되는 사람인지([ADR-0065](
    ../../docs/adr/0065-수집-실행을-배포-api-에-연다.md)).

    **`x-finnect-token` 과는 다른 문이다.** 저 토큰은 Next.js 서버가 이 API 로
    들어오는 문이라 운영 화면을 보는 누구나 이미 그 문을 통과한 뒤다. 여기는 **버튼을
    눌러도 되는 사람인지**를 묻는다 — 수집도 첨부 받기도 외부 서버에 실제 요청을
    수천 번 내보내고 쿼터를 쓴다.

    **쓰기 둘이 같은 문을 쓴다.** 토큰을 하나 더 만들면 "수집은 되는데 첨부는 안 되는
    사람" 이 생기는데, 그 구분이 필요하다는 근거가 없다 — 둘 다 운영자가 이 서버에서
    돌리는 같은 종류의 일이다([ADR-0071](
    ../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).

    **설정 안 돼 있으면 503 이다.** `api_token` 처럼 비어 있을 때 조용히 검사를
    끄지 않는다 — 잊고 비워 두면 열리는 쪽이 아니라 닫히는 쪽이어야 한다.
    """
    if not settings.ingest_trigger_token:
        raise HTTPException(503, "이 배포에 실행 토큰이 설정돼 있지 않다")
    sent = request.headers.get("x-ingest-trigger-token", "")
    if not secrets.compare_digest(sent.encode(), settings.ingest_trigger_token.encode()):
        raise HTTPException(401, "실행 토큰이 없거나 틀렸어요")


@app.post(
    "/api/admin/ingest/run/{source}",
    response_model=IngestTriggerOut,
    tags=["admin"],
)
def admin_ingest_run(
    source: str, request: Request, full: bool = False, limit: int | None = None
) -> IngestTriggerOut:
    """수집을 시작한다(ADR-0065). 응답을 기다리지 않는다 — `jobs.launch` 가 스레드로 뗀다.

    문은 `_require_trigger_token` 이 지킨다. 외부 정부 API 에 실제 요청을 내보내고
    쿼터를 쓰기 때문이다(K-Startup 일 한도 10,000회 · 기업마당 키는 IP 에 묶일 수 있다).
    """
    _require_trigger_token(request)

    # 서버리스 시절의 흔적이다 — 최상단에 두면 이 모듈을 그냥 import 하는 것만으로
    # httpx 가 딸려 온다. 지금은 배포본에도 httpx 가 있지만(ADR-0065), 굳이 그
    # 자유를 새로 안 쓴다. `wiki.service` 도 같은 이유로 함수 안에서 임포트한다.
    from finnect.ingest import service as ingest_service

    if source not in ingest_service.BY_NAME:
        raise HTTPException(404, f"모르는 출처: {source}")

    # **`full` 하나가 필터 넷을 다 끈다.** 화면 체크박스가 그 하나다 — 나눠 두면
    # 「어떤 조합으로 받은 코퍼스인지」가 실행마다 달라져 재현이 안 된다.
    result = ingest_service.launch(
        source,
        only_open=not full,
        skip_mlsfc=not full,
        require_form=not full,
        sample=1 if full else None,  # None 이면 출처 기본값(기업마당 10 · K-Startup 3)
        limit=limit,
        trigger="admin",
    )
    return IngestTriggerOut(started=result.started, reason=result.reason)


@app.get("/api/admin/attach", response_model=AdminAttachOut, tags=["admin"])
def admin_attach() -> AdminAttachOut:
    """첨부 받기 카드 — 지금 돌고 있나, 아직 안 받은 것이 몇 건인가([ADR-0071](
    ../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).

    **`/api/admin/attachments` 와 따로 둔다.** 저 경로는 집계 다섯을 훑는 무거운
    질의라 실행 중에 1.5초마다 부를 것이 아니다. 여기는 URL 표만 센다.

    **`attach.service` 를 함수 안에서 임포트한다.** `admin_ingest_run` 과 같은
    이유이고, 이 계산이 `api/admin_service.py` 에 없는 것도 같은 이유다 — 저 모듈은
    파서와 httpx 를 안 끌고 오는 것이 계약이고 `tests/test_admin_api.py` 가 잠근다.

    **셈을 여기 베끼지 않는다.** `backlog()` 가 `run()` 이 대상을 고르는 바로 그
    함수를 쓴다 — 화면이 527건이라고 했는데 눌러 보니 3,354건이면 그 화면은 없느니만
    못하다. `coverage()` 를 베낀 자리가 이미 하나 있고 그것을 테스트가 지키고 있다.
    """
    from finnect.attach import service as attach_service

    with SessionFactory() as s:
        back = attach_service.backlog(s)

    p = jobs.progress_of(attach_service.JOB_KEY)
    last = jobs.outcome_of(attach_service.JOB_KEY)
    return AdminAttachOut(
        running=jobs.running(attach_service.JOB_KEY),
        progress=(
            None
            if p is None
            else AttachProgressOut(
                total=p.total,
                done=p.done,
                skipped=p.skipped,
                bytes_in=p.bytes_in,
                target=p.target,
                goal=p.goal,
                percent=p.percent,
            )
        ),
        pending=back.pending,
        urls=back.urls,
        last=None if last is None else JobOutcomeOut(ok=last.ok, detail=last.detail),
    )


@app.post("/api/admin/attach/run", response_model=IngestTriggerOut, tags=["admin"])
def admin_attach_run(
    request: Request, limit: int | None = None, redo: bool = False
) -> IngestTriggerOut:
    """첨부를 내려받아 해독한다. **아직 안 받은 것만 대상이다**([ADR-0071](
    ../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).

    수집과 **같은 문**을 지난다(`_require_trigger_token`). 이 동작도 외부 서버에
    실제 요청을 수천 번 내보내고 디스크를 GB 단위로 쓴다.

    **출처를 안 가른다.** `finnect.attach` CLI 에는 `--source` 가 있지만 버튼에는
    안 붙였다 — 운영자가 화면에서 고를 이유가 아직 없고, 락이 어차피 하나라 둘을
    동시에 못 돌린다. 필요해지면 그때 쿼리 하나를 더한다.

    **`only` 는 여기 없다.** 그 목록은 `notice-filter/` 가 만드는 것이고 파일로
    온다 — 화면에서 파일을 받는 경로를 여는 것은 다른 결정이다.

    `redo` 는 파서를 고쳤을 때다. 디스크에 있는 파일은 다시 안 받고 해독만 다시 한다.
    **그때는 이미 받아 둔 것도 전부 대상이 된다** — 그것이 `redo` 의 뜻이다.
    """
    _require_trigger_token(request)
    if limit is not None and limit < 1:
        raise HTTPException(400, "건수는 1 이상이어야 해요")

    from finnect.attach import service as attach_service

    result = attach_service.launch(limit=limit, redo=redo)
    return IngestTriggerOut(started=result.started, reason=result.reason)


@app.get("/api/admin/wiki", response_model=AdminWikiOut, tags=["admin"])
def admin_wiki() -> AdminWikiOut:
    """위키가 서 있는 회사 목록([ADR-0072](
    ../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).

    **`admin_service` 에 있다.** 이 계산은 모델만 읽고 파서도 httpx 도 안 부른다 —
    `attach`·`ingest` 를 저 모듈에서 뺀 이유가 여기는 안 걸린다.
    """
    with SessionFactory() as s:
        return admin_service.wikis(s)


@app.post(
    "/api/admin/wiki/purge/{company_id}",
    response_model=WikiPurgeOut,
    tags=["admin"],
)
def admin_wiki_purge(company_id: str, request: Request) -> WikiPurgeOut:
    """그 회사의 위키를 지운다 — 파일 · 청크 · 사실 · 값 · 노드 · 원본([ADR-0072](
    ../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).

    **`uv run python -m finnect.wiki --company … --purge` 와 같은 함수를 부른다.**
    베끼지 않는 이유는 `attach` 의 `backlog()` 와 같다 — 두 벌이면 한쪽이 반드시 낡고,
    낡은 쪽이 **지우는 코드**다.

    **202 가 아니라 200 이다.** 수집·첨부와 달리 스레드로 안 뗀다 — 지우는 일은 몇
    밀리초라 기다릴 것이 없고, 진행 표가 없으므로 화면이 물으러 올 곳도 없다.

    **문 둘을 겹친다.**

    1. `jobs.running` — 이 프로세스에서 그 회사의 빌드가 도는 중인가. 해독 단계에는
       아래 어드바이저리 락이 아직 안 잡혀 있어서 **이것 없이는 읽는 중인 파일이
       지워진다.**
    2. `wiki.service.purge` 안의 `build.hold` — 다른 프로세스(CLI `--build`)가 세우는
       중인가. `jobs` 의 락은 `threading.Lock` 이라 프로세스를 못 건넌다(plan/12 T-0094).
       **그 락을 여기서 따로 안 잡는다** — 잡는 자리가 지우는 함수 안이라 CLI `--purge`
       도 같은 문을 지난다.

    **거절이 409 다.** 수집·첨부의 「이미 돌고 있어요」는 202 에 `started: false` 인데,
    저건 **시작하는 일**이라 "안 시작했다" 가 답이 된다. 여기는 시작할 것이 없고
    지우거나 안 지우거나 둘뿐이라, 안 지웠으면 그것은 성공이 아니다.
    """
    _require_trigger_token(request)

    if jobs.running(_job_key(company_id)):
        raise HTTPException(409, "지금 그 회사의 위키를 세우고 있어요. 끝나고 다시 눌러 주세요")

    # 최상단에 두면 `import finnect.api.app` 이 pdfplumber 를 끌고 온다 —
    # `admin_ingest_run` · `wiki_upload` 와 같은 이유다(`tests/test_admin_api.py`).
    from finnect.wiki import build
    from finnect.wiki import service as wiki_files

    try:
        with SessionFactory() as s:
            files, facts = wiki_files.purge(s, company_id)
            # **디스크를 커밋 전에 지운다.** 순서를 뒤집으면 행은 없어졌는데 파일이
            # 남는 창이 생기고, 그 파일은 가리키는 행이 없어 아무도 못 찾는다.
            # 반대로 여기서 터지면 롤백돼서 **둘 다 남는다** — 다시 누르면 된다.
            gone = storage.purge(company_id)
            s.commit()
    except build.BuildBusy as e:
        raise HTTPException(409, str(e)) from e
    except storage.IsolationError as e:
        raise HTTPException(400, str(e)) from e

    return WikiPurgeOut(company_id=company_id, files=files, facts=facts, storage=gone)
