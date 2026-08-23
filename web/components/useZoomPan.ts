"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Box, Point } from "@/lib/graph";

/** SVG 판을 확대·축소하고 끌어서 옮긴다. **viewBox 하나만 바꾼다.**
 *
 * `transform` 으로 확대하면 선 굵기와 이름표가 배율만큼 같이 굵어지는데 이 그래프는
 * 가지가 1px 이라 3배에서 3px 이 되어 그물로 읽힌다. viewBox 를 좁히면 화면에 그리는
 * 크기는 그대로이므로 **선은 1px 로 남고 점 사이만 벌어진다** — 확대의 목적이 겹쳐서
 * 못 읽던 이름을 읽는 것이니 이쪽이 맞다.
 *
 * ## 축소는 전체 보기가 하한이다
 *
 * `fit()` 이 이미 내용에 딱 맞춘 틀을 준다. 그보다 더 줄이면 여백만 늘고 점은 작아져서
 * 보이는 것이 줄어든다 — **「전체보다 작게」에는 뜻이 없다.**
 *
 * ## 휠을 통째로 뺏지 않는다
 *
 * 일반 휠은 페이지 스크롤로 남기고 `Ctrl`·`⌘` 이 눌렸을 때만 확대한다. 캔버스가 세로로
 * 크고 좁은 화면에서는 화면을 거의 채워서, 휠을 뺏으면 그 위에서 페이지를 못 내린다.
 * **트랙패드 핀치가 `ctrlKey` 붙은 wheel 로 오므로** 이 조건 하나가 둘을 같이 받는다.
 * 휠이 없는 입력(마우스 휠만 있는 손, 키보드)은 버튼이 받는다. */

/** 최대 배율. 자리 쉰여섯이 가장 빽빽한 곳에서 이름표가 갈라지는 지점이다 */
const MAX = 6;

/** 이 아래로는 확대한 것으로 안 친다. 부동소수 오차를 넘기려는 값이다 */
const ZOOMED = 1.02;

/** 끌었다고 볼 최소 거리(px). **이보다 짧으면 클릭이다** — 손이 떨려서 1~2px 이
 * 움직이는 일이 흔하고, 그걸 끌기로 치면 자리를 못 고른다 */
const DRAG = 4;

/** 틀 안에 가둔다. **밖으로 나가면 빈 여백이 보이고 되돌릴 길이 안 보인다** */
function clamp(v: Box, box: Box): Box {
  const width = Math.min(v.width, box.width);
  const height = Math.min(v.height, box.height);
  return {
    width,
    height,
    x: Math.max(box.x, Math.min(box.x + box.width - width, v.x)),
    y: Math.max(box.y, Math.min(box.y + box.height - height, v.y)),
  };
}

/** 한 점을 제자리에 붙들어 둔 채 배율만 바꾼 틀.
 *
 * **고정점이 있어야 «가리킨 곳이 커진다»가 된다.** 중심만 기준으로 확대하면 보려던
 * 자리가 화면 밖으로 밀려나고, 사용자는 확대한 뒤 그것을 다시 찾아야 한다. */
function zoomTo(view: Box, box: Box, k: number, at: Point): Box {
  const next = Math.max(1, Math.min(MAX, k));
  const width = box.width / next;
  const height = box.height / next;
  // 고정점이 틀 안에서 차지하던 상대 위치를 그대로 유지한다
  const rx = (at.x - view.x) / view.width;
  const ry = (at.y - view.y) / view.height;
  return clamp({ x: at.x - rx * width, y: at.y - ry * height, width, height }, box);
}

