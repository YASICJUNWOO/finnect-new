"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./SvgPages.module.css";

/** rhwp 가 낸 페이지 SVG 를 우리 DOM 에 그린다.
 *
 * **rhwp 의 에디터 크롬을 안 쓰려고 있는 파일이다.** `@rhwp/editor` 는 메뉴 여덟 +
 * 아이콘 툴바 + 서식 리본(합쳐 153~426px)과 눈금자·상태 표시줄을 가진 에디터
 * 전체이고, **그것을 감출 방법을 라이브러리가 안 준다** — `EditorOptions` 에 UI
 * 항목이 없고 postMessage 창구에도 없다. iframe 이 `edwardkim.github.io` 라
 * 우리 CSS 도 못 들어간다. 그래서 `getPageSvg()` 로 페이지만 받아 여기서 그린다.
 *
 * **잘라내기(음수 마진)로 안 한 이유.** 헤더 높이가 폭을 따라 갈린다 —
 * 1400px 에서 153 · 1100 에서 196 · 900~700 에서 264 · 560 에서 311 · 420 에서 426
 * 이다(실측). 양식 단은 유동 폭이라 숫자를 못 박으면 좁아졌을 때 문서 위쪽이
 * 잘린다.
 *
 * **글자가 `<text>` 로 온다**(실측: 한 쪽에 text 694 · path 0). 글자마다 절대 좌표가
 * 박혀 있어서 **폰트가 대체돼도 자리가 안 밀린다.** 대가는 크기다 — 20쪽이 6.9MB 라
 * 전량을 DOM 에 두면 무겁고, 그래서 아래가 보이는 쪽만 그린다. */

/** 한 번에 DOM 에 두는 쪽 수. 보이는 쪽 앞뒤로 이만큼 더 그린다.
 *
 * **0 이면 안 된다** — 스크롤이 그리기를 앞지르면 빈 종이가 지나간다. 1 이면
 * 20쪽 6.9MB 중 최대 세 쪽(약 1MB)만 살아 있다. */
const NEIGHBORS = 1;

