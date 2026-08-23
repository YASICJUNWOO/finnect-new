"""hwpx 어댑터 — **순수 파이썬이고 덮어쓰기가 된다** (plan/24 T-0151 · ADR-0060).

`spike/hwpx_fill.py` 가 실측한 것을 제품 코드로 옮긴 것이다. 달라진 것은 **앵커가
라벨이 아니라 좌표**이고 서술 항목의 문단까지 본다는 점이다([ADR-0063](
../../../docs/adr/0063-서술-항목의-좌표를-문단으로-준다.md)).

hwp 와 갈리는 점이 둘이다.

- **JVM 이 없다.** 어디서든 돈다.
- **덮어쓸 수 있다.** ZIP + XML 이라 갈아 끼워도 무너지지 않는다(ADR-0060 실측에서
  22칸을 덮어쓰고 확인했다). hwp 는 같은 일을 하면 표가 다음 쪽으로 밀린다.

## 순회 규칙을 hwp 와 맞춘다

`doc.tables` 를 안 쓰고 **구역 → 문단 → 그 문단의 표** 순으로 센다. hwp 어댑터가
`ControlTable` 을 문단 순회로 찾는 것과 같은 순서라, 같은 양식을 두 포맷으로
받았을 때 좌표가 같은 자리를 가리킨다.

**중첩 표를 안 편다.** `docx.py` 와 같은 규칙이다 — 중첩까지 펴면 표 번호가 hwp 쪽과
어긋난다. 중첩 표에 든 칸은 좌표를 못 얻고 안 채워진다.

## `set_text` 를 쓰지 않는다

셀의 문단과 런을 버리고 새로 만들 수 있어서 글꼴·크기·정렬이 날아간다. docx 에서
`cell.text = value` 를 피한 것과 같은 자리다(ADR-0060 결정 2) — **첫 런의 글자만
바꾸고 나머지 런을 비운다.**
"""

from __future__ import annotations

from finnect.forms.base import Anchor, Cell, FormsUnavailable, Para, ParaAnchor


