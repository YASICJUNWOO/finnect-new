"""진행률이 단계 둘을 말한다(2026-08-24).

K-Startup 을 모집중만 받으면 목록 뒤에 상세 페이지 긁기가 이어 붙는다. 그 몇 분 동안
목록 숫자만 보고 있으면 **막대가 멈춘 것처럼 보인다** — `running` 은 참인데 화면은
죽은 것으로 읽힌다. 여기서 잠그는 것 셋.

1. **분모가 단계마다 다르다.** 목록은 받을 공고 수, 첨부는 열 상세 페이지 수
2. **`items` 를 첨부 단계에서 재사용하지 않는다.** '공고 몇 건'과 '상세 몇 장'은 다른 뜻이다
3. **`launch()` 가 훅 둘을 다 건다.** 하나라도 빠지면 그 단계에서 막대가 선다

DB 도 네트워크도 안 탄다.
"""

from __future__ import annotations

from finnect.ingest import jobs


class Test분모가_단계마다_다르다:
    def test_목록_단계는_공고_수가_분모다(self) -> None:
        p = jobs.Progress(pages=2, items=134, expected=268)
        assert p.phase == jobs.PHASE_LIST, "기본값이 목록이다"
        assert p.goal == 268
        assert p.percent == 50

    def test_맛보기면_분모도_그만큼이다(self) -> None:
        """500건만 받는 중이면 분모도 500이어야 막대가 맞는다."""
        p = jobs.Progress(items=250, expected=29789, target=500)
        assert p.goal == 500
        assert p.percent == 50

    def test_첨부_단계는_상세_페이지_수가_분모다(self) -> None:
        p = jobs.Progress(
            pages=2, items=268, expected=268,
            phase=jobs.PHASE_ATTACH, scraped=67, scrape_total=268,
        )
        assert p.goal == 268
        assert p.percent == 25, "목록의 268/268(100%) 이 아니라 첨부의 67/268 이다"

    def test_첨부_대상이_0이면_분모가_없다(self) -> None:
        """이미 다 긁혀 있으면 대상이 0건이다. 0으로 나누지 않는다."""
        p = jobs.Progress(items=268, expected=268, phase=jobs.PHASE_ATTACH)
        assert p.goal is None
        assert p.percent is None

    def test_전량을_모르면_분모가_없다(self) -> None:
        assert jobs.Progress(items=10).percent is None


def test_목록_숫자를_첨부_단계에서도_들고_간다() -> None:
    """화면이 "공고 268건을 받았고 지금 그중 상세를 여는 중" 을 한 줄로 말해야 한다."""
    p = jobs.Progress(
        pages=2, items=268, expected=268,
        phase=jobs.PHASE_ATTACH, scraped=10, scrape_total=268,
    )
    assert (p.pages, p.items) == (2, 268), "목록 단계 값이 살아 있다"
    assert p.scraped == 10, "그리고 첨부 진행은 따로 센다"


def test_퍼센트는_100을_안_넘는다() -> None:
    """출처가 말한 전량보다 실제로 더 올 수 있다. 막대가 밖으로 나가면 안 된다."""
    assert jobs.Progress(items=300, expected=268).percent == 100
    assert jobs.Progress(
        phase=jobs.PHASE_ATTACH, scraped=300, scrape_total=268
    ).percent == 100


def test_launch가_훅_둘을_다_건다(monkeypatch) -> None:  # noqa: ANN001
    """**하나라도 빠지면 그 단계에서 막대가 선다.** 그게 이 파일이 생긴 이유다."""
    from finnect.ingest import service

    seen: dict[str, object] = {}

    def fake_execute(source: str, **kw: object) -> None:
        seen.update(kw)

    monkeypatch.setattr(service, "execute", fake_execute)
    monkeypatch.setattr(service.runs, "live", lambda _s: None)  # noqa: ARG005
    # jobs.launch 가 스레드를 띄우지 않게, work() 를 그 자리에서 부른다.
    monkeypatch.setattr(
        service.jobs, "launch", lambda _k, work, **_kw: (work(), jobs.Launch(True))[1]
    )

    result = service.launch("kstartup", trigger="admin")

    assert result.started
    assert callable(seen.get("on_page")), "목록 단계 훅이 없다"
    assert callable(seen.get("on_scrape")), "첨부 단계 훅이 없다 — 긁는 동안 막대가 선다"
