/* 시안 목록. **한 곳에서만 정의한다** — switch.html · index.html · 각 시안이 같은 id 를 본다.
 *
 * `A 접수증`(a-receipt.html)은 **폐기됐다**(2026-08-20 피드백). 파일도 지웠다.
 * `C 여백`(c-quiet.html)은 에디토리얼이라 버렸다 — ADR-0040. 자리는 `C 던지기`가 대신한다. */
var VARIANTS = [
  { id: "base", label: "현행",     file: "base.html" },
  { id: "b",    label: "B 관제",   file: "b-console.html" },
  { id: "c",    label: "C 던지기", file: "c-drop.html" },
  { id: "d",    label: "D 면",     file: "d-plane.html" },
  { id: "e",    label: "E 조립",   file: "e-assemble.html" },
  { id: "f",    label: "F 현행+",  file: "f-plus.html" },
];
