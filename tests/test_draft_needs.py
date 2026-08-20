"""양식 읽기 — 항목이 무엇을 요구하나 (plan/16 T-0063 · ADR-0028).

**진짜 호출은 여기서 안 한다.** 키가 있어야 하고 돈이 들고 답이 매번 다르다.

여기서 막는 것은 **배관과 규율**이다.

1. 자리 이름을 **자유 생성하지 않는다.** 목록 밖이면 버리고 센다 — 위키에 없는
   자리를 요구하면 그 항목은 영원히 "못 채움" 이 된다
2. `index` 가 범위 밖이면 버린다. 스키마가 막지만 **와도 아는 척하지 않는다**
3. 문서 **하나에 호출 하나다.** 항목마다 부르면 항목들 사이 관계를 못 본다 —
   그게 이 작업의 전부다
4. 겹침 쌍은 **작은 쪽이 `a`** 다. 안 그러면 같은 쌍이 두 줄로 들어온다
5. 자리 목록이 `wiki/topics.py` 와 **같아야 한다.** 갈리면 여기서 통과한 자리가
   위키에 없다
"""

from __future__ import annotations

from finnect.draft import needs as nd
from finnect.wiki import topics


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


ITEMS = [
    nd.ItemView("2-1", "사업수행 배경 및 목적", 2, "배경 및 필요성, 목적 등을 자세하게 기술", None),
    nd.ItemView("2-2", "지원필요성", 2, "애로사항 중심으로 필요성, 시의성을 기술", "1page 이내"),
    nd.ItemView("3", "요약", 1, None, None),
]


def _read(out: dict, items: list[nd.ItemView] | None = None):
    r = nd.LlmReader(client=가짜클라이언트(out))
    return r, r.read("[붙임2] 사업계획서", items if items is not None else ITEMS)


def _item(index: int, places: list[str], summary: bool = False) -> dict:
    return {
        "index": index,
        "summary_of_others": summary,
        "needs": [{"place": p, "required": True} for p in places],
    }


class Test자리:
    def test_항목마다_필요한_자리를_낸다(self) -> None:
        _, reading = _read({"items": [_item(0, ["problem", "identity"])], "overlaps": []})

        assert [n.place for n in reading.items[0].needs] == ["problem", "identity"]

    def test_슬롯과_노드를_가른다(self) -> None:
        """화면이 "값이 비었다" 와 "글이 비었다" 를 다르게 말한다."""
        assert nd.PLACE_KIND["revenue"] == "slot"
        assert nd.PLACE_KIND["problem"] == "node"

    def test_목록_밖의_이름은_버리고_센다(self) -> None:
        """**지어낸 자리를 요구하면 그 항목은 영원히 "못 채움" 이다.**"""
        r, reading = _read({"items": [_item(0, ["problem", "우리회사강점"])], "overlaps": []})

        assert [n.place for n in reading.items[0].needs] == ["problem"]
        assert r.dropped == [("place", "우리회사강점")]

    def test_같은_자리가_두_번_오면_센_쪽을_남긴다(self) -> None:
        out = {
            "items": [{
                "index": 0, "summary_of_others": False,
                "needs": [
                    {"place": "problem", "required": False},
                    {"place": "problem", "required": True},
                ],
            }],
            "overlaps": [],
        }
        _, reading = _read(out)

        assert len(reading.items[0].needs) == 1
        assert reading.items[0].needs[0].required is True

    def test_필요_없으면_빈_목록이다(self) -> None:
        """표지·서명란처럼 사업 내용을 안 쓰는 자리가 실제로 있다."""
        _, reading = _read({"items": [_item(0, [])], "overlaps": []})

        assert reading.items[0].needs == ()

    def test_자리_목록이_위키와_같다(self) -> None:
        """**갈리면 여기서 통과한 자리가 위키에 없다.**"""
        assert set(nd.PLACES) == set(topics.SLOTS) | set(topics.NODES)
        assert len(nd.PLACES) == 24