class HwpxForm:
    """hwpx 파일 하나. **빈 칸이 아니어도 채운다.**"""

    ext = "hwpx"

    def __init__(self, path: str) -> None:
        try:
            from hwpx.document import HwpxDocument
        except ImportError as e:
            raise FormsUnavailable(
                "hwpx 를 열려면 `uv sync --group forms` 가 필요해요"
            ) from e

        self._path = path
        self._doc = HwpxDocument.open(path)
        #: 원래 서식 → 색·기울임을 뺀 사본. **같은 것을 두 번 안 만든다**
        self._neutral: dict[str, str | None] = {}

    def _sections(self):  # noqa: ANN202
        return list(self._doc.sections)

    def _tables(self):  # noqa: ANN202
        """`(구역, 표번호, 표)` 를 순서대로.

        **표 번호가 구역 안에서 이어진다.** hwp 와 같다 — 구역을 건너 이어 세면
        구역이 둘인 문서에서 좌표가 밀린다.
        """
        for si, sec in enumerate(self._sections()):
            ti = 0
            for para in sec.paragraphs:
                for table in para.tables:
                    yield si, ti, table
                    ti += 1

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for si, ti, table in self._tables():
            for ri in range(table.row_count):
                for ci in range(table.column_count):
                    cell = _cell(table, ri, ci)
                    if cell is None:
                        continue
                    out.append(Cell(Anchor(si, ti, ri, ci), (cell.text or "").strip()))
        return out

    def paragraphs(self) -> list[Para]:
        """본문 문단을 순서대로. **표 안 문단은 안 온다** — 저기는 `cells()` 다.

        번호가 `sec.paragraphs` 의 인덱스 그대로다. 표를 건너뛰며 다시 세면 표를
        하나 더 찾거나 덜 찾는 날 좌표가 통째로 밀린다.
        """
        out: list[Para] = []
        for si, sec in enumerate(self._sections()):
            for i, para in enumerate(sec.paragraphs):
                out.append(Para(ParaAnchor(si, i), (para.text or "").strip()))
        return out

    def _cell_at(self, a: Anchor):  # noqa: ANN202
        for si, ti, table in self._tables():
            if si != a.section or ti != a.table:
                continue
            return _cell(table, a.row, a.col)
        return None

    def _para_at(self, a: ParaAnchor):  # noqa: ANN202
        secs = self._sections()
        if a.section >= len(secs):
            return None
        paras = list(secs[a.section].paragraphs)
        return paras[a.index] if a.index < len(paras) else None

    def fill(self, anchor: Anchor | ParaAnchor, value: str) -> bool:
        """**덮어쓴다.** 안내문이 들어 있어도 지우고 값을 넣는다.

        hwp 는 여기서 빈 자리만 받는다 — 갈아 끼우는 것 자체가 배치를 깨뜨려서다
        (ADR-0060 결정 3). **hwpx 에는 그 제약이 없다.**
        """
        if isinstance(anchor, ParaAnchor):
            para = self._para_at(anchor)
            if para is None:
                return False
            _write(para, value)
            self._neutralize(para)
            return True

        cell = self._cell_at(anchor)
        if cell is None:
            return False
        paras = list(cell.paragraphs)
        if not paras:
            cell.set_text(value)
            return True

        head, *rest = paras
        _write(head, value)
        for para in rest:
            for run in para.runs:
                run.text = ""
        return True

    def _neutralize(self, para) -> None:  # noqa: ANN001
        """그 문단의 **글자 모양에서 색과 기울임을 뺀다** (ADR-0063 결정 3).

        빈 문단이라고 서식이 중립인 것이 아니다. hwp 에서 겪은 것과 같은 일이
        hwpx 에도 있다 — 실측한 양식에서 서술 자리 열셋 중 하나가 `#FF0000` 을
        물고 있었다(`charPr 91`).

        ## 원본 정의를 안 건드리고 사본을 만든다

        hwp 어댑터는 `CharShape` 를 직접 고치고 **글자가 있는 문단도 쓰는 서식이면
        물러난다** — 고치면 남의 글 색이 같이 바뀌기 때문이다. 실제로 그 자리가
        하나 남았다(열셋 중 하나가 빨강으로 나갔다).

        hwpx 에는 `ensure_char_property` 가 있어서 **base 를 복제하고 색만 바꾼
        새 서식**을 만들 수 있다. 원본을 안 건드리니 물러날 이유가 없다.

        **`ensure_run_style` 은 쓰지 않는다.** `base_char_pr_id` 를 줘도 굵기와
        글꼴이 base 를 안 따라온다(실측: `74` 가 `bold=True` 인데 결과가 `False`
        였고 글꼴이 2 에서 4 로 바뀌었다).

        **굵기와 취소선은 안 건드린다.** hwp 쪽과 같은 규칙이다 — 실측이 본 것이
        색과 기울임 둘이고, 보지 않은 것을 고치면 그것이 지어낸 규칙이 된다.
        """
        for run in para.runs:
            ref = run.char_pr_id_ref
            if ref is None:
                continue
            el = self._char_pr(str(ref))
            if el is None or _neutral(el):
                continue  # 이미 검정이고 안 기울었으면 사본을 안 만든다
            new_id = self._neutral_style(str(ref))
            if new_id is not None:
                run.char_pr_id_ref = new_id

    def _neutral_style(self, ref: str) -> str | None:
        """`ref` 를 복제하고 색과 기울임만 뺀 서식의 id.

        **같은 것을 두 번 만들지 않는다** — `predicate` 가 이미 있는 것을 찾고,
        우리 캐시가 같은 base 에 대한 호출을 접는다.
        """
        if ref in self._neutral:
            return self._neutral[ref]

        base = self._char_pr(ref)
        if base is None:
            return None

        def modify(el) -> None:  # noqa: ANN001
            el.set("textColor", "#000000")
            for child in list(el):
                if child.tag.endswith("}italic"):
                    el.remove(child)

        def matches(el) -> bool:  # noqa: ANN001
            # **같은 모양이면서 중립인 것.** id 와 색·기울임을 뺀 나머지가 같아야
            # 글꼴·크기·테두리가 원래 자리의 것으로 남는다.
            if not _neutral(el):
                return False
            a = {k: v for k, v in el.attrib.items() if k not in ("id", "textColor")}
            b = {k: v for k, v in base.attrib.items() if k not in ("id", "textColor")}
            return a == b

        made = self._doc.parts.headers[0].ensure_char_property(
            predicate=matches, modifier=modify, base_char_pr_id=ref
        )
        self._neutral[ref] = made.get("id")
        return self._neutral[ref]

    def _char_pr(self, ref: str):  # noqa: ANN202
        """`header.xml` 의 `charPr` 요소. 없으면 `None`."""
        for header in self._doc.parts.headers:
            for el in header.element.iter():
                if el.tag.endswith("}charPr") and el.get("id") == ref:
                    return el
        return None

    def save(self, path: str) -> None:
        """**포맷을 안 바꾼다.** 손대지 않은 ZIP 엔트리는 바이트까지 남는다
        (ADR-0060 실측 — 바뀐 것이 `Contents/section*.xml` 뿐이었다).

        **서식을 고쳤으면 `header.xml` 도 바뀐다.** 그때는 엔트리 둘이 달라지고,
        그것이 정상이다.
        """
        self._doc.save_to_path(path)


def _neutral(el) -> bool:  # noqa: ANN001
    """검정이고 안 기울었나."""
    return (el.get("textColor") or "").upper() in ("", "#000000") and not any(
        c.tag.endswith("}italic") for c in el
    )


def _cell(table, row: int, col: int):  # noqa: ANN001, ANN202
    """병합 셀과 범위 밖을 `None` 으로 받는다.

    **예외를 삼키는 것이 아니라 없는 자리를 없다고 말하는 것이다.** 병합된 표에서
    `cell(r, c)` 가 무엇을 낼지 라이브러리가 보장하지 않아서, 좌표가 가리키는 칸이
    없으면 그 항목은 안 채워진다(`anchor` 가 NULL 인 것과 같은 결과다).
    """
    if row >= table.row_count or col >= table.column_count:
        return None
    try:
        return table.cell(row, col)
    except Exception:  # noqa: BLE001 — 병합 셀에서 나는 것이고 칸 하나를 버린다
        return None


def _write(para, value: str) -> bool:  # noqa: ANN001
    """문단 하나에 값을 넣는다. **첫 런만 갈고 나머지를 비운다.**

    런을 통째로 버리면 그 자리의 글꼴·크기·정렬이 날아간다(ADR-0060 결정 2).
    빈 문단은 런이 없으므로 새로 만든다.
    """
    runs = list(para.runs)
    if runs:
        runs[0].text = value
        for run in runs[1:]:
            run.text = ""
    else:
        para.add_run(value)
    return True
