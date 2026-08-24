"""파일 하나를 받아 저장 → 해독 → 청크까지(plan/12 T-0043 · T-0047).

**파일별로 독립이다**(SPEC F1-1-8). 전체를 한 트랜잭션으로 묶지 않는다 — 다섯 중 하나가
읽히지 않아도 넷으로 위키가 선다. 부분 성공이 예외가 아니라 정상 상태다.

여기서 사실을 뽑지 않는다. 청크까지가 이 태스크의 끝이고 추출은 T-0045 다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.attach import extract, formats
from finnect.config import settings
from finnect.models import Chunk, ParseStatus, UserFile, UserFileStatus
from finnect.wiki import chunk as chunker
from finnect.wiki import storage, unpack


@dataclass(slots=True)
class IngestReport:
    company_id: str = ""
    files: int = 0
    #: 이번에 처리한 것
    done: int = 0
    #: 이미 있어서 건너뛴 것. 같은 회사가 같은 파일을 다시 올린 경우
    duplicate: int = 0
    failed: int = 0
    needs_review: int = 0
    chunks: int = 0
    status: Counter[str] = field(default_factory=Counter)
    #: (파일명, 사유). **조용히 버리지 않는다**
    problems: list[tuple[str, str]] = field(default_factory=list)


#: 조각에 번호를 붙일지. **경계를 지키는 것과 번호를 붙이는 것은 다른 일이다** —
#: 없는 쪽 번호를 만들어 붙이면 근거가 거짓이 된다.
#:
#: | 포맷 | 경계 | `page` |
#: |---|---|---|
#: | PDF | 쪽 | **찬다.** 쪽이 실재한다 |
#: | PPTX | 슬라이드 | **찬다.** 슬라이드는 쪽처럼 세어진다 |
#: | XLSX | 시트 | **비운다.** 시트는 쪽이 아니다. 이름은 `heading` 이 받는다 |
NUMBERED = {"pdf": True, "pptx": True, "xlsx": False}


def receive(
    session: Session,
    company_id: str,
    data: bytes,
    filename: str,
) -> tuple[UserFile, str]:
    """바이트를 받아 자리를 만든다. **읽지는 않는다.**

    `ingest_file` 에서 갈라낸 앞 절반이다(plan/15 T-0059). 나눈 이유 하나뿐이다 —
    **진행 표시(F1-1-9)가 '받았다'와 '읽었다'를 다른 단계로 말해야 한다.** 붙어 있으면
    다섯 개를 올렸을 때 해독이 끝난 것부터 한 줄씩 나타나고, 그동안 화면은 나머지가
    올라오긴 한 건지 말할 수 없다.

    돌려주는 둘째 값은 `received` 또는 `duplicate` 다.
    """
    sha = storage.digest(data)

    existing = session.scalar(
        select(UserFile).where(UserFile.company_id == company_id, UserFile.sha256 == sha)
    )
    if existing is not None:
        # 같은 회사가 같은 파일을 다시 올렸다. 청크가 두 벌 되지 않게 여기서 멈춘다.
        return existing, "duplicate"

    storage.put(company_id, data)
    # **저장한 파일로 판정한다.** 콘텐츠 주소라 원본과 바이트가 같고, 그래서 업로드처럼
    # 원본 경로가 없는 경우에도 같은 답이 나온다. 이름은 물러날 자리로만 넘긴다.
    ext = formats.detect(storage.abs_path(company_id, sha), filename)

    uf = UserFile(
        company_id=company_id,
        sha256=sha,
        filename=filename,
        byte_size=len(data),
        ext=ext,
        status=UserFileStatus.UPLOADED,
    )
    session.add(uf)
    session.flush()
    return uf, "received"


def receive_many(
    session: Session,
    company_id: str,
    data: bytes,
    filename: str,
) -> list[tuple[UserFile, str]]:
    """바이트 하나를 받아 행 여럿으로. **묶음이면 안쪽까지 편다**(T-0102).

    **첫 항목이 항상 던진 파일 자신이다.** 묶음이어도 제 행으로 남는다 — 사용자가 던진
    것이 목록에서 사라지면 무슨 일이 있었는지 못 본다.

    묶음이 아니면 `receive` 를 한 번 부른 것과 같다. `is_archive` 가 HWPX·DOCX 같은
    문서를 걸러 낸다 — **저것들도 ZIP 이라** 안 걸러 주면 문서 하나가 XML 조각 수십 개가
    된다.

    안쪽 파일도 `(company_id, sha256)` 키를 타므로, 같은 파일을 따로 올린 적이 있으면
    `duplicate` 로 걸린다. 청크가 두 벌 되지 않는다.
    """
    uf, what = receive(session, company_id, data, filename)
    out = [(uf, what)]

    if what == "duplicate" or not unpack.is_archive(data):
        return out

    try:
        got = unpack.expand(data)
    except unpack.BadArchive as e:
        # 묶음인 줄 알았는데 못 열었다. **이 파일만 실패로 남고 예외는 안 나간다**
        uf.status = UserFileStatus.FAILED
        uf.parse_status = ParseStatus.FAILED
        uf.parse_error = str(e)
        uf.chunk_count = 0
        return out

    for member in got.members:
        out.append(receive(session, company_id, member.data, member.name))

    uf.status = UserFileStatus.UNPACKED
    uf.parse_status = ParseStatus.CONTAINER
    uf.parser = "zip/unpack"
    uf.chunk_count = 0
    uf.text_chars = 0
    # **버린 것을 조용히 넘기지 않는다.** 부스러기(`__MACOSX/`)는 사용자 파일이 아니라
    # 말할 것이 없지만, 상한에 걸린 것은 사용자 파일인데 안 넣은 것이라 말해야 한다.
    if got.dropped:
        uf.parse_error = (
            f"{got.dropped}개를 못 풀었다"
            f"(상한: 파일 {settings.user_zip_max_files}개 · 총 {settings.user_zip_max_mb}MB"
            f" · 개당 {settings.user_file_max_mb}MB)"
        )
    session.flush()
    return out


def decode(session: Session, uf: UserFile) -> str:
    """받아 둔 파일을 읽어 청크까지. **원본은 저장소에서 꺼낸다.**

    `ingest_file` 에서 갈라낸 뒤 절반이다. 상태를 `parsing` 으로 올리고 시작하는 것이
    요점이다 — 이 함수가 도는 동안 다른 세션이 그 행을 보면 무엇을 하고 있는지 안다.
    """
    uf.status = UserFileStatus.PARSING
    session.flush()

    path = storage.abs_path(uf.company_id, uf.sha256)
    parsed = extract.parse(
        path, uf.filename, allowed=settings.wiki_formats, use_ocr=settings.user_file_ocr
    )
    uf.parse_status = parsed.status
    uf.parser = parsed.parser
    uf.parse_error = parsed.error
    uf.text_chars = len(parsed.text or "")

    if parsed.status != ParseStatus.OK or not (parsed.text or "").strip():
        # 읽을 수 없는 포맷은 실패, 글자가 안 나온 것은 검토 대기다. **둘은 다르다** —
        # 스캔본은 OCR 이 붙으면 읽힌다(T-0042). 포맷이 없는 것은 안 읽힌다.
        uf.status = (
            UserFileStatus.NEEDS_REVIEW
            if parsed.status == ParseStatus.EMPTY
            else UserFileStatus.FAILED
        )
        uf.chunk_count = 0
        return uf.status

    # **파서가 준 조각을 그대로 쓴다.** 다시 파싱하면 PDF 를 두 번 읽고, OCR 이면
    # 그 비용이 쪽당 십수 초씩 두 배가 된다.
    pages = parsed.pages or [parsed.text or ""]
    # **쪽 수가 아니라 포맷으로 정한다.** 1쪽짜리 PDF 도 그 1쪽이 어딘지 안다 —
    # `len(pages) > 1` 로 걸면 한 장짜리 사업자등록증의 쪽이 NULL 이 된다.
    numbered = NUMBERED.get(uf.ext or "")

    # **청커가 이은 것을 저장한다.** 파서의 `text` 를 저장하면 좌표계가 두 벌이 되고,
    # 이으는 문자가 한 글자만 달라도 모든 청크의 좌표가 어긋난다. 실제로 그랬다.
    text = chunker.join(pages)
    storage.put_text(uf.company_id, uf.sha256, text)
    uf.text_chars = len(text)
    uf.page_count = len(pages) if numbered else None

    pieces = chunker.split(pages, numbered=numbered)
    session.add_all(
        Chunk(
            user_file_id=uf.id,
            company_id=uf.company_id,
            ordinal=p.ordinal,
            text=p.text,
            chars=p.chars,
            char_start=p.char_start,
            char_end=p.char_end,
            page=p.page,
            heading=p.heading,
        )
        for p in pieces
    )
    uf.chunk_count = len(pieces)
    uf.status = UserFileStatus.CHUNKED
    return "done"


def ingest_file(
    session: Session,
    company_id: str,
    path: Path,
    *,
    filename: str | None = None,
) -> list[tuple[UserFile, str]]:
    """파일 하나를 받아 청크까지. `receive_many` 와 `decode` 를 이어 놓은 것이다.

    CLI 가 부르는 자리다. 업로드(plan/15)는 둘을 **따로** 부른다 — 받는 것은 요청 안에서,
    읽는 것은 응답을 보낸 뒤에 한다.

    **경로 하나가 행 여럿이 된다**(T-0102). 묶음이면 안쪽 파일이 각자 선다.

    **예외를 밖으로 던지지 않는 것이 목표가 아니다.** 던지는 것은 호출부(`ingest_files`)가
    받아 그 파일만 실패로 남긴다. 여기서 다 삼키면 원인이 사라진다.
    """
    got = receive_many(session, company_id, path.read_bytes(), filename or path.name)
    out: list[tuple[UserFile, str]] = []
    for uf, what in got:
        if what == "duplicate" or uf.status in (
            UserFileStatus.UNPACKED,
            UserFileStatus.FAILED,
        ):
            # 묶음 자신은 읽을 것이 없다. 안쪽 파일이 각자 읽힌다
            out.append((uf, what))
            continue
        out.append((uf, decode(session, uf)))
    return out


def ingest_files(
    session_factory,  # noqa: ANN001 — SessionFactory 또는 테스트가 준 것
    company_id: str,
    paths: list[Path],
) -> IngestReport:
    """여러 개. **파일 하나가 실패해도 나머지는 진행한다**(F1-1-8).

    파일마다 세션을 따로 연다. 하나가 터져 롤백될 때 앞의 것이 같이 날아가지 않아야 한다.
    """
    report = IngestReport(company_id=company_id, files=len(paths))

    for path in paths:
        try:
            with session_factory() as session:
                got = ingest_file(session, company_id, path)
                session.commit()
                # **경로 하나가 행 여럿일 수 있다**(T-0102). 셈은 행 단위다 —
                # 묶음 하나를 1건으로 세면 안쪽 파일 스무 개가 보고에서 사라진다
                for uf, what in got:
                    report.status[uf.status] += 1
                    report.chunks += uf.chunk_count or 0
                    label = uf.filename
                    if what == "duplicate":
                        report.duplicate += 1
                    elif uf.status == UserFileStatus.CHUNKED:
                        report.done += 1
                    elif uf.status == UserFileStatus.UNPACKED:
                        # 실패가 아니다. 제 할 일을 했고 안쪽 파일이 따로 세어진다.
                        # 못 푼 것이 있으면 그것만 말한다
                        if uf.parse_error:
                            report.problems.append((label, uf.parse_error))
                    elif uf.status == UserFileStatus.NEEDS_REVIEW:
                        report.needs_review += 1
                        report.problems.append((label, uf.parse_status or "글자가 없어요"))
                    else:
                        report.failed += 1
                        report.problems.append(
                            (label, uf.parse_error or uf.parse_status or "실패")
                        )
        except Exception as e:  # noqa: BLE001 — 이 파일만 실패시키고 다음으로 간다
            report.failed += 1
            report.status[UserFileStatus.FAILED] += 1
            report.problems.append((path.name, f"{type(e).__name__}: {e}"))

    return report


def rechunk(session: Session, company_id: str, *, sha256: str | None = None) -> int:
    """청킹 규칙을 고쳤을 때. **원본을 다시 읽지 않는다** — 저장된 `.txt` 로 다시 쪼갠다.

    `attach --redo` 와 같은 성격이다. 쪽 경계가 필요한 PDF 는 원본을 다시 열어야 해서
    거기서만 파일을 만진다.
    """
    q = select(UserFile).where(
        UserFile.company_id == company_id, UserFile.status == UserFileStatus.CHUNKED
    )
    if sha256:
        q = q.where(UserFile.sha256 == sha256)

    total = 0
    for uf in session.scalars(q).all():
        text = storage.read_text(company_id, uf.sha256)
        if text is None:
            continue
        # 다시 쪼갤 때는 저장된 텍스트만 쓴다. **원본을 다시 읽지 않는다** —
        # OCR 을 다시 돌리는 것은 특히 비싸다. 대가로 조각 경계가 사라져 통짜가 된다.
        pages, numbered = [text], None
        session.execute(sa_delete(Chunk).where(Chunk.user_file_id == uf.id))
        pieces = chunker.split(pages, numbered=numbered)
        session.add_all(
            Chunk(
                user_file_id=uf.id,
                company_id=company_id,
                ordinal=p.ordinal,
                text=p.text,
                chars=p.chars,
                char_start=p.char_start,
                char_end=p.char_end,
                page=p.page,
                heading=p.heading,
            )
            for p in pieces
        )
        uf.chunk_count = len(pieces)
        total += len(pieces)
    return total


def purge(session: Session, company_id: str) -> tuple[int, int]:
    """탈퇴. **회사의 것을 전부 지운다** — 파일 · 청크 · 사실 · 근거.

    돌려주는 것은 (지운 파일 수, 지운 사실 수)다. 원본 파일은 `storage.purge` 가 따로 지운다.

    **`wiki_fact` 와 `chunk` 를 여기서 명시적으로 지운다.** `user_file` 에 FK 가 없어서 —
    사실 하나가 파일 여럿을 근거로 들 수 있으니 그게 맞다 — 파일을 지워도 안 따라 지워진다.
    2026-08-18 실제로 그랬다: 탈퇴 뒤 다시 올렸더니 사실 118건이 전부 '이미 있음' 으로
    나왔고, **지웠어야 할 값이 DB 에 그대로 있었다.**

    **세우는 중이면 거절한다**([ADR-0072](
    ../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md) · `BuildBusy`). `build.hold` 가
    잡는 키가 `build_company` 의 것과 같다 — 안 잡으면 `--build` 가 청크를 읽는 동안
    그 행이 지워지고, 그쪽은 **이미 없는 파일을 들고 끝까지 돈다.** 부르는 쪽이 이
    예외를 받아야 한다(CLI 는 exit 1 · API 는 409).

    **초안과 판정은 안 지운다.** `draft`·`notice_fit` 은 `company_id` 를 들지만 여기서
    안 건드린다 — 사람이 고친 글이 거기 있고(ADR-0055), 지우는 자리는 화면의
    「초기화」다(ADR-0062). 사실을 가리키던 근거 행(`draft_evidence`·
    `notice_fit_evidence`)은 FK 가 `CASCADE` 라 사실과 함께 없어진다.
    """
    from finnect.wiki import build  # 순환 임포트를 피한다 — build 가 service 를 안 쓴다

    build.hold(session, company_id)
    facts = build.clear(session, company_id)
    files = session.scalars(select(UserFile).where(UserFile.company_id == company_id)).all()
    # **청크를 DB 캐스케이드에 맡기지 않는다.** Postgres 는 지워 주지만 SQLite 는
    # `PRAGMA foreign_keys` 가 꺼져 있으면 안 지운다. 탈퇴는 개인정보 경로라
    # 어느 엔진에서든 같게 돌아야 한다.
    session.execute(sa_delete(Chunk).where(Chunk.company_id == company_id))
    for uf in files:
        session.delete(uf)
    return len(files), facts
