"""조건을 자유 문자열 대신 **축·연산자·값 객체**로 뽑아 본다 — 실측용 버리는 코드.

같은 공고 50건에 라운드마다 호출을 건다. 표본은 고정이라 라운드끼리 비교된다.

    uv run python spike/cond_axes.py v1      # 첫 판 (축 9개)
    uv run python spike/cond_axes.py v2      # 축 12개 · entity_type 좁힘
    uv run python spike/cond_axes.py --cmp   # 라운드 비교표

## 채점기를 왜 붙였나

1라운드는 자동 집계가 45% 인데 눈으로 세니 31% 였다. `small_business` 에 중소기업이
섞이고 `entity_type` 이 쓰레기통이 된 것을 자동 집계가 못 봤다. 라운드마다 눈으로
세면 라운드끼리 비교가 안 되므로 **축마다 검산 정규식**을 둔다.

**이건 근사다.** 정규식이 통과시킨 것이 다 맞지는 않다. 그래서 라운드마다
`--cmp` 로 틀린 것을 뽑아 눈으로 본다 — 숫자만 보고 넘어가지 않는다.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select

from finnect import llm, trace
from finnect.db import session_scope
from finnect.match import bodies
from finnect.match import eligible as el
from finnect.match import normalize as nz
from finnect.models import BizinfoNotice, KstartupNotice

OUT = Path("out")
N_EACH = 25

# ══════════════════════════════════════════════════════════════════
# 라운드
# ══════════════════════════════════════════════════════════════════
AXES_V1 = [
    "business_years", "ceo_age", "headcount", "revenue", "capital",
    "gov_program", "entity_type", "small_business", "other",
]
#: v2 — 실측이 시킨 것 넷. `sme` 가 없어서 중소기업이 `small_business` 로 갔고,
#: 그건 코드가 10인 상한으로 푸는 축이라 **오탈락**이었다(1라운드 결함 ③)
AXES_V2 = [
    "business_years", "ceo_age", "headcount", "revenue", "capital", "funding",
    "sme", "small_business", "entity_type", "certification", "gov_program", "other",
]
OPS_V1 = ["lte", "lt", "gte", "gt", "eq", "require", "exclude", "none"]
#: `none` 을 뺀다 — "창업기업" 에 `business_years none` 이 붙었다. 값이 없으면 축도 없다
OPS_V2 = ["lte", "lt", "gte", "gt", "eq", "require", "exclude"]

_HEAD = """\
너는 한국 정부·지자체 지원사업 공고에서 **누구를 찾는 공고인가**를 뽑는 추출기다.
요약하지 말고 공고에 적힌 것만 낸다.

## regions — 신청할 수 있는 지역
**시·군·구까지 적힌 대로 낸다.** `경기` 가 아니라 `성남시` 다. 여러 곳이면 전부 낸다.
**제한이 없으면 빈 배열이다.** '전국' 같은 말을 넣지 마라. 지역이 안 적혀 있어도
주최가 지역 기관이면 그 지역을 낸다.

## industries — 요구하는 업종
`바이오헬스` · `의료기기` · `식품` 처럼 공고가 요구하는 분야. **안 가리면 빈 배열이다.**
지원 분야(사업화·판로·컨설팅)를 넣지 마라 — 그건 신청자의 업종이 아니다.

## conditions — 신청자가 갖춰야 하는 것
하나마다 **축을 골라** 객체로 낸다.

    axis            무엇에 관한 조건인가. 아래 목록에서 고른다
    op              lte 이하 · lt 미만 · gte 이상 · gt 초과 · eq 같음
                    require 갖춰야 함 · exclude 배제됨
    value           숫자면 숫자만. 아니면 null
    quote           공고에 적힌 말 그대로. 고쳐 쓰지 마라
"""

_TAIL = """
## anchor — 가장 중요하다
위 판단의 근거가 된 **원문 조각을 그대로** 낸다. 20자 이상. **고쳐 쓰면 버려진다.**
"""

AXIS_DOC_V1 = """
### axis 목록
    business_years  업력·창업 기간. `창업 7년 이내` → lte 7
    ceo_age         대표자 나이. `만 39세 이하` → lte 39
    headcount       직원·상시근로자 수. `10인 미만` → lt 10
    revenue         매출액. 단위는 억원으로 맞춰라
    capital         자본금. 단위는 억원으로 맞춰라
    gov_program     정부지원 중복수혜·기수혜. `기수혜 기업 제외` → exclude
    entity_type     법인 / 개인사업자 / 예비창업자 / 사업자등록 여부
    small_business  소상공인 · 소공인
    other           위 어디에도 안 맞는 것

