"""LLM 추출기 — 키 없이 검증할 수 있는 것만 (ADR-0037 · plan/22 T-0126).

**진짜 호출은 여기서 안 한다.** 키가 있어야 하고 돈이 들고 답이 매번 다르다.
정확도는 `--score` 가 픽스처 118개와 대조해서 잰다.

여기서 막는 것은 **배관과 규율**이다. 트랙이 둘로 갈렸으니 **둘 다** 본다.

1. 앵커가 원문에 없으면 그 사실을 **버리고 센다**. 조용히 사라지면 "아무것도 안
   나온 것" 과 구분이 안 된다(ADR-0037 결정 5)
2. 앵커 비교 규칙이 `build.py` 와 **같아야 한다**. 다르면 여기서 통과한 앵커가
   거기서 죽는다
3. 키가 없으면 **멈춘다.** 조용히 스텁으로 물러나지 않는다(결정 4)
4. 트랙 B 의 key 는 **열다섯 밖으로 못 나간다.** 밖의 이름이 오면 그 값은 안 선다 —
   옛 추출기는 문서가 쓴 이름을 받아 별칭 표에서 찾았고, 표에 없으면 미분류로
   떨어졌다(ADR-0056 맥락 ②)

갈라짐을 막는 장치(T-0127)는 `tests/test_wiki_roster.py` 가 본다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect import llm
from finnect.wiki import build, extract_nodes, extract_profile, port, profile, spots
from finnect.wiki.extract_nodes import LlmNodes
from finnect.wiki.extract_profile import LlmProfile
from finnect.wiki.port import FileView, Known


class 가짜클라이언트:
    """준 대로 돌려준다. **네트워크를 안 쓴다.**"""

    model = "gpt-5.6-luna"

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._payload


VIEW = FileView(
    sha256="a" * 64,
    filename="회사소개서.pdf",
    chunks=((0, "주식회사 다시로는 2024년 3월 5일에 문을 열었다."),
            (1, "재구매율이 34%에서 51%로 올랐다.")),
)


def _spot(path: str) -> int:
    """자리표에서 번호를 찾는다. **숫자를 손으로 적지 않는다.**"""
    return next(i for i, s in enumerate(spots.SPOTS, 1) if s.path == path)


def _n(**kw) -> dict:
    """트랙 A 사실 하나. 스키마의 모든 칸이 온다(`strict: true`)."""
    base = {
        "spot": _spot("Customer/검증/{활동}-{결과}"), "instance": "파일럿-12개소",
        "key": None, "value": None,
        "text": "", "as_of": None, "grade": "1차", "source": None, "anchor": "",
    }
    return {**base, **kw}


def _v(**kw) -> dict:
    """트랙 B 값 하나."""
    base = {"key": "revenue", "value": "100", "text": "", "as_of": None,
            "qualifier": None, "anchor": ""}
    return {**base, **kw}


def _nodes(facts: list[dict]) -> LlmNodes:
    return LlmNodes(client=가짜클라이언트({"facts": facts}))


def _values(vals: list[dict]) -> LlmProfile:
    return LlmProfile(client=가짜클라이언트({"values": vals}))


# ─────────────────────────────────────────────────────────────────
# 앵커 — 트랙이 갈려도 규칙이 같다
# ─────────────────────────────────────────────────────────────────


def test_앵커가_원문에_있으면_통과한다() -> None:
    ex = _nodes([_n(text="재구매율이 올랐다", anchor="재구매율이 34%에서 51%로")])
    got = ex.extract(VIEW, Known())
    assert len(got) == 1
    assert got[0].path == "Customer/검증/파일럿-12개소"
    assert ex.dropped == []


def test_앵커가_원문에_없으면_버리고_센다() -> None:
    """**가장 중요한 검사다.** LLM 이 조사 하나만 바꿔도 근거를 잃는다."""
    ex = _nodes([
        _n(text="지어낸 사실", anchor="이 문장은 원문에 없다"),
        _n(text="진짜", anchor="재구매율이 34%에서 51%로"),
    ])
    got = ex.extract(VIEW, Known())
    assert [f.text for f in got] == ["진짜"]
    assert len(ex.dropped) == 1
    assert "원문에 없다" in ex.dropped[0][1]


def test_트랙_B_도_앵커가_없으면_버린다() -> None:
    """**여기서 빠지면 자격 판별 입력이 사라진다.** 그래도 지어낸 근거보다 낫다."""
    ex = _values([
        _v(value="100", anchor="이 문장은 원문에 없다"),
        _v(value="200", anchor="2024년 3월 5일에 문을 열었다"),
    ])
    got = ex.extract(VIEW, Known())
    assert [f.value for f in got] == ["200"]
    assert len(ex.dropped) == 1


def test_공백만_다른_앵커는_통과한다() -> None:
    """`build.py` 가 공백을 지우고 찾는다. **여기 규칙이 거기와 같아야 한다.**"""
    ex = _nodes([_n(text="띄어쓰기가 다르다", anchor="2024년3월5일에 문을열었다")])
    assert len(ex.extract(VIEW, Known())) == 1


def test_앵커_비교가_build_와_같은_규칙이다() -> None:
    """규칙이 갈라지면 여기서 통과한 앵커가 `build.py` 에서 죽는다."""
    for s in ("공백  여럿", "줄\n바꿈", " 앞뒤 ", "탭\t사이"):
        assert port.squash(s) == build._squash(s)


# ─────────────────────────────────────────────────────────────────
# 트랙 A — 자리를 추출기가 정한다
# ─────────────────────────────────────────────────────────────────


def test_번호가_자리표의_경로가_된다() -> None:
    """**경로를 다시 쓰게 하지 않는다**(ADR-0058). 번호가 표를 가리킨다."""
    ex = _nodes([_n(spot=_spot("Market/시장규모"), instance=None,
                    anchor="재구매율이 34%에서 51%로")])
    assert ex.extract(VIEW, Known())[0].path == "Market/시장규모"


def test_인스턴스가_깊은_자리를_채운다() -> None:
    """`Custom/특허/{상태}-{번호}`. **깊이는 표가 정하고 이름만 문서에서 온다.**"""
    ex = _nodes([_n(spot=_spot("Custom/특허/{상태}-{번호}"),
                    instance="등록-10-2025-0114882", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].path == "Custom/특허/등록-10-2025-0114882"


def test_표_밖의_번호는_검토_대기로_간다() -> None:
    """**사실이 안 사라진다.** 표 밖으로 나가는 길이 이제 없다."""
    ex = _nodes([_n(spot=99, anchor="재구매율이 34%")])
    got = ex.extract(VIEW, Known())[0]
    assert got.path == "Custom/검토 대기"
    assert got.why


def test_자리를_안_고르면_검토_대기로_간다() -> None:
    """**버리지 않는다.** 검토 대기가 트리의 진짜 자리라 화면에 뜬다."""
    ex = _nodes([_n(spot=None, instance=None, text="무엇", anchor="재구매율이 34%")])
    got = ex.extract(VIEW, Known())[0]
    assert got.path == "Custom/검토 대기"
    assert got.why


def test_스키마가_이름과_값을_받고_한정어는_안_받는다() -> None:
    """**`kind` 를 안 받는다**(ADR-0059). 이름·값이 짝으로 왔나가 곧 종류다 —
    받으면 「값이라고 했는데 값이 없는」 상태가 표현된다.
    """
    props = extract_nodes.SCHEMA["properties"]["facts"]["items"]["properties"]
    assert set(props) == {
        "spot", "instance", "key", "value", "text", "as_of", "grade", "source", "anchor",
    }
    assert "qualifier" not in props
    assert "kind" not in props


def test_값이면_이름과_값이_붙고_시점이_이름에서_떨어진다() -> None:
    """**문서가 쓴 표현은 `text` 에 남는다.** 고친 값은 `value` 에만 있다."""
    ex = _nodes([_n(key="2025년 매출액", value="86400000", text="2025년 매출 8,640만원",
                    as_of="2025-12-31", anchor="재구매율이 34%")])
    f = ex.extract(VIEW, Known())[0]
    assert f.key == "매출액", "시점을 코드가 뗀다"
    assert (f.value, f.text) == ("86400000", "2025년 매출 8,640만원")
    assert f.as_of == dt.date(2025, 12, 31)


def test_이름이나_값이_반쪽이면_서술이_된다() -> None:
    """어느 쪽도 반쪽이라 서술로 떨어뜨린다 — 이름 없는 숫자를 화면에 안 낸다."""
    for kw in ({"key": "매출액"}, {"value": "86400000"}):
        f = _nodes([_n(text="x", anchor="재구매율이 34%", **kw)]).extract(VIEW, Known())[0]
        assert (f.key, f.value) == (None, None)


def test_날짜가_아니면_시점_없는_값이_된다() -> None:
    """**지어내지 않는다.** `2024년쯤` 을 날짜로 만들면 없는 시계열이 생긴다."""
    ex = _nodes([_n(kind="value", value="100", as_of="2024년쯤", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].as_of is None


def test_등급과_출처가_실린다() -> None:
    """기획 §5 — **`source` 는 `2차` 일 때만 산다.**

    다른 등급에 기관 이름이 붙으면 프론트매터가 「이 값은 통계청 것」이라고 말하는데
    문서는 그런 적이 없게 된다.
    """
    cited = _nodes([_n(grade="2차", source="통계청", text="x", anchor="재구매율이 34%")])
    f = cited.extract(VIEW, Known())[0]
    assert (f.grade, f.source) == ("2차", "통계청")

    ours = _nodes([_n(grade="1차", source="통계청", text="x", anchor="재구매율이 34%")])
    assert ours.extract(VIEW, Known())[0].source == ""

    #: 모르는 등급이 오면 `1차` 다. **`실측`·`미정` 은 추출기가 낼 수 없다**
    odd = _nodes([_n(grade="실측", text="x", anchor="재구매율이 34%")])
    assert odd.extract(VIEW, Known())[0].grade == "1차"


# ─────────────────────────────────────────────────────────────────
# 트랙 B — key 가 열다섯 밖으로 못 나간다
# ─────────────────────────────────────────────────────────────────


def test_스키마가_key_를_열다섯으로_막는다() -> None:
    """**여기가 사전 문제를 끝내는 자리다**(ADR-0056 맥락 ②).

    옛 추출기는 문서가 쓴 이름을 받아 별칭 43개에서 찾았다. 표에 없으면 미분류로
    떨어졌고, 그건 자격 판별 입력이라 **그 회사가 규모 조건 공고에서 조용히 빠졌다.**
    """
    enum = extract_profile.SCHEMA["properties"]["values"]["items"]["properties"]["key"]["enum"]
    assert set(enum) == set(profile.PROFILE_KEYS)
    assert len(enum) == 15


def test_열다섯_밖의_key_는_안_선다() -> None:
    """enum 을 어겨도 **지어내지 않는다.** 무엇이 버려졌는지는 남는다."""
    ex = _values([_v(key="tenure", value="1년 6개월", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known()) == []
    assert len(ex.dropped) == 1


def test_값이_비면_안_선다() -> None:
    """빈 값이 앉으면 화면이 「채웠다」고 말하는데 볼 것이 없다."""
    ex = _values([_v(key="revenue", value="   ", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known()) == []


def test_시점을_파싱한다() -> None:
    ex = _values([_v(key="revenue", value="100", as_of="2024-12-31", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].as_of == dt.date(2024, 12, 31)


def test_트랙_B_는_노드를_안_만든다() -> None:
    """**그래프에 안 뜬다.** 회사 정보 표 한 장이다(ADR-0056 결정 5)."""
    got = _values([_v(anchor="재구매율이 34%")]).extract(VIEW, Known())[0]
    assert not hasattr(got, "path")


# ─────────────────────────────────────────────────────────────────
# 프롬프트와 설정
# ─────────────────────────────────────────────────────────────────


def test_원문과_현재_상태만_넘긴다() -> None:
    """사용자 프롬프트는 파일 이름과 원문뿐이다. **현재 상태는 시스템 쪽에 있다.**"""
    c = 가짜클라이언트({"facts": []})
    LlmNodes(client=c).extract(VIEW, Known.of(spots=["Competitor/배달의민족"]))
    user, system = c.calls[0]["user"], c.calls[0]["system"]
    assert "회사소개서.pdf" in user
    assert "재구매율이 34%" in user
    assert "배달의민족" not in user
    assert "- `Competitor/{업체명}` — 배달의민족" in system


def test_자리표_전체가_프롬프트에_있다() -> None:
    """**스키마가 번호를 안 막는다**(정수 하나다). 표가 프롬프트에만 있으므로 전부 실려야 한다."""
    system = extract_nodes.system_prompt(Known())
    for i, s in enumerate(spots.SPOTS, 1):
        assert f"[{i}] {s.path}" in system, s.path
    #: 등급 셋만 낼 수 있다 — `실측`·`미정` 은 추출이 정하는 것이 아니다
    grade = extract_nodes.SCHEMA["properties"]["facts"]["items"]["properties"]["grade"]
    assert grade["enum"] == ["1차", "2차", "가정"]


def test_트랙_B_프롬프트가_별칭을_힌트로만_싣는다() -> None:
    """별칭은 **라우팅에서 빠졌다.** 문서가 쓰는 말이 무엇인지 알려 주기만 한다."""
    system = extract_profile.system_prompt(Known())
    assert "`headcount`" in system
    assert "상시 근로자" in system


def test_키가_없으면_스텁으로_안_물러난다(monkeypatch) -> None:  # noqa: ANN001
    """**조용히 물러나면 픽스처 7건만 처리하고 나머지를 조용히 버린다.**"""
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    with pytest.raises(llm.MissingKey, match="OPENAI_API_KEY"):
        llm.client()


@pytest.mark.parametrize(
    ("mod", "cls"), [(extract_nodes, LlmNodes), (extract_profile, LlmProfile)]
)
def test_설정이_llm_이면_양쪽_다_llm_이_된다(mod, cls, monkeypatch) -> None:  # noqa: ANN001
    """**설정 하나가 둘을 고른다.** 한쪽만 LLM 이면 위키가 반쪽만 진짜가 된다."""
    monkeypatch.setattr(mod.settings, "wiki_extractor", "llm")
    assert isinstance(mod.get_extractor(), cls)
