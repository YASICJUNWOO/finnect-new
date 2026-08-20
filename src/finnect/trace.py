"""LLM 호출을 Langfuse 로 보낸다 — **OTLP/HTTP 엔드포인트 하나만 부른다.**

결정은 [ADR-0038](
../../docs/adr/0038-llm-호출을-langfuse-로-남기고-sdk-대신-otlp-엔드포인트를-부른다.md) 이다.

## `langfuse` 패키지를 안 쓴다

[ADR-0037](../../docs/adr/0037-llm-제공자를-openai-로-정하고-gpt-5-6-luna-부터-잰다.md)
결정 2 와 같은 이유다. `requirements.txt` 가 읽기 API 에 필요한 다섯만 싣는데, 새
패키지를 `pyproject` 에 넣으면 누군가 `api/` 에서 임포트했을 때 **로컬은 통과하고
배포본만 죽는다.** 우리가 쓰는 것은 `POST /api/public/otel/v1/traces` 하나뿐이라
SDK 가 주는 값이 작다.

## 관측이 본 일을 막지 않는다

**추적은 절대 호출을 막지 않는다.** 큐에 넣고 즉시 돌아오고, 뒤에서 스레드가 묶어
보낸다. 큐가 차면 버리고 센다. 전송이 실패하면 **한 번만** 말한다 — 7,717번
부르는 자리에서 매번 찍으면 진짜 오류가 묻힌다.

키가 없으면 그냥 꺼진다. 이건 정확성 기능이 아니라 **보는 기능**이라, 없다고 멈추면
안 된다 — `wiki_extractor` 가 키 없이 멈추는 것과 성질이 다르다.

## 켜기

    LANGFUSE_PUBLIC_KEY=pk-lf-…
    LANGFUSE_SECRET_KEY=sk-lf-…
    LANGFUSE_BASE_URL=https://cloud.langfuse.com   # 기본값. 자체 호스팅이면 바꾼다
"""

from __future__ import annotations

import atexit
import base64
import contextvars
import json
import os
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from finnect.config import settings

#: OTLP/HTTP 경로. Langfuse 가 이 하나로 받는다
PATH = "/api/public/otel/v1/traces"
#: 실시간 적재를 요구하는 헤더. 없으면 배치 처리로 들어가 화면에 늦게 뜬다
INGESTION_VERSION = "4"

#: 한 번에 묶어 보낼 최대 스팬 수
BATCH = 32
#: 이 시간이 지나면 덜 찼어도 보낸다 (초)
LINGER = 2.0
#: 큐 상한. 넘치면 **버리고 센다** — 호출을 막지 않는다
QUEUE_MAX = 2_000

#: 지금 묶고 있는 추적. `session()` 이 정한다
_trace: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "finnect_trace", default=None
)


@dataclass(slots=True)
class Stats:
    """보낸 것과 못 보낸 것. **조용히 사라지지 않게 센다.**"""

    queued: int = 0
    sent: int = 0
    dropped: int = 0
    failed: int = 0
    first_error: str = ""

    def line(self) -> str:
        out = f"추적 {self.sent:,}건 보냄"
        if self.dropped:
            out += f" · 큐가 차서 버림 {self.dropped:,}"
        if self.failed:
            out += f" · 전송 실패 {self.failed:,} ({self.first_error})"
        return out


stats = Stats()
_q: queue.Queue[dict] | None = None
_worker: threading.Thread | None = None
_lock = threading.Lock()
_said = False
#: `flush()` 가 켠다. 켜져 있으면 펌프가 **덜 찼어도 기다리지 않고 보낸다**
_draining = threading.Event()


def enabled() -> bool:
    """둘 다 있어야 켜진다. 하나만 있으면 오타일 가능성이 높다."""
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


@contextmanager
def session(name: str):  # noqa: ANN201
    """이 안에서 부른 것들을 **한 추적으로 묶는다.**

        with trace.session("draft:c_dasiro:PBLN-000"):
            ...                      # 항목 67개가 한 화면에 뜬다

    안 감싸면 호출마다 따로 뜬다. `--classify` 는 구간이 서로 독립이라 그게 맞고,
    초안은 한 벌이 한 추적이어야 읽을 수 있다.
    """
    token = _trace.set((os.urandom(16).hex(), name))
    try:
        yield
    finally:
        _trace.reset(token)


def current() -> tuple[str, str] | None:
    """지금 추적. **스레드에 물려 줄 때 쓴다** — `contextvars` 는 스레드로 안 넘어간다."""
    return _trace.get()


def adopt(trace: tuple[str, str] | None) -> None:
    """`current()` 로 받은 것을 이 스레드에서 이어받는다."""
    _trace.set(trace)


