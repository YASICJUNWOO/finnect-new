"use client";

import { useMemo } from "react";
import { arc, fit, labelWidth, place, type Body, type Edge, type Point, type Rect } from "@/lib/graph";
import type { WikiNode } from "@/lib/wiki";
import { useZoomPan } from "./useZoomPan";
import styles from "./WikiGraph.module.css";

/** 위키 자유 그래프. **자리만 올린다. 사실은 점으로 안 그린다.**
 *
 * 사실 하나를 점 하나로 매달아 봤고, 자리 쉰여섯에 사실 삼백스물넷이 붙자 회색 점이
 * 자리 점을 후광처럼 둘러싸 **어느 것이 누를 수 있는 자리인지 안 읽혔다.** 담긴 양은
 * 자리 점의 크기가 이미 말하므로 같은 말을 두 번 하면서 화면만 지저분해진 것이다.
 * **사실은 자리를 눌렀을 때 곁 패널이 문장으로 보여 준다** — 세는 자리와 읽는 자리를
 * 가른다.
 *
 * ## 힘 배치를 쓴다. 시드가 고정이다
 *
 * ADR-0017 과 ADR-0056 이 힘 배치를 거절했고 그 이유는 **「열 때마다 모양이 달라진다」**
 * 였다. `lib/graph.ts` 가 `Math.random` 대신 고정 시드를 돌리므로 같은 위키는 늘 같은
 * 그림이다. **이건 되돌리기 어려운 결정이라 ADR 이 필요하다** — 지금은 없다.
 *
 * ## 카테고리 열의 각도를 못 박는다
 *
 * 시드로 안 풀리는 반론이 하나 남는다 — 파일을 더 올리면 노드가 늘고 배치가 통째로
 * 다시 잡힌다. 그래서 카테고리 열만 **각도를 고정하고 반지름을 힘에 맡긴다.** 「회사」가
 * 늘 같은 방위에 서므로 지도의 방향이 유지되고, 안쪽 뭉침만 자유롭다. 각도가 뜻을
 * 갖는다는 ADR-0017 의 성질이 여기서 살아남는다.
 *
 * ## 색을 안 쓴다
 *
 * ADR-0052 · ADR-0056 그대로다. 상태는 **채움·선·크기**로 가른다. 카테고리 가지가 이미
 * 묶어 주므로 분류색은 같은 말을 두 번 하게 된다. */

/** 힘 배치를 돌리는 판.
 *
 * **이 값이 곧 글자 크기다.** SVG 는 viewBox 를 상자에 맞춰 늘이고 줄이므로, 판이
 * 그려지는 상자보다 크면 13px 로 적은 이름표가 그만큼 작게 나온다. 판을 실제 상자
 * (`WikiBoard.module.css` 의 `.canvas`, 최대 720px)에 가깝게 잡아 배율을 1 근처에
 * 두는 것이 이름표를 읽히게 하는 유일한 방법이다 — **판을 키우고 여백으로 맞추면
 * 글자가 조용히 작아진다.** */
const W = 660;
const H = 560;

/** 카테고리 열이 중심에서 최소한 이만큼은 떨어진다. 허브 지름 + 이름표 자리 */
const CATEGORY_RING = 128;

/** 이름표 크기. **CSS 와 같은 값이어야 한다** — 겹침 판정을 여기서 하고 그리기는
 *  저기서 한다. 갈리면 겹치지 않는다고 판정한 이름표가 화면에서 겹친다. */
const FONT = { category: 13, spot: 12 } as const;

type Kind = "hub" | "category" | "spot";

type Drawn = {
  id: string;
  kind: Kind;
  /** 눌렀을 때 열 자리 */
  path: string;
  parent: string;
  label: string;
  radius: number;
  filled: boolean;
  facts: number;
  x: number;
  y: number;
  /** 중심에서 얼마나 먼가. 0~1. 등장 순서를 이 값이 정한다 */
  reach: number;
};

/** 물체 id. **자리 경로를 그대로 id 로 쓰지 않는다** — 허브와 한 목록에 들어가므로
 * 접두사로 갈라야 `hub` 라는 자리가 오는 날 부딪히지 않는다. 화면에 쓰는 이름은
 * `Drawn.path` 가 따로 든다 — 주소(`?spot=`)와 `onSelect` 가 보는 것은 그쪽이다. */
const HUB = "hub";
const nodeId = (path: string) => `n:${path}`;

