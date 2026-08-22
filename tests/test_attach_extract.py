"""해독 판정 — **예외를 밖으로 던지지 않는다.**

이 모듈의 산출물은 텍스트가 아니라 판정이라, 실패도 정상적인 반환값이다.
조용히 건너뛰는 경로가 하나도 없어야 T-0004 가 닫힌다(plan/07).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from finnect.attach import extract
from finnect.models import ParseStatus

DOCX_BODY = (
    b'<?xml version="1.0"?><w:document xmlns:w="x"><w:p><w:r>'
    b"<w:t>\xec\x82\xac\xec\x97\x85\xea\xb3\x84\xed\x9a\x8d\xec\x84\x9c</w:t>"  # 사업계획서
    b"</w:r></w:p></w:document>"
)


def _zip(path: Path, names: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in names.items():
            z.writestr(name, data)
    return path


def test_docx에서_텍스트가_나온다(tmp_path: Path) -> None:
    f = _zip(tmp_path / "양식.docx", {"word/document.xml": DOCX_BODY})

    got = extract.parse(f, "양식.docx")

    assert got.status is ParseStatus.OK
    assert got.parser == "docx/zip"
    assert "사업계획서" in (got.text or "")


#: 문단 둘과 2x2 표 하나. 셀 내용은 실물처럼 <hp:subList> 안의 <hp:p> 에 둔다.
HWPX_BODY = """<?xml version="1.0"?><hs:sec xmlns:hp="x" xmlns:hs="y">
<hp:p><hp:run><hp:t>2026년 지원사업 신청서</hp:t></hp:run></hp:p>
<hp:p><hp:run><hp:t>기업 정보</hp:t></hp:run></hp:p>
<hp:p><hp:run><hp:tbl rowCnt="2" colCnt="2">
<hp:tr>
 <hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList></hp:tc>
 <hp:tc><hp:subList><hp:p><hp:run><hp:t>(주)가나다</hp:t></hp:run></hp:p></hp:subList></hp:tc>
</hp:tr>
<hp:tr>
 <hp:tc><hp:subList><hp:p><hp:run><hp:t>대표자</hp:t></hp:run></hp:p></hp:subList></hp:tc>
 <hp:tc><hp:subList><hp:p><hp:run><hp:t>홍길동</hp:t></hp:run></hp:p></hp:subList></hp:tc>
