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

from finnect.wiki import extract_nodes, extract_profile, merge, profile, spots, tree
from finnect.wiki.extract_nodes import NodeFact
from finnect.wiki.extract_profile import ProfileFact
from finnect.wiki.merge import Claim, Status

D = dt.date


def _claim(slot: str, value: str, as_of: D | None = None, qualifier: str | None = None) -> Claim:
    return Claim(key=slot, qualifier=qualifier, as_of=as_of, value=value)


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
# 픽스처 번역 — **라우팅이 여기로 옮겨 왔다**(T-0126)
#
# 2026-08-22 까지 `merge.place` 가 `topic` 을 표에서 찾아 자리를 정했다. 이제 추출기가
# 자리를 알고 나오고, 옛 어휘를 옮기는 것은 스텁의 일이다.
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["상시 근로자", "종업원 수", "구성원", "임직원", "직원 수"])
def test_직원_수의_네_이름이_한_슬롯으로_모인다(key: str):
    """**문자열이 다르다고 슬롯이 갈리면 안 된다**(픽스처 함정 1)."""
    assert profile.key_of(key) == "headcount"


def test_업태와_종목은_다른_슬롯이다():
    """하나로 접으면 `정보통신업` 과 `응용 소프트웨어…` 가 같은 자리에 앉아 없는 충돌이 난다."""
    assert profile.key_of("업태") == "industry"
    assert profile.key_of("종목") == "industry_item"


def test_모르는_이름은_버리지_않고_검토_대기로_간다():
    """`업력` 은 슬롯이 없다. 문서에 박힌 업력은 기준일이 달라 그대로 믿으면 틀린다."""
    d = {"kind": "value", "topic": "company_profile", "key": "업력",
         "value": "1년 6개월", "text": "업력 1년 6개월", "anchor": "업력"}
    #: 트랙 B 는 안 받는다 — 열넷 밖이다
    assert extract_profile.from_fixture(d) is None
    #: 트랙 A 가 **값으로** 받는다. 버리지 않는다
    got = extract_nodes.from_fixture(d)
    assert got is not None
    assert (got.path, got.kind) == (spots.REVIEW.path, "value")
    assert "업력" in got.why


def test_서술_노드가_없는_topic_은_검토_대기로_간다():
    """`company_profile` 은 매칭 정보의 재료라 노드 자리가 없다."""
    got = extract_nodes.from_fixture(
        {"kind": "event", "topic": "company_profile", "text": "회사 개요", "anchor": "회사 개요"}
    )
    assert got.path == spots.REVIEW.path


def test_트랙이_갈리고_한_사실이_양쪽에_안_간다():
    """**같은 픽스처 줄을 둘 다 받으면 사실이 두 번 선다.** `key_of` 하나가 가른다."""
    d = {"kind": "value", "topic": "company_profile", "key": "상시 근로자",
         "value": "15", "text": "상시 근로자 15명", "anchor": "상시 근로자 15명"}
    assert extract_profile.from_fixture(d).key == "headcount"
    assert extract_nodes.from_fixture(d) is None


def test_모든_픽스처_topic_이_갈_자리가_있거나_왜_없는지_적혀_있다():
    """**표에 구멍이 있으면 사실이 조용히 검토 대기에 쌓인다.** 여기서 잡는다.

    셋만 일부러 자리가 없다.

    - `company_profile` · `application_history` — 매칭 정보의 재료라 자리가 없다
    - `FIXTURE_GAP` 셋 — 기획 트리에 자리가 없거나(지역 연계) 픽스처에 인스턴스
      이름이 없다(인증명·기술명). **이유가 `FIXTURE_GAP` 에 적혀 있어야 한다**
    """
    value_only = {"company_profile", "application_history"}
    for topic in extract_nodes.FIXTURE_TOPICS - value_only:
        if topic in extract_nodes.FIXTURE_GAP:
            assert extract_nodes.FIXTURE_GAP[topic], topic
            continue
        path = extract_nodes.FIXTURE_PATH.get(topic)
        assert path, topic
        #: **자리표 안에 실재해야 한다.** 밖이면 화면이 그 자리를 잃는다
        assert spots.spot_of(path) is not None, path
        assert tree.category_of(path) in spots.FOLDERS, path


