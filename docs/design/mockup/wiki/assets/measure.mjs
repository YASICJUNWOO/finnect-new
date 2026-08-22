// 위키 시안 열하나를 실측해 대조표로 뽑는다.
// 사용: `node assets/measure.mjs` (wiki 폴더에서 · `npm i --no-save playwright` 필요)
//
// **시안 목록을 여기 적지 않는다.** `variants.js` 를 읽는다 — switch·harness·index 와
// 같은 것을 봐야 한 곳만 고치면 된다.
//
// 왜 이 항목들인가 — 전부 DESIGN.md 나 이 하네스의 논지가 숫자로 못 박은 것이다.
//   노드 · 연결 · 이름표   이 하네스의 논지. 「무엇을 노드로 그리는가」가 갈리는 축이다
//   본문 최소             §3 "14px 과 15px 이 없는 것이 요점이다. 본문은 16px 이상이다"
//   최장 줄               §5 "줄길이는 62ch 이하"
//   최소 타깃             §5 "터치 타깃은 44px 이상"
//   그림자                §6 "모든 카드에 같은 옅은 그림자를 바르지 않는다"
//   화면 세로             밀도를 체감이 아니라 수로 잰다
//   근거까지 클릭         이 화면의 시그니처가 근거 줄이다. **몇 번 눌러야 원문이 보이나**
//
// 재는 방법에서 조심할 곳 넷 —
//  1) **모든** 글자의 최소 크기를 재면 배지 안 숫자가 잡혀 전부 "본문 11px" 로 나온다.
//     본문은 산문이다 — 제 텍스트가 25자 넘는 요소만 본다.
//  2) 줄길이를 canvas 의 "0" 폭으로 나누면 한글이 전각이라 값이 두 배로 부푼다.
//     Range.getClientRects() 로 실제 렌더된 줄을 받아 글자 폭을 평균 낸다.
//  3) 하네스 바(.hns)는 목업 전용이라 전부 제외한다.
//  4) **G2 는 힘 배치를 420틱 돌린다.** 그리기 전에 재면 노드가 0 이다 — 넉넉히 기다린다.
import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const SIZE = { width: 1440, height: 1000 };

// variants.js 를 읽어 온다. 가짜 window 에 실행시켜 목록만 꺼낸다
const src = readFileSync(new URL("../variants.js", import.meta.url), "utf8");
const win = { VARIANTS: null };
new Function("window", src)(win);
const FILES = win.VARIANTS.map((v) => [v.label, v.file]);

const probe = ({ foldH }) => {
  const inHarness = (el) => el.closest(".hns, .hns-out") !== null;
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || s.opacity === "0") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const all = [...document.querySelectorAll("body *")].filter((el) => !inHarness(el) && vis(el));

  // 그래프 — SVG 든 canvas 든 노드로 세는 것을 시안이 스스로 표시한다
  const nodes =
    document.querySelectorAll(".n, .node, .cNode, .far, .slot, .file, .item[data-key]").length;
  const edges = document.querySelectorAll(".edge, .band, .beam, .thread, .spoke, .cSpoke, .tether").length;
  const labels = document.querySelectorAll(
    ".lb, .label, .cLabel, .centerLabel, .itemLabel, .slotName, .fileName, .far text"
  ).length;

  // 본문 최소 — 제 텍스트가 25자 넘는 요소만 산문으로 본다
  let bodyMin = Infinity;
  for (const el of all) {
    const own = [...el.childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join("");
    if (own.length > 25) bodyMin = Math.min(bodyMin, parseFloat(getComputedStyle(el).fontSize));
  }

  // 최장 줄 — 실제 렌더된 줄에서 글자 폭을 평균 내 ch 로 환산
  let maxCh = 0;
  for (const el of all) {
    const own = [...el.childNodes].filter((n) => n.nodeType === 3);
    for (const t of own) {
      const s = t.textContent.trim();
      if (s.length < 20) continue;
      const r = document.createRange();
      r.selectNodeContents(t);
      const rects = [...r.getClientRects()];
      if (!rects.length) continue;
      const widest = Math.max(...rects.map((x) => x.width));
      const perChar = rects.reduce((a, x) => a + x.width, 0) / s.length;
      if (perChar > 0) maxCh = Math.max(maxCh, Math.round(widest / perChar));
    }
  }

  // 최소 타깃 — 실제로 누를 수 있는 것만. SVG 안의 role=button 도 센다
  let minTarget = Infinity;
  const hits = all.filter(
    (el) =>
      el.matches("a[href], button, [role=button], summary, input") &&
      !el.hasAttribute("disabled")
  );
  for (const el of hits) {
    const r = el.getBoundingClientRect();
    minTarget = Math.min(minTarget, Math.min(r.width, r.height));
  }

  // 그림자 — inset 은 뺀다(밑줄이 inset 이라 안 빼면 전부 1 이 된다)
  const shadows = all.filter((el) => {
    const s = getComputedStyle(el).boxShadow;
    return s && s !== "none" && !s.includes("inset");
  }).length;

  // 근거까지 몇 번 눌러야 하나. 화면에 원문 조각이 이미 떠 있으면 1(자리를 누른 것)
  const openQuotes = document.querySelectorAll(
    ".evText, .evTable, .sideText, .sideTable, .evT td:last-child"
  ).length;
  const foldedQuotes = document.querySelectorAll(".cSrcSummary").length;

  return {
    nodes,
    edges,
    labels,
    bodyMin: bodyMin === Infinity ? null : bodyMin,
    maxCh,
    minTarget: minTarget === Infinity ? null : Math.round(minTarget),
    shadows,
    pageH: document.body.scrollHeight,
    foldH,
    openQuotes,
    foldedQuotes,
  };
};

