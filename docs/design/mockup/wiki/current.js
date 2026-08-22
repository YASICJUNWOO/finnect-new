/* 현행 재현. **대조군이자 시안의 고정 변인이다.**
 *
 * `web/components/Orbit.tsx` · `Orbit.module.css` · `WikiPanel.tsx` · `WikiPanel.module.css`
 * 를 그대로 옮긴 것이다. 값을 바꾸지 않는다 — 대조군이 실제와 다르면 «좋아졌나» 판정이
 * 통째로 무의미해진다.
 *
 * **G 시안은 이 패널을 쓰고 P 시안은 이 궤도를 쓴다.** 그래야 갈리는 축이 하나씩만
 * 남는다(하네스 규칙 1). 둘 다 바꾼 시안은 만들지 않는다 — 무엇 때문에 좋아 보이는지
 * 분간이 안 된다.
 *
 * 옮기면서 고친 것 0개. 이미 알고 있는 결함 둘은 **그대로 둔다** —
 *  · 빈 자리 이름표가 `--ink-3` 2.65:1 로 AA 미달이다
 *  · 구획 라벨이 바깥 넷에만 있다(ADR-0017 결정 2 미이행 — 안쪽은 자리가 없다)
 * 고치면 대조군이 현행이 아니게 된다. */

