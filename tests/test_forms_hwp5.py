"""hwp 를 바이트로 읽는다 ([ADR-0070](../docs/adr/0070-hwp-를-바이트로-읽고-쓴다.md)).

**JVM 이 없어야 도는 테스트다.** 레코드를 손으로 만들어 넣으므로 파일도 필요 없다 —
`tests/test_attach_extract.py` 가 `_assemble` 을 같은 방식으로 시험하는 자리와 짝이다.
"""

from __future__ import annotations

import struct

from finnect.forms.hwp5 import HWPTAG_PARA_HEADER, emit, parse_addr, parse_section

CTRL_HEADER, PARA_TEXT, LIST_HEADER, TABLE = 71, 67, 72, 77
#: 뒤집혀 들어온다. 사람이 읽는 이름은 `tbl ` 이다
TBL = b" lbt"


def _rec(tag: int, level: int, payload: bytes = b"") -> bytes:
    return emit(tag, level, payload)


def _text(s: str) -> bytes:
    """문단 글. **끝에 U+000D 가 붙는다** — 실측에서 원본 146/146 이 그랬다."""
    return (s + "\r").encode("utf-16-le")


def _lh(col: int, row: int, cs: int = 1, rs: int = 1, w: int = 5000, h: int = 2000) -> bytes:
    """LIST_HEADER — nParas(4) + listAttr(4) 다음이 주소다."""
    return b"\x00" * 8 + struct.pack("<HHHH", col, row, cs, rs) + struct.pack("<ii", w, h)


def _cell(col: int, row: int, text: str, *, cs: int = 1, rs: int = 1,
          w: int = 5000, h: int = 2000, level: int = 2) -> bytes:
    """칸 하나 — LIST_HEADER + 문단. **칸 안 문단이 LIST_HEADER 와 같은 레벨이다.**"""
    out = _rec(LIST_HEADER, level, _lh(col, row, cs, rs, w, h)) + _rec(HWPTAG_PARA_HEADER, level)
    if text:
        out += _rec(PARA_TEXT, level + 1, _text(text))
    return out


class Test주소_해독:
    """`LIST_HEADER` 가 격자 좌표를 들고 있다.

    옛 어댑터는 이것을 안 읽고 **그 행의 셀 리스트 인덱스**를 열로 썼다 — 가로 병합이
    앞에 있으면 어긋난다(실측 36.4%).
    """

    def test_주소와_병합과_크기를_읽는다(self) -> None:
        assert parse_addr(_lh(3, 1, 2, 4, 16390, 1990)) == (3, 1, 2, 4, 16390, 1990)

    def test_짧으면_칸이_아니다(self) -> None:
        """글상자 LIST_HEADER 는 이 자리가 주소가 아니다."""
        assert parse_addr(b"\x00" * 16) is None

    def test_병합이_0이면_칸이_아니다(self) -> None:
        """표 칸이면 span 이 반드시 1 이상이다. 그것이 유일한 판별 재료다."""
        assert parse_addr(_lh(0, 0, cs=0)) is None
        assert parse_addr(_lh(0, 0, rs=0)) is None


class Test격자_좌표:
    """**열이 격자 열이다.** 셀 리스트 안 순번이 아니다."""

    def test_병합이_앞에_있어도_열이_안_밀린다(self) -> None:
        """HWP 는 가로 병합된 칸을 한 번만 저장한다. 리스트 인덱스로 세면 3칸 병합
        뒤의 칸이 열 1 이 되지만 실제 격자 열은 3 이다."""
        data = (
            _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _cell(0, 0, "기업명", cs=3)
            + _cell(3, 0, "(주)가나다")
        )
        boxes, _ = parse_section(data, 0)

        assert [(b.col, b.colspan, b.text) for b in boxes] == [
            (0, 3, "기업명"),
            (3, 1, "(주)가나다"),
        ]

    def test_칸_크기를_같이_준다(self) -> None:
        """얇은 장식 칸을 거르는 재료다 — 실측에서 5.4pt 짜리가 값을 삼켰다."""
        data = (
            _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _cell(0, 0, "", w=48970, h=540)
        )
        boxes, _ = parse_section(data, 0)

        assert (boxes[0].width, boxes[0].height) == (48970, 540)


