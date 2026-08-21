// 시안이 요청한 font-weight 가 실제로 렌더되는지 확인한다.
// 사용: `node assets/font-probe.mjs` (landing 폴더에서)
//
// 왜 필요한가 — 폰트에 그 weight face 가 없으면 브라우저는 **조용히 가장 가까운 값으로
// 떨어뜨린다.** 에러도 경고도 없다. 시안이 서로 다른 웹폰트를 쓰는데,
// "굵기로 위계를 준다"는 판단이 폰트에 그 face 가 없으면 통째로 헛돈다.
//
// ─── 이 스크립트가 한 번 틀렸다. 그 자리를 적어 둔다 ───────────────────────────
// 처음엔 **한글 표본**("가진 파일만 올리면 0123")의 폭으로 판별했다. 그래서
// IBM Plex Sans KR 의 300·400·600 이 "같은 face" 로 나왔고, 그 말을 믿고 B 관제의
// 굵기 위계를 400/500/700 으로 줄였다. **틀렸다.**
//
//   IBM Plex Sans KR 40px 실측
//     한글  400: 187.84   500: 186.77   700: 187.84   ← 400 과 700 이 같다
//     라틴  400: 250.38   500: 255.73   700: 262.89   ← 셋 다 다르다
//
// 한글 글자는 굵기가 달라도 advance 가 거의 고정이다. 획은 실제로 굵어지는데 폭이 안 변한다.
// **그래서 폭으로 판별하려면 라틴으로 재야 한다.** 등폭 폰트도 같은 이유로 안 통한다
// (모든 글자의 advance 가 같다) — 그 줄은 `등폭` 으로 표시하고 판정하지 않는다.
//
// 판별법: 같은 라틴 문자열을 weight 만 바꿔 재고 **폭이 같으면 같은 face** 다.
// `document.fonts.check()` 로 face 유무도 같이 확인한다 — 이쪽이 더 직접적인 답이다.
import { chromium } from "playwright";

const SAMPLE = "Business Plan 0123";     // **라틴이어야 한다.** 위 주석 참고
const WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];

// [이름, 파일, 잴 폰트 스택, 이 시안이 실제로 쓰는 굵기, 등폭이면 true]
// `쓰는 굵기` 는 각 파일에서 `grep -o "font-weight:[0-9]*"` 로 뽑은 것이다. 지어내지 않는다.
const FILES = [
  ["현행", "base.html", "Pretendard", [400, 700], false],
  ["B 관제", "b-console.html", "var(--sans)", [300, 400, 500, 600], false],
  ["B 관제 (등폭)", "b-console.html", "var(--mono)", [400, 500], true],
  ["C 던지기", "c-drop.html", "Pretendard", [400, 600, 700, 800], false],
  ["D 면", "d-plane.html", "var(--sans)", [400, 500, 700, 900], false],
  ["E 조립", "e-assemble.html", "Pretendard", [400, 600, 700], false],   // --w-normal/medium/bold
  ["F 현행+", "f-plus.html", "Pretendard", [400, 600, 700], false],
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, locale: "ko-KR" });

let problems = 0;

for (const [label, file, stack, used, isMono] of FILES) {
  await page.goto("file://" + process.cwd() + "/" + file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);

  const r = await page.evaluate(async ({ sample, weights, stack, used }) => {
    const probe = document.createElement("span");
    probe.textContent = sample;
    probe.style.cssText =
      "position:absolute;visibility:hidden;white-space:nowrap;font-size:40px;font-family:" + stack;
    document.body.appendChild(probe);

    const widths = {};
    for (const w of weights) {
      probe.style.fontWeight = String(w);
      widths[w] = +probe.getBoundingClientRect().width.toFixed(2);
    }
    const family = getComputedStyle(probe).fontFamily.split(",")[0].replace(/['"]/g, "");
    probe.remove();

    // face 가 실제로 있는지 — 폭과 무관한 직접적인 답이다
    const have = {};
    for (const w of used) have[w] = document.fonts.check(`${w} 40px "${family}"`);
    return { widths, family, have };
  }, { sample: SAMPLE, weights: WEIGHTS, stack, used });

  const buckets = new Map();
  for (const [w, px] of Object.entries(r.widths)) {
    if (!buckets.has(px)) buckets.set(px, []);
    buckets.get(px).push(+w);
  }

  if (isMono) {
    console.log(`${label.padEnd(16)} ${r.family.padEnd(20)} 등폭 — 폭으로 판정하지 않는다`);
    continue;
  }

  // 이 시안이 실제로 쓰는 굵기끼리 겹치는지만 본다. 안 쓰는 굵기가 뭉치는 건 상관없다
  const collided = [];
  for (const ws of buckets.values()) {
    const hit = ws.filter((w) => used.includes(w));
    if (hit.length > 1) collided.push(hit.join("·"));
  }
  const missing = Object.entries(r.have).filter(([, ok]) => !ok).map(([w]) => w);

  let verdict = "쓰는 굵기 " + used.length + "개가 전부 구분된다";
  if (collided.length) { verdict = `⚠ 겹침 ${collided.join(" / ")}`; problems++; }
  if (missing.length) { verdict += `  ⚠ face 없음 ${missing.join(",")}`; problems++; }

  console.log(`${label.padEnd(16)} ${r.family.padEnd(20)} 구분 ${String(buckets.size).padStart(2)}종  쓰는 것 ${used.join("/")}  ${verdict}`);
}

console.log(`\n문제 ${problems}건.`);
console.log("표본이 라틴인 이유는 파일 맨 위 주석에 있다 — 한글과 등폭은 굵기가 달라도 폭이 안 변한다.");
await browser.close();
