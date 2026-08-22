"""테스트 코퍼스용 문서 생성기 — hwpx · docx · xlsx · pptx · pdf · jpg.

**빌드 단계가 아니다.** `tools/make-icons.py` 와 같은 성질이다 — 손으로 돌리고
**결과물을 커밋한다**(ADR-0035). 이 서버에 `libreoffice` · `pandoc` · `python-docx` ·
`reportlab` 이 전부 없어서, ZIP+XML 인 포맷은 직접 조립하고 PDF 는 TrueType 을
심어서 만든다.

**파서가 읽는 지점만 맞춘다**(`attach/hwp.py`). hwpx 는 `Contents/section0.xml` 의
`<hp:t>`, docx 는 `word/document.xml` 의 `<w:t>` 다. 나머지 XML 은 파일이 열리게
하는 최소한이고 서식을 흉내내지 않는다 — 흉내내면 고칠 곳이 늘고 읽히는 글자는
그대로다.
"""

from __future__ import annotations

import html
import struct
import zipfile
import zlib
from pathlib import Path

# --- 한글 폰트 --------------------------------------------------------------
#
# **레포 밖에 있다.** 2.7MB 를 커밋하지 않으려고 참조만 한다. 없으면 PDF 두 장을
# 못 만들고 나머지 다섯은 만들어진다.
FONT_CANDIDATES = [
    Path("/home/joonoo3/project/finnect/app/assets/fonts/pretendard/Pretendard-Regular.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]


def find_font() -> Path | None:
    return next((p for p in FONT_CANDIDATES if p.exists()), None)


# ===========================================================================
# HWPX
# ===========================================================================

_HWPX_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" version="1.4" secCnt="1">
<hh:refList><hh:fontfaces itemCnt="1"><hh:fontface lang="HANGUL" fontCnt="1">
<hh:font id="0" face="함초롬돋움" type="TTF" isEmbedded="0"/></hh:fontface></hh:fontfaces>
<hh:charProperties itemCnt="1">
<hh:charPr id="0" height="1000" textColor="#000000"/></hh:charProperties>
<hh:paraProperties itemCnt="1"><hh:paraPr id="0"/></hh:paraProperties>
</hh:refList></hh:head>"""

_HWPX_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
<odf:file-entry odf:full-path="Contents/content.hpf"
 odf:media-type="application/hwpml-package+xml"/>
<odf:file-entry odf:full-path="Contents/header.xml"
 odf:media-type="application/xml"/>
<odf:file-entry odf:full-path="Contents/section0.xml"
 odf:media-type="application/xml"/>
</odf:manifest>"""

_HWPX_CONTAINER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">
<ocf:rootfiles><ocf:rootfile ocf:full-path="Contents/content.hpf"
 ocf:media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>"""

_HWPX_HPF = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" unique-identifier="">
<opf:metadata><opf:title>참여신청서</opf:title></opf:metadata>
<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>
<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>
<opf:spine><opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>"""


def _hp_para(text: str) -> str:
    return (
        '<hp:p paraPrIDRef="0"><hp:run charPrIDRef="0">'
        f"<hp:t>{html.escape(text)}</hp:t></hp:run></hp:p>"
    )


def _hp_table(rows: list[list[str]]) -> str:
    cols = max(len(r) for r in rows)
    out = [f'<hp:p><hp:run><hp:tbl rowCnt="{len(rows)}" colCnt="{cols}">']
    for row in rows:
        out.append("<hp:tr>")
        for cell in row:
            out.append(
                '<hp:tc colSpan="1"><hp:subList>' + _hp_para(cell) + "</hp:subList></hp:tc>"
            )
        out.append("</hp:tr>")
    out.append("</hp:tbl></hp:run></hp:p>")
    return "".join(out)


def hwpx(path: Path, blocks: list[tuple[str, object]]) -> None:
    """`blocks` 는 `("p", 문장)` 이나 `("table", [[셀…]…])` 목록이다."""
    body = []
    for kind, payload in blocks:
        if kind == "p":
            body.append(_hp_para(str(payload)))
        elif kind == "table":
            body.append(_hp_table(payload))  # type: ignore[arg-type]
        else:
            raise ValueError(kind)

    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
        ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        + "".join(body)
        + "</hs:sec>"
    )
    preview = "\n".join(
        str(p) if k == "p" else "\n".join("\t".join(r) for r in p)  # type: ignore[union-attr]
        for k, p in blocks
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        # **mimetype 은 압축하지 않고 맨 앞이다.** OCF 규칙이고, 안 지키면 한글이 안 연다.
        z.writestr(
            zipfile.ZipInfo("mimetype"), "application/hwp+zip", zipfile.ZIP_STORED
        )
        z.writestr("version.xml", '<?xml version="1.0" encoding="UTF-8"?><hv:HCFVersion/>')
        z.writestr("META-INF/container.xml", _HWPX_CONTAINER)
        z.writestr("META-INF/manifest.xml", _HWPX_MANIFEST)
        z.writestr("Contents/content.hpf", _HWPX_HPF)
        z.writestr("Contents/header.xml", _HWPX_HEADER)
        z.writestr("Contents/section0.xml", section)
        z.writestr("Preview/PrvText.txt", preview)


# ===========================================================================
# DOCX
# ===========================================================================

_DOCX_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels"
 ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml"
 ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml"
 ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml"
 ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
 Target="word/document.xml"/>
<Relationship Id="rId2"
 Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
 Target="docProps/core.xml"/>
</Relationships>"""

_DOCX_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
 Target="styles.xml"/>
</Relationships>"""

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

_DOCX_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {_W}><w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕"/>
<w:sz w:val="20"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>
<w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
</w:styles>"""


def _w_para(text: str, *, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    if not text:
        return f"<w:p>{ppr}</w:p>"
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{html.escape(text)}</w:t></w:r></w:p>'


def _w_table(rows: list[list[str]]) -> str:
    out = [
        "<w:tbl><w:tblPr><w:tblBorders>"
        + "".join(
            f'<w:{e} w:val="single" w:sz="4" w:color="999999"/>'
            for e in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders></w:tblPr>"
    ]
    for row in rows:
        out.append("<w:tr>")
        for cell in row:
            out.append(
                '<w:tc><w:tcPr><w:tcW w:w="2200" w:type="dxa"/></w:tcPr>'
                + _w_para(cell)
                + "</w:tc>"
            )
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def docx(path: Path, blocks: list[tuple[str, object]], *, title: str = "") -> None:
    """`blocks` 는 `("h", 제목)` · `("p", 문장)` · `("table", 행들)` 목록이다."""
    body = []
    for kind, payload in blocks:
        if kind == "h":
            body.append(_w_para(str(payload), style="Heading1"))
        elif kind == "p":
            body.append(_w_para(str(payload)))
        elif kind == "table":
            body.append(_w_table(payload))  # type: ignore[arg-type]
            body.append(_w_para(""))  # 표 뒤에 문단이 없으면 Word 가 경고한다
        else:
            raise ValueError(kind)

    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {_W}><w:body>" + "".join(body) + "</w:body></w:document>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{html.escape(title)}</dc:title></cp:coreProperties>"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _DOCX_TYPES)
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", _DOCX_DOC_RELS)
        z.writestr("word/styles.xml", _DOCX_STYLES)
        z.writestr("docProps/core.xml", core)


# ===========================================================================
# PDF — 텍스트 레이어
# ===========================================================================
#
# `reportlab` 도 `PyMuPDF` 도 없다. TrueType 을 통째로 심고 Type0 / Identity-H 로
# 쓴다. **텍스트가 되돌아오는 근거는 `/ToUnicode` CMap 이다** — pdfminer 가 그걸
# 읽어 글리프 번호를 유니코드로 되돌린다. 없으면 글자가 안 나온다.


class TrueType:
    """`cmap`(format 4) · `hmtx` · `head` · `hhea` 만 읽는다. 서브셋은 안 한다."""

    def __init__(self, path: Path) -> None:
        self.data = path.read_bytes()
        d = self.data
        self.tables: dict[str, tuple[int, int]] = {}
        for i in range(struct.unpack(">H", d[4:6])[0]):
            off = 12 + i * 16
            tag = d[off : off + 4].decode("latin-1")
            o, ln = struct.unpack(">II", d[off + 8 : off + 16])
            self.tables[tag] = (o, ln)

        ho, _ = self.tables["head"]
        self.units = struct.unpack(">H", d[ho + 18 : ho + 20])[0]
        self.bbox = struct.unpack(">hhhh", d[ho + 36 : ho + 44])
        ao, _ = self.tables["hhea"]
        self.ascent, self.descent = struct.unpack(">hh", d[ao + 4 : ao + 8])
        self.num_hmetrics = struct.unpack(">H", d[ao + 34 : ao + 36])[0]
        self._cmap = self._read_cmap()
        self._widths: dict[int, int] = {}

    def _read_cmap(self) -> dict[int, int]:
        d = self.data
        co, _ = self.tables["cmap"]
        nt = struct.unpack(">H", d[co + 2 : co + 4])[0]
        sub = None
        for i in range(nt):
            pid, eid, so = struct.unpack(">HHI", d[co + 4 + i * 8 : co + 12 + i * 8])
            if (pid, eid) == (3, 1):
                sub = co + so
                break
        if sub is None or struct.unpack(">H", d[sub : sub + 2])[0] != 4:
            raise RuntimeError("cmap (3,1) format 4 가 없다")

        seg2 = struct.unpack(">H", d[sub + 6 : sub + 8])[0]
        seg = seg2 // 2
        base = sub + 14
        end = struct.unpack(f">{seg}H", d[base : base + seg2])
        start = struct.unpack(f">{seg}H", d[base + seg2 + 2 : base + seg2 * 2 + 2])
        delta = struct.unpack(f">{seg}h", d[base + seg2 * 2 + 2 : base + seg2 * 3 + 2])
        ro_at = base + seg2 * 3 + 2
        rng = struct.unpack(f">{seg}H", d[ro_at : ro_at + seg2])

        out: dict[int, int] = {}
        for i in range(seg):
            for c in range(start[i], min(end[i], 0xFFFF) + 1):
                if rng[i] == 0:
                    g = (c + delta[i]) & 0xFFFF
                else:
                    at = ro_at + i * 2 + rng[i] + (c - start[i]) * 2
                    if at + 2 > len(d):
                        continue
                    g = struct.unpack(">H", d[at : at + 2])[0]
                    if g:
                        g = (g + delta[i]) & 0xFFFF
                if g:
                    out[c] = g
        return out

    def gid(self, ch: str) -> int:
        return self._cmap.get(ord(ch), 0)

    def width(self, gid: int) -> int:
        """1000 단위 advance."""
        if gid not in self._widths:
            mo, _ = self.tables["hmtx"]
            i = min(gid, self.num_hmetrics - 1)
            adv = struct.unpack(">H", self.data[mo + i * 4 : mo + i * 4 + 2])[0]
            self._widths[gid] = round(adv * 1000 / self.units)
        return self._widths[gid]

    def text_width(self, text: str, size: float) -> float:
        return sum(self.width(self.gid(c)) for c in text) * size / 1000


class TextPdf:
    """쪽마다 `(크기, x, y, 문장)` 을 받아 PDF 한 벌로 낸다. A4 세로."""

    def __init__(self, font: TrueType, page: tuple[int, int] = (595, 842)) -> None:
        self.f = font
        self.page = page
        self.pages: list[list[tuple[float, float, float, str]]] = []

    def add_page(self, lines: list[tuple[float, float, float, str]]) -> None:
        self.pages.append(lines)

    def _content(self, lines) -> bytes:
        out = ["BT"]
        for size, x, y, text in lines:
            gids = "".join(f"{self.f.gid(c):04X}" for c in text)
            out.append(f"/F1 {size:g} Tf 1 0 0 1 {x:g} {y:g} Tm <{gids}> Tj")
        out.append("ET")
        return "\n".join(out).encode("latin-1")

    def _tounicode(self, used: set[str]) -> bytes:
        pairs = sorted({(self.f.gid(c), ord(c)) for c in used if self.f.gid(c)})
        head = (
            "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            "/CMapName /F1 def /CMapType 2 def\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
        )
        body = []
        # **한 블록에 100개까지다.** PDF 명세 한도이고, 넘으면 리더가 조용히 자른다.
        for i in range(0, len(pairs), 100):
            part = pairs[i : i + 100]
            body.append(f"{len(part)} beginbfchar")
            body += [f"<{g:04X}> <{u:04X}>" for g, u in part]
            body.append("endbfchar")
        tail = "endcmap CMapName currentdict /CMap defineresource pop end end"
        return (head + "\n".join(body) + "\n" + tail).encode("latin-1")

    def build(self) -> bytes:
        used = {c for pg in self.pages for _, _, _, t in pg for c in t}
        objs: list[bytes] = [b"", b""]  # 1 Catalog · 2 Pages 는 자리를 미리 잡는다

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        fz = zlib.compress(self.f.data)
        ff = add(
            b"<< /Length %d /Filter /FlateDecode /Length1 %d >>\nstream\n%s\nendstream"
            % (len(fz), len(self.f.data), fz)
        )
        sc = 1000 / self.f.units
        bb = " ".join(str(round(v * sc)) for v in self.f.bbox)
        fd = add(
            f"<< /Type /FontDescriptor /FontName /Embedded /Flags 4 /FontBBox [{bb}]"
            f" /ItalicAngle 0 /Ascent {round(self.f.ascent * sc)}"
            f" /Descent {round(self.f.descent * sc)} /CapHeight {round(self.f.ascent * sc)}"
            f" /StemV 80 /FontFile2 {ff} 0 R >>".encode("latin-1")
        )
        gids = sorted({self.f.gid(c) for c in used if self.f.gid(c)})
        warr = " ".join(f"{g} [{self.f.width(g)}]" for g in gids)
        cid = add(
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Embedded"
            f" /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
            f" /FontDescriptor {fd} 0 R /DW 1000 /W [{warr}]"
            f" /CIDToGIDMap /Identity >>".encode("latin-1")
        )
        tz = zlib.compress(self._tounicode(used))
        tu = add(
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream" % (len(tz), tz)
        )
        font = add(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /Embedded /Encoding /Identity-H"
            f" /DescendantFonts [{cid} 0 R] /ToUnicode {tu} 0 R >>".encode("latin-1")
        )

        kids = []
        for lines in self.pages:
            cz = zlib.compress(self._content(lines))
            cs = add(
                b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream"
                % (len(cz), cz)
            )
            kids.append(
                add(
                    f"<< /Type /Page /Parent 2 0 R"
                    f" /MediaBox [0 0 {self.page[0]} {self.page[1]}]"
                    f" /Resources << /Font << /F1 {font} 0 R >> >>"
                    f" /Contents {cs} 0 R >>".encode("latin-1")
                )
            )

        objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objs[1] = (
            f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}]"
            f" /Count {len(kids)} >>"
        ).encode("latin-1")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o in offsets:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objs) + 1,
            xref,
        )
        return bytes(out)


def flow(font: TrueType, lines: list[tuple[float, str]], *, page=(595, 842),
         margin=64, top=None, leading=1.7) -> TextPdf:
    """`(크기, 문장)` 목록을 쪽에 흘려 넣는다. 넘치면 쪽을 넘긴다.

    빈 문장은 빈 줄이고 **간격은 그 줄의 크기가 정한다** — `(0, "")` 을 주면
    간격이 0 이라 아무 일도 안 일어난다.

    **`size < 0` 은 쪽 나눔이다.** 자동 넘김에만 맡기면 절이 쪽 경계에서 갈리고,
    근거 청크의 쪽 번호가 내용과 안 맞게 된다(ADR-0014).
    """
    pdf = TextPdf(font, page)
    top = top if top is not None else page[1] - margin
    cur: list[tuple[float, float, float, str]] = []
    y = top
    for size, text in lines:
        if size < 0:
            if cur:
                pdf.add_page(cur)
            cur, y = [], top
            continue
        step = size * leading
        if y - step < margin:
            pdf.add_page(cur)
            cur, y = [], top
        if text:
            cur.append((size, margin, y, text))
        y -= step
    if cur:
        pdf.add_page(cur)
    return pdf


# ===========================================================================
# 이미지 — 스캔 PDF · 사진
# ===========================================================================
#
# **텍스트 레이어가 없어야 한다.** 사업자등록증은 거의 사진이고 위키의 자격 판별
# 입력 다섯 중 넷이 거기서 나온다(ADR-0030). OCR 을 끄면 `empty` 로 남는 것이
# 이 파일의 시험 내용이다 — 글자를 심으면 그 경로가 안 밟힌다.


def _render(
    lines: list[tuple[int, int, int, str]],
    font_path: Path,
    size: tuple[int, int],
    *,
    bg: int = 252,
    noise: int = 0,
    rotate: float = 0.0,
) -> object:
    """`(글자크기, x, y, 문장)` 을 흰 바탕에 그린다. PIL 이미지를 돌려준다."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", size, bg)
    draw = ImageDraw.Draw(img)
    cache: dict[int, object] = {}
    for pt, x, y, text in lines:
        if pt not in cache:
            cache[pt] = ImageFont.truetype(str(font_path), pt)
        draw.text((x, y), text, fill=40, font=cache[pt])  # type: ignore[arg-type]

    if noise:
        # 스캔본 느낌. **OCR 을 방해할 만큼 넣지 않는다** — 이 파일의 시험 대상은
        # 노이즈 내성이 아니라 "텍스트 레이어가 없을 때 OCR 이 붙나" 다.
        import random

        px = img.load()
        rnd = random.Random(0)  # 돌릴 때마다 같은 바이트가 나와야 한다
        for _ in range(noise):
            x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
            px[x, y] = max(0, min(255, px[x, y] + rnd.randint(-70, 40)))  # type: ignore[index]
    if rotate:
        img = img.rotate(rotate, expand=False, fillcolor=bg)
    return img


def scan_pdf(path: Path, lines, font_path: Path, *, size=(1240, 1754)) -> None:
    """이미지만 든 PDF. **텍스트 레이어가 0자다.**"""
    img = _render(lines, font_path, size, noise=size[0] * size[1] // 900, rotate=-0.4)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PDF", resolution=150.0)


def photo_jpg(path: Path, lines, font_path: Path, *, size=(1280, 960)) -> None:
    """사진. 간판 글자 몇 개만 읽힌다."""
    from PIL import ImageFilter

    img = _render(lines, font_path, size, bg=228, noise=size[0] * size[1] // 300)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=82)
