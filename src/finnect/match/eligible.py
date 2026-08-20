"""자격 대조 — **못 넘으면 뺀다** (plan/17 T-0072 · M1).

LLM 을 거치지 않는다(`SPEC.md` F3-1-3). 같은 프로필과 같은 공고에 항상 같은 답이
나와야 한다.

## 배제형 원칙을 그대로 쓰지 않는다

`notice-filter` 의 축은 전부 배제형이다 — *"조건이 명시되지 않으면 통과시키고,
명시된 조건이 우리를 배제할 때만 뺀다."* 그건 **공고 쪽이 빈 경우**의 규칙이다.

**회사 쪽이 비면 다른 문제다.** 공고는 "충북 소재" 라고 분명히 말했고 우리가
사용자를 모르는 것뿐이다. 그때 통과시키면 못 받을 공고를 권하고, 탈락시키면 받을
수 있는 공고를 놓친다. **판정하지 않고 `UNKNOWN` 으로 남긴다**(`SPEC.md` F3-1-5).

## 축마다 확신이 다르다

| 축 | 안 맞으면 | 왜 |
|---|---|---|
| 소재지 | **탈락** | 주소 문자열에 지역명이 있어 결정론이 잘 된다 |
| 업종 | **`UNKNOWN`** | `ICT` 와 `정보통신업` 이 문자열로 안 겹친다. 오탈락이 오추천보다 나쁘다 |
| 연령 | **탈락** | 숫자 비교다 |
| 규모 | **탈락** | 숫자 비교다. 소상공인 전용은 10인 상한만 확실하다(`_규모`) |
| 중복수혜 | **`UNKNOWN`** | 수혜 이력이 있다고 그 사업이 같은 사업인지 모른다 |

업종을 탈락으로 두지 않는 이유가 이 표의 요점이다. **오탈락은 화면에서 사라져서
사용자가 알아챌 방법이 없다**(ADR-0003 — 판정 근거를 안 보여 준다). 오추천은 열어
보면 안다.

## 못 읽은 조건을 센다

`conditions` 는 자유 텍스트라 규칙이 닿는 것이 일부다. 닿지 않은 것을 **세서
보고한다** — `SPEC.md` §2.1 이 *"규칙으로 안 떨어지는 요건이 얼마나 되는지는 아직
모른다"* 고 적어 둔 숫자가 그것이다. 조용히 통과시키지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from finnect.match.profile import CompanyProfile


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    #: 판정하지 않았다. **`FAIL` 과 섞으면 안 된다** — 저쪽은 봤는데 안 되는
    #: 것이고 이쪽은 아직 못 본 것이다
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Judgement:
    verdict: Verdict
    #: 왜 탈락인가. 화면에 안 나간다(ADR-0003) — 우리가 되짚을 때 읽는다
    reasons: tuple[str, ...] = ()
    #: 왜 판정 못 했나
    unknowns: tuple[str, ...] = ()
    #: 규칙이 못 읽은 조건. **센다**
    unhandled: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.PASS


#: 광역 약칭 ↔ 정식 이름. **주소는 정식으로, 공고는 약칭으로 쓴다.**
#: `충남` 을 그냥 찾으면 `충청남도 천안시` 를 놓친다
_REGION_ALIAS: dict[str, tuple[str, ...]] = {
    "서울": ("서울특별시",),
    "부산": ("부산광역시",),
    "대구": ("대구광역시",),
    "인천": ("인천광역시",),
    "광주": ("광주광역시",),
    "대전": ("대전광역시",),
    "울산": ("울산광역시",),
    "세종": ("세종특별자치시",),
    "경기": ("경기도",),
    "강원": ("강원도", "강원특별자치도"),
    "충북": ("충청북도",),
    "충남": ("충청남도",),
    "전북": ("전라북도", "전북특별자치도"),
    "전남": ("전라남도",),
    "경북": ("경상북도",),
    "경남": ("경상남도",),
    "제주": ("제주특별자치도", "제주도"),
}

#: 뒤에 붙는 행정 단위. 떼고 비교한다 — `성남시` 와 `성남` 이 갈리면 안 된다
_UNIT = re.compile(r"(특별자치도|특별자치시|특별시|광역시|자치시|자치구|[도시군구])$")

_WS = re.compile(r"\s+")


def _bare(s: str) -> str:
    """행정 단위를 떼고 공백을 지운다. `성남시` → `성남`."""
    t = _WS.sub("", s or "")
    # 한 글자만 남는 것은 떼지 않는다 — `도` 하나가 남으면 아무 주소에나 걸린다
    stripped = _UNIT.sub("", t)
    return stripped if len(stripped) >= 2 else t


def region_hit(wanted: str, address: str) -> bool:
    """공고가 요구한 지역 하나가 이 주소에 해당하나.

    약칭과 정식 이름을 둘 다 본다. `대구` → `대구광역시 수성구` · `대구 수성구`.
    """
    addr = _WS.sub("", address or "")
    if not addr:
        return False
    bare = _bare(wanted)
    if bare and bare in addr:
        return True
    return any(alias in addr for alias in _REGION_ALIAS.get(bare, ()))


def industry_hit(wanted: str, mine: tuple[str, ...]) -> bool:
    """공고가 요구한 업종 하나가 내 업종에 해당하나. **양방향 부분 문자열이다.**

    `소프트웨어` 는 `응용 소프트웨어 개발 및 공급업` 안에 있고, 반대로 공고가
    `응용 소프트웨어 개발 및 공급업` 이라 쓰고 우리가 `소프트웨어` 만 알 수도 있다.
    """
    w = _WS.sub("", wanted or "")
    if len(w) < 2:
        return False
    for m in mine:
        t = _WS.sub("", m or "")
        if not t:
            continue
        if w in t or t in w:
            return True
    return False


#: `만 39세 이하` · `39세 이하` · `만39세이하`
_AGE_MAX = re.compile(r"만?\s*(\d{2})\s*세\s*(?:이하|미만|까지)")
#: 중복수혜 제한을 말하는 어휘. **있다고 탈락은 아니다** — 같은 사업인지 모른다
_DUP = re.compile(r"기수혜|재수혜|중복\s*수혜|이미\s*지원|동일\s*사업")
#: `상시 근로자 5인 미만` · `상시근로자 10인 이하`
_STAFF_MAX = re.compile(r"(?:상시\s*)?근로자\s*(?:수\s*)?(\d{1,3})\s*인\s*(?:미만|이하)")
#: `상시 근로자 5인 이상`
_STAFF_MIN = re.compile(r"(?:상시\s*)?근로자\s*(?:수\s*)?(\d{1,3})\s*인\s*이상")
#: 소상공인 전용. **실측으로 잡았다** — 손 라벨 15건에서 못 읽은 조건 13건 중 4건이
#: 이것이었고, 그 넷이 추천 3건을 통째로 차지했다(2026-08-20)
_SMALL = re.compile(r"소상공인|소공인")

#: 소상공인 상한. 업종별로 5인 또는 10인 미만인데(소상공인기본법 시행령 제3조)
#: **업종 대응표가 없다.** 그래서 `10` 을 쓴다 — 어느 업종이든 10명 이상은 확실히
#: 소상공인이 아니다. 10명 미만은 `UNKNOWN` 이다: 업종을 봐야 갈린다
_SMALL_CEILING = 10


def judge(
    *,
    regions: tuple[str, ...],
    industries: tuple[str, ...],
    conditions: tuple[str, ...],
    company: CompanyProfile,
    on,
) -> Judgement:
    """공고 프로필 하나와 회사 하나를 대조한다.

    `on` 은 파생값 기준일이다. 공고마다 다르므로 부르는 쪽이 준다 — 신청일인지
    마감일인지는 `service.py` 가 정한다.
    """
    reasons: list[str] = []
    unknowns: list[str] = []
    unhandled: list[str] = []

    # --- 소재지. 안 맞으면 탈락 ---
    if regions:
        addr = company.value("location")
        if not addr:
            unknowns.append(f"소재지 요구({'·'.join(regions)}) — 위키에 소재지가 없다")
        elif not any(region_hit(r, addr) for r in regions):
            reasons.append(f"소재지 {'·'.join(regions)} — 우리는 {addr[:20]}")

    # --- 업종. 안 맞으면 UNKNOWN ---
    if industries:
        mine = tuple(
            v for v in (company.value("industry"), company.value("industry_item")) if v
        )
        if not mine:
            unknowns.append(f"업종 요구({'·'.join(industries)}) — 위키에 업종이 없다")
        elif not any(industry_hit(w, mine) for w in industries):
            unknowns.append(
                f"업종 {'·'.join(industries)} — 우리는 {'·'.join(mine)}. 이름이 안 겹친다"
            )

    # --- 조건. 인식한 것만 판정하고 나머지를 센다 ---
    for c in conditions:
        m = _AGE_MAX.search(c)
        if m:
            limit = int(m.group(1))
            age = company.age(on)
            if age is None:
                unknowns.append(f"{c} — 위키에 생년월일이 없다")
            elif age > limit:
                reasons.append(f"{c} — 만 {age}세")
            continue
        if _DUP.search(c):
            if company.value("gov_program"):
                unknowns.append(f"{c} — 수혜 이력이 있다. 같은 사업인지 모른다")
            continue
        if _규모(c, company, reasons, unknowns):
            continue
        unhandled.append(c)

    if reasons:
        return Judgement(Verdict.FAIL, tuple(reasons), tuple(unknowns), tuple(unhandled))
    if unknowns:
        return Judgement(Verdict.UNKNOWN, (), tuple(unknowns), tuple(unhandled))
    return Judgement(Verdict.PASS, (), (), tuple(unhandled))


def _규모(
    c: str, company: CompanyProfile, reasons: list[str], unknowns: list[str]
) -> bool:
    """직원 수로 갈리는 조건. **읽었으면 `True`.**

    셋을 한 자리에서 본다 — 상한(`5인 미만`) · 하한(`5인 이상`) · 소상공인 전용.
    같은 값(`headcount`)을 보므로 흩어 놓으면 없는 값 처리가 세 번 갈린다.
    """
    상한 = _STAFF_MAX.search(c)
    하한 = _STAFF_MIN.search(c)
    작음 = _SMALL.search(c)
    if not (상한 or 하한 or 작음):
        return False

    n = company.value("headcount")
    if not n or not n.isdigit():
        unknowns.append(f"{c} — 위키에 직원 수가 없다")
        return True
    사람 = int(n)

    if 상한 and 사람 >= int(상한.group(1)):
        reasons.append(f"{c} — 우리는 {사람}명")
        return True
    if 하한 and 사람 < int(하한.group(1)):
        reasons.append(f"{c} — 우리는 {사람}명")
        return True
    if 작음 and not 상한:
        # 업종별 기준(5인 또는 10인)을 모른다. **10명 이상은 어느 업종이든 아니다**
        if 사람 >= _SMALL_CEILING:
            reasons.append(f"{c} — 우리는 {사람}명이라 소상공인이 아니다")
        else:
            unknowns.append(f"{c} — {사람}명. 업종별 기준(5인·10인)을 몰라 못 가른다")
    return True