def test_픽스처_경로에_채우다_만_구멍이_없다():
    """`Custom/인증/{인증명}` 같은 것이 표에 남으면 **그 글자가 자리 이름이 된다.**"""
    for topic, path in extract_nodes.FIXTURE_PATH.items():
        assert "{" not in path, (topic, path)


def test_별칭이_가리키는_슬롯이_전부_실재한다():
    for key, slot in profile.ALIASES.items():
        assert slot in profile.PROFILE_KEYS, f"{key} → {slot}"


# ─────────────────────────────────────────────────────────────────
# 병합 키
# ─────────────────────────────────────────────────────────────────


def _pf(**kw) -> ProfileFact:
    base = {"key": "industry_item", "value": "", "anchor": "", "text": ""}
    return ProfileFact(**{**base, **kw})


def test_띄어쓰기만_다른_값은_하나로_모인다():
    """OCR 이 `응용 소프트웨어개발및공급업` 을 낸다. 안 모으면 노이즈가 전부 충돌이 된다."""
    a = _pf(value="응용 소프트웨어 개발 및 공급업", as_of=D(2024, 3, 11))
    b = _pf(value="응용 소프트웨어개발및공급업", as_of=D(2024, 3, 11))
    assert merge.value_key(a) == merge.value_key(b)


def test_시점_없는_슬롯은_시점이_와도_떨어진다():
    """사업자등록번호에 발급일이 붙어 오면 자리가 갈려 충돌이 안 잡힌다."""
    f = _pf(key="business_no", value="501-86-33271", as_of=D(2024, 3, 11))
    assert profile.as_of_for("business_no", f.as_of) is None
    assert merge.value_key(f).endswith("||501-86-33271")


def test_똑같은_것은_두_번_안_선다():
    """**중복 방지가 트랙 A 에 남은 전부다**(ADR-0058).

    같은 자리 · 같은 시점 · 같은 문장이면 한 행이고 근거만 쌓인다. 파서마다 줄바꿈이
    달라서 공백을 지운 뒤 비교한다 — 안 지우면 `--rechunk` 뒤에 같은 문장이 또 앉는다.
    """
    a = NodeFact(path="Customer/검증/파일럿-12개소", kind="event", anchor="",
                 text="월 재구매율이 34%에서 51%로 올랐다")
    b = NodeFact(path="Customer/검증/파일럿-12개소", kind="event", anchor="",
                 text="월 재구매율이\n34%에서 51%로  올랐다")
    assert merge.node_key(a) == merge.node_key(b)


def test_다르게_쓰인_같은_사실은_둘로_선다():
    """**이 테스트가 ADR-0058 의 대가를 잠근다.**

    재구매율 하나가 네 문서에 `올랐다`·`상승했다`·`올랐습니다`·`34% → 51%` 로 있다.
    옛 `key` 가 그 넷을 하나로 묶었고, `key` 를 없애면서 **묶는 근거가 사라졌다.**

    묶으려면 문장 유사도밖에 없는데 그건 같은 문서를 두 번 올릴 때 다른 답을 내서
    비결정론이다. **둘로 서는 것이 결정이고 사고가 아니다** — 여기가 뒤집히면
    누군가 유사도를 넣은 것이다.
    """
    a = NodeFact(path="Customer/검증/파일럿-12개소", kind="event", anchor="",
                 text="월 재구매율이 34%에서 51%로 올랐습니다")
    b = NodeFact(path="Customer/검증/파일럿-12개소", kind="event", anchor="",
                 text="34% → 51%")
    assert merge.node_key(a) != merge.node_key(b)


