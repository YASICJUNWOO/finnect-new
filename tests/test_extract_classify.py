"""양식 구간 판별 — 키 없이 검증할 수 있는 것만 (plan/11 T-0036 · ADR-0037).

**진짜 호출은 여기서 안 한다.** 키가 있어야 하고 돈이 들고 답이 매번 다르다.
정확도는 `--classify N --dry` 로 손 분류와 대조해서 잰다.

여기서 막는 것은 **배관과 규율**이다.

1. 스키마 밖 답이 오면 `unknown` 으로 되돌리고 **센다.** 조용히 넘기면 아무 말이나
   `kind` 에 들어간다
2. `unknown` 은 답이 아니다. 모른다고 온 것을 `none` 으로 밀지 않는다 — 밀면
   다시 볼 대상이 사라진다
3. 긴 구간을 자르되 **잘랐다고 말한다.** 말하지 않으면 모델이 끊긴 것을 끝난 것으로 읽는다
4. 키가 없으면 **멈춘다.** 조용히 규칙으로 물러나지 않는다(결정 4)
5. `classify` 모듈이 최상단에서 `httpx` 를 안 끌고 온다 — 끌고 오면 배포본이 죽는다
"""

from __future__ import annotations

import pytest

from finnect.config import settings
from finnect.extract import classify as cl
from finnect.models import DocumentKind


class 가짜클라이언트:
    """준 대로 돌려준다. **네트워크를 안 쓴다.**"""

    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


def _llm(kind: str = "narrative", reason: str = "항목마다 기술 지시가 붙는다"):
    c = 가짜클라이언트({"kind": kind, "reason": reason})
    return cl.LlmClassifier(client=c), c


VIEW = cl.SegmentView(
    title="[붙임2] 사업계획서",
    text="2-1. 사업수행 배경 및 목적\n… 자세하게 기술",
)


class Test판정:
    def test_셋_중_하나로_답한다(self) -> None:
        for raw in ("narrative", "fields", "none"):
            clf, _ = _llm(raw)

            assert clf.classify(VIEW).kind is DocumentKind(raw)

    def test_이유를_들고_온다(self) -> None:
        """손 분류와 대조할 때 눈으로 읽는 것이다."""
        clf, _ = _llm("narrative", "  ※ 작성 요령이 붙어 있다  ")

        assert clf.classify(VIEW).reason == "※ 작성 요령이 붙어 있다"

    def test_모르는_답은_되돌리고_센다(self) -> None:
        """**조용히 넘기지 않는다.** 넘기면 아무 말이나 `kind` 에 들어간다."""
        clf, _ = _llm("사업계획서")

        v = clf.classify(VIEW)

        assert v.kind is DocumentKind.UNKNOWN
        assert clf.dropped == [("[붙임2] 사업계획서", "사업계획서")]

    def test_모른다고_답하면_받아_준다(self) -> None:
        """**실측 40건 중 여섯이 표지 한 줄뿐이었다.** 셋 중 하나를 강제하면
        모델이 `reason` 에 "제목만 있다" 고 적으면서 답을 낸다."""
        clf, _ = _llm("unclear", "제목만 제시되어 있다")

        v = clf.classify(VIEW)

        assert v.kind is DocumentKind.UNKNOWN
        assert clf.declined == [("[붙임2] 사업계획서", "제목만 제시되어 있다")]
        assert clf.dropped == []  # **버린 것과 따로 센다** — 실패가 아니다

    def test_너무_짧은_구간은_안_묻는다(self) -> None:
        """문턱은 실측이다 — 표지뿐인 구간이 17~53자, 진짜 내용의 최소가 102자였다."""
        assert cl.MIN_BODY_CHARS == 80

    def test_unknown_은_답이_아니다(self) -> None:
        """모른다고 온 것을 `none` 으로 밀면 **다시 볼 대상이 사라진다.**"""
        clf, _ = _llm("unknown")

        assert clf.classify(VIEW).kind is DocumentKind.UNKNOWN
        assert len(clf.dropped) == 1

    def test_판정자를_이름으로_남긴다(self) -> None:
        """`document.decided_by` 에 그대로 들어간다."""
        clf, _ = _llm()

        assert clf.name == "llm/gpt-5.6-luna"


