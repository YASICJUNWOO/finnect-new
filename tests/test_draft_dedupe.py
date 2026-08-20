"""중복 점검 (plan/16 T-0067).

**"1 장점 / 2 살면서 성공한 경험" 에 같은 이야기를 쓰면 안 된다** — 항목을 독립으로
쓰기로 한 결정이 만든 구멍이고, 여기가 그 구멍을 막는 마지막 겹이다.

1. **같은 청크는 코드가 잡는다.** 검사기를 따로 안 만든다 — F6-13 이 낸 배당금
2. **요약 항목은 안 건드린다.** 되풀이하라고 있는 자리다(T-0063)
3. **한 항목 안은 중복이 아니라 전개다**
4. 코드가 이미 잡은 쌍은 **LLM 에 다시 안 묻는다**
"""

from __future__ import annotations

from finnect.draft.dedupe import Clash, LlmChecker, ParaView, by_chunk


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


BACKGROUND = ParaView(item_index=0, paragraph=0, text="철강 경기로 수주가 끊겼다", chunk_ids=(5,))
NEED = ParaView(item_index=1, paragraph=0, text="수주가 끊겨 어렵다", chunk_ids=(5,))
OTHER = ParaView(item_index=2, paragraph=0, text="직원은 7명이다", chunk_ids=(9,))


class Test청크로_잡기:
    def test_같은_청크를_들면_잡는다(self) -> None:
        got = by_chunk([BACKGROUND, NEED, OTHER])

        assert len(got) == 1
        assert (got[0].a, got[0].b) == ((0, 0), (1, 0))
        assert got[0].found_by == "chunk"

    def test_무엇이_겹쳤는지_적는다(self) -> None:
        assert "[5]" in by_chunk([BACKGROUND, NEED])[0].note

    def test_다른_청크면_안_잡는다(self) -> None:
        assert by_chunk([BACKGROUND, OTHER]) == []

    def test_한_항목_안은_전개다(self) -> None:
        """**한 근거를 여러 문단에서 푸는 것은 중복이 아니다.**"""
        second = ParaView(item_index=0, paragraph=1, text="그래서 설비를 바꿨다", chunk_ids=(5,))

        assert by_chunk([BACKGROUND, second]) == []

    def test_요약_항목은_안_건드린다(self) -> None:
        """**안 거르면 검사가 정상 항목을 때린다**(T-0063)."""
        summary = ParaView(item_index=3, paragraph=0, text="요약", chunk_ids=(5,))

        assert by_chunk([BACKGROUND, summary], summary=frozenset({3})) == []

    def test_LLM_을_안_부른다(self) -> None:
        """코드다. 이것이 이 함수의 요점이다."""
        assert by_chunk([BACKGROUND, NEED])[0].found_by == "chunk"


class Test같은_얘기_다른_근거:
    def test_잡아_온다(self) -> None:
        """**사업자등록증과 회사소개서에 같은 내용이 적혀 있으면 근거가 다르다.**"""
        c = LlmChecker(client=가짜클라이언트(
            {"clashes": [{"a": "0-0", "b": "2-0", "note": "같은 사례를 두 번 쓴다"}]}
        ))
        got = c.check([BACKGROUND, OTHER])

        assert (got[0].a, got[0].b) == ((0, 0), (2, 0))
        assert got[0].found_by == "llm"

    def test_코드가_잡은_쌍은_다시_안_묻는다(self) -> None:
        known = by_chunk([BACKGROUND, NEED])
        c = LlmChecker(client=가짜클라이언트(
            {"clashes": [{"a": "0-0", "b": "1-0", "note": "겹친다"}]}
        ))

        assert c.check([BACKGROUND, NEED], known=known) == []

    def test_모르는_문단_이름은_버리고_센다(self) -> None:
        c = LlmChecker(client=가짜클라이언트({"clashes": [{"a": "0-0", "b": "9-9", "note": "x"}]}))

        assert c.check([BACKGROUND, NEED]) == []
        assert c.dropped == [("clash", "0-0,9-9")]

    def test_같은_항목_안은_버린다(self) -> None:
        second = ParaView(item_index=0, paragraph=1, text="그래서", chunk_ids=(7,))
        c = LlmChecker(client=가짜클라이언트({"clashes": [{"a": "0-0", "b": "0-1", "note": "x"}]}))

        assert c.check([BACKGROUND, second]) == []

    def test_문단이_하나면_안_부른다(self) -> None:
        c = LlmChecker(client=가짜클라이언트({"clashes": []}))

        assert c.check([BACKGROUND]) == []
        assert c.client.calls == []

    def test_요약을_뺀_뒤_하나만_남으면_안_부른다(self) -> None:
        c = LlmChecker(client=가짜클라이언트({"clashes": []}))
        summary = ParaView(item_index=3, paragraph=0, text="요약", chunk_ids=())

        assert c.check([BACKGROUND, summary], summary=frozenset({3})) == []
        assert c.client.calls == []

    def test_요약_항목을_프롬프트에_안_넣는다(self) -> None:
        c = LlmChecker(client=가짜클라이언트({"clashes": []}))
        summary = ParaView(item_index=3, paragraph=0, text="여기가요약", chunk_ids=())
        c.check([BACKGROUND, NEED, summary], summary=frozenset({3}))

        assert "여기가요약" not in c.client.calls[0]["user"]

    def test_스키마가_문단_이름을_막는다(self) -> None:
        from finnect.draft import dedupe

        assert dedupe._schema(["0-0", "1-0"])["properties"]["clashes"]["items"][
            "properties"
        ]["a"]["enum"] == ["0-0", "1-0"]


def test_쌍은_작은_쪽이_a_다() -> None:
    """**안 그러면 같은 쌍이 두 줄로 들어온다.**"""
    c = LlmChecker(client=가짜클라이언트({"clashes": [{"a": "2-0", "b": "0-0", "note": "x"}]}))
    got = c.check([BACKGROUND, OTHER])

    assert got[0].a == (0, 0)
    assert isinstance(got[0], Clash)


def test_최상단에서_httpx_를_안_끌고_온다() -> None:
    import ast
    import pathlib

    from finnect.draft import dedupe

    src = pathlib.Path(dedupe.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names and "finnect.llm" not in names
