"use client";

import type { WikiNode } from "@/lib/wiki";
import styles from "./Orbit.module.css";

/** 위키 방사 트리(마인드맵). **힘 기반 배치를 쓰지 않는다**(ADR-0017 · ADR-0056).
 *
 * 중심(회사) → 카테고리 열 → 노드 → 하위 노드로 **간선이 뻗는다.** 자리를 고정하면
 * 두 번째 볼 때 찾는다 — 물리 배치는 열 때마다 모양이 달라진다.
 *
 * ## 궤도·링·구획 호를 걷어냈다
 *
 * 저것들은 **깊이가 둘로 고정일 때만** 성립한다. 자리가 동적이 되면서 깊이가 정해져
 * 있지 않고, 그래서 층마다 반지름을 주는 방사 트리라야 한다.
 *
 * ## 각도를 잎 수로 나눈다
 *
 * 카테고리마다 각도 구간을 갖고 **그 폭은 제 아래 잎 수에 비례한다** — `Plan` 이
 * 자라면 넓어진다. 각도가 뜻을 갖는다는 ADR-0017 의 성질이 여기서 유지된다.
 *
 * 잎이 없는 카테고리도 한 몫을 받는다. **비어도 자리가 있어야** 무엇이 없는지 보인다
 * (`DESIGN.md` §7-5).
 *
 * ## 점마다 이름이 붙는다
 *
 * 가지를 따라 라벨이 퍼져서 47개도 들어간다. 한 링에 몰아넣으면 점 사이가 26px 이라
 * 라벨을 못 붙였는데, 그 제약이 트리에서는 없다.
 *
 * **색을 안 쓴다**(ADR-0056). 카테고리 가지가 이미 묶어 줘서 분류색이 같은 말을 두 번
 * 하게 된다. 상태는 채움·선·크기로 가른다 — 색조 하나에 뜻 둘을 얹지 않는다. */

const SIZE = 900;
const C = SIZE / 2;

/** 층마다의 반지름. 0 은 중심이라 목록에 없다. **깊이가 더 깊으면 마지막 간격으로 민다.** */
const RING = [0, 150, 290, 400] as const;
const STEP = 110;

/** 점 크기. 얕을수록 크다 — **가지의 굵기가 층을 말한다.** */
const DOT = [26, 9, 6, 5] as const;

/** 카테고리 사이를 벌리는 각도. **이게 없으면 가지가 서로 붙는다.** */
const GAP = 6;

type Placed = WikiNode & { x: number; y: number; angle: number; r: number; state: string };

function radiusOf(depth: number): number {
  return depth < RING.length ? RING[depth] : RING[RING.length - 1] + (depth - RING.length + 1) * STEP;
}

function stateOf(n: WikiNode): "filled" | "empty" {
  return n.filled ? "filled" : "empty";
}

/** 각도를 나눈다. **부모의 구간 안에서 자식이 다시 나뉜다** — 그게 트리다.
 *
 * 몫은 **제 아래 잎 수**다. 잎이 없으면 자기 자신을 1로 센다 — 안 그러면 빈 카테고리가
 * 폭 0 이 되어 사라진다. */
function place(nodes: WikiNode[]): { placed: Placed[]; edges: [Placed, Placed][] } {
  const byParent = new Map<string, WikiNode[]>();
  for (const n of nodes) byParent.set(n.parent, [...(byParent.get(n.parent) ?? []), n]);

  // 제 아래 잎 수. 깊은 곳부터 올라오며 더한다
  const weight = new Map<string, number>();
  const weigh = (n: WikiNode): number => {
    const kids = byParent.get(n.path) ?? [];
    const w = kids.length === 0 ? 1 : kids.reduce((a, k) => a + weigh(k), 0);
    weight.set(n.path, w);
    return w;
  };
  const roots = byParent.get("") ?? [];
  const total = roots.reduce((a, r) => a + weigh(r), 0) || 1;

  const placed: Placed[] = [];
  const at = new Map<string, Placed>();
  const edges: [Placed, Placed][] = [];

  // 12시에서 시작해 시계 방향. 최상위 사이만 벌린다
  const span = 360 - roots.length * GAP;
  let cursor = -90;

  const walk = (n: WikiNode, from: number, to: number): void => {
    const mid = (from + to) / 2;
    const rad = (mid * Math.PI) / 180;
    const r = radiusOf(n.depth);
    const node: Placed = {
      ...n,
      angle: mid,
      r: DOT[Math.min(n.depth, DOT.length - 1)],
      state: stateOf(n),
      x: C + r * Math.cos(rad),
      y: C + r * Math.sin(rad),
    };
    placed.push(node);
    at.set(n.path, node);

    const parent = at.get(n.parent);
    if (parent) edges.push([parent, node]);

    const kids = byParent.get(n.path) ?? [];
    if (kids.length === 0) return;
    const w = weight.get(n.path) ?? 1;
    let cur = from;
    for (const kid of kids) {
      const share = ((weight.get(kid.path) ?? 1) / w) * (to - from);
      walk(kid, cur, cur + share);
      cur += share;
    }
  };

  for (const root of roots) {
    const share = ((weight.get(root.path) ?? 1) / total) * span;
    walk(root, cursor + GAP / 2, cursor + GAP / 2 + share);
    cursor += share + GAP;
  }
  return { placed, edges };
}

