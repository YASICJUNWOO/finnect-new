"""HWP / HWPX / PDF 텍스트 추출기 — 스파이크용.

제품 코드가 아니다. "기계적으로 텍스트가 뽑히는가"만 확인한다.

HWP 5.0 은 OLE 복합문서다. BodyText/Section* 스트림이 raw deflate 로 눌려 있고,
그 안에 레코드가 이어 붙어 있다. 본문 문자열은 HWPTAG_PARA_TEXT 레코드에 UTF-16LE 로 들어간다.
제어문자 일부는 16바이트를 차지하므로 그만큼 건너뛰어야 글자가 안 깨진다.
"""

import re
import struct
import zipfile
import zlib
from pathlib import Path

HWPTAG_PARA_TEXT = 67  # HWPTAG_BEGIN(16) + 51

# PARA_TEXT 안의 제어문자. 확장형은 자기 자신 포함 8개 UInt16(=16바이트)을 차지한다.
CTRL_EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}
CTRL_INLINE = {4, 5, 6, 7, 8, 9, 19, 20}
CTRL_CHAR = {0, 10, 13, 24, 25, 26, 27, 28, 29, 30, 31}


def _iter_records(buf: bytes):
    """레코드 헤더 4바이트: tag 10bit, level 10bit, size 12bit. size==0xFFF 면 다음 4바이트가 실제 크기."""
    pos, n = 0, len(buf)
    while pos + 4 <= n:
        (header,) = struct.unpack_from("<I", buf, pos)
        pos += 4
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 4 > n:
                break
            (size,) = struct.unpack_from("<I", buf, pos)
            pos += 4
        if pos + size > n:
            break
        yield tag, buf[pos : pos + size]
        pos += size


def _para_text(payload: bytes) -> str:
    """PARA_TEXT 페이로드를 UTF-16LE 로 읽으며 제어문자를 건너뛴다."""
    out = []
    i, n = 0, len(payload) // 2
    words = struct.unpack_from(f"<{n}H", payload, 0)
    while i < n:
        c = words[i]
        if c in CTRL_EXTENDED:
            i += 8  # 확장 제어문자는 8 워드
            continue
        if c in CTRL_INLINE:
            i += 1
            continue
        if c in CTRL_CHAR:
            if c in (10, 13):
                out.append("\n")
            i += 1
            continue
        out.append(chr(c))
        i += 1
    return "".join(out)


def from_hwp(path: Path) -> str:
    import olefile

    if not olefile.isOleFile(str(path)):
        raise ValueError("OLE 파일이 아니다 (HWP 5.0 아님)")
    ole = olefile.OleFileIO(str(path))
    try:
        header = ole.openstream("FileHeader").read()
        if not header.startswith(b"HWP Document File"):
            raise ValueError("HWP 시그니처 없음")
        (flags,) = struct.unpack_from("<I", header, 36)
        compressed = bool(flags & 1)

        sections = sorted(
            ("/".join(e) for e in ole.listdir() if e[0] == "BodyText"),
            key=lambda s: int(re.sub(r"\D", "", s.split("/")[-1]) or 0),
        )
        if not sections:
            raise ValueError("BodyText 스트림 없음")

        chunks = []
        for s in sections:
            raw = ole.openstream(s).read()
            data = zlib.decompress(raw, -15) if compressed else raw
            for tag, payload in _iter_records(data):
                if tag == HWPTAG_PARA_TEXT:
                    chunks.append(_para_text(payload))
        return "\n".join(chunks)
    finally:
        ole.close()


def from_hwpx(path: Path) -> str:
    """HWPX 는 ZIP + XML 이다. 본문은 Contents/section*.xml 의 <hp:t> 에 있다."""
    texts = []
    with zipfile.ZipFile(path) as z:
        names = sorted(
            n for n in z.namelist()
            if re.match(r"Contents/section\d+\.xml$", n)
        )
        if not names:
            names = [n for n in z.namelist() if n.endswith(".xml") and "section" in n.lower()]
        for n in names:
            xml = z.read(n).decode("utf-8", errors="replace")
            # <hp:t> 안의 텍스트. 태그 접두사가 다를 수 있어 느슨하게 잡는다.
            for m in re.finditer(r"<(?:\w+:)?t(?:\s[^>]*)?>(.*?)</(?:\w+:)?t>", xml, re.S):
                frag = re.sub(r"<[^>]+>", "", m.group(1))
                texts.append(
                    frag.replace("&lt;", "<").replace("&gt;", ">")
                        .replace("&amp;", "&").replace("&quot;", '"')
                )
            texts.append("\n")
    return "".join(texts)


def from_docx(path: Path) -> str:
    """DOCX 도 ZIP + XML 이다. 본문은 word/document.xml 의 <w:t>.

    표 안 텍스트도 같은 <w:t> 에 들어가므로 그대로 잡힌다.
    머리글·바닥글·텍스트박스까지 보려면 header*/footer* 도 훑는다.
    """
    texts = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if re.match(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$", n)]
        for n in sorted(names):
            xml = z.read(n).decode("utf-8", errors="replace")
            # 단락 경계를 줄바꿈으로, 표 셀 경계를 탭으로 살린다
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"</w:tc>", "\t", xml)
            for m in re.finditer(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|(\n|\t)", xml, re.S):
                if m.group(1) is not None:
                    frag = re.sub(r"<[^>]+>", "", m.group(1))
                    texts.append(
                        frag.replace("&lt;", "<").replace("&gt;", ">")
                            .replace("&amp;", "&").replace("&quot;", '"')
                    )
                else:
                    texts.append(m.group(2))
    return "".join(texts)


def from_pdf(path: Path) -> str:
    import pdfplumber

    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def extract(path: Path) -> tuple[str, str]:
    """(텍스트, 사용한 방식) 을 돌려준다. 실패하면 예외."""
    ext = path.suffix.lower().lstrip(".")
    if ext == "hwp":
        return from_hwp(path), "hwp/ole"
    if ext == "hwpx":
        return from_hwpx(path), "hwpx/zip"
    if ext == "pdf":
        return from_pdf(path), "pdf/plumber"
    if ext in ("docx", "docm"):
        return from_docx(path), "docx/zip"
    raise ValueError(f"지원하지 않는 확장자: {ext}")