**`소상공인` 을 인원수로 바꾸지 마라.** `small_business` · `require` 로 내면 된다.

**모르면 `other` 로 낸다.** 억지로 축에 넣지 마라 — 틀린 축이 축 없는 것보다 나쁘다.
"""

#: v2 — 1라운드 결함 셋을 고친다.
#:   ③ `sme` 를 만들어 중소기업을 `small_business` 에서 떼낸다
#:   ④ `entity_type` 을 셋으로 좁히고 `certification` 을 만든다
#:   ⑤ 지역·업종 중복을 못 박는다
AXIS_DOC_V2 = """
### axis 목록 — **뜻이 겹치는 것이 없다. 가장 좁은 칸을 골라라**
    business_years  업력·창업 기간. `창업 7년 이내` → lte 7
    ceo_age         대표자 나이. `만 39세 이하` → lte 39
    headcount       직원·상시근로자 수. `10인 미만` → lt 10
    revenue         매출액·수출실적. 단위는 억원으로 맞춰라
    capital         자본금. 단위는 억원으로 맞춰라
    funding         투자 유치액·조달액. `누적투자 50억 이상` → gte 50
    sme             **중소기업 · 중견기업 · 벤처기업 · 스타트업**. 기업 규모 구분이다
    small_business  **「소상공인」 「소공인」 이라고 적혀 있을 때만.** 아래 참고
    entity_type     **셋뿐이다** — 예비창업자 / 개인사업자 / 법인
    certification   보유한 인증·자격. 벤처기업확인 · 이노비즈 · 메인비즈 ·
                    기업부설연구소 · 특허·상표 보유 · 각종 인허가
    gov_program     정부지원 중복수혜·기수혜. `기수혜 기업 제외` → exclude
    other           위 어디에도 안 맞는 것

### 세 가지를 특히 지켜라

**1. `중소기업` 은 `small_business` 가 아니다.**
`small_business` 는 소상공인 전용이고 우리가 인원수로 푸는 유일한 축이다. 여기에
중소·중견·벤처를 넣으면 **직원이 많은 회사가 잘못 탈락한다.**

    「소상공인기본법」제2조에 따른 소상공인   → small_business
    중소ㆍ중견기업                          → sme
    중소·벤처기업 및 스타트업 기업            → sme
    정선군 소재 중소 제조기업                → sme        (지역은 regions 에 이미 냈다)

**2. `entity_type` 은 셋뿐이다. 애매하면 `other` 로 보내라.**
뜻이 넓어 보인다고 여기에 던지지 마라.

    예비창업자 / 창업예정자                  → entity_type
    「관광진흥법」제4조에 따른 업체            → other          (인허가지만 축이 아니다)
    특허·상표권을 보유한 기업                 → certification
    기술기반 중소기업 및 중견기업              → sme
    아래 ①②③ 요건을 모두 충족하는 창업기업    → 내지 마라       (내용이 없다)

**3. 지역·업종은 위에 이미 냈다. conditions 에 다시 쓰지 마라.**

    "성남시 소재 중소기업(본사 또는 공장)"
      → regions 에 성남시를 냈으니 여기서는 `sme` 만 낸다. quote 는 원문 그대로 둔다

### 조건이 아닌 것은 내지 마라
**의사·관심·희망 표명은 자격이 아니다.** 아래는 전부 내지 않는다.

    미국 수출에 관심이 있는 · 협업 가능한 기술을 보유하고 싶은 ·
    3D프린터에 관심있는 누구나 · 교육을 필요로 하는 · 진단을 희망하는

**모르면 `other` 로 낸다.** 억지로 축에 넣지 마라 — 틀린 축이 축 없는 것보다 나쁘다.
"""

#: v3 — 2라운드가 남긴 것 넷.
#:   ① **OR 그룹.** "소상공인 또는 중소기업" 을 두 행으로 잘 냈는데 **둘이 OR 이라는
#:      표시가 없다.** 코드가 AND 로 읽으면 직원 10명 회사가 탈락한다 — 지금 정규식이
#:      내는 것과 같은 오탈락이고, 축을 고쳐도 안 없어지는 유일한 자리다
#:   ② `창업기업` 이 `sme` 로 갔다
#:   ③ `entity_type` 을 셋으로 좁혔더니 예비창업자 변형이 `other` 로 갔다
#:   ④ 업종이 conditions 로 샌다("국내 AI 기반 Age-Tech 관련 기업")
AXIS_DOC_V3 = AXIS_DOC_V2 + """
### alt — **또는(OR) 조건**
조건 여럿이 **하나만 맞아도 되는** 경우가 있다. 그때만 같은 `alt` 번호를 준다.
따로따로 다 맞아야 하면 `alt` 는 0 이다.

    "소상공인 또는 중소기업"
      → {axis: small_business, op: require, alt: 1}
      → {axis: sme,            op: require, alt: 1}      ← 같은 번호 = 하나만 맞으면 된다

    "성남시 소재이고 창업 7년 이내"
      → {axis: business_years, op: lte, value: 7, alt: 0}  ← 둘 다 맞아야 한다

