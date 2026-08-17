"""확장자를 **내용으로** 판정한다.

파일명만 믿으면 안 되는 이유가 여기 있다. `.hwp` 로 끝나는데 실제로는 HWPX(ZIP) 인 파일이
실재하고, 그러면 "지원하는 포맷인데 파서가 실패했다"는 잘못된 기록이 남는다.
디스크만 타고 네트워크도 DB 도 안 탄다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from finnect.attach import formats


def _zip(path: Path, names: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in names.items():
            z.writestr(name, data)
    return path


def test_확장자가_거짓말해도_내용으로_잡는다(tmp_path: Path) -> None:
    # 이름은 .hwp 인데 알맹이는 HWPX 다.
    f = _zip(tmp_path / "속았다.hwp", {"Contents/section0.xml": b"<hml/>"})

    assert formats.detect(f, "속았다.hwp") == "hwpx"


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("Contents/section0.xml", "hwpx"),
        ("word/document.xml", "docx"),
        ("xl/workbook.xml", "xlsx"),
        ("ppt/presentation.xml", "pptx"),
    ],
)
def test_zip_계열을_갈라_본다(tmp_path: Path, marker: str, expected: str) -> None:
    f = _zip(tmp_path / f"{expected}.bin", {marker: b"<x/>"})

    assert formats.detect(f) == expected


def test_알맹이가_없는_zip은_zip이다(tmp_path: Path) -> None:
    f = _zip(tmp_path / "그냥.zip", {"읽어보세요.txt": b"hi"})

    assert formats.detect(f) == "zip"


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"%PDF-1.7\n", "pdf"),
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"\xff\xd8\xff\xe0", "jpg"),
    ],
)
def test_시그니처로_잡는다(tmp_path: Path, head: bytes, expected: str) -> None:
    f = tmp_path / "무명"
    f.write_bytes(head + b"\x00" * 32)

    assert formats.detect(f, "무명") == expected


def test_모르겠으면_파일명으로_물러난다(tmp_path: Path) -> None:
    f = tmp_path / "정체불명.xlsx"
    f.write_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08")

    assert formats.detect(f, "정체불명.xlsx") == "xlsx"


def test_파일명도_없으면_모른다고_한다(tmp_path: Path) -> None:
    f = tmp_path / "무명"
    f.write_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08")

    assert formats.detect(f) is None