class Test표_세기:
    """표 번호가 **레코드 순서**다. 두 경로가 어긋나면 폴백이 다른 칸에 쓴다."""

    def test_중첩_표를_센다(self) -> None:
        """실측에서 표 258개 중 57개(22%)가 중첩 표다. 옛 어댑터는 최상위 문단의
        컨트롤만 봐서 그것들을 **한 번도 못 봤다.**"""
        data = (
            _rec(HWPTAG_PARA_HEADER, 0)
            + _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _rec(LIST_HEADER, 2, _lh(0, 0))
            + _rec(HWPTAG_PARA_HEADER, 2)
            + _rec(CTRL_HEADER, 3, TBL)           # 칸 안에 표가 또 있다
            + _rec(TABLE, 4, b"\x00" * 8)
            + _cell(0, 0, "안쪽", level=4)
            + _rec(HWPTAG_PARA_HEADER, 0)          # level 이 내려오면 둘 다 닫힌다
            + _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _cell(0, 0, "다음 표")
        )
        boxes, _ = parse_section(data, 0)

        assert [(b.table, b.text) for b in boxes] == [(1, "안쪽"), (0, ""), (2, "다음 표")]

    def test_구역이_좌표에_든다(self) -> None:
        """표 번호가 구역 안에서만 이어진다 — 구역을 건너 세면 좌표가 밀린다."""
        data = _rec(CTRL_HEADER, 1, TBL) + _rec(TABLE, 2, b"\x00" * 8) + _cell(0, 0, "가")
        boxes, _ = parse_section(data, 3)

        assert boxes[0].section == 3


class Test표_밖:
    """표 밖 문단과 표 밖 `LIST_HEADER`."""

    def test_최상위_문단만_센다(self) -> None:
        """번호가 hwplib 의 `getParagraph(i)` 와 같아야 한다 — 칸 안 문단을 같이 세면
        이미 심긴 문단 좌표가 통째로 밀린다."""
        data = (
            _rec(HWPTAG_PARA_HEADER, 0)
            + _rec(PARA_TEXT, 1, _text("1. 목적 및 필요성"))
            + _rec(HWPTAG_PARA_HEADER, 0)
            + _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _cell(0, 0, "칸 안 글")
            + _rec(HWPTAG_PARA_HEADER, 0)
            + _rec(PARA_TEXT, 1, _text("2. 수주 활동 대상"))
        )
        _, blocks = parse_section(data, 0)

        assert [(p.index, p.text) for p in blocks] == [
            (0, "1. 목적 및 필요성"),
            (1, ""),
            (2, "2. 수주 활동 대상"),
        ]

    def test_표_밖_list_header는_칸이_아니다(self) -> None:
        """글상자에도 쓰인다. 표가 열린 채로 나오면 칸으로 새어 들어온다 —
        레벨이 그 표의 바로 아래일 때만 칸이다."""
        data = (
            _rec(CTRL_HEADER, 1, TBL)
            + _rec(TABLE, 2, b"\x00" * 8)
            + _cell(0, 0, "진짜 칸")
            + _rec(LIST_HEADER, 3, _lh(9, 9))     # 한 단 깊다 — 글상자다
            + _rec(HWPTAG_PARA_HEADER, 3)
            + _rec(PARA_TEXT, 4, _text("글상자 안"))
        )
        boxes, _ = parse_section(data, 0)

        assert [b.text for b in boxes] == ["진짜 칸"]


class Test레코드_왕복:
    """`emit` 이 `iter_records` 의 역이다. 쓰기가 이걸 딛고 선다."""

    def test_큰_레코드도_되읽힌다(self) -> None:
        """0xFFF 이상이면 크기가 뒤에 4바이트로 붙는다."""
        from finnect.attach.hwp import iter_records

        big = b"\xab" * 5000
        got = list(iter_records(emit(PARA_TEXT, 2, big)))

        assert got == [(PARA_TEXT, 2, big)]


