"""기업마당 공고 필터 — 예비창업~3년 미만 창업가가 지원 가능한 공고만 남긴다.

의존성 없다. 표준 라이브러리만 쓴다.
LLM 호출 0회 · 첨부 다운로드 0건 · 기업마당 오픈API 응답 필드만 본다.

    python filter.py --test        픅스처 54건 + 단위 15건 (네트워크·DB 불필요)

로직과 선택 근거는 로직과근거.md 에 있다.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import date

HERE = pathlib.Path(__file__).parent

# ══════════════════════════════════════════════════════════════════
# 축1 — 신청 주체가 기업인가
#   bsnsSumryCn 은 "☞ 지원대상 … ☞ 지원내용 …" 구조이고 1,538건 전부(100%)에 있다.
#   한국어는 수식이 앞에 오므로 첫 ☞ 절의 끝 명사가 신청 주체다. (☞ = U+261E)
# ══════════════════════════════════════════════════════════════════
INST_HEAD = re.compile(
    r"(공공기관|지방자치단체|자치단체|지자체|정부기관|공기관|중앙부처|"
    r"대학|연구기관|연구소|기관ㆍ기업|기업ㆍ기관|기관·기업|기업·기관|"
    r"단체|법인|협회|조합|센터|재단|진흥원|테크노파크|기관)$")
SUPPLIER = re.compile(
    r"(제공이? 가능|제공할|납품할|수행할|수행 ?가능|운영할|운영 ?가능|"
    r"위탁|주관기관|운영사|수행기관|수요기관|정예팀|컨소시엄|"
    r"보유하거나|확보ㆍ유통|확보·유통|구축ㆍ운영|구축·운영)")
BIZ_HEAD = re.compile(
    r"(창업기업|스타트업|창업자|창업팀|예비창업자|중소기업|중소벤처기업|중견기업|"
    r"소상공인|기업|사업자|업체|소기업|벤처기업|제조기업|수출기업|자영업자|"
    r"기업인|대표자|팀|개인사업자|사업주|중기업|기업체|법인사업자)$")
MID_LARGE = re.compile(r"(중견기업|중견 ?기업|중소ㆍ중견|중소·중견|대기업)")

# 2026-08-18 — 끝 명사 파싱 버그 3건을 고치면서 넣은 규칙들.
#   셋 다 원인이 같았다. **끝 명사를 잘라내는 자리가 틀렸다.**
#   축1 자체(기업이냐 기관이냐)는 맞았는데 잘린 조각이 명사가 아니라서 보류로 떨어졌다.
#   1,524건에 재면 52건이 보류→타겟계로 올라오고 **반대 방향은 0건이다.**

# 숫자에 붙은 마침표로는 문장을 자르지 않는다.
#   `‘26. 1. 1.(일) 이후 … 예비창업자 및 업종전환희망자`(125047) 가 첫 마침표에서 잘려
#   끝명사가 `‘26` 이 됐다. 날짜로 시작하는 지원대상 절은 흔하다 — 이 규칙만으로 20건이 풀린다.
SENT_SPLIT = re.compile(r"(?<!\d)\.|;| - |①|②|—")
# 끝에 남는 지시어. 명사구가 아니라 뒤에 올 문장을 가리키는 말이다.
FILLER_TAIL = re.compile(r"\s*(아래|다음|위|상기|해당|각)\s*$")
# 꼬리 조사. `중견기업으로 아래`(121389) 의 `으로` 가 BIZ_HEAD 의 $ 앵커를 깨뜨렸다.
TAIL_PARTICLE = re.compile(r"\s*(등|외|들|의|과|와|으로서|으로써|으로|로서|로써|이며|이고)\s*$")
# 출처 조사. 이게 붙은 앞말은 주체가 아니라 **어디서 받았는지**다.
ABLATIVE = re.compile(r"^(으로부터|로부터|에게서)")

# ══════════════════════════════════════════════════════════════════
# 축2 — 중분류 제외. 첨부를 열어 '행정 신청서'임을 확인한 3개 값만.
#   나머지 21개 값은 근거가 없어 제외하지 않고 T4 로 내린다.
# ══════════════════════════════════════════════════════════════════
SKIP_MLSFC = {"융자", "시험/인증", "국내일반인력",
              # 국가 R&D 과제의 수행형태 분류. 순수 연구개발 과제라 제외한다.
              # 이름으로 추측한 것이 아니라 국가 R&D 가 실제로 쓰는 구분이다.
              # 장비 활용·인건비 지원·인프라 제공처럼 R&D 어휘만 붙은 것은 여기 안 들어온다.
              "단독기술개발", "공동기술개발", "혼합(단독+공동)"}
# ══════════════════════════════════════════════════════════════════
# 축2d — 계획서로 심사하지 않는 세부분야. 2026-08-18 추가.
#
#   T4(미검증 21개 값) 를 근거 없이 남겨 뒀더니 `[경기] 안양시 안양춤축제 연계
#   중소기업 홍보관 참가` 같은 것이 계속 나왔다. 그래서 층마다 표본을 뽑아
#   **첨부를 전부 열고** 선정 방식과 제출물을 실측했다 — 20건, 추출 20/20 성공.
#
#     층                표본  계획서 심사  선정 방식
#     인력(고용지원금)      5      0      요건충족 전원 / 견적서
#     금융(보증·보험)       4      0      요건충족 전원 / 선착순
#     내수(행사·부스)       5      0      적격심사 / 추첨 / 서류심사
#     제도(인증)           3      0      요건충족 전원 / 서류심사
#
#   20건 중 발표·대면평가가 있는 것은 1건, 추첨이 1건이었다.
#   `사업계획서` 라는 말이 나온 4건도 실체가 달랐다 —
#     `사업계획서(휴게시설 현장사진, 견적서 등 포함)`     ← 설비 견적
#     `[서식1] 지원사업 신청서 및 사업계획서(견적서 2부)`   ← 설비 견적
#     `사업계획서 1부 <서식2>` (신용보증수수료 환급)        ← 금융 서식
#     `멘토링 희망 내용 예) … 사업계획서 작성 등`          ← 주제 예시, 제출물 아님
#
#   안양춤축제(125203)가 이 축의 기준 사례다. 공고문 원문이 이렇다.
#     선정방법 : 적격심사 ※ 16개사 이상 모집시 서류심사 실시
#     제출서류 - 참가신청서 1부 - 전시ㆍ판매 제품 설명서 1부 - 동의서 - 사업자등록증명
#     부스 위치 배정은 추첨에 의해 배정함을 원칙으로 하되…
#   `시장규모`·`연간 총매출액` 같은 성장 라벨이 잡히지만 그건 사업계획서 문항이
#   아니라 **참가신청서의 제품 정보 칸**이다. 정부가 주는 것은 부스 자리다.
#
#   146건이 걸리고 **전부 T4 안에 있다(T1~T3 에 0건).** 층 경계가 실재한다는 뜻이다.
# ══════════════════════════════════════════════════════════════════
SKIP_MLSFC_NOPLAN = {
    # 인력 — 근로자 채용·유지 요건을 증빙하면 나오는 보조금. 54건
    "고용유지", "고용환경개선", "작업환경개선", "교육/훈련/연수",
    "국내전문인력", "인력정보제공", "해외인력",
    # 금융 — 신용평가·보험 가입으로 심사한다. `융자` 와 같은 계열. 25건
    "보증", "보험(수출+무역)",
    # 내수 — 정부가 주는 것이 부스 자리·입점 자리다. 59건
    "오프라인", "온라인", "홍보지원", "공공구매",
    # 제도 — 인증·지정. 요건 충족 확인이다. 8건
    "제도",
}

# 근거가 없어 값만으로는 제외하지 않는 세부분야. 축2e 의 재료다.
UNVERIFIED_MLSFC = {
    "FTA활용/대응", "동반성장", "수출정보제공", "창업정보제공",
    "기술정보제공", "정보화지원", "교육",
} | SKIP_MLSFC_NOPLAN

# ══════════════════════════════════════════════════════════════════
# 축2e — 미검증 세부분야이고 타겟 신호가 하나도 없는 것. 2026-08-18 추가.
#
#   축2d 를 넣고 남은 T4 24건을 **전건 첨부를 열어** 확인했다(추출 21/24,
#   실패 3건은 png·zip 전용). 결과가 한 방향이었다.
#
#     정부가 주는 것이 용역(컨설팅·상담·보고서·번역·교육)     23 / 24
#     사업에 투입되는 자원(자금·장비·시제품)이 있는 것          0 / 24
#     제출물에 사업계획서가 있는 것                        1 / 24
#     실질 경쟁 심사(발표평가)가 있는 것                    1 / 24
#
#   현금이 나오는 것도 전부 용역 비용이다 — `확인서 건당 50만원`,
#   `기업당 최대 150만원`, `업체당 100만원 한도`. 기업이 자기 사업에 쓸 돈이 아니다.
#   11건은 우리 타겟이 아직 못 갖춘 상태를 전제한다(수출 실적 7 · 협력업체 5개 이상 ·
#   지식재산권 보유 · 피해 발생 · 가업승계 · 법정 의무교육 대상 각 1).
#
#   **세부분야 값으로는 뺄 수 없었다.** 같은 `교육` 안에 정반대 두 건이 있다.
#     119373 [인천] 세대융합 청년창업 멘티   예비창업자·3년 이내·사업화 1,000만원
#     123341 [울산] 찾아가는 사업장 안전교육  산업안전보건법 법정 의무교육
#   그래서 값이 아니라 **3중 조건**으로 뺀다. 119373 은 키움 어휘 `창업` 이 있어
#   빠져나가고, 123341 은 셋 다 없어서 걸린다.
#
#   알려진 오배제 1건 — `125217` 민관 공동 전략형 상생협력사업(창의트랙).
#   `제출한 사업계획서 및 발표 내용을 바탕으로 과제 평가 / 대면 평가가 원칙 /
#   타당성 50점 + 사업성 50점` 으로, 24건 중 유일하게 계획서로 경쟁 심사한다.
#   첨부를 열지 않으면 나머지 23건과 구분되지 않아 함께 빠진다(오배제율 4%).
#   첨부 파싱을 붙이면 되찾을 수 있다.
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 축2b — 정부 과업 수행 배제. 키움 어휘를 '요구'하지 않는다(배제 전용).
#
#   2026-08-18 좁혔다. 처음에는 실증·구축사업·테스트베드·용역·납품까지 넣었는데
#   51건을 배제하면서 그중 대부분이 오배제였다. 표본 7건의 첨부 양식을 열어 확인한 결과:
#     AI어장 현장실증          A9 G2 B8 E5 → 조달·수행    ← 유일한 진짜 과업형
#     기술개발제품 공공기관 실증   A9 G1 B0 E4 → 설비·도입
#     전북 스케일업 공공실증      A12 G1 B1 E3 → 행정 신청서
#     광주여대 … 지원 용역       A8 G3 B0 E2 → 행정 신청서
#     반도체 FOWLP 테스트베드    A8 G1 B0 E2 → 행정 신청서
#     산업혁신기반구축사업 기업지원  A6 G0 B0 E1 → 행정 신청서
#     Stand-up 맞춤지원(구축사업) A14 G0 B0 E2 → 행정 신청서
#   예산 세목(B)이 붙는 것은 AI어장뿐이었다. 나머지는 정부가 만든 인프라를 기업이
#   '쓰는' 수혜 사업이고 구축사업·테스트베드·용역은 모사업 이름일 뿐이었다.
#
#   그래서 남긴 것은 **신청 주체를 직접 지목하는 말**뿐이다.
#   AI어장류는 제목의 '현장실증'으로만 잡힌다 — 그 밖의 과업형은 양식을 열어야 나온다.
# ══════════════════════════════════════════════════════════════════
TASK = [
    ("주관·운영·수행기관 모집", re.compile(r"(주관기관|운영사|수행기관|위탁기관|수탁기관)\s*(모집|선정|공모)")),
    ("과업지시서·입찰", re.compile(r"과업지시서|과업 ?내용서|입찰|낙찰|제안요청")),
    ("현장실증", re.compile(r"현장 ?실증")),
]
# 티어 정렬용. 필터가 아니다.
GROW = [
    ("육성", re.compile(r"육성")), ("발굴", re.compile(r"발굴")),
    ("경진대회", re.compile(r"경진대회")), ("공모전", re.compile(r"공모전")),
    ("스케일업", re.compile(r"스케일 ?업")),
    ("액셀러레이팅", re.compile(r"액셀러레이팅|엑셀러레이팅")),
    ("보육", re.compile(r"보육")), ("데모데이", re.compile(r"데모 ?데이")),
    ("투자유치", re.compile(r"투자 ?유치")), ("투자연계", re.compile(r"투자 ?연계")),
    ("사업화지원", re.compile(r"사업화 ?지원")),
    ("성장지원", re.compile(r"성장 ?지원|성장사다리")),
    ("창업", re.compile(r"창업")),
    ("IR", re.compile(r"(?<![A-Za-z])IR(?![A-Za-z])")),   # FAIR 오탐 방지
]

# ══════════════════════════════════════════════════════════════════
# 축2g — 정부가 주는 것이 '사업장 설비·시설' 이면 배제. 2026-08-18 추가.
#
#   T3 502건에서 30건을 무작위 표본(seed 20260818)으로 읽다가 나온 덩어리다.
#   표본에 `시설/입지지원` 이 6건 들어왔는데 모집단 비율은 33/502(6.6%)라
#   기댓값이 2건이다. 표본이 쏠린 것이라 **비율을 확대하지 않고 전수로 다시 쟀다.**
#
#   걸리는 것이 방지시설·IoT 측정기기 부착·스마트공장 구축·HACCP 작업장 개보수·
#   고효율 설비 교체다. 전부 **사업장이 이미 있어야 신청이 성립한다.**
#   예비창업자와 3년 미만 1~5인 팀은 대기배출시설도 공장도 없다.
#
#   세부분야 값(`시설/입지지원` 33건)으로 빼지 않은 이유가 있다. 그 안에
#   `122893` 세종테크밸리 **사무실 임차료**(연 최대 2천만원)와 `118285` 실감콘텐츠
#   스튜디오 현물지원이 같이 있다. 둘은 사업장이 없어도 신청하고, 오히려
#   초기 팀에 유용하다. **주는 물건을 보고 빼야지 분류로 빼면 안 된다.**
FACILITY = re.compile(
    r"방지시설|측정기기 ?(부착|설치)|기업환경 ?개선|"
    r"스마트공장 ?(구축|보급|수준확인|자부담)|HACCP ?시설|저장시설 ?보관|"
    r"취급시설 ?안전|고효율 ?설비|공장 ?스마트화")

# ══════════════════════════════════════════════════════════════════
# 축2h — 특정 법인격 전용. 2026-08-18 추가.
#
#   사회적경제기업·마을기업·자활기업·장애인기업만 받는 공고다. 인증이나 지정을
#   받아야 신청 자격이 생기므로 일반 창업팀은 서류조차 낼 수 없다.
#   **축2c 소상공인 전용과 같은 형태다** — 절에 그 어휘만 있고 일반 기업·창업자
#   언급이 없을 때만 뺀다.
#
#   일반 어휘 목록에 `예비창업`·`창업자`·`초기창업` 을 넣지 않으면 두 건이 오배제된다.
#     125432 [충북] 장애인기업 육성 — `장애인기업 또는 장애인 예비창업자`
#     124128 [경기] 반려동물 창업 공모전 — `예비창업자 및 도내 3년 이내 초기창업자`
#   둘 다 우리 타겟이다. 사회적경제는 지원내용 쪽에 나오는 낱말일 뿐이다.
SPECIAL_ORG = re.compile(
    r"사회적경제|사회적기업|협동조합|마을기업|자활기업|장애인기업")
GENERAL_BIZ = re.compile(
    r"중소기업|창업기업|스타트업|벤처기업|중견기업|제조기업|예비창업|창업자|초기창업")

# ══════════════════════════════════════════════════════════════════
# 축2i — 금융 비용 보전. 2026-08-18 추가.
#
#   보증료·화재보험료·사회보험료·전세대출이자. **사업에 쓸 돈이 아니라 이미 낸
#   비용의 일부를 돌려주는 것**이다. 축2 가 중분류 `융자` 를 이미 빼고 있는데,
#   이것들은 `시설/입지지원`·`디자인/상품화/사업화` 로 분류돼 새 나갔다.
#
#   지원내용에 `보험료` 가 들어 있다고 다 빼면 안 된다. `125330` 무역사절단은
#   `편도 항공료 및 보험료`, `122876` 물류바우처는 `국제운송료 및 보험료` 라
#   **묶음 안의 한 항목**이다. 그래서 절 첫머리이거나 나열의 머리일 때만 본다.
FIN_COST_SUPPORT = re.compile(
    r"^\s*보증료|보증료[,ㆍ·]|화재보험료|사회보험료|수출보험ㆍ보증료|전세대출이자")
FIN_COST_TITLE = re.compile(r"보증료|화재보험료|사회보험료|보험료 ?지원")

# ══════════════════════════════════════════════════════════════════
# 축3 — 업력 상한·하한
# ══════════════════════════════════════════════════════════════════
AGE_CTX = re.compile(r"(창업|업력|설립|개업|사업자\s*등록|법인\s*설립|회사\s*성립)")
AGE_CEIL = re.compile(r"(?<!\d)(\d{1,2})\s*년\s*(?:이내|미만|이하)")
AGE_FLOOR = re.compile(r"(?<!\d)(\d{1,2})\s*년\s*(?:이상|초과|경과)")
AGE_PRE = re.compile(r"예비\s*창업")
AGE_CUT = re.compile(r"((?:19|20)\d{2})\s*[.\-]\s*\d{1,2}\s*[.\-]\s*\d{1,2}\s*\.?\s*이후")

# ══════════════════════════════════════════════════════════════════
# 축2f — 규모 하한. 상시근로자 N인 이상을 요구하면 소규모 팀이 배제된다.
#   817건 중 24건에 하한이 있고 22건이 5인 이상을 요구한다(고용·일자리 계열).
#   상한(N인 미만)은 배제하지 않는다 — 소규모 우대 신호다.
# ══════════════════════════════════════════════════════════════════
STAFF_FLOOR = re.compile(
    r"(?:상시\s*)?(?:근로자|종업원|임직원|고용|피보험자)[^.]{0,14}?"
    r"(\d{1,3})\s*(?:인|명)\s*(?:이상|초과)")

# 축2c — 소상공인 전용 배제. **지원대상 절 전체**에 소상공인 계열이 있고
#   창업기업·중소기업 언급이 없을 때 뺀다. 함께 언급되면 3년차도 자격이 있으므로 남긴다.
#
#   2026-08-18 끝 명사만 보다가 절 전체로 넓혔다. `부산지역 소상공인 및 예비창업자` 는
#   끝 명사가 '및 예비창업자' 라 소상공인이 절 앞부분에 있으면 놓쳤다(13건).
#   예비창업자를 함께 받는 소상공인 사업도 배제한다 — 자격은 있어도 사업 성격이 타겟이 아니다.
#   `상인` 은 '이상인 벤처기업' 에 걸려서 `상인회` 로 좁혔다.
SOLE_TARGET = re.compile(r"(소상공인|자영업자|소공인|점포|상인회)")
BIZ_MENTION = re.compile(r"(창업기업|스타트업|중소기업|중소벤처|벤처기업|중견기업|"
                          r"제조기업|수출기업|기술기업)")

PLAN_FN = re.compile(r"(사업계획서|수행계획서)")
REGION_TAG = re.compile(r"^\[([가-힣ㆍ·A-Za-z]{2,10})\]")
PERIOD_END = re.compile(r"~\s*(\d{4})[.\-](\d{2})[.\-](\d{2})")


# ─────────────────────────── 파서 ───────────────────────────
def clean_summary(raw: str | None) -> str:
    """bsnsSumryCn 은 HTML 이다. 태그 제거와 &nbsp; 처리를 빼먹으면 축1 이 깨진다."""
    s = re.sub(r"<[^>]+>", " ", raw or "").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s)


def first_clause(sm: str) -> str:
    """첫 ☞ 절 = 지원대상."""
    m = re.search(r"☞\s*([^☞]{3,600})", sm)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.split(r"※|\n", m.group(1))[0]).strip(" -·ㆍ")


def second_clause(sm: str) -> str:
    """두 번째 ☞ 절 = 지원내용."""
    p = re.split(r"☞", sm)
    return re.sub(r"\s+", " ", re.split(r"※", p[2])[0]).strip(" -·ㆍ") if len(p) > 2 else ""


def head_segment(clause: str) -> str:
    """절의 첫 문장에서 괄호·지시어·꼬리조사를 떼어낸 것."""
    s = SENT_SPLIT.split(clause)[0]
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[<\[][^>\]]*[>\]]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,·ㆍ-")
    for _ in range(4):                     # '중견기업으로 아래' 처럼 겹쳐 붙는다
        t = TAIL_PARTICLE.sub("", FILLER_TAIL.sub("", s)).strip()
        if t == s:
            break
        s = t
    return s


def _last2(s: str) -> str:
    tk = [t for t in s.split(" ") if t]
    return " ".join(tk[-2:]) if len(tk) >= 2 else s


def head_noun(clause: str) -> str:
    """절의 끝 명사구. 괄호·꼬리조사를 떼고 마지막 두 어절."""
    return _last2(head_segment(clause))


def subject_heads(clause: str) -> list[str]:
    """신청 주체 후보. **나열이면 하나라도 기업이면 기업이다.**

    `… 장애인 중 예비창업자 및 업종전환희망자`(125047) 처럼 나열의 마지막 조각이
    사전에 없는 낱말이면, 끝만 보는 판정은 앞에 있는 `예비창업자` 를 통째로 놓친다.
    나열을 풀어 마지막 두 조각을 각각 본다."""
    s = head_segment(clause)
    parts = [p.strip(" ,·ㆍ") for p in re.split(r"\s*(?:및|또는|그리고)\s*", s) if p.strip()]
    return [_last2(p) for p in parts[-2:]] or [s]


def supplier_hit(clause: str) -> bool:
    """공급자 어휘가 **신청자를 가리킬 때만** 참이다.

    `중기부가 지정한 운영사로부터 先투자받은 유망 소상공인`(120117) 의 운영사는
    돈이 나오는 곳이지 신청자가 아니다. 출처 조사가 붙으면 주체가 아니다.
    절 전체에서 공급자 어휘를 찾는 것 자체는 유지한다 — 끝 명사 근처로 좁히면
    `위탁`·`컨소시엄` 이 뒷문장에 있는 18건이 한꺼번에 통과로 뒤집힌다(실측).
    출처 조사 조건은 1,524건 중 1건만 건드린다."""
    return any(not ABLATIVE.match(clause[m.end():]) for m in SUPPLIER.finditer(clause))


def axis1(clause: str, head: str, heads: list[str] | None = None) -> str:
    if not clause:
        return "불명"
    if INST_HEAD.search(head) and not BIZ_HEAD.search(head):
        return "배제:기관"
    if supplier_hit(clause):
        return "배제:공급자"
    if any(BIZ_HEAD.search(h) for h in (heads or [head])):
        return "주의:중견포함" if MID_LARGE.search(clause) else "타겟"
    return "보류"


def strip_paren(t: str) -> str:
    """공고명의 괄호는 모사업명·분야 부가정보다. 과업/키움 판정에서 뺀다."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", t or "")).strip()


