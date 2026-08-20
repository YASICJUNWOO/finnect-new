"""순서와 이유 (plan/17 T-0074 · M2).

**이유 문장을 코드가 만드는 자리라 조사가 여기서 틀리면 화면 카피가 틀린다.**

1. 등급 셋. 점수가 없다
2. 겹친 노드가 0건이면 이유가 없고 추천에 안 오른다 (`SPEC.md` §9-2)
3. 근거는 겹친 노드 **전부**를 든다 — 문장에 쓰는 것은 하나지만 낡음 계산이 전부를 읽는다
4. 흔한 낱말(`지원`·`기업`)로 겹침을 세지 않는다
"""

from __future__ import annotations

from finnect.match import rank as rk
from finnect.match.profile import NodeFact
from finnect.models import FitVerdict

NODES = (
    NodeFact(
        8801,
        "identity",
        "바코드와 QR로 입출고 기록을 자동으로 남겨, 발주 시점을 놓치지 않게 하는 "
        "소상공인용 재고관리 소프트웨어",
    ),
    NodeFact(8814, "customer", "1차 목표 시장은 매장 1~3개를 직접 운영하는 식자재 소매 사업자다"),
    NodeFact(8836, "region", "성남 지역 상인회 3개소와 업무협약 체결"),
    NodeFact(8822, "roadmap", "2단계 경기 남부 지역 영업망 구축, 유료 전환 매장 300곳"),
)


def _j(keywords, sector_hit=False):  # noqa: ANN001, ANN202
    return rk.judge(keywords=keywords, nodes=NODES, sector_hit=sector_hit)


# ─────────────────────────── 등급 ───────────────────────────


def test_겹치면_맞다() -> None:
    f = _j(("소상공인", "디지털전환"))
    assert f.verdict is FitVerdict.MATCH
    assert f.matched == ("소상공인",)


def test_안_겹치는데_분야가_맞으면_애매() -> None:
    f = _j(("의료기기", "임상"), sector_hit=True)
    assert f.verdict is FitVerdict.MAYBE
    assert f.reason == ""


def test_안_겹치고_분야도_아니면_아니다() -> None:
    assert _j(("의료기기",)).verdict is FitVerdict.MISS


def test_이유가_없으면_추천에_안_오른다() -> None:
    """`SPEC.md` §9-2 — 템플릿이라 못 만드는 경우가 겹침 0 하나뿐이다."""
    f = _j(("의료기기",), sector_hit=True)
    assert not f.reason
    assert not f.evidence


# ─────────────────────────── 이유 문장 ───────────────────────────


def test_이유가_주제와_근거를_함께_말한다() -> None:
    f = _j(("소상공인", "재고관리"))
    assert f.reason.startswith("소상공인·재고관리가 주제예요.")
    assert "재고관리" in f.reason


def test_조사가_받침에_맞는다() -> None:
    assert rk.josa("소상공인", "이", "가") == "이"  # ㄴ 받침
    assert rk.josa("재고관리", "이", "가") == "가"  # 받침 없음
    assert rk.josa("기술", "이", "가") == "이"
    assert rk.josa("IR", "이", "가") == "가"  # 한글이 아니면 없는 쪽
    assert rk.josa("", "이", "가") == "가"


def test_짧은_근거는_안_자른다() -> None:
    """실측 — `c_dasiro` 노드 서른 개 중 70자를 넘는 것은 하나(자금 83자)다."""
    f = _j(("소상공인",))
    assert "…" not in f.reason
    assert f.reason.endswith("소상공인용 재고관리 소프트웨어")


def test_긴_근거는_잘라_한_줄에_넣는다() -> None:
    긴것 = (
        NodeFact(
            9001,
            "finance",
            "정부지원금 집행 계획 합계 7,000만원 — 인건비 3,600 · 외주용역비 1,800 · "
            "지급수수료 600 · 광고선전비 500 · 기타 500만원",
        ),
    )
    f = rk.judge(keywords=("정부지원금",), nodes=긴것, sector_hit=False)
    assert "…" in f.reason
    assert len(f.reason) < 100


def test_겹침이_많은_노드를_근거로_고른다() -> None:
    """`region` 이 둘 다 맞았고 `identity` 는 하나도 안 맞았다."""
    f = _j(("성남", "상인회"))
    assert "상인회" in f.reason
    assert 8836 in f.evidence


# ─────────────────────────── 근거 ───────────────────────────


def test_근거는_겹친_노드_전부를_든다() -> None:
    """문장에 쓰는 것은 하나지만, 낡음 계산이 전부를 읽는다."""
    f = _j(("소상공인", "매장"))
    assert len(f.evidence) >= 2
    assert 8801 in f.evidence  # 소상공인
    assert 8814 in f.evidence  # 매장


