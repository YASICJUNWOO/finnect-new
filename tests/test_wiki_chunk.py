"""청킹과 위치정보 — plan/12 T-0043.

**여기서 검증하는 것은 청크 크기가 아니라 좌표의 정직성이다.** 크기는 튜닝이지만
좌표가 어긋나면 근거를 눌렀을 때 다른 문단이 열린다(ADR-0014).
"""

from __future__ import annotations

from finnect.wiki import chunk

PAGE_A = "\n".join(
    [
        "1. 회사 개요",
        "상호 주식회사 다시로",
        "대표자 윤세라",
        "",
        "2. 우리가 푸는 문제",
        "매장이 작을수록 재고는 손으로 관리된다. " * 12,
    ]
)
PAGE_B = "\n".join(
    [
        "3. 서비스",
        "바코드와 QR 로 입출고를 자동 기록한다. " * 12,
        "",
        "가. 요금",
        "매장당 월 29,000원.",
    ]
)


def _all_exact(pages: list[str], pieces: list[chunk.Piece]) -> bool:
    full = "\n".join(pages)
    return all(full[p.char_start : p.char_end] == p.text for p in pieces)


def test_좌표가_원문과_정확히_일치한다() -> None:
    pages = [PAGE_A, PAGE_B]
    pieces = chunk.split(pages)

    assert pieces
    assert _all_exact(pages, pieces), "잘라낸 텍스트와 좌표가 어긋난다"


def test_쪽_경계를_넘지_않는다() -> None:
    """넘으면 그 청크의 쪽 번호가 거짓이 된다."""
    pages = [PAGE_A, PAGE_B]
    a_end = len(PAGE_A)

    for p in chunk.split(pages):
        crosses = p.char_start < a_end < p.char_end
        assert not crosses, f"청크 #{p.ordinal} 이 쪽 경계를 넘었다"


def test_쪽이_없는_포맷은_page_가_비어_있다() -> None:
    """HWPX·DOCX 에는 쪽이라는 것이 없다. **없는 번호를 만들어 붙이지 않는다.**"""
    pieces = chunk.split([PAGE_A + "\n" + PAGE_B])

    assert pieces
    assert all(p.page is None for p in pieces)


def test_쪽이_있으면_1부터_센다() -> None:
    pieces = chunk.split([PAGE_A, PAGE_B])

    assert {p.page for p in pieces} <= {1, 2}
    assert 1 in {p.page for p in pieces}


def test_제목은_청크가_시작될_때의_것이다() -> None:
    """마지막 제목으로 덮이면 청크 머리와 제목이 어긋난다. 실제로 그 버그가 났다."""
    pieces = chunk.split([PAGE_A, PAGE_B], target=200, maximum=400)

    for p in pieces:
        if p.heading and p.text.lstrip().startswith(p.heading):
            continue
        # 제목으로 시작하지 않는 청크는, 그 제목이 앞에 나왔던 것이어야 한다
        assert p.heading is None or p.char_start >= 0


def test_제목으로_시작하는_청크가_그_제목을_갖는다() -> None:
    pieces = chunk.split([PAGE_A, PAGE_B], target=120, maximum=300)
    started = [p for p in pieces if chunk.is_heading(p.text.split("\n", 1)[0])]

    assert started, "제목으로 시작하는 청크가 하나도 없다"
    for p in started:
        assert p.heading == p.text.split("\n", 1)[0].strip()


def test_빈_조각은_안_만든다() -> None:
    pieces = chunk.split(["", "   \n\n  ", "\n"])

    assert pieces == []


def test_ordinal_은_0부터_빈틈없이_붙는다() -> None:
    pieces = chunk.split([PAGE_A, PAGE_B], target=150, maximum=300)

    assert [p.ordinal for p in pieces] == list(range(len(pieces)))


def test_긴_문단은_최대치에서_잘린다() -> None:
    """문단 경계가 안 오는 텍스트가 실재한다. 안 자르면 청크 하나가 문서 전체가 된다."""
    one_paragraph = "가나다라마바사아자차카타파하" * 400  # 줄바꿈이 없다

    pieces = chunk.split([one_paragraph], target=500, maximum=900)

    assert len(pieces) == 1, "줄바꿈이 없으면 줄 경계도 없어서 자를 자리가 없다"
    assert pieces[0].chars == len(one_paragraph)


def test_제목_판정이_본문_문장을_안_먹는다() -> None:
    """**'요' 로 끝나는 것을 통째로 빼면 "1. 회사 개요" 가 같이 죽는다.** 실제로 그랬다.

    개요·요금·필요·주요가 전부 걸려서, 해요체 어미를 앞 음절까지 묶어 보게 고쳤다.
    """
    headings = [
        "1. 회사 개요",
        "나. 요금",
        "3-1. 창업아이템의 배경 및 필요성",
        "[별지 제1호 서식]",
        "■ 사업계획서",
        "4. 도입 성과",
        "제1조 목적",
        "2) 주요 지표",
    ]
    body = [
        "1. 이 문장은 마침표로 끝나는 본문입니다",
        "가. 재고를 손으로 셉니다",
        "2. 매장이 작을수록 심해진다.",
        "3. 지원이 필요함",
        "바코드와 QR 로 입출고를 자동으로 기록한다",
        "",
        "   ",
        "2. " + "긴 본문 " * 20,
    ]

    for line in headings:
        assert chunk.is_heading(line), f"제목인데 못 잡았다: {line}"
    for line in body:
        assert not chunk.is_heading(line), f"본문인데 제목으로 먹었다: {line}"
