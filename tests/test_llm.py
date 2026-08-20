"""LLM 클라이언트 — 네트워크 없이 (ADR-0037).

**`openai` 패키지를 안 쓰기로 한 결정이 여기 걸려 있다.** SDK 가 해 주던 것을
우리가 하므로, 재시도와 응답 파싱을 우리가 검증해야 한다.
"""

from __future__ import annotations

import httpx
import pytest

from finnect import llm


def _resp(text: str) -> dict:
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 100, "output_tokens": 20}}


class 가짜Transport(httpx.BaseTransport):
    def __init__(self, *responses: tuple[int, dict | str]) -> None:
        self._q = list(responses)
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        code, body = self._q.pop(0) if len(self._q) > 1 else self._q[0]
        if isinstance(body, str):
            return httpx.Response(code, text=body, request=request)
        return httpx.Response(code, json=body, request=request)


@pytest.fixture(autouse=True)
def _잠들지_않는다(monkeypatch):  # noqa: ANN001, ANN201
    """백오프가 테스트를 7초 잡아먹지 않게 한다."""
    monkeypatch.setattr(llm, "_sleep", lambda attempt: None)


#: **원본을 모듈 로드 때 잡아 둔다.** monkeypatch 한 뒤에 `httpx.Client` 를 부르면
#: 패치가 자기 자신을 불러 무한 재귀가 된다.
_REAL_CLIENT = httpx.Client


def _붙인다(monkeypatch, transport: httpx.BaseTransport) -> None:  # noqa: ANN001
    monkeypatch.setattr(httpx, "Client",
                        lambda **kw: _REAL_CLIENT(transport=transport, **kw))


def test_구조화_출력을_파싱한다(monkeypatch) -> None:  # noqa: ANN001
    t = 가짜Transport((200, _resp('{"facts": [{"text": "x"}]}')))
    _붙인다(monkeypatch, t)
    c = llm.Client(api_key="sk-test", model="gpt-5.6-luna")
    assert c.json(system="s", user="u", schema={}, schema_name="n") == {"facts": [{"text": "x"}]}


def test_토큰을_센다(monkeypatch) -> None:  # noqa: ANN001
    t = 가짜Transport((200, _resp("{}")))
    _붙인다(monkeypatch, t)
    c = llm.Client(api_key="sk-test", model="gpt-5.6-luna")
    c.json(system="s", user="u", schema={}, schema_name="n")
    assert (c.usage.calls, c.usage.input_tokens, c.usage.output_tokens) == (1, 100, 20)
    assert "$" in c.usage.line()


def test_429_는_다시_건다(monkeypatch) -> None:  # noqa: ANN001
    """레이트 리밋은 우리 잘못이 아니라 타이밍이다."""
    t = 가짜Transport((429, "rate limited"), (200, _resp("{}")))
    _붙인다(monkeypatch, t)
    c = llm.Client(api_key="sk-test", model="gpt-5.6-luna")
    c.json(system="s", user="u", schema={}, schema_name="n")
    assert t.calls == 2


def test_5xx_도_다시_건다(monkeypatch) -> None:  # noqa: ANN001
    t = 가짜Transport((503, "down"), (200, _resp("{}")))
    _붙인다(monkeypatch, t)
    llm.Client(api_key="sk-test", model="gpt-5.6-luna").json(
        system="s", user="u", schema={}, schema_name="n")
    assert t.calls == 2


def test_끝내_실패하면_몇_번_했는지_말한다(monkeypatch) -> None:  # noqa: ANN001
    t = 가짜Transport((503, "down"))
    _붙인다(monkeypatch, t)
    c = llm.Client(api_key="sk-test", model="gpt-5.6-luna", retries=3)
    with pytest.raises(llm.LlmError, match="3번"):
        c.json(system="s", user="u", schema={}, schema_name="n")
    assert t.calls == 3


def test_거절을_빈_결과로_안_넘긴다() -> None:
    """**조용히 비면 '아무것도 안 나온 것' 처럼 보인다.**"""
    body = {"output": [{"type": "message",
                        "content": [{"type": "refusal", "refusal": "안 할래요"}]}]}
    with pytest.raises(llm.LlmError, match="거절"):
        llm._parse(body)


def test_JSON_이_아니면_말한다() -> None:
    with pytest.raises(llm.LlmError, match="JSON"):
        llm._parse(_resp("이건 JSON 이 아니다"))


def test_본문이_비면_말한다() -> None:
    with pytest.raises(llm.LlmError, match="비었"):
        llm._parse({"output": [], "status": "incomplete"})


def test_요청이_문서가_정한_모양이다(monkeypatch) -> None:  # noqa: ANN001
    """`POST /v1/responses` · `text.format.type = json_schema` · `strict: true`."""
    보낸것: dict = {}

    class 잡는Transport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            import json as _j
            보낸것.update(url=str(request.url), body=_j.loads(request.content),
                        auth=request.headers.get("Authorization"))
            return httpx.Response(200, json=_resp("{}"), request=request)

    _붙인다(monkeypatch, 잡는Transport())
    llm.Client(api_key="sk-test", model="gpt-5.6-luna").json(
        system="시스템", user="사용자", schema={"type": "object"}, schema_name="wiki_facts")

    assert 보낸것["url"] == "https://api.openai.com/v1/responses"
    assert 보낸것["auth"] == "Bearer sk-test"
    b = 보낸것["body"]
    assert b["model"] == "gpt-5.6-luna"
    assert [m["role"] for m in b["input"]] == ["system", "user"]
    fmt = b["text"]["format"]
    assert (fmt["type"], fmt["name"], fmt["strict"]) == ("json_schema", "wiki_facts", True)


def test_401_은_다시_안_건다(monkeypatch) -> None:  # noqa: ANN001
    """**키가 틀린 것은 다시 걸어도 같다.** 나눠 두지 않으면 오타 하나에 3번 나간다."""
    t = 가짜Transport((401, "Incorrect API key provided"))
    _붙인다(monkeypatch, t)
    c = llm.Client(api_key="sk-bad", model="gpt-5.6-luna", retries=3)
    with pytest.raises(llm.LlmError, match="401"):
        c.json(system="s", user="u", schema={}, schema_name="n")
    assert t.calls == 1


def test_400_도_다시_안_건다(monkeypatch) -> None:  # noqa: ANN001
    """요청이 틀린 것도 마찬가지다. 스키마를 고쳐야지 다시 걸 일이 아니다."""
    t = 가짜Transport((400, "invalid schema"))
    _붙인다(monkeypatch, t)
    with pytest.raises(llm.LlmError, match="400"):
        llm.Client(api_key="sk-test", model="gpt-5.6-luna").json(
            system="s", user="u", schema={}, schema_name="n")
    assert t.calls == 1