</hp:tr>
</hp:tbl></hp:run></hp:p>
</hs:sec>""".encode()


def test_hwpx가_문단을_줄로_남긴다(tmp_path: Path) -> None:
    """텍스트만 이어 붙이면 9,841자 문서가 1줄로 나온다 — 305건이 그 상태였다."""
    f = _zip(tmp_path / "신청서.hwpx", {"Contents/section0.xml": HWPX_BODY})

    got = extract.parse(f, "신청서.hwpx")

    assert got.status is ParseStatus.OK
    assert got.parser == "hwpx/zip"
    lines = [ln for ln in (got.text or "").splitlines() if ln.strip()]
    assert lines[0] == "2026년 지원사업 신청서"
    assert lines[1] == "기업 정보"


def test_hwpx가_표를_행과_셀로_남긴다(tmp_path: Path) -> None:
    """양식 항목은 셀 라벨로 산다. 라벨과 값이 같은 줄에 있어야 짝이 보인다."""
    f = _zip(tmp_path / "신청서.hwpx", {"Contents/section0.xml": HWPX_BODY})

    got = extract.parse(f, "신청서.hwpx")

    lines = [ln for ln in (got.text or "").splitlines() if ln.strip()]
    assert "기업명\t(주)가나다" in lines
    assert "대표자\t홍길동" in lines


def _rec(tag: int, level: int, payload: bytes) -> tuple[int, int, bytes]:
    return tag, level, payload


def _para(text: str) -> bytes:
    return text.encode("utf-16-le")


def _cell(col: int, row: int) -> bytes:
    """LIST_HEADER — nParas(4) + listAttr(4) 다음이 셀 주소다."""
    import struct

    return b"\x00" * 8 + struct.pack("<HHHH", col, row, 1, 1)


def test_배포용_문서는_해독_성공이_아니다() -> None:
    """본문이 ViewText 에 있고 BodyText 에는 '뷰어가 필요합니다' 안내문만 있다.

    그냥 두면 107자짜리 '해독 성공'으로 남는다 — 조용한 누락과 같다.
    """
    import pytest

    from finnect.attach import hwp

    with pytest.raises(ValueError, match="배포용"):
        hwp._reject_flags(0x5)  # 압축 + 배포용. 실측 5건이 전부 이 값이다

    with pytest.raises(ValueError, match="암호"):
        hwp._reject_flags(0x3)

    hwp._reject_flags(0x4001)  # ViewText 는 있으나 배포용이 아니다. 멀쩡히 해독된다


def test_표_컨트롤_id는_뒤집혀_들어온다() -> None:
    """실물에서 확인한 바이트다. 상수를 뒤집어 쓰면 표를 하나도 못 찾는다.

    이 검사를 따로 두는 이유는, 조립 테스트가 같은 상수를 쓰면 방향이 틀려도 통과하기
    때문이다. 실제로 한 번 그렇게 놓쳤다.
    """
    from finnect.attach import hwp

    assert hwp.CTRL_ID_TABLE[::-1] == b"tbl "


def test_hwp가_표를_행과_셀로_편다() -> None:
    """양식 항목은 표 셀 라벨로 산다. 뭉개면 어느 것이 라벨인지 사라진다."""
    from finnect.attach import hwp

    recs = [
        _rec(67, 1, _para("신청서\r")),
        _rec(71, 1, hwp.CTRL_ID_TABLE),  # 표 시작
        _rec(77, 2, b"\x00" * 8),
        _rec(72, 2, _cell(0, 0)),
        _rec(67, 3, _para("기업명\r")),
        _rec(72, 2, _cell(1, 0)),
        _rec(67, 3, _para("(주)가나다\r")),
        _rec(72, 2, _cell(0, 1)),
        _rec(67, 3, _para("대표자\r")),
        _rec(72, 2, _cell(1, 1)),
        _rec(67, 3, _para("홍길동\r")),
        _rec(66, 0, b""),  # level 이 내려오면 표가 끝난다
        _rec(67, 1, _para("끝\r")),
    ]

    got = hwp._assemble(iter(recs))

    lines = [ln for ln in got.splitlines() if ln.strip()]
    assert "기업명\t(주)가나다" in lines
    assert "대표자\t홍길동" in lines
    assert lines[0] == "신청서"
    assert lines[-1] == "끝"


def test_hwp의_빈_셀이_탭_자리를_지킨다() -> None:
    """빈 셀이 양식에서는 채울 칸이다. 지우면 라벨만 남아 짝이 깨진다."""
    from finnect.attach import hwp

    recs = [
        _rec(71, 0, hwp.CTRL_ID_TABLE),
        _rec(77, 1, b"\x00" * 8),
        _rec(72, 1, _cell(0, 0)),
        _rec(67, 2, _para("기업명\r")),
        _rec(72, 1, _cell(1, 0)),  # 빈 칸 — 신청자가 채운다
        _rec(72, 1, _cell(2, 0)),
        _rec(67, 2, _para("담당자\r")),
    ]

    got = hwp._assemble(iter(recs))

    assert "기업명\t\t담당자" in got


def test_표_밖의_list_header는_셀이_아니다() -> None:
    """LIST_HEADER 는 글상자에도 쓰인다. 표 안일 때만 셀로 읽는다."""
    from finnect.attach import hwp

    recs = [
        _rec(72, 0, _cell(3, 7)),  # 표 컨트롤이 없다
        _rec(67, 1, _para("글상자 안 글\r")),
    ]

    got = hwp._assemble(iter(recs))

    assert "글상자 안 글" in got
    assert "\t" not in got


def test_이미지는_실패가_아니라_미지원이다(tmp_path: Path) -> None:
    """'안 해봤다'와 '해봤는데 안 됐다'는 다른 사실이다."""
    f = tmp_path / "공고문.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    got = extract.parse(f, "공고문.png")

    assert got.status is ParseStatus.UNSUPPORTED
    assert got.ext == "png"
    assert got.text is None


@pytest.mark.parametrize(
    ("name", "head", "ext"),
    [
        ("스캔본.tiff", b"II*\x00", "tiff"),
        ("사진.webp", b"RIFF\x00\x00\x00\x00WEBP", "webp"),
        ("도면.bmp", b"BM\x36\x00\x00\x00", "bmp"),
        ("표.gif", b"GIF89a", "gif"),
    ],
)
def test_사용자_그림_넷이_ocr_문턱까지_간다(
    tmp_path: Path, name: str, head: bytes, ext: str
) -> None:
    """**문전에서 잘린 것과 그림이라 OCR 이 필요한 것은 다른 사실이다**(T-0097).

    `ocr.IMAGE_EXTS` 는 여섯인데 `user_file_formats` 가 `jpg`·`png` 둘만 열어 둬서
    나머지 넷이 `ext not in allowed` 에서 잘렸다. **파서가 있는데 설정이 막고 있었다** —
    tiff 는 스캐너·팩스 기본 출력이고 webp 는 웹에서 저장한 그림의 기본이다.

    이유를 보는 것이 요점이다. 두 경로가 상태는 같고(`UNSUPPORTED`) 뜻이 다르다.
    """
    from finnect.config import settings

    f = tmp_path / name
    f.write_bytes(head + b"\x00" * 64)

    got = extract.parse(f, name, allowed=settings.wiki_formats, use_ocr=False)

    assert got.ext == ext
    assert got.status is ParseStatus.UNSUPPORTED
    # 목록에서 잘렸으면 이유가 없다. 그림 분기까지 갔으면 이유가 OCR 을 말한다.
    assert got.error and "OCR" in got.error


def test_첨부_목록은_그림을_안_받는다(tmp_path: Path) -> None:
    """**T-0097 은 사용자 파일만 연다.**

    첨부를 같이 열면 plan/07 이 측정한 2,827/3,354 가 근거를 잃는다.
    """
    from finnect.config import settings

    f = tmp_path / "스캔본.tiff"
    f.write_bytes(b"II*\x00" + b"\x00" * 64)

    got = extract.parse(f, "스캔본.tiff", allowed=settings.formats, use_ocr=False)

    assert got.status is ParseStatus.UNSUPPORTED
    assert got.error is None  # 문전에서 잘렸다. 그림 분기까지 안 갔다


def test_깨진_pdf는_실패로_남는다(tmp_path: Path) -> None:
    f = tmp_path / "깨진.pdf"
    f.write_bytes(b"%PDF-1.7\n" + b"\xff" * 64)

    got = extract.parse(f, "깨진.pdf")

    # 예외가 밖으로 나오면 안 된다. 상태와 이유가 남아야 한다.
    assert got.status is ParseStatus.FAILED
    assert got.parser == "pdf/plumber"
    assert got.error


def test_빈_문서는_empty다(tmp_path: Path) -> None:
    """파서는 돌았는데 0바이트. 스캔본이 여기 걸리고 T-0007 이 이 숫자를 쓴다."""
    f = _zip(tmp_path / "빈.docx", {"word/document.xml": b'<?xml version="1.0"?><w:document/>'})

    got = extract.parse(f, "빈.docx")

    assert got.status is ParseStatus.EMPTY
    assert got.text == ""


def test_zip은_목록만_읽는다(tmp_path: Path) -> None:
    f = _zip(
        tmp_path / "묶음.zip",
        {"별첨1_사업계획서.hwp": b"x" * 10, "별첨2_안내.pdf": b"y" * 20},
    )

    got = extract.parse(f, "묶음.zip")

    assert got.status is ParseStatus.CONTAINER
    assert got.text is None  # 풀지 않는다
    assert [c["ext"] for c in got.contents] == ["hwp", "pdf"]


def test_지원_목록을_줄이면_미해독이_늘_뿐_사라지지_않는다(
    tmp_path: Path, monkeypatch
) -> None:
    from finnect.config import settings

    f = _zip(tmp_path / "양식.docx", {"word/document.xml": DOCX_BODY})
    monkeypatch.setattr(settings, "attachment_formats", "pdf")  # docx 를 뺀다

    got = extract.parse(f, "양식.docx")

    assert got.status is ParseStatus.UNSUPPORTED
    assert got.ext == "docx"  # 무엇이었는지는 여전히 남는다
