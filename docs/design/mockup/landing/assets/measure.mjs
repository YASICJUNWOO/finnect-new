// 랜딩 시안 여섯을 실측해 대조표로 뽑는다.
// 사용: `node assets/measure.mjs` (landing 폴더에서)
//
// 왜 이 항목들인가 — 전부 DESIGN.md 가 숫자로 못 박은 규칙이다.
//   본문 최소      §8.2 "본문 16px 이상". 현행이 14·15px 을 쓰는 것을 §10.2 가 지적했다
//   최장 줄        §8.2 "62ch 이하"
//   CTA 높이       §8.2 "터치 타깃 44px 이상"
//   채운 버튼      §5.4-5 · §8.1-6 "화면에 하나나 둘"
//   크기 종류      §4.2 "스케일은 일곱 단계"
// 체감("빽빽해 보인다")을 적지 않기 위한 것이다.
//
// 재는 방법에서 두 번 틀렸고 그 자리를 적어 둔다 —
//  1) 처음엔 **모든** 글자의 최소 크기를 쟀다. 배지 안의 11px 숫자가 잡혀 여섯 시안이 전부
//     "본문 11px" 로 나왔다. 본문은 산문이다 — 제 텍스트가 25자 넘는 요소만 본다.
//  2) 줄길이를 canvas 의 "0" 폭으로 나눴다. 한글은 "0" 의 두 배쯤 되는 전각이라 값이 두 배로 부풀었다.
//     지금은 Range.getClientRects() 로 **실제 렌더된 줄**을 받아 글자 폭을 평균 낸다.
import { chromium } from "playwright";

const SIZE = { width: 1600, height: 1000 };
const FILES = [
  ["현행", "base.html"],
  ["B 관제", "b-console.html"],
  ["C 던지기", "c-drop.html"],
  ["D 면", "d-plane.html"],
  ["E 조립", "e-assemble.html"],
  ["F 현행+", "f-plus.html"],
];
const CTA_TEXT = "파일 올리고 시작하기";

const probe = ({ foldH, ctaText }) => {
  const inHarness = (el) => el.closest(".hns, .hns-out") !== null;

  const rgb = (s) => {
    const m = String(s).match(/[\d.]+/g);
    return m ? m.slice(0, 3).map(Number) : [255, 255, 255];
  };
  const alpha = (s) => {
    const m = String(s).match(/[\d.]+/g);
    return m && m.length > 3 ? +m[3] : 1;
  };
  const lum = (c) => {
    const s = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2];
  };
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  const pageBg = rgb(getComputedStyle(document.body).backgroundColor);

  let minProse = Infinity, minProseTag = null, minAny = Infinity, maxLine = 0, filled = 0, minHit = Infinity;
  const sizes = new Set();

  for (const el of document.querySelectorAll("body *")) {
    if (inHarness(el)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const r = el.getBoundingClientRect();
    // 부모가 숨긴 요소는 자기 display 가 살아 있어도 화면에 없다. 크기로 거른다 —
    // 안 거르면 C 던지기의 완료 화면 버튼이 '채운 버튼'으로 세어져 셋이 된다(실제로 그랬다)
    if (r.width < 1 || r.height < 1) continue;

    // 제 텍스트를 직접 가진 요소만 글자 계측 대상이다 (래퍼가 섞이면 값이 흐려진다)
    const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3 && n.textContent.trim());
    const text = own.map((n) => n.textContent.trim()).join("");
    if (text) {
      const fs = parseFloat(cs.fontSize);
      minAny = Math.min(minAny, fs);
      sizes.add(Math.round(fs * 10) / 10);
      if (text.length >= 25) {
        // 어느 요소가 최솟값을 냈는지 같이 들고 나간다 — 숫자만 보면 "본문이 14px"로 읽히는데
        // 실제로는 푸터 한 줄인 경우가 있다. 그 구분을 표 밑에 적기 위한 것이다
        if (fs < minProse) {
          minProse = fs;
          minProseTag = el.tagName.toLowerCase() +
            (typeof el.className === "string" && el.className.trim()
              ? "." + el.className.trim().split(/\s+/)[0] : "");
        }
        // 실제 렌더된 줄. 여러 줄이면 rect 가 줄마다 하나씩 나온다
        const range = document.createRange();
        range.selectNodeContents(el);
        const rects = Array.from(range.getClientRects()).filter((x) => x.width > 1);
        if (rects.length) {
          const total = rects.reduce((s, x) => s + x.width, 0);
          const avgChar = total / text.length;          // 한글·라틴이 섞인 이 글의 실제 평균 글자 폭
          const widest = Math.max(...rects.map((x) => x.width));
          if (avgChar > 0) maxLine = Math.max(maxLine, widest / avgChar);
        }
      }
    }

    if (el.matches("a, button, input, [role=button]")) {
      // 인라인 링크는 타깃 규칙의 대상이 아니다 — 블록으로 앉은 조작 요소만 본다
      if (r.height > 0 && cs.display !== "inline") minHit = Math.min(minHit, Math.round(r.height));
      // "채워진" 은 면이 있다는 뜻이다. 흰 카드 위의 흰 버튼은 채운 것이 아니다
      if (alpha(cs.backgroundColor) > 0.9 && ratio(rgb(cs.backgroundColor), pageBg) >= 2) filled++;
    }
  }

  let cta = null;
  for (const el of document.querySelectorAll("a, button")) {
    if (inHarness(el)) continue;
    if (el.textContent.trim() === ctaText) {
      const r = el.getBoundingClientRect();
      cta = { top: Math.round(r.top + scrollY), h: Math.round(r.height) };
      break;
    }
  }

  return {
    pageH: Math.round(document.documentElement.scrollHeight),
    ctaTop: cta ? cta.top : null,
    ctaH: cta ? cta.h : null,
    inFold: cta ? cta.top + cta.h <= foldH : false,
    minProse: minProse === Infinity ? null : Math.round(minProse * 10) / 10,
    minProseTag,
    minAny: minAny === Infinity ? null : Math.round(minAny * 10) / 10,
    maxLine: Math.round(maxLine),
    sizes: sizes.size,
    filled,
    minHit: minHit === Infinity ? null : minHit,
  };
};

