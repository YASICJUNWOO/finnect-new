"""LLM 클라이언트 — OpenAI Responses API 하나만 부른다 (ADR-0037).

**`openai` 패키지를 안 쓴다.** 이미 의존성인 `httpx` 로 `POST /v1/responses` 하나만
부른다. 패키지를 안 넣는 이유가 배포다 — `requirements.txt` 가 읽기 API 에 필요한
다섯만 싣는데, `openai` 를 `pyproject` 에 넣으면 누군가 `api/` 에서 임포트했을 때
**로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정).

**키가 없으면 조용히 물러나지 않는다.** 무엇이 없는지 말하고 멈춘다 — 물러나면
처리하지 못한 것이 "아무것도 안 나온 것" 처럼 보인다(ADR-0031 이 `UnknownFile` 로
막은 상황과 같다).

    from finnect import llm
    c = llm.client()                       # 키가 없으면 MissingKey
    out = c.json(system="…", user="…", schema={…}, schema_name="facts")
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from finnect import trace
from finnect.config import settings

ENDPOINT = "https://api.openai.com/v1/responses"


class MissingKey(RuntimeError):
    """키가 없다. **스텁으로 물러나지 않는다.**"""


class LlmError(RuntimeError):
    """호출이 실패했다."""


class _Retryable(LlmError):
    """다시 걸면 달라질 수 있는 실패. **429 와 5xx 뿐이다.**

    401(키가 틀렸다) · 400(요청이 틀렸다) 은 다시 걸어도 같다. 나눠 두지 않으면
    키 오타 하나에 3번씩 나가고 백오프로 7초를 기다린다.
    """


@dataclass(slots=True)
class Usage:
    """토큰 집계. **비용을 말할 때 지어내지 않으려고 센다.**"""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, body: dict) -> None:
        u = body.get("usage") or {}
        self.calls += 1
        self.input_tokens += int(u.get("input_tokens") or 0)
        self.output_tokens += int(u.get("output_tokens") or 0)

    def cost_usd(self, in_per_m: float = 0.20, out_per_m: float = 1.20) -> float:
        """기본값은 `gpt-5.6-luna` 단가다(ADR-0037). 모델을 바꾸면 같이 넘긴다."""
        return (self.input_tokens * in_per_m + self.output_tokens * out_per_m) / 1_000_000

    def merge(self, other: Usage) -> None:
        """다른 집계를 흡수한다. **스레드마다 따로 세고 마지막에 합치는 자리**
        가 있어서(plan/16 T-0069) 여기서 더한다 — lock 은 부르는 쪽이 없앤다."""
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens

    def reset(self) -> None:
        self.calls = self.input_tokens = self.output_tokens = 0

    def line(self) -> str:
        return (
            f"호출 {self.calls:,}회 · 입력 {self.input_tokens:,} · "
            f"출력 {self.output_tokens:,} 토큰 · 약 ${self.cost_usd():.2f}"
        )


@dataclass(slots=True)
class Client:
    """Responses API 한 곳만 부른다. **세션을 안 들고 있다** — 호출마다 연다."""

    api_key: str
    model: str
    timeout: float = 120.0
    retries: int = 3
    usage: Usage = field(default_factory=Usage)
    #: 마지막 호출의 토큰. **추적에 실을 값이라 집계와 따로 든다** — `Usage` 는
    #: 누적이고 추적은 호출 하나짜리다
    _last_usage: dict = field(default_factory=dict)

    def json(self, *, system: str, user: str, schema: dict, schema_name: str) -> dict:
        """구조화 출력을 받아 dict 로 돌려준다.

        `strict: true` 라 스키마를 벗어난 응답이 안 온다. **그래도 파싱을 감싼다** —
        거절(refusal)이나 길이 초과로 본문이 비는 경우가 있다.

        **호출 하나가 추적 하나다**(`trace.py`). 여기가 LLM 을 부르는 유일한 자리라
        모든 호출이 자동으로 남는다 — 부르는 쪽이 뭘 안 해도 된다. 추적은 절대
        이 함수를 막지 않는다: 실패해도 결과는 그대로 나간다.
        """
        started = time.time_ns()
        try:
            out = self._json(system=system, user=user, schema=schema, schema_name=schema_name)
        except Exception as e:
            trace.record(
                name=schema_name, model=self.model, system=system, user=user,
                output=None, usage={}, started_ns=started, ended_ns=time.time_ns(),
                error=f"{type(e).__name__}: {e}",
            )
            raise
        trace.record(
            name=schema_name, model=self.model, system=system, user=user,
            output=out, usage=self._last_usage, started_ns=started, ended_ns=time.time_ns(),
        )
        return out

    def _json(self, *, system: str, user: str, schema: dict, schema_name: str) -> dict:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        body = self._post(payload)
        self.usage.add(body)
        self._last_usage = body.get("usage") or {}
        return _parse(body)

    def _post(self, payload: dict) -> dict:
        """**`httpx` 를 여기서 임포트한다.** 최상단에 두면 `Usage` 하나 쓰려고 이
        모듈을 읽은 곳이 전부 httpx 를 끌고 온다 — `requirements.txt` 가 그것을
        뺐으니 **로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정).
        """
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as c:
                    r = c.post(ENDPOINT, headers=headers, json=payload)
                # 4xx 는 우리 잘못이라 다시 걸어도 같다. **429 만 예외다.**
                if r.status_code == 429 or r.status_code >= 500:
                    raise _Retryable(f"HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code >= 400:
                    raise LlmError(f"HTTP {r.status_code}: {r.text[:400]}")
                return r.json()
            except (httpx.HTTPError, _Retryable) as e:
                last = e
                if attempt == self.retries:
                    break
                _sleep(attempt)
        raise LlmError(f"{self.retries}번 시도하고 실패했어요 — {last}")


def _sleep(attempt: int) -> None:
    """지수 백오프. 1 · 2 · 4초. **테스트가 갈아끼울 수 있게 함수로 뺐다.**"""
    import time

    time.sleep(2 ** (attempt - 1))


def _parse(body: dict) -> dict:
    """`output[].content[].output_text` 에서 JSON 을 꺼낸다."""
    for item in body.get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                raise LlmError(f"모델이 거절했어요 — {part.get('refusal')!r}")
            if part.get("type") == "output_text":
                try:
                    return json.loads(part["text"])
                except json.JSONDecodeError as e:
                    raise LlmError(f"JSON 이 아니에요 — {part['text'][:200]!r}") from e
    raise LlmError(f"본문이 비었어요 — status={body.get('status')!r}")


def client(model: str | None = None) -> Client:
    """설정에서 키와 모델을 읽어 만든다. **키가 없으면 여기서 멈춘다.**"""
    if not settings.openai_api_key:
        raise MissingKey(
            "OPENAI_API_KEY 가 없어요. `.env` 에 넣거나 환경변수로 주세요 "
            "— ADR-0037. 키 없이 돌리려면 WIKI_EXTRACTOR=stub 이에요"
        )
    return Client(
        api_key=settings.openai_api_key,
        model=model or settings.openai_model,
        timeout=settings.openai_timeout_sec,
    )
