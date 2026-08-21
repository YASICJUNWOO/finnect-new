"""자격 대조 (plan/17 T-0072 · M1).

**축마다 확신이 다른 것이 이 파일의 요점이다.**

    소재지 안 맞음   →  탈락       주소 문자열에 지역명이 있다
    업종 안 맞음     →  확인 필요   `ICT` 와 `정보통신업` 이 안 겹친다
    연령 초과        →  탈락       숫자 비교다
    수혜 이력 있음   →  확인 필요   같은 사업인지 모른다

오탈락은 화면에서 사라져서 사용자가 알아챌 방법이 없다(ADR-0003). 오추천은 열어
보면 안다. 그래서 확신이 낮은 축을 탈락으로 두지 않는다.
"""

from __future__ import annotations

import datetime as dt

from finnect.match import eligible as el
from finnect.match.profile import CompanyProfile, NodeFact, SlotValue

ON = dt.date(2026, 8, 20)


def _me(**slots: str) -> CompanyProfile:
    base = {
        "location": "경기도 성남시 분당구 판교로 255, 3층",
        "industry": "정보통신업",
        "industry_item": "응용 소프트웨어 개발 및 공급업",
        "ceo_birth": "1992-07-04",
        "founded_on": "2024-03-11",
    }
    base.update(slots)
    return CompanyProfile(
        company_id="c_x",
        slots={
            k: SlotValue(value=v, as_of=None) for k, v in base.items() if v
        },
        nodes=(NodeFact(1, "identity", "소상공인용 재고관리 소프트웨어"),),
    )


def _j(**kw):  # noqa: ANN003, ANN202
    kw.setdefault("regions", ())
    kw.setdefault("industries", ())
    kw.setdefault("conditions", ())
    kw.setdefault("company", _me())
    kw.setdefault("on", ON)
    return el.judge(**kw)


# ─────────────────────────── 소재지 ───────────────────────────


def test_지역_제한이_없으면_통과() -> None:
    assert _j().ok


def test_시_단위가_맞으면_통과() -> None:
    assert _j(regions=("성남시",)).ok


def test_광역만_적혀_있어도_통과() -> None:
    assert _j(regions=("경기",)).ok
    assert _j(regions=("경기도",)).ok


def test_다른_시는_탈락() -> None:
    """**`[경기]` 46건 중 성남시가 2건이었다.** 광역으로 통과시키면 44건이 오추천이다."""
    j = _j(regions=("김포시",))
    assert j.verdict is el.Verdict.FAIL
    assert "김포시" in j.reasons[0]


def test_광역_약칭과_정식_이름을_둘_다_본다() -> None:
    대구 = _me(location="대구광역시 수성구 알파시티1로 170")
    assert _j(regions=("대구",), company=대구).ok
    충남 = _me(location="충청남도 천안시 서북구")
    assert _j(regions=("충남",), company=충남).ok
    assert _j(regions=("충북",), company=충남).verdict is el.Verdict.FAIL


def test_여러_지역_중_하나만_맞으면_통과() -> None:
    assert _j(regions=("충북", "충남", "대전", "세종", "경기")).ok


def test_소재지가_위키에_없으면_판정하지_않는다() -> None:
    """배제형 원칙을 쓰면 안 된다 — 공고는 분명히 말했고 우리가 모르는 것이다."""
    j = _j(regions=("성남시",), company=_me(location=""))
    assert j.verdict is el.Verdict.UNKNOWN
    assert "소재지" in j.unknowns[0]


# ─────────────────────────── 업종 ───────────────────────────


def test_업종이_부분_문자열로_겹치면_통과() -> None:
    assert _j(industries=("소프트웨어",)).ok
    assert _j(industries=("정보통신",)).ok


def test_업종이_안_겹치면_탈락이_아니라_확인_필요() -> None:
    j = _j(industries=("의료기기",))
    assert j.verdict is el.Verdict.UNKNOWN
    assert "의료기기" in j.unknowns[0]


def test_업종이_비면_무관이다() -> None:
    assert _j(industries=()).ok


# ─────────────────────────── 조건 ───────────────────────────


def test_연령_상한을_넘으면_탈락() -> None:
    젊음 = _me(ceo_birth="1992-07-04")  # 2026-08-20 기준 만 34세
    assert _j(conditions=("만 39세 이하",), company=젊음).ok
    j = _j(conditions=("만 30세 이하",), company=젊음)
    assert j.verdict is el.Verdict.FAIL
    assert "만 34세" in j.reasons[0]


def test_연령_표기_여럿을_읽는다() -> None:
    젊음 = _me()
    for c in ("만 39세 이하", "39세 이하", "만39세미만", "만 39 세 까지"):
        assert _j(conditions=(c,), company=젊음).ok, c