**한 문장 안의 `또는` 이 다 OR 은 아니다.** `본사 또는 사업장이 있는` · `특허 또는
상표권을 보유한` 은 한 조건이라 한 행이고 `alt` 는 0 이다. **축이 갈릴 때만** 번호를 준다.

### 두 가지를 더 지켜라

**4. `창업기업` 은 `sme` 가 아니다.** 기업 규모 구분(중소·중견·벤처)일 때만 `sme` 다.
`창업기업` 만 적혀 있고 연수가 없으면 **내지 마라** — 판정할 값이 없다.

**5. `entity_type` 은 셋이지만 표현은 여럿이다.** 아래는 전부 `entity_type` 이다.

    예비창업자 · 창업예정자 · 창업희망자 · 1인 창조기업 창업예정자 ·
    입주 후 3개월 이내 창업(사업자등록)이 가능한 자 ·
    예비창업자의 경우 입주 후 6개월 이내 사업자 등록이 가능한 자

**6. 업종은 industries 다.** `국내 AI 기반 Age-Tech 관련 기업` 은 conditions 가 아니라
industries 에 `AI` · `Age-Tech` 로 낸다.
"""

ROUNDS: dict[str, tuple[list[str], list[str], str]] = {
    "v1": (AXES_V1, OPS_V1, AXIS_DOC_V1),
    "v2": (AXES_V2, OPS_V2, AXIS_DOC_V2),
    "v3": (AXES_V2, OPS_V2, AXIS_DOC_V3),
    #: **같은 설정을 두 번 돌린다.** 이 레포는 같은 모델·같은 픽스처로 재현이 안 된
    #: 전례가 있다(추출 정확도 70.3 → 60.2 → 58.5). 라운드 차이를 말하기 전에
    #: **회차 간 변동을 먼저 재야 한다**
    "v2b": (AXES_V2, OPS_V2, AXIS_DOC_V2),
    "v3b": (AXES_V2, OPS_V2, AXIS_DOC_V3),
}
#: `alt` 를 스키마에 넣는 라운드.
#: **여기를 빼먹으면 프롬프트만 바뀌고 스키마는 안 바뀐다** — v3b 가 그렇게 돌아서
#: OR 묶음 0개가 나왔고, 모델이 흔들린 줄 알았다. 실은 낼 칸이 없었다
WITH_ALT = {"v3", "v3b"}


def _cond_item(axes: list[str], ops: list[str], *, alt: bool) -> dict:
    """조건 하나의 스키마. **`strict` 라 필드는 전부 `required` 다.**"""
    props: dict = {
        "axis": {"type": "string", "enum": axes},
        "op": {"type": "string", "enum": ops},
        "value": {"type": ["number", "null"]},
        "quote": {"type": "string"},
    }
    if alt:
        #: 같은 번호끼리 OR. 0 이면 AND
        props["alt"] = {"type": "integer"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(props),
        "properties": props,
    }


def build(round_: str) -> tuple[str, dict]:
    axes, ops, doc = ROUNDS[round_]
    system = _HEAD + doc + _TAIL
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["regions", "industries", "conditions", "anchor"],
        "properties": {
            "regions": {"type": "array", "items": {"type": "string"}},
            "industries": {"type": "array", "items": {"type": "string"}},
            "conditions": {
                "type": "array",
                "items": _cond_item(axes, ops, alt=round_ in WITH_ALT),
            },
            "anchor": {"type": "string"},
        },
    }
    return system, schema


# ══════════════════════════════════════════════════════════════════
# 채점 — **근사다.** 통과한 것이 다 맞지는 않다
# ══════════════════════════════════════════════════════════════════
#: 축마다 (있어야 하는 말, 있으면 안 되는 말)
#: **2라운드 뒤에 고쳤다.** 채점기가 결과의 절반을 오탐으로 만들고 있었다 —
#: `벤처` 를 `벤처기업` 으로만 봐서 "물산업분야 벤처" 를 틀렸다 하고, `창업` 하나로
#: "창업자" 를 업력 조건이라 했다. **고친 뒤 모든 라운드를 다시 잰다** — 자가
#: 바뀌면 라운드 비교가 깨지므로 옛 라운드도 같은 자로 다시 잰다.
CHECK: dict[str, tuple[str, str | None]] = {
    #: **숫자와 년이 있어야 한다.** `창업자` · `예비창업자` 가 걸리면 안 된다
    "business_years": (
        r"(창업|업력|사업개시|설립|재창업)[^.]{0,20}?\d+\s*년|\d+\s*년\s*(이내|미만|이하|이상|초과)|\d+\s*년차",
        None,
    ),
    "ceo_age": (r"만?\s*\d+\s*세|연령|나이", None),
    "headcount": (r"근로자|직원|고용|종업원|임직원|상시|\d+\s*인\s*(미만|이하|이상)", None),
    "revenue": (r"매출|수출\s*실적|매출액", None),
    "capital": (r"자본금", None),
    "funding": (r"투자|유치|조달", None),
    #: `벤처기업` 이 아니라 `벤처` 다 — "물산업분야 벤처 또는 창업기업"
    "sme": (r"중소|중견|벤처|스타트업", r"소상공인|소공인|벤처기업\s*(확인|인증)"),
    "small_business": (r"소상공인|소공인", None),
    #: **`개인` 만으로는 안 된다** — "개인정보" 가 걸린다
    "entity_type": (r"예비창업|창업\s*예정|창업\s*희망|법인|개인\s*사업자|사업자\s*등록", None),
    #: **`연구소` 만으로는 안 된다** — "연구소 입주" 가 걸린다
    "certification": (
        r"인증|확인서|기업부설\s*연구소|전담부서|특허|상표권|이노비즈|메인비즈|인허가|등록증|임치",
        None,
    ),
    #: **`참여한`·`선정된` 이 기수혜다** — 공고가 그 말을 더 자주 쓴다
    "gov_program": (
        r"기수혜|재수혜|중복\s*수혜|이미\s*지원|동일\s*사업|수혜\s*이력|지원받은|"
        r"지원사업에\s*참여|선정된\s*(적|기업)",
        None,
    ),
}
_CHECK = {k: (re.compile(a), re.compile(b) if b else None) for k, (a, b) in CHECK.items()}


def ok_axis(axis: str, quote: str) -> bool | None:
    """이 축이 이 문장에 맞나. 축이 `other` 면 `None`(채점 대상 아님)."""
    if axis == "other":
        return None
    pair = _CHECK.get(axis)
    if pair is None:
        return False
    must, never = pair
    if never is not None and never.search(quote):
        return False
    return bool(must.search(quote))


def missed_axis(quote: str) -> str | None:
    """`other` 로 갔는데 축이 있어 보이는가. **미탐 근사다.**"""
    for axis, (must, never) in _CHECK.items():
        if never is not None and never.search(quote):
            continue
        if must.search(quote):
            return axis
    return None


def regex_axis(c: str) -> str:
    """지금 코드(`eligible.py`)가 이 문자열을 무엇으로 읽나."""
    if el._AGE_MAX.search(c):
        return "ceo_age"
    if el._DUP.search(c):
        return "gov_program"
    if el._STAFF_MAX.search(c) or el._STAFF_MIN.search(c):
        return "headcount"
    if el._SMALL.search(c):
        return "small_business"
    return "unhandled"


_ENYY = {"1년미만": 1, "2년미만": 2, "3년미만": 3, "5년미만": 5, "7년미만": 7, "10년미만": 10}


def enyy_ceiling(raw: str | None) -> int | None:
    vals = [_ENYY[v] for v in (raw or "").split(",") if v.strip() in _ENYY]
    return max(vals) if vals else None


def pick() -> list[tuple[nz.NoticeBody, str | None]]:
    """공고 50건. **무작위를 안 쓴다** — 라운드끼리 같은 표본이어야 한다."""
    out: list[tuple[nz.NoticeBody, str | None]] = []
    with session_scope() as s:
        rows = list(s.scalars(select(BizinfoNotice).order_by(BizinfoNotice.pblancId)))
        for r in rows[:: max(1, len(rows) // N_EACH)][:N_EACH]:
            out.append((bodies.from_bizinfo(r), None))
        krows = list(s.scalars(select(KstartupNotice).order_by(KstartupNotice.pbanc_sn)))
        for r in krows[:: max(1, len(krows) // N_EACH)][:N_EACH]:
            out.append((bodies.from_kstartup(r), r.biz_enyy))
    return out


def run_one(b: nz.NoticeBody, enyy: str | None, system: str, schema: dict) -> dict:
    #: **스레드마다 만든다.** `Usage.calls += 1` 이 원자적이 아니다
    c = llm.client()
    rec: dict = {
        "key": f"{b.source}:{b.external_id}",
        "title": b.title[:70],
        "biz_enyy": enyy,
        "enyy_ceiling": enyy_ceiling(enyy),
    }
    try:
        out = c.json(system=system, user=nz.user_prompt(b),
                     schema=schema, schema_name="notice_profile_x")
        anchor = (out.get("anchor") or "").strip()
        rec["anchor_ok"] = bool(anchor) and nz.squash(anchor) in nz.squash(b.text)
        rec["regions"] = out.get("regions") or []
        rec["industries"] = out.get("industries") or []
        rec["conditions"] = out.get("conditions") or []
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"[:200]
    rec["_usage"] = (c.usage.calls, c.usage.input_tokens, c.usage.output_tokens)
    return rec


def run(round_: str) -> None:
    system, schema = build(round_)
    picks = pick()
    print(f"[{round_}] 표본 {len(picks)}건 · 축 {len(ROUNDS[round_][0])}개")
    with ThreadPoolExecutor(max_workers=8) as ex:
        recs = list(ex.map(lambda t: run_one(t[0], t[1], system, schema), picks))
    total = llm.Usage()
    for r in recs:
        calls, i, o = r.pop("_usage", (0, 0, 0))
        total.merge(llm.Usage(calls=calls, input_tokens=i, output_tokens=o))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"spike-cond-{round_}.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    trace.flush()
    print(total.line())
    score(round_)


def load(round_: str) -> list[dict]:
    p = OUT / f"spike-cond-{round_}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def score(round_: str, *, show: bool = True) -> dict:
    recs = [r for r in load(round_) if "error" not in r]
    cs = [c for r in recs for c in r["conditions"]]
    typed = [c for c in cs if c["axis"] != "other"]
    good = [c for c in typed if ok_axis(c["axis"], c["quote"])]
    bad = [c for c in typed if not ok_axis(c["axis"], c["quote"])]
    oth = [c for c in cs if c["axis"] == "other"]
    miss = [(c, missed_axis(c["quote"])) for c in oth]
    miss = [(c, m) for c, m in miss if m]
    dead = sum(1 for r in recs if not any(c["axis"] != "other" for c in r["conditions"]))
    out = {
        "n": len(recs), "conds": len(cs), "typed": len(typed),
        "good": len(good), "bad": len(bad), "other": len(oth),
        "missed": len(miss), "dead": dead,
        "anchor_lost": sum(1 for r in recs if not r.get("anchor_ok")),
    }
    if show:
        print(f"\n=== [{round_}] 채점 ===")
        print(f"  조건 {out['conds']}개 · 축 붙음 {out['typed']} · other {out['other']}")
        print(f"  축이 맞음   {out['good']:3}  ({out['good']/max(1,out['conds']):.0%} of 전체)")
        print(f"  축이 틀림   {out['bad']:3}  ← 오분류. 여기가 오탈락을 만든다")
        print(f"  놓친 축     {out['missed']:3}  ← other 인데 축이 있어 보인다")
        print(f"  판정 0 공고 {out['dead']:3}/{out['n']}")
        print(f"  앵커 유실   {out['anchor_lost']:3}/{out['n']}")
        if bad:
            print("\n  --- 축이 틀린 것 ---")
            for c in bad[:20]:
                print(f"    [{c['axis']:14}] {c['quote'][:62]}")
        if miss:
            print("\n  --- other 인데 축이 있어 보이는 것 ---")
            for c, m in miss[:20]:
                print(f"    →{m:14} {c['quote'][:62]}")
    return out


def cmp_rounds() -> None:
    rs = [r for r in ROUNDS if (OUT / f"spike-cond-{r}.json").exists()]
    ss = {r: score(r, show=False) for r in rs}
    keys = ["conds", "typed", "good", "bad", "missed", "dead", "anchor_lost"]
    label = {"conds": "조건 수", "typed": "축 붙음", "good": "축이 맞음",
             "bad": "축이 틀림", "missed": "놓친 축", "dead": "판정 0 공고",
             "anchor_lost": "앵커 유실"}
    print(f"  {'':14}" + "".join(f"{r:>8}" for r in rs))
    for k in keys:
        print(f"  {label[k]:14}" + "".join(f"{ss[r][k]:>8}" for r in rs))
    print(f"  {'정확률':14}" + "".join(
        f"{ss[r]['good']/max(1,ss[r]['conds']):>7.0%} " for r in rs))


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "v1"
    if arg == "--cmp":
        cmp_rounds()
    elif arg == "--score":
        score(sys.argv[2])
    else:
        run(arg)
