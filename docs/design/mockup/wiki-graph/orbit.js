/* 궤도 기하. **시안 셋이 이걸 공유한다.**
 *
 * `web/components/Orbit.tsx` 의 배치를 그대로 옮겼고 지름만 키웠다.
 * 자리·각도·구획이 시안마다 달라지면 **무엇 때문에 좋아 보이는지 분간이 안 된다** —
 * 이번에 갈리는 것은 오직 **노드를 무엇으로 그리는가** 하나다.
 *
 * 지름을 키운 이유는 하나뿐이다. 현행 도트가 지름 30px 이라 `DESIGN.md` §8.2 의
 * 44px 타깃에 못 미쳤고, 구체로 그리면 그 크기에서는 음영이 뭉개진다.
 * r 23 → 지름 46px 이라 규칙도 넘고 재질도 보인다. 궤도 반지름은 그만큼 넓혔다.
 */

var SIZE = 700, C = SIZE / 2;
var RING = { identity: 0, company: 158, content: 286 };
var DOT = { identity: 54, company: 23, content: 23 };
var GAP = 14;   /* 구획 사이를 벌리는 각도. 이게 없으면 구획이 안 보인다 */

/* 한 궤도의 자리를 잡는다. **구획끼리 붙여 두고 사이만 벌린다.**
 * 서버가 준 순서(`wiki/topics.py` 의 ORBIT)가 이미 구획별로 묶여 있어서 다시 정렬하지 않는다. */
function placeRing(nodes, radius) {
  if (!nodes.length) return { placed: [], arcs: [] };

  var runs = [];
  nodes.forEach(function (n) {
    var last = runs[runs.length - 1];
    if (last && last[0].sector === n.sector) last.push(n);
    else runs.push([n]);
  });

  var step = (360 - runs.length * GAP) / nodes.length;
  var placed = [], arcs = [], deg = -90 - step / 2;   /* 12시에서 시계 방향 */

  runs.forEach(function (run) {
    var from = deg + GAP / 2;
    deg += GAP / 2;
    run.forEach(function (n) {
      deg += step;
      var rad = deg * Math.PI / 180;
      placed.push(Object.assign({}, n, {
        angle: deg,
        r: DOT[n.kind],
        x: C + radius * Math.cos(rad),
        y: C + radius * Math.sin(rad),
      }));
    });
    arcs.push({ sector: run[0].sector, from: from, to: deg + GAP / 2 });
    deg += GAP / 2;
  });
  return { placed: placed, arcs: arcs };
}

/* 호 하나의 d. **궤도를 구획별로 끊어 그린다** — 끊긴 자리가 구획 경계다.
 * 원 하나로 그리면 각도가 뜻을 갖는다는 것이 안 보인다. */
function arcPath(radius, from, to) {
  var a = from * Math.PI / 180, b = to * Math.PI / 180;
  return "M " + (C + radius * Math.cos(a)) + " " + (C + radius * Math.sin(a)) +
    " A " + radius + " " + radius + " 0 " + (to - from > 180 ? 1 : 0) + " 1 " +
    (C + radius * Math.cos(b)) + " " + (C + radius * Math.sin(b));
}

var ORBIT = (function () {
  var inner = placeRing(byKind("company"), RING.company);
  var outer = placeRing(byKind("content"), RING.content);
  var center = Object.assign({}, byKind("identity")[0], {
    angle: 0, r: DOT.identity, x: C, y: C,
  });
  return {
    center: center,
    inner: inner,
    outer: outer,
    all: inner.placed.concat(outer.placed),
    everything: [center].concat(inner.placed, outer.placed),
  };
})();

/* 바큇살. 중심에서 각 자리로, 구체 앞에서 멈춘다 */
function spokes() {
  return ORBIT.all.map(function (n) {
    var rad = n.angle * Math.PI / 180;
    var from = DOT.identity + 8;
    var to = Math.hypot(n.x - C, n.y - C) - n.r - 8;
    return {
      x1: C + from * Math.cos(rad), y1: C + from * Math.sin(rad),
      x2: C + to * Math.cos(rad), y2: C + to * Math.sin(rad),
    };
  });
}

/* 구획 라벨. **구획이 시작하는 빈 각도에 세운다** — 노드도 노드 라벨도 없는 유일한 자리다.
 * 바깥 궤도에만 얹는다. 안쪽은 지름이 작아 노드 이름과 겹친다. */
function sectorLabels(offset) {
  return ORBIT.outer.arcs.map(function (a) {
    var rad = a.from * Math.PI / 180, r = RING.content + offset;
    return {
      key: a.sector,
      label: SECTORS[a.sector] || a.sector,
      x: C + r * Math.cos(rad),
      y: C + r * Math.sin(rad) + 4,
    };
  });
}

/* 이름표 자리. 궤도 바깥으로 민다 — 왼쪽 반원이면 오른쪽 정렬이라야 글자가 구체를 안 덮는다 */
function labelAt(n, gap) {
  var rad = n.angle * Math.PI / 180, out = n.r + (gap || 18);
  return {
    x: n.x + out * Math.cos(rad),
    y: n.y + out * Math.sin(rad) + 4,
    anchor: Math.cos(rad) > 0.25 ? "start" : Math.cos(rad) < -0.25 ? "end" : "middle",
  };
}

function stateOf(n) {
  return n.filled ? (n.conflicted ? "손봐야 해요" : "찼어요") : "아직 비어 있어요";
}