def test_생년월일이_없으면_연령을_판정하지_않는다() -> None:
    j = _j(conditions=("만 39세 이하",), company=_me(ceo_birth=""))
    assert j.verdict is el.Verdict.UNKNOWN


def test_수혜_이력이_있으면_확인_필요() -> None:
    """탈락이 아니다 — **같은 사업인지 모른다.**"""
    받음 = _me(gov_program="50000000")
    j = _j(conditions=("기수혜 기업 제외",), company=받음)
    assert j.verdict is el.Verdict.UNKNOWN
    없음 = _me()
    assert _j(conditions=("기수혜 기업 제외",), company=없음).ok


def test_규칙이_못_읽은_조건을_센다() -> None:
    """`SPEC.md` §2.1 이 "얼마나 되는지 모른다" 고 적어 둔 숫자다."""
    j = _j(conditions=("프로토타입 수준의 시연 가능한 제품 필요", "사업장 보유"))
    assert j.ok  # 조용히 통과시키되
    assert len(j.unhandled) == 2  # 세서 보고한다


def test_탈락이_확인_필요보다_세다() -> None:
    """둘이 같이 나오면 탈락이다. 확인 필요는 '아직 안 봤다' 라서 약하다."""
    j = _j(regions=("김포시",), industries=("의료기기",))
    assert j.verdict is el.Verdict.FAIL
    assert j.unknowns  # 기록은 남는다


# ─────────────────────────── 낱자 함수 ───────────────────────────


def test_한_글자_지역명을_안_만든다() -> None:
    """`도` 하나가 남으면 아무 주소에나 걸린다."""
    assert el._bare("도") == "도"
    assert el._bare("성남시") == "성남"
    assert el._bare("제주특별자치도") == "제주"


def test_업종_한_글자는_안_맞춘다() -> None:
    assert el.industry_hit("업", ("정보통신업",)) is False


# ─────────────────────── 규모 (실측 수정) ───────────────────────


def test_소상공인_전용을_직원_수로_뺀다() -> None:
    """**2026-08-20 손 라벨 15건에서 잡은 결함이다.**

    이 조건을 못 읽어서 소상공인 전용 공고 넷이 통과하고 **추천 3건을 통째로
    차지했다.** `c_dasiro` 는 직원 10명이라 소상공인이 아니다.
    """
    열명 = _me(headcount="10")
    j = _j(conditions=("「소상공인기본법」 제2조에 따른 소상공인",), company=열명)
    assert j.verdict is el.Verdict.FAIL
    assert "10명" in j.reasons[0]
    assert not j.unhandled  # 규칙이 읽었다


def test_소상공인_상한_아래면_업종을_봐야_한다() -> None:
    """업종별 기준이 5인 또는 10인이라 **대응표 없이 못 가른다.**"""
    셋 = _me(headcount="3")
    j = _j(conditions=("소상공인",), company=셋)
    assert j.verdict is el.Verdict.UNKNOWN
    assert "업종별 기준" in j.unknowns[0]


def test_상시근로자_상한을_읽는다() -> None:
    열명 = _me(headcount="10")
    assert _j(conditions=("상시 근로자 5인 미만",), company=열명).verdict is el.Verdict.FAIL
    assert _j(conditions=("상시근로자 10인 이하",), company=열명).verdict is el.Verdict.FAIL
    assert _j(conditions=("상시 근로자 수 30인 미만",), company=열명).ok


def test_상시근로자_하한을_읽는다() -> None:
    """`notice-filter` 축2f 와 같은 축이다 — 이쪽은 실제 직원 수를 본다."""
    셋 = _me(headcount="3")
    assert _j(conditions=("상시 근로자 5인 이상",), company=셋).verdict is el.Verdict.FAIL
    열다섯 = _me(headcount="15")
    assert _j(conditions=("상시 근로자 5인 이상",), company=열다섯).ok


def test_직원_수가_없으면_규모를_판정하지_않는다() -> None:
    j = _j(conditions=("소상공인",), company=_me(headcount=""))
    assert j.verdict is el.Verdict.UNKNOWN
    assert "직원 수가 없다" in j.unknowns[0]


def test_상한이_있으면_소상공인_어휘보다_상한을_따른다() -> None:
    """`소상공인(상시 근로자 5인 미만)` 처럼 같이 오면 숫자가 정확하다."""
    일곱 = _me(headcount="7")
    j = _j(conditions=("소상공인(상시 근로자 5인 미만)",), company=일곱)
    assert j.verdict is el.Verdict.FAIL
    assert "7명" in j.reasons[0]
