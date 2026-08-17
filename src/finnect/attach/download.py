"""첨부 내려받기.

**두 가지가 이 파일의 이유다.**

1. `HEAD` 가 403 이고 `GET` 만 200 이다. 브라우저 UA 와 Referer 가 필요하다.
   크기를 미리 못 재므로 스트리밍으로 받으면서 한도를 넘으면 끊는다.
2. **기업마당은 오류를 HTTP 200 + HTML 로 준다.** 목록 API 가 실패를 200 으로 주는 것과
   같은 함정이다. 안 거르면 3KB 짜리 오류 페이지가 hwp 로 저장돼 '파서 실패'로 둔갑한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

import httpx

from finnect.config import settings
from finnect.models import FetchStatus

# 그냥 UA 로는 403 이다. 상대가 브라우저를 기대한다.
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REFERER = {"bizinfo": "https://www.bizinfo.go.kr/"}

#: 파일이 아니라 오류 페이지가 왔다는 신호.
HTML_HEAD = (b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML", b"<?xml")


@dataclass(slots=True)
class Fetched:
    status: FetchStatus
    http_status: int | None = None
    data: bytes | None = None
    content_type: str | None = None
    filename: str | None = None
    error: str | None = None


def headers_for(source: str) -> dict[str, str]:
    h = {"User-Agent": UA, "Accept": "*/*"}
    ref = REFERER.get(source)
    if ref:
        h["Referer"] = ref
    return h


def filename_of(disposition: str | None) -> str | None:
    """Content-Disposition 에서 파일명. URL 에는 파일명이 없다.

    기업마당은 `filename=` 에 퍼센트 인코딩된 한글을 그대로 넣는다. RFC 5987 형식도 받는다.
    """
    if not disposition:
        return None
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", disposition)
    if m is None:
        m = re.search(r'filename\s*=\s*"?([^";]+)"?', disposition)
    if m is None:
        return None
    return unquote(m.group(1)).strip() or None


def fetch(client: httpx.Client, url: str, source: str) -> Fetched:
    limit = settings.attachment_max_mb * 1024 * 1024
    try:
        with client.stream(
            "GET", url, headers=headers_for(source), timeout=settings.request_timeout_sec
        ) as r:
            if r.status_code >= 400:
                return Fetched(FetchStatus.NOT_FOUND, r.status_code)

            chunks: list[bytes] = []
            size = 0
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > limit:
                    r.close()
                    return Fetched(
                        FetchStatus.TOO_LARGE,
                        r.status_code,
                        error=f"{settings.attachment_max_mb}MB 초과",
                    )
                chunks.append(chunk)

            data = b"".join(chunks)
            ctype = r.headers.get("content-type")
            name = filename_of(r.headers.get("content-disposition"))

            if is_html(data, ctype):
                # 200 이지만 파일이 아니다. 저장하지 않는다.
                return Fetched(FetchStatus.NOT_HTML, r.status_code, content_type=ctype)

            return Fetched(FetchStatus.OK, r.status_code, data, ctype, name)
    except httpx.HTTPError as e:
        return Fetched(FetchStatus.FAILED, error=f"{type(e).__name__}: {e}")


def is_html(data: bytes, content_type: str | None) -> bool:
    """받은 것이 파일이 아니라 오류 페이지인가."""
    if not data:
        return True
    head = data.lstrip()[:64]
    if any(head.startswith(sig) for sig in HTML_HEAD):
        return True
    # content-type 만으로는 못 믿는다. 기업마당은 정상 파일에도 x-download 를 준다.
    return bool(content_type and content_type.startswith("text/html"))
