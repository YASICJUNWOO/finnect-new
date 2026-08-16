"""기업마당(중소벤처기업부 bizinfo) 어댑터.

실측 2026-08-16: searchCnt=2000 한 번에 전량 1,538건(3.67MB)이 온다.
pageUnit·pageIndex 가 공식 문서에 있으나 쓸 일이 없다.
일 한도는 공식 안내에 명시가 없다.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from finnect.config import settings
from finnect.ingest.base import (
    FetchedPage,
    NormalizedAttachment,
    NormalizedNotice,
    content_hash,
    mask,
    parse_period,
    split_ext,
    split_known,
)
from finnect.ingest.envelope import bizinfo_items, ratelimit_remaining
from finnect.models import AttachmentKind, AttachmentStatus, BizinfoNotice, Source

ENDPOINT = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
SEARCH_CNT = 2000  # 전량 1,538건보다 크게 준다. 페이징이 필요 없다


class BizinfoAdapter:
    source = str(Source.BIZINFO)
    model = BizinfoNotice

    def __init__(
        self, client: httpx.Client, api_key: str | None = None, limit: int | None = None
    ) -> None:
        self.client = client
        self.api_key = api_key if api_key is not None else settings.bizinfo_api_key
        self.limit = limit
        if not self.api_key:
            raise RuntimeError("BIZINFO_API_KEY 가 없다")

    def pages(self) -> Iterator[FetchedPage]:
        # searchCnt 가 그대로 건수 제한이다. 2026-08-16 실측: 10→10건, 100→100건, 500→500건.
        # 잘라 받아도 totCnt 는 1538 로 오므로 전량이 몇 건인지 잃지 않는다.
        count = self.limit if self.limit else SEARCH_CNT
        params = {"crtfcKey": self.api_key, "dataType": "json", "searchCnt": str(count)}
        resp = self.client.get(ENDPOINT, params=params, timeout=settings.request_timeout_sec)
        items = bizinfo_items(resp)  # 인증 실패(HTTP 200 + reqErr)를 여기서 잡는다
        yield FetchedPage(
            request_url=mask(str(resp.url), self.api_key),
            page=None,
            payload=resp.json(),
            items=items,
            byte_size=len(resp.content),
            ratelimit_remaining=ratelimit_remaining(resp),
            total_count=_total_count(items),
        )

    def normalize(self, item: dict[str, Any]) -> NormalizedNotice | None:
        external_id = item.get("pblancId")
        if not external_id:
            return None

        columns, extra = split_known(item, BizinfoNotice.API_FIELDS)
        start, end = parse_period(item.get("reqstBeginEndDe"))

        return NormalizedNotice(
            source=self.source,
            external_id=str(external_id),
            columns=columns,
            extra=extra,
            derived_apply_start=start,
            derived_apply_end=end,
            # 목록 API 가 첨부를 알려준다. 0개인 것도 확인된 0개다(431/1,538).
            attachment_status=str(AttachmentStatus.LISTED),
            attachments=_attachments(item),
            content_hash=content_hash(item),
        )


def _total_count(items: list[dict[str, Any]]) -> int | None:
    """이 출처의 전량 건수. **잘라 받아도 값이 안 변한다.**

    응답 메타인 totCnt 가 item 마다 반복해서 온다. searchCnt=10 으로 10건만 받아도
    totCnt 는 1538 이다(2026-08-16 실측). 그래서 '500건만 받았다'와 '500건뿐이다'가 구분된다.
    """
    if not items:
        return 0
    try:
        return int(items[0].get("totCnt"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _pairs(item: dict[str, Any], name_field: str, url_field: str) -> list[tuple[str, str | None]]:
    """fileNm 과 flpthNm 은 '@' 로 이어붙인 병렬 배열이다.

    길이가 어긋날 수 있으므로 URL 이 모자라면 None 으로 두되 파일명은 버리지 않는다.
    """
    names = [n.strip() for n in (item.get(name_field) or "").split("@") if n.strip()]
    urls = [u.strip() for u in (item.get(url_field) or "").split("@") if u.strip()]
    return [(n, urls[i] if i < len(urls) else None) for i, n in enumerate(names)]


def _attachments(item: dict[str, Any]) -> list[NormalizedAttachment]:
    out: list[NormalizedAttachment] = []
    for kind, name_field, url_field in (
        (AttachmentKind.NOTICE_DOC, "printFileNm", "printFlpthNm"),
        (AttachmentKind.OTHER, "fileNm", "flpthNm"),
    ):
        for name, url in _pairs(item, name_field, url_field):
            out.append(
                NormalizedAttachment(
                    position=len(out),
                    kind=str(kind),
                    filename=name,
                    ext=split_ext(name),
                    url=url,
                )
            )
    return out
