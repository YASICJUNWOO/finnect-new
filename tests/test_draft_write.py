"""집필 — 재료 조립 → LLM 1회 → 코드 검증 (plan/16 T-0066 · F6-12 · F6-13).

**진짜 호출은 여기서 안 한다.** 문장이 좋은지는 사람이 읽어야 하고, 여기서
막는 것은 **규율**이다.

1. 환각을 프롬프트가 아니라 **계층으로** 막는다. `verify()` 가 코드다
2. **문장을 통째로 지우지 않는다.** 지우면 무엇이 문제였는지 화면에서 사라진다
3. **근거 없는 문단은 버린다.** `wiki_evidence` 없는 `wiki_fact` 를 안 만드는 규율과 같다
4. **재료가 없으면 안 부른다.** 부르면 지어내고, 그걸 지우면 `[확인 필요]` 만 남는다
5. 검증이 대조하는 뭉치가 **프롬프트에 넣은 것과 같아야 한다.** 갈리면 맞는 값이 지워진다
"""

from __future__ import annotations

from finnect.draft.write import (
    UNVERIFIED,
    FactMaterial,
    LlmWriter,
    Material,
    verify,
)


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


FACTS = (
    FactMaterial(
        id=11, place="traction", text="2024년 매출은 24,100천원이다",
        quotes=("매출액 24,100천원",), chunk_ids=(5,),
    ),
    FactMaterial(id=12, place="identity", text="(주)다시로는 중고 설비를 되살린다"),
)
MATERIAL = Material(
    number="2-1", title="사업수행 배경 및 목적",
    instruction="배경 및 필요성을 자세하게 기술", limit_text="1page 이내",
    facts=FACTS, notice=(("지원금액", "최대 5,000만원"),),
)


def _write(paragraphs: list[dict], material: Material = MATERIAL):
    w = LlmWriter(client=가짜클라이언트({"paragraphs": paragraphs}))
    return w, w.write(material)


class Test검증:
    def test_재료에_있는_숫자는_남는다(self) -> None:
        got, killed = verify("2024년 매출은 24,100천원입니다.", MATERIAL.corpus())

        assert got == "2024년 매출은 24,100천원입니다."
        assert killed == []

    def test_쉼표와_공백을_무시하고_대조한다(self) -> None:
        """`24,100 천원` 과 `24,100천원` 이 같아야 한다."""
        got, killed = verify("매출 24,100 천원", "매출액 24,100천원")

        assert killed == []
        assert UNVERIFIED not in got

    def test_재료에_없는_금액을_지운다(self) -> None:
        """**F6-12 가 요구한 그것이다.** 지어낸 금액이 본문에 남으면 안 된다."""
        got, killed = verify("매출은 98,700천원입니다.", MATERIAL.corpus())

        assert got == f"매출은 {UNVERIFIED}천원입니다."
        assert killed == ["98,700"]

    def test_문장을_통째로_안_지운다(self) -> None:
        """**지우면 무엇이 문제였는지 화면에서 사라진다.**"""
        got, _ = verify("2024년 매출은 98,700천원까지 올랐습니다.", MATERIAL.corpus())

        assert got.startswith("2024년 매출은")
        assert got.endswith("까지 올랐습니다.")

    def test_재료에_없는_고유명사를_지운다(self) -> None:
        got, killed = verify("(주)없는회사와 협업했습니다.", MATERIAL.corpus())

        # **조사까지 같이 지워진다.** 이름과 조사를 가르려면 조사 목록이 필요한데,
        # 목록을 만들면 빠진 조사에서 다시 틀린다. 문장은 읽히고 자리는 드러난다
        assert got == f"{UNVERIFIED} 협업했습니다."
        assert killed == ["(주)없는회사와"]

    def test_재료에_있는_회사명은_남는다(self) -> None:
        got, killed = verify("(주)다시로는 설비를 되살립니다.", MATERIAL.corpus())

        assert killed == []
        assert "(주)다시로" in got

    def test_조사가_달라도_안_지운다(self) -> None:
        """**맞는 회사 이름이 조사 때문에 지워지면 안 된다.**"""
        got, killed = verify("(주)다시로가 만들었습니다.", MATERIAL.corpus())

        assert killed == []
        assert got == "(주)다시로가 만들었습니다."

    def test_지어낸_로마자를_지운다(self) -> None:
        _, killed = verify("SaaS 형태로 제공합니다.", MATERIAL.corpus())

        assert killed == ["SaaS"]

    def test_공고가_준_값은_재료다(self) -> None:
        """금액·마감일이 여기서 온다. **위키에 없어도 쓸 수 있다.**"""
        got, killed = verify("최대 5,000만원을 신청합니다.", MATERIAL.corpus())

        assert killed == []
        assert UNVERIFIED not in got

    def test_번호_매김을_사실로_안_본다(self) -> None:
        """**한 자리 번호까지 잡으면 목록이 깨진다.**"""
        got, killed = verify("1. 첫째\n2. 둘째", MATERIAL.corpus())

        assert killed == []
        assert got == "1. 첫째\n2. 둘째"

    def test_단위가_붙은_한_자리_수는_사실이다(self) -> None:
        _, killed = verify("직원 7명이 있습니다.", MATERIAL.corpus())

        assert killed == ["7"]

    def test_검증_뭉치가_프롬프트와_같다(self) -> None:
        """**갈리면 모델이 본 것을 검증이 모르고, 맞는 값이 지워진다.**"""
        w, _ = _write([])
        user = w.client.calls[0]["user"]
        corpus = MATERIAL.corpus()

        for piece in ("24,100천원", "매출액 24,100천원", "최대 5,000만원", "1page 이내"):
            assert piece in user
            assert piece in corpus


