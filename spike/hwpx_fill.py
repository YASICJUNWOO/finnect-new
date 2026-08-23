"""HWPX 양식의 표 셀을 라벨로 찾아 채운다. JVM 이 필요 없다.

hwp 쪽(`hwp_fill.py`)에서 확인된 제약이 여기에도 걸리는지 보는 것이 목적이다.
hwplib 은 기존 글자를 갈아 끼우면 한/글에서 배치가 무너져서 빈 칸만 채우기로
물러났다. HWPX 는 ZIP + XML 이고 python-hwpx 가 손대지 않은 부분의 원본 바이트를
유지한다고 하니, 덮어쓰기가 살아 있을 수 있다.

그래서 **여기서는 덮어쓰기를 막지 않고 하되 따로 센다.** 덮어쓴 칸이 있는 파일에서
레이아웃이 무너지면 hwp 와 같은 제약이 있는 것이고, 멀쩡하면 포맷이 갈린다.

실행:
    uv run --with python-hwpx python spike/hwpx_fill.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from form_values import norm, 값, 빈칸표시

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "신청서"
OUT = ROOT / "data" / "신청서-채움"


def 모든표(doc):
    """중첩 표까지 훑는다. doc.tables 는 최상위만 준다."""
    def 파고들기(t):
        yield t
        for r in range(t.row_count):
            for c in range(t.column_count):
                try:
                    for inner in t.cell(r, c).tables:
                        yield from 파고들기(inner)
                except Exception:
                    continue

    for t in doc.tables:
        yield from 파고들기(t)


def fill(doc) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """라벨 오른쪽 첫 빈 칸에 값을 넣는다. (새로 채운 것, 덮어쓴 것)."""
    새로, 덮어씀 = [], []
    본적 = set()
    for t in 모든표(doc):
        for r in range(t.row_count):
            for c in range(t.column_count):
                try:
                    라벨 = norm(t.cell(r, c).text)
                except Exception:
                    continue
                if 라벨 not in 값:
                    continue
                for cj in range(c + 1, t.column_count):
                    try:
                        옆 = t.cell(r, cj)
                        본문 = (옆.text or "").strip()
                    except Exception:
                        break
                    if norm(본문) == 라벨:  # 병합 셀이라 라벨이 반복된다
                        continue
                    if not 빈칸표시.match(본문):
                        break
                    키 = (id(옆.element), 라벨)
                    if 키 in 본적:
                        break
                    본적.add(키)
                    옆.set_text(값[라벨])
                    (덮어씀 if 본문 else 새로).append((라벨, 본문 or 값[라벨]))
                    break
    return 새로, 덮어씀


def main() -> None:
    from hwpx.document import HwpxDocument

    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC.glob("*.hwpx"))
    if not files:
        raise SystemExit(f"{SRC} 에 hwpx 가 없다")

    print(f"{'파일':<36} {'새로':>4} {'덮음':>4} {'표':>4}  검증")
    print("-" * 88)
    합_새, 합_덮 = 0, 0
    for p in files:
        doc = HwpxDocument.open(str(p))
        표수 = sum(1 for _ in 모든표(doc))
        새로, 덮어씀 = fill(doc)
        합_새 += len(새로)
        합_덮 += len(덮어씀)

        dst = OUT / p.name
        doc.save_to_path(str(dst))

        a, b = zipfile.ZipFile(p), zipfile.ZipFile(dst)
        na = {i.filename for i in a.infolist()}
        nb = {i.filename for i in b.infolist()}
        같음 = [n for n in na & nb if a.read(n) == b.read(n)]
        바뀐것 = sorted(set(na & nb) - set(같음))

        다시 = HwpxDocument.open(str(dst))
        되읽기 = sum(1 for _ in 모든표(다시)) == 표수
        엔트리 = "OK" if na == nb else f"엔트리 {len(na)}→{len(nb)}"
        본문만 = all(n.startswith("Contents/section") for n in 바뀐것)
        표시 = "OK" if (되읽기 and na == nb and (not 바뀐것 or 본문만)) else "확인 필요"
        print(
            f"{p.name[:34]:<36} {len(새로):>4} {len(덮어씀):>4} {표수:>4}  "
            f"{표시} · 바이트 동일 {len(같음)}/{len(na & nb)} · 바뀐 것 {바뀐것 or '없음'} · {엔트리}"
        )

    print(f"\n새로 채운 칸 {합_새}개 · 글자가 있던 칸에 덮어쓴 것 {합_덮}개 · 결과 {OUT}")
    if 합_덮:
        print("덮어쓴 칸이 있는 파일은 한/글에서 레이아웃을 꼭 봐야 한다 — hwp 는 여기서 무너졌다.")


if __name__ == "__main__":
    main()
