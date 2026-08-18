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

import datetime as dt
import re
import struct
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

HWPTAG_PARA_TEXT = 67  # HWPTAG_BEGIN(16) + 51
HWPTAG_CTRL_HEADER = 71
HWPTAG_LIST_HEADER = 72  # 표에서는 셀 하나다
HWPTAG_TABLE = 77

#: CTRL_HEADER 페이로드 앞 4바이트가 컨트롤 ID 다. **뒤집혀 들어온다** —
#: 사람이 읽는 이름은 `tbl ` 이고 바이트로는 `" lbt"` 다. 뒤집는 것을 잊으면
#: 표를 하나도 못 찾고, 단위 테스트가 같은 상수를 쓰면 그 사실이 안 잡힌다.
CTRL_ID_TABLE = b" lbt"

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


def _iter_records(buf: bytes) -> Iterator[tuple[int, int, bytes]]:
    """레코드 헤더 4바이트: tag 10bit · level 10bit · size 12bit.

    size == 0xFFF 면 다음 4바이트가 실제 크기다.

    **level 을 같이 준다.** 레코드는 level 로 트리를 이룬다 — 표 컨트롤이 level L 이면
    그 표의 셀은 L+1 이고, level 이 L 이하로 내려오는 순간이 표가 끝난 자리다.
    표 구조를 살리려면(T-0033) 이 값이 있어야 한다.
    """
    pos, n = 0, len(buf)
    while pos + 4 <= n:
        (header,) = struct.unpack_from("<I", buf, pos)
        pos += 4
        tag = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 4 > n:
                break
            (size,) = struct.unpack_from("<I", buf, pos)
            pos += 4
        if pos + size > n:
            break
        yield tag, level, buf[pos : pos + size]
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


#: FileHeader 속성 비트. 0 압축 · 1 암호 · 2 배포용 문서.
HWP_FLAG_COMPRESSED = 0x1
HWP_FLAG_ENCRYPTED = 0x2
HWP_FLAG_DISTRIBUTION = 0x4


def _reject_flags(flags: int) -> None:
    """열어 봤자 본문이 안 나오는 문서를 **실패로 돌려세운다**(T-0034).

    배포용 문서는 본문이 `BodyText` 가 아니라 `ViewText` 에 암호화돼 들어간다.
    `BodyText` 에는 "최신 버전의 글 또는 글 전용 뷰어가 필요합니다" 안내문만 있어서,
    그냥 두면 **107자짜리 '해독 성공'** 으로 남는다. 조용한 누락과 같은 것이라
    plan/07 의 "조용한 누락 0건" 검증에 구멍이 됐다.

    실측 5건이 전부 이 비트다. `ViewText` 스트림만 있고 이 비트가 없는 4건은
    멀쩡히 해독되므로 **스트림 유무가 아니라 이 비트로 가른다.**
    """
    if flags & HWP_FLAG_ENCRYPTED:
        # 암호가 걸린 문서. 풀 수 없는 것과 파서가 틀린 것을 구분해서 남긴다.
        raise ValueError("암호가 걸린 문서다")
    if flags & HWP_FLAG_DISTRIBUTION:
        raise ValueError("배포용 문서다 — 본문이 ViewText 에 암호화돼 있다")


class _Table:
    """열려 있는 표 하나. 셀을 (행, 열)로 받아 두었다가 끝날 때 행 단위로 편다."""

    __slots__ = ("level", "rows", "cur")

    def __init__(self, level: int) -> None:
        self.level = level
        self.rows: dict[int, dict[int, list[str]]] = {}
        self.cur: tuple[int, int] | None = None

    def open_cell(self, row: int, col: int) -> None:
        self.rows.setdefault(row, {}).setdefault(col, [])
        self.cur = (row, col)

    def parts(self) -> list[str] | None:
        if self.cur is None:
            return None
        row, col = self.cur
        return self.rows[row][col]

    def render(self) -> str:
        """행은 줄, 셀은 탭. **빈 셀도 탭 자리를 지킨다** — 양식에서 그게 채울 칸이다."""
        lines = []
        for r in sorted(self.rows):
            cells = ["".join(v).split() for _, v in sorted(self.rows[r].items())]
            lines.append("\t".join(" ".join(c) for c in cells))
        return "\n".join(lines)


