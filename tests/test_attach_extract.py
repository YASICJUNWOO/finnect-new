"""해독 판정 — **예외를 밖으로 던지지 않는다.**

이 모듈의 산출물은 텍스트가 아니라 판정이라, 실패도 정상적인 반환값이다.
조용히 건너뛰는 경로가 하나도 없어야 T-0004 가 닫힌다(plan/07).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

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


def test_이미지는_실패가_아니라_미지원이다(tmp_path: Path) -> None:
    """'안 해봤다'와 '해봤는데 안 됐다'는 다른 사실이다."""
    f = tmp_path / "공고문.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    got = extract.parse(f, "공고문.png")

    assert got.status is ParseStatus.UNSUPPORTED
    assert got.ext == "png"
    assert got.text is None


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
