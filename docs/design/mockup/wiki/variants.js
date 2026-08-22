/* 시안 목록. **switch · harness · index 가 같은 걸 본다** — 세 곳에 적으면 갈린다.
 *
 * 축이 둘이고 각 축에서 갈리는 것은 하나뿐이다.
 *   G 그래프  — 패널은 전부 현행(`current.js`)을 쓴다
 *   P 패널    — 궤도는 전부 현행(`current.js`)을 쓴다
 * 둘 다 바꾼 시안은 만들지 않는다. 무엇 때문에 좋아 보이는지 분간이 안 된다. */

window.VARIANTS = [
  { id: "base", axis: "-", label: "현행", file: "base.html",
    thesis: "자리 15개를 납작한 원으로. 근거 117개는 클릭 뒤에 있다." },

  { id: "g1", axis: "graph", label: "G1 성층", file: "g1-strata.html",
    thesis: "자리는 제자리에 두고 표시 단위 47개를 위성으로 띄운다. 밀도가 보인다." },
  { id: "g2", axis: "graph", label: "G2 성운", file: "g2-nebula.html",
    thesis: "근거와 파일까지 186개를 힘 배치로. 시드가 고정이라 열 때마다 같다." },
  { id: "g3", axis: "graph", label: "G3 구체", file: "g3-orb.html",
    thesis: "구면에 얹고 돌린다. 의존성 0 — canvas 에 손으로 투영한다." },
  { id: "g4", axis: "graph", label: "G4 별자리", file: "g4-constellation.html",
    thesis: "한 번에 자리 하나. 고른 자리가 허브가 되고 근거가 둘레에 선다." },
  { id: "g5", axis: "graph", label: "G5 이분", file: "g5-bipartite.html",
    thesis: "파일 ↔ 자리. 어느 파일을 지우면 무엇이 사라지는지가 구조 자체다." },

  { id: "p2", axis: "panel", label: "P2 곁", file: "p2-aside.html",
    thesis: "오른쪽 고정. 그래프를 안 가리고 스크롤이 따로 논다." },
  { id: "p3", axis: "panel", label: "P3 시트", file: "p3-sheet.html",
    thesis: "노드 위에서 자란다. 좁은 화면에서는 바텀 시트가 된다." },
];

/* **P 는 다섯에서 둘로 줄었다**(2026-08-21 육안 검토). 뺀 셋이 무엇이었는지는
 * README «닫은 것 셋» 에 있다 — 같은 안이 다시 올라오는 것을 막는 자리다. */

/* 밀도는 `common-parts.js` 가 만든다 — 데이터를 아는 쪽이 만들어야 한다 */
window.CONTROLS = function () {
  return [window.DENSITY_CONTROL].filter(Boolean);
};
