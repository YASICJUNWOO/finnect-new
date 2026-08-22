/* 노드 재질과 색. **여기가 정본이다.**
 *
 * 처음엔 이걸 안 만들고 다섯 시안이 전부 평면 원 + 종류색 셋을 쓰게 뒀다. 축을 하나로
 * 묶으려고(「무엇을 노드로 그리는가」) 재질을 고정 변인으로 둔 것인데, **원래 물음이
 * 「노드 퀄리티가 떨어진다」였으므로 재질 자체가 축이어야 맞다.**
 *
 * 그래서 시안을 다섯 배로 늘리는 대신 **노브 둘로 뺀다.** 재질 다섯 × 색 셋이
 * 그래프 시안 다섯 위에 얹혀서 조합이 75가지가 되고, 시안 파일은 그대로 다섯이다.
 * 하네스가 원래 이런 것을 위해 있다.
 *
 * ── 재질 다섯 ──────────────────────────────────────────────
 *   평면  현행. 단색 채움. 대조군이라 지우지 않는다
 *   발광  가운데가 밝고 바깥으로 빛이 번진다. 어두운 면에서 산다
 *   구체  왼쪽 위 하이라이트 + 오른쪽 아래 그늘 + 테두리 빛
 *   유리  반투명. 속의 알이 비치고 위쪽에 정반사 한 점
 *   링    속이 빈 도넛. 굵은 테두리. 그래프 도구에서 가장 흔한 어법이다
 *
 * ── 색 셋 ──────────────────────────────────────────────────
 *   종류 셋    DESIGN.md §2. identity · company · content
 *   구획 여섯  §2 밖이다. 186개에서 셋은 덩어리가 안 갈린다
 *   단색+강조  회색 하나 + 고른 것만 액센트. 레퍼런스 이미지 3 의 어법
 *
 * **색조 하나에 뜻 둘을 얹지 않는다는 §2 규칙은 재질을 바꿔도 그대로다.** 빈 자리와
 * 충돌은 여전히 형태와 개수로 말한다 — 재질은 「무엇인가」를 안 말하고 「얼마나 도드라지나」
 * 만 말한다. 그래서 재질을 상태에 쓰면 안 된다. */

