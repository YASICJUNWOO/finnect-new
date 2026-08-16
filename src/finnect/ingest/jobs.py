"""버튼 뒤 — 한 출처에 하나만, 백그라운드 스레드에서.

요청 스레드에서 돌리면 K-Startup 149회가 끝날 때까지 응답이 안 나간다.
그래서 스레드로 뗀다. **스케줄러도 잡 큐도 아니다.** 프로세스가 죽으면 실행도 죽고,
남은 자국은 `runs.reap()` 이 INTERRUPTED 로 정리한다([ADR-0011](
../../../docs/adr/0011-수집-실행-화면.md)).

이 모듈은 DB 를 모른다. 락과 진행 상태만 들고 있어서 가짜 작업으로 시험할 수 있다.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Progress:
    """지금까지 받은 양. 실행 중에만 의미가 있다.

    frozen 이다. 적재 스레드의 IngestReport 는 계속 변하는데 화면 스레드가 그걸 그대로
    읽으면 한 화면 안에서 앞뒤가 안 맞는 숫자가 나온다. 매번 새로 만들어 갈아 끼운다.
    """

    pages: int = 0
    items: int = 0
    expected: int | None = None  # 출처가 말한 전량
    target: int | None = None  # 이번에 받기로 한 건수. None 이면 전량

    @property
    def goal(self) -> int | None:
        """진행률의 분모. 500건만 받는 중이면 분모도 500이어야 막대가 맞는다."""
        if self.target is None:
            return self.expected
        return min(self.target, self.expected) if self.expected else self.target

    @property
    def percent(self) -> int | None:
        goal = self.goal
        if not goal:
            return None
        return min(100, round(self.items * 100 / goal))


@dataclass(frozen=True)
class Launch:
    """실행 요청의 결과. 시작했거나, 왜 못 했는지."""

    started: bool
    reason: str = ""


_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_progress: dict[str, Progress] = {}


def launch(key: str, work: Callable[[], None]) -> Launch:
    """key 하나에 하나만 돌린다. 이미 돌고 있으면 거절한다.

    거절이 기본값이다. 큐에 쌓아 두면 버튼을 두 번 누른 사람이 두 번 도는 것을 못 본다.
    """
    lock = _lock_for(key)
    if not lock.acquire(blocking=False):
        return Launch(False, "이미 돌고 있다")

    with _guard:
        _progress[key] = Progress()

    def runner() -> None:
        try:
            work()
        except BaseException:  # noqa: BLE001 - 스레드 밖으로 안 나가므로 여기서 찍는다
            # work 안에서 이미 IngestRun.error 에 남긴다. 여기는 터미널용 사본이다.
            traceback.print_exc()
        finally:
            with _guard:
                _progress.pop(key, None)
            lock.release()

    threading.Thread(target=runner, name=f"ingest:{key}", daemon=True).start()
    return Launch(True)


def report(key: str, progress: Progress) -> None:
    with _guard:
        _progress[key] = progress


def progress_of(key: str) -> Progress | None:
    """돌고 있으면 진행 상태, 아니면 None."""
    with _guard:
        return _progress.get(key)


def running(key: str) -> bool:
    return _lock_for(key).locked()


def _lock_for(key: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(key, threading.Lock())