def test_시점이_다르면_다른_기록이다():
    """**쌓이는 축이 시점이다**(ADR-0057 결정 1·2). 한 자리 안에서 이력이 된다."""
    a = NodeFact(path="Company/팀", kind="event", anchor="", text="개발 8명",
                 as_of=D(2026, 8, 31))
    b = NodeFact(path="Company/팀", kind="event", anchor="", text="개발 8명",
                 as_of=D(2025, 11, 30))
    assert merge.node_key(a) != merge.node_key(b)


def test_자리가_다르면_같은_문장이라도_다른_사실이다():
    """자리를 키에서 빼면 트리 어디에 있든 같은 문장이 하나로 접힌다."""
    a = NodeFact(path="Company/팀", kind="event", anchor="", text="열다섯 명이다")
    b = NodeFact(path="Financial/매출", kind="event", anchor="", text="열다섯 명이다")
    assert merge.node_key(a) != merge.node_key(b)


def test_값은_값이_키에_들어간다():
    """같은 자리·같은 시점에 값이 둘이면 **행이 둘로 서고 사용자가 본다.**

    어느 하나를 고르지 않는다(F1-1-7). 트랙 A 에는 `status` 가 없어서 `conflict` 라는
    이름표가 안 붙을 뿐, 둘 다 남는 것은 같다.
    """
    a = NodeFact(path="Financial/자금계획", kind="value", anchor="", text="",
                 qualifier="시드", value="300000000", as_of=D(2025, 9, 30))
    b = NodeFact(path="Financial/자금계획", kind="value", anchor="", text="",
                 qualifier="시드", value="280000000", as_of=D(2025, 9, 30))
    assert merge.node_key(a) != merge.node_key(b)
    #: 공백만 다른 값은 하나다 — 트랙 B 와 같은 규칙이어야 한다
    c = NodeFact(path="Financial/자금계획", kind="value", anchor="", text="",
                 qualifier="시드", value="300 000 000", as_of=D(2025, 9, 30))
    assert merge.node_key(a) == merge.node_key(c)


def test_한정어가_값을_가른다():
    """**`key` 가 없어지면서 한정어가 그 일을 받았다.** TAM·SAM·SOM 이 한 자리에 산다."""
    tam = NodeFact(path="Market/시장규모", kind="value", anchor="", text="",
                   qualifier="TAM", value="100000000000", as_of=D(2025, 12, 31))
    sam = NodeFact(path="Market/시장규모", kind="value", anchor="", text="",
                   qualifier="SAM", value="20000000000", as_of=D(2025, 12, 31))
    assert merge.node_key(tam) != merge.node_key(sam)


def test_공백_지운_항목_이름도_슬롯을_찾는다():
    """HWP 표와 OCR 이 띄어쓰기를 지워서 낸다 — **표에 있는 말이 미분류로 가면 안 된다.**

    plan/19 항목 7. `match/sectors.py` 와 반대로 여기는 공백을 지워야 한다 — 저기는
    본문에서 어휘를 **찾는** 것이고 여기는 이름 하나를 **꺼내는** 것이다.
    """
    assert profile.key_of("상시근로자") == "headcount"
    assert profile.key_of("직원수") == "headcount"
    assert profile.key_of("종업원수") == "headcount"
    assert profile.key_of("대표자생년월일") == "ceo_birth"
    #: 공백만 넣어도 찾는다
    assert profile.key_of("자 본 금") == "capital"
    #: **모르는 것은 그대로 모른다.** 추측하지 않는다
    assert profile.key_of("직원현황표") is None


def test_공백을_지워도_별칭이_안_부딪힌다():
    """부딪히면 같은 문자열이 슬롯 둘을 가리켜 라우팅이 뒤집힌다."""
    tight: dict[str, set[str]] = {}
    for alias, slot in profile.ALIASES.items():
        tight.setdefault("".join(alias.split()), set()).add(slot)
    assert {k: v for k, v in tight.items() if len(v) > 1} == {}
