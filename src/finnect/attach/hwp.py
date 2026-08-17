"""HWP / HWPX / DOCX / PDF 텍스트 추출기.

`spike/hwp_text.py` 를 승격한 것이다. **스파이크는 버리는 코드지만 알아낸 것은 유효하다**
(plan/02). 실측 추출률은 HWP·HWPX·DOCX 100% · PDF 91% · 전체 95%다.

**라이브러리를 바꾸지 않는 이유가 그 숫자다**(ADR-0022 3번). 95%는 `pdfplumber` 로 잰
값이라, 다른 것으로 갈면 더는 근거가 아니게 되고 다시 재야 한다.

승격하면서 붙인 것은 예외 방어뿐이다. 추출 로직은 그대로다.

HWP 5.0 은 OLE 복합문서다. BodyText/Section* 스트림이 raw deflate 로 눌려 있고 그 안에
레코드가 이어 붙어 있다. 본문은 HWPTAG_PARA_TEXT 레코드에 UTF-16LE 로 들어간다.
제어문자 일부가 16바이트를 차지하므로 그만큼 건너뛰어야 글자가 안 깨진다.
"""

from __future__ import annotations

import re
import struct
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

HWPTAG_PARA_TEXT = 67  # HWPTAG_BEGIN(16) + 51

# PARA_TEXT 안의 제어문자. 확장형은 자기 자신 포함 8개 UInt16(=16바이트)을 차지한다.
CTRL_EXTENDED = frozenset({1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23})
CTRL_INLINE = frozenset({4, 5, 6, 7, 8, 9, 19, 20})
CTRL_CHAR = frozenset({0, 10, 13, 24, 25, 26, 27, 28, 29, 30, 31})

_ENTITIES = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&amp;", "&"))


def _unescape(s: str) -> str:
    # &amp; 를 마지막에 푼다. 먼저 풀면 &amp;lt; 가 < 로 두 번 풀린다.
    for src, dst in _ENTITIES:
        s = s.replace(src, dst)
    return s


def _iter_records(buf: bytes) -> Iterator[tuple[int, bytes]]:
    """레코드 헤더 4바이트: tag 10bit · level 10bit · size 12bit.

    size == 0xFFF 면 다음 4바이트가 실제 크기다.
    """
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
    """PARA_TEXT 페이로드를 UTF-16LE 로 읽으며 제어문자를 건너뛴다.

    **코드유닛을 `chr()` 로 하나씩 옮기지 않는다.** 스파이크가 그렇게 했는데, 이모지처럼
    BMP 밖의 글자는 UTF-16 에서 서로게이트 **쌍**으로 오므로 낱개로 옮기면 짝 잃은
    서로게이트가 남는다. 파이썬 문자열로는 만들어지지만 UTF-8 로 저장할 때 터진다.
    실제로 첫 20건 안에서 터졌다.

    남길 코드유닛만 모아서 **한 번에** UTF-16LE 로 디코드한다. 쌍은 그때 알아서 합쳐진다.
    """
    kept: list[int] = []
    n = len(payload) // 2
    words = struct.unpack_from(f"<{n}H", payload, 0)
    i = 0
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
                kept.append(0x000A)
            i += 1
            continue
        kept.append(c)
        i += 1
    return struct.pack(f"<{len(kept)}H", *kept).decode("utf-16-le", errors="replace")


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
        if flags & 2:
            # 암호가 걸린 문서. 풀 수 없는 것과 파서가 틀린 것을 구분해서 남긴다.
            raise ValueError("암호가 걸린 문서다")

        sections = sorted(
            ("/".join(e) for e in ole.listdir() if e[0] == "BodyText"),
            key=lambda s: int(re.sub(r"\D", "", s.split("/")[-1]) or 0),
        )
        if not sections:
            raise ValueError("BodyText 스트림 없음")

        chunks: list[str] = []
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
    """HWPX 는 ZIP + XML 이다. 본문은 Contents/section*.xml 의 <hp:t>."""
    texts: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        if not names:
            names = [n for n in z.namelist() if n.endswith(".xml") and "section" in n.lower()]
        for n in names:
            xml = z.read(n).decode("utf-8", errors="replace")
            # 태그 접두사가 다를 수 있어 느슨하게 잡는다.
            for m in re.finditer(r"<(?:\w+:)?t(?:\s[^>]*)?>(.*?)</(?:\w+:)?t>", xml, re.S):
                texts.append(_unescape(re.sub(r"<[^>]+>", "", m.group(1))))
            texts.append("\n")
    return "".join(texts)


def from_docx(path: Path) -> str:
    """DOCX 도 ZIP + XML 이다. 본문은 word/document.xml 의 <w:t>.

    표 안 텍스트도 같은 <w:t> 라 그대로 잡힌다. 머리글·바닥글·주석까지 훑는다.
    """
    texts: list[str] = []
    with zipfile.ZipFile(path) as z:
        pattern = r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"
        for n in sorted(x for x in z.namelist() if re.match(pattern, x)):
            xml = z.read(n).decode("utf-8", errors="replace")
            # 단락 경계를 줄바꿈으로, 표 셀 경계를 탭으로 살린다.
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"</w:tc>", "\t", xml)
            for m in re.finditer(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|(\n|\t)", xml, re.S):
                if m.group(1) is not None:
                    texts.append(_unescape(re.sub(r"<[^>]+>", "", m.group(1))))
                else:
                    texts.append(m.group(2))
    return "".join(texts)


def from_pdf(path: Path) -> str:
    import pdfplumber

    out: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def zip_listing(path: Path) -> list[dict[str, object]]:
    """ZIP 안의 파일 목록. **풀지 않는다**(ADR-0022 4번).

    166건 안에 사업계획서 양식이 몇 개 들어 있는지는 알아야 하고, 재귀 파싱을 지금 붙이면
    저장 모델이 한 단계 깊어진다. 목록만 남기고 그걸 보고 정한다.
    """
    with zipfile.ZipFile(path) as z:
        return [
            {
                "name": i.filename,
                "ext": Path(i.filename).suffix.lower().lstrip(".") or None,
                "size": i.file_size,
            }
            for i in z.infolist()
            if not i.is_dir()
        ]
