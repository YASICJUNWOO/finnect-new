/* 껍데기 마크업과 공용 조각. **여기가 정본이다.**
 *
 * 시안이 갈리는 것은 그래프 판과 패널뿐이고 그 바깥은 전부 같아야 한다 — 헤더가
 * 시안마다 다르면 무엇 때문에 좋아 보이는지 분간이 안 된다(하네스 규칙 1).
 *
 * 껍데기 구조의 정본은 `docs/design/mockup/notice/r-adaptive.html` 이다. */

window.Parts = (function () {
  var W = window.WIKI;

  /* 3축. **배열 하나를 레일과 상단 막대가 같이 읽는다** — 두 곳에 적지 않는다.
   * 제품의 `web/app/(product)/layout.tsx` 가 같은 제약을 갖는다 */
  var AXES = [
    { href: "#", label: "지원사업", short: "지원<br>사업" },
    { href: "#", label: "내 사업", short: "내<br>사업", on: true },
    { href: "#", label: "신청 현황", short: "신청<br>현황", soon: true },
  ];

  function axis(a, short) {
    var text = short ? a.short : a.label;
    if (a.soon) {
      return (
        '<span class="soon" aria-disabled="true">' +
        text +
        '<span class="srOnly"> — 아직 없어요</span></span>'
      );
    }
    return (
      '<a' +
      (a.on ? ' class="on" aria-current="page"' : "") +
      ' href="' +
      a.href +
      '">' +
      text +
      "</a>"
    );
  }

  /* 껍데기 하나. `main` 안쪽만 시안이 채운다 */
  function shell(opts) {
    var o = opts || {};
    return (
      '<div class="app">' +
      '<aside class="rail">' +
      '<a href="#" aria-label="finnect 홈"><i class="mark" aria-hidden="true"></i></a>' +
      '<nav aria-label="주요 메뉴 (넓은 화면)" style="display:contents">' +
      AXES.map(function (a) {
        return axis(a, true);
      }).join("") +
      "</nav></aside>" +
      '<div class="col">' +
      '<header class="bar">' +
      '<div class="tier1">' +
      '<a class="brand" href="#"><i class="mark" aria-hidden="true"></i>finnect</a>' +
      '<nav class="menu" aria-label="주요 메뉴">' +
      AXES.map(function (a) {
        return axis(a, false);
      }).join("") +
      "</nav>" +
      '<a class="admin" href="#">운영 도구</a>' +
      "</div>" +
      '<div class="tier2">' +
      '<span class="crumb">내 사업 <span class="sep">›</span> <b>' +
      (o.crumb || "사업 위키") +
      "</b></span>" +
      '<span class="sep">|</span>' +
      '<span data-numeric id="shellStat"></span>' +
      "</div></header>" +
      "<main></main></div></div>"
    );
  }

  /* 화면 머리. **채움 상태를 막대로 그리지 않는다** — 숫자가 근거를 갖는 값이라
   * 막대로 그리면 비율처럼 읽힌다 */
  function head(density) {
    var s = W.summary(density);
    return (
      '<header class="head">' +
      '<div class="headTop"><h1 class="h1">내 사업</h1>' +
      '<a class="ghost" href="#">파일 올리기</a></div>' +
      '<p class="sub">올린 파일에서 뽑은 것들이에요. 값마다 어느 파일 몇 쪽에서 왔는지 볼 수 있어요.</p>' +
      '<p class="counts">' +
      '<span data-numeric>자리 ' +
      s.total +
      "개 중 <b>" +
      s.filled +
      "개</b>가 찼어요</span>" +
      '<span data-numeric>근거 <b>' +
      s.evidence +
      "</b>개</span>" +
      (s.conflicts
        ? '<span class="warn" data-numeric>값이 갈린 곳 ' + s.conflicts + "건</span>"
        : "") +
      (s.uncategorized
        ? '<span data-numeric>갈 자리를 못 찾은 것 ' + s.uncategorized + "건</span>"
        : "") +
      "</p></header>"
    );
  }

  /* 상단 2단의 통계. 껍데기가 읽으므로 밀도를 갈면 같이 간다 */
  function stat(density) {
    var s = W.summary(density);
    var el = document.getElementById("shellStat");
    if (el) {
      el.textContent =
        "파일 " + s.files + " · 자리 " + s.filled + "/" + s.total + " · 근거 " + s.evidence;
    }
  }

  /* 시안 하나를 세운다. `render(main, density)` 가 판을 그린다 */
  function mount(opts) {
    var o = opts || {};
    document.body.insertAdjacentHTML("afterbegin", shell(o));
    var main = document.querySelector("main");

    var density = "heavy";
    function draw() {
      main.innerHTML = head(density);
      stat(density);
      o.render(main, density);
    }
    draw();

    /* 밀도 노브. **갈리는 것은 밀도 하나뿐이다** — 가벼움은 무거움의 부분집합이라
     * 파일 둘로 좁힌 것이고, 빈 자리 다섯이 지어낸 공백이 아니다 */
    window.DENSITY_CONTROL = {
      kind: "segment",
      label: "밀도",
      name: "density",
      value: density,
      options: [
        { v: "heavy", label: "일곱 장 (근거 117)" },
        { v: "light", label: "두 장 (근거 29)" },
      ],
      apply: function (v) {
        density = v;
        draw();
      },
    };
    return { redraw: draw };
  }

  /* ── 값 다루기 ── */

  /* 근거 한 줄. **파일명과 쪽이 따로 온다** — 미리 이어 붙이면 화면이 "3쪽"을
   * 다르게 쓸 자유가 없다 */
  function where(e) {
    return e.filename + (e.page ? " " + e.page + "쪽" : "");
  }

  /* 근거 여럿의 한 줄 요약. **넷을 다 적으면 줄이 넘친다** — 둘까지 적고 나머지는 센다 */
  function wheres(evidence) {
    if (evidence.length <= 2) return evidence.map(where).join(" · ");
    return where(evidence[0]) + " 외 " + (evidence.length - 1) + "곳";
  }

  /* 표 부스러기인가. **노드 텍스트가 문장이라고 믿으면 안 된다**(plan/12 T-0078).
   * 스키마는 「사람이 읽는 문장」이라고 적었는데 표 한 줄이 그대로 노드가 된다.
   *
   * ── 이 함수는 불완전하다. 그게 요점이다 ────────────────────
   * 처음에는 `rank.quotable()` 처럼 **탭과 줄바꿈만** 봤다. 그랬더니 P1 에서
   * `합계 49200000 37200000 86400000` 이 그대로 인용문으로 나갔다 — 재무제표의 표
   * 한 줄인데 해독 과정에서 탭이 공백이 된 것이다. 숫자 토큰 셋 이상이 줄지어 있으면
   * 표로 보는 규칙을 하나 더 얹었지만, **이렇게 증상마다 규칙을 붙이는 것이 이미 진 싸움이다.**
   *
   * 뿌리는 추출기 쪽(T-0078)이고 화면에서 완전히 막을 수 없다. 시안이 할 수 있는 것은
   * 「인용을 어디까지 신뢰하는가」를 정하는 것뿐이라, 이 함수가 거른 것은 원문 대신
   * 출처만 남긴다. **고쳐 쓰지 않는다** — 고쳐 쓰면 원문에 없는 문장이 되어 근거
   * 대조가 깨진다(`rank.quotable()` 과 같은 이유). */
  function quotable(text) {
    if (/[\t\n]/.test(text)) return false;
    if (text.length >= 160) return false;
    /* 숫자 토큰이 셋 이상 줄지어 있으면 표 한 줄이다 */
    if (/(^|\s)\d[\d,.]*(\s+\d[\d,.]*){2,}(\s|$)/.test(text)) return false;
    return true;
  }

  /* 미래 날짜인가. `current` 는 "가장 늦은 시점"이라 미래도 current 다 */
  function future(as_of) {
    return !!as_of && as_of > W.TODAY;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  return {
    AXES: AXES,
    mount: mount,
    head: head,
    where: where,
    wheres: wheres,
    quotable: quotable,
    future: future,
    esc: esc,
  };
})();
