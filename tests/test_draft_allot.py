"""배분 — 어느 사실을 누가 맡나 (plan/16 T-0064).

여기서 막는 것은 **규율 넷**이다.

1. **다투는 것이 없으면 LLM 을 안 부른다.** 나눌 것이 없으면 각 항목이 자기 자리의
   사실을 그냥 다 쓴다
2. **겹침 쌍 안에서만 다툰다.** 쌍이 아닌 항목끼리는 같은 사실을 써도 된다 —
   금지 대상은 사실 공유가 아니라 서사 재사용이다
3. **요약 항목은 안 다툰다.** 되풀이하라고 있는 자리다(T-0063 이 표시한다)
4. **못 채운 곳은 코드가 센다.** 판단이 아니라 뺄셈이라 LLM 에 물으면 매번 달라진다
"""

from __future__ import annotations

from finnect.draft.allot import Allotter, FactView, ItemView


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


FACTS = [
    FactView(id=11, place="problem", text="철강 경기 침체로 수주가 끊겼다"),
    FactView(id=12, place="problem", text="설비 노후로 불량률이 올랐다"),
    FactView(id=13, place="identity", text="다시로는 중고 설비를 되살린다"),
]

BACKGROUND = ItemView(
    index=0, number="2-1", title="사업수행 배경 및 목적",
    instruction="배경 및 필요성, 목적 등을 자세하게 기술", places=("problem", "identity"),
)
NEED = ItemView(
    index=1, number="2-2", title="지원필요성",
    instruction="애로사항 중심으로 필요성, 시의성을 기술", places=("problem",),
)


def _allot(out: dict, items, pairs, facts=None):  # noqa: ANN001
    a = Allotter(client=가짜클라이언트(out))
    return a, a.allot(items, facts if facts is not None else FACTS, pairs)


class Test안_다툴_때:
    def test_쌍이_없으면_LLM_을_안_부른다(self) -> None:
        """**나눌 것이 없으면 부를 이유가 없다.**"""
        a, got = _allot({"assign": []}, [BACKGROUND, NEED], pairs=[])

        assert a.client.calls == []
        assert got[0].fact_ids == (11, 12, 13)
        assert got[1].fact_ids == (11, 12)

    def test_쌍이어도_후보가_안_겹치면_안_부른다(self) -> None:
        other = ItemView(index=1, number="4", title="팀 구성",
                         instruction=None, places=("team",))
        a, _ = _allot({"assign": []}, [BACKGROUND, other], pairs=[(0, 1)])

        assert a.client.calls == []


class Test다툴_때:
    def test_주인만_그_사실을_쓴다(self) -> None:
        out = {"assign": [
            {"fact": 11, "item": 1, "why": "애로사항이다"},
            {"fact": 12, "item": 0, "why": "배경이다"},
        ]}
        _, got = _allot(out, [BACKGROUND, NEED], pairs=[(0, 1)])

        assert got[0].fact_ids == (12, 13)
        assert got[1].fact_ids == (11,)

    def test_다투지_않는_사실은_그대로_남는다(self) -> None:
        """`identity` 는 2-2 의 자리가 아니라 애초에 안 다툰다."""
        _, got = _allot({"assign": [{"fact": 11, "item": 1, "why": "x"}]},
                        [BACKGROUND, NEED], pairs=[(0, 1)])

        assert 13 in got[0].fact_ids

    def test_주인을_못_정한_사실은_아무도_안_쓴다(self) -> None:
        """**양쪽 다 주면 중복이 그대로 나오고, 임의로 주면 설명할 수 없다.**"""
        _, got = _allot({"assign": []}, [BACKGROUND, NEED], pairs=[(0, 1)])

        assert 11 not in got[0].fact_ids and 11 not in got[1].fact_ids

    def test_후보가_아닌_항목에_주면_버리고_센다(self) -> None:
        a, got = _allot({"assign": [{"fact": 11, "item": 9, "why": "x"}]},
                        [BACKGROUND, NEED], pairs=[(0, 1)])

        assert a.dropped == [("item", "11→9")]
        assert 11 not in got[0].fact_ids

    def test_다투는_사실만_프롬프트에_넣는다(self) -> None:
        a, _ = _allot({"assign": []}, [BACKGROUND, NEED], pairs=[(0, 1)])
        user = a.client.calls[0]["user"]

        assert "#11" in user and "#12" in user
        assert "#13" not in user

    def test_지시문을_같이_보낸다(self) -> None:
        """**항목 제목보다 지시문이 무엇을 요구하는지 정확하다.**"""
        a, _ = _allot({"assign": []}, [BACKGROUND, NEED], pairs=[(0, 1)])

        assert "애로사항 중심으로" in a.client.calls[0]["user"]


class Test요약_항목:
    def test_안_다툰다(self) -> None:
        """**되풀이하라고 있는 자리다**(T-0063)."""
        summary = ItemView(index=1, number="3", title="요약", instruction=None,
                           places=("problem",), summary_of_others=True)
        a, got = _allot({"assign": []}, [BACKGROUND, summary], pairs=[(0, 1)])

        assert a.client.calls == []
        assert got[1].fact_ids == (11, 12)


class Test못_채운_곳:
    def test_사실이_0건인_자리를_센다(self) -> None:
        """**F6-6 이 이것이다.** 판단이 아니라 뺄셈이라 코드가 한다."""
        item = ItemView(index=0, number="4", title="팀 구성", instruction=None,
                        places=("team", "problem"))
        a, got = _allot({"assign": []}, [item], pairs=[])

        assert got[0].missing == ("team",)
        assert a.client.calls == []

    def test_필수와_선택을_나눠_센다(self) -> None:
        """**같이 세면 "못 채운 곳 9군데" 가 뜨고 그중 둘만 진짜 막힌 것이다.**"""
        item = ItemView(index=0, number="4", title="팀 구성", instruction=None,
                        places=("team",), places_optional=("roadmap",))
        _, got = _allot({"assign": []}, [item], pairs=[])

        assert got[0].missing == ("team",)
        assert got[0].missing_optional == ("roadmap",)

    def test_선택_자리의_사실도_쓴다(self) -> None:
        item = ItemView(index=0, number="1", title="소개", instruction=None,
                        places=("identity",), places_optional=("problem",))
        _, got = _allot({"assign": []}, [item], pairs=[])

        assert got[0].fact_ids == (11, 12, 13)

    def test_위키가_비면_전부_못_채움이다(self) -> None:
        _, got = _allot({"assign": []}, [BACKGROUND], pairs=[], facts=[])

        assert got[0].fact_ids == ()
        assert set(got[0].missing) == {"problem", "identity"}


def test_최상단에서_httpx_를_안_끌고_온다() -> None:
    import ast
    import pathlib

    from finnect.draft import allot

    src = pathlib.Path(allot.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names and "finnect.llm" not in names