const rows = [];
const browser = await chromium.launch();
for (const [label, file] of FILES) {
  const page = await browser.newPage({ viewport: SIZE });
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  await page.goto(new URL(`../${file}`, import.meta.url).href);
  // G2 는 힘 배치 420틱. 그리기 전에 재면 노드가 0 이다
  await page.waitForTimeout(2200);
  // 자리를 하나 골라 둔다 — 패널이 닫힌 채로 재면 시그니처를 못 잰다.
  // SVG <g> 는 bbox 중심이 빈 자리라 진짜 클릭이 안 먹어 DOM 이벤트로 부른다
  await page.evaluate(() => {
    const el = document.querySelector('[data-key="traction"]');
    if (el) el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await page.waitForTimeout(700);
  const m = await page.evaluate(probe, { foldH: SIZE.height });
  rows.push([label, m, errs]);
  await page.close();
}
await browser.close();

const pad = (s, n, right = true) =>
  right ? String(s).padStart(n) : String(s).padEnd(n);
const cols = [
  ["시안", 16, false],
  ["노드", 5],
  ["연결", 5],
  ["이름표", 6],
  ["본문최소", 8],
  ["최장줄", 6],
  ["최소타깃", 8],
  ["그림자", 6],
  ["세로", 6],
  ["원문열림", 8],
  ["접힌근거", 8],
];
console.log(cols.map(([h, w, r]) => pad(h, w, r === false ? false : true)).join(" "));
console.log(cols.map(([, w]) => "─".repeat(w)).join(" "));
for (const [label, m, errs] of rows) {
  console.log(
    [
      pad(label, 16, false),
      pad(m.nodes, 5),
      pad(m.edges, 5),
      pad(m.labels, 6),
      pad(m.bodyMin ?? "—", 8),
      pad(m.maxCh + "ch", 6),
      pad(m.minTarget ?? "—", 8),
      pad(m.shadows, 6),
      pad(m.pageH, 6),
      pad(m.openQuotes, 8),
      pad(m.foldedQuotes, 8),
    ].join(" ") + (errs.length ? "   ⚠ " + errs[0].slice(0, 60) : "")
  );
}

console.log(`
본문최소  §3 은 16px 이상을 요구한다. 다만 --t-aux 가 ≥1024px 에서 13px 이므로
          (ADR-0044) 이 폭에서 13 이 나오는 것은 위반이 아니라 그 결정의 결과다.
최장줄    §5 는 62ch 이하.
최소타깃  §5 는 44px 이상. **그래프 노드는 여기서 거의 다 미달이다** — 도트가
          작아서다. 시안이 그걸 어떻게 감당하는지가 고르는 기준의 하나다.
그림자    §6 은 "실제로 위에 뜨는 것에만". inset 은 뺐다.
원문열림  자리를 하나 누른 뒤 화면에 이미 떠 있는 원문 조각 수.
접힌근거  한 번 더 눌러야 원문이 나오는 <details> 수. **현행이 여기 크다.**`);
