"""분량 제한 — 양식이 준 것을 잴 수 있을 때만 잰다 (plan/16 구멍 2).

**쪽 수는 환산하지 않는다.** A4 한 장에 한글 몇 자인지는 서체·여백·줄간격이 정하고
우리에게 근거가 없다. 관례로 1,800자를 쓰지만 관례는 근거가 아니다.

**`내외` 는 초과 판정을 못 한다.** "그 정도" 라서 넘었다고 말할 근거가 없다.
"""

from __future__ import annotations

from finnect.draft import limits


class Test읽기:
    def test_글자_제한(self) -> None:
        got = limits.parse("500자 이내")

        assert (got.kind, got.amount, got.qualifier) == ("chars", 500, "이내")

    def test_쪽_제한을_여러_이름으로_받는다(self) -> None:
        for text in ("50페이지 내외", "1page 이내", "A4 2매 이하", "3장 이내"):
            assert limits.parse(text).kind == "pages", text

    def test_줄_제한(self) -> None:
        assert limits.parse("10줄 이내").kind == "lines"

    def test_문장_안에서_찾는다(self) -> None:
        got = limits.parse("본문은 50페이지 내외로 작성하되 표는 제외")

        assert got.raw == "50페이지 내외"

    def test_없으면_None(self) -> None:
        assert limits.parse(None) is None
        assert limits.parse("분량 제한 없음") is None

    def test_상한인지_가른다(self) -> None:
        assert limits.parse("500자 이내").hard is True
        assert limits.parse("500자 이하").hard is True
        assert limits.parse("500자 내외").hard is False


class Test재기:
    def test_상한을_넘으면_over(self) -> None:
        got = limits.check("가" * 600, "500자 이내")

        assert got.over
        assert got.measured == 600
        assert "100 넘음" in got.note

    def test_상한_안이면_ok(self) -> None:
        got = limits.check("가" * 300, "500자 이내")

        assert got.verdict == "ok"
        assert not got.over

    def test_쪽_수는_못_잰다(self) -> None:
        """**틀린 숫자를 내는 것보다 못 잰다고 말하는 것이 낫다.**"""
        got = limits.check("가" * 100_000, "5페이지 이내")

        assert got.verdict == "unmeasurable"
        assert got.measured is None
        assert "환산율의 근거가 없다" in got.note

    def test_내외는_초과_판정을_안_한다(self) -> None:
        got = limits.check("가" * 900, "500자 내외")

        assert got.verdict == "unmeasurable"
        assert got.measured == 900  # 비율은 낸다
        assert not got.over

    def test_제한이_없으면_none(self) -> None:
        got = limits.check("아무 글", None)

        assert got.verdict == "none"
        assert got.limit is None

    def test_글자는_공백을_뺀다(self) -> None:
        """**줄바꿈을 늘려 제한을 우회할 수 있어서다.** 정확한 값이 아니라 신호다."""
        assert limits.check("가\n나 다\t라", "100자 이내").measured == 4

    def test_줄은_빈_줄을_안_센다(self) -> None:
        assert limits.check("한 줄\n\n\n두 줄", "10줄 이내").measured == 2
