"""분야 대조 (plan/17 T-0073 · M2 앞단).

**아래 `NEED` 는 `c_dasiro` 위키의 실값이다.** 로드맵·자금·기술 노드 아홉 줄을
그대로 옮겼다 — 어휘를 그 위에서 골랐으므로 정답지도 그것이어야 한다.

버킷 열 개가 맞음 넷 · 밀림 여섯으로 갈린다. 이 회사는 국내 소상공인 대상 구독
사업이라 **해외진출 153건이 밀리는 것**이 이 표의 값이다.
"""

from __future__ import annotations

from finnect.match import sectors as sc

#: `c_dasiro` 의 `need_text()` — roadmap · finance · solution 아홉 줄
NEED = " ".join(
    [
        "정부지원금 집행 계획 합계 7,000만원 — 인건비 3,600 · 외주용역비 1,800 · "
        "지급수수료 600 · 광고선전비 500 · 기타 500만원",
        "2025년말 현금 1억 8,270만원. 현재 소진 속도로 2027년 1분기까지 운영 가능하다",
        "2025년말 결손금이 자본금을 초과하며, 2025.09 유치 자금으로 향후 18개월 "
        "운영이 가능하다고 판단했습니다",
        "2단계 2026. 07. ~ 12. — 경기 남부 지역 영업망 구축, 유료 전환 매장 300곳",
        "이번 라운드(브리지) 5억원 목표 — 2026.10 클로징 목표, 영업 확장 및 다점포 개발",
        "1단계 2026. 01. ~ 06. — POS 3사 연동 완료, 유료 전환 매장 120곳",
        "특허 출원 — 오프라인 환경에서의 재고 기록 동기화 방법 및 장치 (10-2025-0114882)",
        "파일럿 매장에 자체 QR을 부착한 구간 (2025.07.14 현장)",
        "1단계 모듈의 프로토타입 개발을 마쳤다",
    ]
)

#: 버킷별 정답. **육안 검증 기록이다** — 아홉 줄을 놓고 하나씩 맞춰 봤다
정답 = {
    "투자": True,
    "사업화": True,
    "기술": True,
    "판로_국내": True,
    "판로_해외": False,
    "공간": False,
    "인력": False,
    "융자": False,
    "배움": False,
    "정보": False,
}


def _cat(bucket: str) -> str:
    """그 버킷으로 가는 기업마당 분류값 하나."""
    return next(k for k, v in sc.BIZINFO.items() if v == bucket)


def test_버킷_열_개가_정답대로_갈린다() -> None:
    for bucket, want in 정답.items():
        got = sc.match("bizinfo", _cat(bucket), NEED)
        assert got.hit is want, f"{bucket} — 어휘 {list(got.cues)}"


def test_공백을_지우면_융자가_오탐이_난다() -> None:
    """`결손금이 자본금을` 에서 `이자` 가 걸렸다. **실측으로 잡은 버그다.**"""
    assert "이자" not in NEED
    assert "이자" in NEED.replace(" ", "")
    assert sc.match("bizinfo", "융자", NEED).hit is False


def test_해외진출이_밀린다() -> None:
    """기업마당 542건 중 153건(28%)이 해외 계열이다."""
    for cat in ("해외진출", "해외진출준비", "시장개척", "FTA활용/대응", "보험(수출+무역)"):
        m = sc.match("bizinfo", cat, NEED)
        assert m.bucket == "판로_해외"
        assert m.hit is False


def test_투자와_사업화가_맞는다() -> None:
    투자 = sc.match("bizinfo", "펀드/투자", NEED)
    assert 투자.hit and "브리지" in 투자.cues
    사업화 = sc.match("bizinfo", "사업화지원", NEED)
    assert 사업화.hit and "인건비" in 사업화.cues


# ─────────────────────────── 표 두 벌 ───────────────────────────


def test_표_두_벌의_키가_안_겹친다() -> None:
    """이름 교집합이 0 이라 공통 분류로 못 접는다."""
    assert not (set(sc.BIZINFO) & set(sc.KSTARTUP))


def test_기업마당_39종_kstartup_11종이_다_있다() -> None:
    assert len(sc.BIZINFO) == 39
    assert len(sc.KSTARTUP) == 11
    # 모든 값이 실제 버킷을 가리킨다
    assert set(sc.BIZINFO.values()) <= set(sc.BUCKETS)
    assert set(sc.KSTARTUP.values()) <= set(sc.BUCKETS)


def test_HTML_엔티티를_읽는_쪽에서_푼다() -> None:
    """DB 에 `기술개발(R&amp;D)` 로 앉아 있다. 저장할 때 고치지 않는다."""
    m = sc.match("kstartup", "기술개발(R&amp;D)", NEED)
    assert m.bucket == "기술"
    assert m.hit is True


def test_kstartup_사업화가_같은_버킷으로_간다() -> None:
    """`사업화` 하나가 24% 라 이 표는 힘이 약하다 — 그래도 갈리기는 한다."""
    assert sc.match("kstartup", "사업화", NEED).hit is True
    assert sc.match("kstartup", "판로ㆍ해외진출", NEED).hit is False


# ─────────────────────────── 표 밖의 값 ───────────────────────────


def test_표에_없는_분류는_밀리고_보고된다() -> None:
    """**조용히 통과시키지 않는다.** 새 분류가 생기면 `--report` 가 센다."""
    m = sc.match("bizinfo", "새로생긴분야", NEED)
    assert m.hit is False and m.bucket == ""
    assert sc.unknown_categories("bizinfo", ["새로생긴분야", "융자", None]) == ["새로생긴분야"]


def test_정보_버킷은_어휘가_비어_항상_밀린다() -> None:
    """제도·동반성장·정보제공은 로드맵과 이을 낱말이 없다."""
    assert sc.BUCKETS["정보"] == ()
    for cat in ("제도", "동반성장", "기술정보제공", "창업정보제공"):
        assert sc.match("bizinfo", cat, NEED).hit is False


def test_모르는_출처는_밀린다() -> None:
    assert sc.match("newsource", "사업화", NEED).hit is False
