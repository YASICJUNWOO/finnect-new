"""앱 아이콘 PNG 를 만든다. **의존성 없이 손으로 래스터라이즈한다.**

DESIGN.md §12 가 정한 궤도 마크를 192·512·180 으로 낸다.

**왜 Python 이고 왜 `web/` 밖인가.** `web/` 은 의존성이 셋이다(next·react·react-dom).
아이콘 하나를 위해 `sharp` 를 넣으면 배포 번들에 네이티브 바이너리가 붙는다. 이 서버에
PIL·cairosvg·ImageMagick 이 전부 없어서 SVG 를 PNG 로 굽는 길도 없다. 남은 것이
**거리장(SDF)으로 직접 칠하고 zlib 으로 PNG 를 조립하는 것**이고, 그건 표준 라이브러리로 된다.

**PNG 를 커밋한다.** 이 스크립트는 빌드 단계가 아니다 — 마크를 고칠 때만 돌린다.
빌드에 걸면 `npm run build` 가 Python 을 요구하고, Vercel 은 그걸 안 준다(ADR-0035).

    python3 tools/make-icons.py

**기하 정본은 이 파일이고 SVG 도 여기서 낸다.** 손으로 적은 `d` 속성과 여기 상수가
갈리면 파비콘과 앱 아이콘이 다른 마크가 된다 — 좌표를 두 곳에 두지 않는다.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

# --- 색. DESIGN.md §4.1 --- #
INK = (0x16, 0x18, 0x1B)  # --ink. 바탕을 꽉 채운다 (maskable)
WHITE = (0xFF, 0xFF, 0xFF)  # --surface. 마크

# --- 기하. 512 기준이고 다른 크기는 배율만 곱한다 --- #
#
# **maskable 안전영역이 이 값들을 정한다.** OS 가 가운데 80% 만 남기고 자를 수 있어서
# (지름 0.8 · 반지름 204.8) 마크의 가장 바깥이 그 안에 있어야 한다.
# 궤도 반지름 150 + 도트 반지름 30 = 180 < 204.8.
BASE = 512
RING_R = 150.0  # 궤도 반지름
RING_W = 4.5  # 궤도 선 반폭 (선 굶기 9)
DOT_R = 30.0  # 자리 도트 반지름
CORE_R = 58.0  # 중심 반지름
SPOKE_W = 4.5  # 살 반폭
ARC_HALF = 50.0  # 호 하나가 도트 양쪽으로 뻗는 각도. 사이가 20도씩 비워진다
DOT_DEG = (-90.0, 30.0, 150.0)  # 12시 · 4시 · 8시

# 살은 중심과 도트에서 각각 이만큼 떨어져 시작하고 끝난다. 붙으면 한 덩어리로 읽힌다
SPOKE_GAP = 10.0

# 모서리 반경 비율. **`any` 와 SVG 만 쓴다** — `maskable` 은 각져야 한다(아래 `TARGETS`)
CORNER = 0.22


def _wrap(a: float) -> float:
    """각도를 -π..π 로 접는다."""
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _circle(px: float, py: float, cx: float, cy: float, r: float) -> float:
    return math.hypot(px - cx, py - cy) - r


def _capsule(px: float, py: float, ax: float, ay: float, bx: float, by: float, w: float) -> float:
    """둥근 끝 선분. 살에 쓴다."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / L2))
    return math.hypot(wx - t * vx, wy - t * vy) - w


