"use client";

import type { WikiSpot } from "@/lib/wiki";
import styles from "./Orbit.module.css";

/** 위키 방사형. **힘 기반 배치를 쓰지 않는다**(ADR-0017 · ADR-0052).
 *
 * 자리가 마흔일곱이고 어느 폴더에 들어갈지가 표로 정해져 있어서 배치를 물리에 맡길
 * 이유가 없다. 자리를 고정하면 **두 번째 볼 때 찾는다** — 물리 배치는 열 때마다 모양이
 * 달라진다.
 *
 * ## 각도가 뜻하는 것이 바뀌었다
 *
 * 2026-08-22 까지 구획은 우리가 지어낸 여섯(`registration` · `principal` …)이었고 점이
 * 열다섯이었다. 지금은 **기획 문서가 그린 폴더 열**이고 점이 마흔일곱이다([ADR-0052](../../docs/adr/0052-위키-자리를-기획-트리로-바꾸고-구획을-폴더로-세운다.md)).
 * 구획 크기는 자리 수에 비례한다 — `Plan/` 일곱이 `Competitor/` 둘보다 넓다.
 *
 * **링이 하나다.** 안팎을 가르던 것이 `kind` 였는데 트리 자리 하나가 value 와 event 를
 * 같이 받아서(`Financial/매출.md`) 어느 링인지 정해지지 않는다.
 *
 * ## 글자로 서는 것은 폴더 이름뿐이다
 *
 * 점 마흔일곱을 한 링에 놓으면 점 사이가 29px 이라 **라벨 마흔일곱이 원 밖에 안 들어간다.**
 * 자리 이름은 고르거나 올렸을 때 그 점 옆에 뜨고, 전부는 아래 패널과 셈이 말한다.
 * 궤도 열다섯은 이름이 전부 보였다 — 그것이 점을 세 배로 늘린 값이다.
 *
 * **색을 안 쓴다**(ADR-0052 포기 ④). 폴더 구획이 이미 묶는 일을 해서 분류색이 같은 말을
 * 두 번 하게 된다. 상태 셋은 채움·선·크기로 가른다 — 색조 하나에 뜻 둘을 얹지 않는다.
 *
 * **관련 선(점선)이 없다.** 자리 간 연결(F1-1-6)이 아직 데이터에 없어서다. 없는 관계를
 * 그리지 않는다 — 같은 폴더에 있다고 이어 버리면 사용자가 근거 있는 연결로 읽는다. */

const SIZE = 720;
const C = SIZE / 2;

/** 점이 앉는 반지름과 폴더 이름이 앉는 반지름. */
const RING = 262;
const LABEL = RING + 52;

/** 점 크기. **채울 topic 이 없는 자리는 작다** — 상태를 색 대신 크기로도 말한다. */
const DOT = { filled: 7, empty: 6, none: 4 } as const;

/** 구획 사이를 벌리는 각도. **이게 없으면 마흔일곱이 고르게 퍼져 구획이 안 보인다.** */
const GAP = 9;

type Placed = WikiSpot & { x: number; y: number; angle: number; r: number; state: string };
/** 폴더 하나가 링에서 차지하는 각도 범위. **링을 이 단위로 끊어 그린다.** */
type Arc = { folder: string; from: number; to: number; mid: number; done: number; total: number };

function stateOf(spot: WikiSpot): keyof typeof DOT {
  if (spot.filled) return "filled";
  // 채울 topic 이 아예 없는 자리. **파일을 더 올려도 안 찬다** — 「아직」이 아니다
  return spot.gap ? "none" : "empty";
}

/** 자리를 잡는다. **폴더끼리 붙여 두고 사이만 벌린다.**
 *
 * 서버가 준 순서가 이미 폴더별로 묶여 있다(`export.TREE`). 여기서 다시 정렬하면 그
 * 순서가 두 곳에 살게 되고, 한쪽만 고쳐지는 날이 온다. */
function place(spots: WikiSpot[]): { placed: Placed[]; arcs: Arc[] } {
  if (spots.length === 0) return { placed: [], arcs: [] };

  // 이웃한 같은 폴더끼리 묶는다. 정렬하지 않는다 — 서버 순서가 정본이다
  const runs: WikiSpot[][] = [];
  for (const s of spots) {
    const last = runs.at(-1);
    if (last && last[0].folder === s.folder) last.push(s);
    else runs.push([s]);
  }

  const step = (360 - runs.length * GAP) / spots.length;
  const placed: Placed[] = [];
  const arcs: Arc[] = [];
  let deg = -90 - step / 2; // 12시에서 시작해 시계 방향

  for (const run of runs) {
    const from = deg + GAP / 2;
    deg += GAP / 2;
    for (const s of run) {
      deg += step;
      const rad = (deg * Math.PI) / 180;
      const state = stateOf(s);
      placed.push({
        ...s,
        angle: deg,
        r: DOT[state],
        state,
        x: C + RING * Math.cos(rad),
        y: C + RING * Math.sin(rad),
      });
    }
    const to = deg + GAP / 2;
    arcs.push({
      folder: run[0].folder,
      from,
      to,
      mid: (from + to) / 2,
      done: run.filter((s) => s.filled).length,
      total: run.length,
    });
    deg += GAP / 2;
  }
  return { placed, arcs };
}

