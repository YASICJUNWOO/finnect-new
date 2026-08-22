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
        (b"GIF89a", "gif"),
        (b"BM\x36\x00\x00\x00", "bmp"),
        # TIFF 는 바이트 순서를 앞 두 글자로 말한다. **둘 다 TIFF 다** —
        # 스캐너가 어느 쪽으로 쓸지는 기기가 정한다.
        (b"II*\x00", "tiff"),
        (b"MM\x00*", "tiff"),
        (b"RIFF\x00\x00\x00\x00WEBP", "webp"),
    ],
)
def test_시그니처로_잡는다(tmp_path: Path, head: bytes, expected: str) -> None:
    f = tmp_path / "무명"
    f.write_bytes(head + b"\x00" * 32)

    assert formats.detect(f, "무명") == expected


def test_riff인데_webp가_아니면_webp라고_안_한다(tmp_path: Path) -> None:
    """RIFF 는 WebP · WAV · AVI 가 공유한다. **앞 네 바이트만 보면 소리가 그림이 된다.**

    ZIP 을 `_zip_kind` 로 더 가르는 것과 같은 이유다. 컨테이너 이름은 포맷이 아니다.
    """
    f = tmp_path / "녹음.wav"
    f.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 32)

    # 모르는 것은 모른다고 하고 파일명으로 물러난다.
    assert formats.detect(f, "녹음.wav") == "wav"
    assert formats.detect(f) is None


def test_모르겠으면_파일명으로_물러난다(tmp_path: Path) -> None:
    f = tmp_path / "정체불명.xlsx"
    f.write_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08")

    assert formats.detect(f, "정체불명.xlsx") == "xlsx"


def test_파일명도_없으면_모른다고_한다(tmp_path: Path) -> None:
    f = tmp_path / "무명"
    f.write_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08")

    assert formats.detect(f) is None


def test_사용자_파일_그림_목록이_ocr_목록과_같다() -> None:
    """**갈리면 조용히 잘린다**(T-0097).

    두 표가 따로 사는 데는 이유가 있다 — `IMAGE_EXTS` 는 "OCR 이 읽을 수 있는가" 이고
    `user_file_formats` 는 "받을 것인가" 다. 그런데 그림에 한해서는 답이 같아야 한다.
    한쪽에만 있으면 `extract.parse` 가 `ext not in allowed` 에서 잘라내고, 사용자는
    **왜 안 되는지 모르는 채** `unsupported` 만 본다.

    첨부(`settings.formats`)는 일부러 안 잰다. 저기는 그림을 안 받는 것이 결정이다.
    """
    from finnect.attach import ocr
    from finnect.config import settings

    assert settings.wiki_formats & ocr.IMAGE_EXTS == ocr.IMAGE_EXTS


def test_시그니처_표에_없는_그림은_파일명에_기댄다(tmp_path: Path) -> None:
    """**HEIC 가 여기 걸린다**(T-0100 · 아직 안 함).

    아이폰 사진 기본 포맷인데 `MAGIC` 에 시그니처가 없다. ISO-BMFF 라 `ftyp` 이
    맨 앞이 아니라 **오프셋 4** 에 있어서 지금의 `startswith` 표로는 안 잡힌다.
    이 테스트는 그 사실을 박아 두는 것이지 동작을 승인하는 것이 아니다.
    """
    f = tmp_path / "사업자등록증.heic"
    f.write_bytes(b"\x00\x00\x00\x20ftypheic" + b"\x00" * 32)

    assert formats.detect(f, "사업자등록증.heic") == "heic"  # 파일명이 맞았을 때만
    assert formats.detect(f) is None  # 이름이 없으면 못 잡는다