def _round_rect(px: float, py: float, c: float, half: float, r: float) -> float:
    """둥근 정사각형. 전면 블리드용이라 중심과 반쪽 길이만 받는다."""
    qx = abs(px - c) - (half - r)
    qy = abs(py - c) - (half - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _arc(px, py, cx, cy, R: float, w: float, mid: float, half: float) -> float:
    """둥근 끝 호. `mid` 를 가운데로 양쪽 `half` 만큼 (라디안).

    각도 안이면 고리까지의 거리, 밖이면 가까운 끝점까지의 거리다 — 그래서 끝이 둥글다.
    """
    dx, dy = px - cx, py - cy
    if abs(_wrap(math.atan2(dy, dx) - mid)) <= half:
        return abs(math.hypot(dx, dy) - R) - w
    best = 1e9
    for e in (mid - half, mid + half):
        best = min(best, math.hypot(px - (cx + R * math.cos(e)), py - (cy + R * math.sin(e))) - w)
    return best


def _mark_sdf(size: int):
    """그 크기에서 '마크까지의 거리'를 주는 함수를 만든다. 음수면 마크 안이다."""
    k = size / BASE
    c = size / 2.0
    ring_r, ring_w = RING_R * k, RING_W * k
    dot_r, core_r, spoke_w = DOT_R * k, CORE_R * k, SPOKE_W * k
    gap = SPOKE_GAP * k
    half = math.radians(ARC_HALF)

    rads = [math.radians(d) for d in DOT_DEG]
    dots = [(c + ring_r * math.cos(a), c + ring_r * math.sin(a)) for a in rads]
    # 살. 중심 밖에서 시작해 도트 앞에서 멈춘다
    spokes = []
    for a in rads:
        r0, r1 = core_r + gap, ring_r - dot_r - gap
        spokes.append(
            (c + r0 * math.cos(a), c + r0 * math.sin(a), c + r1 * math.cos(a), c + r1 * math.sin(a))
        )

    def sdf(px: float, py: float) -> float:
        d = _circle(px, py, c, c, core_r)
        for dx, dy in dots:
            d = min(d, _circle(px, py, dx, dy, dot_r))
        for ax, ay, bx, by in spokes:
            d = min(d, _capsule(px, py, ax, ay, bx, by, spoke_w))
        for a in rads:
            d = min(d, _arc(px, py, c, c, ring_r, ring_w, a, half))
        return d

    return sdf


def render(size: int, rounded: bool = False) -> list[bytes]:
    """스캔라인. `rounded` 면 RGBA(모서리가 투명), 아니면 RGB(전면 블리드).

    **둘이 다른 것이 맞는 상태다.** `maskable` 과 iOS 는 OS 가 깎으니 각진 채로 줘야 하고,
    `purpose: "any"` 는 **아무도 안 깎는다** — 크롬 설치 창과 데스크톱 작업 표시줄이
    그걸 그대로 그린다. 거기에 각진 것을 주면 같은 순간 파비콘은 둥근데 앱 아이콘만
    검은 네모가 되고, 그게 DESIGN.md §12.1 이 말한 '파비콘과 앱 아이콘이 갈린다'다.
    """
    sdf = _mark_sdf(size)
    span = [WHITE[i] - INK[i] for i in range(3)]
    c = size / 2.0
    r = size * CORNER
    rows: list[bytes] = []
    for y in range(size):
        py = y + 0.5
        row = bytearray()
        for x in range(size):
            px = x + 0.5
            # 거리 1px 로 경계를 흐린다. 이게 안티에일리어싱 전부다
            a = 0.5 - sdf(px, py)
            a = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
            row += bytes((round(INK[i] + span[i] * a) for i in range(3)))
            if rounded:
                # 마크는 안전영역 안에 있어서 모서리와 안 겹친다 — 알파를 따로 매긴다
                bg = 0.5 - _round_rect(px, py, c, c, r)
                bg = 0.0 if bg < 0.0 else (1.0 if bg > 1.0 else bg)
                row += bytes((round(bg * 255),))
        rows.append(bytes(row))
    return rows


def write_png(path: Path, size: int, rows: list[bytes], alpha: bool = False) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + r for r in rows)  # 필터 0 (없음)
    # 색 타입 2 = 트루컬러, 6 = 트루컬러+알파. 둘 다 8비트
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6 if alpha else 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def svg(size: int = BASE) -> str:
    """같은 기하를 SVG 로. **브라우저는 마스크를 안 씌우니 모서리를 우리가 깎는다.**

    PNG 는 각진 사각형이다(OS 가 깎는다). 이 둘이 다른 것은 맞는 상태다.
    """
    c = size / 2.0
    rads = [math.radians(d) for d in DOT_DEG]
    half = math.radians(ARC_HALF)

    def pt(r: float, a: float) -> str:
        return f"{c + r * math.cos(a):.1f} {c + r * math.sin(a):.1f}"

    arcs = " ".join(
        f"M {pt(RING_R, a - half)} A {RING_R:g} {RING_R:g} 0 0 1 {pt(RING_R, a + half)}"
        for a in rads
    )
    spokes = "".join(
        f'\n    <line x1="{c + (CORE_R + SPOKE_GAP) * math.cos(a):.1f}"'
        f' y1="{c + (CORE_R + SPOKE_GAP) * math.sin(a):.1f}"'
        f' x2="{c + (RING_R - DOT_R - SPOKE_GAP) * math.cos(a):.1f}"'
        f' y2="{c + (RING_R - DOT_R - SPOKE_GAP) * math.sin(a):.1f}" />'
        for a in rads
    )
    dots = "".join(
        f'\n    <circle cx="{c + RING_R * math.cos(a):.1f}"'
        f' cy="{c + RING_R * math.sin(a):.1f}" r="{DOT_R:g}" />'
        for a in rads
    )
    ink = "#%02x%02x%02x" % INK
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="라스트마일">
  <!-- tools/make-icons.py 가 낸 파일이다. 손으로 고치지 않는다 — 좌표 정본이 저기다. -->
  <rect width="{size}" height="{size}" rx="{size * CORNER:.0f}" fill="{ink}" />
  <g fill="none" stroke="#fff" stroke-width="{RING_W * 2:g}" stroke-linecap="round">
    <path d="{arcs}" />{spokes}
  </g>
  <g fill="#fff">
    <circle cx="{c:g}" cy="{c:g}" r="{CORE_R:g}" />{dots}
  </g>
</svg>
"""


# (경로, 크기, 둥근가). **둥근 쪽이 `purpose: "any"`, 각진 쪽이 `maskable` 이다**
TARGETS = (
    ("web/public/icon-192.png", 192, True),
    ("web/public/icon-512.png", 512, True),
    ("web/public/icon-192-maskable.png", 192, False),
    ("web/public/icon-512-maskable.png", 512, False),
    # iOS 는 maskable 을 안 본다. 자기가 둥글게 깎으니 각진 것을 준다
    ("web/app/apple-icon.png", 180, False),
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    for rel, size, rounded in TARGETS:
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        write_png(out, size, render(size, rounded), alpha=rounded)
        kind = "둥근 · any" if rounded else "각진 · maskable"
        print(f"{rel}  {size}x{size}  {kind}  {out.stat().st_size:,} bytes")

    svg_out = root / "web/app/icon.svg"
    svg_out.write_text(svg(), encoding="utf-8")
    print(f"web/app/icon.svg  벡터  {svg_out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
