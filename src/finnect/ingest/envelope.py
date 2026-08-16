"""봉투 검증. 방어 코드가 아니라 파싱의 첫 단계다.

**두 API 모두 실패를 HTTP 200 으로 준다.** 2026-08-16 실측:

  기업마당   인증 실패 → HTTP 200 + <reqErr>
  K-Startup  없는 필드로 필터 → HTTP 200 + 봉투 없는 {"code":0,"msg":"정상"}

후자는 `data.get("data") or []` 로 받으면 **0건 성공으로 읽고 조용히 넘어간다.**
그래서 item 수보다 봉투를 먼저 본다.
"""

from __future__ import annotations

from typing import Any

import httpx


class EnvelopeError(RuntimeError):
    """응답 봉투가 기대한 모양이 아니다. 0건이 아니라 실패로 다룬다."""


def _head(resp: httpx.Response, n: int = 300) -> str:
    return resp.text[:n].replace("\n", " ")


def _require_http_200(resp: httpx.Response) -> None:
    if resp.status_code != 200:
        raise EnvelopeError(f"HTTP {resp.status_code}: {_head(resp)}")


def bizinfo_items(resp: httpx.Response) -> list[dict[str, Any]]:
    """기업마당 응답에서 공고 배열을 꺼낸다."""
    _require_http_200(resp)

    # 인증 실패가 HTTP 200 + reqErr 로 온다. JSON 파싱보다 먼저 본다.
    if "reqErr" in resp.text:
        raise EnvelopeError(f"인증 실패로 보인다 (reqErr): {_head(resp)}")

    try:
        data = resp.json()
    except ValueError as e:
        raise EnvelopeError(f"JSON 아님: {_head(resp)}") from e

    if not isinstance(data, dict) or "jsonArray" not in data:
        raise EnvelopeError(f"jsonArray 키가 없다: {_head(resp)}")

    items = data["jsonArray"]
    if not isinstance(items, list):
        raise EnvelopeError(f"jsonArray 가 배열이 아니다: {type(items).__name__}")
    return items


def kstartup_envelope(resp: httpx.Response) -> tuple[list[dict[str, Any]], int]:
    """K-Startup 응답에서 (공고 배열, matchCount) 를 꺼낸다.

    **matchCount 가 필터 결과다.** totalCount 는 필터와 무관하게 29,789 로 고정이라
    페이징 종료 조건으로 쓰면 필터를 걸고도 149 페이지를 돈다.
    """
    _require_http_200(resp)

    try:
        data = resp.json()
    except ValueError as e:
        raise EnvelopeError(f"JSON 아님: {_head(resp)}") from e

    if not isinstance(data, dict):
        raise EnvelopeError(f"객체가 아니다: {_head(resp)}")

    # 봉투 없는 {"code":0,"msg":"정상"} 을 여기서 잡는다. data 키 유무보다 먼저 본다.
    if "matchCount" not in data:
        raise EnvelopeError(f"봉투가 없다 (matchCount 없음): {_head(resp)}")

    items = data.get("data")
    if not isinstance(items, list):
        raise EnvelopeError(f"data 가 배열이 아니다: {_head(resp)}")

    return items, int(data["matchCount"])


def ratelimit_remaining(resp: httpx.Response) -> int | None:
    """K-Startup 은 x-ratelimit-remaining 을 매 응답에 준다. 기업마당은 안 준다."""
    raw = resp.headers.get("x-ratelimit-remaining")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
