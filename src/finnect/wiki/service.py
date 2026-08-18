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

from finnect.attach import extract, formats, hwp
from finnect.config import settings
from finnect.models import Chunk, ParseStatus, UserFile, UserFileStatus
from finnect.wiki import chunk as chunker
from finnect.wiki import storage


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


def _pages(path: Path, ext: str | None, text: str) -> tuple[list[str], bool | None]:
    """조각 경계와 **번호를 붙일지**.

    | 포맷 | 경계 | `page` |
    |---|---|---|
    | PDF | 쪽 | **찬다.** 쪽이 실재한다 |
    | PPTX | 슬라이드 | **찬다.** 슬라이드는 쪽처럼 세어진다 |
    | XLSX | 시트 | **비운다.** 시트는 쪽이 아니다. 이름은 `heading` 이 받는다 |
    | 그 밖 | 없음 | 비운다 |

    없는 쪽 번호를 만들어 붙이면 근거가 거짓이 된다. 경계를 지키는 것과 번호를 붙이는
    것은 다른 일이다.
    """
    try:
        if ext == "pdf":
            return hwp.pages_from_pdf(path), True
        if ext == "pptx":
            return hwp.slides_from_pptx(path), True
        if ext == "xlsx":
            return hwp.sheets_from_xlsx(path), False
    except Exception:  # noqa: BLE001 — 조각 분해가 실패하면 통짜로라도 청크는 낸다
        return [text], False
    return [text], None


def ingest_file(
    session: Session,
    company_id: str,
    path: Path,
    *,
    filename: str | None = None,
) -> tuple[UserFile, str]:
    """파일 하나. 돌려주는 두 번째 값은 무슨 일이 있었나다 — `done` · `duplicate` · …

    **예외를 밖으로 던지지 않는 것이 목표가 아니다.** 던지는 것은 호출부(`ingest_files`)가
    받아 그 파일만 실패로 남긴다. 여기서 다 삼키면 원인이 사라진다.
    """
    name = filename or path.name
    data = path.read_bytes()
    sha = storage.digest(data)

    existing = session.scalar(
        select(UserFile).where(UserFile.company_id == company_id, UserFile.sha256 == sha)
    )
    if existing is not None:
        # 같은 회사가 같은 파일을 다시 올렸다. 청크가 두 벌 되지 않게 여기서 멈춘다.
        return existing, "duplicate"

    storage.put(company_id, data)
    ext = formats.detect(path, name)

    uf = UserFile(
        company_id=company_id,
        sha256=sha,
        filename=name,
        byte_size=len(data),
        ext=ext,
        status=UserFileStatus.PARSING,
    )
    session.add(uf)
    session.flush()

    parsed = extract.parse(path, name, allowed=settings.wiki_formats)
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
        return uf, uf.status

    pages, numbered = _pages(path, ext, parsed.text or "")

    # **청커가 이은 것을 저장한다.** 파서의 `text` 를 저장하면 좌표계가 두 벌이 되고,
    # 이으는 문자가 한 글자만 달라도 모든 청크의 좌표가 어긋난다. 실제로 그랬다.
    text = chunker.join(pages)
    storage.put_text(company_id, sha, text)
    uf.text_chars = len(text)
    uf.page_count = len(pages) if numbered and len(pages) > 1 else None

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
    uf.status = UserFileStatus.CHUNKED
    return uf, "done"


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
                uf, what = ingest_file(session, company_id, path)
                session.commit()
                report.status[uf.status] += 1
                report.chunks += uf.chunk_count or 0
                if what == "duplicate":
                    report.duplicate += 1
                elif uf.status == UserFileStatus.CHUNKED:
                    report.done += 1
                elif uf.status == UserFileStatus.NEEDS_REVIEW:
                    report.needs_review += 1
                    report.problems.append((path.name, uf.parse_status or "글자가 없어요"))
                else:
                    report.failed += 1
                    report.problems.append((path.name, uf.parse_error or uf.parse_status or "실패"))
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
        if uf.ext in {"pdf", "pptx", "xlsx"}:
            pages, numbered = _pages(storage.abs_path(company_id, uf.sha256), uf.ext, text)
        else:
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