def _near(text: str, m: re.Match) -> bool:
    a, b = max(0, m.start() - 22), min(len(text), m.end() + 22)
    return bool(AGE_CTX.search(text[a:b]))


def parse_staff_floor(clause: str) -> int:
    """지원대상 절이 요구하는 상시근로자 하한. 없으면 0.

    **여럿이면 가장 낮은 것을 쓴다.** 지원대상 절의 여러 조건은 대개 OR 다 —
    고령군 공고가 "아래 조건을 하나 이상 충족하는 … 근로자 2인 이상 … 근로자 5인 이상"
    이라 max() 를 쓰면 2인 조건으로 지원할 수 있는 기업을 잘못 배제한다.
    AND 로 묶인 경우는 더 좁게 판정되지만, 자격을 잘못 빼는 것보다 낫다."""
    v = [int(m.group(1)) for m in STAFF_FLOOR.finditer(clause)]
    return min(v) if v else 0


def parse_age(clause: str, notice_year: int = 2026):
    """(상한, 하한, 예비창업 명시). 상한 None = 제한 없음."""
    ceils = [int(m.group(1)) for m in AGE_CEIL.finditer(clause) if _near(clause, m)]
    floors = [int(m.group(1)) for m in AGE_FLOOR.finditer(clause) if _near(clause, m)]
    cut = AGE_CUT.search(clause)
    if cut and not ceils:
        ceils.append(max(1, notice_year - int(cut.group(1))))
    return (max(ceils) if ceils else None,
            max(floors) if floors else 0,
            bool(AGE_PRE.search(clause)))


