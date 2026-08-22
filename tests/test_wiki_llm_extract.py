"""LLM 추출기 — 키 없이 검증할 수 있는 것만 (ADR-0037 · plan/22 T-0126).

**진짜 호출은 여기서 안 한다.** 키가 있어야 하고 돈이 들고 답이 매번 다르다.
정확도는 `--score` 가 픽스처 118개와 대조해서 잰다.

여기서 막는 것은 **배관과 규율**이다. 트랙이 둘로 갈렸으니 **둘 다** 본다.

1. 앵커가 원문에 없으면 그 사실을 **버리고 센다**. 조용히 사라지면 "아무것도 안
   나온 것" 과 구분이 안 된다(ADR-0037 결정 5)
2. 앵커 비교 규칙이 `build.py` 와 **같아야 한다**. 다르면 여기서 통과한 앵커가
   거기서 죽는다
3. 키가 없으면 **멈춘다.** 조용히 스텁으로 물러나지 않는다(결정 4)
4. 트랙 B 의 key 는 **열넷 밖으로 못 나간다.** 밖의 이름이 오면 그 값은 안 선다 —
   옛 추출기는 문서가 쓴 이름을 받아 별칭 표에서 찾았고, 표에 없으면 미분류로
   떨어졌다(ADR-0056 맥락 ②)

갈라짐을 막는 장치(T-0127)는 `tests/test_wiki_roster.py` 가 본다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect import llm
from finnect.wiki import build, extract_nodes, extract_profile, port, profile
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


def _n(**kw) -> dict:
    """트랙 A 사실 하나. 스키마의 모든 칸이 온다(`strict: true`)."""
    base = {
        "node_ref": None, "node_category": "Customer", "node_path": "검증",
        "key_ref": None, "key_new": "재구매율 상승",
        "qualifier_ref": None, "qualifier_new": None,
        "kind": "event", "text": "", "value": None, "as_of": None, "anchor": "",
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
    assert got[0].key == "재구매율 상승"
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


def test_카테고리와_경로가_한_자리로_붙는다() -> None:
    """`node_category` 와 `node_path` 가 함께 `node_new` 다. 붙인 것이 노드 경로다."""
    ex = _nodes([_n(node_category="Market", node_path="시장규모",
                    anchor="재구매율이 34%에서 51%로")])
    assert ex.extract(VIEW, Known())[0].path == "Market/시장규모"


def test_깊이가_자유다() -> None:
    """`Custom/특허/등록-10-…`. **트리가 두 층으로 고정이 아니다**(ADR-0056 결정 2)."""
    ex = _nodes([_n(node_category="Custom", node_path="특허/등록-10-2025-0114882",
                    anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].path == "Custom/특허/등록-10-2025-0114882"


def test_카테고리_밖이면_Custom_밑으로_민다() -> None:
    """**LLM 이 enum 을 어겨도 사실이 안 사라진다.** `Custom` 이 탈출구다."""
    ex = _nodes([_n(node_category="없는카테고리", node_path="무엇", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].path == "Custom/없는카테고리/무엇"


def test_자리를_안_고르면_검토_대기로_간다() -> None:
    """**버리지 않는다.** 검토 대기가 트리의 진짜 자리라 화면에 뜬다."""
    ex = _nodes([_n(node_ref=None, node_category=None, node_path=None,
                    text="무엇", anchor="재구매율이 34%")])
    got = ex.extract(VIEW, Known())[0]
    assert got.path == "Custom/검토 대기"
    assert got.why


def test_서술에는_값_필드가_안_붙는다() -> None:
    """`value` 가 서술에 붙으면 병합 키가 어긋난다."""
    ex = _nodes([_n(kind="event", value="100", as_of="2024-12-31", qualifier_new="시드",
                    text="x", anchor="재구매율이 34%")])
    f = ex.extract(VIEW, Known())[0]
    assert (f.value, f.as_of, f.qualifier) == (None, None, None)


def test_값이면_값_필드가_붙는다() -> None:
    ex = _nodes([_n(kind="value", value="100", as_of="2024-12-31", qualifier_new="시드",
                    key_new="매출", text="x", anchor="재구매율이 34%")])
    f = ex.extract(VIEW, Known())[0]
    assert f.kind == "value"
    assert (f.value, f.as_of, f.qualifier) == ("100", dt.date(2024, 12, 31), "시드")


def test_날짜가_아니면_시점_없는_값이_된다() -> None:
    """**지어내지 않는다.** `2024년쯤` 을 날짜로 만들면 없는 시계열이 생긴다."""
    ex = _nodes([_n(kind="value", value="100", as_of="2024년쯤", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].as_of is None


def test_key_가_안_오면_문장이_키가_된다() -> None:
    """**안 묶인다. 잘못 묶는 것보다 낫다.**"""
    ex = _nodes([_n(key_new=None, text="재구매율이 올랐다", anchor="재구매율이 34%")])
    assert ex.extract(VIEW, Known())[0].key == "재구매율이 올랐다"


# ─────────────────────────────────────────────────────────────────
# 트랙 B — key 가 열넷 밖으로 못 나간다
# ─────────────────────────────────────────────────────────────────


def test_스키마가_key_를_열넷으로_막는다() -> None:
    """**여기가 사전 문제를 끝내는 자리다**(ADR-0056 맥락 ②).

    옛 추출기는 문서가 쓴 이름을 받아 별칭 43개에서 찾았다. 표에 없으면 미분류로
    떨어졌고, 그건 자격 판별 입력이라 **그 회사가 규모 조건 공고에서 조용히 빠졌다.**
    """
    enum = extract_profile.SCHEMA["properties"]["values"]["items"]["properties"]["key"]["enum"]
    assert set(enum) == set(profile.PROFILE_KEYS)
    assert len(enum) == 14


def test_열넷_밖의_key_는_안_선다() -> None:
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
    LlmNodes(client=c).extract(VIEW, Known.of(nodes=["Company/팀"]))
    user, system = c.calls[0]["user"], c.calls[0]["system"]
    assert "회사소개서.pdf" in user
    assert "재구매율이 34%" in user
    assert "Company/팀" not in user
    assert "[1] Company/팀" in system


def test_카테고리_열이_프롬프트와_스키마에_같이_있다() -> None:
    """**갈리면 모델이 프롬프트에 있는 이름을 내고 스키마가 튕긴다.**"""
    from finnect.wiki import tree

    enum = extract_nodes.SCHEMA["properties"]["facts"]["items"]["properties"]["node_category"]
    assert set(enum["enum"]) == {*tree.CATEGORIES, None}
    system = extract_nodes.system_prompt(Known())
    assert all(f"`{c}`" in system for c in tree.CATEGORIES)


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