/** 노드를 물체 목록으로 편다. **여기가 그래프의 정의다.** */
function build(
  nodes: readonly WikiNode[],
  categories: Record<string, string>,
): { bodies: Body[]; edges: Edge[]; meta: Map<string, Omit<Drawn, "x" | "y" | "reach">> } {
  const bodies: Body[] = [{ id: HUB, radius: 34, fixed: true }];
  const edges: Edge[] = [];
  const meta = new Map<string, Omit<Drawn, "x" | "y" | "reach">>();

  const roots = nodes.filter((n) => n.depth === 0);
  // 방위는 서버가 준 카테고리 순서가 정한다. **화면이 다시 정렬하지 않는다** —
  // 정렬이 두 곳에 살면 한쪽만 고쳐지는 날이 오고 그날 지도의 방향이 갈린다
  const slot = new Map(roots.map((n, i) => [n.path, (i / Math.max(1, roots.length)) * Math.PI * 2 - Math.PI / 2]));

  /** 카테고리 열은 **제 아래에 뭐라도 앉으면 찬 것이다.** 사실은 잎에 앉으므로
   * `n.filled` 를 그대로 쓰면 「회사」가 자식 셋을 채우고도 빈 것으로 그려진다 */
  const alive = new Set<string>();
  for (const n of nodes) {
    if (!n.filled) continue;
    for (const part of n.path.split("/").slice(0, -1).reduce<string[]>((acc, seg) => {
      acc.push(acc.length ? `${acc[acc.length - 1]}/${seg}` : seg);
      return acc;
    }, [])) {
      alive.add(part);
    }
  }

  for (const n of nodes) {
    const isRoot = n.depth === 0;
    const filled = n.filled || alive.has(n.path);
    const facts = n.statements.length;
    // 자리 크기가 담긴 양을 따른다. **사실 점을 뺐으므로 양을 말하는 것이 이 크기
    // 하나다.** 제곱근으로 눌러 담는다 — 선형이면 넓이 차가 개수 차의 제곱이 되어
    // 작은 자리가 먼지로 읽힌다
    const radius = isRoot ? 10 : n.filled ? 4.5 + Math.sqrt(facts) * 2.3 : 4.5;

    const id = nodeId(n.path);
    // **부모도 id 다.** 경로를 그대로 들면 `branchOf` 가 조상을 거슬러 오를 때
    // `meta` 를 못 찾는다 — 저 표는 id 로 열린다
    const parent = n.parent ? nodeId(n.parent) : HUB;

    bodies.push({
      id,
      radius,
      anchor: isRoot ? { angle: slot.get(n.path) ?? 0, minRadius: CATEGORY_RING } : undefined,
    });
    meta.set(id, {
      id,
      kind: isRoot ? "category" : "spot",
      path: n.path,
      parent,
      label: isRoot ? (categories[n.category] ?? n.name) : n.name,
      radius,
      filled,
      facts,
    });
    edges.push({ from: parent, to: id, weight: isRoot ? 1.8 : 1.5 });
  }

  return { bodies, edges, meta };
}

/** 이름표가 놓이는 자리. **점의 바깥쪽으로 뻗는다** — 안쪽으로 두면 가지 위에 얹힌다. */
function labelBox(d: Drawn): Rect {
  const size = d.kind === "category" ? FONT.category : FONT.spot;
  const w = labelWidth(d.label, size);
  const right = d.x >= W / 2;
  const lx = right ? d.x + d.radius + 6 : d.x - d.radius - 6;
  return {
    x0: right ? lx : lx - w,
    x1: right ? lx + w : lx,
    y0: d.y - size * 0.85,
    y1: d.y + size * 0.4,
  };
}

/** 이름표를 몇 개나 세울 수 있나. **겹치면 뒤엣것을 버린다.**
 *
 * 자유 배치라 이름표가 겹치는 것을 자리로 막을 수 없다. 카테고리 열은 무슨 일이 있어도
 * 세우고(지도의 방위라서), 자리 이름은 담긴 양이 많은 것부터 넣다가 겹치면 버린다.
 * 버려진 이름은 그 점을 고르거나 올리면 뜬다.
 *
 * 세운 상자를 같이 낸다 — **틀을 맞추는 쪽이 그 상자를 알아야** 이름표가 안 잘린다. */
function labels(drawn: readonly Drawn[]): { kept: Set<string>; boxes: Rect[] } {
  const order = [...drawn]
    .filter((d) => d.kind === "category" || d.kind === "spot")
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "category" ? -1 : 1;
      return b.facts - a.facts;
    });

  const boxes: Rect[] = [];
  const kept = new Set<string>();

  for (const d of order) {
    const box = labelBox(d);
    const clash = boxes.some((t) => box.x0 < t.x1 && box.x1 > t.x0 && box.y0 < t.y1 && box.y1 > t.y0);
    // 카테고리 열은 겹쳐도 세운다. **방위를 읽는 유일한 글자다**
    if (clash && d.kind !== "category") continue;
    boxes.push(box);
    kept.add(d.id);
  }
  return { kept, boxes };
}

