"""LLM 추적 — Langfuse (OTLP/HTTP 하나).

**진짜로 보내지 않는다.** 네트워크가 붙고 키가 있어야 하고, 여기서 막는 것은 규율이다.

1. **관측이 본 일을 막지 않는다.** 전송이 터져도 `json()` 은 결과를 낸다
2. 키가 없으면 **그냥 꺼진다.** `wiki_extractor` 처럼 멈추지 않는다 —
   정확성 기능이 아니라 보는 기능이다
3. **큐가 차면 버리고 센다.** 조용히 사라지면 몇 건이 안 남았는지 모른다
4. `session()` 안에서 부른 것들이 **한 추적으로 묶인다.** 초안 한 벌이 한 화면이다
5. `contextvars` 는 스레드로 안 넘어간다 — `current()`/`adopt()` 가 그걸 넘긴다
6. `langfuse` 패키지를 **안 쓴다.** 최상단에서 `httpx` 도 안 끌고 온다
"""

from __future__ import annotations

import queue

import pytest

from finnect import trace
from finnect.config import settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN202
    """모듈 전역을 매번 되돌린다. 스레드를 띄우지 않는다."""
    monkeypatch.setattr(trace, "_q", None)
    monkeypatch.setattr(trace, "_worker", None)
    monkeypatch.setattr(trace, "stats", trace.Stats())
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    # 스레드를 안 띄우고 큐만 만든다 — 보내는 것은 여기서 시험 대상이 아니다
    monkeypatch.setattr(trace.threading, "Thread", _가짜스레드)
    yield


class _가짜스레드:
    def __init__(self, **kw) -> None:  # noqa: ANN003
        self.kw = kw

    def start(self) -> None:
        pass


def _record(**kw) -> None:  # noqa: ANN003
    base = dict(
        name="wiki_facts", model="gpt-5.6-luna", system="s", user="u",
        output={"ok": True}, usage={"input_tokens": 10, "output_tokens": 3},
        started_ns=1, ended_ns=2,
    )
    trace.record(**{**base, **kw})


def _spans() -> list[dict]:
    return list(trace._q.queue) if trace._q else []


