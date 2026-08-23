"""변환만 한다. **맞는 버전의 jar 로 띄운다.** 버리는 코드다.

`hwp_to_hwpx_probe.py` 와 갈라 둔 이유는 클래스패스가 달라서다 — 우리 배포본은
`hwplib 1.1.10` · `hwpxlib 1.0.8` 인데 `hwp2hwpx 1.1.4` 는 `hwplib 1.1.8` ·
`hwpxlib 1.1.4` 를 요구하고, 안 맞추면 그림이 든 문서에서 `ImageRect.pt0()` 로
터진다. JVM 은 프로세스당 한 번만 뜨므로 프로세스를 나눈다.

`uv run python spike/hwp2hwpx_convert.py <sha256> [sha256 …]`
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import jpype
import jpype.imports  # noqa: F401

OUT = Path("out/hwp-to-hwpx")
JARS = [
    Path("/tmp/hwp2hwpx/match/hwplib-1.1.8.jar"),
    Path("/tmp/hwp2hwpx/match/hwpxlib-1.1.4.jar"),
    Path("/tmp/hwp2hwpx/hwp2hwpx-1.1.4.jar"),
]


def _boot() -> None:
    missing = [j for j in JARS if not j.exists()]
    if missing:
        raise SystemExit(f"jar 가 없다: {missing}")
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[str(j) for j in JARS])


def patch_preview(path: Path) -> tuple[Path, bool]:
    """`container.xml` 이 선언한 `Preview/PrvText.txt` 를 실제로 넣는다."""
    with zipfile.ZipFile(path) as z:
        items = {n: z.read(n) for n in z.namelist()}
    if "Preview/PrvText.txt" in items:
        return path, False
    items["Preview/PrvText.txt"] = b""
    out = path.with_name(path.stem + "-보정.hwpx")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), items.pop("mimetype"), zipfile.ZIP_STORED)
        for n, b in items.items():
            z.writestr(n, b)
    return out, True


def main() -> None:
    from finnect.attach import store

    shas = sys.argv[1:]
    if not shas:
        raise SystemExit("sha256 을 하나 이상 달라")

    _boot()
    OUT.mkdir(parents=True, exist_ok=True)

    from kr.dogfoot.hwp2hwpx import Hwp2Hwpx
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwpxlib.writer import HWPXWriter

    ok = fail = patched = 0
    for sha in shas:
        src = str(store.abs_path(store.rel_path(sha)))
        dst = OUT / f"{sha[:12]}.hwpx"
        try:
            HWPXWriter.toFilepath(Hwp2Hwpx.toHWPX(HWPReader.fromFile(src)), str(dst))
        except Exception as e:  # noqa: BLE001 — 스파이크다
            fail += 1
            msg = str(e).split("\n")[0][:110]
            print(f"  {sha[:12]}  실패 · {type(e).__name__}: {msg}")
            continue
        final, did = patch_preview(dst)
        patched += int(did)
        ok += 1
        print(f"  {sha[:12]}  성공 · {final.stat().st_size:>9,} 바이트{'  (미리보기 보정)' if did else ''}")

    print(f"\n변환 {ok}/{ok + fail} · 미리보기 보정 {patched}건")


if __name__ == "__main__":
    main()
