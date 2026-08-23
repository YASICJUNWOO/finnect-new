"""hwp 어댑터 — **JVM 이 이 파일 안에만 산다** (plan/24 T-0151 · ADR-0060).

`spike/hwp_fill.py` 가 실측한 것을 제품 코드로 옮긴 것이다. 달라진 것은 **앵커가
라벨이 아니라 좌표**라는 점이고, 그 근거는 `spike/anchor_check.py` 에 있다.

## 빈 칸만 채운다

한/글로 눈으로 확인해서 정한 경계다(ADR-0060 결정 3, 판본 A~G). 이미 글자가 있는
칸을 갈아 끼우면 표가 다음 쪽으로 밀린다 — **원래와 똑같은 값을 다시 써넣어도**
밀렸으니 값도 길이도 원인이 아니라 갈아 끼우는 행위 자체다.

## 문단 리스트를 비우지 않는다

`getCharList().clear()` 가 지운 리스트에는 보이는 글자만 있는 것이 아니다. 문단 끝
문자와 개체 앵커(`HWPCharControlExtend`)가 같이 들어 있어서, 비우면 컨트롤은 남고
닻이 없어져 **한/글이 손상으로 판정한다.**

## 미리보기

`HWPFile` 이 `PrvText`·`PrvImage` 를 모델에 안 갖고 있어 저장할 때마다 사라진다.
텍스트는 본문에서 재현하고 **이미지는 포기한다** — 원본 것을 옮기면 값이 든 문서에
빈 양식 썸네일이 붙는다(ADR-0060 결정 4).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from finnect.forms.base import Anchor, Cell, FormsUnavailable, Para, ParaAnchor

#: 미리보기 텍스트 상한. hwp 규격이 정한 값이다
_PRV_LIMIT = 1023


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


class HwpForm:
    """hwp 파일 하나. **덮어쓰기를 거절한다.**"""

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
        """**빈 자리에만 넣는다.** 글자가 있으면 `False` 이고 파일을 안 건드린다.

        **빈 자리는 `getText()` 가 `None` 이다.** hwplib 은 글자가 하나도 없는 문단에
        `ParaText` 객체를 안 만든다 — 그러니 `None` 이 「채울 수 있다」는 신호이고,
        객체가 있으면 이미 무언가 적혀 있다는 뜻이라 거절한다.

        처음에 이것을 뒤집어 읽어서 **빈 칸을 전부 거절했다**. `bizinfo:PBLN_…125577`
        에서 좌표가 있고 그 자리가 비어 있는데도 채움 0 이었다.

        `createText()` 로 만들어 넣는 것은 안전하다(ADR-0060 실측 · 17번 16칸이
        그랬고 레이아웃이 원본과 같았다). **갈아 끼우는 것만 배치를 깨뜨린다.**

        **문단도 같은 규칙을 받는다.** 표 셀이 아니라 본문 문단이지만 밀림의 원인이
        「갈아 끼우는 행위」였으므로 빈 자리를 고르는 것으로 같이 피한다.
        """
        into_para = isinstance(anchor, ParaAnchor)
        para = self._para_at(anchor) if into_para else self._cell_para(anchor)
        if para is None or para.getText() is not None:
            return False

        if into_para:
            # **글자를 넣기 전에 센다.** 넣고 나서 세면 방금 채운 문단이 「글자가
            # 있는 문단」으로 잡혀서 그 서식이 보호 대상이 되고, `_neutralize` 가
            # 아무것도 안 고친다 — 빨간 기울임이 그대로 남는다.
            self._shapes_with_text()

        para.createText()
        para.getText().addString(value)
        if into_para:
            self._neutralize(para)
            # **줄 나눔 캐시를 지운다.** 빈 문단의 캐시는 「이 문단은 빈 줄 하나」라고
            # 적혀 있고, 남겨 두면 한/글이 넣은 글을 **한 줄에 다 그려서 글자가
            # 겹친다.** 판본 B(색만 고침)에서 겹쳤고 C(캐시 삭제)에서 풀렸다.
            #
            # **표 셀에는 안 한다.** 거기는 지금 그대로 정상이고(ADR-0060 실측 165칸),
            # 셀은 크기가 정해져 있어 한/글이 다시 계산한다.
            para.deleteLineSeg()
        return True

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
        복사해 붙이면 빈 양식의 글이 남는다."""
        parts: list[str] = []
        for _, _, table in self._tables():
            rows = table.getRowList()
            for ri in range(rows.size()):
                cl = rows.get(ri).getCellList()
                parts.append(
                    "".join(f"<{_cell_text(cl.get(ci))}>" for ci in range(cl.size()))
                )
        return re.sub(r"\s+", " ", "\n".join(parts))[:_PRV_LIMIT].encode("utf-16-le")

    def save(self, path: str) -> None:
        """**포맷을 안 바꾼다.** 미리보기 텍스트는 되살리고 이미지는 안 넣는다."""
        from kr.dogfoot.hwplib.writer import HWPWriter

        HWPWriter.toFile(self._file, path)