/** 고른 자리에 딸린 것들. 조상 사슬 + 제 아래 전부.
 *
 * **경로를 받고 id 를 낸다.** 고른 자리는 주소에서 오므로 경로이고, 흐리게 할지 말지는
 * 물체 단위라 id 다. 둘을 안 가르면 `meta.get()` 이 조용히 `undefined` 를 내고
 * 조상 사슬이 통째로 빠진다 — 그러면 고른 자리만 뜨고 거기까지 가는 가지가 흐려진다. */
function branchOf(path: string, meta: Map<string, Omit<Drawn, "x" | "y" | "reach">>): Set<string> {
  const hot = new Set<string>([HUB, nodeId(path)]);

  for (let at = meta.get(nodeId(path))?.parent; at && !hot.has(at); at = meta.get(at)?.parent) {
    hot.add(at);
  }

  // 제 아래로 내려간다. 경로가 접두사라 한 번 훑으면 된다
  for (const [id, m] of meta) {
    if (m.path === path || m.path.startsWith(`${path}/`)) hot.add(id);
  }
  return hot;
}

export function WikiGraph({
  nodes,
  categories,
  filled,
  total,
  selected,
  onSelect,
}: {
  nodes: WikiNode[];
  categories: Record<string, string>;
  filled: number;
  total: number;
  selected: string | null;
  onSelect: (path: string) => void;
}) {
  // 배치는 비싸고 노드가 바뀔 때만 달라진다. **고를 때마다 다시 잡으면 그림이 튄다**
  const { drawn, edges, box, named } = useMemo(() => {
    const { bodies, edges: links, meta } = build(nodes, categories);
    const at = place(bodies, links, { width: W, height: H, spread: 0.56 });

    const items: Drawn[] = bodies.map((b) => {
      const p = at.get(b.id) ?? { x: W / 2, y: H / 2 };
      const m = meta.get(b.id);
      const reach = Math.min(1, Math.hypot(p.x - W / 2, p.y - H / 2) / (Math.min(W, H) / 2));
      return m
        ? { ...m, x: p.x, y: p.y, reach }
        : {
            id: HUB, kind: "hub" as const, path: HUB, parent: "", label: "",
            radius: 34, filled: true, facts: 0, x: p.x, y: p.y, reach: 0,
          };
    });

    const pos = new Map(items.map((d) => [d.id, { x: d.x, y: d.y } as Point]));
    const { kept, boxes } = labels(items);
    const dots: Rect[] = items.map((d) => ({
      x0: d.x - d.radius, y0: d.y - d.radius, x1: d.x + d.radius, y1: d.y + d.radius,
    }));

    return {
      drawn: items,
      named: kept,
      // 점과 이름표를 같이 재고 여백은 얇게. **틀이 커지면 글자가 작아진다**
      box: fit([...dots, ...boxes], 14),
      edges: links
        .map((l) => ({ ...l, a: pos.get(l.from), b: pos.get(l.to) }))
        .filter((l): l is typeof l & { a: Point; b: Point } => !!l.a && !!l.b),
    };
  }, [nodes, categories]);

  const meta = useMemo(() => new Map(drawn.map((d) => [d.id, d])), [drawn]);
  const hot = useMemo(
    () => (selected && meta.has(selected) ? branchOf(selected, meta) : null),
    [selected, meta],
  );

  // 그리는 순서가 곧 쌓임 순서다. 자리 → 카테고리 → 허브.
  // **이름표가 점에 덮이면 안 되므로** 이름이 붙는 것이 뒤로 간다
  const rank: Record<Kind, number> = { spot: 0, category: 1, hub: 2 };
  const order = [...drawn].sort((a, b) => rank[a.kind] - rank[b.kind]);

  const { ref, view, zoom, zoomed, panning, zoomBy, reset, onPointerDown, onClickCapture } =
    useZoomPan(box);

  return (
    /* **넘침을 여기서 자른다.** SVG 는 `overflow: visible` 이라 확대하면 판 밖 노드가
     * 캔버스 밖으로 흘러 옆 패널을 덮는다 */
    <div className={styles.wrap} data-zoomed={zoomed}>
      <svg
        ref={ref}
        className={styles.svg}
        viewBox={`${view.x.toFixed(1)} ${view.y.toFixed(1)} ${view.width.toFixed(1)} ${view.height.toFixed(1)}`}
        preserveAspectRatio="xMidYMid meet"
        role="group"
        aria-label={`내 사업 위키. 자리 ${total}개 중 ${filled}개가 찼어요`}
        data-picking={hot ? "true" : "false"}
        data-zoomed={zoomed}
        data-panning={panning}
        onPointerDown={onPointerDown}
        onClickCapture={onClickCapture}
      >
        {/* 가지. **선이 구조를 말하니 거의 안 보인다** — 진하게 하면 그물이 되고
          * 점이 안 읽힌다. 고른 갈래만 진해진다 */}
        <g className={styles.edges}>
          {edges.map((l) => (
            <path
              key={`${l.from}→${l.to}`}
              className={styles.edge}
              data-kind={meta.get(l.to)?.kind ?? "spot"}
              data-hot={hot ? hot.has(l.from) && hot.has(l.to) : null}
              d={arc(l.a, l.b)}
            />
          ))}
        </g>

        {order.map((d) =>
          d.kind === "hub" ? (
            <g key={d.id} className={styles.hub}>
              <circle className={styles.hubDot} cx={d.x} cy={d.y} r={d.radius} />
              <text className={styles.hubTitle} x={d.x} y={d.y - 3} textAnchor="middle">
                내 사업
              </text>
              <text className={styles.hubCount} x={d.x} y={d.y + 15} textAnchor="middle" data-numeric>
                {filled}/{total}
              </text>
            </g>
          ) : (
            <Dot
              key={d.id}
              node={d}
              named={named.has(d.id)}
              selected={selected === d.path}
              dim={hot ? !hot.has(d.id) : false}
              onSelect={onSelect}
            />
          ),
        )}
      </svg>

      <Zoom zoom={zoom} zoomBy={zoomBy} reset={reset} />
    </div>
  );
}

