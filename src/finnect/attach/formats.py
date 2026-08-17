"""지원 포맷 목록과 **내용 기반** 확장자 판정.

목록은 설정에 있다(`ATTACHMENT_FORMATS`). 코드를 고치지 않고 끄고 켠다 — T-0004 완료 조건.

확장자를 파일명이 아니라 내용으로 판정하는 이유는 **파일명이 거짓말을 하기 때문이다.**
`.hwp` 로 끝나는데 실제로는 HWPX(ZIP) 인 파일이 실재하고, 반대로 확장자가 없는 것도 있다.
파일명만 믿으면 "지원하는 포맷인데 파서가 실패했다"는 잘못된 기록이 남는다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from finnect.config import settings

#: 시그니처 → 확장자. 앞에서부터 처음 맞는 것을 쓴다.
MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "pdf"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),  # HWP 5.0 · DOC · XLS 공통
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF8", "gif"),
    (b"PK\x03\x04", "zip"),  # HWPX · DOCX · XLSX · PPTX 공통. 아래에서 더 가른다
)

#: ZIP 안에 이 경로가 있으면 그 포맷이다.
ZIP_MARKERS: tuple[tuple[str, str], ...] = (
    ("Contents/section0.xml", "hwpx"),
    ("word/document.xml", "docx"),
    ("xl/workbook.xml", "xlsx"),
    ("ppt/presentation.xml", "pptx"),
)


def supported() -> frozenset[str]:
    return settings.formats


def name_ext(filename: str | None) -> str | None:
    """파일명에서 딴 확장자. 판정의 근거가 아니라 참고값이다."""
    if not filename:
        return None
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or None


def detect(path: Path, filename: str | None = None) -> str | None:
    """파일 내용으로 확장자를 판정한다. 모르겠으면 파일명 확장자로 물러난다."""
    try:
        head = path.open("rb").read(8)
    except OSError:
        return name_ext(filename)

    kind = next((ext for sig, ext in MAGIC if head.startswith(sig)), None)

    if kind == "zip":
        return _zip_kind(path) or "zip"
    if kind == "ole":
        # OLE 는 HWP · DOC · XLS 가 공유한다. HWP 는 FileHeader 스트림에 시그니처가 있다.
        return "hwp" if _is_hwp(path) else (name_ext(filename) or "ole")
    return kind or name_ext(filename)


def _zip_kind(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (zipfile.BadZipFile, OSError):
        return None
    for marker, ext in ZIP_MARKERS:
        if marker in names:
            return ext
    # HWPX 는 section 번호가 0 이 아닐 수 있다.
    if any(n.startswith("Contents/section") for n in names):
        return "hwpx"
    return None


def _is_hwp(path: Path) -> bool:
    try:
        import olefile

        if not olefile.isOleFile(str(path)):
            return False
        ole = olefile.OleFileIO(str(path))
        try:
            if not ole.exists("FileHeader"):
                return False
            return ole.openstream("FileHeader").read(17).startswith(b"HWP Document File")
        finally:
            ole.close()
    except Exception:
        return False
