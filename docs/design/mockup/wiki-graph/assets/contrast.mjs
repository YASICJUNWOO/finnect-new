// 색 조합의 WCAG 대비비를 재서 AA/AAA 를 판정한다. 브라우저 없이 도는 순수 계산.
// 사용: `node contrast.mjs`  (PAIRS 를 고쳐서 쓴다)
//
// 왜 필요한가 — "글자가 약해 보인다"는 체감과 실제 미달 지점은 자주 다르다.
// 본문은 이미 AAA 인데 정작 그룹 라벨·아이콘 같은 보조 tier 가 AA 미달인 식이다.
// 눈으로 고치기 전에 어디가 진짜 문제인지 먼저 가른다.

const hex = (h) => {
  h = String(h).replace("#", "");
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
};
const lum = (c) => {
  const s = hex(c).map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2];
};
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
// 본문(<18.66px bold / <24px regular) 기준. 큰 글자는 3:1 로 완화된다.
const grade = (r) => (r >= 7 ? "AAA" : r >= 4.5 ? "AA" : r >= 3 ? "large만" : "미달");

// 프로젝트에 맞게 고칠 곳 — [묶음 이름, [[항목, 전경, 배경], ...]]
const GROUPS = [
  // 2026-08-21 ADR-0041 로 값이 바뀌었다. 이 표는 tokens.css 의 사본이라 **손으로 맞춰야 한다** —
  // .mjs 라 @import 로 따라올 수가 없다. tokens.css 를 고치면 여기도 고친다.
  ["현행 (web/app/tokens.css)", [
    ["본문", "#222222", "#f7f7f8"],
    ["보조 글자", "#5f656d", "#f7f7f8"],
    ["빈 자리 이름표", "#6b7280", "#f7f7f8"],
    ["노드 · 우리가 하는 일", "#5b5bd6", "#ffffff"],
    ["노드 · 사업 내용", "#0f766e", "#ffffff"],
    ["노드 · 사업체 정보", "#9a3412", "#ffffff"],
    ["손봐야 해요", "#b45309", "#f7f7f8"],
  ]],
  ["A 행성 (어두운 배경)", [
    ["본문", "#eef1f5", "#0e1116"],
    ["보조 글자", "#a3adba", "#0e1116"],
    ["빈 자리 이름표", "#7c8898", "#0e1116"],
    ["구획 라벨", "#7c8898", "#0e1116"],
    ["손봐야 해요(고리)", "#f0a33a", "#0e1116"],
    ["행성 · 사업 내용", "#3fbfa8", "#0e1116"],
    ["행성 · 사업체 정보", "#e08a4a", "#0e1116"],
  ]],
  ["B 유리", [
    ["본문", "#1d1b17", "#f2efe9"],
    ["보조 글자", "#5e5951", "#f2efe9"],
    ["빈 자리 이름표", "#6f695c", "#f2efe9"],
    ["손봐야 해요", "#8a5a08", "#f2efe9"],
    ["알 · 사업 내용", "#0f8478", "#f2efe9"],
    ["알 · 사업체 정보", "#c2571d", "#f2efe9"],
  ]],
  ["C 젤리", [
    ["본문", "#16161c", "#e9e9ef"],
    ["보조 글자", "#565a68", "#e9e9ef"],
    ["빈 자리 이름표", "#63687a", "#e9e9ef"],
    ["손봐야 해요(글자)", "#8a5500", "#e9e9ef"],
    ["젤리 · 사업 내용", "#0d9488", "#e9e9ef"],
    ["젤리 · 사업체 정보", "#d1541a", "#e9e9ef"],
    ["가운데 글자", "#ffffff", "#5b5bd6"],
  ]],
];



let fails = 0;
for (const [name, pairs] of GROUPS) {
  console.log(`\n── ${name} ──`);
  for (const [label, fg, bg] of pairs) {
    const r = ratio(fg, bg);
    const g = grade(r);
    if (r < 4.5) fails++;
    console.log(
      `${label.padEnd(20)} ${fg} / ${bg}  ${r.toFixed(2).padStart(5)}:1  ${g}`
    );
  }
}
console.log(`\nAA(4.5:1) 미달 ${fails}건`);