window.Materials = (function () {
  /* ── 색 다루기 ────────────────────────────────────────── */

  function hex(h) {
    var s = String(h).replace("#", "");
    if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
  }

  function rgb(c, a) {
    return a == null || a >= 1
      ? "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")"
      : "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")";
  }

  /* 흰 쪽으로 t 만큼. **HSL 로 안 간다** — 채도가 같이 흔들려 종류색이 서로 가까워진다 */
  function lighten(c, t) {
    return c.map(function (v) { return Math.round(v + (255 - v) * t); });
  }

  function darken(c, t) {
    return c.map(function (v) { return Math.round(v * (1 - t)); });
  }

  function slug(h) {
    return String(h).replace(/[^0-9a-z]/gi, "");
  }

  /* ── 팔레트 ───────────────────────────────────────────── */

  /* 어두운 면과 밝은 면에서 값이 다르다. **같은 값을 양쪽에 쓰면 한쪽이 반드시 죽는다** */
  var PALETTES = {
    light: {
      kind: { identity: "#5b5bd6", company: "#9a3412", content: "#0f766e" },
      sector: {
        registration: "#5b5bd6", principal: "#7e22ce",
        problem_solution: "#0f766e", market_customer: "#0369a1",
        result_money: "#9a3412", team_plan: "#a21caf",
      },
      mono: "#8a8f98",
      accent: "#222222",
      surface: "#ffffff",
    },
    dark: {
      kind: { identity: "#8b8bf0", company: "#e08c5a", content: "#3fb9a5" },
      sector: {
        registration: "#7c8cf8", principal: "#e2a2ff",
        problem_solution: "#4dd4ac", market_customer: "#5ec8f5",
        result_money: "#f0a05a", team_plan: "#f77f9e",
      },
      mono: "#6f7684",
      accent: "#ffffff",
      surface: "#0d1117",
    },
  };

  /* 노드 하나의 색을 정한다. **`selected` 는 단색 모드에서만 쓴다** —
   * 다른 모드에서 선택을 색으로 말하면 종류가 먼저 망가진다(§2) */
  function colorOf(node, opts) {
    var o = opts || {};
    var P = PALETTES[o.tone || "light"];
    var palette = o.palette || "kind";
    if (palette === "sector") return P.sector[node.sector] || P.mono;
    if (palette === "mono") return o.selected ? P.accent : P.mono;
    return P.kind[node.kind] || P.mono;
  }

  /* ── SVG defs ─────────────────────────────────────────────
   *
   * 재질마다 색당 그라데이션 하나가 필요하다. **쓰는 색만 만든다** — 팔레트를 통째로
   * 만들면 안 쓰는 def 이 스무 개씩 남고, 그게 시안마다 다르면 measure 의 노드 수가
   * 어긋난다(`<defs>` 안의 circle 은 안 그려지지만 셀 수는 있다). */
  function defs(colors, material, tone) {
    if (material === "flat") return "";
    var surface = PALETTES[tone || "light"].surface;
    var seen = {};
    var out = [];

    colors.forEach(function (h) {
      if (!h || seen[h]) return;
      seen[h] = 1;
      var id = "m-" + material + "-" + slug(h);
      var c = hex(h);

      if (material === "glow") {
        out.push(
          '<radialGradient id="' + id + '" cx="50%" cy="50%" r="50%">' +
          '<stop offset="0%" stop-color="' + rgb(lighten(c, 0.42)) + '"/>' +
          '<stop offset="58%" stop-color="' + rgb(c) + '"/>' +
          '<stop offset="100%" stop-color="' + rgb(darken(c, 0.14)) + '"/>' +
          "</radialGradient>" +
          '<radialGradient id="' + id + '-halo" cx="50%" cy="50%" r="50%">' +
          '<stop offset="0%" stop-color="' + rgb(c, 0.5) + '"/>' +
          '<stop offset="55%" stop-color="' + rgb(c, 0.16) + '"/>' +
          '<stop offset="100%" stop-color="' + rgb(c, 0) + '"/>' +
          "</radialGradient>"
        );
      } else if (material === "orb") {
        /* 광원은 왼쪽 위 한 곳. **시안 안에서 방향이 갈리면 안 된다** —
         * 노드마다 빛이 다른 데서 오면 구체가 아니라 얼룩으로 보인다 */
        out.push(
          '<radialGradient id="' + id + '" cx="32%" cy="28%" r="76%">' +
          '<stop offset="0%" stop-color="' + rgb(lighten(c, 0.62)) + '"/>' +
          '<stop offset="34%" stop-color="' + rgb(lighten(c, 0.16)) + '"/>' +
          '<stop offset="76%" stop-color="' + rgb(c) + '"/>' +
          '<stop offset="100%" stop-color="' + rgb(darken(c, 0.34)) + '"/>' +
          "</radialGradient>"
        );
      } else if (material === "glass") {
        out.push(
          '<radialGradient id="' + id + '" cx="50%" cy="50%" r="50%">' +
          '<stop offset="0%" stop-color="' + rgb(c, 0.92) + '"/>' +
          '<stop offset="46%" stop-color="' + rgb(c, 0.5) + '"/>' +
          '<stop offset="82%" stop-color="' + rgb(c, 0.2) + '"/>' +
          '<stop offset="100%" stop-color="' + rgb(lighten(c, 0.3), 0.42) + '"/>' +
          "</radialGradient>" +
          '<radialGradient id="' + id + '-spec" cx="34%" cy="26%" r="34%">' +
          '<stop offset="0%" stop-color="' + rgb(hex(surface), 0.85) + '"/>' +
          '<stop offset="100%" stop-color="' + rgb(hex(surface), 0) + '"/>' +
          "</radialGradient>"
        );
      }
    });

    return out.length ? "<defs>" + out.join("") + "</defs>" : "";
  }

  /* 노드 하나를 그린다. **`<g>` 하나를 돌려준다** — 부르는 쪽은 재질을 모른다.
   *
   * 빈 자리는 재질과 무관하게 **속을 비우고 점선을 두른다.** 재질에 상태를 얹으면
   * 「비었다」와 「유리다」가 구분이 안 된다. */
  function node(x, y, r, color, opts) {
    var o = opts || {};
    var m = o.material || "flat";
    var id = "m-" + m + "-" + slug(color);
    var c = hex(color);

    if (o.empty) {
      return (
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' +
        (o.tone === "dark" ? "none" : PALETTES.light.surface) +
        '" stroke="' + color + '" stroke-width="1.5" stroke-dasharray="3 3"/>'
      );
    }

    if (m === "flat") {
      return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + color + '"/>';
    }

    if (m === "glow") {
      return (
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r * 2.6).toFixed(1) +
        '" fill="url(#' + id + '-halo)"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#' + id + ')"/>'
      );
    }

    if (m === "orb") {
      return (
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#' + id + ')"/>' +
        /* 테두리 빛. 아래쪽만 도는 얇은 호라 구체가 면에서 떨어져 보인다 */
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r - 0.5) +
        '" fill="none" stroke="' + rgb(lighten(c, 0.5), 0.5) +
        '" stroke-width="0.9" stroke-dasharray="' + (r * 2.1).toFixed(1) + " " + (r * 4.2).toFixed(1) +
        '" stroke-dashoffset="' + (r * 1.1).toFixed(1) + '"/>'
      );
    }

    if (m === "glass") {
      return (
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#' + id + ')"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + r +
        '" fill="none" stroke="' + rgb(lighten(c, 0.34), 0.6) + '" stroke-width="1"/>' +
        /* 속의 알. **유리는 흰 게 아니라 맑은 것이다** — 알이 비쳐야 구슬로 읽힌다 */
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r * 0.42).toFixed(1) +
        '" fill="' + rgb(c, 0.85) + '"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#' + id + '-spec)"/>'
      );
    }

    /* 링 — 속이 빈 도넛. 굵기가 반지름을 따라간다 */
    var w = Math.max(1.6, r * 0.42);
    return (
      '<circle cx="' + x + '" cy="' + y + '" r="' + (r - w / 2).toFixed(1) +
      '" fill="none" stroke="' + color + '" stroke-width="' + w.toFixed(1) + '"/>'
    );
  }

  /* ── 하네스 노브 ──────────────────────────────────────── */

  var MATERIALS = [
    { v: "flat", label: "평면" },
    { v: "glow", label: "발광" },
    { v: "orb", label: "구체" },
    { v: "glass", label: "유리" },
    { v: "ring", label: "링" },
  ];

  var PALETTE_OPTS = [
    { v: "kind", label: "종류 셋" },
    { v: "sector", label: "구획 여섯" },
    { v: "mono", label: "단색+강조" },
  ];

  /* 노브 둘을 만든다. **`redraw` 를 받는다** — 재질은 CSS 변수로 못 바꾼다.
   * 그라데이션 def 이 색마다 하나씩이라 다시 그려야 한다 */
  function controls(redraw, state) {
    return [
      {
        kind: "segment", label: "재질", name: "material", value: state.material || "flat",
        options: MATERIALS,
        apply: function (v) { state.material = v; redraw(); },
      },
      {
        kind: "segment", label: "색", name: "palette", value: state.palette || "kind",
        options: PALETTE_OPTS,
        apply: function (v) { state.palette = v; redraw(); },
      },
    ];
  }

  return {
    PALETTES: PALETTES,
    colorOf: colorOf,
    defs: defs,
    node: node,
    controls: controls,
    hex: hex,
    rgb: rgb,
    lighten: lighten,
    darken: darken,
  };
})();
