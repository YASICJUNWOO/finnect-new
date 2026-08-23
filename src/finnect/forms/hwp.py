"""hwp 어댑터 — **JVM 이 이 파일 안에만 산다** (plan/24 T-0151 · ADR-0060).

`spike/hwp_fill.py` 가 실측한 것을 제품 코드로 옮긴 것이다. 달라진 것은 **앵커가
라벨이 아니라 좌표**라는 점이고, 그 근거는 `spike/anchor_check.py` 에 있다.

## 덮어쓰기 — 결정 3 의 문장이 한 칸 넓었다

오래 「빈 칸만 채운다」였다(ADR-0060 결정 3, 판본 A~G). 2026-08-23 **그 결정을 정한
바로 그 파일에서 덮어쓰기가 통했다**([실측](
../../../docs/adr/evidence/2026-08-23-hwp-덮어쓰기가-된다.md) · plan/24 T-0164).

    판본 C~G — 밀린다.  ParaText 를 살려 둔 채 안을 갈아 끼운다
        cl = tx.getCharList(); cl.clear(); …

    판본 I — 안 밀렸다.  ParaText 객체 자체를 없앴다 새로 만든다
        p.deleteText(); p.createText(); p.getText().addString(value)

깨뜨리는 것은 「갈아 끼우는 행위 자체」가 아니라 **「`ParaText` 를 살려 둔 채 안을
갈아 끼우는 것」**이었다. 빈 칸이 통했던 이유가 「글자가 없어서」가 아니라
**「`ParaText` 가 아예 없어서」**라면 앞뒤가 맞고, 그러면 `deleteText()` 가 그 상태를
만들어 준다 — 덮어쓰기가 「지우고 → 빈 칸에 쓰기」로 바뀐다.

**육안이 아직 두 건이다.** 결정 3 은 양식 20건과 판본 7개로 정해졌으므로 ADR 은
그 규모로 다시 재기 전에 안 뒤집는다(T-0164).

## 문단 리스트를 비우지 않는다

`getCharList().clear()` 가 지운 리스트에는 보이는 글자만 있는 것이 아니다. 문단 끝
문자와 개체 앵커(`HWPCharControlExtend`)가 같이 들어 있어서, 비우면 컨트롤은 남고
닻이 없어져 **한/글이 손상으로 판정한다.** `deleteText()` 도 같은 것을 지우므로
**개체 앵커가 든 문단은 아예 손대지 않는다** — 판본 B 가 안 열린 원인이 거기였다.

## 저장이 잃는 스트림 셋

`HWPFile` 모델에 `PrvText`·`PrvImage`·`DocOptions` 가 없어서 저장할 때마다 사라진다.
`save()` 가 POI 로 뒤에서 붙이는데 셋을 다르게 다룬다.

    PrvText              만든다   채운 값이 반영돼야 한다
    DocOptions/_LinkDoc  옮긴다   우리가 만들 재료가 없다
    PrvImage             포기한다  렌더링이 필요하고, 원본 것을 옮기면
                                  값이 든 문서에 빈 양식 썸네일이 붙는다

**`_LinkDoc` 소실은 2026-08-23 까지 아무 문서에도 없었다.** 미리보기만 보고 있어서
같이 빠지는 것을 못 봤고, 스트림 목록을 원본과 대조해서야 나왔다(ADR-0060 결정 4 는
`PrvImage` 만 말한다).
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from finnect.forms.base import Anchor, Cell, FormsUnavailable, Para, ParaAnchor

#: 미리보기 텍스트 상한. hwp 규격이 정한 값이다
_PRV_LIMIT = 1023

#: 저장하면 사라지는데 **우리가 만들 수 없어서 원본에서 옮기는** 스트림.
#:
#: `PrvText` 는 여기 없다 — 채운 값이 반영돼야 해서 `_prv_text()` 가 만든다.
#: `PrvImage` 도 없다 — 옮기면 값이 든 문서에 빈 양식 썸네일이 붙는다(ADR-0060 결정 4).
_CARRY = ("DocOptions/_LinkDoc",)


def _start_jvm() -> None:
    """**한 프로세스에 한 번이다.** JVM 은 껐다 켤 수 없다.

    실패를 `FormsUnavailable` 로 바꾸는 이유는 화면이 사용자에게 「이 서버는 hwp 를
    못 연다」와 「이 파일은 채울 수 없다」를 다르게 말해야 해서다.
    """
    try:
        import jpype
        import jpype.imports  # noqa: F401 — 있어야 `from kr.dogfoot…` 이 걸린다
    except ImportError as e:
        raise FormsUnavailable("hwp 를 열려면 `uv sync --group forms` 가 필요해요") from e

    if jpype.isJVMStarted():
        return

    spec = importlib.util.find_spec("hwp_hwpx_editor")
    if spec is None or not spec.submodule_search_locations:
        raise FormsUnavailable("hwp 라이브러리가 없어요")
    jars = sorted(Path(next(iter(spec.submodule_search_locations))).rglob("*.jar"))
    if not jars:
        raise FormsUnavailable("hwp 라이브러리의 jar 를 못 찾았어요")
    try:
        jpype.startJVM(classpath=[str(j) for j in jars])
    except Exception as e:  # noqa: BLE001 — Java 가 없으면 여기서 난다
        raise FormsUnavailable("이 서버에 Java 가 없어서 hwp 를 못 열어요") from e


def _para_text(para) -> str:  # noqa: ANN001
    tx = para.getText()
    return str(tx.getNormalString(0)) if tx is not None else ""


def _cell_text(cell) -> str:  # noqa: ANN001
    pl = cell.getParagraphList()
    parts = [_para_text(pl.getParagraph(i)) for i in range(pl.getParagraphCount())]
    return " ".join(p for p in parts if p).strip()


def _ole_read(path: str, name: str) -> bytes | None:
    """OLE 스트림 하나를 읽는다. 없으면 `None`.

    **`olefile` 을 안 쓴다.** POI 가 `hwp-hwpx-editor` 안에 이미 들어 있고
    (`poi-3.9.jar`) `_start_jvm` 이 그 jar 를 클래스패스에 넣으므로 **새 의존성이
    0 이다.** 오래 이 자리에 「olefile 을 제품 의존성으로 들여야 한다」고 적혀 있었고
    그것이 미리보기 복구를 막고 있었다.
    """
    from java.io import FileInputStream
    from org.apache.poi.poifs.filesystem import DocumentInputStream, POIFSFileSystem
    from org.apache.poi.util import IOUtils

    node = POIFSFileSystem(FileInputStream(path)).getRoot()
    parts = name.split("/")
    for p in parts[:-1]:
        if not node.hasEntry(p):
            return None
        node = node.getEntry(p)
    if not node.hasEntry(parts[-1]):
        return None
    arr = IOUtils.toByteArray(DocumentInputStream(node.getEntry(parts[-1])))
    # `byte[]` 를 부호 없는 바이트로 되돌린다. `bytes(arr)` 는 음수에서 죽는다
    return bytes(memoryview(arr).cast("B"))


def _graft(path: str, streams: dict[str, bytes]) -> None:
    """저장이 끝난 파일에 OLE 스트림을 붙인다.

    **`HWPWriter` 를 못 고쳐서 뒤에서 붙인다.** hwplib 의 `HWPFile` 모델이
    `PrvText`·`PrvImage`·`DocOptions` 를 아예 안 갖고 있어서, 저장할 때 그 스트림이
    통째로 빠진다. 모델에 없는 것은 넘길 방법이 없다.

    **임시 파일에 쓰고 옮긴다.** POI 는 읽고 있는 파일에 바로 못 쓴다.
    """
    import jpype
    from java.io import ByteArrayInputStream, FileInputStream, FileOutputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem

    fs = POIFSFileSystem(FileInputStream(path))
    root = fs.getRoot()
    for name, data in streams.items():
        parts = name.split("/")
        node = root
        for p in parts[:-1]:
            node = node.getEntry(p) if node.hasEntry(p) else node.createDirectory(p)
        if node.hasEntry(parts[-1]):
            node.getEntry(parts[-1]).delete()
        # **Java `byte` 는 부호가 있다.** 128~255 를 그대로 넘기면 넘침으로 죽는다
        signed = jpype.JArray(jpype.JByte)([b - 256 if b > 127 else b for b in data])
        node.createDocument(parts[-1], ByteArrayInputStream(signed))

    tmp = Path(path).with_suffix(".graft.tmp")
    out = FileOutputStream(str(tmp))
    try:
        fs.writeFilesystem(out)
    finally:
        out.close()
    shutil.move(str(tmp), path)


def _has_object_anchor(para) -> bool:  # noqa: ANN001
    """개체 앵커가 매달려 있나. **있으면 손대지 않는다.**

    글자 리스트에는 보이는 글자만 있는 것이 아니다. 그림·표·글상자가 이 문단에
    닻을 내리고 있으면 `deleteText()` 가 그 닻을 같이 지우고, 컨트롤은 남아서
    **한/글이 손상으로 판정한다**(판본 B).

    `Extend` 와 `Inline` 을 둘 다 본다 — 앞엣것이 개체이고 뒤엣것이 글자처럼
    자리를 차지하는 것(누름틀·각주 표시)이다.
    """
    tx = para.getText()
    if tx is None:
        return False
    cl = tx.getCharList()
    return any(
        str(cl.get(i).getClass().getSimpleName()).endswith(("Extend", "Inline"))
        for i in range(cl.size())
    )


def _first_shape(para) -> int:  # noqa: ANN001
    """그 문단의 첫 글자 모양. **지우기 전에 읽어야 한다.**"""
    cs = para.getCharShape()
    if cs is None:
        return 0
    pairs = cs.getPositonShapeIdPairList()
    return int(pairs.get(0).getShapeId()) if pairs.size() else 0


class HwpForm:
    """hwp 파일 하나. **개체 앵커가 든 자리만 거절한다.**"""

    ext = "hwp"

    def __init__(self, path: str) -> None:
        _start_jvm()
        from kr.dogfoot.hwplib.reader import HWPReader

        self._path = path
        self._file = HWPReader.fromFile(path)
        #: 글자가 있는 문단이 쓰는 글자 모양. **처음 채울 때 한 번만 센다**
        self._used: set[int] | None = None

    def _tables(self):  # noqa: ANN202
        """`(구역, 표번호, 표)` 를 순서대로.

        **표 번호가 구역 안에서 이어진다.** 구역을 건너 이어 세면 구역이 둘인
        문서에서 좌표가 밀린다.
        """
        body = self._file.getBodyText().getSectionList()
        for si in range(body.size()):
            sec = body.get(si)
            ti = 0
            for i in range(sec.getParagraphCount()):
                cl = sec.getParagraph(i).getControlList()
                if cl is None:
                    continue
                for k in range(cl.size()):
                    c = cl.get(k)
                    if str(c.getClass().getSimpleName()) == "ControlTable":
                        yield si, ti, c
                        ti += 1

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for si, ti, table in self._tables():
            rows = table.getRowList()
            for ri in range(rows.size()):
                cl = rows.get(ri).getCellList()
                for ci in range(cl.size()):
                    out.append(
                        Cell(Anchor(si, ti, ri, ci), _cell_text(cl.get(ci)))
                    )
        return out

    def paragraphs(self) -> list[Para]:
        """본문 문단을 순서대로. **표 안 문단은 안 센다** — 저기는 `cells()` 다.

        번호가 `getParagraph(i)` 의 `i` 그대로다. 표를 건너뛰며 다시 세면 표를
        하나 더 찾거나 덜 찾는 날 좌표가 통째로 밀린다.
        """
        out: list[Para] = []
        body = self._file.getBodyText().getSectionList()
        for si in range(body.size()):
            sec = body.get(si)
            for i in range(sec.getParagraphCount()):
                out.append(Para(ParaAnchor(si, i), _para_text(sec.getParagraph(i)).strip()))
        return out

    def _para_at(self, a: ParaAnchor):  # noqa: ANN202
        body = self._file.getBodyText().getSectionList()
        if a.section >= body.size():
            return None
        sec = body.get(a.section)
        return sec.getParagraph(a.index) if a.index < sec.getParagraphCount() else None

    def _cell_at(self, a: Anchor):  # noqa: ANN202
        for si, ti, table in self._tables():
            if si != a.section or ti != a.table:
                continue
            rows = table.getRowList()
            if a.row >= rows.size():
                return None
            cl = rows.get(a.row).getCellList()
            return cl.get(a.col) if a.col < cl.size() else None
        return None

    def fill(self, anchor: Anchor | ParaAnchor, value: str) -> bool:
        """그 자리에 값을 넣는다. **개체 앵커가 든 문단만 `False` 다.**

        **빈 자리는 `getText()` 가 `None` 이다.** hwplib 은 글자가 하나도 없는 문단에
        `ParaText` 객체를 안 만든다 — 그러니 `None` 은 「비어 있다」는 신호다.

        처음에 이것을 뒤집어 읽어서 **빈 칸을 전부 거절했다**. `bizinfo:PBLN_…125577`
        에서 좌표가 있고 그 자리가 비어 있는데도 채움 0 이었다.

        글자가 있으면 `_overwrite` 가 **`ParaText` 를 없앴다가 다시 만들어** 같은
        경로로 보낸다(판본 I · 위 모듈 주석). 그래서 두 길의 마지막 세 줄이 같다.

        **문단도 같은 규칙을 받는다.** 표 셀이 아니라 본문 문단이지만 밀림의 원인이
        「`ParaText` 안을 갈아 끼우는 것」이었으므로 객체를 새로 만드는 것으로 같이
        피한다.
        """
        into_para = isinstance(anchor, ParaAnchor)
        para = self._para_at(anchor) if into_para else self._cell_para(anchor)
        if para is None:
            return False

        if into_para:
            # **글자를 넣기 전에 센다.** 넣고 나서 세면 방금 채운 문단이 「글자가
            # 있는 문단」으로 잡혀서 그 서식이 보호 대상이 되고, `_neutralize` 가
            # 아무것도 안 고친다 — 빨간 기울임이 그대로 남는다.
            self._shapes_with_text()

        overwriting = para.getText() is not None
        shape = 0
        if overwriting:
            # **개체 앵커가 있으면 파일을 안 건드린다.** 지우면 컨트롤의 닻이
            # 없어져 한/글이 손상으로 본다(판본 B).
            if _has_object_anchor(para):
                return False
            shape = _first_shape(para)
            para.deleteText()

        para.createText()
        para.getText().addString(value)
        if overwriting:
            self._reshape(para, shape)
        if into_para:
            self._neutralize(para)
        if into_para or overwriting:
            # **줄 나눔 캐시를 지운다.** 캐시는 옛 글자 기준이라 남겨 두면 한/글이
            # 넣은 글을 그 자리에 그려서 **글자가 겹친다.** 판본 B(색만 고침)에서
            # 겹쳤고 C(캐시 삭제)에서 풀렸다.
            #
            # **비어 있던 표 셀에는 안 한다.** 거기는 지금 그대로 정상이고
            # (ADR-0060 실측 165칸) 셀은 크기가 정해져 있어 한/글이 다시 계산한다.
            para.deleteLineSeg()
        if overwriting:
            self._recount(para)
        return True

    def _reshape(self, para, shape: int) -> None:  # noqa: ANN001
        """**서식 위치 쌍을 하나로 되돌린다** (판본 I).

        글자를 갈면 `CharShape` 의 위치 쌍이 옛 글자 수 기준으로 남아 **문자열 밖을
        가리킨다.** 지우기 전 첫 쌍의 글자 모양을 살려 하나만 남기는 이유는 그것이
        그 칸에 원래 쓰인 서식이라서다.

        **서식을 중립으로 만들지 않는다.** 플레이스홀더가 파란 기울임이면 넣은 값도
        파란 기울임이 된다 — `_neutralize` 는 그 글자 모양을 **다른 글이 같이 쓰고
        있을 때** 남의 글 색까지 바꾸므로 글자가 있던 자리에는 못 쓴다. 대가로 남는
        것은 색이고, 사용자가 한/글에서 고칠 수 있다.
        """
        para.deleteCharShape()
        para.createCharShape()
        para.getCharShape().addParaCharShape(0, shape)

    def _recount(self, para) -> None:  # noqa: ANN001
        """문단 머리의 개수 셋을 다시 적는다. **옛 글자 수가 남으면 안 열린다.**"""
        h = para.getHeader()
        h.setCharacterCount(para.getText().getCharSize())
        h.setCharShapeCount(para.getCharShape().getPositonShapeIdPairList().size())
        h.setLineAlignCount(0)

    def _neutralize(self, para) -> None:  # noqa: ANN001
        """그 문단이 물고 있던 **글자 모양에서 색과 기울임을 뺀다.**

        빈 문단이라고 서식이 중립인 것이 아니다. 실측(`bizinfo:PBLN_…125577`)에서
        글 자리의 빈 문단이 **빨강 기울임**을 물고 있었다 — 양식 작성자가 거기에
        작성 예시를 적었다가 지운 흔적이고, 글을 넣으면 그 서식을 그대로 받는다.

            문단 16  1. 목적 및 필요성   → 검정 굵게
            문단 17  - …에 대하여 작성    → 파랑 기울임
            문단 18  (빈 문단)          → **빨강 기울임**  ← 우리가 쓰는 자리

        **글자가 있는 문단도 쓰는 서식이면 안 건드린다.** 그 경우 고치면 남의 글
        색이 같이 바뀐다. 실측한 파일에서는 그 서식을 쓰는 문단이 전부 빈 문단이라
        (글자 있는 문단 0개) 부작용이 없었다.

        **굵기와 취소선은 안 건드린다.** 실측이 본 것은 색과 기울임 둘이고,
        보지 않은 것을 고치면 그것이 지어낸 규칙이 된다.
        """
        cs = para.getCharShape()
        if cs is None:
            return
        pairs = cs.getPositonShapeIdPairList()
        used = self._shapes_with_text()
        shapes = self._file.getDocInfo().getCharShapeList()
        for i in range(pairs.size()):
            sid = int(pairs.get(i).getShapeId())
            if sid in used:
                continue
            s = shapes.get(sid)
            color = s.getCharColor()
            color.setR(0)
            color.setG(0)
            color.setB(0)
            s.getProperty().setItalic(False)

    def _shapes_with_text(self) -> set[int]:
        """**글자가 있는 문단이 쓰는 글자 모양.** 여기 있는 것은 안 고친다.

        한 번만 센다 — 항목마다 문서 전체를 훑으면 문단 수의 제곱이 된다.
        """
        if self._used is not None:
            return self._used

        used: set[int] = set()
        body = self._file.getBodyText().getSectionList()
        for si in range(body.size()):
            sec = body.get(si)
            for i in range(sec.getParagraphCount()):
                p = sec.getParagraph(i)
                if not _para_text(p).strip():
                    continue
                cs = p.getCharShape()
                if cs is None:
                    continue
                pairs = cs.getPositonShapeIdPairList()
                used.update(int(pairs.get(k).getShapeId()) for k in range(pairs.size()))
        self._used = used
        return used

    def _cell_para(self, anchor: Anchor):  # noqa: ANN202
        """그 칸의 첫 문단. 없으면 `None`."""
        cell = self._cell_at(anchor)
        if cell is None:
            return None
        pl = cell.getParagraphList()
        return pl.getParagraph(0) if pl.getParagraphCount() else None

    def _prv_text(self) -> bytes:
        """본문에서 미리보기 텍스트를 재현한다. **채운 값이 반영된다** — 원본 것을
        복사해 붙이면 빈 양식의 글이 남는다.

        **줄바꿈을 살린다.** 값이 문단마다 한 줄이고 표는 행마다 한 줄에 `<셀><셀>`
        인데, 전부 공백으로 뭉개면 목록에서 두 줄만 보여 주는 자리에 첫 표의 첫 행만
        뜬다. 상한 1,023자는 hwp 규격이 정한 것이라 뭉개도 더 담기지 않는다.

        **문단도 센다.** 표만 담으면 문서 제목이 빠지는데, 미리보기에서 가장 먼저
        읽히는 글자가 그것이다. 문단과 표를 문서 순서대로 섞는 이유도 같다.
        """
        lines: list[str] = []
        body = self._file.getBodyText().getSectionList()
        for si in range(body.size()):
            sec = body.get(si)
            for i in range(sec.getParagraphCount()):
                para = sec.getParagraph(i)
                if text := _para_text(para):
                    lines.append(text)
                cl = para.getControlList()
                if cl is None:
                    continue
                for k in range(cl.size()):
                    c = cl.get(k)
                    if str(c.getClass().getSimpleName()) != "ControlTable":
                        continue
                    rows = c.getRowList()
                    for ri in range(rows.size()):
                        cells = rows.get(ri).getCellList()
                        lines.append(
                            "".join(
                                f"<{_cell_text(cells.get(ci))}>"
                                for ci in range(cells.size())
                            )
                        )
        return "\r\n".join(lines)[:_PRV_LIMIT].encode("utf-16-le")

    def save(self, path: str) -> None:
        """**포맷을 안 바꾼다.** 저장한 뒤에 잃은 스트림을 붙인다.

        `HWPWriter` 가 본문 모델만 써서 그냥 저장하면 셋이 사라진다 —
        `PrvText` · `PrvImage` · `DocOptions/_LinkDoc` 다(실측 85,504 → 34,304 바이트).
        **본문 손실은 아니지만**(`cells()` 로 되읽으면 칸 수가 원본과 같다) 탐색기
        썸네일과 그룹웨어 미리보기가 비고, `_LinkDoc` 는 원본에 있던 문서 연결 정보를
        잃는다.

        **`PrvText` 는 만들고 `_LinkDoc` 는 옮긴다.** 앞엣것은 채운 값이 반영돼야 하고
        (원본 것을 붙이면 빈 양식의 글이 남는다) 뒤엣것은 우리가 만들 재료가 없다.
        **`PrvImage` 는 둘 다 못 한다** — 렌더링이 필요하고, 원본 것을 옮기면 값이 든
        문서에 빈 양식 썸네일이 붙는다(ADR-0060 결정 4).

        **실패를 삼키지 않는다.** 붙이다가 죽으면 예외가 그대로 올라간다 — 미리보기가
        빈 파일이 조용히 나가면 그것이 「되는 것」으로 굳고, 이 함수가 오래 그 상태였다.
        """
        from kr.dogfoot.hwplib.writer import HWPWriter

        HWPWriter.toFile(self._file, path)

        carry = {"PrvText": self._prv_text()}
        for name in _CARRY:
            if (data := _ole_read(self._path, name)) is not None:
                carry[name] = data
        _graft(path, carry)
