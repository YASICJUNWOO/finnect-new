/* 공유 기하. **여기가 정본이다.**
 *
 * 시안이 다르게 가져도 되는 것은 「어느 배치를 고르는가」이지 배치 코드 자체가 아니다.
 * 같은 배치를 두 시안이 각자 구현하면 미세한 차이가 시안의 차이로 오독된다.
 *
 * ── 셋이 있다 ──────────────────────────────────────────────
 *   orbit(...)   자리 고정. ADR-0017 이 정한 것 — 중심 1 · 안쪽 5 · 바깥 9
 *   force(...)   힘 배치. **시드가 고정이라 열 때마다 같다**
 *   radial(...)  허브 하나 + 방사
 *
 * **ADR-0017 이 힘 배치를 거절한 이유는 "열 때마다 모양이 달라진다"였다.** 그 반론은
 * 시드를 고정하면 사라진다 — 같은 입력에 같은 그림이 나온다. 남는 반론은 「두 번째 볼
 * 때 찾는다」이고 그건 시드로 안 풀린다. 파일을 하나 더 올리면 노드가 늘고 배치가
 * 통째로 다시 잡히기 때문이다. 그 대가를 시안이 지는 것이고 README 에 적는다. */

window.Layout = (function () {
  /* 시드 PRNG(mulberry32). **Math.random 을 쓰지 않는다** — 스크린샷을 바이트로
   * 비교할 수 없게 되고, 그러면 시안 비교가 눈대중으로 떨어진다 */
  function rng(seed) {
    var t = seed >>> 0;
    return function () {
      t += 0x6d2b79f5;
      var r = t;
      r = Math.imul(r ^ (r >>> 15), r | 1);
      r ^= r + Math.imul(r ^ (r >>> 7), r | 61);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ── 자리 고정 (ADR-0017) ───────────────────────────────── */

  var GAP = 14; /* 구획 사이를 벌리는 각도. 없으면 다섯이 고르게 퍼져 구획이 안 보인다 */

  /* 한 궤도의 자리를 잡는다. **구획끼리 붙여 두고 사이만 벌린다.**
   * 서버가 준 순서가 이미 구획별로 묶여 있다 — 여기서 다시 정렬하면 순서가 두 곳에
   * 살게 되고 한쪽만 고쳐지는 날이 온다 */
  function ring(nodes, cx, cy, radius) {
    if (!nodes.length) return { placed: [], arcs: [] };

    var runs = [];
    nodes.forEach(function (n) {
      var last = runs[runs.length - 1];
      if (last && last[0].sector === n.sector) last.push(n);
      else runs.push([n]);
    });

    var step = (360 - runs.length * GAP) / nodes.length;
    var placed = [];
    var arcs = [];
    var deg = -90 - step / 2; /* 12시에서 시작해 시계 방향 */

    runs.forEach(function (run) {
      var from = deg + GAP / 2;
      deg += GAP / 2;
      run.forEach(function (n) {
        deg += step;
        var rad = (deg * Math.PI) / 180;
        placed.push({
          node: n,
          angle: deg,
          x: cx + radius * Math.cos(rad),
          y: cy + radius * Math.sin(rad),
        });
      });
      arcs.push({ sector: run[0].sector, from: from, to: deg + GAP / 2 });
      deg += GAP / 2;
    });
    return { placed: placed, arcs: arcs };
  }

  function orbit(nodes, opts) {
    var o = opts || {};
    var size = o.size || 640;
    var cx = o.cx == null ? size / 2 : o.cx;
    var cy = o.cy == null ? size / 2 : o.cy;
    var rInner = o.inner || 132;
    var rOuter = o.outer || 258;

    var center = nodes.filter(function (n) {
      return n.kind === "identity";
    });
    var inner = ring(
      nodes.filter(function (n) {
        return n.kind === "company";
      }),
      cx, cy, rInner
    );
    var outer = ring(
      nodes.filter(function (n) {
        return n.kind === "content";
      }),
      cx, cy, rOuter
    );

    return {
      cx: cx, cy: cy, size: size, inner: rInner, outer: rOuter,
      center: center.length ? { node: center[0], x: cx, y: cy, angle: 0 } : null,
      placed: inner.placed.concat(outer.placed),
      innerArcs: inner.arcs,
      outerArcs: outer.arcs,
    };
  }

  /* 호 하나의 `d`. 궤도를 구획별로 끊어 그린다 — 끊긴 자리가 구획 경계다 */
  function arcPath(cx, cy, radius, from, to) {
    var a = (from * Math.PI) / 180;
    var b = (to * Math.PI) / 180;
    var large = to - from > 180 ? 1 : 0;
    return (
      "M " + (cx + radius * Math.cos(a)) + " " + (cy + radius * Math.sin(a)) +
      " A " + radius + " " + radius + " 0 " + large + " 1 " +
      (cx + radius * Math.cos(b)) + " " + (cy + radius * Math.sin(b))
    );
  }

  /* ── 힘 배치 ──────────────────────────────────────────────
   *
   * Fruchterman-Reingold 계열. 179 노드면 O(n²) 로 충분하다 —
   * 32k × 400틱 이 브라우저에서 100ms 안쪽이다. Barnes-Hut 을 안 넣는 이유다.
   *
   * **한 번에 다 돌리고 끝낸다.** 애니메이션으로 수렴하는 것을 보여 주면 예뻐 보이지만
   * 스크린샷이 찍히는 시점이 매번 달라져 비교가 깨진다(하네스 함정 2와 같은 자리). */
  function force(items, links, opts) {
    var o = opts || {};
    var W = o.width || 1000;
    var H = o.height || 700;
    var iters = o.iterations || 420;
    var rand = rng(o.seed == null ? 20260821 : o.seed);

    var n = items.length;
    if (!n) return items;

    var byId = {};
    items.forEach(function (it, i) {
      /* 시작 자리를 무작위로 흩되 **시드가 고정이라 늘 같은 흩뜨림이다.**
       * 원판에 고르게 뿌린다 — 정사각에 뿌리면 모서리에서 안쪽으로 밀려드는
       * 초기 몇 틱이 낭비되고 수렴한 그림도 네모나진다 */
      var a = rand() * Math.PI * 2;
      var r = Math.sqrt(rand()) * Math.min(W, H) * 0.42;
      it.x = W / 2 + r * Math.cos(a);
      it.y = H / 2 + r * Math.sin(a);
      it.i = i;
      byId[it.id] = it;
    });

    var edges = links
      .map(function (l) {
        var s = byId[l.source], t = byId[l.target];
        return s && t ? { s: s, t: t, w: l.weight || 1 } : null;
      })
      .filter(Boolean);

    var area = W * H;
    var k = Math.sqrt(area / n) * (o.spread || 0.72);
    var temp = Math.min(W, H) * 0.16;
    var cool = temp / (iters + 1);

    var dx = new Float64Array(n), dy = new Float64Array(n);

    for (var step = 0; step < iters; step++) {
      dx.fill(0); dy.fill(0);

      /* 밀어내기 */
      for (var a2 = 0; a2 < n; a2++) {
        for (var b2 = a2 + 1; b2 < n; b2++) {
          var ux = items[a2].x - items[b2].x;
          var uy = items[a2].y - items[b2].y;
          var d2 = ux * ux + uy * uy;
          if (d2 < 0.01) { ux = (rand() - 0.5) * 0.1; uy = (rand() - 0.5) * 0.1; d2 = 0.01; }
          var d = Math.sqrt(d2);
          /* 반지름을 셈에 넣는다 — 큰 노드가 작은 노드를 더 밀어야 겹침이 준다 */
          var rr = (items[a2].r || 4) + (items[b2].r || 4);
          var f = ((k * k) / d) * (1 + rr / 24);
          dx[a2] += (ux / d) * f; dy[a2] += (uy / d) * f;
          dx[b2] -= (ux / d) * f; dy[b2] -= (uy / d) * f;
        }
      }

      /* 당기기 */
      edges.forEach(function (e) {
        var ux = e.s.x - e.t.x, uy = e.s.y - e.t.y;
        var d = Math.sqrt(ux * ux + uy * uy) || 0.01;
        var f = ((d * d) / k) * e.w;
        var fx = (ux / d) * f, fy = (uy / d) * f;
        dx[e.s.i] -= fx; dy[e.s.i] -= fy;
        dx[e.t.i] += fx; dy[e.t.i] += fy;
      });

      /* 중심으로 아주 약하게. **없으면 연결 없는 덩어리가 화면 밖으로 흘러간다** */
      for (var c = 0; c < n; c++) {
        dx[c] += (W / 2 - items[c].x) * 0.006;
        dy[c] += (H / 2 - items[c].y) * 0.006;
      }

      for (var m = 0; m < n; m++) {
        var len = Math.sqrt(dx[m] * dx[m] + dy[m] * dy[m]) || 1;
        var lim = Math.min(len, temp);
        items[m].x += (dx[m] / len) * lim;
        items[m].y += (dy[m] / len) * lim;
        var pad = (items[m].r || 4) + 6;
        items[m].x = Math.max(pad, Math.min(W - pad, items[m].x));
        items[m].y = Math.max(pad, Math.min(H - pad, items[m].y));
      }
      temp -= cool;
    }
    return items;
  }

  /* 내용에 뷰박스를 맞춘다. **배치를 먼저 하고 틀을 나중에 맞춘다.**
   *
   * 힘 배치는 어디까지 퍼질지 미리 모른다. 틀을 먼저 고정하면 가장자리 노드가 잘리고,
   * 잘린 것을 막으려고 경계에 가두면 **테두리에 노드가 줄지어 붙는다** — 실제로 그랬다.
   * 이름표는 오른쪽으로 자라므로 그쪽 여백을 더 준다. */
  function fit(items, pad) {
    /* 숫자 하나로도 `{right: n}` 로도 받는다. **객체를 그대로 p 에 넣으면 안 된다** —
     * `x0 - {}` 가 NaN 이 되고 viewBox 가 통째로 무효가 되어 SVG 가 안 그려진다 */
    var o = typeof pad === "object" && pad ? pad : {};
    var p = typeof pad === "number" ? pad : o.pad == null ? 24 : o.pad;
    var right = o.right == null ? p : o.right;
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    items.forEach(function (it) {
      var r = (it.r || 4) + 2;
      if (it.x - r < x0) x0 = it.x - r;
      if (it.y - r < y0) y0 = it.y - r;
      if (it.x + r > x1) x1 = it.x + r;
      if (it.y + r > y1) y1 = it.y + r;
    });
    if (!isFinite(x0)) return { x: 0, y: 0, w: 100, h: 100, str: "0 0 100 100" };
    var box = {
      x: x0 - p, y: y0 - p,
      w: x1 - x0 + p + right, h: y1 - y0 + p * 2,
    };
    box.str = box.x.toFixed(1) + " " + box.y.toFixed(1) + " " + box.w.toFixed(1) + " " + box.h.toFixed(1);
    return box;
  }

  /* ── 허브 하나 + 방사 ─────────────────────────────────────
   *
   * 고른 자리를 가운데 두고 그 근거를 둘레에 건다. 링이 여럿이면 안쪽부터 채운다. */
  function radial(items, opts) {
    var o = opts || {};
    var cx = o.cx || 0, cy = o.cy || 0;
    var base = o.radius || 190;
    var perRing = o.perRing || 18;
    var gap = o.ringGap || 96;
    var rand = rng(o.seed == null ? 20260821 : o.seed);

    items.forEach(function (it, i) {
      var ringIdx = Math.floor(i / perRing);
      var inRing = i % perRing;
      var count = Math.min(perRing, items.length - ringIdx * perRing);
      /* 링마다 시작 각도를 조금 돌린다 — 안 돌리면 바큇살이 한 줄로 겹쳐 선다 */
      var offset = ringIdx * 0.37 + (o.rotate || 0);
      var a = (inRing / count) * Math.PI * 2 + offset - Math.PI / 2;
      /* 링 안에서 반지름을 조금 흔든다. 정확한 원은 도형으로 읽히고 그래프로 안 읽힌다 */
      var jitter = (rand() - 0.5) * (o.jitter == null ? 26 : o.jitter);
      var r = base + ringIdx * gap + jitter;
      it.x = cx + r * Math.cos(a);
      it.y = cy + r * Math.sin(a);
      it.angle = a;
      it.ring = ringIdx;
    });
    return items;
  }

  /* ── 3D 투영 ──────────────────────────────────────────────
   *
   * **three.js 를 안 쓴다.** 목업에 의존성을 넣으면 「이 시안을 고르면 무엇을 지불하는가」가
   * 흐려진다 — 여기서 손으로 투영하고, 고를 때 실제 비용(three.js ≈ 150KB gz)을 README 가 적는다.
   *
   * **CSS 3D 로 하지 않는다.** 카메라를 향해 되돌린 원이 바닥 면과 교차하면 브라우저가
   * 교차선에서 잘라 그려 도트가 부채꼴이 되고, `filter: blur()` 는 `preserve-3d` 를 끊는다.
   * canvas 에 z 순으로 그리면 이 문제가 통째로 없다. */
  function project(p, cam) {
    /* Y 축 회전 → X 축 기울기 → 원근 */
    var cosY = Math.cos(cam.yaw), sinY = Math.sin(cam.yaw);
    var x = p.x * cosY - p.z * sinY;
    var z = p.x * sinY + p.z * cosY;
    var cosP = Math.cos(cam.pitch), sinP = Math.sin(cam.pitch);
    var y = p.y * cosP - z * sinP;
    z = p.y * sinP + z * cosP;

    var d = cam.distance;
    var s = d / (d + z);
    return { x: cam.cx + x * s, y: cam.cy + y * s, z: z, scale: s };
  }

  /* 구면에 고르게 뿌린다(피보나치 격자). **경도·위도로 뿌리면 극에 뭉친다** */
  function sphere(count, radius, offset) {
    var pts = [];
    var golden = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < count; i++) {
      var t = count === 1 ? 0.5 : (i + (offset || 0.5)) / count;
      var y = 1 - t * 2;
      var r = Math.sqrt(Math.max(0, 1 - y * y));
      var a = golden * i;
      pts.push({ x: Math.cos(a) * r * radius, y: y * radius, z: Math.sin(a) * r * radius });
    }
    return pts;
  }

  return {
    rng: rng,
    orbit: orbit,
    arcPath: arcPath,
    force: force,
    radial: radial,
    project: project,
    sphere: sphere,
    fit: fit,
  };
})();