# ─────────────────────────── 흔한 낱말 ───────────────────────────


def test_흔한_낱말로_겹침을_세지_않는다() -> None:
    """`지원`·`기업`·`사업` 은 어느 위키에나 있어 전부 `맞다` 가 된다."""
    assert _j(("지원", "기업", "사업", "창업")).verdict is FitVerdict.MISS


def test_한_글자는_안_센다() -> None:
    assert _j(("A", "매")).verdict is FitVerdict.MISS


def test_키워드가_전부_걸러지면_겹침_0_이다() -> None:
    f = _j(("지원", "모집", "선정"), sector_hit=True)
    assert f.verdict is FitVerdict.MAYBE


# ─────────────────────────── 정렬 ───────────────────────────


def test_등급이_먼저_분야가_다음_마감이_마지막() -> None:
    맞다먼저 = rk.sort_key(str(FitVerdict.MATCH), False, 0, 300)
    애매나중 = rk.sort_key(str(FitVerdict.MAYBE), True, 9, 1)
    assert 맞다먼저 < 애매나중

    분야맞음 = rk.sort_key(str(FitVerdict.MATCH), True, 1, 100)
    분야밀림 = rk.sort_key(str(FitVerdict.MATCH), False, 5, 1)
    assert 분야맞음 < 분야밀림

    급함 = rk.sort_key(str(FitVerdict.MATCH), True, 1, 3)
    안급함 = rk.sort_key(str(FitVerdict.MATCH), True, 1, 90)
    assert 급함 < 안급함


def test_마감일이_없으면_맨_뒤다() -> None:
    """기업마당 접수 기간의 57%가 날짜가 아니다. 급하지 않다."""
    있음 = rk.sort_key(str(FitVerdict.MATCH), True, 1, 200)
    없음 = rk.sort_key(str(FitVerdict.MATCH), True, 1, None)
    assert 있음 < 없음


def test_확인_필요가_아니다보다_뒤다() -> None:
    """둘 다 추천에 안 오르지만 순서를 정해 둔다 — 목록의 꼬리다."""
    assert rk.sort_key(str(FitVerdict.MISS), False, 0, 1) < rk.sort_key(
        str(FitVerdict.UNKNOWN), False, 0, 1
    )


# ─────────────────────── 근거 노드 우선순위 (실측 수정) ───────────────────────

#: `c_dasiro` 실값. **`problem` 이 짧고 `identity` 가 길다** — 실측에서 그래서 틀렸다
실물 = (
    NodeFact(1, "problem", "성남·용인 소상공인 30명 중 21명(70%)이 재고를 수기로 관리하고 있었다"),
    NodeFact(
        2,
        "identity",
        "바코드와 QR로 입출고 기록을 자동으로 남겨, 발주 시점을 놓치지 않게 하는 "
        "소상공인용 재고관리 소프트웨어",
    ),
)


def test_짧은_problem_보다_긴_identity_를_근거로_고른다() -> None:
    """**2026-08-20 손 라벨 15건에서 잡은 결함이다.**

    고치기 전 이유가 이랬다 — "소상공인이 주제예요. 성남·용인 소상공인 30명 중
    21명(70%)이 재고를 수기로 관리하고 있었다". 그건 **시장 조사 결과이지 우리가
    맞는 이유가 아니다.**
    """
    f = rk.judge(keywords=("소상공인",), nodes=실물, sector_hit=True)
    assert "재고관리 소프트웨어" in f.reason
    assert "21명" not in f.reason
    # 근거 링크는 둘 다 남는다 — 낡음 계산이 전부를 읽는다
    assert set(f.evidence) == {1, 2}


def test_겹침_수가_노드_종류보다_앞이다() -> None:
    """종류는 동점을 가르는 것이다. 겹침이 더 많으면 `problem` 도 이긴다."""
    f = rk.judge(keywords=("소상공인", "재고", "수기"), nodes=실물, sector_hit=True)
    assert "21명" in f.reason  # problem 이 셋 다 맞았다


def test_표에_없는_노드는_맨_뒤다() -> None:
    낯선것 = (
        NodeFact(3, "새로생긴노드", "소상공인 관련 새 자리"),
        NodeFact(4, "identity", "소상공인용 재고관리 소프트웨어"),
    )
    f = rk.judge(keywords=("소상공인",), nodes=낯선것, sector_hit=False)
    assert "재고관리" in f.reason


def test_모든_서술_노드가_표에_있다() -> None:
    """`topics.NODES` 에 노드가 더 생기면 여기도 채운다 — 안 채우면 맨 뒤로 밀린다."""
    from finnect.wiki import topics

    assert set(rk.NODE_RANK) == set(topics.NODES)
