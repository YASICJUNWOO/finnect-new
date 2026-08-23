"""라벨 재대조 대 표 좌표 — **어느 쪽이 칸을 정확히 짚나** (plan/24 T-0152 검증).

`spike/hwp_fill.py` 는 라벨을 찾아 **옆 칸**에 넣는다. 그 방식이 틀리는 조건은
하나다: **같은 라벨이 한 파일에 여러 번 나오는 것.** 그때 어느 칸에 넣을지가
순서로 정해지고, 순서는 우리가 고른 것이 아니다.

여기서 재는 것은 셋이다.

1. 표 좌표 `(표, 행, 열)` 를 실제로 뽑을 수 있나
2. 라벨이 파일 안에서 **몇 번 겹치나**
3. 우리가 채우려는 칸 이름(`document_item.title`)이 그중 몇 개나 겹치는 라벨인가

3 번이 답을 정한다. 겹치는 라벨을 우리가 채우지 않는다면 라벨 재대조로 충분하고,
채운다면 좌표가 필요하다.

    uv run --with hwp-hwpx-editor --with jpype1 --with olefile python spike/anchor_check.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

import jpype
import jpype.imports  # noqa: F401 — 이것이 있어야 `from kr.dogfoot…` 이 걸린다

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "attachments"

#: 이 공고(kstartup:178881)의 칸 서식 둘. 사용자가 화면에서 본 그 파일이다
대상 = [
    ("f612000bb4de09f0a488b9ee8386a4aa64b9834bc84b8164574c2939bba0421a", "붙임2 신청서"),
    ("7e7784f8438e44a655148d08f22e25544927be12503fa8ce0092b26e50c65f0a", "붙임3 통합서식"),
]


def _jvm() -> None:
    if jpype.isJVMStarted():
        return
    spec = importlib.util.find_spec("hwp_hwpx_editor")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("hwp-hwpx-editor 가 없다. --with hwp-hwpx-editor 로 돌려라")
    pkg = Path(next(iter(spec.submodule_search_locations)))
    jars = sorted(pkg.rglob("*.jar"))
    if not jars:
        raise SystemExit(f"jar 를 못 찾았다: {pkg}")
    jpype.startJVM(classpath=[str(j) for j in jars])


def norm(s: str) -> str:
    """**공백을 지운다.** 관공서 양식이 `기   업   명` 처럼 자간을 벌려 칸을 맞춘다
    (ADR-0060 실측). 본문에서 어휘를 *찾는* 경우와는 반대 규칙이다."""
    return re.sub(r"[\s　:：]", "", s or "").lower()


def para_text(para) -> str:  # noqa: ANN001
    tx = para.getText()
    return str(tx.getNormalString(0)) if tx is not None else ""


def cell_text(cell) -> str:  # noqa: ANN001
    pl = cell.getParagraphList()
    parts = [para_text(pl.getParagraph(i)) for i in range(pl.getParagraphCount())]
    return " ".join(p for p in parts if p).strip()


def tables(hwp_file):  # noqa: ANN001, ANN201
    """본문의 표를 순서대로. **`spike/hwp_fill.py` 의 것과 같은 순회다** — 좌표가
    거기서 채우는 순서와 어긋나면 이 측정이 뜻을 잃는다."""
    body = hwp_file.getBodyText().getSectionList()
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


def 좌표별_셀(hwp_file) -> list[tuple[int, int, int, str]]:
    """`(표, 행, 열, 글자)` 전부. **이것이 뽑히면 좌표 방식이 성립한다.**"""
    out = []
    for ti, t in enumerate(tables(hwp_file)):
        rows = t.getRowList()
        for ri in range(rows.size()):
            cells = rows.get(ri).getCellList()
            for ci in range(cells.size()):
                out.append((ti, ri, ci, cell_text(cells.get(ci))))
    return out


def main() -> None:
    _jvm()
    from kr.dogfoot.hwplib.reader import HWPReader  # noqa: F401

    우리가_채울_이름 = {norm(x) for x in sys.argv[1:]}

    for sha, 이름 in 대상:
        path = STORE / sha[:2] / sha
        if not path.exists():
            print(f"[건너뜀] {이름} — 파일이 없다: {path}")
            continue

        f = HWPReader.fromFile(str(path))
        셀 = 좌표별_셀(f)
        라벨 = [t for *_, t in 셀 if t.strip()]
        norm_라벨 = [norm(t) for t in 라벨]
        겹침 = {k: v for k, v in Counter(norm_라벨).items() if v > 1}

        print(f"\n── {이름} ──────────────────────────────")
        print(f"표 {len({c[0] for c in 셀})} · 셀 {len(셀)} · 글자 있는 셀 {len(라벨)}")
        print(f"좌표 표본: {[(c[0], c[1], c[2], c[3][:10]) for c in 셀[:3]]}")
        print(f"**겹치는 라벨 {len(겹침)}종 / {sum(겹침.values())}칸**")
        if 겹침:
            상위 = sorted(겹침.items(), key=lambda x: -x[1])[:8]
            print(f"  많은 것: {상위}")

        if 우리가_채울_이름:
            부딪힘 = sorted(우리가_채울_이름 & set(겹침))
            print(f"우리가 채울 이름 {len(우리가_채울_이름)}개 중 **겹치는 라벨 {len(부딪힘)}개**")
            if 부딪힘:
                print(f"  → {[(b, 겹침[b]) for b in 부딪힘]}")


if __name__ == "__main__":
    main()
