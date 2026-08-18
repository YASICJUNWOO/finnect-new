"use client";

import type { WikiNode } from "@/lib/wiki";
import styles from "./Orbit.module.css";

/** 위키 궤도. **힘 기반 배치를 쓰지 않는다**(ADR-0017).
 *
 * 노드가 열다섯이고 종류가 셋으로 정해져 있어서 배치를 물리에 맡길 이유가 없다.
 * 자리를 고정하면 **두 번째 볼 때 찾는다** — 물리 배치는 열 때마다 모양이 달라진다.
 *
 * 중심 하나 · 안쪽 다섯(사업체 정보) · 바깥 아홉(사업 내용). 각도가 구획을 뜻하고,
 * 순서는 서버가 준 `nodes` 순서 그대로다(`wiki/topics.py` 의 `ORBIT`).
 *
 * **색은 종류만 말한다**(DESIGN.md §4.1). 신뢰도나 상태를 색조로 표현하지 않는다.
 * 비어 있으면 속을 비우고 점선을 두르되 **테두리 색은 제 종류 색**이고, 손봐야 하는
 * 자리는 오른쪽 위에 배지 점 하나를 더 붙인다. 색조 하나에 뜻 둘을 얹으면 흐린 초록과
 * 흐린 갈색이 구분되지 않아 종류가 먼저 망가진다.
 *
 * **ADR-0017 에서 하나를 덜 했다.** 결정 2 가 구획 라벨을 두 궤도 모두에 얹으라고 하는데
 * 바깥 넷만 얹었다. 안쪽 다섯은 지름이 작아 라벨 둘을 더 두면 노드 이름과 겹친다 —
 * 대신 구획 사이를 각도로 벌려 뭉치지 않게 했다. 안쪽 구획 이름은 노드를 누르면 패널이 적는다.
 *
 * **관련 선(점선)이 없다.** 노드 간 연결(F1-1-6)이 아직 데이터에 없어서다. 없는 관계를
 * 그리지 않는다 — 같은 구획에 있다고 이어 버리면 사용자가 근거 있는 연결로 읽는다. */

const SIZE = 640;
const C = SIZE / 2;

/** 중심 · 안쪽 · 바깥. 값은 반지름이고 도트 크기는 아래 `DOT` 이다. */
const RING = { identity: 0, company: 132, content: 258 } as const;
const DOT = { identity: 40, company: 15, content: 15 } as const;

/** 구획 사이를 벌리는 각도. **이게 없으면 다섯이 고르게 퍼져 구획이 안 보인다.** */
const GAP = 14;

type Placed = WikiNode & { x: number; y: number; angle: number; r: number };
/** 구획 하나가 궤도에서 차지하는 각도 범위. **링을 이 단위로 끊어 그린다.** */
type Arc = { sector: string; from: number; to: number };

/** 한 궤도의 자리를 잡는다. **구획끼리 붙여 두고 사이만 벌린다.**
 *
 * 서버가 준 순서가 이미 구획별로 묶여 있다(`ORBIT`). 여기서 다시 정렬하면 그 순서가
 * 두 곳에 살게 되고, 한쪽만 고쳐지는 날이 온다. */
function place(nodes: WikiNode[], radius: number): { placed: Placed[]; arcs: Arc[] } {
  if (nodes.length === 0) return { placed: [], arcs: [] };

  // 이웃한 같은 구획끼리 묶는다. 정렬하지 않는다 — 서버 순서가 정본이다
  const runs: WikiNode[][] = [];
  for (const n of nodes) {
    const last = runs.at(-1);
    if (last && last[0].sector === n.sector) last.push(n);
    else runs.push([n]);
  }

  const step = (360 - runs.length * GAP) / nodes.length;
  const placed: Placed[] = [];
  const arcs: Arc[] = [];
  let deg = -90 - step / 2; // 12시에서 시작해 시계 방향

  for (const run of runs) {
    const from = deg + GAP / 2;
    deg += GAP / 2;
    for (const n of run) {
      deg += step;
      const rad = (deg * Math.PI) / 180;
      placed.push({
        ...n,
        angle: deg,
        r: DOT[n.kind as keyof typeof DOT] ?? DOT.content,
        x: C + radius * Math.cos(rad),
        y: C + radius * Math.sin(rad),
      });
    }
    arcs.push({ sector: run[0].sector, from, to: deg + GAP / 2 });
    deg += GAP / 2;
  }
  return { placed, arcs };
}

/** 호 하나의 `d`. 궤도를 구획별로 끊어 그린다. */
function arcPath(radius: number, from: number, to: number): string {
  const a = (from * Math.PI) / 180;
  const b = (to * Math.PI) / 180;
  const large = to - from > 180 ? 1 : 0;
  return [
    `M ${C + radius * Math.cos(a)} ${C + radius * Math.sin(a)}`,
    `A ${radius} ${radius} 0 ${large} 1 ${C + radius * Math.cos(b)} ${C + radius * Math.sin(b)}`,
  ].join(" ");
}

/** 구획 라벨 자리. **구획이 시작하는 빈 각도에 세운다.**
 *
 * 처음에 구획 노드들의 **가운데 각도**에 뒀는데 틀렸다. 구획에 노드가 홀수면 가운데가
 * 노드 위에 정확히 얹혀서 라벨 둘이 겹친다 — `시장과 고객`(노드 셋)이 `시장과 경쟁`
 * 바로 밑에 붙었다. 빈 각도는 노드도 노드 라벨도 없는 유일한 자리라 겹칠 것이 없다.
 *
 * 어느 구획을 가리키는지는 **링이 말한다.** 링을 구획별로 끊어 그려서 라벨이 자기 호의
 * 시작점에 선다 — 라벨만 띄우면 앞뒤 어느 쪽 것인지 모호하다. */
