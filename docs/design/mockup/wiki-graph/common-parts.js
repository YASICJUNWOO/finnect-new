/* base.html(대조군) 전용 껍데기. 데이터는 data.js 가 정본이다.
 * **탐색 시안 셋은 이 파일을 안 쓴다** — 저기는 껍데기까지 각자 짓는다. */

/* ── 페이지 껍데기 ────────────────────────────────────────────────────────
 * 그래프를 뺀 전부. 시안 파일은 #graph 안만 채운다. */
function chrome(opts) {
  document.body.insertAdjacentHTML("afterbegin", [
    '<main class="page">',
    '  <header class="head">',
    '    <p class="crumb">내 사업 위키</p>',
    '    <h1 class="h1">다시로</h1>',
    '    <p class="sum">자리 <b data-num>' + NODES.length + '</b>개 중 <b data-num>' + FILLED + '</b>개가 찼어요.',
    '       <span class="warn">손봐야 하는 자리 <b data-num>' + CONFLICTS + '</b>개</span></p>',
    '  </header>',
    '  <nav class="tabs" role="tablist">',
    '    <button role="tab" aria-selected="true">궤도</button>',
    '    <button role="tab" aria-selected="false">원본 파일 <span class="tabN" data-num>4</span></button>',
    '  </nav>',
    '  <section class="stage">',
    '    <p class="thesis">' + opts.thesis + '</p>',
    '    <div id="graph" class="graph"></div>',
    '    <ul class="legend">',
    '      <li data-kind="identity">우리가 하는 일</li>',
    '      <li data-kind="company">사업체 정보</li>',
    '      <li data-kind="content">사업 내용</li>',
    '      <li data-mark="blank">손봐야 해요</li>',
    '      <li data-mark="empty">아직 비었어요</li>',
    '    </ul>',
    '    <div id="panel" class="panel" hidden></div>',
    '    <p id="hint" class="hint">자리를 누르면 무엇이 들어 있는지, 어디서 왔는지 열려요.</p>',
    '  </section>',
    '</main>',
  ].join("\n"));
}

/* 고른 자리 하나. **시안 셋이 같은 패널을 쓴다.** */
function selectNode(key) {
  var n = NODES.filter(function (x) { return x.key === key; })[0];
  var panel = document.getElementById("panel");
  var hint = document.getElementById("hint");
  if (!n) { panel.hidden = true; hint.hidden = false; return; }
  panel.hidden = false;
  hint.hidden = true;
  panel.dataset.kind = n.kind;
  panel.innerHTML = [
    '<p class="pSector">' + (SECTORS[n.sector] || n.sector) + '</p>',
    '<h2 class="pTitle">' + n.label + '</h2>',
    '<p class="pState" data-state="' + (n.filled ? (n.conflicted ? "blank" : "ok") : "empty") + '">'
      + (n.filled ? (n.conflicted ? "값이 갈렸어요" : "찼어요") : "아직 비어 있어요")
      + (n.sources ? ' · 파일 <b data-num>' + n.sources + '</b>개에서 왔어요' : "") + '</p>',
    '<ul class="pLines">' + n.lines.map(function (l) { return "<li>" + l + "</li>"; }).join("") + '</ul>',
  ].join("");
}