function span(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function mid(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

export type ZoomPan = {
  ref: React.RefObject<SVGSVGElement | null>;
  /** `viewBox` 에 그대로 넣는 값 */
  view: Box;
  /** 1 이 전체 보기다 */
  zoom: number;
  zoomed: boolean;
  panning: boolean;
  /** 판 가운데를 붙들고 배율을 곱한다. 버튼이 부른다 */
  zoomBy: (factor: number) => void;
  reset: () => void;
  onPointerDown: (e: React.PointerEvent<SVGSVGElement>) => void;
  /** 끌고 나서 손을 뗄 때 딸려 오는 클릭을 막는다 */
  onClickCapture: (e: React.MouseEvent<SVGSVGElement>) => void;
};

export function useZoomPan(box: Box): ZoomPan {
  const ref = useRef<SVGSVGElement | null>(null);
  const [view, setView] = useState<Box>(box);
  const [panning, setPanning] = useState(false);
  const [seen, setSeen] = useState<Box>(box);

  // 판이 바뀌면(파일을 더 올려 자리가 늘면) 전체 보기로 되돌린다. **옛 틀을 그대로
  // 두면 새 배치의 엉뚱한 구석을 확대한 채로 뜬다.**
  //
  // `useEffect` 가 아니라 렌더 중에 맞춘다 — effect 로 하면 옛 틀로 한 번 그리고
  // 다음 프레임에 되돌아와서 화면이 깜빡인다. React 가 이 자리를 위해 열어 둔
  // 길이고(같은 컴포넌트의 상태를 렌더 중에 고치는 것), 아래 `return` 전에 다시
  // 렌더돼 옛 틀은 화면에 안 나간다.
  if (seen !== box) {
    setSeen(box);
    setView(box);
  }

  /** 화면 좌표를 판 좌표로. **`getBoundingClientRect` 를 매번 다시 잰다** —
   * 사이드바가 접히거나 패널이 열리면 SVG 폭이 바뀌는데 캐시하면 그때부터 어긋난다.
   *
   * `preserveAspectRatio` 가 `meet` 이지만 레터박스를 안 따진다 — SVG 높이가 `auto`
   * 라 요소 자체가 늘 viewBox 비율이고, 확대해도 비율을 유지하므로 여백이 안 생긴다. */
  const toLocal = useCallback((cx: number, cy: number, v: Box): Point => {
    const el = ref.current;
    if (!el) return { x: v.x + v.width / 2, y: v.y + v.height / 2 };
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return { x: v.x + v.width / 2, y: v.y + v.height / 2 };
    return {
      x: v.x + ((cx - r.left) / r.width) * v.width,
      y: v.y + ((cy - r.top) / r.height) * v.height,
    };
  }, []);

  /** 화면 거리를 판 거리로. 끌기와 핀치가 같이 쓴다 */
  const ratio = useCallback((v: Box): number => {
    const el = ref.current;
    const r = el?.getBoundingClientRect();
    return r && r.width > 0 ? v.width / r.width : 1;
  }, []);

  // ── 휠 · 트랙패드 핀치 ────────────────────────────────────
  //
  // **React 의 `onWheel` 을 안 쓴다.** 위임된 리스너가 passive 로 붙어서
  // `preventDefault()` 가 무시되고 콘솔 경고만 남는다 — 페이지가 같이 스크롤된다.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setView((v) => {
        const at = toLocal(e.clientX, e.clientY, v);
        // 지수로 곱한다. **덧셈으로 하면 확대할수록 한 칸이 잘게 느껴진다**
        return zoomTo(v, box, (box.width / v.width) * Math.exp(-e.deltaY * 0.01), at);
      });
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [box, toLocal]);

  // ── 끌기와 두 손가락 핀치 ─────────────────────────────────

  const pointers = useRef(new Map<number, Point>());
  const pinch = useRef<number | null>(null);
  /** 누른 자리. **총 이동 거리를 여기서 잰다** — click 이벤트의 `movementX` 는 직전
   * 한 칸만 담아서, 천천히 끌면 매 칸이 1px 이라 끌기가 클릭으로 새어 나간다 */
  const start = useRef<Point | null>(null);
  const dragged = useRef(false);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      // 마우스는 왼쪽 버튼만. 오른쪽은 브라우저 메뉴 몫이다
      if (e.pointerType === "mouse" && e.button !== 0) return;
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      start.current = { x: e.clientX, y: e.clientY };
      dragged.current = false;
      // **포인터 캡처를 안 건다.** SVG 루트가 캡처하면 뒤따르는 click 이 거기로
      // 리타깃돼서 자리 점의 `onClick` 이 아예 안 불린다 — 대신 아래에서 창을 듣는다
      if (pointers.current.size === 2) {
        const [a, b] = [...pointers.current.values()];
        pinch.current = span(a, b);
      }
      setPanning(true);
    },
    [],
  );

  // **창을 늘 듣는다. `panning` 을 조건으로 걸지 않는다** — 그러면 누른 뒤 리렌더가
  // 끝나야 리스너가 붙어서 그 사이의 움직임이 통째로 씹힌다(빠르게 끌면 첫 수십 px 이
  // 사라진다). 누르지 않았을 때는 첫 줄에서 바로 돌아오므로 값이 없다.
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const prev = pointers.current.get(e.pointerId);
      if (!prev) return;
      const now = { x: e.clientX, y: e.clientY };
      pointers.current.set(e.pointerId, now);

      const from = start.current;
      if (from && Math.hypot(now.x - from.x, now.y - from.y) > DRAG) dragged.current = true;

      // 두 손가락이면 핀치다. 벌린 만큼 확대하고 두 손가락 가운데를 붙든다
      if (pointers.current.size >= 2) {
        const [a, b] = [...pointers.current.values()];
        const dist = span(a, b);
        const was = pinch.current;
        pinch.current = dist;
        if (!was || was < 1 || dist < 1) return;
        setView((v) => zoomTo(v, box, (box.width / v.width) * (dist / was), toLocal(mid(a, b).x, mid(a, b).y, v)));
        return;
      }

      // 한 손가락(또는 마우스)이면 옮긴다. **전체 보기에서는 옮길 것이 없다** —
      // 여기서 잡아 두면 좁은 화면에서 캔버스 위 세로 스크롤이 죽는다
      setView((v) => {
        if (v.width >= box.width) return v;
        const k = ratio(v);
        return clamp(
          { ...v, x: v.x - (now.x - prev.x) * k, y: v.y - (now.y - prev.y) * k },
          box,
        );
      });
    };

    const onUp = (e: PointerEvent) => {
      pointers.current.delete(e.pointerId);
      if (pointers.current.size < 2) pinch.current = null;
      if (pointers.current.size === 0) setPanning(false);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [box, ratio, toLocal]);

  /** 끌고 나서 손을 뗄 때 자리 점이 눌리는 것을 막는다. **끌기의 끝은 선택이 아니다** */
  const onClickCapture = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragged.current) return;
    e.stopPropagation();
    e.preventDefault();
  }, []);

  const zoomBy = useCallback(
    (factor: number) => {
      setView((v) =>
        zoomTo(v, box, (box.width / v.width) * factor, {
          x: v.x + v.width / 2,
          y: v.y + v.height / 2,
        }),
      );
    },
    [box],
  );

  const reset = useCallback(() => setView(box), [box]);

  const zoom = box.width / view.width;
  return {
    ref,
    view,
    zoom,
    zoomed: zoom > ZOOMED,
    panning,
    zoomBy,
    reset,
    onPointerDown,
    onClickCapture,
  };
}