export function SvgPages({
  pages,
  label,
}: {
  /** 페이지마다 한 장. `getPageSvg(i)` 가 준 문자열 그대로다 */
  pages: readonly string[];
  /** 스크롤 영역의 이름. 무슨 문서를 보고 있는지 보조기술이 읽는다 */
  label: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // 지금 DOM 에 실물을 둔 쪽. 나머지는 같은 크기의 빈 종이로 자리만 잡는다
  const [live, setLive] = useState<ReadonlySet<number>>(() => new Set([0]));

  // **정제는 한 번만 한다.** 쪽을 오갈 때마다 다시 하면 스크롤이 끊긴다.
  // 쪽 번호를 같이 넘기는 이유는 `sanitize` 의 id 접두사 때문이다
  const clean = useMemo(() => pages.map((svg, i) => sanitize(svg, i)), [pages]);

  // 종이 크기. 첫 장의 viewBox 가 문서 전체의 판형이다
  const paper = useMemo(() => sizeOf(clean[0]), [clean]);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root) return;

    // **문서가 바뀌면 첫 쪽으로 돌아간다.** 안 되돌리면 12쪽짜리를 보다 20쪽짜리를
    // 열었을 때 스크롤이 중간에 남는다
    root.scrollTop = 0;
    setLive(new Set([0]));

    const seen = new Set<number>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const i = Number((e.target as HTMLElement).dataset.page);
          if (e.isIntersecting) seen.add(i);
          else seen.delete(i);
        }
        // 보이는 쪽 앞뒤로 이웃을 더한다
        const next = new Set<number>();
        for (const i of seen) {
          for (let d = -NEIGHBORS; d <= NEIGHBORS; d++) {
            if (i + d >= 0 && i + d < clean.length) next.add(i + d);
          }
        }
        // **아무것도 안 보이면 지금 것을 지키다.** 비우면 스크롤 도중 화면이 빈다
        if (next.size === 0) return;
        setLive((prev) => (sameSet(prev, next) ? prev : next));
      },
      // 화면 밖 반 쪽까지 미리 잡는다. 스크롤이 빠를 때 빈 종이를 덜 본다
      { root, rootMargin: "50% 0px" },
    );

    for (const el of root.querySelectorAll("[data-page]")) io.observe(el);
    return () => io.disconnect();
  }, [clean]);

  return (
    <div ref={scrollRef} className={styles.scroll} tabIndex={0} role="group" aria-label={label}>
      <div className={styles.reel}>
        {clean.map((svg, i) => (
          <div
            key={i}
            data-page={i}
            className={styles.page}
            // 실물이 없을 때도 자리를 차지해야 스크롤 길이가 안 흔들린다
            style={{ aspectRatio: `${paper.w} / ${paper.h}` }}
          >
            {live.has(i) ? (
              // 정제를 거친 문자열이다. 아래 `sanitize` 참조
              <div className={styles.paint} dangerouslySetInnerHTML={{ __html: svg }} />
            ) : (
              // **쪽 번호를 안 적는다.** 곧 실물로 바뀌는 자리라 글자가 깜빡인다
              <span className={styles.blank} aria-hidden />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** 문서에서 온 SVG 를 우리 DOM 에 넣기 전에 손본다. 하는 일이 둘이다 —
 * **실행되는 것을 걷어내고, `id` 를 쪽마다 고유하게 만든다.**
 *
 * ## 왜 `id` 를 고쳐야 하나
 *
 * **rhwp 는 쪽마다 번호를 1부터 다시 매긴다.** 표 셀 클립이 `cell-clip-6` ·
 * `cell-clip-10` 인데 4쪽에도 같은 이름이 있다. iframe 안에서는 한 문서에 SVG 가
 * 하나뿐이라 안 겹쳤지만 **여기서는 쪽 넷이 같은 문서에 산다.**
 *
 * HTML 에서 `id` 는 전역이라 `clip-path="url(#cell-clip-6)"` 는 **문서에서 먼저
 * 나온 것**을 가리킨다. 그래서 4쪽 표가 2쪽의 클립으로 잘려 글자가 통째로 사라졌다.
 * 더 나쁜 것은 **창 관리가 어느 쪽을 DOM 에 둘지 바꾸면 「먼저 나온 것」도 바뀐다는
 * 점이다** — 같은 쪽이 스크롤에 따라 보였다 안 보였다 했다(2026-08-23 실측).
 *
 * `<use href="#…">` 도 같은 함정이라 `href` 계열을 같이 고친다.
 *
 * ## 왜 실행되는 것을 걷어내나
 *
 * **공고 첨부는 외부 데이터다**(CLAUDE.md — 외부 데이터를 믿지 않는다). rhwp 가
 * 스크립트를 낼 이유는 없지만, 낼 수 없다는 보장도 우리에게 없다.
 *
 * **`<img>` 로 안 넣는 이유.** 그러면 브라우저가 SVG 를 비활성으로 그려서 이 일이
 * 공짜인데, 대신 **문서 폰트를 못 가져와 글자가 대체된다.** 그래도 자리는 안 밀리지만
 * 글자 폭이 달라져 표 안에서 넘친다. 인라인으로 넣고 걷어내는 쪽을 골랐다.
 *
 * **정규식으로 안 한다** — `<script` 를 문자열로 지우는 방식은 중첩과 인코딩에서
 * 새고, 브라우저의 파서와 우리 파서가 다르게 읽는 그 틈이 이런 코드가 뚫리는 자리다. */
function sanitize(svg: string, page: number): string {
  if (typeof window === "undefined") return "";

  const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
  if (doc.querySelector("parsererror")) return "";

  const root = doc.documentElement;
  if (root.tagName.toLowerCase() !== "svg") return "";

  // `<foreignObject>` 는 SVG 안에 HTML 을 들이는 문이라 같이 닫는다
  for (const el of root.querySelectorAll("script, foreignObject, a")) el.remove();

  for (const el of root.querySelectorAll("*")) {
    for (const attr of [...el.attributes]) {
      const name = attr.name.toLowerCase();
      // `onload` 계열과 `javascript:` 를 문 자리다
      if (name.startsWith("on") || /(?:^|:)\s*javascript:/i.test(attr.value)) {
        el.removeAttribute(attr.name);
      }
    }
  }

  // ── id 를 쪽마다 고유하게 ──────────────────────────────
  const prefix = `p${page}-`;
  const renamed = new Map<string, string>();
  // **root 자신도 본다** — `querySelectorAll` 은 자기를 안 담는다
  for (const el of [root, ...root.querySelectorAll("[id]")]) {
    const old = el.getAttribute("id");
    if (old) {
      renamed.set(old, prefix + old);
      el.setAttribute("id", prefix + old);
    }
  }

  if (renamed.size > 0) {
    const swap = (id: string) => renamed.get(id) ?? id;
    for (const el of [root, ...root.querySelectorAll("*")]) {
      for (const attr of [...el.attributes]) {
        // `clip-path`·`fill`·`mask`·`filter`·`stroke` 와 인라인 style 이 이 꼴이다
        let next = attr.value.replace(
          /url\(\s*(['"]?)#([^)'"\s]+)\1\s*\)/g,
          (whole, q, id) => (renamed.has(id) ? `url(${q}#${swap(id)}${q})` : whole),
        );
        // `<use href="#glyph">` 계열. 같은 문서 안을 가리킬 때만이다
        const name = attr.name.toLowerCase();
        if ((name === "href" || name.endsWith(":href")) && next.startsWith("#")) {
          next = "#" + swap(next.slice(1));
        }
        if (next !== attr.value) el.setAttribute(attr.name, next);
      }
    }
    // `<style>` 안에도 `url(#…)` 이 있을 수 있다. 지금 rhwp 는 안 내지만
    // 내기 시작하면 조용히 같은 버그가 돌아온다
    for (const style of root.querySelectorAll("style")) {
      style.textContent = (style.textContent ?? "").replace(
        /url\(\s*(['"]?)#([^)'"\s]+)\1\s*\)/g,
        (whole, q, id) => (renamed.has(id) ? `url(${q}#${swap(id)}${q})` : whole),
      );
    }
  }

  // 크기는 우리 CSS 가 정한다. 속성으로 박혀 있으면 폭 맞춤이 안 된다
  root.removeAttribute("width");
  root.removeAttribute("height");
  return new XMLSerializer().serializeToString(root);
}

/** 종이 판형. `viewBox` 가 없으면 A4 로 둔다 — 없는 쪽이 이상한 것이라 추측이
 * 아니라 마지막 방어다. */
function sizeOf(svg: string | undefined): { w: number; h: number } {
  const box = svg?.match(/viewBox="([\d.\-\s]+)"/)?.[1]?.trim().split(/\s+/);
  if (box?.length === 4) {
    const w = Number(box[2]);
    const h = Number(box[3]);
    if (w > 0 && h > 0) return { w, h };
  }
  return { w: 210, h: 297 };
}

function sameSet(a: ReadonlySet<number>, b: ReadonlySet<number>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}
