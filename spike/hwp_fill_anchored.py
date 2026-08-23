"""hwp 양식을 **좌표로** 채운다. 덮어쓰기·체크 표시·여러 문단 칸까지 한다.

[ADR-0060](../docs/adr/0060-양식을-채워서-원본-포맷으로-돌려준다.md) 결정 3 이
「hwp 는 빈 칸만 채운다」로 막아 둔 자리를 다시 연 것이고, 실측 기록은
[2026-08-23 hwp 덮어쓰기가 된다](../docs/adr/evidence/2026-08-23-hwp-덮어쓰기가-된다.md)
에 있다. `spike/hwp_overwrite_retry.py` 의 **판본 I** 를 좌표 지정 방식으로 세운 것이다.

`spike/hwp_fill.py` 와 갈리는 점이 넷이다.

1. **라벨을 안 찾고 좌표를 직접 든다.** 안내문이 붙은 양식에서 라벨 대조가 안 걸린다
   (ADR-0060 결정 6). 눈으로 확인한 양식이라면 `(표, 행, 열)` 이 빠르다
2. **글자가 있는 칸을 덮어쓴다.** `charList` 를 만지지 않고 `ParaText` 를 없앴다
   새로 만든다 — 그것이 판본 C~G 와 갈리는 유일한 지점이다
3. **한 칸의 문단 여럿을 다룬다.** 가이드 문구가 여러 줄이면 첫 문단만 갈아서는
   안내가 아래에 남는다
4. **체크박스를 표시한다.** `□` 가 개체가 아니라 글자라 문자열 치환으로 된다.
   셀을 통째로 덮으면 라벨이 같이 지워지므로 **문단 안 부분 치환**을 한다

**버리는 코드다**(`spike/`). 아래 값 표는 테스트 페르소나 `c_narin`(주식회사
나린데이터)을 손으로 옮긴 예시이고, 좌표는 2026 현대모비스 CSV 오픈 이노베이션
신청서의 것이다. **다른 양식에 돌리려면 좌표부터 다시 잡아야 한다** — `--dump` 가
그 일을 한다.

실행:
    uv run --with hwp-hwpx-editor --with jpype1 --with olefile \
      python spike/hwp_fill_anchored.py --dump <원본.hwp>
    uv run --with hwp-hwpx-editor --with jpype1 --with olefile \
      python spike/hwp_fill_anchored.py <원본.hwp> <결과.hwp>
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import jpype
import jpype.imports  # noqa: F401
import olefile

# ── 채울 값 ────────────────────────────────────────────────────────────────
#: `(표, 행, 열)` → 값. 첫 문단에 쓰고 그 칸의 나머지 문단은 비운다.
CELLS: dict[tuple[int, int, int], str] = {
    (1, 1, 1): "주식회사 나린데이터",
    (1, 1, 3): "105-88-21734",
    (1, 2, 1): "2026. 05. 26.",
    (1, 2, 3): "110111-9204418",
    (1, 3, 1): "정보통신업 · 데이터베이스 및 온라인정보 제공업",
    (1, 4, 1): "서울특별시 성동구 아차산로17길 48, 4층",
    (1, 5, 1): "조민서",
    (1, 5, 6): "hello@narindata.example",
    (1, 6, 1): "조민서",
    (1, 6, 2): "대표이사",
    (1, 8, 2): "해당 없음 (2026년 6월 설립으로 출원 이력 없음)",
    (3, 2, 1): "주식회사 나린데이터",
    (3, 2, 3): "조민서",
    (5, 5, 1): "해당 없음",
    (5, 7, 1): "해당 없음",
}

#: 문단마다 다른 값을 넣는 칸. `(표, 행, 열)` → 문단별 값.
#: **양식이 한 칸에서 여러 가지를 묻는 자리다** — 한 문단에 몰아넣으면 어느 질문에
#: 답한 것인지 읽는 사람이 갈라야 한다. 값이 문단 수보다 적으면 남은 문단은 비운다.
CELL_PARAS: dict[tuple[int, int, int], list[str]] = {
    (6, 6, 0): [
        "대기업·공공기관·지자체와 진행한 협업 이력은 없습니다.",
        "제품이 소프트웨어 서비스라 생산·양산 인프라는 보유하고 있지 않습니다.",
    ],
}

#: 칸 안 **문단 하나**를 부분 치환하는 자리. `(표, 행, 열, 문단)` → (찾을 것, 바꿀 것).
#: 체크박스와 서명 날짜가 여기 온다 — 라벨을 남겨야 해서 통째로 못 덮는다.
PARAS: dict[tuple[int, int, int, int], tuple[str, str]] = {
    (3, 1, 0, 0): ("2026년  08월  00일", "2026년  08월  23일"),
    (2, 1, 3, 0): ("□ 스마트 기술", "☑ 스마트 기술"),
    (2, 2, 1, 0): ("□ 미해당", "☑ 미해당"),
    (5, 4, 1, 0): ("□ 없음", "☑ 없음"),
    (5, 6, 1, 0): ("□ 없음", "☑ 없음"),
}


def _boot() -> None:
    spec = importlib.util.find_spec("hwp_hwpx_editor")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("hwp-hwpx-editor 가 없다. --with hwp-hwpx-editor 로 돌려라")
    jars = sorted(Path(next(iter(spec.submodule_search_locations))).rglob("*.jar"))
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[str(j) for j in jars])


def para_text(p) -> str:  # noqa: ANN001
    tx = p.getText()
    return str(tx.getNormalString(0)) if tx is not None else ""


def has_object_anchor(p) -> bool:  # noqa: ANN001
    """개체 앵커가 매달린 문단인가. **있으면 손대지 않는다.**

    지우면 컨트롤은 남고 닻이 없어져 한/글이 손상으로 판정한다(판본 B).
    **`HWPCharControlChar` 는 앵커가 아니다** — 문단 끝 문자라 거의 모든 문단에
    있고, 이것까지 피하면 손댈 수 있는 문단이 거의 없어진다.
    """
    tx = p.getText()
    if tx is None:
        return False
    cl = tx.getCharList()
    return any(
        "Extend" in str(cl.get(i).getClass().getSimpleName())
        or "Inline" in str(cl.get(i).getClass().getSimpleName())
        for i in range(cl.size())
    )


def tables(f):  # noqa: ANN001, ANN202
    """구역 → 문단 → `ControlTable` 순. **이 순회 순서가 표 번호를 정한다.**"""
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


def cell_at(f, ti: int, ri: int, ci: int):  # noqa: ANN001, ANN202
    for i, t in enumerate(tables(f)):
        if i != ti:
            continue
        rows = t.getRowList()
        if ri >= rows.size():
            return None
        cells = rows.get(ri).getCellList()
        return cells.get(ci) if ci < cells.size() else None
    return None


def _reset(p, value: str) -> None:  # noqa: ANN001
    """**판본 I.** `charList` 를 만지지 않고 `ParaText` 를 없앴다 새로 만든다.

    빈 칸이 통했던 이유가 「글자가 없어서」가 아니라 **「`ParaText` 가 아예
    없어서」**라는 가설 위에 서 있다. `deleteText()` 가 그 상태를 만들어 주므로
    덮어쓰기가 「지우고 → 빈 칸에 쓰기」가 되고, 그 뒤는 판본 D 가 165칸에서
    검증한 경로다.

    **글자 0개짜리 `ParaText` 를 만들지 않는다.** 원본의 빈 문단은 `ParaText` 가
    아예 없는 것이지 비어 있는 것이 아니다. 만들면 `CharShape` 의 위치 0 쌍이
    문자열 밖을 가리켜 저장이 `IndexOutOfBoundsException` 으로 죽는다. 지우는
    자리에는 공백 한 칸을 넣는다.
    """
    cs = p.getCharShape()
    first = int(cs.getPositonShapeIdPairList().get(0).getShapeId()) if cs else 0

    p.deleteText()
    p.createText()
    p.getText().addString(value or " ")

    # 위치 쌍을 하나로 되돌린다. 글자 수가 달라져 옛 쌍이 문자열 밖을 가리킬 수 있다
    p.deleteCharShape()
    p.createCharShape()
    p.getCharShape().addParaCharShape(0, first)

    # 줄 나눔 캐시는 옛 글자 기준이다. 남기면 한/글이 그대로 그린다
    p.deleteLineSeg()

    h = p.getHeader()
    h.setCharacterCount(p.getText().getCharSize())
    h.setCharShapeCount(p.getCharShape().getPositonShapeIdPairList().size())
    h.setLineAlignCount(0)


def write_para(p, value: str) -> str:  # noqa: ANN001
    if p.getText() is None:
        if value:
            p.createText()
            p.getText().addString(value)
        return "새로"
    _reset(p, value)
    return "덮어"


def fill_cell(cell, value: str) -> tuple[str, int]:  # noqa: ANN001
    """첫 문단에 값을 쓰고 **나머지 문단을 비운다.**

    가이드 문구가 문단 여럿에 걸쳐 있어서, 첫 문단만 갈면 안내가 아래에 남는다.
    """
    pl = cell.getParagraphList()
    how = write_para(pl.getParagraph(0), value)
    cleared = 0
    for i in range(1, pl.getParagraphCount()):
        p = pl.getParagraph(i)
        if has_object_anchor(p) or p.getText() is None:
            continue
        _reset(p, "")
        cleared += 1
    return how, cleared


def fill_cell_paras(cell, values: list[str]) -> int:  # noqa: ANN001
    pl = cell.getParagraphList()
    n = pl.getParagraphCount()
    if len(values) > n:
        raise SystemExit(f"문단이 {n}개인데 값이 {len(values)}개다")
    for i in range(n):
        p = pl.getParagraph(i)
        if has_object_anchor(p):
            continue
        write_para(p, values[i] if i < len(values) else "")
    return n


def build_prvtext(f, limit: int = 1023) -> bytes:  # noqa: ANN001
    """한/글이 만드는 미리보기 텍스트를 본문에서 재현한다(ADR-0060 결정 4).

    **`PrvImage` 는 만들 수 없다.** 렌더링이 필요하고, 원본 것을 옮기면 값이 든
    문서에 빈 양식 썸네일이 붙는다.
    """
    lines: list[str] = []
    body = f.getBodyText().getSectionList()
    for si in range(body.size()):
        sec = body.get(si)
        for i in range(sec.getParagraphCount()):
            p = sec.getParagraph(i)
            if (t := para_text(p)):
                lines.append(t)
            cl = p.getControlList()
            if cl is None:
                continue
            for k in range(cl.size()):
                c = cl.get(k)
                if str(c.getClass().getSimpleName()) != "ControlTable":
                    continue
                rows = c.getRowList()
                for ri in range(rows.size()):
                    cells = rows.get(ri).getCellList()
                    parts = []
                    for ci in range(cells.size()):
                        pl = cells.get(ci).getParagraphList()
                        txt = " ".join(
                            filter(
                                None,
                                (para_text(pl.getParagraph(x)) for x in range(pl.getParagraphCount())),
                            )
                        ).strip()
                        parts.append(f"<{txt}>")
                    lines.append("".join(parts))
    return "\r\n".join(lines)[:limit].encode("utf-16-le")


def graft(target: Path, streams: dict[str, bytes]) -> None:
    """저장이 끝난 HWP 에 OLE 스트림을 붙인다. hwplib 이 모델에 안 갖고 있는 것들이다."""
    from java.io import ByteArrayInputStream, FileInputStream, FileOutputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem

    fs = POIFSFileSystem(FileInputStream(str(target)))
    root = fs.getRoot()
    for name, data in streams.items():
        parts = name.split("/")
        node = root
        for p in parts[:-1]:
            node = node.getEntry(p) if node.hasEntry(p) else node.createDirectory(p)
        if node.hasEntry(parts[-1]):
            node.getEntry(parts[-1]).delete()
        signed = [b - 256 if b > 127 else b for b in data]
        node.createDocument(parts[-1], ByteArrayInputStream(jpype.JArray(jpype.JByte)(signed)))
    tmp = target.with_suffix(".tmp")
    out = FileOutputStream(str(tmp))
    fs.writeFilesystem(out)
    out.close()
    shutil.move(tmp, target)


def stats(f) -> dict:  # noqa: ANN001
    """되읽어 대조할 것. **밀림은 여기서 안 잡힌다** — 판본 C~G 도 구조는 멀쩡했다."""
    di = f.getDocInfo()
    n_table = n_cell = n_para = 0
    body = f.getBodyText().getSectionList()
    for si in range(body.size()):
        n_para += body.get(si).getParagraphCount()
    for t in tables(f):
        n_table += 1
        rows = t.getRowList()
        for ri in range(rows.size()):
            n_cell += rows.get(ri).getCellList().size()
    return {
        "문단": n_para,
        "표": n_table,
        "셀": n_cell,
        "서식": (
            di.getCharShapeList().size(),
            di.getParaShapeList().size(),
            di.getStyleList().size(),
            di.getBorderFillList().size(),
        ),
    }


def dump(path: str) -> None:
    """좌표를 잡는 데 쓴다. **빈 칸·앵커·문단 수를 같이 낸다.**"""
    from kr.dogfoot.hwplib.reader import HWPReader

    f = HWPReader.fromFile(path)
    for ti, t in enumerate(tables(f)):
        rows = t.getRowList()
        print(f"\n=== 표{ti} · 행 {rows.size()} ===")
        for ri in range(rows.size()):
            cells = rows.get(ri).getCellList()
            for ci in range(cells.size()):
                pl = cells.get(ci).getParagraphList()
                n = pl.getParagraphCount()
                p0 = pl.getParagraph(0)
                mark = "빈칸" if p0.getText() is None else ("앵커" if has_object_anchor(p0) else "글자")
                txt = " ".join(
                    filter(None, (para_text(pl.getParagraph(x)) for x in range(n)))
                ).strip()
                print(f"  [{ri},{ci}] {mark} 문단{n} | {txt[:70]!r}")
                if n > 1:
                    for pi in range(n):
                        print(f"        p{pi} | {para_text(pl.getParagraph(pi))[:66]!r}")


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--dump":
        _boot()
        dump(sys.argv[2])
        return
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)

    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    _boot()
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwplib.writer import HWPWriter

    f = HWPReader.fromFile(str(src))
    before = stats(f)
    done = 0

    for (ti, ri, ci), value in CELLS.items():
        cell = cell_at(f, ti, ri, ci)
        if cell is None:
            print(f"표{ti}[{ri},{ci}] 없는 좌표")
            continue
        old = para_text(cell.getParagraphList().getParagraph(0))
        how, _ = fill_cell(cell, value)
        done += 1
        print(f"표{ti}[{ri},{ci}] {how} {value[:44]!r} ← {old[:24]!r}")

    for (ti, ri, ci), values in CELL_PARAS.items():
        cell = cell_at(f, ti, ri, ci)
        if cell is None:
            print(f"표{ti}[{ri},{ci}] 없는 좌표")
            continue
        n = fill_cell_paras(cell, values)
        done += 1
        print(f"표{ti}[{ri},{ci}] 문단{n} 에 값 {len(values)}개")

    for (ti, ri, ci, pi), (find, repl) in PARAS.items():
        cell = cell_at(f, ti, ri, ci)
        if cell is None:
            print(f"표{ti}[{ri},{ci}] 없는 좌표")
            continue
        p = cell.getParagraphList().getParagraph(pi)
        old = para_text(p)
        if find not in old:
            print(f"표{ti}[{ri},{ci}]p{pi} 못 찾음: {find!r} · 실제 {old[:40]!r}")
            continue
        write_para(p, old.replace(find, repl))
        done += 1
        print(f"표{ti}[{ri},{ci}]p{pi} 덮어 {repl[:40]!r}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    HWPWriter.toFile(f, str(dst))

    keep: dict[str, bytes] = {}
    o = olefile.OleFileIO(str(src))
    have = {"/".join(s) for s in o.listdir()}
    if "DocOptions/_LinkDoc" in have:
        keep["DocOptions/_LinkDoc"] = o.openstream("DocOptions/_LinkDoc").read()
    o.close()
    keep["PrvText"] = build_prvtext(HWPReader.fromFile(str(dst)))
    graft(dst, keep)

    after = stats(HWPReader.fromFile(str(dst)))
    same = all(before[k] == after[k] for k in ("문단", "표", "셀", "서식"))
    print(f"\n채운 자리 {done}개 · 구조 {'같음' if same else '다름'}")
    print(f"{before} → {after}")
    print(f"용량 {src.stat().st_size:,} → {dst.stat().st_size:,} 바이트 (PrvImage 가 빠진다)")
    print(f"\n{dst}\n**한/글로 열어 봐야 한다** — 표가 밀리는 것은 위 대조에 안 잡힌다.")


if __name__ == "__main__":
    main()
