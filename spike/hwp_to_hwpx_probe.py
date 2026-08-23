"""hwp → hwpx 변환이 좌표와 덮어쓰기를 살려 주는지 잰다. **버리는 코드다.**

물어보는 것 넷이다.

1. `hwp2hwpx` 가 우리 jar 조합(hwplib 1.1.10 · hwpxlib 1.0.8)에서 도는가
2. 변환된 hwpx 의 좌표가 **원본 hwp 와 같은 자리를 가리키는가**
3. 안내문이 든 칸을 덮어쓸 수 있는가 (hwp 어댑터가 거절하던 그 칸)
4. 덮어쓴 뒤에도 파일이 다시 열리고 나머지 글자가 남는가

`uv run python spike/hwp_to_hwpx_probe.py <sha256> [sha256 …]`
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
import zipfile
from pathlib import Path

import jpype
import jpype.imports  # noqa: F401

OUT = Path("out/hwp-to-hwpx")
EXTRA_JAR = Path("/tmp/hwp2hwpx/hwp2hwpx-1.1.4.jar")


def _boot() -> None:
    spec = importlib.util.find_spec("hwp_hwpx_editor")
    jars = sorted(Path(next(iter(spec.submodule_search_locations))).rglob("*.jar"))
    cp = [str(j) for j in jars]
    if EXTRA_JAR.exists():
        cp.append(str(EXTRA_JAR))
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=cp)


def convert(src: str, dst: str) -> None:
    from kr.dogfoot.hwp2hwpx import Hwp2Hwpx
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwpxlib.writer import HWPXWriter

    HWPXWriter.toFilepath(Hwp2Hwpx.toHWPX(HWPReader.fromFile(src)), dst)


def patch_preview(path: Path) -> Path:
    """`container.xml` 이 선언한 `Preview/PrvText.txt` 를 실제로 넣는다.

    hwp2hwpx 가 선언만 하고 파일을 안 만든다. OCF 검사기가 있는 리더는 전부
    여기서 거절한다.
    """
    with zipfile.ZipFile(path) as z:
        items = {n: z.read(n) for n in z.namelist()}
    if "Preview/PrvText.txt" in items:
        return path
    items["Preview/PrvText.txt"] = "".encode("utf-16-le")
    out = path.with_name(path.stem + "-보정.hwpx")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), items.pop("mimetype"), zipfile.ZIP_STORED)
        for n, b in items.items():
            z.writestr(n, b)
    return out


def adjacent_pairs(cells: list) -> list[tuple[str, object]]:
    """`label_targets` 에서 **「다음 칸이 비어 있어야」만 뺀 것.**

    덮어쓰는 포맷에서 값 자리가 어디까지 늘어나는지 재려고 만든 것이다.
    """
    from finnect.forms.base import _fold_spans

    by_row: dict[tuple[int, int, int], list] = {}
    for c in cells:
        by_row.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)
    out = []
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        run = _fold_spans(row)
        for i, c in enumerate(run[:-1]):
            if c.blank:
                continue
            out.append((c.text, run[i + 1].anchor))
    return out


def survey(path: str, ext: str) -> dict:
    from finnect.forms import label_targets, open_form

    form = open_form(path, ext)
    cells = list(form.cells())
    return {
        "form": form,
        "cells": cells,
        "tables": len({(c.anchor.section, c.anchor.table) for c in cells}),
        "cols": {
            (c.anchor.section, c.anchor.table): max(
                d.anchor.col for d in cells if (d.anchor.section, d.anchor.table) == (c.anchor.section, c.anchor.table)
            )
            + 1
            for c in cells
        },
        "blank": sum(1 for c in cells if c.blank),
        "strict": label_targets(cells),
        "loose": adjacent_pairs(cells),
        "text_at": {str(c.anchor): c.text.strip() for c in cells},
    }


def main() -> None:
    from finnect.attach import store

    shas = sys.argv[1:]
    if not shas:
        print("sha256 을 하나 이상 달라")
        return

    _boot()
    OUT.mkdir(parents=True, exist_ok=True)

    for sha in shas:
        src = str(store.abs_path(store.rel_path(sha)))
        raw = OUT / f"{sha[:12]}.hwpx"
        print(f"\n{'=' * 64}\n{sha[:12]}")

        try:
            convert(src, str(raw))
        except Exception as e:  # noqa: BLE001
            print(f"  ① 변환 실패 — {type(e).__name__}: {e}")
            continue
        print(f"  ① 변환 성공 · {raw.stat().st_size:,} 바이트")

        fixed = patch_preview(raw)
        note = " (미리보기 보정함)" if fixed != raw else ""

        try:
            before = survey(src, "hwp")
            after = survey(str(fixed), "hwpx")
        except Exception as e:  # noqa: BLE001
            print(f"  ② 어댑터로 못 열었다 — {type(e).__name__}: {e}")
            continue

        print(f"  ② 열림{note}")
        print(f"     {'':10} {'hwp':>7} {'hwpx':>7}")
        for k, lbl in [("cells", "셀"), ("tables", "표"), ("blank", "빈칸")]:
            b = len(before["cells"]) if k == "cells" else before[k]
            a = len(after["cells"]) if k == "cells" else after[k]
            print(f"     {lbl:10} {b:>7} {a:>7}")
        print(f"     {'열 수':10} {str(sorted(set(before['cols'].values()))):>7} {str(sorted(set(after['cols'].values()))):>7}")
        print(f"     {'라벨쌍(빈칸)':10} {len(before['strict']):>7} {len(after['strict']):>7}")
        print(f"     {'라벨쌍(인접)':10} {len(before['loose']):>7} {len(after['loose']):>7}")

        same = sum(1 for a, t in before["text_at"].items() if after["text_at"].get(a, "\0") == t)
        print(
            f"  ③ 좌표가 같은 글자를 가리킴 {same}/{len(before['text_at'])}"
            f" ({100 * same / max(1, len(before['text_at'])):.0f}%)"
        )

        # 안내문이 든 칸에 덮어쓴다
        targets = [
            (lbl, a)
            for lbl, a in after["loose"]
            if after["text_at"].get(str(a), "")
        ][:8]
        if not targets:
            print("  ④ 안내문 든 값 자리가 없다")
            continue

        form = after["form"]
        ok = sum(1 for lbl, a in targets if form.fill(a, f"덮어씀-{lbl[:6]}"))
        filled = OUT / f"{sha[:12]}-채움.hwpx"
        form.save(str(filled))
        print(f"  ④ 안내문 칸 덮어쓰기 {ok}/{len(targets)} · 저장 {filled.stat().st_size:,} 바이트")

        from finnect.forms import open_form

        check = open_form(str(filled), "hwpx")
        got = {str(c.anchor): c.text.strip() for c in check.cells()}
        kept = sum(1 for lbl, a in targets if got.get(str(a), "") == f"덮어씀-{lbl[:6]}")
        # 안 건드린 칸이 그대로인가
        touched = {str(a) for _, a in targets}
        intact = sum(
            1
            for k, v in after["text_at"].items()
            if k not in touched and got.get(k, "\0") == v
        )
        total = len(after["text_at"]) - len(touched)
        print(f"  ⑤ 다시 열어 확인 — 쓴 칸 {kept}/{len(targets)} · 안 건드린 칸 {intact}/{total}")


if __name__ == "__main__":
    main()
