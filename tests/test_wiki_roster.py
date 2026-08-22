"""갈라짐을 막는 장치 — plan/22 T-0127 · ADR-0056 결정 6.

동적 이름의 유일한 위험은 **같은 얘기가 여러 자리로 흩어지는 것**이다
(`기능` · `주요기능` · `핵심 기능`). 사용자는 노드가 셋인 게 정상인지 모른다.

막는 방법이 둘이고 **둘 다 쓴다.**

1. **번호로 답하게 한다.** 프롬프트에 지금 있는 것을 번호와 함께 싣는다
2. **코드가 마지막 그물이다.** 새 이름이 와도 정규화 후 기존과 정확히 같으면 기존으로

**유사도를 안 쓴다.** 쓰면 같은 문서를 두 번 올릴 때 다른 자리로 가서 비결정론이 된다 —
이 파일의 마지막 절이 그것을 잠근다.
"""

from __future__ import annotations

import pytest

from finnect.wiki import port, tree
from finnect.wiki.extract_nodes import LlmNodes
from finnect.wiki.port import Known, Roster

VIEW = port.FileView(
    sha256="a" * 64,
    filename="회사소개서.pdf",
    chunks=((0, "우리 제품의 기능은 셋이다. 재구매율이 34%에서 51%로 올랐다."),),
)
ANCHOR = "재구매율이 34%에서 51%로"


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return {"facts": self._facts}


def _n(**kw) -> dict:
    base = {
        "node_ref": None, "node_category": None, "node_path": None,
        "key_ref": None, "key_new": "사실",
        "qualifier_ref": None, "qualifier_new": None,
        "kind": "event", "text": "x", "value": None, "as_of": None, "anchor": ANCHOR,
    }
    return {**base, **kw}


def _paths(facts: list[dict], known: Known) -> list[str]:
    return [f.path for f in LlmNodes(client=가짜클라이언트(facts)).extract(VIEW, known)]


# ─────────────────────────────────────────────────────────────────
# 번호 — 경로를 다시 쓰게 하지 않는다
# ─────────────────────────────────────────────────────────────────


def test_번호가_이름으로_풀린다():
    """자유 문자열로 받으면 `Product/기능`·`기능`·`Product/ 기능` 이 전부 새 자리가 된다."""
    known = Known.of(nodes=["Company/기본정보", "Company/팀", "Product/기능"])
    assert _paths([_n(node_ref=3)], known) == ["Product/기능"]


def test_번호가_새_이름을_이긴다():
    """둘 다 오면 번호가 이긴다. 모델이 번호를 쓰라는 것이 이 장치의 뜻이다."""
    known = Known.of(nodes=["Product/기능"])
    got = _paths([_n(node_ref=1, node_category="Market", node_path="시장규모")], known)
    assert got == ["Product/기능"]


def test_없는_번호는_지어내지_않는다():
    """**모델이 범위 밖 번호를 낼 수 있다.** 이름을 만들어 주면 엉뚱한 자리에 앉는다."""
    known = Known.of(nodes=["Product/기능"])
    #: 새 이름이 같이 왔으면 그쪽으로 떨어진다
    assert _paths([_n(node_ref=9, node_category="Market", node_path="시장규모")], known) == [
        "Market/시장규모"
    ]
    #: 새 이름도 없으면 검토 대기다. **버리지 않는다**
    assert _paths([_n(node_ref=9)], known) == [tree.REVIEW_PATH]


def test_현재_상태가_프롬프트에_번호와_함께_실린다():
    c = 가짜클라이언트([])
    known = Known.of(nodes=["Company/팀"], keys=["팀 구성"], qualifiers=["시드"])
    LlmNodes(client=c).extract(VIEW, known)
    system = c.calls[0]["system"]
    assert "[1] Company/팀" in system
    assert "[1] 팀 구성" in system
    assert "[1] 시드" in system


def test_아무것도_없으면_없다고_적는다():
    """빈 목록을 그냥 두면 프롬프트에 제목만 남아서 모델이 잘린 줄 안다."""
    c = 가짜클라이언트([])
    LlmNodes(client=c).extract(VIEW, Known())
    assert "(아직 없다)" in c.calls[0]["system"]
    assert Roster().render() == "(아직 없다)"


