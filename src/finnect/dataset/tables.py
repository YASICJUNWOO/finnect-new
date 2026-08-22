"""이 모듈이 다루는 표와, 행을 JSON 으로 오가게 하는 변환.

**공고와 첨부까지다.** `document`·`draft`·`wiki_*` 는 안 건드린다 —
`document` 는 콘텐츠 주소(`sha256`)라 같은 첨부를 다시 받으면 같은 행이 서고,
위키는 사용자 파일에서 나온 것이라 공고 코퍼스와 무관하다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Date, DateTime
from sqlalchemy import inspect as sa_inspect

from finnect.models import (
    Attachment,
    AttachmentFile,
    BizinfoNotice,
    KstartupNotice,
    NoticeFit,
    NoticeProfile,
)

__all__ = ["DUMPED", "NOTICE_TABLES", "PURGED", "row_to_json", "json_to_kwargs"]

#: 출처 이름 → (모델, PK 속성). PK 이름이 출처마다 다르다 — 두 API 가
#: 필드 이름을 하나도 공유하지 않는 것의 연장이다(교집합 0).
NOTICE_TABLES: dict[str, tuple[type, str]] = {
    "bizinfo": (BizinfoNotice, "pblancId"),
    "kstartup": (KstartupNotice, "pbanc_sn"),
}

#: 백업에 담는 표. 되돌릴 때 이 순서로 넣는다.
DUMPED: tuple[type, ...] = (BizinfoNotice, KstartupNotice, Attachment, AttachmentFile)

#: 초기화가 비우는 표. `attachment_file` 이 여기 있는 이유는 원본 파일을 같이
#: 지우기 때문이다 — 행만 남으면 `stored_path` 가 없는 파일을 가리킨다.
PURGED: tuple[type, ...] = (
    NoticeFit,
    NoticeProfile,
    AttachmentFile,
    Attachment,
    BizinfoNotice,
    KstartupNotice,
)


def _columns(model: type) -> dict[str, Any]:
    return {c.key: c for c in sa_inspect(model).mapper.column_attrs}


def row_to_json(row: object) -> dict[str, Any]:
    """행 하나를 JSON 으로. 날짜·시각만 문자열로 바꾸고 나머지는 그대로 둔다."""
    out: dict[str, Any] = {}
    for key in _columns(type(row)):
        v = getattr(row, key)
        out[key] = v.isoformat() if isinstance(v, dt.date | dt.datetime) else v
    return out


def json_to_kwargs(model: type, data: dict[str, Any]) -> dict[str, Any]:
    """JSON 하나를 생성자 인자로. **모르는 키는 버린다.**

    백업을 뜬 뒤 컬럼이 늘거나 줄 수 있다. 모르는 키에서 터지면 옛 백업이
    통째로 못 쓰게 되므로, 버리고 건수를 세는 쪽이 낫다(`ingest` 의 `extra` 와 같은 자세).
    """
    cols = _columns(model)
    kwargs: dict[str, Any] = {}
    for key, v in data.items():
        col = cols.get(key)
        if col is None or v is None:
            if col is not None:
                kwargs[key] = None
            continue
        kwargs[key] = _coerce(col.expression.type, v)
    return kwargs


def _coerce(col_type: Any, v: Any) -> Any:
    # DateTime 이 Date 의 하위형이 아니라 형제다. 순서에 의존하지 않는다.
    if isinstance(col_type, DateTime) and isinstance(v, str):
        return dt.datetime.fromisoformat(v)
    if isinstance(col_type, Date) and isinstance(v, str):
        return dt.date.fromisoformat(v)
    return v
