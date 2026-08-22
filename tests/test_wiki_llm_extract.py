"""LLM 추출기 — 키 없이 검증할 수 있는 것만 (ADR-0037).

**진짜 호출은 여기서 안 한다.** 키가 있어야 하고 돈이 들고 답이 매번 다르다.
정확도는 `scripts/score_wiki_extract.py` 가 픽스처 118개와 대조해서 잰다.

여기서 막는 것은 **배관과 규율**이다.

1. 앵커가 원문에 없으면 그 사실을 **버리고 센다**. 조용히 사라지면 "아무것도 안
   나온 것" 과 구분이 안 된다(ADR-0037 결정 5)
2. 앵커 비교 규칙이 `build.py` 와 **같아야 한다**. 다르면 여기서 통과한 앵커가
   거기서 죽는다
3. 키가 없으면 **멈춘다.** 조용히 스텁으로 물러나지 않는다(결정 4)
4. 모르는 라벨은 `uncategorized` 로 간다. **버리지 않는다**
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect import llm
from finnect.wiki import build, extract, topics
from finnect.wiki.extract import FileView, LlmExtractor


class 가짜클라이언트:
    """준 대로 돌려준다. **네트워크를 안 쓴다.**"""

    model = "gpt-5.6-luna"

    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return {"facts": self._facts}


VIEW = FileView(
    sha256="a" * 64,
    filename="회사소개서.pdf",
    chunks=((0, "주식회사 다시로는 2024년 3월 5일에 문을 열었다."),
            (1, "재구매율이 34%에서 51%로 올랐다.")),
)


def _f(**kw) -> dict:
    base = {"topic": "company_profile", "kind": "event", "text": "", "anchor": "",
            "fact_key": None, "key": None, "value": None, "as_of": None, "qualifier": None}
    return {**base, **kw}


def test_앵커가_원문에_있으면_통과한다() -> None:
    ex = LlmExtractor(client=가짜클라이언트([
        _f(kind="value", key="개업연월일", value="2024-03-05", as_of=None,
           text="2024년 3월 5일 개업", anchor="2024년 3월 5일에 문을 열었다"),
    ]))
    got = ex.extract(VIEW)
    assert len(got) == 1
    assert got[0].value == "2024-03-05"
    assert ex.dropped == []


def test_앵커가_원문에_없으면_버리고_센다() -> None:
    """**가장 중요한 검사다.** LLM 이 조사 하나만 바꿔도 근거를 잃는다."""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(text="지어낸 사실", anchor="이 문장은 원문에 없다"),
        _f(text="진짜", anchor="재구매율이 34%에서 51%로"),
    ]))
    got = ex.extract(VIEW)
    assert [f.text for f in got] == ["진짜"]
    assert len(ex.dropped) == 1
    assert "원문에 없다" in ex.dropped[0][1]


def test_공백만_다른_앵커는_통과한다() -> None:
    """`build.py` 가 공백을 지우고 찾는다. **여기 규칙이 거기와 같아야 한다.**"""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(text="띄어쓰기가 다르다", anchor="2024년3월5일에 문을열었다"),
    ]))
    assert len(ex.extract(VIEW)) == 1


def test_앵커_비교가_build_와_같은_규칙이다() -> None:
    """규칙이 갈라지면 여기서 통과한 앵커가 `build.py` 에서 죽는다."""
    for s in ("공백  여럿", "줄\n바꿈", " 앞뒤 ", "탭\t사이"):
        assert extract._squash(s) == build._squash(s)


def test_모르는_라벨은_uncategorized_로_간다() -> None:
    """**버리지 않는다**(구상도 ④ 예외)."""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(topic="없는라벨", text="x", anchor="재구매율이 34%"),
    ]))
    assert ex.extract(VIEW)[0].topic == topics.UNCATEGORIZED


def test_날짜가_아니면_시점_없는_값이_된다() -> None:
    """**지어내지 않는다.** `2024년쯤` 을 날짜로 만들면 없는 시계열이 생긴다."""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(kind="value", key="매출액", value="100", as_of="2024년쯤",
           text="x", anchor="재구매율이 34%"),
    ]))
    assert ex.extract(VIEW)[0].as_of is None


def test_날짜가_맞으면_파싱한다() -> None:
    ex = LlmExtractor(client=가짜클라이언트([
        _f(kind="value", key="매출액", value="100", as_of="2024-12-31",
           text="x", anchor="재구매율이 34%"),
    ]))
    assert ex.extract(VIEW)[0].as_of == dt.date(2024, 12, 31)


def test_서술_노드에는_슬롯_필드가_안_붙는다() -> None:
    """`value` 가 서술에 붙으면 병합 키가 어긋난다."""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(kind="event", text="x", anchor="재구매율이 34%",
           key="매출액", value="100", qualifier="시드"),
    ]))
    f = ex.extract(VIEW)[0]
    assert (f.key, f.value, f.qualifier) == (None, None, None)


def test_정형_슬롯에는_fact_key_가_안_붙는다() -> None:
    """`fact_key` 는 서술 전용이다. 슬롯에 오면 `dedupe_key` 가 어긋난다."""
    ex = LlmExtractor(client=가짜클라이언트([
        _f(kind="value", key="매출액", value="100", fact_key="rev",
           text="x", anchor="재구매율이 34%"),
    ]))
    assert ex.extract(VIEW)[0].fact_key is None


def test_원문에_라벨_목록을_안_넘긴다() -> None:
    """사용자 프롬프트는 파일 이름과 원문뿐이다. 라벨은 스키마 `enum` 이 강제한다."""
    c = 가짜클라이언트([])
    LlmExtractor(client=c).extract(VIEW)
    user = c.calls[0]["user"]
    assert "회사소개서.pdf" in user
    assert "재구매율이 34%" in user
    schema = c.calls[0]["schema"]
    enum = schema["properties"]["facts"]["items"]["properties"]["topic"]["enum"]
    assert set(enum) == set(topics.TOPICS)


def test_키가_없으면_스텁으로_안_물러난다(monkeypatch) -> None:  # noqa: ANN001
    """**조용히 물러나면 픽스처 7건만 처리하고 나머지를 조용히 버린다.**"""
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    with pytest.raises(llm.MissingKey, match="OPENAI_API_KEY"):
        llm.client()


def test_설정이_llm_이면_llm_추출기가_나온다(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(extract.settings, "wiki_extractor", "llm")
    assert isinstance(extract.get_extractor(), LlmExtractor)


def test_모르는_추출기는_막는다(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(extract.settings, "wiki_extractor", "claude")
    with pytest.raises(NotImplementedError, match="stub"):
        extract.get_extractor()
