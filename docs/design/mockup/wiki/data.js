/* 공유 데이터. **여기가 정본이다.**
 *
 * 시안마다 사실 수나 채움 비율이 달라지면 밀도 비교가 통째로 깨진다. 시안이 다르게
 * 가져도 되는 것은 **그리는 방식**이지 무엇을 그리느냐가 아니다.
 *
 * ── 어디서 왔나 ────────────────────────────────────────────
 * `tests/fixtures/wiki/facts.json` 118건을 `src/finnect/wiki/topics.py` 의 라우팅
 * (SLOT_ALIASES · TOPIC_NODE · ORBIT)으로 자리 열다섯에 앉힌 것이다. **지어낸 값이
 * 하나도 없다** — 전부 `tests/fixtures/wiki/` 의 실제 파일에 적힌 문장이고 `anchor` 는
 * 그 파일의 해독 텍스트에 그대로 있다(`tests/test_wiki_extract.py` 가 118개를 막는다).
 *
 * `page` 는 실제로 파싱해서 얻었다. **PDF·PPTX 에만 있다** — hwpx·docx·xlsx 에는
 * 쪽이라는 것이 없어서 null 이고, 그게 정상 상태다. 118건 중 42건에 쪽이 붙는다.
 *
 * ── 손으로 맞춘 곳 하나 ────────────────────────────────────
 * **스캔본 둘의 파서 메타를 OCR 기준으로 적었다**(`사업자등록증_스캔.pdf` ·
 * `현장사진_파일럿매장.jpg`). 이 파일을 만들 때 이 서버에 `uv sync --group ocr` 이
 * 안 깔려 있어 `empty` · `unsupported` 가 나왔는데, **제품은 사용자 파일에 OCR 이
 * 켜져 있다**(`USER_FILE_OCR` · ADR-0030). 안 맞추면 화면에 「안 읽혔어요 · 근거 1」
 * 이라는 스스로 모순된 줄이 뜬다 — 실제로 G5 에서 그렇게 나왔다.
 * 나머지 다섯의 파서·쪽수·청크 수는 전부 실제로 파싱해서 얻은 값이다.
 *
 * ── 손으로 맞춘 곳 하나 ────────────────────────────────────
 * **스캔본 둘의 파서 메타를 OCR 기준으로 적었다**(`사업자등록증_스캔.pdf` ·
 * `현장사진_파일럿매장.jpg`). 이 파일을 만들 때 이 서버에 `uv sync --group ocr` 이
 * 없어서 파싱이 `empty` · `unsupported` 로 나왔는데, **제품은 사용자 파일에 OCR 이
 * 켜져 있다**(`USER_FILE_OCR` · ADR-0030). 안 맞추면 화면에 「안 읽혔어요 · 근거 1」
 * 이라는 스스로 모순된 줄이 뜬다 — G5 에서 실제로 그렇게 나왔다.
 * **나머지 다섯의 파서·쪽수·청크 수는 전부 실제로 파싱해서 얻은 값이다.**
 *
 * ── 밀도 둘 ───────────────────────────────────────────────
 *   가벼움  등록증 + 회사소개서 두 장만 올린 상태. 사실 29 · 자리 10/15
 *   무거움  일곱 장 전부. 사실 118 · 자리 15/15 · 표시 단위 47 · 근거 117
 *
 * **가벼움은 무거움의 부분집합이다.** 파일 둘로 좁힌 것이라 빈 자리 다섯(수령 이력 ·
 * 목표 고객 · 시장과 경쟁 · 자금 현황 · 로드맵)은 지어낸 공백이 아니라 그 두 파일에
 * 실제로 없는 것이다. 갈리는 것이 밀도 하나뿐이어야 비교가 성립한다.
 *
 * ── 픽스처가 심어 둔 함정 넷 ───────────────────────────────
 *  1. **직원 수가 넷이다** — 7 → 8 → 10 → 15. 이름이 전부 다르다(상시 근로자 ·
 *     종업원 수 · 구성원 · 임직원). 시계열이지 충돌이 아니다.
 *  2. **마지막 직원 수 15의 as_of 가 2026-08-31 이다** — 오늘(2026-08-21)보다 열흘
 *     뒤다. `current` 가 "가장 늦은 시점"이라 미래 날짜도 current 다.
 *  3. **매출액에 진짜 충돌이 있다** — 24,100,000 과 86,400,000 이 둘 다 재무제표
 *     2025-12-31 에서 나왔다. 같은 슬롯 · 같은 시점 · 다른 값.
 *  4. **`업력 1년 6개월` 은 갈 자리가 없다** — topics.py 가 일부러 슬롯에서 뺐다
 *     (공고마다 기준일이 달라 개업일로 계산한다). `uncategorized` 로 서야 맞다.
 *
 * 다시 만들려면 레포 루트에서:
 *   uv run python docs/design/mockup/wiki/assets/make-data.py
 */

