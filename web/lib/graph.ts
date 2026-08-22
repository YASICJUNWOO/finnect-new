/** 자유 그래프 배치. **의존성이 없고 시드가 고정이다.**
 *
 * Fruchterman-Reingold 계열의 힘 배치. `d3-force` 를 안 붙이는 이유는 목업이 적어 둔
 * 것과 같다 — 이 화면이 무엇을 지불하는지가 번들 크기로 흐려지면 안 된다. 여기서 쓰는
 * 것은 밀어내기·당기기·중심 인력 셋뿐이라 60줄이면 끝난다.
 *
 * ## `Math.random` 을 쓰지 않는다
 *
 * mulberry32 를 고정 시드로 돌린다. **ADR-0017 이 힘 배치를 거절한 이유가 「열 때마다
 * 모양이 달라진다」였고 그 반론이 여기서 사라진다** — 같은 입력에 같은 그림이 나오므로
 * 스크린샷을 바이트로 비교할 수 있다.
 *
 * ## 남는 반론은 각도 고정으로 푼다
 *
 * 시드로 안 풀리는 것이 하나 있다. **파일을 하나 더 올리면 노드가 늘고 배치가 통째로
 * 다시 잡힌다** — 「두 번째 볼 때 찾는다」가 깨진다.
 *
 * 그래서 `anchor` 가 있다. 각도를 못 박고 **반지름만 힘이 정한다.** 카테고리 열이 늘
 * 같은 방위에 서므로 지도의 방향이 유지되고, 그 안쪽은 자유롭게 뭉친다. 각도가 뜻을
 * 갖는다는 ADR-0017 의 성질이 여기서 살아남는다. */

