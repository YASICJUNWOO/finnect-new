"""양식 채우기의 경계 (plan/24 T-0151 · ADR-0060).

**여기서 실제 파일을 안 연다.** hwp 를 열려면 JVM 이 필요하고, 그것을 테스트가
요구하면 `uv run pytest` 가 Java 없는 곳에서 통째로 죽는다 — 되는 범위는
`spike/` 가 실측으로 재고 여기는 **경계와 좌표 규칙**을 잠근다.
"""

from __future__ import annotations

import pytest

from finnect.forms import SUPPORTED, Anchor, UnsupportedFormat, open_form


class Test임포트_경계:
    """**`import finnect.forms` 가 JVM 을 안 끌고 온다.**

    최상단에 어댑터를 두면 이 임포트가 jpype 를 부르고, 그러면 Java 가 없는
    배포본에서 **읽기 경로가 통째로 죽는다.** `api/app.py` 가 `wiki.service` 를
    함수 안에서 부르는 것과 같은 함정이고, 그 함정은 실제로 두 번 밟혔다
    (`attach.service` · `ingest.service`).
    """

    def test_jpype_를_안_끌고_온다(self) -> None:
        import sys

        for mod in ("finnect.forms", "finnect.forms.base"):
            sys.modules.pop(mod, None)
        sys.modules.pop("jpype", None)

        import finnect.forms  # noqa: F401

        assert "jpype" not in sys.modules

    def test_어댑터도_안_끌고_온다(self) -> None:
        """포맷별 모듈이 임포트 시점에 안 붙는다. **셋 다 무거운 것을 든다.**"""
        import sys

        sys.modules.pop("finnect.forms", None)
        import finnect.forms  # noqa: F401

        assert "finnect.forms.hwp" not in sys.modules
        assert "finnect.forms.docx" not in sys.modules


class Test포맷_경계:
    def test_못_채우는_포맷은_거절한다(self) -> None:
        """**코퍼스의 8% 다**(pdf 7 · zip 6 · xlsx/xls 3). 조용히 빈 파일을
        만들지 않는다."""
        for ext in ("pdf", "zip", "xlsx", "hwpx2", ""):
            with pytest.raises(UnsupportedFormat):
                open_form("/없는/파일", ext)

    def test_어댑터가_있는_것만_된다고_말한다(self) -> None:
        """**될 것과 되는 것을 가른다.** ADR-0060 이 셋 다 된다고 쟀지만 어댑터는
        hwp 뿐이다 — 목록에 미리 넣으면 화면이 「된다」고 말한다."""
        from finnect.forms import PLANNED

        assert {"hwp"} == SUPPORTED
        assert {"hwpx", "docx"} == PLANNED
        assert not (SUPPORTED & PLANNED)

    def test_예정된_포맷은_이유를_말한다(self) -> None:
        """`pdf` 와 `hwpx` 를 같은 말로 거절하지 않는다 — 앞은 영영 안 되고
        뒤는 아직 안 된 것이다."""
        with pytest.raises(UnsupportedFormat, match="아직"):
            open_form("/없는/파일", "hwpx")


class Test앵커:
    """**좌표가 라벨을 대신한다.** 실측에서 우리가 채운 17칸 중 둘이 겹치는
    라벨이었다(`기업명` 3회 · `합계` 3회 · `spike/anchor_check.py`)."""

    def test_문자열로_오간다(self) -> None:
        a = Anchor(0, 3, 1, 2)
        assert str(a) == "0:3:1:2"
        assert Anchor.parse("0:3:1:2") == a

    def test_구역이_좌표에_든다(self) -> None:
        """**표 번호가 구역 안에서만 이어진다.** 구역을 건너 세면 구역이 둘인
        문서에서 좌표가 밀린다."""
        assert Anchor(0, 1, 0, 0) != Anchor(1, 1, 0, 0)

    def test_망가진_문자열은_거절한다(self) -> None:
        for bad in ("0:3:1", "a:b:c:d", "", "0:3:1:2:4"):
            with pytest.raises(ValueError):
                Anchor.parse(bad)


class Test빈칸:
    """**글자가 없는 것만 빈 칸이다.**

    관공서 양식이 빈칸에 형식을 적어 두지만(`000-0000-0000`) 그것을 규칙으로 가르면
    안내문이 붙었을 때 안 갈린다 — 실측에서 양식 하나가 표 115개에서 한 칸도 안
    걸렸다(ADR-0060 결정 6). 그 판정은 T-0153 이 LLM 으로 한다.
    """

    def test_공백만_있으면_빈_칸이다(self) -> None:
        from finnect.forms.base import Cell

        a = Anchor(0, 0, 0, 0)
        assert Cell(a, "").blank
        assert Cell(a, "   ").blank
        assert not Cell(a, "주식회사 다시로").blank

    def test_플레이스홀더는_빈_칸이_아니다(self) -> None:
        """**여기서 가르지 않는다.** 가르는 척하면 안내문이 붙은 칸에서 조용히
        틀린다 — 그 판정은 원문을 읽어야 한다."""
        from finnect.forms.base import Cell

        assert not Cell(Anchor(0, 0, 0, 0), "000-0000-0000").blank