def _assemble(records: Iterator[tuple[int, int, bytes]]) -> str:
    """레코드 흐름을 텍스트로 편다. **표는 행과 셀을 살린다**(T-0033).

    OLE 를 열지 않으므로 레코드만 있으면 그대로 시험할 수 있다.

    표 하나는 이렇게 생겼다.

        level L    CTRL_HEADER  ctrl='tbl '
        level L+1  TABLE        rows · cols
        level L+1  LIST_HEADER  col · row · span   ← 셀 하나
        level L+2  PARA_TEXT    셀 안 글
        …
        level ≤ L                                  ← 여기서 표가 끝난다

    `LIST_HEADER` 는 표 밖에서도 쓰인다(글상자 등). **표 컨트롤 안에 있을 때만** 셀로 읽는다.
    """
    out: list[str] = []
    stack: list[_Table] = []

    def sink() -> list[str]:
        """지금 글이 들어갈 자리. 표 안이면 그 셀, 아니면 본문이다."""
        if stack:
            parts = stack[-1].parts()
            if parts is not None:
                return parts
        return out

    def close_to(level: int) -> None:
        # level 이 표 컨트롤 이하로 내려오면 그 표는 끝났다. 중첩이면 부모 셀로 들어간다.
        while stack and level <= stack[-1].level:
            done = stack.pop()
            sink().append("\n" + done.render() + "\n")

    for tag, level, payload in records:
        close_to(level)

        if tag == HWPTAG_CTRL_HEADER:
            if payload[:4] == CTRL_ID_TABLE:
                stack.append(_Table(level))
        elif tag == HWPTAG_LIST_HEADER:
            # nParas(4) + listAttr(4) 다음이 셀 주소다. 실측으로 확인했다.
            if stack and level == stack[-1].level + 1 and len(payload) >= 16:
                col, row = struct.unpack_from("<HH", payload, 8)
                stack[-1].open_cell(row, col)
        elif tag == HWPTAG_PARA_TEXT:
            sink().append(_para_text(payload))
            if not stack:
                out.append("\n")

    close_to(0)
    while stack:  # level 0 짜리 표가 열린 채 끝났을 때
        out.append("\n" + stack.pop().render() + "\n")

    # 셀 안 줄바꿈은 render 가 이미 없앴다. 줄 끝 여백만 턴다.
    return re.sub(r"[ \t]+\n", "\n", "".join(out))


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
        _reject_flags(flags)

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
            chunks.append(_assemble(_iter_records(data)))
        return "\n".join(chunks)
    finally:
        ole.close()


#: HWPX 본문 토큰. **순서대로 훑어야** 문단·행·셀 경계가 제자리에 남는다.
#: 태그 접두사(`hp:`)가 다를 수 있어 느슨하게 잡는다. `t` 패턴이 `tbl`·`tr`·`tc`·`tab`
#: 을 삼키지 않는 것은 `t` 다음에 공백이나 `>` 를 요구하기 때문이다.
_HWPX_TOKEN = re.compile(
    r"<(?:\w+:)?t(?:\s[^>]*)?>(?P<text>.*?)</(?:\w+:)?t>"
    r"|(?P<tab><(?:\w+:)?tab(?:\s[^>]*)?/?>)"
    r"|(?P<para></(?:\w+:)?p>)"
    r"|(?P<cell_open><(?:\w+:)?tc(?:\s[^>]*)?>)"
    r"|(?P<cell_close></(?:\w+:)?tc>)"
    r"|(?P<row_close></(?:\w+:)?tr>)",
    re.S,
)


def from_hwpx(path: Path) -> str:
    """HWPX 는 ZIP + XML 이다. 본문은 Contents/section*.xml 의 <hp:t>.

    **문단과 표 경계를 살린다**(plan/11 T-0032). 텍스트만 이어 붙이면 9,841자 문서가
    1줄로 나와서 줄 단위 판정이 통째로 안 통한다 — 305건이 그 상태였다
    ([실측](docs/adr/evidence/2026-08-17-양식-항목-추출-실측.md) §6.1).

    규칙은 `from_docx` 와 같다. 문단은 줄바꿈, 셀은 탭, 행은 줄바꿈이다.
    다만 **셀 안의 문단은 줄을 바꾸지 않는다.** 셀 내용이 `<hp:subList>` 안의 `<hp:p>`
    라서 그대로 두면 `라벨` 과 `값` 이 다른 줄로 흩어져 행 구조가 도로 깨진다.
    """
    texts: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        if not names:
            names = [n for n in z.namelist() if n.endswith(".xml") and "section" in n.lower()]
        for n in names:
            xml = z.read(n).decode("utf-8", errors="replace")
            depth = 0  # 열려 있는 셀 수. 표가 중첩될 수 있어 불리언이 아니다.
            for m in _HWPX_TOKEN.finditer(xml):
                kind = m.lastgroup
                if kind == "text":
                    texts.append(_unescape(re.sub(r"<[^>]+>", "", m.group("text"))))
                elif kind == "tab":
                    texts.append("\t")
                elif kind == "para":
                    # 셀 안에서는 줄을 바꾸지 않는다. 행 하나가 한 줄로 남아야 한다.
                    texts.append(" " if depth else "\n")
                elif kind == "cell_open":
                    if m.group("cell_open").endswith("/>"):
                        texts.append("\t")  # 빈 셀. 열자마자 닫힌다
                    else:
                        depth += 1
                elif kind == "cell_close":
                    depth = max(0, depth - 1)
                    texts.append("\t")
                elif kind == "row_close":
                    texts.append("\n")
            texts.append("\n")
    out = "".join(texts)
    # 셀 안 문단이 남긴 공백이 탭 바로 앞에 붙는다. `기업명 \t값` 이 되면 짝이 안 보인다.
    out = re.sub(r" +(?=[\t\n])", "", out)
    # 셀을 닫을 때마다 탭이 붙어 행 끝에 하나가 남는다. **줄 끝만** 턴다 —
    # 줄 가운데의 연속된 탭은 빈 셀이고, 양식에서 그게 채울 칸이다.
    return re.sub(r"[ \t]+\n", "\n", out)


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


