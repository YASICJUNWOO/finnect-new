"""실행 기록이 화면에 내보내는 값.

DB 를 안 탄다. 모델 객체와 순수 함수만 본다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect.config import settings
from finnect.ingest import service
from finnect.ingest.runner import IngestReport
from finnect.models import IngestRun


def _run(**kw: object) -> IngestRun:
    base = dict(
        source="kstartup",
        only_open=False,
        trigger="admin",
        status="ok",
        pid=1,
        started_at=dt.datetime(2026, 8, 16, 10, 0, tzinfo=dt.UTC),
    )
    return IngestRun(**{**base, **kw})  # type: ignore[arg-type]


def test_걸린_시간() -> None:
    row = _run(finished_at=dt.datetime(2026, 8, 16, 10, 3, 12, tzinfo=dt.UTC))
    assert row.elapsed == "3분 12초"

    quick = _run(finished_at=dt.datetime(2026, 8, 16, 10, 0, 41, tzinfo=dt.UTC))
    assert quick.elapsed == "41초"


def test_안_끝난_실행도_시간이_나온다() -> None:
    """도는 중에도 '얼마나 됐나'가 보여야 멈춘 건지 도는 건지 안다."""
    row = _run(status="running", finished_at=None)
    assert row.elapsed.endswith("초")


def test_키가_없으면_이름을_알려준다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bizinfo_api_key", "")
    monkeypatch.setattr(settings, "data_go_kr_api_key", "쓸-수-있는-키")

    assert service.missing_key("bizinfo") == "BIZINFO_API_KEY"
    assert service.missing_key("kstartup") == ""


def test_모르는_출처는_실행_거절() -> None:
    result = service.launch("onticheongnyeon")
    assert result.started is False
    assert "모르는 출처" in result.reason


def test_보고서에_처음_보는_필드가_남는다() -> None:
    """API 가 필드를 늘리면 조용히 사라지지 않고 건수까지 문자열에 박힌다."""
    report = IngestReport(source="bizinfo", pages=1, items=1538, inserted=1538)
    report.unknown_fields["sprtRealmNm"] = 12

    rendered = report.render()
    assert "처음 보는 필드" in rendered
    assert "sprtRealmNm(12)" in rendered


def test_touched_ids가_기본으로_비어있다() -> None:
    """K-Startup 이 아닌 출처(기업마당)는 아무도 안 채운다 — 빈 리스트가 정상이다."""
    assert IngestReport(source="bizinfo").touched_ids == []


def test_attach_report가_있으면_같이_찍힌다() -> None:
    """K-Startup 이 모집중만 받으면 상세 페이지 결과가 같은 보고서에 붙는다(2026-08-24)."""
    from finnect.attach.kstartup import ScrapeReport

    report = IngestReport(source="kstartup", items=3, inserted=3)
    report.attach_report = ScrapeReport(total=3, done=3, with_files=2, attachments=5)

    rendered = report.render()
    assert "K-Startup 첨부 긁기" in rendered
    assert "대상 3건" in rendered


def test_attach_report가_없으면_그_문단이_안_붙는다() -> None:
    assert "첨부 긁기" not in IngestReport(source="bizinfo").render()