class Test잘라_보내기:
    def test_짧으면_그대로_보낸다(self) -> None:
        v = cl.SegmentView(title="t", text="짧은 구간")

        assert v.prompt_body() == "짧은 구간"

    def test_길면_앞뒤만_보낸다(self) -> None:
        text = "앞" * cl.HEAD_CHARS + "가운데" * 500 + "뒤" * cl.TAIL_CHARS
        body = cl.SegmentView(title="t", text=text).prompt_body()

        assert body.startswith("앞" * 100)
        assert body.endswith("뒤" * 100)
        assert "가운데가운데" not in body

    def test_잘랐다고_말한다(self) -> None:
        """**말하지 않으면 모델이 끊긴 것을 끝난 것으로 읽는다.**"""
        text = "가" * (cl.HEAD_CHARS + cl.TAIL_CHARS + 1_234)

        assert "1,234자 생략" in cl.SegmentView(title="t", text=text).prompt_body()

    def test_원문_전체를_프롬프트에_안_넣는다(self) -> None:
        clf, c = _llm()
        clf.classify(cl.SegmentView(title="t", text="가" * 50_000))

        assert len(c.calls[0]["user"]) < 6_000


class Test규칙_판정기:
    def test_칸_채우기는_규칙이_가른다(self) -> None:
        text = (
            "기업명\t(주)가나다\t대표자\t홍길동\n사업자등록번호\t000-00-00000\n"
            "업종\t제조업\n연락처\t\n매출액\t백만원\n"
            "위와 같이 신청합니다.\n2026년 월 일\n신청인 (인)\nOO시장 귀하"
        )

        assert cl.RuleClassifier().classify(cl.SegmentView("[서식1] 신청서", text)).kind is (
            DocumentKind.FIELDS
        )

    def test_서술형은_모른다고_답한다(self) -> None:
        """**규칙이 네 번 실패한 자리다.** 다섯 번째를 만들지 않는다."""
        text = "1. 추진배경\n2. 주요내용\n3. 기대효과"

        assert cl.RuleClassifier().classify(cl.SegmentView("[붙임2] 계획서", text)).kind is (
            DocumentKind.UNKNOWN
        )


class Test판정기_고르기:
    def test_설정이_고른다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "document_classifier", "rule")
        assert isinstance(cl.get_classifier(), cl.RuleClassifier)

        monkeypatch.setattr(settings, "document_classifier", "llm")
        assert isinstance(cl.get_classifier(), cl.LlmClassifier)

    def test_모르는_이름은_멈춘다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "document_classifier", "gpt")

        with pytest.raises(NotImplementedError, match="gpt"):
            cl.get_classifier()

    def test_키가_없으면_멈춘다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**조용히 규칙으로 물러나지 않는다**(ADR-0037 결정 4).

        물러나면 규칙이 이미 실패한 것을 다시 실패시키고, 그 실패가
        "LLM 도 못 가른다" 처럼 보인다.
        """
        from finnect import llm

        monkeypatch.setattr(settings, "openai_api_key", "")

        with pytest.raises(llm.MissingKey, match="OPENAI_API_KEY"):
            cl.LlmClassifier().classify(VIEW)


def test_최상단에서_httpx_를_안_끌고_온다() -> None:
    """**로컬은 통과하고 배포본만 죽는** 그 함정이다(CLAUDE.md)."""
    import ast
    import pathlib

    src = pathlib.Path(cl.__file__).read_text()
    top = [
        n
        for n in ast.parse(src).body
        if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names
    assert "finnect.llm" not in names
