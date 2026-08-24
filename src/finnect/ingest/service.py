"""수집 실행 — CLI 와 화면 버튼이 **같은 경로**를 쓴다.

경로가 갈리면 둘 중 하나에서만 나는 버그가 생긴다. 특히 봉투 검증과 실행 기록이 그렇다.
여기가 그 하나뿐인 경로다. 부르는 쪽이 다른 것은 `trigger` 값뿐이다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
    only_open: bool = True,
    limit: int | None = None,
    skip_mlsfc: bool = True,
    scrape_attachments: bool = True,
    trigger: str,
    on_page: Callable[[IngestReport], None] | None = None,
    on_scrape: Callable[[Any], None] | None = None,
) -> IngestReport:
    """한 출처를 끝까지 받아 적재하고 실행 기록을 닫는다. 실패하면 기록만 남기고 다시 던진다.

    **기본이 필터링된 수집이다**(2026-08-24). `only_open` 은 K-Startup 에만,
    `skip_mlsfc` 는 기업마당에만 걸린다 — 서로 무관한 출처의 파라미터라 둘 다 기본
    켬으로 둬도 섞이지 않는다. 전량이 필요하면 CLI `--full` 또는 둘 다 `False` 로
    직접 부른다(`docs/dataset.md` 의 정본 절차).

    **K-Startup 은 모집중만 받을 때 상세 페이지까지 이 자리에서 같이 긁는다**(2026-08-24).
    `only_open` 이 걸리면 이번 배치가 300건 안팎이라 — 그리고 이 명령이 끝나기 전에
    첨부 목록까지 있는 게 "따로 `attach --scrape-kstartup` 을 또 돌려야 한다"는 플래그
    하나를 없앤다. **`--full` 에는 안 걸린다** — 전량이면 예전처럼 몇 시간짜리라 여기서
    조용히 같이 돌면 안 된다. `scrape_attachments=False` 는 테스트와 그 예외적인 상황을
    위한 탈출구다.

    **`on_scrape` 가 `on_page` 와 따로인 이유.** 저건 `IngestReport` 를 주고 이쪽은
    `ScrapeReport` 를 준다 — 다른 표라 한 콜백으로 합치면 받는 쪽이 매번 어느 것인지
    물어봐야 한다. **이 훅이 없으면 상세 긁기 몇 분 동안 진행률이 목록 숫자에 멈춰
    있어서 죽은 것처럼 보인다.**
    """
    if source not in BY_NAME:
        raise ValueError(f"모르는 출처: {source}")

    run_id = runs.start(
        source,
        only_open=only_open,
        trigger=trigger,
        item_limit=limit,
        filter_name="mlsfc" if skip_mlsfc else None,
    )
    try:
        with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True) as client:
            adapter = _adapter(
                source, client, only_open=only_open, limit=limit, skip_mlsfc=skip_mlsfc
            )
            with session_scope() as session:
                report = run(adapter, session, on_page=on_page)

        if (
            source == str(Source.KSTARTUP)
            and only_open
            and scrape_attachments
            and report.touched_ids
        ):
            from finnect.attach.kstartup import scrape as scrape_kstartup_attachments

            report.attach_report = scrape_kstartup_attachments(
                ids=report.touched_ids, on_progress=on_scrape
            )
            report.attachments += report.attach_report.attachments
    except BaseException as e:
        # 적재는 롤백돼도 이 행은 남는다. 실패가 '아무 일 없었음'으로 보이면 안 된다.
        runs.fail(run_id, e)
        raise

    runs.finish(run_id, report)
    return report


def launch(
    source: str,
    *,
    only_open: bool = True,
    skip_mlsfc: bool = True,
    limit: int | None = None,
    trigger: str = "admin",
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
        # 목록 단계와 첨부 단계가 **같은 막대를 쓰되 분모가 다르다**(`jobs.Progress`).
        # 훅이 둘인 이유는 넘어오는 표가 다르기 때문이다 — IngestReport 와 ScrapeReport.
        state = {"pages": 0, "items": 0, "expected": None}

        def on_page(r: IngestReport) -> None:
            state.update(pages=r.pages, items=r.items, expected=r.expected)
            jobs.report(
                source,
                jobs.Progress(pages=r.pages, items=r.items, expected=r.expected, target=limit),
            )

        def on_scrape(r: object) -> None:
            # 목록 단계에서 센 값을 그대로 들고 간다 — 화면이 "공고 268건을 받았고
            # 지금 그중 상세를 여는 중" 을 한 줄로 말할 수 있어야 한다.
            jobs.report(
                source,
                jobs.Progress(
                    pages=state["pages"],
                    items=state["items"],
                    expected=state["expected"],
                    target=limit,
                    phase=jobs.PHASE_ATTACH,
                    scraped=getattr(r, "done", 0),
                    scrape_total=getattr(r, "total", 0),
                ),
            )

        execute(
            source,
            only_open=only_open,
            skip_mlsfc=skip_mlsfc,
            limit=limit,
            trigger=trigger,
            on_page=on_page,
            on_scrape=on_scrape,
        )

    # 락 키는 (출처, 옵션) 이 아니라 출처다. 필터를 켜든 끄든 같은 표에 쓴다.
    return jobs.launch(source, work)


def _adapter(  # noqa: ANN202
    source: str,
    client: httpx.Client,
    *,
    only_open: bool,
    limit: int | None,
    skip_mlsfc: bool = False,
):
    if source == str(Source.BIZINFO):
        # 솎기는 기업마당만이다. K-Startup 에는 중분류 필드가 없다.
        return BizinfoAdapter(client, limit=limit, skip_mlsfc=skip_mlsfc)
    return KstartupAdapter(client, only_open=only_open, limit=limit)