def _shape(align: int, *, border: int = 2, extra: int = 0) -> bytes:
    """PARA_SHAPE — attr1(4) + 여백·간격(24) + 탭·번호(4) + 테두리(2) + 나머지."""
    attr1 = (align << 2) | extra
    return (
        struct.pack("<I", attr1)
        + struct.pack("<6i", 0, 0, 0, 0, 0, 160)
        + struct.pack("<HH", 0, 0)
        + struct.pack("<H", border)
        + b"\x00" * 22
    )


def _docinfo(*shapes: bytes) -> bytes:
    from finnect.forms.hwp5 import HWPTAG_PARA_SHAPE

    return b"".join(_rec(HWPTAG_PARA_SHAPE, 0, p) for p in shapes)


def _header(nchars: int, *, flag: bool = False, shape: int = 0) -> bytes:
    """PARA_HEADER — nChars(4) + ctrlMask(4) + paraShapeID(2) + 나머지."""
    n = nchars | (0x80000000 if flag else 0)
    return struct.pack("<I", n) + b"\x00" * 4 + struct.pack("<H", shape) + b"\x00" * 12


class Test레코드_규칙:
    """실측으로 확정한 것 넷. **PoC 가 셋을 틀리게 쓰고 있었다.**"""

    def test_빈_칸에_레코드를_만든다(self) -> None:
        """빈 문단은 `PARA_TEXT` 가 **아예 없다**(실측 13,104건 전부). 채우는 것은
        고쳐 쓰는 것이 아니라 없던 레코드를 만드는 일이다."""
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import edit

        recs = [(HWPTAG_PARA_HEADER, 2, _header(1))]
        data, done, refused = edit(recs, {0: "주식회사 가나다"})
        got = list(iter_records(data))

        assert (done, refused) == ({0}, set())
        assert [t for t, _lv, _p in got] == [HWPTAG_PARA_HEADER, PARA_TEXT]
        assert got[1][2] == "주식회사 가나다\r".encode("utf-16-le")

    def test_nchars가_글자수_더하기_하나다(self) -> None:
        """문단 끝 문자를 같이 센다. 원본 문단이 전부 그 규칙이었다."""
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import edit

        data, _d, _r = edit([(HWPTAG_PARA_HEADER, 2, _header(1))], {0: "가나다"})
        hdr = next(p for t, _lv, p in iter_records(data) if t == HWPTAG_PARA_HEADER)

        assert struct.unpack_from("<I", hdr, 0)[0] == 4

    def test_플래그_비트를_보존한다(self) -> None:
        """`nChars` 최상위 비트는 개수가 아니다. 지우면 규격을 벗어난다."""
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import NCHARS_FLAG, edit

        data, _d, _r = edit([(HWPTAG_PARA_HEADER, 2, _header(1, flag=True))], {0: "가"})
        hdr = next(p for t, _lv, p in iter_records(data) if t == HWPTAG_PARA_HEADER)
        (n,) = struct.unpack_from("<I", hdr, 0)

        assert n & NCHARS_FLAG
        assert n & ~NCHARS_FLAG == 2

    def test_갈아_끼우면_레코드가_안_는다(self) -> None:
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import edit

        recs = [
            (HWPTAG_PARA_HEADER, 2, _header(4)),
            (PARA_TEXT, 3, _text("옛값")),
            (HWPTAG_PARA_HEADER, 2, _header(1)),
        ]
        data, done, _r = edit(recs, {0: "새값"})
        got = list(iter_records(data))

        assert done == {0}
        assert len(got) == 3
        assert got[1][2] == "새값\r".encode("utf-16-le")

    def test_빈_값이면_레코드를_없앤다(self) -> None:
        """지우는 것은 빈 `PARA_TEXT` 를 쓰는 것이 아니라 레코드를 빼는 일이다."""
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import edit

        recs = [(HWPTAG_PARA_HEADER, 2, _header(4)), (PARA_TEXT, 3, _text("옛값"))]
        data, done, _r = edit(recs, {0: ""})
        got = list(iter_records(data))

        assert done == {0}
        assert [t for t, _lv, _p in got] == [HWPTAG_PARA_HEADER]
        assert struct.unpack_from("<I", got[0][2], 0)[0] == 1


