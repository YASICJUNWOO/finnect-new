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
        """**될 것과 되는 것을 가른다.** 목록에 미리 넣으면 화면이 「된다」고 말한다.

        **2026-08-23 셋이 다 찼다.** `PLANNED` 를 비우고 지우지는 않는다 —
        xlsx 가 거기 올 자리다.
        """
        from finnect.forms import PLANNED

        assert {"hwp", "hwpx", "docx"} == SUPPORTED
        assert not (SUPPORTED & PLANNED)

    def test_덮어쓸_수_있는_것이_갈려_있다(self) -> None:
        """**hwp 만 못 덮어쓴다**(ADR-0060 결정 3). 안내문이 든 칸은 덮어써야
        채워지므로 이 집합이 「어느 칸까지 채울 수 있나」를 정한다."""
        from finnect.forms import OVERWRITABLE

        assert "hwp" not in OVERWRITABLE
        assert {"hwpx", "docx"} <= OVERWRITABLE
        assert OVERWRITABLE <= SUPPORTED

    def test_예정된_포맷은_이유를_말한다(self) -> None:
        """영영 안 되는 것과 아직 안 된 것을 같은 말로 거절하지 않는다.

        **지금 `PLANNED` 가 비어 있어서 가짜 값으로 잰다.** 규칙이 사는지를 보는
        것이라 목록이 비었다고 테스트를 지우지 않는다 — xlsx 가 붙는 날 다시
        걸린다.
        """
        import finnect.forms as forms

        # **`forms.open_form` 으로 부른다.** 위의 임포트 경계 테스트가
        # `sys.modules` 에서 이 모듈을 빼기 때문에, 파일 맨 위에서 가져온
        # `open_form` 은 **옛 모듈 객체의 것**이라 여기서 바꾼 전역을 안 본다.
        planned = forms.PLANNED
        try:
            forms.PLANNED = frozenset({"xlsx"})
            with pytest.raises(forms.UnsupportedFormat, match="아직"):
                forms.open_form("/없는/파일", "xlsx")
        finally:
            forms.PLANNED = planned


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


class Test문단_좌표:
    """**서술 항목의 글 자리는 표가 아니다** (ADR-0061 결정 3의 뒷자리).

    실측(`bizinfo:PBLN_…125577` 활동계획서)에서 이렇게 생겼다.

        16   1. 목적 및 필요성        ← 제목
        17   - …에 대하여 작성         ← 지시문
        18   (빈 문단)               ← 글이 들어간다
        25   2. 수주 활동 대상         ← 다음 항목

    `Anchor` 로는 이 자리를 못 가리켜서 **서술 항목 1,158개가 전부 좌표 없이**
    남아 있었고, 채우기가 통째로 건너뛰어 화면은 「썼어요」인데 파일에는 없었다.
    """

    def test_셀_좌표와_한_문자열에서_갈린다(self) -> None:
        """**옛 값이 그대로 셀로 읽힌다.** 이미 심긴 좌표 956개를 안 건드리려고
        `p:` 접두사로 가른다 — 마이그레이션을 만들지 않는다."""
        from finnect.forms import Anchor, ParaAnchor, parse_anchor

        assert str(ParaAnchor(0, 18)) == "p:0:18"
        assert parse_anchor("p:0:18") == ParaAnchor(0, 18)
        assert parse_anchor("0:3:1:2") == Anchor(0, 3, 1, 2)

    def test_제목_다음의_첫_빈_문단을_고른다(self) -> None:
        from finnect.forms import Para, ParaAnchor, outline_targets

        paras = [
            Para(ParaAnchor(0, 0), "1. 목적 및 필요성"),
            Para(ParaAnchor(0, 1), "- 참가 목적을 작성"),  # 지시문은 비어 있지 않다
            Para(ParaAnchor(0, 2), ""),
            Para(ParaAnchor(0, 3), ""),
            Para(ParaAnchor(0, 4), "2. 수주 활동 대상"),
            Para(ParaAnchor(0, 5), ""),
        ]
        got = dict(outline_targets(paras, ["목적 및 필요성", "수주 활동 대상"]))
        assert got["목적 및 필요성"] == ParaAnchor(0, 2)
        assert got["수주 활동 대상"] == ParaAnchor(0, 5)

    def test_다음_제목을_넘어가지_않는다(self) -> None:
        """넘어가면 항목 둘이 같은 문단을 가리키고, 나중 항목의 글이 앞 항목
        자리에 앉는다."""
        from finnect.forms import Para, ParaAnchor, outline_targets

        paras = [
            Para(ParaAnchor(0, 0), "1. 목적"),
            Para(ParaAnchor(0, 1), "2. 대상"),  # 빈 문단 없이 다음 제목이 온다
            Para(ParaAnchor(0, 2), ""),
        ]
        got = dict(outline_targets(paras, ["목적", "대상"]))
        assert "목적" not in got
        assert got["대상"] == ParaAnchor(0, 2)

    def test_제목이_겹치면_버린다(self) -> None:
        """표 라벨과 같은 판단이다. 하나를 고르면 그 선택이 조용히 일어나고
        **틀려도 파일은 정상으로 열린다.**"""
        from finnect.forms import Para, ParaAnchor, outline_targets

        paras = [
            Para(ParaAnchor(0, 0), "1. 개요"),
            Para(ParaAnchor(0, 1), ""),
            Para(ParaAnchor(0, 2), "2. 개요"),
            Para(ParaAnchor(0, 3), ""),
        ]
        assert outline_targets(paras, ["개요"]) == []

    def test_번호가_붙은_제목에_걸린다(self) -> None:
        """항목 제목은 `outline` 이 번호를 뗀 값이고 문단은 번호를 달고 있다."""
        from finnect.forms import Para, ParaAnchor, outline_targets

        for head in ("1. 활동 계획", "가. 활동 계획", "(3) 활동 계획", "2-1. 활동 계획"):
            paras = [Para(ParaAnchor(0, 0), head), Para(ParaAnchor(0, 1), "")]
            assert dict(outline_targets(paras, ["활동 계획"])) == {
                "활동 계획": ParaAnchor(0, 1)
            }, head

    def test_긴_문장_끝에_우연히_걸리지_않는다(self) -> None:
        """`기타` 같은 두 글자가 본문 한복판에서 끝나는 일이 실제로 있다."""
        from finnect.forms import Para, ParaAnchor, outline_targets

        paras = [
            Para(ParaAnchor(0, 0), "제출 서류는 아래와 같으며 자세한 내용은 기타"),
            Para(ParaAnchor(0, 1), ""),
        ]
        assert outline_targets(paras, ["기타"]) == []

    def test_자리가_없으면_안_준다(self) -> None:
        """제목 바로 밑에 표가 오는 양식이 있다. 아무 문단이나 고르면 글이
        엉뚱한 데에 앉고 **파일은 정상으로 열린다.**"""
        from finnect.forms import Para, ParaAnchor, outline_targets

        paras = [Para(ParaAnchor(0, 0), "1. 목적")]
        assert outline_targets(paras, ["목적", "없는 항목"]) == []