class Test요약_항목:
    def test_일부러_되풀이하는_자리를_표시한다(self) -> None:
        """**중복 점검이 이걸 안 보면 정상 항목을 때린다**(T-0067)."""
        _, reading = _read({"items": [_item(2, ["identity"], summary=True)], "overlaps": []})

        assert reading.items[0].summary_of_others is True


class Test겹침_쌍:
    def test_쌍을_낸다(self) -> None:
        out = {"items": [], "overlaps": [{"a": 0, "b": 1, "note": "둘 다 필요성을 묻는다"}]}
        _, reading = _read(out)

        assert (reading.overlaps[0].a, reading.overlaps[0].b) == (0, 1)
        assert reading.overlaps[0].note == "둘 다 필요성을 묻는다"

    def test_작은_쪽이_a_다(self) -> None:
        """**안 그러면 같은 쌍이 두 줄로 들어온다.**"""
        out = {"items": [], "overlaps": [{"a": 2, "b": 0, "note": "x"}]}
        _, reading = _read(out)

        assert (reading.overlaps[0].a, reading.overlaps[0].b) == (0, 2)

    def test_같은_쌍을_두_번_안_낸다(self) -> None:
        out = {"items": [], "overlaps": [
            {"a": 0, "b": 1, "note": "x"}, {"a": 1, "b": 0, "note": "y"},
        ]}
        _, reading = _read(out)

        assert len(reading.overlaps) == 1

    def test_자기_자신과의_쌍은_버린다(self) -> None:
        r, reading = _read({"items": [], "overlaps": [{"a": 1, "b": 1, "note": "x"}]})

        assert reading.overlaps == ()
        assert r.dropped == [("overlap", "1,1")]


class Test범위:
    def test_index_가_밖이면_버린다(self) -> None:
        r, reading = _read({"items": [_item(9, ["problem"])], "overlaps": []})

        assert reading.items == ()
        assert r.dropped == [("index", "9")]

    def test_스키마가_index_범위를_막는다(self) -> None:
        _, _ = _read({"items": [], "overlaps": []})
        schema = nd._schema(3)

        assert schema["properties"]["items"]["items"]["properties"]["index"]["maximum"] == 2

    def test_스키마가_자리_이름을_막는다(self) -> None:
        enum = nd._schema(1)["properties"]["items"]["items"]["properties"]["needs"]
        assert enum["items"]["properties"]["place"]["enum"] == sorted(nd.PLACES)


class Test호출:
    def test_문서_하나에_호출_하나다(self) -> None:
        """**항목마다 부르면 항목들 사이 관계를 못 본다.**"""
        r, _ = _read({"items": [], "overlaps": []})

        assert len(r.client.calls) == 1

    def test_항목이_없으면_안_부른다(self) -> None:
        r = nd.LlmReader(client=가짜클라이언트({"items": [], "overlaps": []}))

        assert r.read("빈 양식", []) == nd.Reading((), ())
        assert r.client.calls == []

    def test_항목을_번호와_지시문과_함께_보낸다(self) -> None:
        r, _ = _read({"items": [], "overlaps": []})
        user = r.client.calls[0]["user"]

        assert "[0]" in user and "2-1 사업수행 배경 및 목적" in user
        assert "지시문: 배경 및 필요성" in user
        assert "분량: 1page 이내" in user

    def test_고를_수_있는_자리를_프롬프트에_적는다(self) -> None:
        r, _ = _read({"items": [], "overlaps": []})

        assert "`problem` 문제 인식" in r.client.calls[0]["system"]
        assert "`revenue` 매출액" in r.client.calls[0]["system"]


def test_최상단에서_httpx_를_안_끌고_온다() -> None:
    """**로컬은 통과하고 배포본만 죽는** 그 함정이다(CLAUDE.md)."""
    import ast
    import pathlib

    src = pathlib.Path(nd.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names
    assert "finnect.llm" not in names