window.Current = (function () {
  var W = window.WIKI, P = window.Parts, L = window.Layout;

  var SIZE = 640;
  var DOT = { identity: 40, company: 15, content: 15 };

  /* ── 현행 궤도 ─────────────────────────────────────────── */

  function orbit(nodes, opts) {
    var o = opts || {};
    var g = L.orbit(nodes, { size: SIZE });
    var svg = [];

    /* 궤도 두 줄. **구획별로 끊어 그린다** — 끊긴 자리가 구획 경계다 */
    g.innerArcs.forEach(function (a) {
      svg.push('<path class="cRing" d="' + L.arcPath(g.cx, g.cy, g.inner, a.from, a.to) + '"/>');
    });
    g.outerArcs.forEach(function (a) {
      svg.push('<path class="cRing" d="' + L.arcPath(g.cx, g.cy, g.outer, a.from, a.to) + '"/>');
    });

    /* 바큇살. 중심에서 각 자리로, 도트 앞에서 멈춘다 */
    g.placed.forEach(function (p) {
      var rad = (p.angle * Math.PI) / 180;
      var r = DOT[p.node.kind] || DOT.content;
      var from = DOT.identity + 4;
      var to = Math.hypot(p.x - g.cx, p.y - g.cy) - r - 4;
      svg.push(
        '<line class="cSpoke" x1="' + (g.cx + from * Math.cos(rad)) +
        '" y1="' + (g.cy + from * Math.sin(rad)) +
        '" x2="' + (g.cx + to * Math.cos(rad)) +
        '" y2="' + (g.cy + to * Math.sin(rad)) + '"/>'
      );
    });

    /* 구획 라벨. **바깥 넷만이다** — 안쪽 다섯은 지름이 작아 라벨 둘을 더 두면 겹친다 */
    g.outerArcs.forEach(function (a) {
      var rad = (a.from * Math.PI) / 180;
      var r = g.outer + 52;
      svg.push(
        '<text class="cSector" x="' + (g.cx + r * Math.cos(rad)) +
        '" y="' + (g.cy + r * Math.sin(rad) + 4) + '">' +
        P.esc(W.sectors[a.sector]) + "</text>"
      );
    });

    if (g.center) svg.push(dot(g.center, DOT.identity, true, o));
    g.placed.forEach(function (p) {
      svg.push(dot(p, DOT[p.node.kind] || DOT.content, false, o));
    });

    return (
      '<svg class="cSvg" viewBox="0 0 ' + SIZE + " " + SIZE +
      '" role="group" aria-label="사업 위키 궤도. 자리 열다섯">' + svg.join("") + "</svg>"
    );
  }

  function dot(p, r, inside, o) {
    var n = p.node;
    var sel = o.selected === n.key;
    var rad = (p.angle * Math.PI) / 180;
    var out = r + 16;
    var lx = inside ? p.x : p.x + out * Math.cos(rad);
    var ly = inside ? p.y + 5 : p.y + out * Math.sin(rad) + 4;
    var anchor = inside
      ? "middle"
      : Math.cos(rad) > 0.25 ? "start" : Math.cos(rad) < -0.25 ? "end" : "middle";
    var state = n.filled ? (n.conflicted ? "손봐야 해요" : "찼어요") : "아직 비어 있어요";

    return (
      '<g class="cNode" data-kind="' + n.kind + '" data-filled="' + n.filled +
      '" data-key="' + n.key + '" role="button" tabindex="0" aria-pressed="' + sel +
      '" aria-label="' + P.esc(n.label + " — " + state) + '">' +
      (sel ? '<circle class="cHalo" cx="' + p.x + '" cy="' + p.y + '" r="' + (r + 7) + '"/>' : "") +
      '<circle class="cDot" cx="' + p.x + '" cy="' + p.y + '" r="' + r + '"/>' +
      (n.conflicted
        ? '<circle class="cBadge" cx="' + (p.x + r * 0.72) + '" cy="' + (p.y - r * 0.72) + '" r="5"/>'
        : "") +
      '<text class="' + (inside ? "cCenterLabel" : "cLabel") + '" x="' + lx + '" y="' + ly +
      '" text-anchor="' + anchor + '">' + P.esc(n.label) + "</text></g>"
    );
  }

  /* ── 현행 패널 ─────────────────────────────────────────────
   *
   * **이 화면의 시그니처는 근거 줄이다.** 값이든 문장이든 바로 아래 `파일명 · N쪽` 이
   * 붙어 있고 누르면 그 자리에서 원문 조각이 열린다. 출처를 툴팁이나 각주로 빼지 않는다 —
   * 빼는 순간 값과 근거가 떨어지고, 떨어지면 아무도 안 연다. */

  function sources(evidence, quiet) {
    if (!evidence.length) return '<p class="cNoSrc">근거가 없어요</p>';
    return (
      "<details class=\"" + (quiet ? "cSrcQuiet" : "cSrc") + '"><summary class="cSrcSummary">' +
      '<span class="cSrcCount" data-numeric>근거 ' + evidence.length + "</span>" +
      '<span class="cSrcWhere">' +
      P.esc(evidence.map(P.where).join(" · ")) +
      "</span></summary><ul class=\"cQuotes\">" +
      evidence
        .map(function (e) {
          return (
            '<li class="cQuote"><p class="cQuoteWhere">' + P.esc(e.filename) +
            (e.page ? '<span class="cPage" data-numeric>' + e.page + "쪽</span>" : "") +
            '</p><blockquote class="cQuoteText">' + P.esc(e.quote) + "</blockquote></li>"
          );
        })
        .join("") +
      "</ul></details>"
    );
  }

  function values(vals) {
    return (
      '<section class="cBlock"><dl class="cSlots">' +
      vals
        .map(function (v) {
          return (
            '<div class="cSlot"><dt class="cSlotName">' + P.esc(v.label) +
            (v.qualifier ? '<span class="cQual">' + P.esc(v.qualifier) + "</span>" : "") +
            '</dt><dd class="cSlotBody">' +
            (v.conflict
              ? '<p class="cConflict">값이 갈려요. 어느 쪽이 맞는지 정해야 해요 — 둘 다 두었어요.</p>'
              : "") +
            v.current
              .map(function (c) {
                return (
                  '<div class="cValue" data-conflict="' + (c.status === "conflict") + '">' +
                  '<p class="cValueText" data-numeric>' + P.esc(c.display) +
                  (c.as_of ? '<span class="cAsOf">' + P.esc(c.as_of) + " 기준</span>" : "") +
                  "</p>" + sources(c.evidence) + "</div>"
                );
              })
              .join("") +
            (v.history.length
              ? '<details class="cHistory"><summary class="cHistorySummary">이전 값 ' +
                v.history.length + '개</summary><ul class="cHistoryList">' +
                v.history
                  .map(function (h) {
                    return (
                      "<li><span data-numeric>" + P.esc(h.display) + "</span>" +
                      (h.as_of ? '<span class="cAsOf">' + P.esc(h.as_of) + "</span>" : "") +
                      sources(h.evidence, true) + "</li>"
                    );
                  })
                  .join("") + "</ul></details>"
              : "") +
            "</dd></div>"
          );
        })
        .join("") +
      "</dl></section>"
    );
  }

  function panel(n) {
    if (!n) return '<p class="cHint">자리를 누르면 무엇이 들어 있는지, 어디서 왔는지 열려요.</p>';

    var body;
    if (!n.filled) {
      /* 빈 화면. **"데이터 없음"으로 끝내지 않는다** */
      body = '<p class="cEmpty">이 자리를 채우려면 관련된 내용이 담긴 파일을 더 올리면 돼요.</p>';
    } else {
      body =
        (n.values.length ? values(n.values) : "") +
        (n.statements.length
          ? '<section class="cBlock">' +
            (n.values.length ? '<h3 class="cBlockTitle">사업 내용</h3>' : "") +
            '<ul class="cFacts">' +
            n.statements
              .map(function (s) {
                return (
                  '<li class="cFact"><p class="cFactText">' + P.esc(s.text) + "</p>" +
                  sources(s.evidence) + "</li>"
                );
              })
              .join("") +
            "</ul></section>"
          : "");
    }

    return (
      '<article class="cPanel" aria-labelledby="node-title"><header class="cHead">' +
      '<div class="cHeadText"><p class="cEyebrow">' +
      '<span class="cKind" data-kind="' + n.kind + '" aria-hidden="true"></span>' +
      P.esc(n.sectorLabel) +
      (n.eligibility ? '<span class="cTag">자격 판별에 써요</span>' : "") +
      '</p><h2 id="node-title" class="cTitle">' + P.esc(n.label) + "</h2>" +
      '<p class="cMeta">' +
      (n.filled ? "근거가 된 파일 " + n.source_count + "개" : "아직 비어 있어요") +
      (n.conflicted ? '<span class="cWarn">값이 갈렸어요</span>' : "") +
      "</p></div>" +
      '<button type="button" class="cToggle">마크다운으로 보기</button>' +
      "</header>" + body + "</article>"
    );
  }

  return { orbit: orbit, panel: panel, SIZE: SIZE, DOT: DOT };
})();
