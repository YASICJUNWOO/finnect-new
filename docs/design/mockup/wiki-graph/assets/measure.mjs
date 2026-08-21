// 시안별 기하를 실측해 대조표로 뽑는다. 목업 폴더에서 `node assets/measure.mjs`.
//
// **"넓어 보인다"는 체감은 자주 틀린다.** 조판이 답답해 보여도 실제로는 현행보다
// 세로를 덜 먹는 식이다. 여기서 나온 숫자를 README·index 에 그대로 박는다.
//
// 시안 넷이 마크업이 전혀 다르므로 **의미로 잰다** — 자리 하나는 `[data-key]` 하나이고
// 이름표는 시안마다 클래스가 다르다. 셀렉터를 여기 한 곳에만 둔다.
import { chromium } from "playwright";

const SIZE = { width: 1240, height: 1000 };

const TARGETS = [
  ["현행", "base.html", ".label"],
  ["A 행성", "a-planet.html", ".label"],
  ["B 유리", "b-glass.html", ".label"],
  ["C 젤리", "c-jelly.html", ".label"],
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: SIZE, locale: "ko-KR" });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

const rows = [];
for (const [label, file, nameSel] of TARGETS) {
  errors.length = 0;
  await page.goto("file://" + process.cwd() + "/" + file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);

  const v = await page.evaluate((nameSel) => {
    // 자리 하나 = [data-key] 하나. 시안마다 태그가 다르므로 속성으로 센다
    // **케이블도 data-key 를 갖는다**(시안 C). 자리만 세려면 빼야 한다 —
    // 안 빼면 자리 수가 29 로 나오고 최소 타깃이 선 굵기로 잡힌다
    const spots = [...document.querySelectorAll("[data-key]:not(.cable)")]
      .filter((el) => !el.closest("[data-key]:not(.cable)") || el.closest("[data-key]:not(.cable)") === el);
    const rects = spots.map((el) => el.getBoundingClientRect()).filter((r) => r.width > 0);

    const box = rects.reduce((a, r) => ({
      l: Math.min(a.l, r.left), t: Math.min(a.t, r.top),
      rt: Math.max(a.rt, r.right), b: Math.max(a.b, r.bottom),
    }), { l: 1e9, t: 1e9, rt: -1e9, b: -1e9 });

    // 이름표끼리 겹치는 쌍. **읽히지 않는 이름표는 없는 것과 같다**
    const names = [...document.querySelectorAll(nameSel)]
      .map((el) => el.getBoundingClientRect())
      .filter((r) => r.width > 0 && r.height > 0);
    let overlap = 0;
    for (let i = 0; i < names.length; i++)
      for (let j = i + 1; j < names.length; j++) {
        const a = names[i], b = names[j];
        if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) overlap++;
      }

    // 누를 수 있는 자리의 최소 크기. DESIGN.md §8.2 가 44px 이상을 요구한다
    const hit = spots.map((el) => {
      const r = el.getBoundingClientRect();
      return Math.min(r.width, r.height);
    }).filter((n) => n > 0);

    return {
      spots: spots.length,
      pageH: Math.round(document.querySelector("main").getBoundingClientRect().height),
      spanW: Math.round(box.rt - box.l),
      spanH: Math.round(box.b - box.t),
      names: names.length,
      overlap,
      minHit: Math.round(Math.min(...hit)),
      medHit: Math.round(hit.sort((a, b) => a - b)[Math.floor(hit.length / 2)]),
    };
  }, nameSel);

  rows.push([label, v, errors.slice()]);
}
await browser.close();

const COLS = [
  ["자리 수", "spots"], ["화면 세로", "pageH"], ["자리 범위 가로", "spanW"], ["자리 범위 세로", "spanH"],
  ["이름표 수", "names"], ["이름표 겹침", "overlap"], ["최소 타깃", "minHit"], ["중앙 타깃", "medHit"],
];
const w = 15;
console.log("".padEnd(12) + COLS.map(([k]) => k.padStart(w)).join(""));
const base = rows[0][1];
for (const [label, v, errs] of rows) {
  const cells = COLS.map(([, key]) => {
    const d = v[key] - base[key];
    const delta = label === rows[0][0] || d === 0 ? "" : ` ${d > 0 ? "+" : ""}${d}`;
    return String(v[key] + delta).padStart(w);
  });
  console.log(label.padEnd(12) + cells.join(""));
  if (errs.length) console.log("  ⚠︎ 스크립트 오류: " + errs.join(" / "));
}
