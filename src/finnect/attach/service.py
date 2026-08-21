"""첨부 내려받기와 해독 — CLI 와 화면이 같이 쓰는 하나뿐인 경로.

**적재와 달리 한 트랜잭션으로 묶지 않는다.** 목록 수집은 응답 149건이 한 덩어리라 중간에
끊기면 통째로 버리는 게 맞았다. 여기는 파일 3,354개가 각자 독립이고 하나가 몇 초씩 걸린다.
중간에 죽었다고 앞의 2,000건을 다시 받게 만들 이유가 없다. 그래서 주기적으로 커밋한다.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finnect.attach import download, extract, store
from finnect.config import settings
from finnect.db import SessionFactory
from finnect.models import Attachment, AttachmentFile, FetchStatus, ParseStatus

COMMIT_EVERY = 20


@dataclass(slots=True)
class AttachReport:
    total: int = 0  # 대상 첨부
    done: int = 0  # 이번에 처리한 것
    skipped: int = 0  # 이미 되어 있어 건너뛴 것
    bytes_in: int = 0
    fetch: Counter = field(default_factory=Counter)
    parse: Counter = field(default_factory=Counter)
    by_ext: Counter = field(default_factory=Counter)  # (ext, parse_status)

    def render(self) -> str:
        lines = [
            f"[첨부] 대상 {self.total:,}건 · 처리 {self.done:,} · 건너뜀 {self.skipped:,}",
            f"  받음 {self.bytes_in / 1024 / 1024:,.0f}MB",
        ]
        if self.fetch:
            got = " · ".join(f"{k} {v:,}" for k, v in self.fetch.most_common())
            lines.append(f"  내려받기 — {got}")
        if self.parse:
            got = " · ".join(f"{k} {v:,}" for k, v in self.parse.most_common())
            lines.append(f"  해독 — {got}")
        # 조용한 누락 0건이 이 슬라이스의 핵심 검증이다. 처리한 것과 상태가 남은 것이 같아야 한다.
        readable = (str(ParseStatus.OK), str(ParseStatus.CONTAINER))
        unread = sum(v for k, v in self.parse.items() if k not in readable)
        if unread:
            lines.append(f"  ⚠ 텍스트가 없는 첨부 {unread:,}건. 전부 상태로 남았다")
        return "\n".join(lines)


def run(
    *,
    limit: int | None = None,
    redo: bool = False,
    source: str | None = None,
    only: set[str] | None = None,
    on_progress: Callable[[AttachReport], None] | None = None,
) -> AttachReport:
    """첨부를 받아서 읽는다. 이미 끝난 것은 건너뛴다.

    redo 는 파서를 고쳤을 때 쓴다. **디스크에 있는 파일은 다시 안 받고 해독만 다시 한다.**
    콘텐츠 주소로 저장해 둔 덕에 되는 일이다. 지난번에 **받기가 실패한 것은 다시 받는다** —
    그쪽은 고칠 파서가 없고 다시 해보는 것 말고 할 게 없다.

    only 는 받을 URL 을 그 집합으로 좁힌다. **누가 그 목록을 만들었는지 여기서 모른다** —
    K-Startup 전량이 55GB 인데 디스크가 24GB 라 골라 받아야 하고, 고르는 규칙은
    `notice-filter/` 에 따로 산다. 이 인자는 목록을 받을 뿐이라 규칙이 바뀌거나
    사라져도 이 코드는 안 바뀐다.
    """
    report = AttachReport()
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)

    with SessionFactory() as s:
        targets = _targets(s, source=source)
        if only is not None:
            targets = [t for t in targets if t[0] in only]
        report.total = len(targets)
        if limit is not None:
            targets = targets[:limit]

        with httpx.Client(follow_redirects=True) as client:
            for i, (url, src, filename) in enumerate(targets, 1):
                row = s.scalar(select(AttachmentFile).where(AttachmentFile.url == url))

                if not redo and _is_done(row):
                    report.skipped += 1
                    continue

                row = _process(client, s, row, url, src, filename, redo=redo, report=report)
                report.done += 1
                report.fetch[row.fetch_status] += 1
                if row.parse_status:
                    report.parse[row.parse_status] += 1
                    report.by_ext[(row.detected_ext or "?", row.parse_status)] += 1

                if i % COMMIT_EVERY == 0:
                    s.commit()
                    if on_progress is not None:
                        on_progress(report)
        s.commit()

    if on_progress is not None:
        on_progress(report)
    return report


def _targets(s: Session, *, source: str | None) -> list[tuple[str, str, str]]:
    """받을 대상. `attachment` 가 목록이고 URL 이 단위다.

    URL 중복은 실측 0건이지만 distinct 를 건다. 같은 파일을 두 번 받을 이유가 없다.
    """
    stmt = select(Attachment.url, Attachment.source, func.min(Attachment.filename)).where(
        Attachment.url.is_not(None)
    )
    if source:
        stmt = stmt.where(Attachment.source == source)
    stmt = stmt.group_by(Attachment.url, Attachment.source).order_by(Attachment.url)
    return [(u, sc, fn) for u, sc, fn in s.execute(stmt).all()]


def _is_done(row: AttachmentFile | None) -> bool:
    """이미 끝난 것.

    **받기 실패는 끝난 것으로 친다.** 다시 돌릴 때마다 404 를 3,354번 두드리지 않는다.
    다시 시도하려면 --redo 를 쓴다.
    """
    if row is None:
        return False
    if row.fetch_status != str(FetchStatus.OK):
        return True
    return row.parse_status is not None and store.exists(row.stored_path)


def _process(
    client: httpx.Client,
    s: Session,
    row: AttachmentFile | None,
    url: str,
    source: str,
    filename: str,
    *,
    redo: bool,
    report: AttachReport,
) -> AttachmentFile:
    if row is None:
        row = AttachmentFile(url=url, source=source)
        s.add(row)

    # 파일이 이미 디스크에 있으면 다시 안 받는다. redo 는 해독만 다시 한다.
    have = row.fetch_status == str(FetchStatus.OK) and store.exists(row.stored_path)

    if not have:
        time.sleep(settings.request_delay_sec)  # 상대 서버에 대한 예의
        got = download.fetch(client, url, source)
        row.fetch_status = str(got.status)
        row.http_status = got.http_status
        row.fetch_error = got.error
        row.content_type = got.content_type
        row.server_filename = got.filename
        row.fetched_at = func.now()

        if got.status is not FetchStatus.OK or got.data is None:
            # 파일이 없으니 해독도 없다. 상태는 남는다.
            row.parse_status = None
            row.byte_size = None
            row.sha256 = None
            row.stored_path = None
            return row

        report.bytes_in += len(got.data)
        row.byte_size = len(got.data)
        row.sha256 = store.digest(got.data)
        row.stored_path = store.put(got.data)

    name = row.server_filename or filename
    parsed = extract.parse(store.abs_path(row.stored_path), name)  # type: ignore[arg-type]
    row.parse_status = str(parsed.status)
    row.parser = parsed.parser
    row.detected_ext = parsed.ext
    row.parse_error = parsed.error
    row.contents = {"files": parsed.contents} if parsed.contents else {}
    row.parsed_at = func.now()

    if parsed.text:
        row.text_chars = len(parsed.text)
        row.text_path = store.put_text(row.sha256, parsed.text)  # type: ignore[arg-type]
    else:
        row.text_chars = 0 if parsed.status is ParseStatus.EMPTY else None
        row.text_path = None

    return row


# --- 집계 -------------------------------------------------------------------


def coverage(s: Session) -> dict[str, object]:
    """포맷별 해독 현황. **T-0007 이 이 숫자를 근거로 쓴다.**

    `unaccounted` 가 이 슬라이스의 핵심 지표다. 첨부 URL 중 상태 행이 없는 것,
    곧 **조용히 사라진 건수**다. 0이 아니면 나머지 숫자를 믿으면 안 된다.
    """
    urls = s.scalar(
        select(func.count(func.distinct(Attachment.url))).where(Attachment.url.is_not(None))
    ) or 0
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

    return {
        "listed": s.scalar(select(func.count()).select_from(Attachment)) or 0,
        "urls": urls,
        "files": files,
        "unaccounted": urls - files,
        "fetch": fetch,
        "parse": parse,
        "by_ext": [
            {"ext": e, "status": st, "count": c, "avg_chars": int(a) if a else 0}
            for e, st, c, a in by_ext
        ],
    }


def ocr_candidates(s: Session) -> dict[str, int]:
    """OCR 없이는 0바이트인 것들. **T-0007 의 입력이다. 여기서 결정하지 않는다.**"""
    pdf_empty = s.scalar(
        select(func.count())
        .select_from(AttachmentFile)
        .where(
            AttachmentFile.detected_ext == "pdf",
            AttachmentFile.parse_status == str(ParseStatus.EMPTY),
        )
    )
    images = s.scalar(
        select(func.count())
        .select_from(AttachmentFile)
        .where(AttachmentFile.detected_ext.in_(("png", "jpg", "gif")))
    )
    # 공고문 자리에 이미지가 붙은 것. 본문에 평가 정보가 0%라 이건 통째로 안 보이는 공고다.
    image_notices = s.scalar(
        select(func.count())
        .select_from(Attachment)
        .join(AttachmentFile, AttachmentFile.url == Attachment.url)
        .where(
            Attachment.kind == "공고문",
            AttachmentFile.detected_ext.in_(("png", "jpg", "gif")),
        )
    )
    return {
        "pdf_empty": pdf_empty or 0,
        "images": images or 0,
        "image_notices": image_notices or 0,
    }


def per_notice(s: Session, source: str, external_id: str) -> dict[str, AttachmentFile]:
    """공고 하나의 첨부별 해독 결과. URL 로 맞춘다."""
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
    rows = s.scalars(select(AttachmentFile).where(AttachmentFile.url.in_(urls)))
    return {r.url: r for r in rows}


# --- OCR 되돌아보기 (ADR-0030) ----------------------------------------------


@dataclass(slots=True)
class OcrReport:
    """스캔본에 OCR 을 돌린 결과."""

    total: int = 0  # 대상
    done: int = 0
    ok: int = 0  # 글자가 나왔다
    still_empty: int = 0  # OCR 을 돌렸는데도 0자
    failed: int = 0
    pages: int = 0
    chars: int = 0
    seconds: float = 0.0
    problems: list[tuple[str, str]] = field(default_factory=list)

    def render(self) -> str:
        per = f"{self.seconds / self.pages:.1f}초/쪽" if self.pages else "-"
        lines = [
            f"[OCR] 대상 {self.total}건 · 처리 {self.done}건 · {self.pages}쪽 · "
            f"{self.seconds / 60:.1f}분 ({per})",
            f"  글자 나옴   {self.ok}건 · {self.chars:,}자",
            f"  여전히 0자  {self.still_empty}건",
            f"  실패        {self.failed}건",
        ]
        if self.problems:
            lines.append("  [실패한 것]")
            lines += [f"    {n[:56]}  —  {w}" for n, w in self.problems[:20]]
        return "\n".join(lines)


def ocr_pass(
    *,
    limit: int | None = None,
    on_progress: Callable[[OcrReport], None] | None = None,
) -> OcrReport:
    """**텍스트 레이어가 0자인 것만** 다시 본다(ADR-0030).

    새로 받지 않는다. 디스크에 있는 파일을 다시 읽을 뿐이라 `--redo` 와 같은 성격이다.
    다만 비용이 다르다 — 텍스트 레이어는 밀리초, OCR 은 쪽당 십수 초다. 그래서
    **`run()` 안에 넣지 않고 따로 부른다.**

    대상을 `EMPTY` 로 좁힌 것이 요점이다. 읽히는 PDF 까지 OCR 로 돌리면 2,827건에
    쪽당 십수 초를 쓴다.
    """
    report = OcrReport()

    with SessionFactory() as s:
        rows = list(
            s.scalars(
                select(AttachmentFile)
                .where(AttachmentFile.parse_status == str(ParseStatus.EMPTY))
                .order_by(AttachmentFile.byte_size)
            )
        )
        report.total = len(rows)
        if limit is not None:
            rows = rows[:limit]

        for i, row in enumerate(rows, 1):
            if not store.exists(row.stored_path):
                report.failed += 1
                report.problems.append((row.server_filename or row.url, "원본이 없다"))
                continue

            path = store.abs_path(row.stored_path)  # type: ignore[arg-type]
            started = time.monotonic()
            parsed = extract.parse(path, row.server_filename, use_ocr=True)
            report.seconds += time.monotonic() - started
            report.pages += len(parsed.pages) or 1
            report.done += 1

            row.parse_status = str(parsed.status)
            row.parser = parsed.parser
            row.parse_error = parsed.error
            row.parsed_at = func.now()

            if parsed.status is ParseStatus.OK and parsed.text:
                row.text_chars = len(parsed.text)
                row.text_path = store.put_text(row.sha256, parsed.text)  # type: ignore[arg-type]
                report.ok += 1
                report.chars += row.text_chars
            elif parsed.status is ParseStatus.EMPTY:
                row.text_chars = 0
                report.still_empty += 1
            else:
                report.failed += 1
                report.problems.append(
                    (row.server_filename or row.url, parsed.error or str(parsed.status))
                )

            if i % 5 == 0:
                s.commit()
                if on_progress is not None:
                    on_progress(report)
        s.commit()

    if on_progress is not None:
        on_progress(report)
    return report
