"""자리를 고르는 법과 갈라짐을 막는 장치 — ADR-0058.

자리표가 **마흔여섯 고정**이 되면서 이 파일이 잠그는 것이 바뀌었다.

    옛  LLM 이 경로를 짓는다  →  `기능`·`주요기능`·`핵심 기능` 이 전부 새 자리
    새  LLM 이 번호를 고른다  →  고정 자리는 갈릴 수가 없다

**남은 위험은 인스턴스 이름 하나다.** `{…}` 가 있는 자리 열일곱에서 같은 경쟁사가
`배달의민족` 과 `배달의 민족` 으로 두 자리에 앉는 것 — 그 자리만 그물이 걸린다.

**유사도를 안 쓴다.** 쓰면 같은 문서를 두 번 올릴 때 다른 자리로 가서 비결정론이 된다 —
이 파일의 마지막 절이 그것을 잠근다.
"""

from __future__ import annotations

import pytest

from finnect.wiki import port, spots
from finnect.wiki.extract_nodes import LlmNodes
from finnect.wiki.port import Known, Roster

VIEW = port.FileView(
    sha256="a" * 64,
    filename="회사소개서.pdf",
    chunks=((0, "우리 제품의 기능은 셋이다. 재구매율이 34%에서 51%로 올랐다."),),
)
ANCHOR = "재구매율이 34%에서 51%로"


def num(path: str) -> int:
    """자리표에서 번호를 찾는다. **숫자를 손으로 적지 않는다** — 표에 한 줄이 끼면 밀린다."""
    return next(i for i, s in enumerate(spots.SPOTS, 1) if s.path == path)


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
        "spot": None, "instance": None, "key": None, "value": None, "text": "x",
        "as_of": None, "grade": "1차", "source": None, "anchor": ANCHOR,
    }
    return {**base, **kw}


def _paths(facts: list[dict], known: Known | None = None) -> list[str]:
    ex = LlmNodes(client=가짜클라이언트(facts))
    return [f.path for f in ex.extract(VIEW, known or Known())]


# ─────────────────────────────────────────────────────────────────
# 번호 — 자리를 짓게 하지 않는다
# ─────────────────────────────────────────────────────────────────


def test_번호가_자리로_풀린다():
    """경로를 다시 쓰게 하면 `Product/기능`·`기능`·`Product/ 기능` 이 전부 새 자리가 된다."""
    assert _paths([_n(spot=num("Company/팀"))]) == ["Company/팀"]


def test_고정_자리는_인스턴스를_무시한다():
    """**딸려 온 이름이 고정 자리를 흔들면 안 된다.**"""
    assert _paths([_n(spot=num("Financial/매출"), instance="아무거나")]) == ["Financial/매출"]


def test_없는_번호는_지어내지_않는다():
    """모델이 범위 밖 번호를 낼 수 있다. 자리를 만들어 주면 엉뚱한 데 앉는다."""
    for bad in (0, 47, 999, None):
        assert _paths([_n(spot=bad)]) == [spots.REVIEW.path]


def test_자리를_못_골라도_버리지_않는다():
    """검토 대기가 **자리로 산다.** 옛 미분류는 트리에 자리가 없어 화면에 안 나왔다."""
    got = LlmNodes(client=가짜클라이언트([_n(spot=None)])).extract(VIEW, Known())
    assert got[0].path == spots.REVIEW.path
    assert got[0].why  # 왜 거기 갔는지 남는다


# ─────────────────────────────────────────────────────────────────
# 인스턴스 — 짓게 하는 것은 이름뿐이다
# ─────────────────────────────────────────────────────────────────


def test_인스턴스가_템플릿을_채운다():
    got = _paths([
        _n(spot=num("Competitor/{업체명}"), instance="배달의민족"),
        _n(spot=num("Custom/특허/{상태}-{번호}"), instance="등록-10-2025-0114882"),
    ])
    assert got == ["Competitor/배달의민족", "Custom/특허/등록-10-2025-0114882"]


def test_구멍이_둘이면_슬래시로_나눈다():
    """자리표에서 이 모양은 하나뿐이다 — `Product/{서비스명}/화면/{화면명}`."""
    got = _paths([_n(spot=num("Product/{서비스명}/화면/{화면명}"), instance="다시로/주문화면")])
    assert got == ["Product/다시로/화면/주문화면"]


def test_이름이_안_오면_리터럴_폴더를_안_만든다():
    """`Competitor/{업체명}` 이 그대로 서면 **그 글자가 사용자가 보는 자리 이름이 된다.**"""
    assert _paths([_n(spot=num("Competitor/{업체명}"))]) == [spots.REVIEW.path]
    #: 구멍이 둘인데 하나만 와도 같다
    assert _paths([
        _n(spot=num("Product/{서비스명}/화면/{화면명}"), instance="다시로")
    ]) == [spots.REVIEW.path]


# ─────────────────────────────────────────────────────────────────
# 코드 그물 — 인스턴스 이름에만 걸린다
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("written", ["배달의 민족", "배달의민족 ", "배달의·민족", "배달의(민족)"])
def test_정규화가_같으면_기존_이름으로_돌린다(written: str):
    known = Known.of(spots=["Competitor/배달의민족"])
    got = _paths([_n(spot=num("Competitor/{업체명}"), instance=written)], known)
    assert got == ["Competitor/배달의민족"]


