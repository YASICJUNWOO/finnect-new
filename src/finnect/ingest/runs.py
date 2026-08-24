"""수집 실행 기록 — 언제 무엇을 돌렸고 어떻게 끝났나.

**적재 트랜잭션과 다른 세션에 쓴다.** 적재가 실패하면 `session_scope` 가 통째로
롤백하는데, 실패 사실까지 같이 사라지면 화면에서는 아무 일도 없었던 것으로 보인다.
두 API 가 실패를 HTTP 200 으로 주는 마당에 그건 최악이다.

프로세스가 죽으면 실행도 죽는다. 스케줄러도 잡 큐도 아니다([ADR-0011](
../../../docs/adr/0011-수집-실행-화면.md)). 그래서 RUNNING 행은 pid 와 함께 남기고
기동할 때 죽은 pid 의 행을 INTERRUPTED 로 정리한다.
"""

from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import select, update

from finnect.db import session_scope
from finnect.ingest.runner import IngestReport
from finnect.models import IngestRun, RunStatus

#: 화면에 펴는 실행 기록 수. 더 필요하면 SQL 로 본다.
RECENT_LIMIT = 20


def start(
    source: str,
    *,
    only_open: bool,
    trigger: str,
    item_limit: int | None = None,
    filter_name: str | None = None,
) -> int:
    """RUNNING 행을 만들고 id 를 낸다. 바로 커밋한다."""
    with session_scope() as s:
        row = IngestRun(
            source=source,
            only_open=only_open,
            filter_name=filter_name,
            trigger=trigger,
            item_limit=item_limit,
            status=str(RunStatus.RUNNING),
            pid=os.getpid(),
        )
        s.add(row)
        s.flush()
        return row.id


def finish(run_id: int, report: IngestReport) -> None:
    """성공으로 닫는다. CLI 가 찍는 문자열을 그대로 남겨 둘을 대조할 수 있게 한다."""
    _close(
        run_id,
        status=RunStatus.OK,
        report=report.render(),
        expected=report.expected,
        pages=report.pages,
        items=report.items,
        inserted=report.inserted,
        changed=report.changed,
        unchanged=report.unchanged,
        skipped=report.skipped,
        filtered=report.filtered,
        attachments=report.attachments,
        ratelimit_remaining=report.ratelimit_remaining,
        unknown_fields=dict(report.unknown_fields),
    )


def fail(run_id: int, error: BaseException) -> None:
    """실패로 닫는다. **예외 종류까지 남긴다.** 봉투 실패와 키 없음은 다른 사건이다."""
    _close(
        run_id,
        status=RunStatus.FAILED,
        error=f"{type(error).__name__}: {error}",
    )


def reap() -> int:
    """죽은 프로세스가 남긴 RUNNING 행을 INTERRUPTED 로 바꾸고 건수를 낸다.

    pid 가 살아 있는 행은 건드리지 않는다. CLI 수집이 도는 중에 서버를 띄우는 일이
    실제로 있고, 그걸 중단으로 적으면 거짓말이 된다.

    pid 재사용까지는 막지 못한다. 로컬 단일 프로세스 운영 도구라 여기까지만 한다.
    """
    reaped = 0
    with session_scope() as s:
        rows = s.scalars(
            select(IngestRun).where(IngestRun.status == str(RunStatus.RUNNING))
        ).all()
        for row in rows:
            if _alive(row.pid):
                continue
            s.execute(
                update(IngestRun)
                .where(IngestRun.id == row.id)
                .values(
                    status=str(RunStatus.INTERRUPTED),
                    finished_at=dt.datetime.now(dt.UTC),
                    error=f"프로세스 {row.pid} 가 사라졌다. 끝까지 돌았는지 알 수 없다",
                )
            )
            reaped += 1
    return reaped


def live(source: str) -> IngestRun | None:
    """지금 이 출처를 돌리고 있는 실행. 없으면 None.

    프로세스 경계를 넘는 유일한 검사다. 화면 버튼과 CLI 가 같이 돌면 같은 테이블에
    같은 API 응답을 두 벌 넣는다.
    """
    with session_scope() as s:
        rows = s.scalars(
            select(IngestRun)
            .where(IngestRun.source == source, IngestRun.status == str(RunStatus.RUNNING))
            .order_by(IngestRun.started_at.desc())
        ).all()
    return next((r for r in rows if _alive(r.pid)), None)


def recent(limit: int = RECENT_LIMIT) -> list[IngestRun]:
    with session_scope() as s:
        return list(
            s.scalars(select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit))
        )


def last_by_source() -> dict[str, IngestRun]:
    """출처별 마지막 실행. 화면 카드가 '언제 마지막으로 받았나'를 여기서 읽는다."""
    out: dict[str, IngestRun] = {}
    for row in recent(limit=200):
        out.setdefault(row.source, row)
    return out


def _close(run_id: int, *, status: RunStatus, **values: object) -> None:
    with session_scope() as s:
        s.execute(
            update(IngestRun)
            .where(IngestRun.id == run_id)
            .values(status=str(status), finished_at=dt.datetime.now(dt.UTC), **values)
        )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 다른 사용자 소유다. 살아 있다는 뜻이다
    return True
