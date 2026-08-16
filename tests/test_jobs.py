"""단일 실행 보장과 진행 상태.

DB 도 네트워크도 안 탄다. jobs 는 락과 진행 상태만 들고 있어서 가짜 작업으로 시험된다.
**두 번 눌렀을 때 두 번 도는 것이 이 모듈이 막아야 하는 유일한 사고다.**
"""

from __future__ import annotations

import threading

import pytest

from finnect.ingest import jobs


@pytest.fixture
def key(request: pytest.FixtureRequest) -> str:
    """테스트마다 다른 키. 모듈 전역 락이라 이름이 겹치면 서로 간섭한다."""
    return f"test:{request.node.name}"


def test_작업이_돌고_락이_풀린다(key: str) -> None:
    done = threading.Event()

    result = jobs.launch(key, done.set)

    assert result.started is True
    assert done.wait(timeout=5), "작업이 안 돌았다"
    _settle(key)
    assert jobs.running(key) is False
    assert jobs.progress_of(key) is None


def test_돌고_있으면_거절한다(key: str) -> None:
    hold, entered = threading.Event(), threading.Event()

    def work() -> None:
        entered.set()
        hold.wait(timeout=5)

    assert jobs.launch(key, work).started is True
    assert entered.wait(timeout=5)

    second = jobs.launch(key, lambda: pytest.fail("두 번째가 돌면 안 된다"))
    assert second.started is False
    assert second.reason  # 왜 거절했는지 비어 있으면 안 된다

    hold.set()
    _settle(key)


def test_출처가_다르면_같이_돈다() -> None:
    hold = threading.Event()
    a, b = "test:다른키-a", "test:다른키-b"

    assert jobs.launch(a, lambda: hold.wait(timeout=5)).started is True
    assert jobs.launch(b, lambda: hold.wait(timeout=5)).started is True

    hold.set()
    _settle(a)
    _settle(b)


def test_작업이_터져도_락이_풀린다(key: str) -> None:
    """실패한 채로 락이 잠기면 그 출처는 재기동 전까지 영영 못 돌린다."""
    boom = threading.Event()

    def work() -> None:
        boom.set()
        raise RuntimeError("BIZINFO_API_KEY 가 없다")

    assert jobs.launch(key, work).started is True
    assert boom.wait(timeout=5)
    _settle(key)

    assert jobs.running(key) is False
    assert jobs.launch(key, lambda: None).started is True
    _settle(key)


def test_진행_상태를_읽는다(key: str) -> None:
    hold, entered = threading.Event(), threading.Event()

    def work() -> None:
        jobs.report(key, jobs.Progress(pages=37, items=7400, expected=29789))
        entered.set()
        hold.wait(timeout=5)

    jobs.launch(key, work)
    assert entered.wait(timeout=5)

    got = jobs.progress_of(key)
    assert got == jobs.Progress(pages=37, items=7400, expected=29789)

    hold.set()
    _settle(key)


def test_총_건수를_모르면_진행률도_없다() -> None:
    """K-Startup 첫 응답 전에는 matchCount 를 모른다. 0% 로 지어내지 않는다."""
    assert jobs.Progress(pages=0, items=0, expected=None).percent is None
    assert jobs.Progress(pages=1, items=200, expected=29789).percent == 1
    assert jobs.Progress(pages=8, items=1538, expected=1538).percent == 100


def test_진행_상태는_갈아_끼운다() -> None:
    """적재 스레드가 계속 세는 값을 화면이 그대로 잡으면 한 화면 안에서 숫자가 어긋난다."""
    p = jobs.Progress(pages=1, items=200, expected=29789)
    with pytest.raises(Exception):  # noqa: B017 - frozen dataclass
        p.pages = 2  # type: ignore[misc]


def _settle(key: str, timeout: float = 5.0) -> None:
    """작업 스레드가 락을 놓을 때까지 기다린다."""
    lock = jobs._lock_for(key)
    assert lock.acquire(timeout=timeout), "락이 안 풀렸다"
    lock.release()