window.WIKI = (function () {
  var D = {
 "sectors": {
  "registration": "등록 정보",
  "principal": "대표와 이력",
  "problem_solution": "문제와 해결",
  "market_customer": "시장과 고객",
  "result_money": "성과와 자금",
  "team_plan": "팀과 계획"
 },
 "orbit": [
  {
   "key": "identity",
   "label": "우리가 하는 일",
   "kind": "identity",
   "sector": "registration",
   "slots": [
    "company_name"
   ],
   "node": "identity"
  },
  {
   "key": "biz",
   "label": "사업자 정보",
   "kind": "company",
   "sector": "registration",
   "slots": [
    "business_no",
    "corp_no",
    "founded_on"
   ],
   "node": null
  },
  {
   "key": "where",
   "label": "소재지",
   "kind": "company",
   "sector": "registration",
   "slots": [
    "location"
   ],
   "node": null
  },
  {
   "key": "what",
   "label": "업종",
   "kind": "company",
   "sector": "registration",
   "slots": [
    "industry",
    "industry_item"
   ],
   "node": null
  },
  {
   "key": "who",
   "label": "대표자",
   "kind": "company",
   "sector": "principal",
   "slots": [
    "ceo_name",
    "ceo_birth"
   ],
   "node": null
  },
  {
   "key": "grants",
   "label": "수령 이력",
   "kind": "company",
   "sector": "principal",
   "slots": [
    "gov_program"
   ],
   "node": null
  },
  {
   "key": "problem",
   "label": "문제 인식",
   "kind": "content",
   "sector": "problem_solution",
   "slots": [],
   "node": "problem"
  },
  {
   "key": "solution",
   "label": "솔루션과 기술",
   "kind": "content",
   "sector": "problem_solution",
   "slots": [],
   "node": "solution"
  },
  {
   "key": "customer",
   "label": "목표 고객",
   "kind": "content",
   "sector": "market_customer",
   "slots": [],
   "node": "customer"
  },
  {
   "key": "market",
   "label": "시장과 경쟁",
   "kind": "content",
   "sector": "market_customer",
   "slots": [],
   "node": "market"
  },
  {
   "key": "region",
   "label": "지역 연계",
   "kind": "content",
   "sector": "market_customer",
   "slots": [],
   "node": "region"
  },
  {
   "key": "traction",
   "label": "매출과 성과",
   "kind": "content",
   "sector": "result_money",
   "slots": [
    "revenue"
   ],
   "node": "traction"
  },
  {
   "key": "finance",
   "label": "자금 현황",
   "kind": "content",
   "sector": "result_money",
   "slots": [
    "capital",
    "funding"
   ],
   "node": "finance"
  },
  {
   "key": "team",
   "label": "팀 구성",
   "kind": "content",
   "sector": "team_plan",
   "slots": [
    "headcount"
   ],
   "node": "team"
  },
  {
   "key": "roadmap",
   "label": "로드맵",
   "kind": "content",
   "sector": "team_plan",
   "slots": [],
   "node": "roadmap"
  }
 ],
 "slots": {
  "company_name": {
   "label": "상호",
   "dated": false,
   "qualified": false,
   "eligibility": false,
   "unit": "text"
  },
  "business_no": {
   "label": "사업자등록번호",
   "dated": false,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "corp_no": {
   "label": "법인등록번호",
   "dated": false,
   "qualified": false,
   "eligibility": false,
   "unit": "text"
  },
  "founded_on": {
   "label": "개업연월일",
   "dated": false,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "ceo_name": {
   "label": "대표자",
   "dated": false,
   "qualified": false,
   "eligibility": false,
   "unit": "text"
  },
  "ceo_birth": {
   "label": "대표자 생년월일",
   "dated": false,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "location": {
   "label": "소재지",
   "dated": true,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "industry": {
   "label": "업종(업태)",
   "dated": true,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "industry_item": {
   "label": "업종(종목)",
   "dated": true,
   "qualified": false,
   "eligibility": true,
   "unit": "text"
  },
  "headcount": {
   "label": "직원 수",
   "dated": true,
   "qualified": false,
   "eligibility": true,
   "unit": "count"
  },
  "capital": {
   "label": "자본금",
   "dated": true,
   "qualified": false,
   "eligibility": false,
   "unit": "money"
  },
  "revenue": {
   "label": "매출액",
   "dated": true,
   "qualified": false,
   "eligibility": false,
   "unit": "money"
  },
  "funding": {
   "label": "조달액",
   "dated": true,
   "qualified": true,
   "eligibility": false,
   "unit": "money"
  },
  "gov_program": {
   "label": "정부지원 수혜 이력",
   "dated": true,
   "qualified": true,
   "eligibility": true,
   "unit": "money"
  }
 },
 "files": [
  {
   "filename": "성남시_시범사업_신청서.hwpx",
   "ext": "hwpx",
   "as_of": "2025-08-22",
   "parser": "hwpx/zip",
   "parse_status": "ok",
   "page_count": null,
   "chunk_count": 2
  },
  {
   "filename": "사업계획서_2026_초기창업패키지.docx",
   "ext": "docx",
   "as_of": "2025-11-30",
   "parser": "docx/zip",
   "parse_status": "ok",
   "page_count": null,
   "chunk_count": 10
  },
  {
   "filename": "회사소개서_v3.pdf",
   "ext": "pdf",
   "as_of": "2026-01-31",
   "parser": "pdf/plumber",
   "parse_status": "ok",
   "page_count": 4,
   "chunk_count": 6
  },
  {
   "filename": "재무제표_2025.xlsx",
   "ext": "xlsx",
   "as_of": "2025-12-31",
   "parser": "xlsx/openpyxl",
   "parse_status": "ok",
   "page_count": null,
   "chunk_count": 4
  },
  {
   "filename": "피치덱_2026H2.pptx",
   "ext": "pptx",
   "as_of": "2026-08-31",
   "parser": "pptx/python-pptx",
   "parse_status": "ok",
   "page_count": 12,
   "chunk_count": 12
  },
  {
   "filename": "사업자등록증_스캔.pdf",
   "ext": "pdf",
   "as_of": "2024-03-11",
   "parser": "ocr/rapidocr",
   "parse_status": "ok",
   "page_count": 1,
   "chunk_count": 1
  },
  {
   "filename": "현장사진_파일럿매장.jpg",
   "ext": "jpg",
   "as_of": "2025-07-14",
   "parser": "ocr/rapidocr",
   "parse_status": "ok",
   "page_count": null,
   "chunk_count": 1
  }
 ],
 "facts": [
  {
   "kind": "slot",
   "home": "identity",
   "slot": "company_name",
   "label": "상호",
   "qualifier": null,
   "value": "주식회사 다시로",
   "display": "주식회사 다시로",
   "eligibility": false,
   "dated": false,
   "text": "기업명은 주식회사 다시로다",
   "anchor": "기업명 주식회사 다시로",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "기업명"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "business_no",
   "label": "사업자등록번호",
   "qualifier": null,
   "value": "501-86-33271",
   "display": "501-86-33271",
   "eligibility": true,
   "dated": false,
   "text": "사업자등록번호 501-86-33271",
   "anchor": "사업자등록번호 501-86-33271",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "사업자등록번호"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_name",
   "label": "대표자",
   "qualifier": null,
   "value": "윤세라",
   "display": "윤세라",
   "eligibility": false,
   "dated": false,
   "text": "대표자는 윤세라다",
   "anchor": "대표자 윤세라 생년월일",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "대표자"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_birth",
   "label": "대표자 생년월일",
   "qualifier": null,
   "value": "1992-07-04",
   "display": "1992-07-04",
   "eligibility": true,
   "dated": false,
   "text": "대표자 생년월일 1992. 07. 04.",
   "anchor": "생년월일 1992. 07. 04.",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "생년월일"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "founded_on",
   "label": "개업연월일",
   "qualifier": null,
   "value": "2024-03-11",
   "display": "2024-03-11",
   "eligibility": true,
   "dated": false,
   "text": "개업연월일 2024. 03. 11.",
   "anchor": "개업연월일 2024. 03. 11.",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "개업연월일"
  },
  {
   "kind": "slot",
   "home": "uncategorized",
   "slot": null,
   "label": "업력",
   "qualifier": null,
   "value": "1년 6개월",
   "display": "1년 6개월",
   "eligibility": false,
   "dated": false,
   "text": "업력 1년 6개월 (2025-08 기준으로 문서에 박혀 있다)",
   "anchor": "업력 1년 6개월",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "업력"
  },
  {
   "kind": "slot",
   "home": "where",
   "slot": "location",
   "label": "소재지",
   "qualifier": null,
   "value": "경기도 성남시 분당구 판교로 255, 3층",
   "display": "경기도 성남시 분당구 판교로 255, 3층",
   "eligibility": true,
   "dated": true,
   "text": "소재지 경기도 성남시 분당구 판교로 255, 3층",
   "anchor": "소재지 경기도 성남시 분당구 판교로 255, 3층",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "소재지"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry",
   "label": "업종(업태)",
   "qualifier": null,
   "value": "정보통신업",
   "display": "정보통신업",
   "eligibility": true,
   "dated": true,
   "text": "업태는 정보통신업이다",
   "anchor": "업태 / 종목 정보통신업",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "업태"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry_item",
   "label": "업종(종목)",
   "qualifier": null,
   "value": "응용 소프트웨어 개발 및 공급업",
   "display": "응용 소프트웨어 개발 및 공급업",
   "eligibility": true,
   "dated": true,
   "text": "종목은 응용 소프트웨어 개발 및 공급업이다",
   "anchor": "정보통신업 / 응용 소프트웨어 개발 및 공급업",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "종목"
  },
  {
   "kind": "slot",
   "home": "team",
   "slot": "headcount",
   "label": "직원 수",
   "qualifier": null,
   "value": "7",
   "display": "7명",
   "eligibility": true,
   "dated": true,
   "text": "상시 근로자 7명 (2025. 08. 기준)",
   "anchor": "상시 근로자 7명",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "상시 근로자"
  },
  {
   "kind": "slot",
   "home": "traction",
   "slot": "revenue",
   "label": "매출액",
   "qualifier": null,
   "value": "24100000",
   "display": "24,100,000원",
   "eligibility": false,
   "dated": true,
   "text": "직전연도 매출액 24,100천원 (2024년)",
   "anchor": "직전연도 매출액 24,100천원 (2024년)",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2024-12-31",
   "raw_key": "직전연도 매출액"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "capital",
   "label": "자본금",
   "qualifier": null,
   "value": "120000000",
   "display": "120,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "자본금 120,000천원",
   "anchor": "자본금 120,000천원",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": "자본금"
  },
  {
   "kind": "slot",
   "home": "grants",
   "slot": "gov_program",
   "label": "정부지원 수혜 이력",
   "qualifier": "예비창업패키지",
   "value": "38000000",
   "display": "38,000,000원",
   "eligibility": true,
   "dated": true,
   "text": "예비창업패키지 · 창업진흥원 · 2023. 05. ~ 2024. 02. · 38,000천원 · 수행 완료",
   "anchor": "예비창업패키지 창업진흥원",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2023-05-01",
   "raw_key": "지원금"
  },
  {
   "kind": "slot",
   "home": "grants",
   "slot": "gov_program",
   "label": "정부지원 수혜 이력",
   "qualifier": "소상공인 정책자금",
   "value": "50000000",
   "display": "50,000,000원",
   "eligibility": true,
   "dated": true,
   "text": "소상공인 정책자금 · 소상공인시장진흥공단 · 2025. 04. · 50,000천원 (대출) · 실행",
   "anchor": "소상공인 정책자금 소상공인시장진흥공단",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-04-01",
   "raw_key": "지원금"
  },
  {
   "kind": "slot",
   "home": "grants",
   "slot": "gov_program",
   "label": "정부지원 수혜 이력",
   "qualifier": "성남시 디지털 전환 시범사업",
   "value": "20000000",
   "display": "20,000,000원",
   "eligibility": true,
   "dated": true,
   "text": "성남시 디지털 전환 시범사업 · 성남산업진흥원 · 2025. 10. ~ 2026. 03. · 20,000천원 · 본 신청 건",
   "anchor": "성남시 디지털 전환 시범사업 성남산업진흥원",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-10-01",
   "raw_key": "지원금"
  },
  {
   "kind": "node",
   "home": "identity",
   "fact_key": "service_core",
   "topic": "vision",
   "text": "바코드와 QR로 입출고를 자동 기록하고 발주 시점을 알린다. POS 교체 없이 휴대폰만으로 시작할 수 있다",
   "anchor": "POS 교체 없이 휴대폰만으로 시작할 수 있다",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "customer",
   "fact_key": "target_small_retail",
   "topic": "target_customer",
   "text": "적용 대상은 성남시 관내 식자재·생활용품 소매 사업자 40개소",
   "anchor": "성남시 관내 식자재·생활용품 소매 사업자 40개소",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_12_stores",
   "topic": "customer_evidence",
   "text": "2025년 6월부터 성남·용인 지역 파일럿 매장 12개소에서 실사용을 진행했다",
   "anchor": "성남·용인 지역 파일럿 매장 12개소에서 실사용을 진행했다",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_time_41_9",
   "topic": "customer_evidence",
   "text": "일평균 재고 확인 시간이 41분에서 9분으로 줄었다",
   "anchor": "일평균 재고 확인 시간이 41분에서 9분으로 줄었고",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_stockout_42_11",
   "topic": "customer_evidence",
   "text": "품절로 인한 판매 기회 상실이 매장당 월 4.2건에서 1.1건으로 줄었다",
   "anchor": "품절로 인한 판매 기회 상실이 매장당 월 4.2건에서 1.1건으로 감소했다",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_retention_34_51",
   "topic": "customer_evidence",
   "text": "월 재구매율이 도입 3개월 차 34%에서 5개월 차 51%로 올랐다",
   "anchor": "월 재구매율은 도입 3개월 차 34%에서 5개월 차 51%로 상승했다",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_snip_tenant",
   "topic": "region_link",
   "text": "2024년 6월부터 성남산업진흥원 입주기업이다",
   "anchor": "2024년 6월부터 성남산업진흥원 입주기업으로 있다",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_merchants_3",
   "topic": "region_link",
   "text": "성남 지역 상인회 3개소와 업무협약을 체결했고, 파일럿 매장 12개소 중 9개소를 상인회를 통해 확보했다",
   "anchor": "성남 지역 상인회 3개소와 업무협약을 체결했고",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "patent_offline_sync",
   "topic": "patent",
   "text": "특허 출원 — 오프라인 환경에서의 재고 기록 동기화 방법 및 장치 (2025. 08. 12.)",
   "anchor": "오프라인 환경에서의 재고 기록 동기화 방법 및 장치",
   "file": "성남시_시범사업_신청서.hwpx",
   "page": null,
   "as_of": "2025-08-22",
   "raw_key": null
  },
  {
   "kind": "slot",
   "home": "identity",
   "slot": "company_name",
   "label": "상호",
   "qualifier": null,
   "value": "주식회사 다시로",
   "display": "주식회사 다시로",
   "eligibility": false,
   "dated": false,
   "text": "기업명은 주식회사 다시로다",
   "anchor": "기업명 주식회사 다시로",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "기업명"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "business_no",
   "label": "사업자등록번호",
   "qualifier": null,
   "value": "501-86-33271",
   "display": "501-86-33271",
   "eligibility": true,
   "dated": false,
   "text": "사업자등록번호 501-86-33271",
   "anchor": "사업자등록번호 501-86-33271",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "사업자등록번호"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_name",
   "label": "대표자",
   "qualifier": null,
   "value": "윤세라",
   "display": "윤세라",
   "eligibility": false,
   "dated": false,
   "text": "대표자는 윤세라다",
   "anchor": "대표자 윤세라 (1992. 07. 04.)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "대표자"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_birth",
   "label": "대표자 생년월일",
   "qualifier": null,
   "value": "1992-07-04",
   "display": "1992-07-04",
   "eligibility": true,
   "dated": false,
   "text": "대표자 윤세라 (1992. 07. 04.)",
   "anchor": "윤세라 (1992. 07. 04.)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "생년월일"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "founded_on",
   "label": "개업연월일",
   "qualifier": null,
   "value": "2024-03-11",
   "display": "2024-03-11",
   "eligibility": true,
   "dated": false,
   "text": "개업연월일 2024. 03. 11.",
   "anchor": "개업연월일 2024. 03. 11.",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "개업연월일"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry",
   "label": "업종(업태)",
   "qualifier": null,
   "value": "정보통신업",
   "display": "정보통신업",
   "eligibility": true,
   "dated": true,
   "text": "업태는 정보통신업이다",
   "anchor": "업태 정보통신업",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "업태"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry_item",
   "label": "업종(종목)",
   "qualifier": null,
   "value": "응용 소프트웨어 개발 및 공급업",
   "display": "응용 소프트웨어 개발 및 공급업",
   "eligibility": true,
   "dated": true,
   "text": "종목은 응용 소프트웨어 개발 및 공급업이다",
   "anchor": "종목 응용 소프트웨어 개발 및 공급업",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "종목"
  },
  {
   "kind": "slot",
   "home": "where",
   "slot": "location",
   "label": "소재지",
   "qualifier": null,
   "value": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "display": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "eligibility": true,
   "dated": true,
   "text": "소재지 경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "anchor": "소재지 경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "소재지"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "corp_no",
   "label": "법인등록번호",
   "qualifier": null,
   "value": "110111-8842301",
   "display": "110111-8842301",
   "eligibility": false,
   "dated": false,
   "text": "법인등록번호 110111-8842301",
   "anchor": "법인등록번호 110111-8842301",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "법인등록번호"
  },
  {
   "kind": "slot",
   "home": "team",
   "slot": "headcount",
   "label": "직원 수",
   "qualifier": null,
   "value": "8",
   "display": "8명",
   "eligibility": true,
   "dated": true,
   "text": "종업원 수 8명 (2025. 11. 기준)",
   "anchor": "종업원 수 8명 (2025. 11. 기준)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "종업원 수"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "capital",
   "label": "자본금",
   "qualifier": null,
   "value": "120000000",
   "display": "120,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "자본금 1억 2,000만원",
   "anchor": "자본금 1억 2,000만원",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": "자본금"
  },
  {
   "kind": "slot",
   "home": "traction",
   "slot": "revenue",
   "label": "매출액",
   "qualifier": null,
   "value": "24100000",
   "display": "24,100,000원",
   "eligibility": false,
   "dated": true,
   "text": "직전연도 매출 2,410만원 (2024년)",
   "anchor": "직전연도 매출 2,410만원 (2024년)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2024-12-31",
   "raw_key": "직전연도 매출"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "시드",
   "value": "300000000",
   "display": "300,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "시드 투자 3억원 — 2025. 09. 클로징. 경기 지역 액셀러레이터 리드",
   "anchor": "시드 투자 3억원",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-09-30",
   "raw_key": "시드 투자"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "정책자금",
   "value": "50000000",
   "display": "50,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "정책자금 대출 5,000만원 — 2025. 04. 소상공인시장진흥공단",
   "anchor": "정책자금 대출 5,000만원",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-04-30",
   "raw_key": "정책자금 대출"
  },
  {
   "kind": "node",
   "home": "identity",
   "fact_key": "service_core",
   "topic": "vision",
   "text": "바코드와 QR로 입출고 기록을 자동으로 남겨, 발주 시점을 놓치지 않게 하는 소상공인용 재고관리 소프트웨어",
   "anchor": "바코드와 QR로 입출고 기록을 자동으로 남겨, 발주 시점을 놓치지 않게 하는",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "survey_21_of_30",
   "topic": "customer_problem",
   "text": "성남·용인 소상공인 30명 중 21명(70%)이 재고를 수기 또는 기억으로만 관리하고 있었다",
   "anchor": "30명 중 21명(70%)이 재고를 수기 또는 기억으로만 관리하고 있었다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "churn_reason_input",
   "topic": "customer_problem",
   "text": "재고관리 소프트웨어 사용 중단 사유가 3명 중 3명 모두 \"입력이 번거로워서\"였다",
   "anchor": "사용 중단 사유는 \"입력이 번거로워서\"가 3명 중 3명으로 일치했다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "customer",
   "fact_key": "target_small_retail",
   "topic": "target_customer",
   "text": "1차 목표 시장은 매장 1~3개를 직접 운영하는 식자재·생활용품 소매 사업자다",
   "anchor": "매장 1~3개를 직접 운영하는 식자재·생활용품 소매 사업자다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "market",
   "fact_key": "market_gap_under5",
   "topic": "market_size",
   "text": "종사자 5인 미만 사업체가 다수를 차지하며, 이 구간이 기존 솔루션의 가격대와 가장 크게 어긋나 있다",
   "anchor": "종사자 5인 미만 사업체가 다수를 차지하며",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "market",
   "fact_key": "competition_axis_friction",
   "topic": "competitor",
   "text": "경쟁의 축은 기능 수가 아니라 도입 마찰이다",
   "anchor": "경쟁의 축은 기능 수가 아니라 도입 마찰이다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "dev_stage_1_done",
   "topic": "development_status",
   "text": "1단계 모듈의 프로토타입 개발을 마쳤다",
   "anchor": "현재 1단계 모듈의 프로토타입 개발을 마쳤다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_12_stores",
   "topic": "customer_evidence",
   "text": "2025년 6월부터 성남·용인 지역 파일럿 매장 12곳에서 실사용 중이다",
   "anchor": "성남·용인 지역 파일럿 매장 12곳에서 실사용 중이다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_time_41_9",
   "topic": "customer_evidence",
   "text": "일평균 재고 확인 소요 시간이 도입 전 41분에서 도입 후 9분으로 줄었다",
   "anchor": "일평균 재고 확인 소요 시간이 도입 전 41분에서 도입 후 9분으로 줄었다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_stockout_42_11",
   "topic": "customer_evidence",
   "text": "품절로 인한 판매 기회 상실 건수가 매장당 월 평균 4.2건에서 1.1건으로 줄었다",
   "anchor": "매장당 월 평균 4.2건에서 1.1건으로 줄었다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_retention_34_51",
   "topic": "customer_evidence",
   "text": "월 단위 재구매율이 도입 3개월 차 34%에서 5개월 차 51%로 상승했다",
   "anchor": "월 단위 재구매율이 도입 3개월 차 34%에서 5개월 차 51%로 상승했다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "patent_offline_sync",
   "topic": "patent",
   "text": "특허 출원 — 오프라인 환경에서의 재고 기록 동기화 방법 및 장치 (10-2025-0114882)",
   "anchor": "2025. 08. 출원 (10-2025-0114882)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "pricing_29000_base",
   "topic": "revenue_model",
   "text": "매장 단위 월 구독. 기본 요금은 매장당 월 2만 9천원이다",
   "anchor": "기본 요금은 매장당 월 2만 9천원이며",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "gtm_merchant_assoc",
   "topic": "go_to_market",
   "text": "1차 판로는 지역 상인회와 도매 유통사다. 파일럿 12곳 중 9곳이 상인회를 통해 확보됐다",
   "anchor": "1차 판로는 지역 상인회와 도매 유통사다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_snip_tenant",
   "topic": "region_link",
   "text": "성남산업진흥원 입주기업 (2024. 06. ~ 현재)",
   "anchor": "성남산업진흥원 입주기업 (2024. 06. ~ 현재)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_merchants_3",
   "topic": "region_link",
   "text": "성남 지역 상인회 3개소와 업무협약 체결 (2025. 04. ~ 2025. 10.)",
   "anchor": "성남 지역 상인회 3개소와 업무협약 체결",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_pilot_15km",
   "topic": "region_link",
   "text": "파일럿 매장 12곳이 모두 반경 15km 이내에 있어 문제 발생 시 당일 방문이 가능했다",
   "anchor": "파일럿 매장 12곳이 모두 반경 15km 이내에 있어",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "roadmap",
   "fact_key": "roadmap_phase1",
   "topic": "roadmap",
   "text": "1단계 2026. 01. ~ 06. — POS 3사 연동 완료, 유료 전환 매장 120곳",
   "anchor": "POS 3사 연동 완료, 유료 전환 매장 120곳",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "roadmap",
   "fact_key": "roadmap_phase2",
   "topic": "roadmap",
   "text": "2단계 2026. 07. ~ 12. — 경기 남부 지역 영업망 구축, 유료 전환 매장 300곳",
   "anchor": "경기 남부 지역 영업망 구축, 유료 전환 매장 300곳",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "team",
   "fact_key": "team_roles_2025_11",
   "topic": "team",
   "text": "2025년 11월 기준 개발 4명(서버 2·모바일 2), 영업 2명, 운영 1명, 경영 1명",
   "anchor": "서버 2명, 모바일 2명. 오프라인 동기화 및 스캔 인식 담당",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "team",
   "fact_key": "ceo_retail_experience",
   "topic": "team",
   "text": "대표자는 2021년부터 3년간 성남 지역에서 식자재 소매점 두 곳을 직접 운영했다",
   "anchor": "2021년부터 3년간 성남 지역에서 식자재 소매점 두 곳을 직접 운영했다",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "finance",
   "fact_key": "gov_budget_70m",
   "topic": "cost",
   "text": "정부지원금 집행 계획 합계 7,000만원 — 인건비 3,600 · 외주용역비 1,800 · 지급수수료 600 · 광고선전비 500 · 기타 500만원",
   "anchor": "개발자 1명 12개월 (월 300만원)",
   "file": "사업계획서_2026_초기창업패키지.docx",
   "page": null,
   "as_of": "2025-11-30",
   "raw_key": null
  },
  {
   "kind": "slot",
   "home": "identity",
   "slot": "company_name",
   "label": "상호",
   "qualifier": null,
   "value": "주식회사 다시로",
   "display": "주식회사 다시로",
   "eligibility": false,
   "dated": false,
   "text": "상호 주식회사 다시로 (DASIRO Inc.)",
   "anchor": "상호 주식회사 다시로 (DASIRO Inc.)",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "상호"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_name",
   "label": "대표자",
   "qualifier": null,
   "value": "윤세라",
   "display": "윤세라",
   "eligibility": false,
   "dated": false,
   "text": "대표자는 윤세라다",
   "anchor": "대표자 윤세라 설립일",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "대표자"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "founded_on",
   "label": "개업연월일",
   "qualifier": null,
   "value": "2024-03-11",
   "display": "2024-03-11",
   "eligibility": true,
   "dated": false,
   "text": "설립일 2024년 3월 11일",
   "anchor": "설립일 2024년 3월 11일",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "설립일"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "business_no",
   "label": "사업자등록번호",
   "qualifier": null,
   "value": "501-86-33271",
   "display": "501-86-33271",
   "eligibility": true,
   "dated": false,
   "text": "사업자등록번호 501-86-33271",
   "anchor": "사업자등록번호 501-86-33271",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "사업자등록번호"
  },
  {
   "kind": "slot",
   "home": "where",
   "slot": "location",
   "label": "소재지",
   "qualifier": null,
   "value": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "display": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "eligibility": true,
   "dated": true,
   "text": "본사 경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "anchor": "본사 경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "본사"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry",
   "label": "업종(업태)",
   "qualifier": null,
   "value": "정보통신업",
   "display": "정보통신업",
   "eligibility": true,
   "dated": true,
   "text": "업종 정보통신업 / 응용 소프트웨어 개발 및 공급업",
   "anchor": "업종 정보통신업 / 응용 소프트웨어 개발 및 공급업",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "업태"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry_item",
   "label": "업종(종목)",
   "qualifier": null,
   "value": "응용 소프트웨어 개발 및 공급업",
   "display": "응용 소프트웨어 개발 및 공급업",
   "eligibility": true,
   "dated": true,
   "text": "업종 정보통신업 / 응용 소프트웨어 개발 및 공급업",
   "anchor": "정보통신업 / 응용 소프트웨어 개발 및 공급업",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "종목"
  },
  {
   "kind": "slot",
   "home": "team",
   "slot": "headcount",
   "label": "직원 수",
   "qualifier": null,
   "value": "10",
   "display": "10명",
   "eligibility": true,
   "dated": true,
   "text": "구성원 10명 (2026년 1월 기준)",
   "anchor": "구성원 10명 (2026년 1월 기준)",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": "구성원"
  },
  {
   "kind": "node",
   "home": "identity",
   "fact_key": "service_core",
   "topic": "vision",
   "text": "바코드와 QR로 입출고 기록을 자동으로 남깁니다. 남은 수량이 기준 아래로 내려가면 발주 시점을 알립니다",
   "anchor": "바코드와 QR로 입출고 기록을 자동으로 남깁니다",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "survey_21_of_30",
   "topic": "customer_problem",
   "text": "2025년 성남·용인 지역 소상공인 30명 중 21명이 재고를 수기 또는 기억으로만 관리하고 있었습니다",
   "anchor": "21명이 재고를 수기 또는 기억으로만 관리하고 있었습니다",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "churn_reason_input",
   "topic": "customer_problem",
   "text": "재고관리 소프트웨어를 써 본 30명 중 4명, 그중 3명이 6개월 안에 중단했고 사유는 셋 다 \"입력이 번거로워서\"였습니다",
   "anchor": "중단 사유는 셋 다 같았습니다",
   "file": "회사소개서_v3.pdf",
   "page": 2,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "self_qr_labeling",
   "topic": "service_feature",
   "text": "표준 바코드가 없는 소분 상품용으로 자체 QR을 발행합니다",
   "anchor": "자체 QR 발행 표준 바코드가 없는 소분 상품용",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "pricing_29000_base",
   "topic": "pricing",
   "text": "기본 요금제 월 29,000원 — 입출고 기록, 발주 알림, 상품 등록",
   "anchor": "기본 29,000원 입출고 기록, 발주 알림, 상품 등록",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_time_41_9",
   "topic": "customer_evidence",
   "text": "일평균 재고 확인 시간이 41분에서 9분으로 줄었습니다",
   "anchor": "일평균 재고 확인 시간이 41분에서 9분으로 줄었습니다",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_stockout_42_11",
   "topic": "customer_evidence",
   "text": "품절로 놓친 판매 기회가 매장당 월 4.2건에서 1.1건으로 줄었습니다",
   "anchor": "품절로 놓친 판매 기회가 매장당 월 4.2건에서 1.1건으로 줄었습니다",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_retention_34_51",
   "topic": "customer_evidence",
   "text": "월 재구매율이 도입 3개월 차 34%에서 5개월 차 51%로 올랐습니다",
   "anchor": "월 재구매율이 도입 3개월 차 34%에서 5개월 차 51%로 올랐습니다",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "paid_stores_102_2026_01",
   "topic": "revenue",
   "text": "2026년 1월 현재 유료 매장은 102곳입니다",
   "anchor": "2026년 1월 현재 유료 매장은 102곳입니다",
   "file": "회사소개서_v3.pdf",
   "page": 3,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_snip_tenant",
   "topic": "region_link",
   "text": "성남산업진흥원 입주기업 (2024년 6월 ~ 현재)",
   "anchor": "성남산업진흥원 입주기업 (2024년 6월 ~ 현재)",
   "file": "회사소개서_v3.pdf",
   "page": 4,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_merchants_3",
   "topic": "region_link",
   "text": "성남 지역 상인회 3개소와 업무협약 (2025년 4월 ~ 10월)",
   "anchor": "성남 지역 상인회 3개소와 업무협약",
   "file": "회사소개서_v3.pdf",
   "page": 4,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "region",
   "fact_key": "region_pilot_15km",
   "topic": "region_link",
   "text": "파일럿 매장 12곳이 모두 반경 15km 안에 있어 문제가 생기면 그날 찾아갈 수 있었습니다",
   "anchor": "파일럿 매장 12곳이 모두 반경 15km 안에 있어",
   "file": "회사소개서_v3.pdf",
   "page": 4,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "patent_offline_sync",
   "topic": "patent",
   "text": "특허 출원 10-2025-0114882 (2025년 8월)",
   "anchor": "10-2025-0114882",
   "file": "회사소개서_v3.pdf",
   "page": 4,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "team",
   "fact_key": "ceo_retail_experience",
   "topic": "team",
   "text": "대표 윤세라는 2021년부터 3년간 성남에서 식자재 소매점 두 곳을 직접 운영했습니다",
   "anchor": "2021년부터 3년간 성남에서 식자재 소매점 두 곳을 직접 운영했습니다",
   "file": "회사소개서_v3.pdf",
   "page": 4,
   "as_of": "2026-01-31",
   "raw_key": null
  },
  {
   "kind": "slot",
   "home": "traction",
   "slot": "revenue",
   "label": "매출액",
   "qualifier": null,
   "value": "24100000",
   "display": "24,100,000원",
   "eligibility": false,
   "dated": true,
   "text": "제1기(2024) 매출액 24,100,000원",
   "anchor": "매출액 24100000 86400000",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2024-12-31",
   "raw_key": "매출액"
  },
  {
   "kind": "slot",
   "home": "traction",
   "slot": "revenue",
   "label": "매출액",
   "qualifier": null,
   "value": "86400000",
   "display": "86,400,000원",
   "eligibility": false,
   "dated": true,
   "text": "제2기(2025) 매출액 86,400,000원",
   "anchor": "합계 49200000 37200000 86400000",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-12-31",
   "raw_key": "매출액"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "capital",
   "label": "자본금",
   "qualifier": null,
   "value": "120000000",
   "display": "120,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "자본금 120,000,000원 (2025.12.31 현재)",
   "anchor": "Ⅰ. 자본금 120000000 120000000",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-12-31",
   "raw_key": "자본금"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "시드",
   "value": "300000000",
   "display": "300,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다",
   "anchor": "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-09-30",
   "raw_key": "자본잉여금"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "정책자금",
   "value": "50000000",
   "display": "50,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "장기차입금 5,000만원은 2025.04 소상공인시장진흥공단 정책자금입니다",
   "anchor": "장기차입금 5,000만원은 2025.04 소상공인시장진흥공단 정책자금입니다",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-04-30",
   "raw_key": "장기차입금"
  },
  {
   "kind": "node",
   "home": "finance",
   "fact_key": "runway_18m",
   "topic": "cost",
   "text": "2025년말 결손금이 자본금을 초과하며, 2025.09 유치 자금으로 향후 18개월 운영이 가능하다고 판단했습니다",
   "anchor": "2025.09 유치 자금으로 향후 18개월 운영이 가능하다고 판단했습니다",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-12-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "paid_stores_93_2025_12",
   "topic": "revenue",
   "text": "12월 유료 매장 93곳. 파일럿 12곳 중 7곳이 2025.06 유료 전환한 것이 시작점입니다",
   "anchor": "12월 유료 매장 93곳",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-12-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "revenue_mix_2025",
   "topic": "revenue",
   "text": "2025년 매출 8,640만원 — 구독 4,920만원 · 용역 3,720만원",
   "anchor": "구독 매출은 서비스 제공 기간에 걸쳐 월 단위로 인식합니다",
   "file": "재무제표_2025.xlsx",
   "page": null,
   "as_of": "2025-12-31",
   "raw_key": null
  },
  {
   "kind": "slot",
   "home": "team",
   "slot": "headcount",
   "label": "직원 수",
   "qualifier": null,
   "value": "15",
   "display": "15명",
   "eligibility": true,
   "dated": true,
   "text": "임직원 15명 (2026년 8월 기준)",
   "anchor": "임직원 15명",
   "file": "피치덱_2026H2.pptx",
   "page": 10,
   "as_of": "2026-08-31",
   "raw_key": "임직원"
  },
  {
   "kind": "slot",
   "home": "where",
   "slot": "location",
   "label": "소재지",
   "qualifier": null,
   "value": "경기도 성남시 분당구 판교로 255, 3층",
   "display": "경기도 성남시 분당구 판교로 255, 3층",
   "eligibility": true,
   "dated": true,
   "text": "경기도 성남시 분당구 판교로 255, 3층",
   "anchor": "경기도 성남시 분당구 판교로 255, 3층 · 대표 윤세라",
   "file": "피치덱_2026H2.pptx",
   "page": 12,
   "as_of": "2026-08-31",
   "raw_key": "소재지"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "capital",
   "label": "자본금",
   "qualifier": null,
   "value": "120000000",
   "display": "120,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "자본금 1억 2,000만원 — 2024.03 설립 시 납입",
   "anchor": "자본금 1억 2,000만원 2024.03",
   "file": "피치덱_2026H2.pptx",
   "page": 11,
   "as_of": "2024-03-31",
   "raw_key": "자본금"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "시드",
   "value": "280000000",
   "display": "280,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "시드 라운드 2.8억원 — 2025.09 경기 지역 액셀러레이터 리드",
   "anchor": "시드 라운드 2.8억원",
   "file": "피치덱_2026H2.pptx",
   "page": 11,
   "as_of": "2025-09-30",
   "raw_key": "시드 라운드"
  },
  {
   "kind": "slot",
   "home": "finance",
   "slot": "funding",
   "label": "조달액",
   "qualifier": "정책자금",
   "value": "50000000",
   "display": "50,000,000원",
   "eligibility": false,
   "dated": true,
   "text": "정책자금 대출 5,000만원 — 2025.04 소상공인시장진흥공단, 만기 2028.04",
   "anchor": "정책자금 대출 5,000만원 2025.04",
   "file": "피치덱_2026H2.pptx",
   "page": 11,
   "as_of": "2025-04-30",
   "raw_key": "정책자금 대출"
  },
  {
   "kind": "node",
   "home": "identity",
   "fact_key": "service_core",
   "topic": "vision",
   "text": "바코드와 QR로 입출고를 자동으로 기록하고, 발주 시점을 먼저 알린다",
   "anchor": "바코드와 QR 로 입출고를 자동으로 기록하고, 발주 시점을 먼저 알린다",
   "file": "피치덱_2026H2.pptx",
   "page": 1,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "survey_21_of_30",
   "topic": "customer_problem",
   "text": "2025년 3~5월 성남·용인 소상공인 30명 대면 인터뷰 — 21/30이 재고를 수기 또는 기억으로만 관리",
   "anchor": "2025년 3~5월 성남·용인 소상공인 30명 대면 인터뷰",
   "file": "피치덱_2026H2.pptx",
   "page": 2,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "market",
   "fact_key": "competition_axis_friction",
   "topic": "competitor",
   "text": "C사가 무료인데도 이탈률이 높은 이유와 A·B사가 기능이 많은데도 못 들어오는 이유가 같은 축의 양끝이다",
   "anchor": "같은 축의 양끝이다",
   "file": "피치덱_2026H2.pptx",
   "page": 3,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_time_41_9",
   "topic": "customer_evidence",
   "text": "파일럿 12곳에서 일평균 재고 확인 시간 41분 → 9분",
   "anchor": "41분 → 9분",
   "file": "피치덱_2026H2.pptx",
   "page": 5,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_stockout_42_11",
   "topic": "customer_evidence",
   "text": "매장당 월 품절 발생 4.2 → 1.1건",
   "anchor": "4.2 → 1.1건",
   "file": "피치덱_2026H2.pptx",
   "page": 5,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "problem",
   "fact_key": "pilot_retention_34_51",
   "topic": "customer_evidence",
   "text": "월 재구매율 34% → 51%",
   "anchor": "34% → 51%",
   "file": "피치덱_2026H2.pptx",
   "page": 5,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "customer",
   "fact_key": "target_small_retail",
   "topic": "target_customer",
   "text": "1차 — 매장 1~3개를 직접 운영하는 식자재·생활용품 소매 사업자",
   "anchor": "매장 1~3개를 직접 운영하는 식자재·생활용품 소매 사업자",
   "file": "피치덱_2026H2.pptx",
   "page": 7,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "gtm_merchant_assoc",
   "topic": "go_to_market",
   "text": "진입 경로는 지역 상인회와 도매 유통사. 파일럿 12곳 중 9곳이 상인회를 통해 들어왔다",
   "anchor": "진입 경로는 지역 상인회와 도매 유통사",
   "file": "피치덱_2026H2.pptx",
   "page": 7,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "pricing_29000_base",
   "topic": "pricing",
   "text": "기본 요금제 월 2만 9천원 — 입출고 기록, 발주 알림, 상품 등록",
   "anchor": "기본 2만 9천원 입출고 기록, 발주 알림, 상품 등록",
   "file": "피치덱_2026H2.pptx",
   "page": 8,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "traction",
   "fact_key": "paid_stores_93_2025_12",
   "topic": "revenue",
   "text": "유료 매장 93곳 (2025년 월말 기준)",
   "anchor": "유료 매장 93곳",
   "file": "피치덱_2026H2.pptx",
   "page": 6,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "roadmap",
   "fact_key": "roadmap_phase2",
   "topic": "roadmap",
   "text": "2026 하반기 — 경기 남부 영업망 구축, 유료 매장 300곳",
   "anchor": "경기 남부 영업망 구축",
   "file": "피치덱_2026H2.pptx",
   "page": 9,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "roadmap",
   "fact_key": "roadmap_bridge_500m",
   "topic": "roadmap",
   "text": "이번 라운드(브리지) 5억원 목표 — 2026.10 클로징 목표, 영업 확장 및 다점포 개발",
   "anchor": "이번 라운드 (브리지) 5억원 목표",
   "file": "피치덱_2026H2.pptx",
   "page": 11,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "team",
   "fact_key": "team_roles_2026_08",
   "topic": "team",
   "text": "2026년 8월 기준 개발 8명(서버 4·모바일 3·데이터 1), 영업 4명, 운영 2명, 경영 1명",
   "anchor": "서버 4명, 모바일 3명, 데이터 1명",
   "file": "피치덱_2026H2.pptx",
   "page": 10,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "team",
   "fact_key": "ceo_retail_experience",
   "topic": "team",
   "text": "대표 윤세라는 2021년부터 3년간 성남에서 식자재 소매점 두 곳을 직접 운영했다",
   "anchor": "2021년부터 3년간 성남에서 식자재 소매점 두 곳을 직접 운영했다",
   "file": "피치덱_2026H2.pptx",
   "page": 10,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "node",
   "home": "finance",
   "fact_key": "runway_2027q1",
   "topic": "cost",
   "text": "2025년말 현금 1억 8,270만원. 현재 소진 속도로 2027년 1분기까지 운영 가능하다",
   "anchor": "현재 소진 속도로 2027년 1분기까지 운영 가능하다",
   "file": "피치덱_2026H2.pptx",
   "page": 11,
   "as_of": "2026-08-31",
   "raw_key": null
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "business_no",
   "label": "사업자등록번호",
   "qualifier": null,
   "value": "501-86-33271",
   "display": "501-86-33271",
   "eligibility": true,
   "dated": false,
   "text": "등록번호 501-86-33271",
   "anchor": "등록번호:501-86-33271",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "등록번호"
  },
  {
   "kind": "slot",
   "home": "identity",
   "slot": "company_name",
   "label": "상호",
   "qualifier": null,
   "value": "주식회사 다시로",
   "display": "주식회사 다시로",
   "eligibility": false,
   "dated": false,
   "text": "법인명 주식회사 다시로",
   "anchor": ":주식회사다시로",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "법인명"
  },
  {
   "kind": "slot",
   "home": "who",
   "slot": "ceo_name",
   "label": "대표자",
   "qualifier": null,
   "value": "윤세라",
   "display": "윤세라",
   "eligibility": false,
   "dated": false,
   "text": "대표자 윤세라",
   "anchor": ": 윤세라",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "대표자"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "founded_on",
   "label": "개업연월일",
   "qualifier": null,
   "value": "2024-03-11",
   "display": "2024-03-11",
   "eligibility": true,
   "dated": false,
   "text": "개업연월일 2024년 03월 11일",
   "anchor": "2024년03월11일",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "개업연월일"
  },
  {
   "kind": "slot",
   "home": "biz",
   "slot": "corp_no",
   "label": "법인등록번호",
   "qualifier": null,
   "value": "110111-8842301",
   "display": "110111-8842301",
   "eligibility": false,
   "dated": false,
   "text": "법인등록번호 110111-8842301",
   "anchor": "110111-8842301",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "법인등록번호"
  },
  {
   "kind": "slot",
   "home": "where",
   "slot": "location",
   "label": "소재지",
   "qualifier": null,
   "value": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "display": "경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "eligibility": true,
   "dated": true,
   "text": "사업장소재지 경기도 성남시 분당구 판교로 255, 3층 (삼평동)",
   "anchor": "경기도성남시분당구판교로255,3층(삼평동)",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "사업장소재지"
  },
  {
   "kind": "slot",
   "home": "what",
   "slot": "industry_item",
   "label": "업종(종목)",
   "qualifier": null,
   "value": "응용 소프트웨어 개발 및 공급업",
   "display": "응용 소프트웨어 개발 및 공급업",
   "eligibility": true,
   "dated": true,
   "text": "종목 응용 소프트웨어 개발 및 공급업",
   "anchor": "응용 소프트웨어개발및공급업",
   "file": "사업자등록증_스캔.pdf",
   "page": null,
   "as_of": "2024-03-11",
   "raw_key": "종목"
  },
  {
   "kind": "node",
   "home": "solution",
   "fact_key": "self_qr_labeling",
   "topic": "service_feature",
   "text": "파일럿 매장에 자체 QR을 부착한 구간 (2025.07.14 현장)",
   "anchor": "자체QR부착구간",
   "file": "현장사진_파일럿매장.jpg",
   "page": null,
   "as_of": "2025-07-14",
   "raw_key": null
  }
 ]
};

  /* 오늘. **하드코딩한다** — 목업이 날마다 다르게 보이면 스크린샷을 못 비교한다.
   * 픽스처의 미래 날짜(2026-08-31)가 미래인 채로 남아야 함정 2가 살아 있다. */
  var TODAY = "2026-08-21";

  /* 가벼움에 남기는 파일 둘. **자리를 골라 비우지 않는다** — 파일로 좁히면
   * 빈 자리가 저절로 정해지고, 그 공백이 진짜다 */
  var LIGHT_FILES = ["사업자등록증_스캔.pdf", "회사소개서_v3.pdf"];

  function factsOf(density) {
    if (density !== "light") return D.facts;
    return D.facts.filter(function (f) { return LIGHT_FILES.indexOf(f.file) >= 0; });
  }

  /* 근거 하나. **파일명과 쪽이 따로 온다** — 미리 이어 붙이면 화면이 "3쪽"을
   * 다르게 쓸 자유가 없다(lib/wiki.ts Evidence 와 같은 모양) */
  function ev(f) {
    return { filename: f.file, page: f.page, quote: f.anchor, as_of: f.as_of };
  }

  /* 슬롯 값 묶기. **(슬롯, 한정어)가 키다** — 한정어가 다르면 다른 것이다(시드/정책자금).
   *
   * 시점이 다르면 성장이고 같으면 모순이다. dated=false 인데 값이 갈리면 그것도 충돌이다.
   * 이 판정은 서버(`wiki/merge.py`)가 하는 일이고 여기서는 화면이 무엇을 받는지만 흉내낸다. */
  function values(fs) {
    var g = {};
    fs.forEach(function (f) {
      var k = f.slot + "|" + (f.qualifier || "");
      (g[k] = g[k] || []).push(f);
    });
    return Object.keys(g).map(function (k) {
      var items = g[k], head = items[0];
      /* 같은 값 + 같은 시점은 근거만 늘린다. **사실이 둘이 되면 틀렸다** */
      var byVal = {};
      items.forEach(function (f) {
        var vk = f.value + "|" + (f.as_of || "");
        if (!byVal[vk]) byVal[vk] = { value: f.value, display: f.display, as_of: f.as_of, evidence: [] };
        byVal[vk].evidence.push(ev(f));
      });
      var vs = Object.keys(byVal).map(function (x) { return byVal[x]; });
      vs.sort(function (a, b) { return (b.as_of || "").localeCompare(a.as_of || ""); });

      var latest = vs.length ? vs[0].as_of : null;
      var current = head.dated
        ? vs.filter(function (v) { return v.as_of === latest; })
        : vs;
      var history = head.dated
        ? vs.filter(function (v) { return v.as_of !== latest; })
        : [];
      /* 값이 갈렸다 — 같은 시점에 다른 값이거나, 시점이 없는 슬롯에 값이 여럿이다 */
      var distinct = {};
      current.forEach(function (v) { distinct[v.value] = 1; });
      var conflict = Object.keys(distinct).length > 1;

      current.forEach(function (v) { v.status = conflict ? "conflict" : "current"; });
      history.forEach(function (v) { v.status = "superseded"; });

      return {
        slot: head.slot, label: head.label, qualifier: head.qualifier,
        eligibility: head.eligibility, dated: head.dated,
        conflict: conflict, current: current, history: history,
        future: current.some(function (v) { return v.as_of && v.as_of > TODAY; }),
        evidence_count: items.length
      };
    });
  }

  /* 서술 문장 묶기. **`fact_key` 가 같으면 사실 하나에 근거 여럿이다.**
   *
   * 재구매율 34→51% 가 네 문서에 다른 문장으로 있다. 문자열로는 못 묶어서
   * 픽스처가 키를 들고 있고, 안 묶으면 사실 넷이 되어 틀린다. */
  function statements(fs) {
    var g = {};
    fs.forEach(function (f) {
      var k = f.fact_key || f.text;
      (g[k] = g[k] || []).push(f);
    });
    return Object.keys(g).map(function (k) {
      var items = g[k];
      /* 가장 늦은 문서의 표현을 쓴다. **고쳐 쓰지 않는다** — 원문에 있는 문장이어야
       * 근거 대조가 성립한다(rank.quotable 과 같은 이유) */
      var sorted = items.slice().sort(function (a, b) {
        return (b.as_of || "").localeCompare(a.as_of || "");
      });
      return {
        fact_key: k, text: sorted[0].text, topic: sorted[0].topic,
        evidence: sorted.map(ev), evidence_count: items.length
      };
    });
  }

  /* 자리 열다섯. **순서가 곧 배치 순서다**(ADR-0017) — 여기서 다시 정렬하지 않는다. */
  function nodes(density) {
    var fs = factsOf(density);
    var byHome = {};
    fs.forEach(function (f) { (byHome[f.home] = byHome[f.home] || []).push(f); });

    return D.orbit.map(function (o) {
      var mine = byHome[o.key] || [];
      var vals = values(mine.filter(function (f) { return f.kind === "slot"; }));
      var stmts = statements(mine.filter(function (f) { return f.kind === "node"; }));
      var fileSet = {};
      mine.forEach(function (f) { fileSet[f.file] = 1; });
      return {
        key: o.key, label: o.label, kind: o.kind, sector: o.sector,
        sectorLabel: D.sectors[o.sector],
        eligibility: vals.some(function (v) { return v.eligibility; }) ||
          (o.slots || []).some(function (s) { return D.slots[s] && D.slots[s].eligibility; }),
        values: vals, statements: stmts,
        /* 표시 단위 — 슬롯 값 + 문장. 화면에 몇 덩어리가 서는가 */
        items: vals.length + stmts.length,
        /* 근거 수. **밀도는 여기 있다** — 자리마다 3~19 로 갈린다 */
        evidence_count: mine.length,
        source_count: Object.keys(fileSet).length,
        filled: mine.length > 0,
        conflicted: vals.some(function (v) { return v.conflict; }),
        future: vals.some(function (v) { return v.future; })
      };
    });
  }

  /* 갈 자리를 못 찾은 것. **버리지 않는다** — 화면이 건수를 적는다 */
  function orphans(density) {
    return factsOf(density).filter(function (f) { return f.home === "uncategorized"; });
  }

  function files(density) {
    var fs = factsOf(density);
    return D.files
      .filter(function (f) {
        return density !== "light" || LIGHT_FILES.indexOf(f.filename) >= 0;
      })
      .map(function (f) {
        var mine = fs.filter(function (x) { return x.file === f.filename; });
        var homes = {};
        mine.forEach(function (x) { if (x.home !== "uncategorized") homes[x.home] = 1; });
        return Object.assign({}, f, { fact_count: mine.length, nodes: Object.keys(homes) });
      });
  }

  function summary(density) {
    var ns = nodes(density);
    return {
      total: ns.length,
      filled: ns.filter(function (n) { return n.filled; }).length,
      conflicts: ns.filter(function (n) { return n.conflicted; }).length,
      uncategorized: orphans(density).length,
      items: ns.reduce(function (a, n) { return a + n.items; }, 0),
      evidence: ns.reduce(function (a, n) { return a + n.evidence_count; }, 0),
      files: files(density).length
    };
  }

  return {
    sectors: D.sectors, orbit: D.orbit, slots: D.slots, raw: D,
    TODAY: TODAY, LIGHT_FILES: LIGHT_FILES,
    nodes: nodes, files: files, orphans: orphans, summary: summary
  };
})();