class Test문단:
    def test_문단마다_쓴_사실을_남긴다(self) -> None:
        """**F6-13 이 이것이다.** 나중에 붙일 수 없다(ADR-0014)."""
        _, got = _write([{"text": "2024년 매출은 24,100천원이다.", "facts": [11]}])

        assert got[0].fact_ids == (11,)

    def test_근거를_안_적은_문단은_버린다(self) -> None:
        w, got = _write([{"text": "저희는 열심히 하겠습니다.", "facts": []}])

        assert got == []
        assert ("사업수행 배경 및 목적", "근거 없는 문단") in w.dropped

    def test_준_적_없는_사실_번호는_버린다(self) -> None:
        _, got = _write([{"text": "2024년 매출은 24,100천원이다.", "facts": [11, 99]}])

        assert got[0].fact_ids == (11,)

    def test_빈_문단은_안_남긴다(self) -> None:
        _, got = _write([{"text": "   ", "facts": [11]}])

        assert got == []

    def test_지운_것을_센다(self) -> None:
        """**조용히 안 넘긴다.**"""
        w, _ = _write([{"text": "매출 98,700천원", "facts": [11]}])

        assert ("사업수행 배경 및 목적", "98,700") in w.unverified
        assert w.dropped == []  # **문단을 버린 것과 따로 센다**


class Test안_부를_때:
    def test_재료가_없으면_안_부른다(self) -> None:
        """**지어낸 것을 지우면 `[확인 필요]` 만 남는다. 안 쓰는 것이 낫다.**"""
        empty = Material(number="9", title="빈 항목", instruction=None,
                         limit_text=None, facts=())
        w = LlmWriter(client=가짜클라이언트({"paragraphs": []}))

        assert w.write(empty) == []
        assert w.client.calls == []

    def test_항목_하나에_호출_하나다(self) -> None:
        w, _ = _write([{"text": "2024년 매출은 24,100천원이다.", "facts": [11]}])

        assert len(w.client.calls) == 1


class Test프롬프트:
    def test_사용자_답변임을_표시한다(self) -> None:
        """`user_stated` 는 근거 청크가 없어도 재료다(ADR-0028 5번)."""
        m = Material(
            number="1", title="팀", instruction=None, limit_text=None,
            facts=(FactMaterial(id=1, place="team", text="직원은 7명이다",
                                source_type="user_stated"),),
        )
        w = LlmWriter(client=가짜클라이언트({"paragraphs": []}))
        w.write(m)

        assert "사용자가 직접 말한 것" in w.client.calls[0]["user"]

    def test_지시문을_그대로_넣는다(self) -> None:
        w, _ = _write([])

        assert "배경 및 필요성을 자세하게 기술" in w.client.calls[0]["user"]

    def test_스키마가_사실_번호를_막는다(self) -> None:
        from finnect.draft import write

        schema = write._schema([11, 12])
        facts = schema["properties"]["paragraphs"]["items"]["properties"]["facts"]

        assert facts["items"]["enum"] == [11, 12]


def test_최상단에서_httpx_를_안_끌고_온다() -> None:
    import ast
    import pathlib

    from finnect.draft import write

    src = pathlib.Path(write.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names and "finnect.llm" not in names
