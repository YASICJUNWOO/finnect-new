"""K-Startup(창업진흥원) 어댑터 — data.go.kr B552735/kisedKstartupService01.

실측 2026-08-16:
  전량 29,789건. perPage=200 → 149회. 일 한도 10,000회.
  상세 API 가 없다. 목록 API 하나뿐이라 첨부는 detl_pg_url 스크래핑밖에 방법이 없다(plan/02).
  수정일시 필드가 없다. 변경 감지는 콘텐츠 해시뿐이다.

**서버측 날짜 필터를 쓰지 않는다.** cond[...::GTE] 계열이 조건을 위반하는 레코드를 섞어 준다.

**`only_open` 기본값이 2026-08-24 부터 켬이다**(docs/adr/evidence/2026-08-16-목록-API-실측.md
«기업마당 `searchLclasId` 코드값» 절 위). `cond[rcrt_prgs_yn::EQ]=Y` 는 검증된 필터라서
모집중만 받아도 틀린 레코드가 안 섞인다(요청 1회 · 268건, 2026-08-24). 첨부 해독·`--classify`
비용이 공고 수에 비례하는데 전량 29,789건은 대부분 마감 공고라 화면에 안 뜬다.

**그래도 이것이 진짜 모집단은 아니다.** 274건 중 74건(27%)이 수집 뒤 며칠 새 마감됐다
— 플래그가 수집 시점 스냅샷이라 썩는다. 전량이 필요하면(재수집·정본 코퍼스) `--full` 로
끈다. 그때는 149회가 일 한도의 1.5%라 아낄 이유가 없다.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from finnect.config import settings
from finnect.dataset import sample as sampling
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

#: perPage 상한. 2026-08-16 실측으로 2,000 은 오고 3,000 부터 봉투 없는
#: {"code":0,"msg":"정상"} 이 온다. **여기도 실패가 HTTP 200 이다.**
MAX_PER_PAGE = 2000


class KstartupAdapter:
    source = str(Source.KSTARTUP)
    model = KstartupNotice

    def __init__(
        self,
        client: httpx.Client,
        api_key: str | None = None,
        only_open: bool = True,
        limit: int | None = None,
        sample: int = 1,
    ) -> None:
        self.client = client
        self.api_key = api_key if api_key is not None else settings.data_go_kr_api_key
        self.only_open = only_open
        self.limit = limit
        self.sample = sample
        if not self.api_key:
            raise RuntimeError("DATA_GO_KR_API_KEY 가 없다")

    def keep(self, item: dict[str, Any]) -> bool:
        """표본만 본다. 좁히는 것은 `only_open` 이 서버측에서 이미 했다.

        **첨부 낱말로는 여기서 못 거른다.** K-Startup 은 목록 API 가 첨부를 안 줘서
        상세 페이지를 긁어야 아는데, 그 긁기는 이 판정보다 **뒤에** 돈다
        (`service.execute()`). 그쪽은 스크랩이 끝난 뒤에 거른다.

        **표본이 스크랩보다 앞인 것이 요점이다.** 뒤에 두면 버릴 공고의 상세 페이지까지
        열게 된다 — `docs/초기화.md` 의 「표본이 첨부 받기 앞이다」와 같은 자리다.
        """
        return sampling.keeps(str(item.get("pbanc_sn") or ""), self.sample)

    def pages(self) -> Iterator[FetchedPage]:
        # 건수 제한 파라미터가 따로 없다. perPage 로 한 장에 담고 일찍 끊는 수밖에 없다.
        # limit 이 MAX_PER_PAGE 이하면 요청 1회로 정확히 그만큼 온다.
        per_page = min(MAX_PER_PAGE, self.limit) if self.limit else PER_PAGE
        seen = 0

        for page in range(1, MAX_PAGES + 1):
            params: dict[str, Any] = {
                "serviceKey": self.api_key,
                "page": page,
                "perPage": per_page,
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
                # totalCount 가 아니라 matchCount 다. 진행률에도 같은 함정이 있다.
                total_count=match_count,
            )

            seen += len(items)

            # matchCount 가 필터 결과다. totalCount 는 필터와 무관하게 29,789 로 고정이라
            # 종료 조건으로 쓰면 필터를 걸고도 149 페이지를 돈다.
            if not items or page * per_page >= match_count:
                return
            if self.limit is not None and seen >= self.limit:
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
