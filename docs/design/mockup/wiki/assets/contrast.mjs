// 시안 여섯의 **실제로 렌더된** 글자 색을 전부 훑어 WCAG 대비비를 잰다.
// 사용: `node assets/contrast.mjs` (wiki 폴더에서)
//
// **어두운 시안 넷이 있다**(G2·G3·G4 · 그리고 G2 의 좌측 조작기). 어두운 면 위의
// 글자는 배경이 그라데이션이거나 canvas 인 경우가 있어 «잴 수 없음»으로 나온다 —
// 조용히 빼지 않고 그렇게 표시한다. 빼면 통과한 것처럼 보인다.
//
// 손으로 적은 색 목록(PAIRS)을 쓰지 않는 이유 — 목록은 금방 낡고, 정작 미달인 자리는
// 목록에 없던 tier 인 경우가 많다. 화면에서 직접 읽으면 그 일이 없다.
//
// 잴 수 없는 자리도 있다. 캔버스나 그라데이션 위에 글자가 앉으면 배경색이 픽셀마다 다르다.
// 그런 자리는 **버리지 않고 따로 표시한다** — 조용히 빼면 통과한 것처럼 보인다.
import { chromium } from "playwright";

// **시안 목록을 여기 적지 않는다.** `variants.js` 를 읽는다 — switch·harness·index 와
// 같은 것을 봐야 한 곳만 고치면 된다.
import { readFileSync } from "node:fs";
const src = readFileSync(new URL("../variants.js", import.meta.url), "utf8");
const win = { VARIANTS: null };
new Function("window", src)(win);
const FILES = win.VARIANTS.map((v) => [v.label, v.file]);

const probe = () => {
  const rgb = (s) => {
    const m = String(s).match(/[\d.]+/g);
    return m ? m.slice(0, 3).map(Number) : null;
  };
  const alpha = (s) => {
    const m = String(s).match(/[\d.]+/g);
    return m && m.length > 3 ? +m[3] : 1;
  };
  const lum = (c) => {
    const s = c.map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2];
  };
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  // 반투명 전경을 배경 위에 합성한다. 안 하면 opacity 걸린 글자가 실제보다 좋게 나온다
  const over = (fg, a, bg) => fg.map((v, i) => v * a + bg[i] * (1 - a));

  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest(".hns, .hns-out")) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;

    const text = Array.from(el.childNodes)
      .filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim()).join(" ");
    if (!text) continue;

    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    // 유효 배경 — 불투명한 배경색이 나올 때까지 위로 올라간다
    let bg = null, painted = false, node = el;
    while (node && node !== document.documentElement.parentNode) {
      const s = getComputedStyle(node);
      if (s.backgroundImage && s.backgroundImage !== "none") painted = true;
      const a = alpha(s.backgroundColor);
      if (a > 0.92) { bg = rgb(s.backgroundColor); break; }
      node = node.parentElement;
    }
    // 캔버스가 뒤에 깔린 자리(B 히어로)도 픽셀 배경이다
    if (el.closest(".hero") && document.querySelector(".hero canvas")) painted = true;
    if (!bg) bg = [255, 255, 255];

    /* **SVG 글자는 `color` 가 아니라 `fill` 로 칠해진다.**
     * `color` 만 읽었더니 G4 의 흰 이름표가 --ink(#222) 로 잡혀 1.19:1 로 나왔다 —
     * 실제로는 #fff 라 통과하는 자리다. 조용히 넘어가면 시안을 잘못 떨어뜨린다. */
    const isSvgText = el.ownerSVGElement != null;
    const paint = isSvgText && cs.fill && cs.fill !== "none" ? cs.fill : cs.color;
    let fg = rgb(paint);
    const op = parseFloat(cs.opacity);
    const fa = alpha(paint) * (isNaN(op) ? 1 : op);
    if (fa < 1) fg = over(fg, fa, bg);

    const fs = parseFloat(cs.fontSize);
    const fw = parseInt(cs.fontWeight, 10) || 400;
    const large = fs >= 24 || (fs >= 18.66 && fw >= 700);   // WCAG 1.4.3 큰 글자
    const need = large ? 3 : 4.5;
    const cr = ratio(fg, bg);

    out.push({
      tag: el.tagName.toLowerCase() + (el.className && typeof el.className === "string"
        ? "." + el.className.trim().split(/\s+/)[0] : ""),
      text: text.slice(0, 26),
      fg: paint, bg: `rgb(${bg.join(", ")})`,
      fs: Math.round(fs * 10) / 10, fw, large, need,
      cr: Math.round(cr * 100) / 100,
      pass: cr >= need,
      painted,
    });
  }
  return out;
};

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1600, height: 1000 }, locale: "ko-KR", reducedMotion: "reduce",
});

let total = 0, hardFail = 0;
for (const [label, file] of FILES) {
  await page.goto("file://" + process.cwd() + "/" + file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  const rows = await page.evaluate(probe);

  const fails = rows.filter((r) => !r.pass);
  const solid = fails.filter((r) => !r.painted);
  const mixed = fails.filter((r) => r.painted);
  total += rows.length;
  hardFail += solid.length;

  console.log(`\n── ${label}  (글자 자리 ${rows.length}개 · 최저 ${Math.min(...rows.map((r) => r.cr)).toFixed(2)}:1)`);
  if (!fails.length) { console.log("   전부 통과"); continue; }

  for (const r of solid) {
    console.log(`   미달  ${r.tag.padEnd(16)} ${String(r.cr).padStart(5)}:1 (기준 ${r.need})  ` +
      `${r.fs}px/${r.fw}  ${r.fg} on ${r.bg}   "${r.text}"`);
  }
  for (const r of mixed) {
    console.log(`   못 잼  ${r.tag.padEnd(16)} ${String(r.cr).padStart(5)}:1  ` +
      `배경이 캔버스·그라데이션이다 — 눈으로 확인할 것   "${r.text}"`);
  }
}

console.log(`\n글자 자리 ${total}개 중 **단색 배경에서** 기준 미달 ${hardFail}건.`);
console.log("기준: 본문 4.5:1 · 큰 글자(24px+ 또는 18.66px+ 700) 3:1 — WCAG 1.4.3");
await browser.close();
