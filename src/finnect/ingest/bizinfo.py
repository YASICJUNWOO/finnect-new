"""기업마당(중소벤처기업부 bizinfo) 어댑터.

실측 2026-08-16: searchCnt=2000 한 번에 전량 1,538건(3.67MB)이 온다.
pageUnit·pageIndex 가 공식 문서에 있으나 쓸 일이 없다.
일 한도는 공식 안내에 명시가 없다.

**`skip_mlsfc` 기본값이 2026-08-24 부터 켬이다.** 서버측 필터(`searchLclasId`)로 좁히면
분류마다 한 번씩 8회가 되는데 전량이 1회·5초라 오히려 손해다(docs/adr/evidence/
2026-08-16-목록-API-실측.md). 그래서 전량을 받아 놓고 적재 직전에 `ingest.mlsfc` 표로
뺀다. 전량이 필요하면(재수집·정본 코퍼스) `--full` 로 끈다.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import httpx

from finnect.config import settings
from finnect.dataset import sample as sampling
from finnect.ingest import mlsfc
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

#: 첨부 파일명이 「채울 것이 들어 있다」고 말하는 낱말(2026-08-24 · T-0165).
#:
#: **`fileNm` 만 본다. `printFileNm` 은 안 본다** — 저건 공고문이고 1,538건 **전부**에
#: 붙는다(CLAUDE.md 함정). 같이 보면 공고문 이름에 우연히 든 낱말로 통과해 버린다.
#:
#: 2026-08-24 실측 — 중분류를 통과한 932건에 낱말을 넓히면서 잰 값이다.
#:
#:     신청|계획                    487
#:     +양식|서식                   551
#:     +서류                        566   ← 이 표
#:     +서약서                      567
#:     +붙임                        572
#:     +내용 모를 zip 전부          588
#:
#: **`서류` 까지 넣은 이유.** `제출서류+양식+일체.zip` · `기업지원서류.hwp` 처럼
#: 「신청」도 「계획」도 안 쓰는 양식이 실제로 있었다.
#:
#: **여기서 멈춘 이유는 목적이 코퍼스를 줄이는 것이라서다.** `붙임` 은 +6 인데
#: `2.붙임자료.zip` 처럼 내용을 모르는 것을 도로 끌어온다. `서약서` 는 +1 이고
#: 진짜 채우는 서류지만, 한 건 때문에 표를 늘리지 않기로 했다.
FORM_WORDS = re.compile(r"(신청|계획|양식|서식|서류)")


def has_form(file_names: str | None) -> bool:
    """이 공고의 첨부에 채울 양식이 있어 보이나.

    **`.zip` 을 무조건 살리지 않는다.** 이름이 아무것도 안 말하는 묶음
    (`첨부파일.zip` · `2.붙임자료.zip`)이 22건 있었는데, 안에 양식이 있어도 이름으로는
    알 수 없다 — 우리는 ZIP 을 안 푼다(CLAUDE.md — 166개 안에 읽을 수 있는 문서가
    799개 있는데 목록만 읽는다). **모르는 쪽을 버리기로 했다** — 코퍼스를 줄이는 것이
    이 필터의 목적이고, `2026년…지원사업 공고.zip` 처럼 이름이 이미 「공고문을 쌌다」고
    말하는 것이 그 22건에 섞여 있었다.

    **대가를 적어 둔다.** 그 22건 중 일부에는 진짜 양식이 들어 있을 수 있고, 지금은
    그걸 확인할 방법이 없다. 확인하려면 파일을 받아 `attachment_file.contents` 를
    봐야 하는데 그건 이 단계보다 뒤다. **공고가 API 에서 사라지면 되찾을 수 없다.**
    """
    return bool(FORM_WORDS.search(file_names or ""))


class BizinfoAdapter:
    source = str(Source.BIZINFO)
    model = BizinfoNotice

    def __init__(
        self,
        client: httpx.Client,
        api_key: str | None = None,
        limit: int | None = None,
        skip_mlsfc: bool = True,
        require_form: bool = True,
        sample: int = 1,
    ) -> None:
        self.client = client
        self.api_key = api_key if api_key is not None else settings.bizinfo_api_key
        self.limit = limit
        # 계획서로 심사하지 않는 중분류를 적재에서 뺀다. 기본은 켬이다 —
        # 끄는 것은 `docs/dataset.md` 의 정본 전량 절차뿐이다(CLI `--full`).
        self.skip_mlsfc = skip_mlsfc
        # 첨부에 채울 양식이 없어 보이면 뺀다(T-0165). 위와 같은 스위치로 꺼진다.
        self.require_form = require_form
        # 공고번호를 이 수로 나눠 나머지 0 만 남긴다. 1 이면 전부 남는다(끔).
        self.sample = sample
        if not self.api_key:
            raise RuntimeError("BIZINFO_API_KEY 가 없다")

    def keep(self, item: dict[str, Any]) -> bool:
        """중분류와 첨부 파일명으로 거른다. **`pages()` 가 아니라 여기서 한다.**

        `raw_fetch` 는 응답 통째를 남기는 표라, 응답에서 빼면 API 가 무엇을 줬는지가
        기록에서 사라진다. 거르는 자리는 적재 직전이다.

        **둘 다 목록 응답만 본다.** 기업마당은 첨부 목록이 목록 API 에 같이 오므로
        (K-Startup 과 다른 점이다) 파일을 안 받고도 이 판정이 선다 — 요청이 안 는다.
        """
        if self.skip_mlsfc and not mlsfc.keeps(item.get("pldirSportRealmMlsfcCodeNm")):
            return False
        if self.require_form and not has_form(item.get("fileNm")):
            return False
        # **표본이 맨 뒤다.** 앞에 두면 「낱말로 몇 건이 통과했나」를 못 세고,
        # 나눗수를 바꿀 때마다 그 수가 같이 흔들려 무엇이 줄인 건지 알 수 없다.
        return sampling.keeps(str(item.get("pblancId") or ""), self.sample)

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