/** 시드 PRNG. **재현되지 않는 난수를 쓰지 않는다** */
function rng(seed: number): () => number {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = t;
    r = Math.imul(r ^ (r >>> 15), r | 1);
    r ^= r + Math.imul(r ^ (r >>> 7), r | 61);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

/** 각도가 못 박힌 노드. 반지름은 힘이 정한다 */
export type Anchor = { angle: number; minRadius: number };

export type Body = {
  id: string;
  /** 그리는 반지름. 밀어내기 셈에 들어간다 — 큰 점이 더 밀어야 겹침이 준다 */
  radius: number;
  /** 중심에 못 박힌다. 허브 하나뿐이다 */
  fixed?: boolean;
  anchor?: Anchor;
};

export type Edge = { from: string; to: string; weight: number };

export type Point = { x: number; y: number };

export type Box = { x: number; y: number; width: number; height: number };

const SEED = 20260822;

/** 밀어내기가 O(n²)라 총 연산을 예산으로 묶는다. Barnes-Hut 을 안 넣는 대신이다.
 *
 * n=47 이면 상한 420틱이고 n=800 이면 60틱으로 내려온다. **틱이 줄면 덜 수렴하지
 * 결과가 틀리지는 않는다** — 힘 배치에 정답이 없다. */
function iterationsFor(n: number): number {
  return Math.max(60, Math.min(420, Math.round(3e7 / Math.max(1, n * n))));
}

/** 힘 배치를 한 번에 다 돌리고 끝낸다.
 *
 * **수렴을 애니메이션으로 보여 주지 않는다.** 예뻐 보이지만 화면이 안정되는 시점이
 * 매번 달라져 «두 번째 볼 때 찾는다» 를 다시 깨뜨린다. 도착한 그림만 보여 준다.
 *
 * ## 가둔 판과 내놓는 판이 다르다
 *
 * `width`·`height` 는 **결과를 맞출 틀**이지 계산하는 판이 아니다. 계산은 그보다
 * 넉넉한 판에서 하고 끝나면 틀에 맞춰 늘린다.
 *
 * **한 판에서 다 하면 잎이 벽에 줄지어 붙는다.** 사실 점은 밀어내기를 받기만 하고
 * 되받을 이웃이 없어서 바깥으로 나가는데, 벽이 가까우면 거기서 멈춰 서로 나란히
 * 선다 — 구조가 아니라 테두리 장식으로 읽힌다. 실제로 두 번 그렇게 됐다.
 *
 * 끝나고 늘리므로 **틀 크기가 배치의 성김에 영향을 주지 않는다.** 성김을 정하는 것은
 * `spread` 하나다.
 *
 * 입력을 건드리지 않는다 — 계산은 지역 배열에서 하고 새 `Map` 을 낸다. */
export function place(
  bodies: readonly Body[],
  edges: readonly Edge[],
  opts: { width: number; height: number; spread?: number } = { width: 1000, height: 700 },
): Map<string, Point> {
  const n = bodies.length;
  const out = new Map<string, Point>();
  if (n === 0) return out;

  const { width: TARGET_W, height: TARGET_H } = opts;
  // 계산하는 판. **틀보다 넉넉하다** — 벽이 멀어야 잎이 거기 붙지 않는다
  const W = TARGET_W * 1.5;
  const H = TARGET_H * 1.5;
  const cx = W / 2;
  const cy = H / 2;
  const rand = rng(SEED);

  const x = new Float64Array(n);
  const y = new Float64Array(n);
  const dx = new Float64Array(n);
  const dy = new Float64Array(n);
  const rad = new Float64Array(n);
  const mass = new Float64Array(n);
  const index = new Map<string, number>();

  bodies.forEach((b, i) => {
    index.set(b.id, i);
    rad[i] = b.radius;
    // **밀어내는 힘이 크기를 따른다.** 이게 없으면 잎이 전부 같은 무게로 밀려서
    // 지름 2px 짜리 사실 점이 지름 20px 짜리 자리만큼 자리를 요구하고, 되받을 이웃이
    // 없는 잎부터 판 테두리로 밀려나 줄지어 붙는다 — 실제로 그렇게 됐다
    mass[i] = 0.35 + b.radius / 10;
    if (b.fixed) {
      x[i] = cx;
      y[i] = cy;
      return;
    }
    // 원판에 고르게 뿌린다. **정사각에 뿌리면 모서리에서 밀려드는 초기 몇 틱이 낭비되고
    // 수렴한 그림도 네모나진다.** 각도가 못 박힌 노드는 제 방위에서 출발한다
    const a = b.anchor ? b.anchor.angle : rand() * Math.PI * 2;
    const r = b.anchor
      ? b.anchor.minRadius + rand() * 40
      : Math.sqrt(rand()) * Math.min(W, H) * 0.42;
    x[i] = cx + r * Math.cos(a);
    y[i] = cy + r * Math.sin(a);
  });

  const links = edges
    .map((e) => ({ a: index.get(e.from), b: index.get(e.to), w: e.weight }))
    .filter((l): l is { a: number; b: number; w: number } => l.a != null && l.b != null);

  // 성김. **끝나고 틀에 맞춰 늘리므로 절대 크기는 여기서 안 정해진다** — 이 값이
  // 정하는 것은 «간선 하나의 길이 대 밀어내는 거리» 의 비뿐이다
  const k = Math.sqrt((TARGET_W * TARGET_H) / n) * (opts.spread ?? 0.72);
  const iters = iterationsFor(n);
  let temp = Math.min(W, H) * 0.16;
  const cool = temp / (iters + 1);

  for (let step = 0; step < iters; step++) {
    dx.fill(0);
    dy.fill(0);

    // 밀어내기
    for (let a = 0; a < n; a++) {
      for (let b = a + 1; b < n; b++) {
        let ux = x[a] - x[b];
        let uy = y[a] - y[b];
        let d2 = ux * ux + uy * uy;
        if (d2 < 0.01) {
          ux = (rand() - 0.5) * 0.1;
          uy = (rand() - 0.5) * 0.1;
          d2 = 0.01;
        }
        const d = Math.sqrt(d2);
        const f = ((k * k) / d) * mass[a] * mass[b];
        dx[a] += (ux / d) * f;
        dy[a] += (uy / d) * f;
        dx[b] -= (ux / d) * f;
        dy[b] -= (uy / d) * f;
      }
    }

    // 당기기
    for (const l of links) {
      const ux = x[l.a] - x[l.b];
      const uy = y[l.a] - y[l.b];
      const d = Math.hypot(ux, uy) || 0.01;
      const f = ((d * d) / k) * l.w;
      dx[l.a] -= (ux / d) * f;
      dy[l.a] -= (uy / d) * f;
      dx[l.b] += (ux / d) * f;
      dy[l.b] += (uy / d) * f;
    }

    // 중심으로 아주 약하게. **없으면 연결 없는 덩어리가 화면 밖으로 흘러간다**
    for (let i = 0; i < n; i++) {
      dx[i] += (cx - x[i]) * 0.006;
      dy[i] += (cy - y[i]) * 0.006;
    }

    for (let i = 0; i < n; i++) {
      const body = bodies[i];
      if (body.fixed) continue;

      const len = Math.hypot(dx[i], dy[i]) || 1;
      const lim = Math.min(len, temp);
      let nx = x[i] + (dx[i] / len) * lim;
      let ny = y[i] + (dy[i] / len) * lim;

      // 각도가 못 박힌 노드는 제 반직선으로 되돌린다. **반지름만 힘이 정한다**
      if (body.anchor) {
        const r = Math.max(body.anchor.minRadius, Math.hypot(nx - cx, ny - cy));
        nx = cx + r * Math.cos(body.anchor.angle);
        ny = cy + r * Math.sin(body.anchor.angle);
      }

      const pad = rad[i] + 6;
      x[i] = Math.max(pad, Math.min(W - pad, nx));
      y[i] = Math.max(pad, Math.min(H - pad, ny));
    }
    temp -= cool;
  }

  // ── 틀에 맞춘다 ──────────────────────────────────────────
  //
  // 여기까지의 좌표는 «서로 얼마나 떨어져 있나» 만 뜻이 있고 절대 크기에는 뜻이 없다.
  // 내용 상자를 재서 틀에 꼭 맞게 늘린다 — **점 크기는 같이 안 늘린다.** 저건 담긴
  // 양을 말하는 값이라 배치 사정으로 커지면 안 된다.
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (let i = 0; i < n; i++) {
    x0 = Math.min(x0, x[i]);
    y0 = Math.min(y0, y[i]);
    x1 = Math.max(x1, x[i]);
    y1 = Math.max(y1, y[i]);
  }
  // 점 하나뿐이면 늘릴 것이 없다. 0 으로 나누지 않는다
  const scale = Math.min(
    x1 - x0 > 1 ? TARGET_W / (x1 - x0) : 1,
    y1 - y0 > 1 ? TARGET_H / (y1 - y0) : 1,
  );
  const midX = (x0 + x1) / 2;
  const midY = (y0 + y1) / 2;

  bodies.forEach((b, i) => {
    out.set(b.id, {
      x: TARGET_W / 2 + (x[i] - midX) * scale,
      y: TARGET_H / 2 + (y[i] - midY) * scale,
    });
  });
  return out;
}

export type Rect = { x0: number; y0: number; x1: number; y1: number };

/** 배치가 끝난 뒤 틀을 내용에 맞춘다. **틀을 먼저 고정하지 않는다** —
 *  힘 배치는 어디까지 퍼질지 미리 모르고, 가둬 두면 테두리에 노드가 줄지어 붙는다.
 *
 *  **점이 아니라 사각형을 받는다.** 이름표가 점보다 훨씬 넓어서, 점만 재고 여백을
 *  넉넉히 주는 식으로는 틀이 필요 이상으로 커진다 — 그러면 SVG 가 더 작게 축소되고
 *  **글자가 지정한 크기보다 작게 나온다.** 이름표 상자를 같이 재면 그 일이 없다. */
export function fit(rects: readonly Rect[], pad: number): Box {
  if (rects.length === 0) return { x: 0, y: 0, width: 100, height: 100 };

  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const r of rects) {
    x0 = Math.min(x0, r.x0);
    y0 = Math.min(y0, r.y0);
    x1 = Math.max(x1, r.x1);
    y1 = Math.max(y1, r.y1);
  }
  return {
    x: x0 - pad,
    y: y0 - pad,
    width: x1 - x0 + pad * 2,
    height: y1 - y0 + pad * 2,
  };
}

/** 부모에서 자식으로 가는 얕은 호. **직선으로 이으면 바큇살이 되고 층이 안 보인다.**
 *
 * 수직 방향으로 길이의 일정 비율만큼 휘어서 전체가 한 방향으로 감긴다 — 그 감김이
 * 그래프를 도형이 아니라 유기체로 읽히게 하는 유일한 장치다. */
export function arc(a: Point, b: Point, bend = 0.14): string {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const vx = b.x - a.x;
  const vy = b.y - a.y;
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${(mx - vy * bend).toFixed(1)} ${(
    my +
    vx * bend
  ).toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}

/** 라벨 상자가 겹치는지. **한글은 전각이라 라틴·숫자와 폭이 다르다** —
 *  `length * fontSize` 로 재면 숫자가 섞인 이름에서 상자가 과하게 커진다. */
export function labelWidth(text: string, fontSize: number): number {
  let units = 0;
  for (const ch of text) units += /[ᄀ-ᇿ㄰-㆏가-힯]/.test(ch) ? 1 : 0.56;
  return units * fontSize;
}
