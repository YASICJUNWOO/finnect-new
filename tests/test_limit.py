"""건수 제한 — 입력 검증과 '잘렸다' 표시.

**맛보기 수집이 전량 수집으로 오인되는 것이 이 기능의 유일한 위험이다.** 500건만 받아
놓고 그걸 모집단으로 믿으면 계획이 경고한 '조용히 틀린 모집단'을 손으로 만드는 셈이다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect.ingest import jobs, service
from finnect.ingest.bizinfo import _total_count
from finnect.ingest.runner import IngestReport
from finnect.models import IngestRun


class Test건수_입력_검증:
    def test_빈_값은_전량(self) -> None:
        assert service.parse_limit("") is None
        assert service.parse_limit("   ") is None
        assert service.parse_limit(None) is None

    def test_숫자를_받는다(self) -> None:
        assert service.parse_limit("500") == 500
        assert service.parse_limit(" 1 ") == 1

    @pytest.mark.parametrize("bad", ["0", "-1", "abc", "1.5", "500건", "1e3"])
    def test_이상한_값은_경계에서_막는다(self, bad: str) -> None:
        """searchCnt=-1 같은 요청이 API 로 나가면 안 된다."""
        with pytest.raises(ValueError):
            service.parse_limit(bad)


class Test전량_건수:
    def test_잘라_받아도_전량을_안다(self) -> None:
        """기업마당은 totCnt 를 item 마다 반복해 준다. 10건만 받아도 1538 이 온다."""
        items = [{"pblancId": "PBLN_1", "totCnt": 1538}] * 10
        assert _total_count(items) == 1538

    def test_빈_응답은_0건(self) -> None:
        assert _total_count([]) == 0

    def test_totCnt_가_없으면_모른다고_한다(self) -> None:
        """추측해서 채우지 않는다. None 이면 화면이 진행률을 안 그린다."""
        assert _total_count([{"pblancId": "PBLN_1"}]) is None


class Test잘림_표시:
    def _run(self, **kw: object) -> IngestRun:
        base = dict(
            source="kstartup",
            only_open=False,
            trigger="admin",
            status="ok",
            pid=1,
            started_at=dt.datetime(2026, 8, 16, 10, 0, tzinfo=dt.UTC),
        )
        return IngestRun(**{**base, **kw})  # type: ignore[arg-type]

    def test_전량_수집은_잘린_게_아니다(self) -> None:
        assert self._run(item_limit=None, expected=29789, items=29789).truncated is False

    def test_맛보기는_잘렸다고_적힌다(self) -> None:
        assert self._run(item_limit=500, expected=29789, items=500).truncated is True

    def test_제한이_전량보다_크면_안_잘렸다(self) -> None:
        """1,538건짜리 출처에 2,000 을 넣으면 전량이 들어온다. 경고할 일이 아니다."""
        assert self._run(item_limit=2000, expected=1538, items=1538).truncated is False

    def test_실패한_실행은_잘림으로_안_친다(self) -> None:
        """실패는 실패로 보여야 한다. '맛보기였다'로 덮으면 원인이 가려진다."""
        assert self._run(status="failed", item_limit=500, expected=29789).truncated is False


class Test보고서:
    def test_덜_받으면_보고서에_경고가_붙는다(self) -> None:
        report = IngestReport(source="kstartup", pages=1, items=500, expected=29789)
        assert "전량 29,789건 중 500건만 받았다" in report.render()

    def test_전량이면_경고가_없다(self) -> None:
        report = IngestReport(source="bizinfo", pages=1, items=1538, expected=1538)
        assert "만 받았다" not in report.render()


class Test진행률_분모:
    def test_맛보기는_요청한_건수가_분모다(self) -> None:
        """분모를 29,789로 두면 500건 맛보기가 영원히 2% 로 멈춘 것처럼 보인다."""
        p = jobs.Progress(pages=1, items=250, expected=29789, target=500)
        assert p.goal == 500
        assert p.percent == 50

    def test_전량이면_출처의_전량이_분모다(self) -> None:
        p = jobs.Progress(pages=75, items=15000, expected=29789)
        assert p.goal == 29789
        assert p.percent == 50

    def test_제한이_전량보다_크면_전량이_분모다(self) -> None:
        p = jobs.Progress(pages=1, items=1538, expected=1538, target=5000)
        assert p.goal == 1538
        assert p.percent == 100
