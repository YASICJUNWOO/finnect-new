/* 시안 여덟이 공유하는 데이터와 카피. **한 곳에서만 정의한다.**
 *
 * 시안마다 행 수나 제목 길이가 달라지면 밀도 비교가 통째로 깨진다.
 * 시안이 가진 것은 이 데이터를 그리는 코드뿐이다.
 *
 * 값은 실제 두 출처의 형태를 따른 표본이다 — 제품 화면에 예시 데이터를 넣지
 * 않는다는 규칙(DESIGN.md §7)은 제품 라우트의 것이고, 비교 하네스는 밀도를
 * 재려면 행이 있어야 한다. 목업 전용이다. */

window.NOTICE_DATA = (function () {
  /** 마감. **57%는 날짜가 아니다** — 기업마당 접수 기간의 실제 분포다.
   * `kind` 가 'date' 가 아닌 것을 시안마다 어떻게 놓는지가 갈리는 자리다. */
  var rows = [
    {
      d: { kind: "date", days: 2, text: "2026-08-23" },
      title: "2026년 성남시 창업기업 성장지원 사업 참여기업 모집 공고",
      org: "성남산업진흥원",
      cat: "창업",
      src: "bizinfo",
      docs: 4,
    },
    {
      d: { kind: "date", days: 5, text: "2026-08-26" },
      title: "초기창업패키지 창업기업 모집 공고 (2026년 3차)",
      org: "창업진흥원",
      cat: "창업",
      src: "kstartup",
      docs: 7,
    },
    {
      d: { kind: "always", text: "예산 소진시까지" },
      title: "소상공인 경영개선 바우처 지원사업 참여자 상시 모집",
      org: "소상공인시장진흥공단",
      cat: "경영",
      src: "bizinfo",
      docs: 3,
    },
    {
      d: { kind: "date", days: 9, text: "2026-08-30" },
      title: "중소기업 기술개발(R&D) 역량강화 바우처 지원 공고",
      org: "중소기업기술정보진흥원",
      cat: "기술",
      src: "bizinfo",
      docs: 6,
    },
    {
      d: { kind: "date", days: 12, text: "2026-09-02" },
      title: "2026년 수출바우처 사업(중소기업 수출지원기반활용) 참여기업 모집",
      org: "KOTRA",
      cat: "수출",
      src: "bizinfo",
      docs: 5,
    },
    {
      d: { kind: "rolling", text: "상시 접수" },
      title: "청년창업사관학교 재도전 트랙 상시 모집",
      org: "중소벤처기업진흥공단",
      cat: "창업",
      src: "kstartup",
      docs: 8,
    },
    {
      d: { kind: "date", days: 16, text: "2026-09-06" },
      title: "지역주력산업 육성 기술개발 지원과제 신규 공모",
      org: "대구테크노파크",
      cat: "기술",
      src: "bizinfo",
      docs: 4,
    },
    {
      d: { kind: "date", days: 19, text: "2026-09-09" },
      title: "스마트공장 구축 및 고도화 지원사업 참여기업 모집",
      org: "중소벤처기업부",
      cat: "제조",
      src: "bizinfo",
      docs: 9,
    },
    {
      d: { kind: "none", text: "안 알려줬어요" },
      title: "제주형 그린바이오 실증지원 참여기업 모집",
      org: "제주테크노파크",
      cat: "기술",
      src: "kstartup",
      docs: 2,
    },
    {
      d: { kind: "date", days: 23, text: "2026-09-13" },
      title: "중소기업 정책자금 융자계획 공고 (하반기)",
      org: "중소벤처기업진흥공단",
      cat: "융자",
      src: "bizinfo",
      docs: 3,
    },
    {
      d: { kind: "date", days: 27, text: "2026-09-17" },
      title: "콘텐츠 스타트업 창업도약 프로그램 참여팀 모집",
      org: "한국콘텐츠진흥원",
      cat: "창업",
      src: "kstartup",
      docs: 5,
    },
    {
      d: { kind: "always", text: "예산 소진시까지" },
      title: "울산 지역 중소기업 시제품 제작 지원 상시 모집",
      org: "울산창조경제혁신센터",
      cat: "제조",
      src: "bizinfo",
      docs: 0,
    },
  ];

  /** S5 상세. 목록 첫 행과 같은 공고다. */
  var detail = {
    d: rows[0].d,
    title: rows[0].title,
    org: "성남산업진흥원",
    supervisor: "성남시",
    cat: "창업",
    src: "bizinfo",
    period: "2026-08-04 ~ 2026-08-23",
    summary: [
      "성남시 소재 창업 7년 이내 기업의 성장 단계별 애로 해소를 위해 시제품 제작, 마케팅, 인증 취득 등에 소요되는 비용을 지원합니다.",
      "기업당 최대 2천만 원 이내에서 총 사업비의 70%까지 지원하며, 자부담 30%는 현금으로 부담해야 합니다.",
    ],
    docs: [
      { name: "사업계획서", items: 16, form: true },
      { name: "사업자등록증 사본", items: 0, form: false },
      { name: "최근 2개년 재무제표", items: 0, form: false },
      { name: "개인정보 수집·이용 동의서", items: 3, form: true },
    ],
    files: [
      { name: "2026년 성남시 창업기업 성장지원 사업 공고문.hwp", ok: true },
      { name: "[붙임1] 사업계획서 양식.hwpx", ok: true },
      { name: "[붙임2] 제출서류 목록.pdf", ok: true },
      { name: "[붙임3] 사업비 집행 기준.pdf", ok: false },
    ],
    gaps: [
      { t: "왜 맞는지", w: "사업 위키가 있어야 공고 취지와 대 볼 수 있어요. 아직 위키가 없어요." },
      { t: "자격이 되는지", w: "사업자 정보를 아직 안 받았어요. 받으면 못 넘는 공고는 목록에서 빼 드려요." },
      { t: "어떻게 심사해요", w: "서류에서 심사 항목을 아직 안 뽑았어요. 서류 글자는 이미 읽어 뒀어요." },
      { t: "놓치기 쉬운 것", w: "심사 항목을 뽑고 나서 알려 드릴 수 있어요." },
    ],
  };

  /** 카피. **시안마다 한 글자도 바꾸지 않는다.** 길이가 달라지면 밀도 비교가 깨진다. */
  var copy = {
    recTitle: "추천 공고",
    recSub: "공고 취지와 사업 내용이 맞는 순서로 골라 드려요",
    recHole: "아직 사업 위키가 없어서 못 고르고 있어요. 파일을 올리면 여기에 세 건이 뜹니다.",
    allTitle: "전체 공고",
    allSub: "마감이 가까운 순서예요. 이미 마감된 공고는 빼 뒀어요.",
    total: 31327,
    back: "← 공고 목록",
    periodLabel: "접수 기간",
    srcLabel: "원문",
    srcLink: "공고 원문 보기",
    summaryTitle: "개요",
    docsTitle: "낼 서류",
    writeCta: "여기에 뭘 쓰는지 보기",
    filesTitle: "첨부",
    upload: "파일 올리기",
  };

  var SRC = { bizinfo: "기업마당", kstartup: "K-Startup" };

  /** 마감 한 줄. 시안이 이 문자열을 그대로 쓰거나 제 방식으로 다시 만든다. */
  function deadlineText(d) {
    if (d.kind === "date") return d.days <= 7 ? "D-" + d.days : d.text + " 마감";
    return d.text;
  }

  /** 급한가. **유일한 액센트가 걸리는 자리다**(DESIGN.md §7 "액센트는 마감뿐"). */
  function urgent(d) {
    return d.kind === "date" && d.days <= 7;
  }

  return {
    rows: rows,
    detail: detail,
    copy: copy,
    SRC: SRC,
    deadlineText: deadlineText,
    urgent: urgent,
    n: function (v) {
      return v.toLocaleString("ko-KR");
    },
  };
})();