def _row(texts: list[str], row: int = 0) -> list:
    """한 행을 만든다. 열 번호가 순서대로 붙는다."""
    from finnect.forms.base import Cell

    return [Cell(Anchor(0, 0, row, i), t) for i, t in enumerate(texts)]


class Test라벨_짝:
    """**바로 오른쪽 칸만 값 자리다.**

    예전에는 「오른쪽 첫 빈 칸」이었고 그 규칙이 칸을 건너뛰었다. 실측
    (`bizinfo:PBLN_…125460` 신청서)의 한 행이 이렇게 생겼다.

        사업자등록번호 | 000-00-00000 | 법인등록번호 | (빈칸)

    `000-00-00000` 은 안내문이라 빈 칸이 아니고, 규칙이 그것을 지나쳐 **법인등록번호의
    빈 칸**을 사업자등록번호의 값 자리로 골랐다. 채운 파일에서 사업자등록번호
    `501-86-33271` 이 법인등록번호 칸에 앉았고, **파일은 정상으로 열려서** 제출
    직전에야 드러난다. 라벨이 겹칠 때 아예 버리는 것과 같은 판단으로 좁힌다.

    **재현율을 정확성과 바꾼 것이다.** 건너뛰어야 닿는 칸을 이제 못 채우는데, 그 자리는
    안내문이 값 자리를 막고 있는 경우라 [plan/24](../docs/plan/24-양식을-채워서-돌려준다.md)
    T-0153 이 그 칸을 값 자리로 인정하면서 되찾는다. **모르는 자리를 찍어서 채우지 않는다.**
    """

    def test_바로_오른쪽_빈_칸을_고른다(self) -> None:
        from finnect.forms import label_targets

        cells = _row(["기업명", ""])
        assert label_targets(cells) == [("기업명", Anchor(0, 0, 0, 1))]

    def test_한_칸도_건너뛰지_않는다(self) -> None:
        """실측에서 틀린 값이 들어간 바로 그 행이다."""
        from finnect.forms import label_targets

        cells = _row(["사업자등록번호", "000-00-00000", "법인등록번호", ""])
        got = dict(label_targets(cells))
        assert "사업자등록번호" not in got
        assert got["법인등록번호"] == Anchor(0, 0, 0, 3)

    def test_병합된_라벨을_접는다(self) -> None:
        """**`python-docx` 가 가로로 병합된 칸을 걸친 수만큼 반복해서 준다.**
        접지 않으면 라벨이 자기 복제를 오른쪽 칸으로 보고 짝을 통째로 잃는다 —
        실측에서 `대표자명` 이 네 번 나왔다."""
        from finnect.forms import label_targets

        cells = _row(["대표자명", "대표자명", "대표자명", ""])
        assert label_targets(cells) == [("대표자명", Anchor(0, 0, 0, 3))]

    def test_병합된_값_칸은_첫_자리를_준다(self) -> None:
        """값 칸도 같은 수만큼 반복돼 온다. 뒤엣것을 고르면 같은 칸을 가리키는
        좌표가 둘이 되어 부르는 쪽이 겹침으로 오판한다."""
        from finnect.forms import label_targets

        cells = _row(["연락처", "", "", ""])
        assert label_targets(cells) == [("연락처", Anchor(0, 0, 0, 1))]

    def test_라벨이_겹쳐도_여기서_안_버린다(self) -> None:
        """**겹치는 것을 아는 것은 부르는 쪽이다.** 여기서 하나를 고르면 그 선택이
        조용히 일어난다(`spike/anchor_check.py` 가 부러뜨린 방식)."""
        from finnect.forms import label_targets

        cells = _row(["기업명", ""], row=0) + _row(["기업명", ""], row=1)
        assert label_targets(cells) == [
            ("기업명", Anchor(0, 0, 0, 1)),
            ("기업명", Anchor(0, 0, 1, 1)),
        ]

    def test_행을_넘어가지_않는다(self) -> None:
        """표가 세로로 짜인 양식에서 아래 칸을 잡으면 엉뚱한 자리에 값이 앉는다."""
        from finnect.forms import label_targets

        cells = _row(["기업명"], row=0) + _row([""], row=1)
        assert label_targets(cells) == []

    def test_빈_칸은_라벨이_아니다(self) -> None:
        from finnect.forms import label_targets

        cells = _row(["", ""])
        assert label_targets(cells) == []
