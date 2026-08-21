/* 시안 목록. **한 곳에서만 정의한다** — 파일 여덟이 각자 들고 있으면 하나를 지웠을 때 갈린다. */

window.VARIANTS = [
  { id: "base", label: "현행", file: "base.html" },
  { id: "a", label: "A 규범", file: "a-spec.html" },
  { id: "e", label: "E 관제", file: "e-console.html" },
  { id: "r", label: "R 적응", file: "r-adaptive.html" },
];

/** 화면 전환 컨트롤. 셋이 같은 것을 쓴다 — 목록만 보고 고르면 상세가 어긋난다. */
window.SCREEN_CONTROL = {
  kind: "segment",
  label: "화면",
  name: "screen",
  value: "list",
  options: [
    { v: "list", label: "목록 S4" },
    { v: "detail", label: "상세 S5" },
  ],
  apply: function (v) {
    document.body.dataset.screen = v;
    window.scrollTo(0, 0);
  },
};


/** 목록 제목 굵기. **§3 의 문장과 표가 어긋난 자리를 눈으로 재는 노브다.**
 *
 * §3 본문은 *"크기로 벌리지 말고 **굵기와 위치로 가른다**"* 라고 적었는데, 같은 절의
 * 관측 표에는 굵은 제목이 없다 — 16/400 · 16/400 · 20/600 셋뿐이다.
 * **문장은 굵기로 가르라 하고 표는 그런 제목을 안 보여 준다.**
 *
 * 지운 F 세그먼트가 `17px/600` 이었고 육안에서 "굵어서 좋다" 가 나왔다. 다만 F 는
 * 크기와 굵기를 같이 올려서 §3 의 문장은 지키고 표는 어겼다. **여기서는 크기를 16 에
 * 두고 굵기만 가른다** — 그러면 문장과 표를 둘 다 지킨다.
 *
 * **2026-08-21 500 으로 정했다**(잠정). 400·600 사이가 좋다는 육안 판단이다.
 *
 * **500 은 관측 밖 값이다** — §3 관측 굵기가 400·600 둘이고 `tokens.css` 도
 * 400·600·700 셋뿐이다. 옛 감사는 500 을 위반으로 짚었다. 코드로 옮기려면
 * **토큰을 새로 만들고 §3 관측 표에 추가해야 한다.** 400·600 을 노브에 남겨 둔
 * 이유는 잠정이라서다. */
window.WEIGHT_CONTROL = {
  kind: "segment",
  label: "제목 굵기",
  name: "weight",
  value: "500",
  options: [
    { v: "400", label: "400 (§3 표)" },
    { v: "500", label: "500 (정함)" },
    { v: "600", label: "600" },
  ],
  apply: function (v) {
    document.body.dataset.weight = v;
  },
};