class Test켜기:
    def test_둘_다_있어야_켜진다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """하나만 있으면 오타일 가능성이 높다."""
        monkeypatch.setattr(settings, "langfuse_secret_key", "")

        assert trace.enabled() is False

    def test_꺼져_있으면_아무것도_안_한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**멈추지 않는다.** 보는 기능이라 없다고 죽으면 안 된다."""
        monkeypatch.setattr(settings, "langfuse_public_key", "")
        _record()

        assert trace._q is None
        assert trace.stats.queued == 0


class Test스팬:
    def test_생성으로_남긴다(self) -> None:
        _record()
        attrs = {a["key"]: a["value"]["stringValue"] for a in _spans()[0]["attributes"]}

        assert attrs["langfuse.observation.type"] == "generation"
        assert attrs["langfuse.observation.model.name"] == "gpt-5.6-luna"

    def test_토큰을_싣는다(self) -> None:
        _record()
        attrs = {a["key"]: a["value"]["stringValue"] for a in _spans()[0]["attributes"]}

        assert '"input": 10' in attrs["langfuse.observation.usage_details"]

    def test_입출력을_싣는다(self) -> None:
        _record(system="너는 판정기다", user="구간 원문")
        attrs = {a["key"]: a["value"]["stringValue"] for a in _spans()[0]["attributes"]}

        assert "너는 판정기다" in attrs["langfuse.observation.input"]
        assert "구간 원문" in attrs["langfuse.observation.input"]

    def test_실패는_상태로_남는다(self) -> None:
        """화면에서 실패한 호출만 걸러 보려고 넣는다."""
        _record(error="LlmError: HTTP 429")

        assert _spans()[0]["status"]["code"] == 2

    def test_성공은_OK_다(self) -> None:
        _record()

        assert _spans()[0]["status"]["code"] == 1

    def test_id_가_매번_다르다(self) -> None:
        _record()
        _record()
        a, b = _spans()

        assert a["spanId"] != b["spanId"]
        assert len(a["traceId"]) == 32 and len(a["spanId"]) == 16


class Test묶기:
    def test_session_안에서_한_추적이다(self) -> None:
        """**초안 한 벌이 한 화면이다.**"""
        with trace.session("draft:c_dasiro:PBLN-000"):
            _record()
            _record()
        a, b = _spans()

        assert a["traceId"] == b["traceId"]

    def test_밖에서는_따로다(self) -> None:
        """구간 판별은 서로 독립이라 이게 맞다."""
        _record()
        _record()
        a, b = _spans()

        assert a["traceId"] != b["traceId"]

    def test_추적_이름을_싣는다(self) -> None:
        with trace.session("draft:c_dasiro"):
            _record()
        attrs = {a["key"]: a["value"]["stringValue"] for a in _spans()[0]["attributes"]}

        assert attrs["langfuse.trace.name"] == "draft:c_dasiro"

    def test_스레드에_물려_줄_수_있다(self) -> None:
        """**`contextvars` 는 스레드로 안 넘어간다.** 안 물려 주면 흩어진다."""
        with trace.session("draft:x"):
            got = trace.current()
            _record()
        trace.adopt(got)
        _record()
        trace.adopt(None)
        a, b = _spans()

        assert a["traceId"] == b["traceId"]


class Test안_막는다:
    def test_큐가_차면_버리고_센다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(trace, "QUEUE_MAX", 2)
        for _ in range(5):
            _record()

        assert trace.stats.queued == 2
        assert trace.stats.dropped == 3
        assert "버림 3" in trace.stats.line()

    def test_전송이_터져도_호출은_산다(self) -> None:
        """**관측이 본 일을 막지 않는다.**"""
        class 터지는httpx:
            class Client:
                def __init__(self, **kw) -> None:  # noqa: ANN003
                    pass

                def __enter__(self):  # noqa: ANN204
                    return self

                def __exit__(self, *a) -> None:  # noqa: ANN002
                    pass

                def post(self, *a, **kw):  # noqa: ANN002, ANN003, ANN202
                    raise OSError("망")

        trace._send(터지는httpx, "http://x", {}, [{"spanId": "a"}])

        assert trace.stats.failed == 1
        assert "OSError" in trace.stats.first_error

    def test_실패를_한_번만_말한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**7,717번 부르는 자리에서 매번 찍으면 진짜 오류가 묻힌다.**"""
        monkeypatch.setattr(trace, "_said", False)
        said: list[str] = []
        monkeypatch.setattr("builtins.print", lambda *a, **k: said.append(" ".join(map(str, a))))

        class 터지는httpx:
            class Client:
                def __init__(self, **kw) -> None:  # noqa: ANN003
                    pass

                def __enter__(self):  # noqa: ANN204
                    return self

                def __exit__(self, *a) -> None:  # noqa: ANN002
                    pass

                def post(self, *a, **kw):  # noqa: ANN002, ANN003, ANN202
                    raise OSError("망")

        for _ in range(3):
            trace._send(터지는httpx, "http://x", {}, [{"spanId": "a"}])

        assert len(said) == 1
        assert trace.stats.failed == 3


def test_최상단에서_langfuse_도_httpx_도_안_끌고_온다() -> None:
    """**로컬은 통과하고 배포본만 죽는** 그 함정이다(CLAUDE.md · ADR-0037 결정 2)."""
    import ast
    import pathlib

    src = pathlib.Path(trace.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in names
    assert "langfuse" not in names


def test_큐가_없으면_flush_가_조용하다() -> None:
    assert trace.flush() == ""


def test_flush_가_보내는_중인_묶음까지_기다린다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**큐가 비었는지로 판단하면 안 된다.**

    펌프가 `get()` 으로 꺼낸 순간 큐는 비지만 그 묶음은 아직 안 갔다.
    실측에서 2건을 불렀는데 1건만 남은 이유가 그것이다.
    """
    _record()
    _record()
    trace._q.get()          # 펌프가 하나 꺼내 간 상태를 만든다
    trace._q.get()

    assert trace._q.empty()          # 큐는 비었다
    assert trace._pending() == 2     # 그런데 둘 다 결말이 안 났다
    assert trace.flush(timeout=0.1) is not None   # 기다렸다가 포기한다

    trace.stats.sent = 2
    assert trace._pending() == 0


def test_queue_full_을_실제로_막는다() -> None:
    """`queue.Full` 을 잡는지 — 위 테스트가 상수를 바꿔 확인한 것의 근거다."""
    assert issubclass(queue.Full, Exception)
