"""어댑터 공통 — 두 출처의 응답 형태가 완전히 다르므로 공통 인터페이스 뒤에 둔다."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class FetchedPage:
    """응답 한 건. 그대로 raw_fetch 로 간다."""

    request_url: str  # 인증키 마스킹된 것
    page: int | None
    payload: dict[str, Any]
    items: list[dict[str, Any]]
    byte_size: int
    ratelimit_remaining: int | None = None
    # 이 출처가 이번 실행에서 줄 총 건수. 진행률 표시에만 쓴다.
    # K-Startup 은 matchCount, 기업마당은 한 번에 전량이라 받은 수 자체다.
    total_count: int | None = None


@dataclass(slots=True)
class NormalizedAttachment:
    position: int
    kind: str
    filename: str
    ext: str | None
    url: str | None


@dataclass(slots=True)
class NormalizedNotice:
    """출처 테이블 한 행.

    columns 는 **API 필드명 그대로**다. 모델 컬럼에 그대로 대입된다.
    extra 는 API_FIELDS 에 없던 필드다. 조용히 버리지 않는다.
    """

    source: str
    external_id: str
    columns: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)
    derived_apply_start: dt.date | None = None
    derived_apply_end: dt.date | None = None
    attachment_status: str = "unknown"
    attachments: list[NormalizedAttachment] = field(default_factory=list)
    content_hash: str = ""


class Adapter(Protocol):
    source: str

    def pages(self) -> Iterator[FetchedPage]:
        """출처를 순회하며 응답을 낸다. 봉투 검증은 어댑터 안에서 끝낸다."""
        ...

    def normalize(self, item: dict[str, Any]) -> NormalizedNotice | None:
        """원문 item 하나를 행으로 만든다. 키가 없으면 None."""
        ...

    def keep(self, item: dict[str, Any]) -> bool:
        """이 item 을 적재하나. **`normalize` 가 None 을 내는 것과 다른 사건이다.**

        저기는 사고(외부 ID 가 없다)이고 여기는 정책(우리가 안 받기로 했다)이다.
        한 숫자로 세면 `skipped` 가 늘었을 때 API 가 깨진 건지 우리가 거른 건지
        구분이 안 된다.
        """
        ...


def content_hash(item: dict[str, Any]) -> str:
    """원문 item 의 해시.

    K-Startup 은 수정일시 필드가 없다. 변경 감지 수단이 이것뿐이다.
    기업마당은 updtPnttm 이 있지만 두 출처를 같은 방식으로 다룬다.
    """
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def split_known(item: dict[str, Any], api_fields: frozenset[str]) -> tuple[dict, dict]:
    """(아는 필드, 처음 보는 필드) 로 가른다. 뒤엣것은 extra 로 간다."""
    known = {k: as_text(v) for k, v in item.items() if k in api_fields}
    unknown = {k: v for k, v in item.items() if k not in api_fields}
    return known, unknown


def as_text(value: Any) -> str | None:
    """컬럼이 전부 TEXT 다. API 가 int 로 주는 필드(id, pbanc_sn, totCnt)를 맞춰준다.

    값을 해석하지 않는다. HTML 엔티티도 풀지 않는다. 원문 그대로다.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def mask(url: str, *secrets: str) -> str:
    """인증키는 쿼리스트링으로 나간다. 로그와 DB 에 남기지 않는다."""
    for s in secrets:
        if s:
            url = url.replace(s, "***")
    return url


def parse_yyyymmdd(value: Any) -> dt.date | None:
    """'20260827' → date. K-Startup 표본 4,000건은 전부 8자리였다."""
    s = (str(value) if value is not None else "").strip()
    if not re.fullmatch(r"\d{8}", s):
        return None
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


_PERIOD = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*~\s*(\d{4})-(\d{2})-(\d{2})")


def parse_period(value: Any) -> tuple[dt.date | None, dt.date | None]:
    """'2026-08-14 ~ 2026-08-28' → (date, date).

    **기업마당 1,538건 중 날짜 형식은 662건(43%)뿐이다.** 나머지는
    '예산 소진시까지'(597) · '상시 접수'(123) · '선착순 접수'(43) · '모집 완료시'(29) ·
    '세부사업별 상이'(28) 같은 서술이다. 날짜가 없는 것이 정상 상태이므로
    파싱 실패를 오류로 다루지 않는다. 원문은 reqstBeginEndDe 컬럼에 그대로 남는다.
    """
    s = (str(value) if value is not None else "").strip()
    m = _PERIOD.search(s)
    if not m:
        return None, None
    a, b, c, d, e, f = (int(x) for x in m.groups())
    try:
        return dt.date(a, b, c), dt.date(d, e, f)
    except ValueError:
        return None, None


def split_ext(filename: str) -> str | None:
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext if re.fullmatch(r"[a-z0-9]{1,10}", ext) else None