class Test개체_앵커:
    """그림이 매달린 문단은 **아예 손대지 않는다** — hwplib 판본 B 가 안 열린 자리다."""

    def test_확장_제어문자가_있으면_거절한다(self) -> None:
        from finnect.forms.hwp5 import edit, has_object_anchor

        anchored = struct.pack("<8H", 11, 0, 0, 0, 0, 0, 0, 0) + _text("그림 옆 글")
        assert has_object_anchor(anchored)

        recs = [(HWPTAG_PARA_HEADER, 2, _header(9)), (PARA_TEXT, 3, anchored)]
        data, done, refused = edit(recs, {0: "새값"})

        assert (done, refused) == (set(), {0})
        assert data == emit(HWPTAG_PARA_HEADER, 2, _header(9)) + emit(PARA_TEXT, 3, anchored)

    def test_보통_글은_앵커가_아니다(self) -> None:
        from finnect.forms.hwp5 import has_object_anchor

        assert not has_object_anchor(_text("주식회사 가나다"))


class Test같은_크기_포장:
    """`olefile` 은 CFB 를 새로 못 만든다. **같은 크기로만 되쓸 수 있다.**"""

    def test_정확히_그_크기로_만든다(self) -> None:
        import zlib

        from finnect.forms.hwp5 import pack

        data = ("공고 신청서 본문 " * 400).encode("utf-16-le")
        target = len(zlib.compress(data, 9)) + 400
        got = pack(data, target)

        assert got is not None
        assert len(got) == target
        assert zlib.decompress(got, -15) == data

    def test_안_들어가면_없다고_말한다(self) -> None:
        """실측 5%다. 조용히 잘린 파일을 내놓지 않는다."""
        from finnect.forms.hwp5 import pack

        assert pack(("가" * 5000).encode("utf-16-le"), 10) is None


class Test정렬_보정:
    """배분정렬은 라벨의 서식이다. **값 문단만 옮기고 라벨이 쓰는 모양은 안 건드린다.**"""

    def test_첫_바이트만_다른_것을_고른다(self) -> None:
        from finnect.forms.hwp5 import ALIGN_CENTER, ALIGN_DISTRIBUTE, align_substitutes

        di = _docinfo(_shape(ALIGN_CENTER), _shape(ALIGN_DISTRIBUTE))

        assert align_substitutes(di) == {1: 0}

    def test_다른_속성이_다르면_안_옮긴다(self) -> None:
        """테두리가 다른 모양으로 옮기면 남의 서식을 끌어온다. 벌어져 보이는 것이 낫다."""
        from finnect.forms.hwp5 import ALIGN_CENTER, ALIGN_DISTRIBUTE, align_substitutes

        di = _docinfo(_shape(ALIGN_CENTER, border=7), _shape(ALIGN_DISTRIBUTE, border=2))

        assert align_substitutes(di) == {}

    def test_값_문단의_모양만_바꾼다(self) -> None:
        from finnect.attach.hwp import iter_records
        from finnect.forms.hwp5 import edit

        recs = [
            (HWPTAG_PARA_HEADER, 2, _header(1, shape=5)),   # 값 자리
            (HWPTAG_PARA_HEADER, 2, _header(4, shape=5)),   # 라벨
            (PARA_TEXT, 3, _text("매출액")),
        ]
        data, _d, _r = edit(recs, {0: "1,240"}, {5: 9})
        heads = [p for t, _lv, p in iter_records(data) if t == HWPTAG_PARA_HEADER]

        assert struct.unpack_from("<H", heads[0], 8)[0] == 9
        assert struct.unpack_from("<H", heads[1], 8)[0] == 5