/** 확대·축소 손잡이. **판 위에 뜨지만 그림자를 안 쓴다**(`DESIGN.md` §6) — 흰 면과
 *  1px 경계선으로 세운다. 그래프가 가운데로 뭉치므로 모서리에 둔다.
 *
 *  **전체 보기는 확대했을 때만 나온다.** 누를 일이 없는 버튼을 늘 띄우면 크롬만 는다.
 *
 *  배율을 숫자로 안 적는다 — 「2.4×」가 사용자에게 답하는 질문이 없다. */
function Zoom({
  zoom,
  zoomBy,
  reset,
}: {
  zoom: number;
  zoomBy: (factor: number) => void;
  reset: () => void;
}) {
  return (
    <div className={styles.zoom}>
      {zoom > 1.02 && (
        <button type="button" className={styles.zoomText} onClick={reset}>
          전체 보기
        </button>
      )}
      <button
        type="button"
        className={styles.zoomBtn}
        onClick={() => zoomBy(1 / 1.5)}
        disabled={zoom <= 1.02}
        aria-label="축소"
        title="축소"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3.5 8h9" />
        </svg>
      </button>
      <button
        type="button"
        className={styles.zoomBtn}
        onClick={() => zoomBy(1.5)}
        disabled={zoom >= 5.98}
        aria-label="확대"
        title="확대"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3.5 8h9M8 3.5v9" />
        </svg>
      </button>
    </div>
  );
}

/** 점 하나. **키보드로 갈 수 있어야 한다** — 이 그래프가 자리로 가는 유일한 길이라
 *  마우스 전용이면 못 연다.
 *
 *  찬 자리도 지름이 10~22px 이라 그대로는 44px 타깃이 못 된다. **투명한 손잡이 원**이
 *  점을 넉넉하게 감싸는 이유다. */
function Dot({
  node,
  named,
  selected,
  dim,
  onSelect,
}: {
  node: Drawn;
  named: boolean;
  selected: boolean;
  dim: boolean;
  onSelect: (path: string) => void;
}) {
  const right = node.x >= W / 2;

  return (
    <g
      className={styles.node}
      data-kind={node.kind}
      data-state={node.filled ? "filled" : "empty"}
      data-selected={selected}
      data-dim={dim}
      data-named={named}
      style={{ "--reach": node.reach } as React.CSSProperties}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${node.path} — ${node.filled ? `사실 ${node.facts}개` : "아직 비었어요"}`}
      onClick={() => onSelect(node.path)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(node.path);
        }
      }}
    >
      <circle
        className={styles.hit}
        cx={node.x}
        cy={node.y}
        r={Math.max(node.radius + 12, 16)}
      />
      {selected && <circle className={styles.halo} cx={node.x} cy={node.y} r={node.radius + 6} />}
      <circle className={styles.dot} cx={node.x} cy={node.y} r={node.radius} />
      {/* **크기를 여기서 안 준다.** CSS 가 폭마다 다르게 준다 — 좁은 화면에서는 SVG
        * 자체가 작게 축소되므로 같은 13px 이 6px 으로 나온다(`WikiGraph.module.css`) */}
      <text
        className={styles.label}
        x={right ? node.x + node.radius + 6 : node.x - node.radius - 6}
        y={node.y + 4}
        textAnchor={right ? "start" : "end"}
      >
        {node.label}
      </text>
    </g>
  );
}
