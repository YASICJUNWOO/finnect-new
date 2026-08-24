"""hwp 를 **바이트로** 읽는다 — JVM 이 안 붙는다 ([ADR-0070](
../../../docs/adr/0070-hwp-를-바이트로-읽고-쓴다.md)).

`attach/hwp.py` 가 같은 레코드를 이미 읽고 있다. 저기는 **텍스트로 펴는** 일이라
좌표를 버리고, 여기는 좌표가 필요해서 조립만 다시 한다 — **레코드 층은 저기 것을
그대로 쓴다**(`iter_records` · `para_text` · `reject_flags`). 새 의존성은 0 이고
`olefile` 은 이미 기본 의존성이라 `--group forms` 없이 돈다.

## 레벨이 자리를 정한다

실측(HWP5 12건 · 레코드 10,475개)에서 이렇게 생겼다.

    level 0   PARA_HEADER    ← 최상위 문단. hwplib 의 `sec.getParagraph(i)` 다
    level 1     PARA_TEXT
    level 1     CTRL_HEADER  ctrl='tbl '   ← 최상위 표
    level 2       TABLE
    level 2       LIST_HEADER              ← 칸 하나
    level 2       PARA_HEADER              ← 칸 안 문단. LIST_HEADER 와 같은 레벨이다
    level 3         PARA_TEXT
    level 3         CTRL_HEADER  ctrl='tbl '  ← 중첩 표

**칸 안 문단이 `LIST_HEADER` 와 같은 레벨이다.** 한 단 깊을 것 같지만 아니고,
그래서 「다음 `LIST_HEADER` 까지가 이 칸」이라는 순서로만 가른다.

## 중첩 표를 센다

실측에서 표 258개 중 **57개(22%)가 중첩 표**다. `forms/hwplib.py` 의 `_tables()` 는
`sec.getParagraph(i).getControlList()` 만 봐서 그 57개를 **한 번도 못 봤다** — 칸 안
문단에 매달린 컨트롤이라 최상위 문단의 목록에 없다.

여기서는 **레코드 순서 그대로** 센다. 깊이 우선이라 표 A 안의 중첩 표가 표 B 보다
먼저 온다 — hwplib 쪽을 재귀로 고치면 같은 번호가 나온다. **두 경로의 번호가
어긋나면 폴백이 다른 칸에 쓴다.**

## 좌표는 격자다

`LIST_HEADER` 가 주소를 들고 있다. hwplib 의 옛 어댑터는 이것을 안 읽고 **그 행의
셀 리스트 인덱스**를 열로 썼다 — 가로 병합이 앞에 있으면 어긋난다(실측 36.4%).

    offset  8  <HH>  col, row
    offset 12  <HH>  colspan, rowspan
    offset 16  <ii>  width, height   HWPUNIT (1/7200 inch · /100 이면 pt)
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from finnect.attach.hwp import (
    CTRL_EXTENDED,
    CTRL_ID_TABLE,
    HWP_FLAG_COMPRESSED,
    HWPTAG_CTRL_HEADER,
    HWPTAG_LIST_HEADER,
    HWPTAG_PARA_TEXT,
    iter_records,
    para_text,
    reject_flags,
)

#: `attach/hwp.py` 에는 없다 — 텍스트만 뽑을 때는 문단 머리를 볼 일이 없어서다.
HWPTAG_PARA_HEADER = 66

#: `LIST_HEADER` 페이로드가 주소까지 들어 있으려면 이만큼은 돼야 한다.
_ADDR_BYTES = 24

#: `DocInfo` 의 문단 모양. `attach/hwp.py` 에는 없다 — 텍스트만 뽑을 때는 안 본다.
HWPTAG_PARA_SHAPE = 25

#: `PARA_HEADER.nChars` 의 최상위 비트는 개수가 아니라 **플래그다.** 지우면 안 된다.
NCHARS_FLAG = 0x80000000

#: 문단 끝 문자. 실측에서 원본 `PARA_TEXT` 146/146 이 이걸로 끝났고,
#: `nChars` 는 **글자수 + 1**(이 문자)이었다.
CR = "\r"

#: `attr1` 의 정렬 자리. 0 양쪽 · 1 왼쪽 · 2 오른쪽 · 3 가운데 · 4 배분 · 5 나눔.
ALIGN_CENTER, ALIGN_DISTRIBUTE, ALIGN_DIVIDE = 3, 4, 5

#: 빈 stored block(BFINAL=0 · LEN=0)과 마감 block. 규격 그대로라 찌꺼기가 아니다.
_EMPTY_BLOCK = b"\x00\x00\x00\xff\xff"
_FINAL_BLOCK = b"\x01\x00\x00\xff\xff"

#: 포장에 써 볼 압축 조합. 레벨 아홉 × 전략 다섯이다.
_COMBOS = tuple((lvl, st) for lvl in range(1, 10) for st in range(5))


def emit(tag: int, level: int, payload: bytes) -> bytes:
    """레코드 하나를 바이트로. **`iter_records` 의 역이다.**

    크기가 0xFFF 이상이면 헤더에 0xFFF 를 적고 뒤에 4바이트로 붙인다 — 읽는 쪽과
    같은 규칙이라, 원본이 그 형태였는지와 무관하게 다시 읽힌다.
    """
    n = len(payload)
    head = (tag & 0x3FF) | ((level & 0x3FF) << 10)
    if n < 0xFFF:
        return struct.pack("<I", head | (n << 20)) + payload
    return struct.pack("<I", head | (0xFFF << 20)) + struct.pack("<I", n) + payload


@dataclass(frozen=True, slots=True)
class Box:
    """표 안의 칸 하나. **좌표가 격자다.**"""

    section: int
    table: int
    row: int
    col: int
    colspan: int
    rowspan: int
    #: HWPUNIT. 얇은 장식 칸을 거르는 데 쓴다 — 실측에서 5.4pt 짜리가 값을 삼켰다
    width: int
    height: int
    text: str
    #: 값을 쓸 자리. 이 칸의 **첫 문단**의 `PARA_HEADER` 레코드 번호다
    para: int = -1


@dataclass(frozen=True, slots=True)
class Block:
    """표 **밖** 문단 하나. 서술 항목의 글 자리가 여기 있다."""

    section: int
    #: 그 구역 안에서 몇 번째 최상위 문단인가. **hwplib 의 `getParagraph(i)` 와 같다**
    index: int
    text: str
    para: int = -1


@dataclass(slots=True)
class Section:
    """구역 하나. **원본 스트림 크기를 들고 다닌다** — 되쓸 때 그 크기에 맞춰야 한다."""

    name: str
    raw_size: int
    data: bytes
    #: 레코드 흐름. **`edit` 이 이걸 받는다** — 되쓸 때 다시 훑지 않는다
    records: list[tuple[int, int, bytes]] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class Doc:
    """파일 하나."""

    path: str
    compressed: bool
    sections: list[Section] = field(default_factory=list)
    #: 압축 푼 `DocInfo`. 문단 모양(정렬)을 읽는 데 쓴다
    docinfo: bytes = b""

    def boxes(self) -> list[Box]:
        return [b for s in self.sections for b in s.boxes]

    def blocks(self) -> list[Block]:
        return [p for s in self.sections for p in s.blocks]


def parse_addr(payload: bytes) -> tuple[int, int, int, int, int, int] | None:
    """`LIST_HEADER` → `(col, row, colspan, rowspan, width, height)`.

    **표 칸이 아니면 `None` 이다.** `LIST_HEADER` 는 글상자·머리말에도 쓰이고
    거기는 이 자리가 주소가 아니다. 걸러 내는 값이 span 인 이유는 표 칸이면
    반드시 1 이상이어서다.
    """
    if len(payload) < _ADDR_BYTES:
        return None
    col, row, colspan, rowspan = struct.unpack_from("<HHHH", payload, 8)
    width, height = struct.unpack_from("<ii", payload, 16)
    if not (1 <= colspan <= 100 and 1 <= rowspan <= 100):
        return None
    return col, row, colspan, rowspan, width, height


@dataclass(slots=True)
class _Open:
    """열려 있는 표 하나."""

    level: int
    number: int
    cell: tuple[int, int, int, int, int, int] | None = None
    #: 그 칸의 `LIST_HEADER` 레벨. 글이 이 칸 것인지 가르는 유일한 재료다
    cell_level: int = -1
    parts: list[str] = field(default_factory=list)
    first_para: int = -1


def parse_section(data: bytes, section: int) -> tuple[list[Box], list[Block]]:
    """레코드 흐름 → 칸과 문단. **OLE 를 안 열어서 레코드만 있으면 시험할 수 있다.**

    `attach/hwp.py` 의 `_assemble` 이 같은 흐름을 텍스트로 펴는 것과 짝이다.
    """
    boxes: list[Box] = []
    blocks: list[Block] = []
    stack: list[_Open] = []
    tables = 0
    top = -1
    #: 지금 글이 쌓이는 곳. 표 안이면 그 칸, 아니면 최상위 문단
    cur_block: list[str] | None = None
    cur_para = -1

    def close_cell(t: _Open) -> None:
        if t.cell is None:
            return
        col, row, cs, rs, w, h = t.cell
        boxes.append(
            Box(section, t.number, row, col, cs, rs, w, h,
                " ".join(p for p in t.parts if p).strip(), t.first_para)
        )
        t.cell = None
        t.cell_level = -1
        t.parts = []
        t.first_para = -1

    def flush_block() -> None:
        nonlocal cur_block, cur_para
        if cur_block is not None:
            blocks.append(Block(section, top, "".join(cur_block).strip(), cur_para))
        cur_block = None
        cur_para = -1

    for i, (tag, level, payload) in enumerate(iter_records(data)):
        # **표가 끝나는 자리.** level 이 그 컨트롤 이하로 내려온 순간이다
        while stack and level <= stack[-1].level:
            close_cell(stack.pop())

        if tag == HWPTAG_CTRL_HEADER:
            if payload[:4] == CTRL_ID_TABLE:
                stack.append(_Open(level, tables))
                tables += 1
        elif tag == HWPTAG_LIST_HEADER and stack and level == stack[-1].level + 1:
            # **레벨을 같이 본다.** `LIST_HEADER` 는 글상자·머리말에도 쓰이고, 표가
            # 열린 채로 그것이 나오면 칸으로 새어 들어온다 — 실측에서 표 밖
            # `LIST_HEADER` 가 6개 있었다(`attach/hwp.py` `_assemble` 과 같은 규칙)
            addr = parse_addr(payload)
            if addr is not None:
                close_cell(stack[-1])
                stack[-1].cell = addr
                stack[-1].cell_level = level
        elif tag == HWPTAG_PARA_HEADER:
            if level == 0:
                flush_block()
                top += 1
                cur_block = []
                cur_para = i
            elif (
                stack
                and stack[-1].cell is not None
                and level == stack[-1].cell_level
                and stack[-1].first_para < 0
            ):
                stack[-1].first_para = i
        elif tag == HWPTAG_PARA_TEXT:
            txt = para_text(payload)
            if stack and stack[-1].cell is not None:
                # **레벨이 칸의 바로 아래일 때만 이 칸 글이다.** 안 보면 칸 안에
                # 들어앉은 글상자·머리말의 글이 그 칸 글로 붙는다 — 한 단 깊은
                # `LIST_HEADER` 를 칸으로 안 세고도 글은 새어 들어온다
                if level == stack[-1].cell_level + 1:
                    stack[-1].parts.append(txt.strip())
            elif not stack and cur_block is not None:
                cur_block.append(txt)

    while stack:
        close_cell(stack.pop())
    flush_block()
    return boxes, blocks


def read(path: str) -> Doc:
    """파일 하나를 읽는다. **본문을 안 바꾼다** — 바이트를 그대로 들고 있는다."""
    import olefile

    if not olefile.isOleFile(path):
        raise ValueError("OLE 파일이 아니다 (HWP 5.0 아님)")
    ole = olefile.OleFileIO(path)
    try:
        header = ole.openstream("FileHeader").read()
        if not header.startswith(b"HWP Document File"):
            raise ValueError("HWP 시그니처 없음")
        (flags,) = struct.unpack_from("<I", header, 36)
        reject_flags(flags)
        compressed = bool(flags & HWP_FLAG_COMPRESSED)

        def unpack(name: str) -> bytes:
            raw = ole.openstream(name).read()
            return zlib.decompress(raw, -15) if compressed else raw

        names = ["/".join(e) for e in ole.listdir()]
        doc = Doc(path=path, compressed=compressed)
        doc.docinfo = unpack("DocInfo") if "DocInfo" in names else b""

        # **번호순으로 읽는다.** `Section10` 이 `Section2` 앞에 오면 좌표가 밀린다
        sections = sorted(
            (n for n in names if n.startswith("BodyText/Section")),
            key=lambda n: int("".join(c for c in n.split("/")[-1] if c.isdigit()) or 0),
        )
        if not sections:
            raise ValueError("BodyText 스트림 없음")
        for si, name in enumerate(sections):
            data = unpack(name)
            sec = Section(name, len(ole.openstream(name).read()), data)
            sec.records = list(iter_records(data))
            sec.boxes, sec.blocks = parse_section(data, si)
            doc.sections.append(sec)
        return doc
    finally:
        ole.close()


def section_bytes(path: str, name: str) -> int:
    """그 스트림이 원본에서 몇 바이트인가. **되쓸 때 이 크기에 맞춰야 한다.**"""
    import olefile

    ole = olefile.OleFileIO(path)
    try:
        return len(ole.openstream(name).read())
    finally:
        ole.close()


__all__ = [
    "Block",
    "Box",
    "Doc",
    "emit",
    "HWPTAG_PARA_HEADER",
    "Section",
    "align_substitutes",
    "edit",
    "has_object_anchor",
    "pack",
    "parse_addr",
    "parse_section",
    "read",
    "write_streams",
]

# ── 쓰기 ────────────────────────────────────────────────────────────────


def has_object_anchor(payload: bytes) -> bool:
    """`PARA_TEXT` 에 개체 앵커가 매달려 있나. **있으면 손대지 않는다.**

    그림·표·글상자가 이 문단에 닻을 내리고 있으면 글을 갈아 끼울 때 그 닻이 같이
    없어지고, 컨트롤은 남아서 **한/글이 손상으로 판정한다** — hwplib 판본 B 가 안
    열린 원인이 거기였다(ADR-0060). 바이트로 써도 같은 자리다.

    **앞에서부터 훑다 처음 만나는 확장 제어문자가 답이다.** 확장형은 8워드를
    차지하지만 그 안을 들여다볼 일이 없다 — 진짜 하나를 만나는 순간 끝난다.
    글자는 전부 32 이상이라 섞일 수 없다.
    """
    n = len(payload) // 2
    if not n:
        return False
    return any(c in CTRL_EXTENDED for c in struct.unpack_from(f"<{n}H", payload, 0))


def _header_with(payload: bytes, nchars: int, shape: int | None) -> bytes:
    """문단 머리를 고쳐 쓴다. **플래그 비트를 보존한다.**"""
    h = bytearray(payload)
    (old,) = struct.unpack_from("<I", h, 0)
    struct.pack_into("<I", h, 0, (old & NCHARS_FLAG) | nchars)
    if shape is not None and len(h) >= 10:
        struct.pack_into("<H", h, 8, shape)
    return bytes(h)


def edit(
    records: list[tuple[int, int, bytes]],
    values: dict[int, str],
    align_sub: dict[int, int] | None = None,
) -> tuple[bytes, set[int], set[int]]:
    """`values = {PARA_HEADER 레코드 번호: 값}` 을 넣고 레코드 흐름을 다시 만든다.

    빈 자리면 **없던 `PARA_TEXT` 를 만들고**, 글자가 있으면 갈아 끼우고, 값이 `""`
    면 **레코드를 없앤다**(빈 문단은 `PARA_TEXT` 가 아예 없고 `nChars` 가 1 이다 —
    실측 13,104건 전부).

    반환은 `(바이트, 넣은 것, 거절한 것)` 이다. 거절은 개체 앵커가 든 문단뿐이다.
    """
    out: list[bytes] = []
    done: set[int] = set()
    refused: set[int] = set()
    i, n = 0, len(records)
    while i < n:
        tag, level, payload = records[i]
        if tag != HWPTAG_PARA_HEADER or i not in values:
            out.append(emit(tag, level, payload))
            i += 1
            continue

        text = values[i]
        nxt = records[i + 1] if i + 1 < n else None
        had_text = nxt is not None and nxt[0] == HWPTAG_PARA_TEXT
        if had_text and has_object_anchor(nxt[2]):
            refused.add(i)
            out.append(emit(tag, level, payload))
            i += 1
            continue

        shape = None
        if text and align_sub and len(payload) >= 10:
            (ps,) = struct.unpack_from("<H", payload, 8)
            shape = align_sub.get(ps)
        out.append(emit(tag, level, _header_with(payload, len(text) + 1 if text else 1, shape)))
        if text:
            out.append(
                emit(
                    HWPTAG_PARA_TEXT,
                    nxt[1] if had_text else level + 1,
                    (text + CR).encode("utf-16-le"),
                )
            )
        done.add(i)
        i += 2 if had_text else 1
    return b"".join(out), done, refused


def align_substitutes(docinfo: bytes) -> dict[int, int]:
    """배분·나눔정렬 문단모양 → **정렬 말고는 같은** 가운데정렬 문단모양.

    양식은 `매 출 액` 처럼 두 글자 라벨을 칸 폭에 맞추려고 배분정렬을 쓴다. 라벨엔
    그게 맞지만 **값에 그대로 쓰면 `h t t p s : / / n a r i n . c o . k r` 이 된다**
    (실측 · 한/글에서 확인). 같은 문단모양을 라벨 넷과 값 둘이 같이 쓰고 있어서
    모양 자체를 고치면 라벨이 뭉갠다 — **값 문단만 다른 id 로 옮긴다.**

    **첫 바이트만 다른 것을 고른다.** 거기 정렬이 들어 있고 나머지(여백·줄간격·
    테두리)는 그대로여야 한다. 없으면 안 옮긴다 — 벌어져 보이는 것이 남의 서식을
    끌어오는 것보다 낫다.
    """
    shapes = [pay for tag, _lv, pay in iter_records(docinfo) if tag == HWPTAG_PARA_SHAPE]

    def align(p: bytes) -> int:
        return (struct.unpack_from("<I", p, 0)[0] >> 2) & 0x7 if len(p) >= 4 else -1

    out: dict[int, int] = {}
    for i, p in enumerate(shapes):
        if align(p) not in (ALIGN_DISTRIBUTE, ALIGN_DIVIDE):
            continue
        for j, q in enumerate(shapes):
            if j != i and align(q) == ALIGN_CENTER and len(q) == len(p) and q[1:] == p[1:]:
                out[i] = j
                break
    return out


def pack(data: bytes, target: int) -> bytes | None:
    """정확히 `target` 바이트인 raw deflate. **못 만들면 `None` 이다.**

    `olefile` 은 CFB 를 새로 못 만들고 **같은 크기 덮어쓰기만** 된다. 그래서 채운
    본문이 원본 스트림 크기 안에 들어가야 하는데, 한/글이 낮은 압축률로 저장해서
    보통은 남는다(실측 600건 중 96.7%).

    남는 자리는 **빈 stored block 5바이트**로 메우고, 5로 안 나눠떨어지는 1~4바이트는
    압축 조합 45개를 돌려 흡수한다. 규격 그대로라 뒤에 붙은 찌꺼기가 아니다 —
    실측에서 실제 HWP 300건 중 95.0%를 정확히 맞췄다.
    """
    for lvl, strat in _COMBOS:
        co = zlib.compressobj(lvl, zlib.DEFLATED, -15, 9, strat)
        base = co.compress(data) + co.flush(zlib.Z_SYNC_FLUSH)
        slack = target - len(base) - len(_FINAL_BLOCK)
        if slack < 0 or slack % len(_EMPTY_BLOCK):
            continue
        out = base + _EMPTY_BLOCK * (slack // len(_EMPTY_BLOCK)) + _FINAL_BLOCK
        if len(out) == target and zlib.decompress(out, -15) == data:
            return out
    return None


def write_streams(src: str, out: str, blobs: dict[str, bytes]) -> None:
    """원본을 베껴 놓고 **스트림 몇 개만** 덮어쓴다.

    `BodyText/Section*` 말고는 손을 안 대는 것이 요점이다 — hwplib 이 `HWPFile`
    모델에 없는 스트림(`PrvText`·`PrvImage`·`DocOptions/_LinkDoc`)을 저장할 때마다
    버려서 따로 이식해야 했는데(ADR-0060 결정 4), **모델을 안 거치면 버릴 것이 없다.**
    """
    import shutil

    import olefile

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, out)
    ole = olefile.OleFileIO(out, write_mode=True)
    try:
        for name, blob in blobs.items():
            ole.write_stream(name, blob)
    finally:
        ole.close()
