"""K-Startup 수집이 상세 페이지 긁기까지 한 번에 문다(2026-08-24).

모집중만 받을 때(`only_open=True`, 기본값)는 배치가 300건 안팎이라 이 자리에서 상세
페이지까지 같이 긁는다 — 따로 `attach --scrape-kstartup` 을 또 돌려야 하는 플래그
하나를 없앤다. **`--full` 에는 안 걸린다**(몇 시간짜리라 조용히 같이 돌면 안 된다).

**DB 도 네트워크도 안 탄다.** `run()`·`runs.*`·`session_scope`·
`attach.kstartup.scrape` 를 전부 가짜로 갈아 끼우고, `execute()` 가 **언제 스크랩을
부르는지**와 **무엇으로 좁혀 부르는지**만 본다.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from finnect.attach import kstartup as attach_kstartup
from finnect.ingest import service
from finnect.ingest.runner import IngestReport


@pytest.fixture(autouse=True)
def _no_real_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """실행 기록과 DB 세션을 막는다. 이 파일은 배관만 본다."""
    monkeypatch.setattr(service.runs, "start", lambda *a, **k: 1)  # noqa: ARG005
    monkeypatch.setattr(service.runs, "finish", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(service.runs, "fail", lambda *a, **k: None)  # noqa: ARG005

    @contextmanager
    def fake_session_scope():  # noqa: ANN202
        yield None

    monkeypatch.setattr(service, "session_scope", fake_session_scope)


def _fake_run(touched_ids: list[str]):  # noqa: ANN202
    """실제 `run()` 대신 쓴다. 목록 API 를 안 부르고 정해 둔 외부 ID 만 돌려준다."""

    def run(adapter, session, on_page=None):  # noqa: ANN001, ARG001
        return IngestReport(
            source=adapter.source, items=len(touched_ids), touched_ids=list(touched_ids)
        )

    return run


def test_모집중만_받으면_바로_이어서_긁는다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "run", _fake_run(["1", "2", "3"]))
    calls: list[list[str] | None] = []

    def fake_scrape(*, ids=None, **kw):  # noqa: ANN001, ANN003
        calls.append(ids)
        n = len(ids or [])
        return attach_kstartup.ScrapeReport(total=n, done=n, attachments=5)

    monkeypatch.setattr(attach_kstartup, "scrape", fake_scrape)

    report = service.execute("kstartup", trigger="test")

    assert calls == [["1", "2", "3"]], "이번에 받은 외부 ID 로만 좁혀 불러야 한다"
    assert report.attach_report is not None
    assert report.attachments == 5, "긁은 첨부 수가 report.attachments 에 더해져야 한다"


def test_전량이면_안_긁는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--full` 은 몇 시간짜리라 여기서 조용히 같이 돌면 안 된다."""
    monkeypatch.setattr(service, "run", _fake_run(["1", "2", "3"]))
    calls: list[object] = []
    monkeypatch.setattr(attach_kstartup, "scrape", lambda **kw: calls.append(kw))  # noqa: ANN003

    report = service.execute("kstartup", only_open=False, skip_mlsfc=False, trigger="test")

    assert calls == []
    assert report.attach_report is None


def test_기업마당은_안_긁는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """`only_open` 은 K-Startup 개념이다. 기업마당엔 애초에 안 걸린다."""
    monkeypatch.setattr(service, "run", _fake_run(["PBLN_1", "PBLN_2"]))
    calls: list[object] = []
    monkeypatch.setattr(attach_kstartup, "scrape", lambda **kw: calls.append(kw))  # noqa: ANN003

    report = service.execute("bizinfo", trigger="test")

    assert calls == []
    assert report.attach_report is None


def test_scrape_attachments를_끄면_안_긁는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트나 예외적인 상황을 위한 탈출구다."""
    monkeypatch.setattr(service, "run", _fake_run(["1"]))
    calls: list[object] = []
    monkeypatch.setattr(attach_kstartup, "scrape", lambda **kw: calls.append(kw))  # noqa: ANN003

    report = service.execute("kstartup", scrape_attachments=False, trigger="test")

    assert calls == []
    assert report.attach_report is None


def test_모집중이_0건이면_안_긁는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """부를 것이 없으면 부르지 않는다."""
    monkeypatch.setattr(service, "run", _fake_run([]))
    calls: list[object] = []
    monkeypatch.setattr(attach_kstartup, "scrape", lambda **kw: calls.append(kw))  # noqa: ANN003

    report = service.execute("kstartup", trigger="test")

    assert calls == []
    assert report.attach_report is None
