"""hwp 덮어쓰기를 다시 시도한다 (ADR-0060 결정 3 재검토 · 판본 H~L).

## 왜 다시 하나

판본 A~G 가 전부 **기존 `ParaText` 의 `charList` 를 만졌다.** B 는 `clear()` 했고
C~G 는 일반 글자만 골라 바꿨다. 그런데 hwplib 에는 `Paragraph.deleteText()` 가 있고
**빈 칸에 쓰는 경로(`createText()` → `addString()`)는 이미 검증됐다**(판본 D · 실측
165칸). 그 둘을 잇는 조합, 곧 **문단을 빈 상태로 되돌린 뒤 검증된 경로를 태우는 것**을
아직 안 해 봤다.

빈 칸이 통하는 이유가 「글자가 없어서」가 아니라 「`ParaText` 객체가 아예 없어서」라면,
`deleteText()` 가 그 상태를 만들어 준다.

## 무엇을 재나

| 판본 | 무엇을 했나 |
|---|---|
| H | 읽고 저장만 (판본 A 재현 · 대조군) |
| I | `deleteText` → `createText` → `addString` + CharShape 리셋 + LineSeg 삭제 + 헤더 카운트 갱신 |
| J | I 에서 **헤더 카운트 갱신을 뺌** (hwplib 이 저장할 때 세는지 본다) |
| K | I 에서 **LineSeg 삭제를 뺌** |
| L | I 에서 **CharShape 리셋을 뺌** |

**개체 앵커가 든 칸은 건너뛴다.** 판본 B 가 안 열린 원인이 거기였다 — 비어 보이는 칸에
그림이 매달려 있었고, 지우니 컨트롤은 남고 닻이 없어졌다.

## 이 스크립트가 못 하는 것

**한/글 육안 확인이다.** 표가 다음 쪽으로 밀리는 것은 프로그램 검증에 안 잡힌다 —
판본 C~G 도 구조 대조는 통과했을 것이다. 결정 3 은 육안으로 정해졌고, 뒤집는 것도
육안이어야 한다. 여기서는 **열어 볼 파일을 만들고 구조만 대조한다.**

**버리는 코드다**(`spike/`).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import jpype
import jpype.imports

OUT = Path("out/hwp-덮어쓰기-판본")

#: 실측 대상. `bizinfo:PBLN_000000000125460` 신청서 — 안내문이 값 자리를 막고 있는
#: 전형이다(셀 65개 중 빈 칸이 6개뿐).
SHA = "e679598ef461124b9024e6245e3d18756f2e6df8c3a0724f9b90e51425676481"

#: 갈아 끼울 값. **실제 초안의 값이다** — 길이가 현실적이어야 밀림을 본다.
VALUES = {
    "주식회사 ○○○○": "주식회사 다시로",
    "010-1234-5678": "031-701-1234",
    "adc@xxxx.com": "contact@dasiro.co.kr",
    "000-00-00000": "501-86-33271",
}


def _boot() -> None:
    import importlib.util

    spec = importlib.util.find_spec("hwp_hwpx_editor")
    jars = sorted(Path(next(iter(spec.submodule_search_locations))).rglob("*.jar"))
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[str(j) for j in jars])


def _para_text(para) -> str:  # noqa: ANN001
    tx = para.getText()
    return str(tx.getNormalString(0)) if tx is not None else ""


def _has_extend_char(para) -> bool:  # noqa: ANN001
    """개체 앵커(그림·표)가 이 문단에 매달려 있나. **있으면 손대지 않는다.**"""
    tx = para.getText()
    if tx is None:
        return False
    cl = tx.getCharList()
    for i in range(cl.size()):
        name = str(cl.get(i).getClass().getSimpleName())
        if "Extend" in name or "Inline" in name:
            return True
    return False


def _tables(f):  # noqa: ANN001, ANN202
    body = f.getBodyText().getSectionList()
    for si in range(body.size()):
        sec = body.get(si)
        for i in range(sec.getParagraphCount()):
            cl = sec.getParagraph(i).getControlList()
            if cl is None:
                continue
            for k in range(cl.size()):
                c = cl.get(k)
                if str(c.getClass().getSimpleName()) == "ControlTable":
                    yield c


def _cell_paras(f):  # noqa: ANN001, ANN202
    for t in _tables(f):
        rows = t.getRowList()
        for ri in range(rows.size()):
            cells = rows.get(ri).getCellList()
            for ci in range(cells.size()):
                pl = cells.get(ci).getParagraphList()
                for pi in range(pl.getParagraphCount()):
                    yield pl.getParagraph(pi)


def _overwrite(para, value: str, *, header: bool, lineseg: bool, charshape: bool) -> None:  # noqa: ANN001
    """**빈 상태로 되돌린 뒤 검증된 경로를 태운다.**

    판본 C~G 와 다른 점은 `deleteText()` 다. 저쪽은 `charList` 를 만졌고 여기는
    `ParaText` 객체 자체를 없앴다가 새로 만든다.
    """
    # 원래 글자 모양 하나를 기억해 둔다. 새로 쓸 글자가 그것을 물어야 서체가 안 바뀐다
    cs = para.getCharShape()
    first_shape = int(cs.getPositonShapeIdPairList().get(0).getShapeId()) if cs else 0

    para.deleteText()
    para.createText()
    para.getText().addString(value)

    if charshape:
        # **위치 쌍을 하나로 되돌린다.** 갈아 끼운 글자 수가 원래와 달라서 옛 쌍의
        # 위치가 문자열 밖을 가리킬 수 있다
        para.deleteCharShape()
        para.createCharShape()
        para.getCharShape().addParaCharShape(0, first_shape)

    if lineseg:
        # 줄 나눔 캐시는 옛 글자 기준이다. 남기면 한/글이 그대로 그린다
        para.deleteLineSeg()

    if header:
        h = para.getHeader()
        h.setCharacterCount(para.getText().getCharSize())
        h.setCharShapeCount(
            para.getCharShape().getPositonShapeIdPairList().size()
            if para.getCharShape()
            else 0
        )
        h.setLineAlignCount(0 if lineseg else h.getLineAlignCount())


def _overwrite_old(para, value: str) -> None:  # noqa: ANN001
    """**판본 C 재현 — 대조군이다.** `charList` 에서 일반 글자만 골라 바꾼다.

    제어 문자와 개체 앵커를 지키면서 글자만 교체하는 옛 방식이다. 이것이 밀렸다는
    것이 ADR-0060 결정 3 이고, **새 판본이 안 밀린다면 이것과 나란히 열어 봐야
    차이가 보인다.**
    """
    tx = para.getText()
    cl = tx.getCharList()
    keep = []
    for i in range(cl.size()):
        c = cl.get(i)
        if str(c.getClass().getSimpleName()) != "HWPCharNormal":
            keep.append(c)
    cl.clear()
    for ch in value:
        tx.addNewNormalChar().setCode(ord(ch))
    for c in keep:
        cl.add(c)


def _make(tag: str, *, fill: bool, old: bool = False, **flags: bool) -> tuple[str, int]:
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwplib.writer import HWPWriter

    from finnect.attach import store

    f = HWPReader.fromFile(str(store.abs_path(store.rel_path(SHA))))
    n = 0
    if fill:
        for para in _cell_paras(f):
            text = _para_text(para).strip()
            if text not in VALUES or _has_extend_char(para):
                continue
            if old:
                _overwrite_old(para, VALUES[text])
                if flags.get("lineseg"):
                    para.deleteLineSeg()  # 판본 G 재현
            else:
                _overwrite(para, VALUES[text], **flags)
            n += 1

    out = OUT / f"{tag}.hwp"
    HWPWriter.toFile(f, str(out))
    return str(out), n


def _verify(path: str) -> str:
    """다시 읽어 구조를 센다. **밀림은 여기서 안 잡힌다.**"""
    from kr.dogfoot.hwplib.reader import HWPReader

    try:
        f = HWPReader.fromFile(path)
    except Exception as e:  # noqa: BLE001
        return f"다시 못 읽음: {type(e).__name__}"
    body = f.getBodyText().getSectionList()
    paras = sum(body.get(i).getParagraphCount() for i in range(body.size()))
    tables = sum(1 for _ in _tables(f))
    cells = sum(1 for _ in _cell_paras(f))
    hit = sum(1 for p in _cell_paras(f) if _para_text(p).strip() in VALUES.values())
    return f"문단 {paras} · 표 {tables} · 셀문단 {cells} · 갈아낀 값 {hit}"


def main() -> None:
    _boot()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    plans = [
        ("H-읽고저장만", {"fill": False}),
        ("C-옛방식-대조군", {"fill": True, "old": True}),
        ("G-옛방식+라인세그삭제", {"fill": True, "old": True, "lineseg": True}),
        ("I-전부", {"fill": True, "header": True, "lineseg": True, "charshape": True}),
        ("J-헤더갱신뺌", {"fill": True, "header": False, "lineseg": True, "charshape": True}),
        ("K-라인세그뺌", {"fill": True, "header": True, "lineseg": False, "charshape": True}),
        ("L-글자모양뺌", {"fill": True, "header": True, "lineseg": True, "charshape": False}),
    ]

    print(f"기준 파일: {SHA[:12]} (bizinfo:PBLN_000000000125460 신청서)")
    print(f"갈아 끼울 칸: {len(VALUES)}종\n")
    for tag, flags in plans:
        try:
            path, n = _make(tag, **flags)
        except Exception as e:  # noqa: BLE001
            print(f"{tag:16} 만들다 실패: {type(e).__name__}: {e}")
            continue
        size = Path(path).stat().st_size
        print(f"{tag:16} 갈아낀 칸 {n:2} · {size:,}바이트 · {_verify(path)}")

    print(f"\n판본이 {OUT} 에 있다. **한/글로 열어 봐야 한다** — 표가 다음 쪽으로")
    print("밀리는 것은 위 구조 대조에 안 잡힌다(판본 C~G 도 구조는 멀쩡했다).")


if __name__ == "__main__":
    sys.exit(main())