# ─────────────────────────────────────────────────────────────────
# 코드 그물 — 기존과 한 번
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("written", ["기 능", "기능 ", "기·능", "기(능)"])
def test_정규화가_같으면_기존_자리로_돌린다(written: str):
    """**모델이 번호를 안 써도 여기서 걸린다.** 마지막 그물이다."""
    known = Known.of(nodes=["Product/기능"])
    assert _paths([_n(node_category="Product", node_path=written)], known) == ["Product/기능"]


def test_key_와_한정어도_같은_그물을_쓴다():
    known = Known.of(keys=["팀 구성"], qualifiers=["예비창업패키지"])
    ex = LlmNodes(client=가짜클라이언트([
        _n(kind="value", key_new="팀구성", qualifier_new="예비 창업 패키지", value="15"),
    ]))
    got = ex.extract(VIEW, known)[0]
    assert (got.key, got.qualifier) == ("팀 구성", "예비창업패키지")


def test_부르는_쪽의_상태를_안_늘린다():
    """**추출이 실패한 파일이 다음 파일의 자리 목록을 오염시키면 안 된다.**

    `build.py` 는 파일마다 DB 에서 다시 읽지만, 한 `Known` 을 두 번 넘기는 코드가
    생기는 날 이 성질이 없으면 조용히 어긋난다.
    """
    known = Known.of(nodes=["Product/기능"])
    _paths([_n(node_category="Market", node_path="시장규모")], known)
    assert known.nodes.names == ["Product/기능"]


# ─────────────────────────────────────────────────────────────────
# 코드 그물 — 같은 호출 결과 안에서 한 번
# ─────────────────────────────────────────────────────────────────


def test_한_호출_안에서_갈린_이름도_모인다():
    """**프롬프트에 있는 건 이전 상태다.** 한 파일에서 둘 다 만들 수 있다(결정 6 마지막 문단)."""
    got = _paths(
        [
            _n(node_category="Product", node_path="기능"),
            _n(node_category="Product", node_path="기 능"),
        ],
        Known(),
    )
    assert got == ["Product/기능", "Product/기능"]


def test_먼저_온_표기가_이긴다():
    """뒤엣것이 이기면 같은 파일을 두 번 넣을 때 이름이 흔들린다."""
    got = _paths(
        [
            _n(node_category="Product", node_path="주요 기능"),
            _n(node_category="Product", node_path="주요기능"),
        ],
        Known(),
    )
    assert got == ["Product/주요 기능"] * 2


# ─────────────────────────────────────────────────────────────────
# 유사도를 안 쓴다 — **이 절이 결정을 잠근다**
# ─────────────────────────────────────────────────────────────────


def test_비슷하기만_한_이름은_다른_자리다():
    """`기능` 과 `주요기능` 은 다른 자리다. 접으면 다시 비결정론이다(ADR-0056 결정 6)."""
    known = Known.of(nodes=["Product/기능"])
    assert _paths([_n(node_category="Product", node_path="주요기능")], known) == [
        "Product/주요기능"
    ]


def test_마디가_다르면_안_섞인다():
    """통째로 정규화하면 `A/BC` 와 `AB/C` 가 같아진다 — 다른 자리인데 하나로 묶인다."""
    known = Known.of(nodes=["Company/기본정보"])
    assert _paths([_n(node_category="Company", node_path="기본/정보")], known) == [
        "Company/기본/정보"
    ]


# ─────────────────────────────────────────────────────────────────
# Roster 그 자체
# ─────────────────────────────────────────────────────────────────


def test_번호는_1부터다():
    """0 을 쓰면 「없음」과 「첫째」가 JSON 에서 구분이 안 된다."""
    r = Roster.of(["가", "나"])
    assert (r.ref(1), r.ref(2)) == ("가", "나")
    assert r.ref(0) is None
    assert r.ref(3) is None
    assert r.ref(None) is None


def test_갈래를_뜨면_원본이_안_자란다():
    r = Roster.of(["가"])
    b = r.copy()
    b.fold("나")
    assert r.names == ["가"]
    assert b.names == ["가", "나"]


def test_빈_이름은_등록되지_않는다():
    """빈 자리가 번호를 먹으면 그 뒤 번호가 통째로 밀린다."""
    r = Roster()
    assert r.fold("  ") == ""
    assert r.fold(None) == ""
    assert r.names == []