const browser = await chromium.launch();
// 모션을 끈 상태로 잰다 — 진입 애니메이션 도중에 재면 C·E 가 다른 값을 준다
const page = await browser.newPage({ viewport: SIZE, locale: "ko-KR", reducedMotion: "reduce" });

const rows = [];
for (const [label, file] of FILES) {
  await page.goto("file://" + process.cwd() + "/" + file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(350);
  rows.push([label, await page.evaluate(probe, { foldH: SIZE.height, ctaText: CTA_TEXT })]);
}
await browser.close();

const COLS = [
  ["화면 세로", (m) => m.pageH, true],
  ["CTA 세로", (m) => m.ctaTop, true],
  ["첫 화면 안", (m) => (m.inFold ? "예" : "아니오"), false],
  ["CTA 높이", (m) => m.ctaH + "px" + (m.ctaH < 44 ? " ⚠" : ""), false],
  ["본문 최소", (m) => m.minProse + "px" + (m.minProse < 16 ? " ⚠" : ""), false],
  ["최장 줄", (m) => m.maxLine + "자" + (m.maxLine > 62 ? " ⚠" : ""), false],
  ["크기 종류", (m) => m.sizes + (m.sizes > 7 ? " ⚠" : ""), false],
  ["채운 버튼", (m) => m.filled + (m.filled > 2 ? " ⚠" : ""), false],
  ["최소 타깃", (m) => m.minHit + "px" + (m.minHit < 44 ? " ⚠" : ""), false],
];

const W = 12;
const pad = (s) => String(s).padStart(W);
console.log("".padEnd(10) + COLS.map((c) => pad(c[0])).join(""));
const base = rows[0][1];
for (const [label, m] of rows) {
  const cells = COLS.map(([, get, diff]) => {
    let s = String(get(m));
    if (diff && m !== base) {
      const d = get(m) - get(base);
      if (d) s += ` ${d > 0 ? "+" : ""}${d}`;
    }
    return pad(s);
  });
  console.log(label.padEnd(10) + cells.join(""));
}
console.log("\n⚠ 는 DESIGN.md 기준 미달 — 본문 16px(§8.2) · 62자(§8.2 62ch) · 일곱 단계(§4.2) · 44px(§8.2) · 채운 버튼 둘(§8.1-6)");
console.log("`최소 타깃` 은 블록으로 앉은 조작 요소만 본다. 인라인 텍스트 링크는 이 규칙의 대상이 아니다.\n");

// 숫자만 보면 "본문이 14px" 로 읽히는데 실제로는 푸터 한 줄인 경우가 있다. 어느 요소인지 같이 적는다
console.log("본문 최소를 낸 자리 · 최소 타깃을 낸 높이");
for (const [label, m] of rows) {
  console.log(`  ${label.padEnd(10)} 본문 ${String(m.minProse + "px").padStart(7)} ← ${(m.minProseTag || "?").padEnd(16)} 최소 타깃 ${m.minHit}px`);
}