def parse_end(n: dict) -> str | None:
    """마감일. derived_apply_end 가 있으면 쓰고, 없으면 접수기간 문자열에서 뽑는다.
    날짜가 아닌 값(예산 소진시까지·상시 접수)은 None — 그것이 정상 상태다."""
    de = n.get("derived_apply_end")
    if de:
        return str(de)[:10]
    m = PERIOD_END.search(n.get("reqstBeginEndDe") or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def tier(unverified: bool, grow: list[str], ceil, floor, lclas: str) -> int:
    """정렬 순서. 강한 신호를 먼저 보고, 미검증은 마지막에 본다.

    2026-08-18 순서를 고쳤다. 전에는 `if unverified: return 4` 가 첫 줄이라
    **근거 없음이 강한 신호를 덮어썼다.** 원칙 1(신호 부재는 근거가 아니다)을
    필터에서는 지키고 정렬에서는 어긴 셈이다.

    실제 피해 사례 — `119373` [인천] 신개념 세대융합 청년창업 지원 멘티 상시모집.
      지원대상  만 39세 이하 예비창업자 또는 3년 이내 창업자
      지원내용  1:1 맞춤형 멘토링 + 최대 1,000만원 사업화 지원
    키움 어휘 `창업` 이 있고 업력 상한 3년이 명시됐는데, 세부분야가 `교육` 이라
    T4 로 내려가 목록 맨 아래에 묻혀 있었다. 623건 중 타겟 적합도가 가장 높은 건이다.

    미검증은 **다른 신호가 하나도 없을 때만** 의미가 있다. 5건이 T4 → T1·T2 로 올라간다.
    건수는 바뀌지 않는다 — 이건 필터가 아니라 정렬이다.
    """
    if grow:
        return 1
    if ceil is not None or floor > 0 or lclas == "창업":
        return 2
    if unverified:
        return 4
    return 3


# ─────────────────────── 단건 판정 ───────────────────────
def filter_notice(n: dict, today: str | None = None, biz_years: float = 2.5,
                  staff: int = 4) -> dict:
    """기업마당 응답 item 하나를 판정한다. 통과 여부와 근거를 함께 돌려준다.

    biz_years  신청자 업력(년). 2.5 = 3년 미만 사업자
    staff      신청자 상시근로자 수. 기본 4 — 1~5인 세그먼트의 보수적 기준.
               5인 사업자라면 staff=5 로 주면 '5인 이상' 요구 공고가 돌아온다.
    """
    today = today or date.today().isoformat()
    sm = clean_summary(n.get("bsnsSumryCn"))
    cl = first_clause(sm)
    hd = head_noun(cl)
    a1 = axis1(cl, hd, subject_heads(cl))
    mlsfc = n.get("pldirSportRealmMlsfcCodeNm") or ""
    lclas = n.get("pldirSportRealmLclasCodeNm") or ""
    title = n.get("pblancNm") or ""
    st = strip_paren(title)
    task = [k for k, p in TASK if p.search(st)]
    grow = [k for k, p in GROW if p.search(st)]
    sup = second_clause(sm)
    ceil, floor, pre = parse_age(cl)
    sfloor = parse_staff_floor(cl)
    end = parse_end(n)
    unv = mlsfc in UNVERIFIED_MLSFC

    ok3 = (ceil is None or ceil >= biz_years) and floor < biz_years
    okpre = pre and floor == 0
    sole = bool(SOLE_TARGET.search(cl)) and not BIZ_MENTION.search(cl)
    facility = bool(FACILITY.search(title) or FACILITY.search(sup))
    fin_cost = bool(FIN_COST_SUPPORT.search(sup) or FIN_COST_TITLE.search(title))
    special = bool(SPECIAL_ORG.search(cl)) and not GENERAL_BIZ.search(cl)
    ok_staff = sfloor <= staff
    # 축2e — 세 조건이 동시에 성립할 때만. 하나라도 있으면 통과다.
    no_signal = unv and not grow and ceil is None and floor == 0 and lclas != "창업"

    reasons = []
    if a1 not in ("타겟", "주의:중견포함"):
        reasons.append(f"축1 {a1} — 끝명사 '{hd}'")
    if mlsfc in SKIP_MLSFC:
        reasons.append(f"축2 중분류 {mlsfc}")
    if mlsfc in SKIP_MLSFC_NOPLAN:
        reasons.append(f"축2d 계획서 심사 없음 — 세부분야 {mlsfc}")
    if no_signal:
        reasons.append(f"축2e 미검증 세부분야({mlsfc}) + 키움 어휘 없음 + 업력 조건 없음")
    if task:
        reasons.append("축2b 과업 " + ",".join(task))
    if sole:
        reasons.append("축2c 소상공인 전용 — 지원대상 절에 기업 언급이 없다")
    if facility:
        reasons.append("축2g 설비·시설 지원 — 사업장 보유가 전제다")
    if fin_cost:
        reasons.append("축2i 금융 비용 보전 — 사업에 쓸 돈이 아니다")
    if special:
        reasons.append("축2h 특정 법인격 전용 — 지원대상 절에 일반 기업·창업자 언급이 없다")
    if end and end < today:
        reasons.append(f"마감 {end}")
    if not ok_staff:
        reasons.append(f"축2f 상시근로자 {sfloor}인 이상 요구")
    if not ok3:
        reasons.append(f"축3 업력 상한{ceil} 하한{floor}")

    return {
        "id": n.get("pblancId"), "sn": (n.get("pblancId") or "")[-6:], "title": title,
        "pass": not reasons, "reasons": reasons,
        "axis1": a1, "head": hd, "task": task, "grow": grow,
        "ceil": ceil, "floor": floor, "pre_stated": pre,
        "eligible_biz": ok3, "eligible_pre": okpre, "sole_proprietor": sole,
        "staff_floor": sfloor, "eligible_staff": ok_staff,
        "facility": facility, "finCost": fin_cost, "specialOrg": special,
        "tier": tier(unv, grow, ceil, floor, lclas), "unverifiedMlsfc": unv,
        "noPlanMlsfc": mlsfc in SKIP_MLSFC_NOPLAN, "noSignal": no_signal,
        "lclas": lclas, "mlsfc": mlsfc, "target": n.get("trgetNm"),
        "jrsd": n.get("jrsdInsttNm"), "exc": n.get("excInsttNm"),
        "eligibility": cl, "support": sup,
        "region": (REGION_TAG.match(title).group(1) if REGION_TAG.match(title) else "전국·미표기"),
        "period": n.get("reqstBeginEndDe"), "end": end, "rolling": end is None,
        "planForm": bool(PLAN_FN.search((n.get("fileNm") or "") + (n.get("printFileNm") or ""))),
        "url": n.get("pblancUrl"),
    }


def run(items: list[dict], today: str | None = None) -> dict:
    """전체를 돌리고 퍼널까지 돌려준다."""
    today = today or date.today().isoformat()
    stage = {"①전량": 0, "②축1": 0, "③축2": 0, "④계획서없음": 0, "⑤신호없음": 0,
             "⑥설비시설": 0, "⑦금융비용": 0, "⑧과업배제": 0, "⑨소상공인제외": 0,
             "⑩특정법인": 0, "⑪규모": 0, "⑫마감전": 0, "⑬업력": 0}
    out, dropped = [], []
    for n in items:
        stage["①전량"] += 1
        r = filter_notice(n, today)
        if r["axis1"] not in ("타겟", "주의:중견포함"):
            dropped.append(r); continue
        stage["②축1"] += 1
        if r["mlsfc"] in SKIP_MLSFC:
            dropped.append(r); continue
        stage["③축2"] += 1
        if r["noPlanMlsfc"]:
            dropped.append(r); continue
        stage["④계획서없음"] += 1
        if r["noSignal"]:
            dropped.append(r); continue
        stage["⑤신호없음"] += 1
        if r["facility"]:
            dropped.append(r); continue
        stage["⑥설비시설"] += 1
        if r["finCost"]:
            dropped.append(r); continue
        stage["⑦금융비용"] += 1
        if r["task"]:
            dropped.append(r); continue
        stage["⑧과업배제"] += 1
        if r["sole_proprietor"]:
            dropped.append(r); continue
        stage["⑨소상공인제외"] += 1
        if r["specialOrg"]:
            dropped.append(r); continue
        stage["⑩특정법인"] += 1
        if not r["eligible_staff"]:
            dropped.append(r); continue
        stage["⑪규모"] += 1
        if r["end"] and r["end"] < today:
            dropped.append(r); continue
        stage["⑫마감전"] += 1
        if not r["eligible_biz"]:
            dropped.append(r); continue
        stage["⑬업력"] += 1
        out.append(r)
    out.sort(key=lambda x: (0 if x["eligible_pre"] else 1, x["tier"], x["end"] or "9999", x["sn"]))
    return {"generated": today, "funnel": stage, "kept": out, "dropped": dropped}


# ─────────────────────── 픅스처 ───────────────────────
# 기업마당은 마감되면 API 에서 사라진다. 그래서 원문을 fixtures.json 에 묶어 뒀다.
FIXTURES = [
    ("125069", True,  "포항 지역산업위기대응 — 업력 조건 없음 = 제한 없음"),
    ("125439", True,  "유망기업 사업화경진대회"),
    ("125312", True,  "경남 정보보호 기업 육성 — 상한 10년"),
    ("125298", True,  "전북 오픈이노베이션 판로개척형 — 상한 7년"),
    ("125460", True,  "서울창업허브M+ — 상한 7년이라 3년차 포함"),
    ("125318", True,  "아트코리아랩 오픈이노베이션 — 상한 10년"),
    ("125276", True,  "BABY AND KIDS FAIR — IR 오탐 방지 확인용. 통과하지만 T3"),
    ("125477", False, "AI어장 현장실증 — 축2b 과업 '실증'"),
    ("125250", False, "AI어장 응용서비스 — 축2b 과업 '실증'"),
    ("125417", False, "독자 AI 데이터 지원 — 축1 공급자 '기관ㆍ기업'"),
    ("125368", False, "오픈이노베이션 공공기관 제안 — 축1 기관 '공공기관'"),
    ("124664", False, "특화 AI 파운데이션 — 축1 기관 '기업ㆍ대학ㆍ연구기관'"),
    ("125043", False, "예비사회적기업 지정 — 축1 기관 '법인ㆍ단체'"),
    ("125382", False, "베트남 D-Global — 축3 하한 7년 초과"),
    # 2026-08-18 추가 — 과업 어휘를 좁힌 근거. 양식을 열어 '기업 지원'임을 확인했다.
    ("124556", True,  "반도체 FOWLP 테스트베드 구축 기업지원 — 양식 A8 G1 B0 E2 행정 신청서"),
    ("123640", True,  "산업혁신기반구축사업 기업지원 — 양식 A6 G0 B0 E1 행정 신청서"),
    ("125311", True,  "부산 Stand-up 맞춤지원(구축사업) — 양식 A14 G0 B0 E2 행정 신청서"),
    ("125256", True,  "전북 스케일업 공공실증 — 양식 A12 G1 B1 E3 행정 신청서"),
    ("125304", True,  "기술개발제품 공공기관 실증지원 — 양식 A9 G1 B0 E4 설비·도입"),
    # 2026-08-18 추가 — 소상공인 전용 배제
    ("124677", False, "동작구 소상공인 개별간판 개선 — 축2c 소상공인 전용"),
    ("121799", False, "조선일보 연계 중소기업 홍보 — 축2d 온라인. 소상공인 병기 회귀는 125149 가 지킨다"),
    # 2026-08-18 추가 — 국가 R&D 수행형태 중분류
    ("124771", False, "대구 대학-기업 공동 기술·제품 기획 — 축2 중분류 '공동기술개발'"),
    ("124904", False, "표준공정 기반 공정최적화 기술개발(R&D) — 축2 중분류 '공동기술개발'"),
    ("125106", False, "괴산군 경쟁력강화산업 육성(R&D) — 축2 중분류 '혼합(단독+공동)'"),
    # 2026-08-18 추가 — 규모 하한. R&D 어휘가 붙었지만 장비·인건비·인프라 지원은 남긴다
    ("117131", False, "구조혁신지원사업 — 축2f 상시근로자 5인 이상 요구"),
    ("124761", False, "달성군 청년 고용 우수기업 — 축2f 상시근로자 30명 이상 요구"),
    # 축2d 추가 전에는 통과였다. 세부분야가 '고용환경개선' 이고 첨부가 견적서 기반이라
    # 이제 축2d 가 먼저 잡는다. min() 회귀는 아래 단위 테스트가 대신 지킨다.
    ("121424", False, "고령군 지역발전 우수기업 — 축2d 고용환경개선"),
    # 2026-08-18 추가 — 소상공인 판정을 절 전체로 넓힌 근거
    ("121931", False, "부산 소상공인 경영전략 컨설팅 — 끝명사가 '및 예비창업자' 라 끝만 보면 놓친다"),
    ("121134", False, "광주 소상공인주치의센터 — 예비창업자도 받지만 소상공인 사업이다"),
    ("125149", True,  "경북세일페스타 입점 마케팅 — '중소기업ㆍ소상공인' 이라 남긴다"),
    # 2026-08-18 축2d 반례 — 사용자가 지목한 기준 사례
    ("125203", False, "안양춤축제 홍보관 — 축2d 홍보지원. 선정방법이 '적격심사' 다"),
    ("124404", False, "콘텐츠IP 마켓 참가 — 축2d 오프라인"),
    ("117945", False, "수원시 중소기업 특례보증 — 축2d 보증"),
    ("120566", False, "지식재산 경영인증 신청 — 축2d 제도"),
    ("119137", False, "청년일자리 도약장려금 — 축2d 고용유지"),
    ("121634", True,  "용인시 창업 멘토링(1:1) — 창업정보제공은 남긴다. 멘토링도 타겟이다"),
    ("119373", True,  "인천 세대융합 청년창업 멘티 — 키움'창업'+상한3년이라 T1. 미검증이 덮으면 안 된다"),
    # 2026-08-18 축2e — T4 24건 전건 첨부 확인 후
    ("123341", False, "울산 찾아가는 안전교육 — 축2e. 119373 과 같은 '교육' 인데 신호가 하나도 없다"),
    ("120487", False, "부산 OK FTA 컨설팅 — 축2e. 주는 것이 원산지증명 용역이다"),
    ("119131", False, "중소기업 승계자문 — 축2e. 가업승계 대상이라 3년미만엔 해당이 없다"),
    # ⚠ 알려진 오배제. 24건 중 유일하게 사업계획서+발표로 심사하는데 첨부를 열지 않으면
    #    구분되지 않는다. 첨부 파싱을 붙여 되찾으면 이 기대값을 True 로 바꿔야 한다.
    ("125217", False, "민관 공동 상생협력(창의트랙) — 축2e **알려진 오배제**. 계획서+대면평가로 심사한다"),
    # 2026-08-18 축1 끝명사 버그 3건 — 원인이 셋 다 '자르는 자리'였다
    ("125047", True,  "장애인 창업사업화 — 절이 날짜로 시작해 끝명사가 '‘26' 이었다"),
    ("121389", True,  "농식품글로벌성장패키지 — 끝명사가 '중견기업으로 아래' 였다"),
    ("120117", False, "소상공인 LIPS — 축1 오판(운영사)은 고쳤다. 이제 축2c 가 제 이유로 뺀다"),
    ("124232", False, "투ㆍ융자 연계 기술개발 — 운영사가 **신청자**다. 공급자 배제는 살아 있어야 한다"),
    # 2026-08-18 축2g — 정부가 주는 것이 사업장 설비다
    ("122168", False, "경주시 소규모 사업장 방지시설 — 축2g. 대기배출시설이 있어야 낸다"),
    ("122893", True,  "세종테크밸리 임차료 — **같은 `시설/입지지원` 인데 남긴다.** 사무실 임차료다"),
    ("118285", True,  "실감콘텐츠 스튜디오 현물지원 — 분류로 빼면 이것도 빠진다"),
    # 2026-08-18 축2i — 이미 낸 비용의 보전이지 사업에 쓸 돈이 아니다
    ("120135", False, "하남산업단지 보증료 — 축2i"),
    ("117068", False, "청년하우스 전세대출이자ㆍ월세 — 축2i. 개인 주거 복지다"),
    ("125330", True,  "말레이시아-인도 무역사절단 — `항공료 및 보험료` 는 묶음 안의 한 항목이라 남긴다"),
    # 2026-08-18 축2h — 인증·지정을 받아야 자격이 생기는 공고
    ("119332", False, "하남시 사회적경제기업 컨설팅 — 축2h"),
    ("125432", True,  "충북 장애인기업 육성 — `장애인 예비창업자` 가 있어 남긴다. 일반 어휘가 덮는다"),
    ("124128", True,  "경기 반려동물 창업 공모전 — `예비창업자 및 3년 이내 초기창업자` 다"),
]

# 축2d 가 공고 단위 픅스처를 가로채도 살아남아야 하는 회귀. 함수를 직접 잰다.
UNIT = [
    # 고령군 원문: "아래 조건을 하나 이상 충족하는 … 근로자 2인 이상 … 근로자 5인 이상"
    # OR 조건이라 min() 이 맞다. max() 면 5가 나와 4인 팀이 배제된다.
    ("parse_staff_floor OR 조건은 min()",
     lambda: parse_staff_floor("아래 조건을 하나 이상 충족하는 기업 - 상시 근로자 2인 이상 "
                               "- 최근 3년 평균 상시 근로자 5인 이상") == 2),
    ("parse_staff_floor 조건 없으면 0",
     lambda: parse_staff_floor("부산지역 소상공인 및 예비창업자") == 0),
    ("parse_staff_floor 30명 이상도 잡는다",
     lambda: parse_staff_floor("상시근로자 30명 이상인 기업") == 30),
    # 소상공인 판정은 끝명사가 아니라 절 전체를 본다
    ("소상공인 절 전체 검사",
     lambda: bool(SOLE_TARGET.search("부산지역 소상공인 및 예비창업자"))),
    ("기업 병기하면 소상공인 아님",
     lambda: bool(BIZ_MENTION.search("중소기업ㆍ소상공인 대상"))),
    ("IR 은 FAIR 에 걸리지 않는다",
     lambda: not any(p.search("BABY AND KIDS FAIR") for k, p in GROW if k == "IR")),
    # 2026-08-18 축1 끝명사 — 공고 픅스처는 '통과/배제' 만 재므로 판정 자체를 여기서 잰다.
    # 120117 은 축2c 로도 배제라 픅스처만으로는 축1 회귀를 못 잡는다.
    ("날짜로 시작하는 절도 끝까지 읽는다",
     lambda: head_noun("‘26. 1. 1.(일) 이후 교육과정을 이수한 장애인 중 "
                       "예비창업자 및 업종전환희망자") == "및 업종전환희망자"),
    ("나열이면 하나라도 기업이면 기업",
     lambda: axis1("장애인 중 예비창업자 및 업종전환희망자", "및 업종전환희망자",
                   subject_heads("장애인 중 예비창업자 및 업종전환희망자")) == "타겟"),
    ("꼬리 조사 '으로' 와 지시어 '아래' 를 뗀다",
     lambda: head_noun("수출 유망 중소기업 및 중견기업으로 아래 ① 요건 중 1개") == "및 중견기업"),
    ("'운영사로부터' 는 신청자가 아니다",
     lambda: not supplier_hit("중기부가 지정한 운영사로부터 先투자받은 유망 소상공인")),
    ("'및 운영사' 는 신청자다",
     lambda: supplier_hit("창업기획자 및 운영사")),
    # 2026-08-18 축2g·2h·2i — 어휘가 '묶음 안의 한 항목' 일 때 걸리면 안 된다
    ("보험료가 나열 뒤쪽이면 금융비용이 아니다",
     lambda: not FIN_COST_SUPPORT.search("편도 항공료 및 보험료, BuyKorea 활용 마케팅")),
    ("보증료가 첫머리면 금융비용이다",
     lambda: bool(FIN_COST_SUPPORT.search("보증료의 30% 지원 (최대 1백만원)"))),
    ("사업장 임차료는 설비·시설이 아니다",
     lambda: not FACILITY.search("사무실 임차료(연간 20백만원), 사무실 조성 공사비")),
    ("일반 창업 어휘가 있으면 특정 법인격 전용이 아니다",
     lambda: bool(SPECIAL_ORG.search("장애인기업 또는 장애인 예비창업자"))
             and bool(GENERAL_BIZ.search("장애인기업 또는 장애인 예비창업자"))),
]
FIXTURE_TODAY = "2026-08-18"   # 픅스처는 이 날짜로 고정해야 마감 판정이 재현된다


def run_tests() -> int:
    fx = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    by = {i["pblancId"][-6:]: i for i in fx["items"]}
    bad = 0
    for sn, want, why in FIXTURES:
        if sn not in by:
            bad += 1
            print(f"  ✗  {sn}  fixtures.json 에 없다 — {why}")
            continue
        r = filter_notice(by[sn], today=FIXTURE_TODAY)
        ok = r["pass"] == want
        bad += not ok
        print(f"  {'✓' if ok else '✗'}  {sn}  기대 {'통과' if want else '배제':<4} "
              f"실제 {'통과' if r['pass'] else '배제':<4} T{r['tier']}  {why}")
        if not ok:
            print(f"       근거: {r['reasons'] or '없음'}")
    print()
    for why, fn in UNIT:
        try:
            ok = bool(fn())
        except Exception as exc:                       # noqa: BLE001
            ok, why = False, f"{why} — {type(exc).__name__}"
        bad += not ok
        print(f"  {'✓' if ok else '✗'}  단위    {why}")
    total = len(FIXTURES) + len(UNIT)
    print(f"\n  {total - bad}/{total} 통과"
          f"   (공고 {len(FIXTURES)} + 단위 {len(UNIT)} · "
          f"기준일 {FIXTURE_TODAY} · 원문 {fx['captured']} 스냅샷)")
    return bad


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(1 if run_tests() else 0)
    print(__doc__)
