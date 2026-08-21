"""라우팅과 병합 — plan/12 T-0045 · T-0046.

**핵심은 충돌과 시계열을 가르는 것이다.** 규칙 하나로 갈리는지를 여기서 본다.
DB 도 파일도 안 쓴다 — 전부 순수 함수다.

    직원 수 7 · 8 · 10 · 15   시점이 넷 다 다르다  →  시계열
    시드 3억 · 3억 · 2.8억     셋 다 2025-09       →  충돌

앞을 충돌로 세우면 오탐이고, 뒤를 시계열로 세우면 거짓이다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from finnect.wiki import merge, topics
from finnect.wiki.extract import Fact
from finnect.wiki.merge import Claim, Status

D = dt.date


def _claim(slot: str, value: str, as_of: D | None = None, qualifier: str | None = None) -> Claim:
    return Claim(slot=slot, qualifier=qualifier, as_of=as_of, value=value)


# ─────────────────────────────────────────────────────────────────
# 시계열이냐 충돌이냐 — 이 파일의 이유
# ─────────────────────────────────────────────────────────────────


def test_직원_수는_시점이_달라_시계열이다():
    """**값이 다르지만 모순이 아니다.** 7 → 8 → 10 → 15 는 성장이다."""
    claims = [
        _claim("headcount", "7", D(2025, 8, 22)),
        _claim("headcount", "8", D(2025, 11, 30)),
        _claim("headcount", "10", D(2026, 1, 31)),
        _claim("headcount", "15", D(2026, 8, 31)),
    ]
    v = merge.decide(claims)
    assert v[claims[-1]] == Status.CURRENT
    assert [v[c] for c in claims[:-1]] == [Status.SUPERSEDED] * 3
    assert Status.CONFLICT not in v.values()


def test_시드_금액은_같은_시점이라_충돌이다():
    """**같은 시점의 같은 사건인데 값이 다르다.** 2 대 1 이어도 다수결로 안 푼다."""
    claims = [
        _claim("funding", "300000000", D(2025, 9, 30), "시드"),
        _claim("funding", "280000000", D(2025, 9, 30), "시드"),
    ]
    v = merge.decide(claims)
    assert set(v.values()) == {Status.CONFLICT}


def test_한정어가_다르면_서로_간섭하지_않는다():
    """시드와 정책자금은 같은 슬롯이지만 다른 것이다. 시점이 달라도 시계열이 아니다."""
    seed = _claim("funding", "300000000", D(2025, 9, 30), "시드")
    loan = _claim("funding", "50000000", D(2025, 4, 30), "정책자금")
    v = merge.decide([seed, loan])
    assert v[seed] == Status.CURRENT
    assert v[loan] == Status.CURRENT


def test_시점_없는_슬롯은_값이_다르면_충돌이다():
    """사업자등록번호는 시점과 무관하게 하나여야 한다."""
    a = _claim("business_no", "501-86-33271")
    b = _claim("business_no", "501-86-99999")
    assert set(merge.decide([a, b]).values()) == {Status.CONFLICT}


def test_같은_값이_여러_번_와도_충돌이_아니다():
    """문서 넷이 같은 번호를 말하는 것은 근거가 넷인 것이지 충돌이 아니다."""
    c = _claim("business_no", "501-86-33271")
    assert merge.decide([c, c]) == {c: Status.CURRENT}


def test_시점_없는_값은_시점_있는_값을_밀어내지_못한다():
    """**언제 것인지 모르는 값이 아는 값을 이기면 안 된다.** 가장 오래된 것으로 놓는다."""
    dated = _claim("headcount", "15", D(2026, 8, 31))
    undated = _claim("headcount", "3", None)
    v = merge.decide([dated, undated])
    assert v[dated] == Status.CURRENT
    assert v[undated] == Status.SUPERSEDED


# ─────────────────────────────────────────────────────────────────
# 라우팅
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["상시 근로자", "종업원 수", "구성원", "임직원", "직원 수"])
def test_직원_수의_네_이름이_한_슬롯으로_모인다(key: str):
    """**문자열이 다르다고 슬롯이 갈리면 안 된다**(픽스처 함정 1)."""
    assert topics.slot_of(key) == "headcount"


def test_업태와_종목은_다른_슬롯이다():
    """하나로 접으면 `정보통신업` 과 `응용 소프트웨어…` 가 같은 자리에 앉아 없는 충돌이 난다."""
    assert topics.slot_of("업태") == "industry"
    assert topics.slot_of("종목") == "industry_item"


def test_모르는_이름은_버리지_않고_검토_대기로_간다():
    """`업력` 은 슬롯이 없다. 문서에 박힌 업력은 기준일이 달라 그대로 믿으면 틀린다."""
    spot = merge.place(
        Fact(topic="company_profile", kind="slot", text="업력 1년 6개월", anchor="업력", key="업력",
             value="1년 6개월")
    )
    assert spot.kind == topics.UNCATEGORIZED
    assert "업력" in spot.reason


def test_서술_노드가_없는_topic_은_검토_대기로_간다():
    """`company_profile` 은 정형 슬롯의 재료라 서술 노드가 없다."""
    spot = merge.place(
        Fact(topic="company_profile", kind="node", text="회사 개요", anchor="회사 개요")
    )
    assert spot.kind == topics.UNCATEGORIZED


def test_온톨로지의_모든_topic_이_갈_자리가_있다():
    """**표에 구멍이 있으면 사실이 통째로 검토 대기에 쌓인다.** 여기서 잡는다."""
    slot_only = {"company_profile", "application_history"}
    for topic in topics.TOPICS - slot_only:
        assert topics.orbit_of(topic) in topics.EVENT_ORBITS, topic


def test_별칭이_가리키는_슬롯이_전부_실재한다():
    for key, slot in topics.SLOT_ALIASES.items():
        assert slot in topics.SLOTS, f"{key} → {slot}"


# ─────────────────────────────────────────────────────────────────
# 병합 키
# ─────────────────────────────────────────────────────────────────


def test_띄어쓰기만_다른_값은_하나로_모인다():
    """OCR 이 `응용 소프트웨어개발및공급업` 을 낸다. 안 모으면 노이즈가 전부 충돌이 된다."""
    a = Fact(topic="company_profile", kind="slot", text="", anchor="", key="종목",
             value="응용 소프트웨어 개발 및 공급업", as_of=D(2024, 3, 11))
    b = Fact(topic="company_profile", kind="slot", text="", anchor="", key="종목",
             value="응용 소프트웨어개발및공급업", as_of=D(2024, 3, 11))
    assert merge.dedupe_key(a, merge.place(a)) == merge.dedupe_key(b, merge.place(b))


def test_시점_없는_슬롯은_시점이_와도_떨어진다():
    """사업자등록번호에 발급일이 붙어 오면 자리가 갈려 충돌이 안 잡힌다."""
    f = Fact(topic="company_profile", kind="slot", text="", anchor="", key="사업자등록번호",
             value="501-86-33271", as_of=D(2024, 3, 11))
    assert merge.as_of_for("business_no", f.as_of) is None
    assert merge.dedupe_key(f, merge.place(f)).endswith("||501-86-33271")


def test_fact_key_가_같으면_문장이_달라도_한_사실이다():
    """재구매율이 네 문서에 다른 문장으로 있다. **사실 넷이 되면 틀렸다.**"""
    a = Fact(topic="customer_evidence", kind="node", anchor="",
             text="월 재구매율이 34%에서 51%로 올랐습니다", fact_key="pilot_retention_34_51")
    b = Fact(topic="customer_evidence", kind="node", anchor="",
             text="34% → 51%", fact_key="pilot_retention_34_51")
    assert merge.dedupe_key(a, merge.place(a)) == merge.dedupe_key(b, merge.place(b))


def test_공백_지운_항목_이름도_슬롯을_찾는다():
    """HWP 표와 OCR 이 띄어쓰기를 지워서 낸다 — **표에 있는 말이 미분류로 가면 안 된다.**

    plan/19 항목 7. `match/sectors.py` 와 반대로 여기는 공백을 지워야 한다 — 저기는
    본문에서 어휘를 **찾는** 것이고 여기는 이름 하나를 **꺼내는** 것이다.
    """
    assert topics.slot_of("상시근로자") == "headcount"
    assert topics.slot_of("직원수") == "headcount"
    assert topics.slot_of("종업원수") == "headcount"
    assert topics.slot_of("대표자생년월일") == "ceo_birth"
    #: 공백만 넣어도 찾는다
    assert topics.slot_of("자 본 금") == "capital"
    #: **모르는 것은 그대로 모른다.** 추측하지 않는다
    assert topics.slot_of("직원현황표") is None


def test_공백을_지워도_별칭이_안_부딪힌다():
    """부딪히면 같은 문자열이 슬롯 둘을 가리켜 라우팅이 뒤집힌다."""
    tight: dict[str, set[str]] = {}
    for alias, slot in topics.SLOT_ALIASES.items():
        tight.setdefault("".join(alias.split()), set()).add(slot)
    assert {k: v for k, v in tight.items() if len(v) > 1} == {}