def record(  # noqa: PLR0913
    *,
    name: str,
    model: str,
    system: str,
    user: str,
    output: object,
    usage: dict,
    started_ns: int,
    ended_ns: int,
    error: str | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    """생성 하나를 남긴다. **즉시 돌아온다.**"""
    if not enabled():
        return
    trace = _trace.get()
    trace_id, trace_name = trace if trace else (os.urandom(16).hex(), name)

    attrs: list[dict] = [
        _s("langfuse.observation.type", "generation"),
        _s("langfuse.observation.model.name", model),
        _s("langfuse.observation.input", json.dumps(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            ensure_ascii=False,
        )),
        _s("langfuse.observation.output", json.dumps(output, ensure_ascii=False)),
        _s("langfuse.observation.usage_details", json.dumps({
            "input": int(usage.get("input_tokens") or 0),
            "output": int(usage.get("output_tokens") or 0),
        })),
        _s("langfuse.trace.name", trace_name),
    ]
    for k, v in (metadata or {}).items():
        attrs.append(_s(f"langfuse.observation.metadata.{k}", v))
    if error:
        attrs.append(_s("langfuse.observation.metadata.error", error))

    _put({
        "traceId": trace_id,
        "spanId": os.urandom(8).hex(),
        "name": name,
        "kind": 1,
        "startTimeUnixNano": str(started_ns),
        "endTimeUnixNano": str(ended_ns),
        "attributes": attrs,
        # 2 = ERROR · 1 = OK. 화면에서 실패한 호출만 걸러 보려고 넣는다
        "status": {"code": 2, "message": error[:200]} if error else {"code": 1},
    })


def flush(timeout: float = 10.0) -> str:
    """남은 것을 다 보낸다. **CLI 가 끝나기 전에 부른다.**

    데몬 스레드라 프로세스가 그냥 끝나면 남은 것이 사라진다.

    **큐가 비었는지로 판단하면 안 된다.** 펌프가 `get()` 으로 꺼낸 순간 큐는 비지만
    그 묶음은 아직 안 갔다. 실측에서 2건을 불렀는데 1건만 남은 이유가 그것이다 —
    센 것으로 판단한다.
    """
    if _q is None:
        return ""
    _draining.set()  # 펌프가 linger 를 건너뛴다
    deadline = time.monotonic() + timeout
    while _pending() > 0 and time.monotonic() < deadline:
        time.sleep(0.02)
    _draining.clear()
    return stats.line()


def _pending() -> int:
    """아직 결말이 안 난 스팬 수. `dropped` 는 큐에 든 적이 없어 여기 없다."""
    return stats.queued - stats.sent - stats.failed


def _s(key: str, value: str) -> dict:
    return {"key": key, "value": {"stringValue": value}}


def _put(span: dict) -> None:
    global _q, _worker
    with _lock:
        if _q is None:
            _q = queue.Queue(maxsize=QUEUE_MAX)
            _worker = threading.Thread(target=_pump, name="langfuse", daemon=True)
            _worker.start()
            atexit.register(flush)
    try:
        _q.put_nowait(span)
        stats.queued += 1
    except queue.Full:
        # **버리고 센다.** 호출을 막지 않는다
        stats.dropped += 1


def _pump() -> None:
    """묶어서 보낸다. `httpx` 는 여기서만 임포트한다."""
    import httpx

    assert _q is not None
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    url = settings.langfuse_base_url.rstrip("/") + PATH
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "x-langfuse-ingestion-version": INGESTION_VERSION,
    }

    while True:
        batch = [_q.get()]
        deadline = time.monotonic() + LINGER
        while len(batch) < BATCH and not _draining.is_set():
            left = deadline - time.monotonic()
            if left <= 0:
                break
            try:
                batch.append(_q.get(timeout=left))
            except queue.Empty:
                break
        # 비우는 중이면 큐에 있는 것을 남기지 않고 다 쓸어 담는다
        while _draining.is_set() and len(batch) < BATCH:
            try:
                batch.append(_q.get_nowait())
            except queue.Empty:
                break
        _send(httpx, url, headers, batch)


def _send(httpx, url: str, headers: dict, batch: list[dict]) -> None:  # noqa: ANN001
    global _said
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [_s("service.name", "finnect")]},
            "scopeSpans": [{"scope": {"name": "finnect"}, "spans": batch}],
        }]
    }
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        stats.sent += len(batch)
    except Exception as e:  # noqa: BLE001 — **추적이 본 일을 막지 않는다**
        stats.failed += len(batch)
        if not _said:
            _said = True
            stats.first_error = f"{type(e).__name__}: {e}"[:200]
            print(f"[추적] Langfuse 로 못 보냈어요 — {stats.first_error}")