/** 호 하나의 `d`. 링을 구획별로 끊어 그린다. */
function arcPath(radius: number, from: number, to: number): string {
  const a = (from * Math.PI) / 180;
  const b = (to * Math.PI) / 180;
  const large = to - from > 180 ? 1 : 0;
  return [
    `M ${C + radius * Math.cos(a)} ${C + radius * Math.sin(a)}`,
    `A ${radius} ${radius} 0 ${large} 1 ${C + radius * Math.cos(b)} ${C + radius * Math.sin(b)}`,
  ].join(" ");
}

/** 글자를 어느 쪽으로 붙일지. 왼쪽 반원이면 오른쪽 정렬 — 안 그러면 원 위로 겹친다. */
function anchorAt(rad: number): "start" | "middle" | "end" {
  const c = Math.cos(rad);
  return c > 0.25 ? "start" : c < -0.25 ? "end" : "middle";
}

export function Orbit({
  spots,
  folders,
  filled,
  total,
  selected,
  onSelect,
}: {
  spots: WikiSpot[];
  folders: Record<string, string>;
  filled: number;
  total: number;
  selected: string | null;
  onSelect: (path: string) => void;
}) {
  const { placed, arcs } = place(spots);

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="group"
      aria-label={`내 사업 위키. 폴더 ${arcs.length}개에 자리 ${total}개`}
    >
      {/* 살. **폴더마다 하나씩이다** — 자리마다 그으면 마흔일곱 줄이 별 모양이 된다.
        * 중심에서 그 구획의 가운데 각도로 나간다. 선이 구조를 말하니 아주 얇다 */}
      {arcs.map((a) => {
        const rad = (a.mid * Math.PI) / 180;
        return (
          <line
            key={`spoke-${a.folder}`}
            className={styles.spoke}
            x1={C + 46 * Math.cos(rad)}
            y1={C + 46 * Math.sin(rad)}
            x2={C + (RING - 16) * Math.cos(rad)}
            y2={C + (RING - 16) * Math.sin(rad)}
          />
        );
      })}

      {/* 링. **구획별로 끊어 그린다** — 끊긴 자리가 구획 경계다 */}
      {arcs.map((a) => (
        <path key={`arc-${a.folder}`} className={styles.ring} d={arcPath(RING, a.from, a.to)} />
      ))}

      {/* 폴더 이름과 셈. **글자로 서는 유일한 것이다.** 막대를 만들지 않는다(§7) */}
      {arcs.map((a) => {
        const rad = (a.mid * Math.PI) / 180;
        const x = C + LABEL * Math.cos(rad);
        const y = C + LABEL * Math.sin(rad);
        return (
          <g key={`label-${a.folder}`} textAnchor={anchorAt(rad)}>
            <text className={styles.folder} x={x} y={y}>
              {folders[a.folder] ?? a.folder}
            </text>
            <text className={styles.count} x={x} y={y + 17}>
              {a.done}/{a.total}
            </text>
          </g>
        );
      })}

      {/* 중심. 노드가 아니라 표지다 — 누를 것이 없다 */}
      <circle className={styles.hub} cx={C} cy={C} r={44} />
      <text className={styles.hubTitle} x={C} y={C - 4} textAnchor="middle">
        내 사업
      </text>
      <text className={styles.hubCount} x={C} y={C + 16} textAnchor="middle">
        {filled}/{total}
      </text>

      {placed.map((s) => (
        <Dot key={s.path} spot={s} selected={selected === s.path} onSelect={onSelect} />
      ))}
    </svg>
  );
}

/** 자리 하나. **키보드로 갈 수 있어야 한다** — 이 그래프가 유일한 길이라 마우스 전용이면 못 연다. */
function Dot({
  spot,
  selected,
  onSelect,
}: {
  spot: Placed;
  selected: boolean;
  onSelect: (path: string) => void;
}) {
  const rad = (spot.angle * Math.PI) / 180;
  const out = spot.r + 14;
  const state =
    spot.state === "filled"
      ? spot.conflicted
        ? "손봐야 해요"
        : "찼어요"
      : spot.state === "none"
        ? `아직 안 채워요 — ${spot.gap}`
        : "아직 비었어요";

  return (
    <g
      className={styles.node}
      data-state={spot.state}
      data-selected={selected}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${spot.title} — ${state}`}
      onClick={() => onSelect(spot.path)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(spot.path);
        }
      }}
    >
      {/* 고른 자리의 링. 색이 아니라 테두리로 말한다 */}
      {selected && <circle className={styles.halo} cx={spot.x} cy={spot.y} r={spot.r + 5} />}
      <circle className={styles.dot} cx={spot.x} cy={spot.y} r={spot.r} />

      {/* 손봐야 하는 자리의 배지. **점 색은 그대로 둔다**(DESIGN.md §2) */}
      {spot.conflicted && (
        <circle
          className={styles.badge}
          cx={spot.x + spot.r * 0.8}
          cy={spot.y - spot.r * 0.8}
          r={3.5}
        />
      )}

      {/* 이름. **고르거나 올렸을 때만 뜬다** — 마흔일곱을 늘 세우면 원 밖에 안 들어간다.
        * CSS 가 `:hover` 와 `[data-selected]` 에서 켠다 */}
      <text
        className={styles.label}
        x={spot.x + out * Math.cos(rad)}
        y={spot.y + out * Math.sin(rad) + 4}
        textAnchor={anchorAt(rad)}
      >
        {spot.title}
      </text>
    </g>
  );
}
