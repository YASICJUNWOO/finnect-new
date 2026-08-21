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


def _j(keywords, label="", cues=()):  # noqa: ANN001, ANN202
    return rk.judge(
        keywords=keywords, nodes=NODES, sector_label=label, sector_cues=cues
    )


#: ④가 걸린 모양. `roadmap` 노드의 `영업망` 이 `판로_국내` 버킷의 낱말이다
분야걸림 = {"label": "국내 판로", "cues": ("영업망",)}


# ─────────────────────────── 등급 ───────────────────────────


def test_겹치면_맞다() -> None:
    f = _j(("소상공인", "디지털전환"))
    assert f.verdict is FitVerdict.MATCH
    assert f.matched == ("소상공인",)


def test_안_겹치는데_분야가_맞으면_애매() -> None:
    f = _j(("의료기기", "임상"), **분야걸림)
    assert f.verdict is FitVerdict.MAYBE


def test_안_겹치고_분야도_아니면_아니다() -> None:
    assert _j(("의료기기",)).verdict is FitVerdict.MISS


def test_분야도_안_걸리면_이유가_없다() -> None:
    """`SPEC.md` §9-2. **⑤도 ④도 못 만들 때만 빈다** (T-0076 이후)."""
    f = _j(("의료기기",))
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
    f = rk.judge(keywords=("정부지원금",), nodes=긴것)
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
    f = _j(("지원", "모집", "선정"), **분야걸림)
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
    f = rk.judge(keywords=("소상공인",), nodes=실물)
    assert "재고관리 소프트웨어" in f.reason
    assert "21명" not in f.reason
    # 근거 링크는 둘 다 남는다 — 낡음 계산이 전부를 읽는다
    assert set(f.evidence) == {1, 2}


def test_겹침_수가_노드_종류보다_앞이다() -> None:
    """종류는 동점을 가르는 것이다. 겹침이 더 많으면 `problem` 도 이긴다."""
    f = rk.judge(keywords=("소상공인", "재고", "수기"), nodes=실물)
    assert "21명" in f.reason  # problem 이 셋 다 맞았다


def test_표에_없는_노드는_맨_뒤다() -> None:
    낯선것 = (
        NodeFact(3, "새로생긴노드", "소상공인 관련 새 자리"),
        NodeFact(4, "identity", "소상공인용 재고관리 소프트웨어"),
    )
    f = rk.judge(keywords=("소상공인",), nodes=낯선것)
    assert "재고관리" in f.reason


def test_모든_서술_노드가_표에_있다() -> None:
    """`topics.NODES` 에 노드가 더 생기면 여기도 채운다 — 안 채우면 맨 뒤로 밀린다."""
    from finnect.wiki import topics

    assert set(rk.NODE_RANK) == set(topics.NODES)


# ─────────────── ④ 분야가 만드는 이유 (T-0076) ───────────────
#
# **실측이 만든 자리다.** 층0 542건 · 정규화 100건에서 자격을 넘은 8건 중 5건이
# `애매` 였고, 다섯 다 눈으로 보면 합리적인데 ⑤ 교집합이 0 이라 이유가 없었다.


def test_분야가_걸리면_그_노드로_이유를_만든다() -> None:
    f = _j(("의료기기", "임상"), **분야걸림)
    assert f.verdict is FitVerdict.MAYBE
    assert f.reason.startswith("국내 판로 분야예요.")
    # 근거가 `영업망` 이 실제로 든 노드다
    assert f.evidence == (8822,)
    assert "영업망" in f.reason


def test_분야_이유의_근거는_need_노드에서만_나온다() -> None:
    """④가 본 것이 `need_text()` 라 **그 밖의 노드를 근거로 들면 거짓말이다.**

    `identity` 노드에도 `소상공인` 이 있지만 ④는 그것을 안 봤다.
    """
    f = _j(("의료기기",), label="사업화", cues=("소상공인",))
    assert f.verdict is FitVerdict.MAYBE
    assert not f.reason  # need 노드(roadmap)에 `소상공인` 이 없다
    assert not f.evidence


