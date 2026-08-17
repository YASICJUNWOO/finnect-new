"""수집 실행 — CLI 와 화면 버튼이 **같은 경로**를 쓴다.

경로가 갈리면 둘 중 하나에서만 나는 버그가 생긴다. 특히 봉투 검증과 실행 기록이 그렇다.
여기가 그 하나뿐인 경로다. 부르는 쪽이 다른 것은 `trigger` 값뿐이다.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from finnect.config import settings
from finnect.db import session_scope
from finnect.ingest import jobs, runs
from finnect.ingest.bizinfo import BizinfoAdapter
from finnect.ingest.kstartup import KstartupAdapter
from finnect.ingest.runner import IngestReport, run
from finnect.models import Source

# 출처 설명은 `finnect/sources.py` 에 산다. **여기서 다시 import 해 주는 이유가 있다** —
# 읽기만 하는 API 가 `SOURCES` 를 쓰는데 이 모듈은 httpx 를 끌고 온다(ADR-0027).
# 부르는 쪽을 안 고치려고 이름을 그대로 내보낸다.
from finnect.sources import BY_NAME, SOURCES, SourceInfo

UA = "finnect-ingest/0.1 (+https://github.com/joonoo3/finnect-new)"

__all__ = ["BY_NAME", "SOURCES", "SourceInfo", "launch", "missing_key", "parse_limit"]


def missing_key(source: str) -> str:
    """설정되지 않은 인증키 이름. 다 있으면 빈 문자열.

    **버튼을 막는 데 쓰지 않는다.** 키가 없을 때 0건 성공이 아니라 실패가 남는 것이
    이 슬라이스의 핵심 검증이라(plan/06 검증 4번) 눌러서 실패하는 경로를 살려 둔다.
    화면에는 미리 알려 준다.
    """
    info = BY_NAME.get(source)
    if info is None:
        return ""
    have = {
        "BIZINFO_API_KEY": settings.bizinfo_api_key,
        "DATA_GO_KR_API_KEY": settings.data_go_kr_api_key,
    }
    return "" if have.get(info.key_env) else info.key_env


def parse_limit(raw: str | None) -> int | None:
    """화면이 준 건수 입력을 검증한다. 빈 값은 전량이라는 뜻이다.

    경계에서 막는다. 음수나 글자가 어댑터까지 흘러가면 searchCnt=-1 같은 요청이 나간다.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f"건수는 숫자여야 한다: {text!r}")
    value = int(text)
    if value < 1:
        raise ValueError("건수는 1 이상이어야 한다")
    return value


def execute(
    source: str,
    *,
    only_open: bool = False,
    limit: int | None = None,
    trigger: str,
    on_page: Callable[[IngestReport], None] | None = None,
) -> IngestReport:
    """한 출처를 끝까지 받아 적재하고 실행 기록을 닫는다. 실패하면 기록만 남기고 다시 던진다."""
    if source not in BY_NAME:
        raise ValueError(f"모르는 출처: {source}")

    run_id = runs.start(source, only_open=only_open, trigger=trigger, item_limit=limit)
    try:
        with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True) as client:
            adapter = _adapter(source, client, only_open=only_open, limit=limit)
            with session_scope() as session:
                report = run(adapter, session, on_page=on_page)
    except BaseException as e:
        # 적재는 롤백돼도 이 행은 남는다. 실패가 '아무 일 없었음'으로 보이면 안 된다.
        runs.fail(run_id, e)
        raise

    runs.finish(run_id, report)
    return report


def launch(
    source: str, *, only_open: bool = False, limit: int | None = None, trigger: str = "admin"
) -> jobs.Launch:
    """백그라운드로 시작한다. 이미 돌고 있으면 거절한다.

    검사가 둘인 이유가 있다. `runs.live` 는 **다른 프로세스**(CLI)를 보고,
    `jobs.launch` 의 락은 같은 프로세스 안의 동시 클릭을 막는다. 하나로는 부족하다.
    """
    if source not in BY_NAME:
        return jobs.Launch(False, f"모르는 출처: {source}")

    busy = runs.live(source)
    if busy is not None:
        return jobs.Launch(False, f"이미 돌고 있다 (실행 #{busy.id}, pid {busy.pid})")

    def work() -> None:
        execute(
            source,
            only_open=only_open,
            limit=limit,
            trigger=trigger,
            on_page=lambda r: jobs.report(
                source,
                jobs.Progress(pages=r.pages, items=r.items, expected=r.expected, target=limit),
            ),
        )

    # 락 키는 (출처, 옵션) 이 아니라 출처다. --only-open 이든 아니든 같은 표에 쓴다.
    return jobs.launch(source, work)


def _adapter(source: str, client: httpx.Client, *, only_open: bool, limit: int | None):  # noqa: ANN202
    if source == str(Source.BIZINFO):
        return BizinfoAdapter(client, limit=limit)
    return KstartupAdapter(client, only_open=only_open, limit=limit)
