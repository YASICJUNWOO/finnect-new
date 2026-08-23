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

from finnect.forms.base import Anchor, Cell, FormsUnavailable

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

    def fill(self, anchor: Anchor, value: str) -> bool:
        """**빈 칸에만 넣는다.** 글자가 있으면 `False` 이고 파일을 안 건드린다."""
        cell = self._cell_at(anchor)
        if cell is None or _cell_text(cell).strip():
            return False

        pl = cell.getParagraphList()
        if pl.getParagraphCount() == 0:
            return False
        para = pl.getParagraph(0)
        text = para.getText()
        if text is None:
            return False

        # **글자만 더한다.** 리스트를 비우지 않는 이유가 이 파일 머리에 있다.
        for ch in value:
            text.addString(ch)
        return True

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