def test_이름_없는_버킷은_이유를_안_만든다() -> None:
    """`정보` 버킷은 표시 이름이 없다. **지어내지 않는다.**"""
    f = _j(("의료기기",), label="", cues=("영업망",))
    assert f.verdict is FitVerdict.MAYBE
    assert not f.reason


def test_취지가_겹치면_분야_이유를_안_쓴다() -> None:
    """⑤가 먼저다. **`맞다` 의 이유를 `애매` 의 이유가 덮지 않는다.**"""
    f = _j(("소상공인",), **분야걸림)
    assert f.verdict is FitVerdict.MATCH
    assert "주제예요" in f.reason


def test_분야_이유도_한_줄로_자른다() -> None:
    긴것 = (NodeFact(1, "roadmap", "영업망 " + "가" * 200),)
    f = rk.judge(
        keywords=("의료기기",), nodes=긴것, sector_label="국내 판로", sector_cues=("영업망",)
    )
    assert len(f.reason) < 100
    assert f.reason.endswith("…")


# ─────────── 표 부스러기를 인용하지 않는다 (실측 · 2026-08-21) ───────────
#
# 진짜 추출기로 갈아 넣은 첫 추천에 이것이 나갔다 —
#   "사업화 분야예요. 통합 9만 9천원\t연동 + 다점포 통합 관리\t2027년 출시"

표부스러기 = "통합 9만 9천원\t연동 + 다점포 통합 관리\t2027년 출시"


def test_탭이_든_노드는_인용하지_않는다() -> None:
    nodes = (NodeFact(1, "roadmap", "영업망 " + 표부스러기),)
    f = rk.judge(
        keywords=("의료기기",), nodes=nodes, sector_label="국내 판로", sector_cues=("영업망",)
    )
    assert not f.reason
    assert f.evidence == (1,)  # **근거 링크는 남는다**


def test_인용할_수_있는_노드가_있으면_그것을_고른다() -> None:
    """더 좋은 자리에 있어도 **인용이 안 되면 밀린다.**"""
    nodes = (
        NodeFact(1, "solution", "특허 " + 표부스러기),          # NODE_RANK 가 앞
        NodeFact(2, "roadmap", "특허 출원을 마치고 프로토타입을 돌리고 있어요"),
    )
    f = rk.judge(
        keywords=("의료기기",), nodes=nodes, sector_label="기술 개발", sector_cues=("특허",)
    )
    assert f.reason == "기술 개발 분야예요. 특허 출원을 마치고 프로토타입을 돌리고 있어요"
    assert f.evidence == (1, 2)  # 둘 다 근거다


def test_취지_이유도_표_부스러기를_피한다() -> None:
    nodes = (
        NodeFact(1, "identity", "소상공인 " + 표부스러기),
        NodeFact(2, "market", "소상공인 재고관리 시장을 보고 있어요"),
    )
    f = rk.judge(keywords=("소상공인",), nodes=nodes)
    assert f.verdict is FitVerdict.MATCH
    assert f.reason.endswith("소상공인 재고관리 시장을 보고 있어요")


def test_전부_표_부스러기면_이유가_비고_근거는_남는다() -> None:
    nodes = (NodeFact(1, "identity", "소상공인 " + 표부스러기),)
    f = rk.judge(keywords=("소상공인",), nodes=nodes)
    assert f.verdict is FitVerdict.MATCH
    assert not f.reason
    assert f.evidence == (1,)


def test_줄바꿈이_든_노드도_인용하지_않는다() -> None:
    """탭을 막았더니 이번엔 줄이 셋인 목록이 나갔다 (같은 실측)."""
    여러줄 = "2027 상반기\n다점포 통합 관리 출시\n프랜차이즈 본부 영업 착수"
    nodes = (NodeFact(1, "roadmap", "출시 " + 여러줄),)
    f = rk.judge(
        keywords=("의료기기",), nodes=nodes, sector_label="사업화", sector_cues=("출시",)
    )
    assert not f.reason
    assert f.evidence == (1,)
