"""K-Startup(창업진흥원) 어댑터 — data.go.kr B552735/kisedKstartupService01.

실측 2026-08-16:
  전량 29,789건. perPage=200 → 149회. 일 한도 10,000회.
  상세 API 가 없다. 목록 API 하나뿐이라 첨부는 detl_pg_url 스크래핑밖에 방법이 없다(plan/02).
  수정일시 필드가 없다. 변경 감지는 콘텐츠 해시뿐이다.

**서버측 날짜 필터를 쓰지 않는다.** cond[...::GTE] 계열이 조건을 위반하는 레코드를 섞어 준다.
전량이 149회라 일 한도의 1.5%다. 아낄 이유가 없는데 아끼면 조용히 틀린 모집단을 얻는다.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from finnect.config import settings
from finnect.ingest.base import (
    FetchedPage,
    NormalizedNotice,
    content_hash,
    mask,
    parse_yyyymmdd,
    split_known,
)
from finnect.ingest.envelope import kstartup_envelope, ratelimit_remaining
from finnect.models import AttachmentStatus, KstartupNotice, Source

ENDPOINT = (
    "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
)
PER_PAGE = 200
MAX_PAGES = 400  # 29,789/200 = 149. 폭주 방지용 상한이지 기대값이 아니다


class KstartupAdapter:
    source = str(Source.KSTARTUP)
    model = KstartupNotice

    def __init__(
        self, client: httpx.Client, api_key: str | None = None, only_open: bool = False
    ) -> None:
        self.client = client
        self.api_key = api_key if api_key is not None else settings.data_go_kr_api_key
        self.only_open = only_open
        if not self.api_key:
            raise RuntimeError("DATA_GO_KR_API_KEY 가 없다")

    def pages(self) -> Iterator[FetchedPage]:
        for page in range(1, MAX_PAGES + 1):
            params: dict[str, Any] = {
                "serviceKey": self.api_key,
                "page": page,
                "perPage": PER_PAGE,
                "returnType": "json",
            }
            if self.only_open:
                # 검증된 필터. rcrt_prgs_yn=Y → 274건, ZZZZ → 0건.
                # 모집단 확정이 아니라 작업 큐 우선순위 용도다.
                params["cond[rcrt_prgs_yn::EQ]"] = "Y"

            resp = self.client.get(ENDPOINT, params=params, timeout=settings.request_timeout_sec)
            # 봉투 없는 {"code":0,"msg":"정상"} 을 여기서 잡는다
            items, match_count = kstartup_envelope(resp)

            yield FetchedPage(
                request_url=mask(str(resp.url), self.api_key),
                page=page,
                payload=resp.json(),
                items=items,
                byte_size=len(resp.content),
                ratelimit_remaining=ratelimit_remaining(resp),
            )

            # matchCount 가 필터 결과다. totalCount 는 필터와 무관하게 29,789 로 고정이라
            # 종료 조건으로 쓰면 필터를 걸고도 149 페이지를 돈다.
            if not items or page * PER_PAGE >= match_count:
                return
            time.sleep(settings.request_delay_sec)

        raise RuntimeError(f"페이지 상한 {MAX_PAGES} 초과. 종료 조건을 확인할 것")

    def normalize(self, item: dict[str, Any]) -> NormalizedNotice | None:
        external_id = item.get("pbanc_sn")
        if external_id in (None, ""):
            return None

        columns, extra = split_known(item, KstartupNotice.API_FIELDS)

        return NormalizedNotice(
            source=self.source,
            external_id=str(external_id),
            columns=columns,
            extra=extra,
            derived_apply_start=parse_yyyymmdd(item.get("pbanc_rcpt_bgng_dt")),
            derived_apply_end=parse_yyyymmdd(item.get("pbanc_rcpt_end_dt")),
            # 목록 API 에 첨부 필드가 없다. 상세를 긁기 전까지 '모른다'가 정확하다.
            attachment_status=str(AttachmentStatus.UNKNOWN),
            attachments=[],
            content_hash=content_hash(item),
        )