function sectorLabels(arcs: Arc[], radius: number, sectors: Record<string, string>) {
  return arcs.map((a) => {
    const rad = (a.from * Math.PI) / 180;
    return {
      key: a.sector,
      label: sectors[a.sector] ?? a.sector,
      x: C + radius * Math.cos(rad),
      y: C + radius * Math.sin(rad) + 4,
    };
  });
}

export function Orbit({
  nodes,
  sectors,
  selected,
  onSelect,
}: {
  nodes: WikiNode[];
  sectors: Record<string, string>;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const center = nodes.find((n) => n.kind === "identity");
  const inner = place(
    nodes.filter((n) => n.kind === "company"),
    RING.company,
  );
  const outer = place(
    nodes.filter((n) => n.kind === "content"),
    RING.content,
  );
  const labels = sectorLabels(outer.arcs, RING.content + 52, sectors);
  const all = [...inner.placed, ...outer.placed];

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="group"
      aria-label="사업 위키 궤도. 자리 열다섯"
    >
      {/* 궤도 두 줄. **구획별로 끊어 그린다** — 끊긴 자리가 구획 경계다.
        * 원 하나로 그리면 각도가 뜻을 갖는다는 것이 안 보이고, 안쪽 구획 둘은
        * 라벨을 둘 자리가 없어 아예 사라진다. 선이 구조를 말하니 아주 얇다 */}
      {inner.arcs.map((a) => (
        <path key={`ia-${a.sector}`} className={styles.ring} d={arcPath(RING.company, a.from, a.to)} />
      ))}
      {outer.arcs.map((a) => (
        <path key={`oa-${a.sector}`} className={styles.ring} d={arcPath(RING.content, a.from, a.to)} />
      ))}

      {/* 하위 관계(ADR-0017 결정 3). 중심에서 각 자리로. 도트 앞에서 멈춘다 */}
      {all.map((n) => {
        const rad = (n.angle * Math.PI) / 180;
        const from = DOT.identity + 4;
        const to = Math.hypot(n.x - C, n.y - C) - n.r - 4;
        return (
          <line
            key={`spoke-${n.key}`}
            className={styles.spoke}
            x1={C + from * Math.cos(rad)}
            y1={C + from * Math.sin(rad)}
            x2={C + to * Math.cos(rad)}
            y2={C + to * Math.sin(rad)}
          />
        );
      })}

      {/* 구획 라벨 넷. 각도가 뜻을 갖는다는 것을 이게 말한다 */}
      {labels.map((s) => (
        <text key={s.key} className={styles.sector} x={s.x} y={s.y}>
          {s.label}
        </text>
      ))}

      {center && (
        <Dot
          node={{ ...center, x: C, y: C, angle: 0, r: DOT.identity }}
          selected={selected === center.key}
          onSelect={onSelect}
          labelInside
        />
      )}
      {all.map((n) => (
        <Dot key={n.key} node={n} selected={selected === n.key} onSelect={onSelect} />
      ))}
    </svg>
  );
}

/** 자리 하나. **키보드로 갈 수 있어야 한다** — 궤도가 유일한 길이라 마우스 전용이면 못 연다. */
function Dot({
  node,
  selected,
  onSelect,
  labelInside = false,
}: {
  node: Placed;
  selected: boolean;
  onSelect: (key: string) => void;
  labelInside?: boolean;
}) {
  // 라벨을 궤도 바깥으로 민다. 왼쪽 반원이면 오른쪽 정렬 — 안 그러면 글자가 원 위로 겹친다
  const rad = (node.angle * Math.PI) / 180;
  const out = node.r + 16;
  const lx = labelInside ? node.x : node.x + out * Math.cos(rad);
  const ly = labelInside ? node.y + 5 : node.y + out * Math.sin(rad) + 4;
  const anchor = labelInside
    ? "middle"
    : Math.cos(rad) > 0.25
      ? "start"
      : Math.cos(rad) < -0.25
        ? "end"
        : "middle";

  const state = node.filled ? (node.conflicted ? "손봐야 해요" : "찼어요") : "아직 비어 있어요";

  return (
    <g
      className={styles.node}
      data-kind={node.kind}
      data-filled={node.filled}
      data-selected={selected}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${node.label} — ${state}`}
      onClick={() => onSelect(node.key)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(node.key);
        }
      }}
    >
      {selected && <circle className={styles.halo} cx={node.x} cy={node.y} r={node.r + 7} />}
      <circle className={styles.dot} cx={node.x} cy={node.y} r={node.r} />

      {/* 손봐야 하는 자리. **노드 색은 그대로 두고 배지 점을 하나 더 붙인다**(DESIGN.md §4.1).
       * 테두리를 표면색으로 둘러 도트에서 떨어져 보이게 한다 */}
      {node.conflicted && (
        <circle
          className={styles.badge}
          cx={node.x + node.r * 0.72}
          cy={node.y - node.r * 0.72}
          r={5}
        />
      )}

      <text className={labelInside ? styles.centerLabel : styles.label} x={lx} y={ly} textAnchor={anchor}>
        {node.label}
      </text>
    </g>
  );
}
