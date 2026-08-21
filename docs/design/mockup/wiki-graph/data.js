/* 공유 데이터. **한 곳에서만 정의한다.**
 *
 * 시안마다 노드 수나 채움 비율이 달라지면 밀도 비교가 통째로 깨진다.
 * 시안이 다르게 가져도 되는 것은 **그리는 방식**이지 무엇을 그리느냐가 아니다.
 *
 * 데이터는 `src/finnect/wiki/topics.py` 의 SECTORS · ORBIT 을 그대로 옮긴 것이다.
 * 순서도 그대로다 — **순서가 곧 배치 순서다**(ADR-0017).
 */

/* 구획 여섯. topics.py SECTORS */
var SECTORS = {
  registration: "등록 정보",
  principal: "대표와 이력",
  problem_solution: "문제와 해결",
  market_customer: "시장과 고객",
  result_money: "성과와 자금",
  team_plan: "팀과 계획",
};

/* 궤도 열다섯. topics.py ORBIT 순서 그대로.
 * filled · conflicted 는 픽스처다 — 열 찼고 하나 충돌한 상태를 만든다.
 * **빈 자리와 배지가 없으면 시안이 그 상태를 어떻게 그리는지 볼 수 없다.** */
var NODES = [
  { key: "identity", label: "우리가 하는 일", kind: "identity", sector: "registration", filled: true, conflicted: false, sources: 4,
    lines: ["도로 함몰 위험을 지하 공동 탐사로 미리 찾아내요", "사업계획서.pdf · 3쪽"] , files: ["사업계획서.pdf"] },

  { key: "biz",   label: "사업자 정보", kind: "company", sector: "registration", filled: true,  conflicted: false, sources: 2,
    lines: ["사업자등록번호 128-88-02914", "개업연월일 2024-03-11", "사업자등록증.jpg"] , files: ["사업자등록증.jpg"] },
  { key: "where", label: "소재지",     kind: "company", sector: "registration", filled: true,  conflicted: false, sources: 2,
    lines: ["경기도 성남시 분당구 판교로 255", "사업자등록증.jpg"] , files: ["사업자등록증.jpg"] },
  { key: "what",  label: "업종",       kind: "company", sector: "registration", filled: true,  conflicted: false, sources: 1,
    lines: ["업태 정보통신업", "종목 응용 소프트웨어 개발 및 공급업", "사업자등록증.jpg"] , files: ["사업자등록증.jpg"] },
  { key: "who",   label: "대표자",     kind: "company", sector: "principal",    filled: true,  conflicted: false, sources: 2,
    lines: ["김다시로", "1991-06-02", "사업자등록증.jpg"] , files: ["사업자등록증.jpg", "사업계획서.pdf"] },
  { key: "grants", label: "수령 이력", kind: "company", sector: "principal",    filled: false, conflicted: false, sources: 0,
    lines: ["아직 비어 있어요. 중복수혜 제한을 판정하려면 이 자리가 필요해요"] , files: [] },

  { key: "problem",  label: "문제 인식",     kind: "content", sector: "problem_solution", filled: true,  conflicted: false, sources: 3,
    lines: ["전국 지반침하 사고 연 200건대. 사전 탐지가 육안 순찰에 기대고 있어요", "사업계획서.pdf · 5쪽"] , files: ["사업계획서.pdf"] },
  { key: "solution", label: "솔루션과 기술", kind: "content", sector: "problem_solution", filled: true,  conflicted: false, sources: 3,
    lines: ["GPR 신호를 학습 모델로 판독해 공동 후보를 자동 표시해요", "사업계획서.pdf · 8쪽"] , files: ["사업계획서.pdf", "IR덱.pptx"] },
  { key: "customer", label: "목표 고객",     kind: "content", sector: "market_customer",  filled: true,  conflicted: true,  sources: 2,
    lines: ["값이 갈렸어요 — 지자체 도로과 / 민간 시공사", "사업계획서.pdf · 11쪽 · IR덱.pptx · 6쪽"] , files: ["사업계획서.pdf", "IR덱.pptx"] },
  { key: "market",   label: "시장과 경쟁",   kind: "content", sector: "market_customer",  filled: false, conflicted: false, sources: 0,
    lines: ["아직 비어 있어요"] , files: [] },
  { key: "region",   label: "지역 연계",     kind: "content", sector: "market_customer",  filled: false, conflicted: false, sources: 0,
    lines: ["아직 비어 있어요. 지자체 공고를 고르는 데 쓰여요"] , files: [] },
  { key: "traction", label: "매출과 성과",   kind: "content", sector: "result_money",     filled: true,  conflicted: false, sources: 2,
    lines: ["매출액 340,000,000원 (2025)", "재무제표.xlsx"] , files: ["재무제표.xlsx"] },
  { key: "finance",  label: "자금 현황",     kind: "content", sector: "result_money",     filled: false, conflicted: false, sources: 0,
    lines: ["아직 비어 있어요"] , files: [] },
  { key: "team",     label: "팀 구성",       kind: "content", sector: "team_plan",        filled: true,  conflicted: false, sources: 3,
    lines: ["직원 수 15명 (2026-08)", "재무제표.xlsx · IR덱.pptx · 4쪽"] , files: ["재무제표.xlsx", "IR덱.pptx"] },
  { key: "roadmap",  label: "로드맵",        kind: "content", sector: "team_plan",        filled: false, conflicted: false, sources: 0,
    lines: ["아직 비어 있어요"] , files: [] },
];

/* 파일 넷. **근거는 문자열이 아니라 연결이다**(SPEC F1-3) — 어느 파일이 어느 자리를
 * 채웠는지 위에 `files` 로 달아 뒀다. 시안 C 가 그 연결을 선으로 그린다 */
var SOURCE_FILES = ["사업자등록증.jpg", "사업계획서.pdf", "IR덱.pptx", "재무제표.xlsx"];

var FILLED = NODES.filter(function (n) { return n.filled; }).length;
var CONFLICTS = NODES.filter(function (n) { return n.conflicted; }).length;

var byKind = function (k) { return NODES.filter(function (n) { return n.kind === k; }); };

/* ── 각도 배치 ────────────────────────────────────────────────────────────
 * `web/components/Orbit.tsx` 의 place() 를 그대로 옮겼다. **세 시안이 같은 각도를
 * 쓴다** — 각도가 달라지면 무엇 때문에 달라 보이는지 분간이 안 된다. */
var GAP = 14;

function place(nodes) {
  if (!nodes.length) return { placed: [], arcs: [] };
  var runs = [];
  nodes.forEach(function (n) {
    var last = runs[runs.length - 1];
    if (last && last[0].sector === n.sector) last.push(n);
    else runs.push([n]);
  });
  var step = (360 - runs.length * GAP) / nodes.length;
  var placed = [], arcs = [], deg = -90 - step / 2;
  runs.forEach(function (run) {
    var from = deg + GAP / 2;
    deg += GAP / 2;
    run.forEach(function (n) {
      deg += step;
      placed.push(Object.assign({}, n, { angle: deg }));
    });
    arcs.push({ sector: run[0].sector, from: from, to: deg + GAP / 2 });
    deg += GAP / 2;
  });
  return { placed: placed, arcs: arcs };
}

