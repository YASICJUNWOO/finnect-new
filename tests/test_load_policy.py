"""코퍼스 적재 정책 — 무엇을 받고 무엇을 빼나.

**기본값이 필터링된 수집이다**(2026-08-24). `finnect.ingest --source X` 를 플래그
없이 돌리는 것 자체가 이 정책이고, `--full` 이 옛 전량 동작으로 되돌린다. `finnect.load`
는 없다 — `--source all` 이 이미 같은 일을 한다.

DB 도 네트워크도 안 탄다. 어댑터의 판정과 CLI 인자 해석, 보고 문자열만 본다.
"""

from __future__ import annotations

import httpx

from finnect.ingest.__main__ import main as ingest_main
from finnect.ingest.bizinfo import BizinfoAdapter
from finnect.ingest.kstartup import KstartupAdapter
from finnect.ingest.runner import IngestReport


def _item(mlsfc: str) -> dict[str, str]:
    return {"pblancId": "PBLN_1", "pldirSportRealmMlsfcCodeNm": mlsfc}


def test_기본_생성자가_이미_거른다() -> None:
    """플래그 없이 만들어도 켬이다. 끄려면 호출자가 명시해야 한다."""
    a = BizinfoAdapter(httpx.Client(), api_key="테스트키")
    assert not a.keep(_item("융자")), "축2"
    assert not a.keep(_item("제도")), "축2d"
    assert a.keep(_item("사업화지원"))


def test_명시적으로_끄면_전량이다() -> None:
    a = BizinfoAdapter(httpx.Client(), api_key="테스트키", skip_mlsfc=False)
    assert a.keep(_item("융자"))


def test_중분류가_없어도_안_죽는다() -> None:
    """API 가 필드를 빠뜨리고 주는 건이 있다. 그때는 남긴다."""
    assert BizinfoAdapter(httpx.Client(), api_key="테스트키").keep({"pblancId": "PBLN_1"})


def test_kstartup_도_기본이_모집중만이다() -> None:
    a = KstartupAdapter(httpx.Client(), api_key="테스트키")
    assert a.only_open is True


def test_kstartup_은_중분류_필드가_없어_전부_남긴다() -> None:
    """좁히는 것은 서버측 only_open 이다. keep() 은 관여하지 않는다."""
    a = KstartupAdapter(httpx.Client(), api_key="테스트키")
    assert a.keep({"pbanc_sn": "1", "supt_biz_clsfc": "융자"})


def test_솎은_건수가_보고에_뜬다() -> None:
    """조용히 버리지 않는다. 코퍼스가 왜 이 크기인지의 유일한 단서다."""
    r = IngestReport(source="bizinfo", pages=1, items=1538, inserted=941, filtered=597)
    assert "솎아 낸 것 597건" in r.render()


def test_안_솎았으면_그_줄이_없다() -> None:
    r = IngestReport(source="kstartup", pages=2, items=268, inserted=268)
    assert "솎아" not in r.render()


def test_솎기와_사고를_따로_센다() -> None:
    """`skipped` 는 외부 ID 가 없어 못 넣은 것이고 `filtered` 는 우리가 뺀 것이다.

    한 숫자로 세면 그 수가 늘었을 때 API 가 깨진 건지 우리가 거른 건지 모른다.
    """
    r = IngestReport(source="bizinfo")
    assert r.skipped == 0
    assert r.filtered == 0


def test_cli는_기본으로_전량을_안_받는다(monkeypatch) -> None:  # noqa: ANN001
    """`--full` 없이 부르면 execute() 에 only_open=True · skip_mlsfc=True 가 간다."""
    calls: list[dict[str, object]] = []

    def fake_execute(name: str, **kw: object) -> IngestReport:
        calls.append({"name": name, **kw})
        return IngestReport(source=name)

    monkeypatch.setattr("finnect.ingest.__main__.execute", fake_execute)

    assert ingest_main(["--source", "bizinfo"]) == 0
    assert calls[-1]["only_open"] is True
    assert calls[-1]["skip_mlsfc"] is True


def test_cli의_full이_둘_다_끈다(monkeypatch) -> None:  # noqa: ANN001
    calls: list[dict[str, object]] = []

    def fake_execute(name: str, **kw: object) -> IngestReport:
        calls.append({"name": name, **kw})
        return IngestReport(source=name)

    monkeypatch.setattr("finnect.ingest.__main__.execute", fake_execute)

    assert ingest_main(["--source", "all", "--full"]) == 0
    assert len(calls) == 2
    assert all(c["only_open"] is False and c["skip_mlsfc"] is False for c in calls)