def test_한_호출_안에서_갈린_이름도_모인다():
    """**프롬프트에 있는 건 이전 상태다.** 한 파일에서 둘 다 만들 수 있다."""
    n = num("Competitor/{업체명}")
    got = _paths([_n(spot=n, instance="배달의민족"), _n(spot=n, instance="배달의 민족")])
    assert got == ["Competitor/배달의민족"] * 2


def test_먼저_온_표기가_이긴다():
    """뒤엣것이 이기면 같은 파일을 두 번 넣을 때 이름이 흔들린다."""
    n = num("Competitor/{업체명}")
    got = _paths([_n(spot=n, instance="요기 요"), _n(spot=n, instance="요기요")])
    assert got == ["Competitor/요기 요"] * 2


def test_부르는_쪽의_상태를_안_늘린다():
    """**추출이 실패한 파일이 다음 파일의 자리 목록을 오염시키면 안 된다.**"""
    known = Known.of(spots=["Competitor/배달의민족"])
    _paths([_n(spot=num("Competitor/{업체명}"), instance="쿠팡이츠")], known)
    assert known.spots.names == ["Competitor/배달의민족"]


# ─────────────────────────────────────────────────────────────────
# 유사도를 안 쓴다 — **이 절이 결정을 잠근다**
# ─────────────────────────────────────────────────────────────────


def test_비슷하기만_한_이름은_다른_자리다():
    """`배민` 은 `배달의민족` 으로 안 접힌다. 접으면 다시 비결정론이다."""
    known = Known.of(spots=["Competitor/배달의민족"])
    assert _paths([_n(spot=num("Competitor/{업체명}"), instance="배민")], known) == [
        "Competitor/배민"
    ]


def test_마디가_다르면_안_섞인다():
    """통째로 정규화하면 `A/BC` 와 `AB/C` 가 같아진다 — 다른 자리인데 하나로 묶인다."""
    r = Roster.of(["Company/기본정보"], norm=port.tree.norm_path)
    assert r.fold("Company/기본/정보") == "Company/기본/정보"


# ─────────────────────────────────────────────────────────────────
# 프롬프트 — 표와 현재 상태가 같이 실린다
# ─────────────────────────────────────────────────────────────────


def test_자리표_전체가_프롬프트에_번호와_함께_실린다():
    c = 가짜클라이언트([])
    LlmNodes(client=c).extract(VIEW, Known())
    system = c.calls[0]["system"]
    for i, s in enumerate(spots.SPOTS, 1):
        assert f"[{i}] {s.path}" in system
    #: **「담는 것」도 같이 간다** — 경로만 주면 어디에 넣을지 고를 근거가 없다
    assert spots.SPOTS[0].holds in system


def test_지금_있는_이름이_자리별로_묶여_실린다():
    """**어느 자리의 이름인지 안 밝히면 자리를 건너 베껴진다**(2026-08-22 실측).

    평평한 경로 목록이었을 때 `Customer/페르소나/출원-10-2025-0114882` 와
    `Custom/인증/성남·용인 소상공인-30명-…` 이 나왔다 — 특허 번호가 페르소나 이름이
    되고 인터뷰 이름이 인증 이름이 됐다.
    """
    c = 가짜클라이언트([])
    LlmNodes(client=c).extract(
        VIEW,
        Known.of(spots=[
            "Competitor/배달의민족", "Competitor/요기요",
            "Custom/특허/등록-10-2025-0114882",
            "Company/팀",                    # 고정 자리 — 실릴 일이 없다
            spots.REVIEW.path,               # 오류 통 — 자리 이름이 아니다
        ]),
    )
    system = c.calls[0]["system"]
    assert "- `Competitor/{업체명}` — 배달의민족 · 요기요" in system
    assert "- `Custom/특허/{상태}-{번호}` — 등록-10-2025-0114882" in system
    #: **경로를 통째로 안 보인다.** 보이면 그 문자열이 다른 자리로 베껴진다
    assert "Competitor/배달의민족" not in system
    #: 고정 자리는 이름을 지을 일이 없다
    assert "Company/팀` —" not in system
    #: **검토 대기가 실리면 `Competitor/검토 대기` 가 나온다** — 실제로 나왔다
    assert "검토 대기` —" not in system


def test_번호가_붙은_목록이_자리표_하나뿐이다():
    """**둘이면 모델이 이어 세어 표 밖 번호를 낸다**(2026-08-22 실측).

    자리표도 `[n]`, 「지금 있는 자리」도 `[n]` 이었다. 모델이 `spot=47~65` 를 냈고
    (표는 46 까지다) **사실 30건이 그것 때문에 검토 대기로 갔다.**
    """
    c = 가짜클라이언트([])
    LlmNodes(client=c).extract(VIEW, Known.of(spots=["Competitor/배달의민족"] * 1))
    system = c.calls[0]["system"]
    import re
    got = sorted({int(m) for m in re.findall(r"^\[(\d+)\]", system, re.M)})
    assert got == list(range(1, len(spots.SPOTS) + 1)), "번호가 자리표 것만 있어야 한다"


def test_아무것도_없으면_없다고_적는다():
    """빈 목록을 그냥 두면 프롬프트에 제목만 남아서 모델이 잘린 줄 안다."""
    c = 가짜클라이언트([])
    LlmNodes(client=c).extract(VIEW, Known())
    assert "(아직 없다)" in c.calls[0]["system"]
    assert Roster().render() == "(아직 없다)"


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