def pages_from_pdf(path: Path) -> list[str]:
    """쪽별 텍스트. **쪽 경계를 살려야 하는 곳이 쓴다**(plan/12 T-0043).

    `from_pdf` 는 이걸 줄바꿈으로 이어 붙인 것이다. 근거 청크에 쪽 번호를 심으려면
    이어 붙이기 **전**이 필요하다 — 붙인 뒤에는 몇 쪽이었는지 되찾을 수 없다(ADR-0014).
    """
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def from_pdf(path: Path) -> str:
    return "\n".join(pages_from_pdf(path))


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


# ─────────────────────────────────────────────────────────────────
# 사용자 파일 전용(plan/12 T-0042). 첨부는 기본으로 안 쓴다 — 그 숫자를 다시 재야 해서다.
# ─────────────────────────────────────────────────────────────────


def _cell(v: object, number_format: str = "") -> str:
    """셀 하나를 글자로. **뭉개지 않는 것이 요점이다.**

    `24100000.0` 을 그대로 두면 사람도 모델도 읽기 어렵고, 반대로 천 단위 쉼표를
    넣으면 숫자를 다시 파싱할 때 걸린다. 정수인 실수만 정수로 내린다.

    **백분율은 서식을 봐야 한다.** 엑셀은 258.5% 를 값 `2.585062240663901` 로 들고 있어서
    값만 읽으면 모델이 2.58 로 읽는다. 화면에 뜬 것과 뽑아낸 것이 달라지면 근거가 거짓이 된다.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, dt.datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (int, float)):
        if "%" in number_format:
            return f"{v * 100:.1f}%"
        if isinstance(v, float):
            return str(int(v)) if v.is_integer() else f"{v:.6g}"
        return str(v)
    return str(v).strip()


def sheets_from_xlsx(path: Path) -> list[str]:
    """시트별 텍스트. **행이 줄, 셀이 탭이다.**

    재무제표는 표 구조와 셀 좌표를 보존해야 한다. 뭉개면 `매출액 24,100,000 86,400,000` 의
    두 값이 각각 2024·2025 인지 알 수 없어져 **연도-항목-값 대응이 통째로 깨진다.**
    행을 줄로, 셀을 탭으로 두면 그 대응이 텍스트 안에 남는다.

    시트를 따로 돌려주는 이유는 청크가 시트를 넘지 않아야 하기 때문이다. 손익계산서와
    재무상태표가 한 조각에 섞이면 같은 항목명이 두 뜻을 갖는다.
    """
    from openpyxl import load_workbook

    wb = load_workbook(str(path), data_only=True, read_only=True)
    try:
        out: list[str] = []
        for ws in wb.worksheets:
            lines = [f"## {ws.title}"]
            for row in ws.iter_rows():
                cells = [_cell(c.value, c.number_format or "") for c in row]
                while cells and not cells[-1]:
                    cells.pop()  # 오른쪽 빈 칸은 버린다. 탭만 남은 줄이 생긴다
                if any(cells):
                    lines.append("\t".join(cells))
            out.append("\n".join(lines))
        return out
    finally:
        wb.close()


def from_xlsx(path: Path) -> str:
    return "\n".join(sheets_from_xlsx(path))


def slides_from_pptx(path: Path) -> list[str]:
    """슬라이드별 텍스트. 표와 발표자 노트를 포함한다.

    피치덱의 숫자는 표와 도형에 흩어져 있어 둘 중 하나만 읽으면 절반이 사라진다.
    노트까지 읽는 이유는 화면에 안 쓴 근거가 거기 적히기 때문이다.
    """
    from pptx import Presentation

    prs = Presentation(str(path))
    out: list[str] = []
    for idx, slide in enumerate(prs.slides, start=1):
        lines = [f"## 슬라이드 {idx}"]
        for shape in slide.shapes:
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    if any(cells):
                        lines.append("\t".join(cells))
            elif shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    lines.append(text)
        if slide.has_notes_slide:
            note = (slide.notes_slide.notes_text_frame.text or "").strip()
            if note:
                lines.append(f"[노트] {note}")
        out.append("\n".join(lines))
    return out


def from_pptx(path: Path) -> str:
    return "\n".join(slides_from_pptx(path))