/** 부모에서 자식으로 가는 곡선. **반지름을 따라 휘어야 가지로 읽힌다.**
 *
 * 직선으로 이으면 별 모양이 되고 층이 안 보인다. 중간점을 부모 반지름에 두고 자식
 * 각도로 돌려 이차 베지에로 잇는다. */
function branch(a: Placed, b: Placed): string {
  const ra = Math.hypot(a.x - C, a.y - C);
  const rad = (b.angle * Math.PI) / 180;
  const mx = C + ra * Math.cos(rad);
  const my = C + ra * Math.sin(rad);
  return `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`;
}

/** 글자를 어느 쪽으로 붙일지. 왼쪽 반원이면 오른쪽 정렬 — 안 그러면 안쪽으로 겹친다. */
function anchorAt(deg: number): "start" | "middle" | "end" {
  const c = Math.cos((deg * Math.PI) / 180);
  return c > 0.2 ? "start" : c < -0.2 ? "end" : "middle";
}

export function Orbit({
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
  const { placed, edges } = place(nodes);

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="group"
      aria-label={`내 사업 위키. 자리 ${total}개 중 ${filled}개가 찼어요`}
    >
      {/* 가지. **선이 구조를 말하니 아주 얇다** */}
      {edges.map(([a, b]) => (
        <path key={`e-${b.path}`} className={styles.branch} d={branch(a, b)} />
      ))}

      {/* 중심. 노드가 아니라 표지다 — 누를 것이 없다 */}
      <circle className={styles.hub} cx={C} cy={C} r={44} />
      <text className={styles.hubTitle} x={C} y={C - 4} textAnchor="middle">
        내 사업
      </text>
      <text className={styles.hubCount} x={C} y={C + 16} textAnchor="middle">
        {filled}/{total}
      </text>

      {placed.map((n) => (
        <Dot
          key={n.path}
          node={n}
          label={n.depth === 0 ? (categories[n.category] ?? n.name) : n.name}
          selected={selected === n.path}
          onSelect={onSelect}
        />
      ))}
    </svg>
  );
}

/** 자리 하나. **키보드로 갈 수 있어야 한다** — 이 그래프가 유일한 길이라 마우스 전용이면 못 연다. */
function Dot({
  node,
  label,
  selected,
  onSelect,
}: {
  node: Placed;
  label: string;
  selected: boolean;
  onSelect: (path: string) => void;
}) {
  const rad = (node.angle * Math.PI) / 180;
  const out = node.r + 12;
  const state = node.filled ? `사실 ${node.statements.length}개` : "아직 비었어요";

  return (
    <g
      className={styles.node}
      data-state={node.state}
      data-depth={node.depth}
      data-selected={selected}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${node.path} — ${state}`}
      onClick={() => onSelect(node.path)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(node.path);
        }
      }}
    >
      {selected && <circle className={styles.halo} cx={node.x} cy={node.y} r={node.r + 5} />}
      <circle className={styles.dot} cx={node.x} cy={node.y} r={node.r} />
      <text
        className={styles.label}
        x={node.x + out * Math.cos(rad)}
        y={node.y + out * Math.sin(rad) + 4}
        textAnchor={anchorAt(node.angle)}
      >
        {label}
      </text>
    </g>
  );
}
