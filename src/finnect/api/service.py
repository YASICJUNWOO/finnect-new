"""조회.

정렬과 기본 필터가 ADR-0024(접수 기간 표현)를 그대로 구현한다.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Sequence

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from finnect.api.schemas import (
    AttachmentOut,
    DocumentItemOut,
    DocumentOut,
    FitOut,
    NoticeDetailOut,
    NoticeDocumentsOut,
    NoticeListOut,
    NoticeOut,
    RecommendationOut,
    RecommendationsOut,
)
from finnect.api.text import to_text
from finnect.attach import store
from finnect.config import settings
from finnect.models import (
    Attachment,
    AttachmentFile,
    Document,
    DocumentItem,
    DocumentKind,
    FitVerdict,
    NoticeFit,
    NoticeFitEvidence,
    Source,
)
from finnect.views import Notice

PAGE_SIZE = 20

SOURCES = {str(Source.BIZINFO), str(Source.KSTARTUP)}

#: 마감 임박순. **네 줄이 ADR-0024 의 세 갈래를 만든다.**
#:   1. 날짜가 있는 것 — 가까운 마감부터
#:   2. 날짜가 없고 원문이 있는 것 — "예산 소진시까지" 등. 원문 사전순
#:   3. 둘 다 없는 것 — 맨 뒤
#: boolean 은 false < true 라 `is_(None)` 오름차순이 "값이 있는 것 먼저"가 된다.
ORDER = (
    Notice.apply_end.is_(None).asc(),
    Notice.apply_end.asc(),
    Notice.apply_period_raw.is_(None).asc(),
    Notice.apply_period_raw.asc(),
    # 같은 마감일이 수백 건이라 안정적인 꼬리가 없으면 페이지마다 순서가 흔들린다.
    Notice.source.asc(),
    Notice.external_id.asc(),
)


def _open_filter(today: dt.date):
    """**마감이 지난 것만 뺀다.**

    날짜가 없는 975건은 빼지 않는다. 마감했는지 알 수 없고 "예산 소진시까지"는
    열려 있을 가능성이 높다. **확인되지 않은 것을 마감으로 처리하지 않는다**(ADR-0024).
    """
    return or_(Notice.apply_end.is_(None), Notice.apply_end >= today)


def _days_left(end: dt.date | None, today: dt.date) -> int | None:
    return (end - today).days if end else None


def _files(s: Session, source: str, external_id: str) -> dict[str, AttachmentFile]:
    """공고 하나의 첨부별 해독 결과. **URL 로 맞춘다**(ADR-0022).

    `attach.service.per_notice` 와 같은 질의다. 거기 것을 안 쓰는 이유는 그 모듈이
    내려받기(httpx)와 파서를 함께 끌고 오기 때문이다. **읽기만 하는 API 가
    다운로더에 딸려 갈 이유가 없다.**
    """
    urls = list(
        s.scalars(
            select(Attachment.url).where(
                Attachment.source == source,
                Attachment.external_id == external_id,
                Attachment.url.is_not(None),
            )
        )
    )
    if not urls:
        return {}
    return {r.url: r for r in s.scalars(select(AttachmentFile).where(AttachmentFile.url.in_(urls)))}


def _counts(s: Session, rows: list[Notice]) -> dict[tuple[str, str], int]:
    """이 페이지 공고들의 첨부 수. 뷰에 상관 서브쿼리를 넣지 않는다."""
    if not rows:
        return {}
    keys = [(r.source, r.external_id) for r in rows]
    got = s.execute(
        select(Attachment.source, Attachment.external_id, func.count())
        .where(tuple_(Attachment.source, Attachment.external_id).in_(keys))
        .group_by(Attachment.source, Attachment.external_id)
    ).all()
    return {(a, b): c for a, b, c in got}


def _to_out(row: Notice, today: dt.date, attachment_count: int) -> NoticeOut:
    return NoticeOut(
        source=row.source,
        external_id=row.external_id,
        title=row.title,
        organization=row.organization,
        supervisor=row.supervisor,
        category=row.category,
        apply_start=row.apply_start,
        apply_end=row.apply_end,
        apply_period_raw=row.apply_period_raw,
        days_left=_days_left(row.apply_end, today),
        detail_url=row.detail_url,
        attachment_count=attachment_count,
    )


#: 화면에 세우는 추천 건수. `SPEC.md` F4-1 — "적합도순 **3건.** 전체를 늘어놓지 않는다"
TOP_N = 3


#: **데모용 고정 추천이다. 판정을 안 거친다.**
#:
#: **`DEMO_RECOMMENDATIONS=true` 일 때만 쓰인다**(`config.py`). 기본값으로는 이
#: 표가 있어도 아무 일이 없고 아래 `recommendations()` 가 평소대로 `notice_fit` 을
#: 읽는다 — 그래서 이 자리가 배포본이나 테스트에 새지 않는다.
#:
#: 2026-08-23 에 박았다. 이 DB 에는 공고 235건과 정규화 234건이 있는데 **회사 쪽이
#: 통째로 비어 있어서**(`user_file`·`wiki_fact`·`wiki_node`·`notice_fit` 이 0행)
#: `match` 가 대조할 재료가 없었고, 그래서 화면이 「아직 사업 위키가 없어서 못 고르고
#: 있어요」에 멈춰 있었다.
#:
#: **이유 문장과 근거 수를 사람이 썼다.** `match/rank.py` 의 템플릿 모양
#: (`"{키워드}이 주제예요. {근거 문장}"`)만 흉내 낸 것이고, 대응하는 `wiki_fact`
#: 행이 하나도 없다 — `DESIGN.md` §12.3(「모든 값에 출처를 매단다」)을 정면으로
#: 어기는 자리다. 플래그를 기본 꺼짐으로 둔 이유가 그것이다.
#:
#: 회사를 안 본다 — `?company=` 가 무엇이든 이 셋이 뜬다. 데모 중에 주소를 잘못
#: 열어 빈 화면이 나오는 것을 막으려는 것이다.
#:
#: **셋이고, 셋을 채우려고 고른 것이 아니다**(2026-08-24). 같은 날 아침에는 한 건이었고
#: 그때 여기 「남은 칸을 안 메운다 · 빈 것이 거짓보다 낫다」고 적혀 있었다 — 그 문장이
#: 금지한 것은 **칸을 채우려고 이유를 지어내는 것**이고, 자격을 실제로 넘는 공고를 더하는
#: 것이 아니다. 그래서 규칙은 그대로 두고 **자격으로 골랐다.**
#:
#: 이 DB 의 열린 공고 90건(K-Startup 35 · 기업마당 55)을 `c_narin` 의 실제 위키
#: 76행에 대조했고 **`178941`·`178914` 둘만 남았다.** 떨어진 이유가 전부 하드 게이트다 —
#: `178875` 공공데이터는 「공공데이터포털에서 제공불가 통보를 받은 경우」가 요건이고
#: 나린데이터는 신청한 적이 없다 · `178821` 후속 지원과 `176076` 팁스는 앞선 선정·투자
#: 이력을 요구하는데 위키가 `정부지원사업 선정 이력 없음`(`Financial/자금계획`)이다 ·
#: `178740` IR 데모데이는 F&B·프랜차이즈 · `178803` SVC Seoul 은 국내 진출을 원하는
#: **외국** 스타트업 · `178686`·`178527`·`177837` 은 본점을 고양·안양·포항으로 옮기는
#: 조건이고 위키의 본점 소재지는 성동구다. 기업마당 55건은 서울 밖 지역 사업이다.
#:
#: **`TOP_N` 을 정원으로 읽지 않는다.** 화면은 있는 만큼만 그린다
#: (`(list)/page.module.css` 의 `.picks` 가 `auto-fit minmax(280px, 1fr)` 이다) —
#: 셋이면 세 열이고 하나가 빠지면 남은 둘이 폭을 나눠 갖는다.
#:
#: **쓰기 데모는 `178951` 에서만 돈다.** `web/components/DemoReply.tsx` 의
#: `DEMO_NOTICE` 가 그 한 건이고 미리 채워 둔 hwp 도 현대모비스 신청서다. 새로 더한 둘은
#: **첨부를 아직 안 받아서**(`attachment` 행은 있고 `attachment_file` 이 없다) 양식이
#: 없고, 카드를 눌러 들어가면 「왜 맞는지」까지는 뜨지만 쓰기 화면은 빈다.
#: 열려면 `attach --only <그 둘의 URL 목록> --source kstartup` 뒤에 `extract` 다
#: (LLM 을 안 쓴다) — 그래도 `DEMO_NOTICE` 는 하나라 진짜 집필 경로로 떨어진다.
#:
#: 진짜로 세우려면 플래그를 끄고, 회사 위키를 만든 뒤
#: (`python -m finnect.wiki --company c_narin …`)
#: `python -m finnect.match --company c_narin --only <이 셋 목록>` 을 돌린다.
#:
#: ## 이유 문장을 어떻게 썼나
#:
#: **`rank.py` 의 템플릿 모양을 일부러 안 따른다.** 저쪽은
#: `"{겹친 키워드}이 주제예요. {노드 원문}"` 인데, 그 모양이 **공고 낱말과 우리 사업을
#: 나란히 놓기만 하고 둘을 잇지 않는다** — 「시장분석이 주제예요. 반품과 배송비를
#: 반영한 채널별 실질 마진을 계산해 보여 줍니다」를 읽은 사람은 왜 그 둘이 맞물리는지
#: 스스로 추론해야 한다. 문자열 교집합으로 만든 문장이라 그렇고, 그것이 ⑤ 키워드 축이
#: 노드를 4.8배로 늘려도 겹침이 11%→12% 였던 것과 같은 자리다(CLAUDE.md).
#:
#: 그래서 여기는 **한 문장에 셋을 담는다** — 내 사업이 어떤 상태인지 · 공고가 무엇을
#: 주는지 · 그래서 왜 맞는지다.
#:
#:     이커머스 데이터를 모으지만 아직 유료 고객이 없어서, 공고가 주는 6개월
#:     현업 PoC 로 첫 실증을 만들고 지원금 최대 9,000만원까지 받을 수 있어요
#:     └ 내 사업(코퍼스)                  └ 공고(본문)          └ 잇는 판단
#:
#: **앞의 둘은 실제 문서에서 왔다.** 공고 쪽은 본문(`pbanc_ctnt` · `aply_trgt_ctnt`)
#: 이고 회사 쪽은 `tests/fixtures/wiki-narin/` 이다 — 지어낸 것은 둘을 잇는 판단뿐이고,
#: 그것이 이 카드가 있는 이유다.
#:
#: **나중에 더한 둘은 코퍼스가 아니라 DB 를 봤다.** `wiki_fact` 의 `c_narin` 76행이고
#: 아래 주석이 자리(`Financial/자금계획` 같은 것)까지 적어 둔다 — 코퍼스는 원문이고 저
#: 표는 **추출기가 실제로 세운 것**이라, 화면에 뜨는 위키와 이유 문장이 같은 문장을 쓴다.
#: 근거 링크가 없는 것은 그대로다(`notice_fit_evidence` 행이 없다).
#:
#: **첨부를 안 인용한다.** `178951` 은 공고문 hwp 가 붙어 있고 거기가 더 자세하지만
#: (5,810자에 모집 분야 넷과 평가 항목이 있다), 본문에 없는 것을 이유로 들면 그 문장이
#: 화면 어디에도 없는 재료를 말하게 된다 — 사용자가 상세로 들어가서 대조할 수 있는 것은
#: 본문이다. **뒤에 더한 둘은 첨부를 아예 안 받아서 인용할 것이 없다** — 규칙이 아니라
#: 상태라서, 받고 나서도 이 규칙이 그대로 걸린다.
#:
#: **자격을 안 적는다**([ADR-0003](../../../docs/adr/0003-판별-비노출.md)). 「서울
#: 소재 7년 미만이라 조건에 들어요」가 사실이고 쓰고 싶어지지만, 못 넘는 공고는
#: 목록에서 빠지는 것으로 이미 답했다 — 여기 조건 대조를 적으면 없앤 「자격이
#: 되는지」 칸을 이유 문장 안에 다시 세우는 것이 된다.
#:
#: **확률을 말하지 않는다**(DESIGN.md §12.2). 「맞을 것 같아요」·「유리해요」가 아니라
#: 무엇이 있고 무엇을 주는지를 적고, 잇는 자리만 짚는다.
#:
#: **대가가 있다.** 플래그를 끄고 진짜 판정으로 갈아타면 문장 모양이 눈에 띄게
#: 되돌아간다 — `rank.py` 는 겹친 키워드와 노드 원문을 잇는 템플릿이라 「공고가
#: 무엇을 주나」를 따로 들고 있지 않다. 좁히려면 `rank.judge()` 가 공고 취지
#: (`notice_profile.purpose`)를 함께 싣도록 고쳐야 하고, 그건 plan/17 의 일이다.
#:
#: `(출처, 공고번호, 이유, 근거 수)`
DEMO_PICKS: tuple[tuple[str, str, str, int], ...] = (
    (
        "kstartup",
        "178951",
        # 코퍼스 「중소 이커머스 사업자의 … 데이터를 자동으로 모읍니다」 「유료 고객
        # 0곳」 · 공고 「선정된 기업은 실제 현업 부서와 6개월간 PoC(기술 실증)를 함께
        # 진행하고, 최대 9,000만 원의 사업화 지원금까지 받을 수 있는」
        #
        # **파일럿 곳수를 안 쓴다.** 코퍼스가 사업계획서·회사소개서 3곳과 피치덱 4곳으로
        # 갈려 있고 이유가 어디에도 없다(`wiki-narin/README.md` §3) — 한쪽을 고르면
        # 다수결로 값을 정하는 것이 되고, 그건 SPEC F1-1-7 이 묻기로 한 자리다.
        # 「유료 고객 0」 은 문서 다섯이 표현만 달리해 같은 말을 한다
        "이커머스 데이터를 모으지만 아직 유료 고객이 없어서, "
        "공고가 주는 6개월 현업 PoC 로 첫 실증을 만들고 "
        "지원금 최대 9,000만원까지 받을 수 있어요",
        2,
    ),
    (
        "kstartup",
        "178941",
        # 위키 `Financial/비용` 「잔여 현금 28,600,000원 (2026년 8월 1일)」
        # 「정산 연동 개발 18,000,000원, 외주 일부 포함」 · `Financial/매출` 「매출 0원」
        # · 공고 「체계적인 인큐베이팅을 통하여 성장 가능성이 높은 혁신형 중소기업으로
        # 육성」 「입주 기업 신규 모집」
        #
        # **고정비를 줄인다는 것이 잇는 판단이다.** 위키에 임차료가 없다 — 있는 것은
        # 본점 소재지 하나(`Custom/검토 대기` 「서울특별시 성동구 아차산로17길 48, 4층」)
        # 라 금액을 안 쓴다. 「사무실 임차료 얼마가 빠져요」는 없는 값을 말하는 것이 된다
        "남은 현금 2,860만원에 매출은 아직 없고 정산 연동 개발에 1,800만원이 필요해서, "
        "공고가 주는 입주 공간과 인큐베이팅으로 고정비를 줄이면 "
        "그 개발에 쓸 몫이 남아요",
        3,
    ),
    (
        "kstartup",
        "178914",
        # 위키 `Financial/자금계획` 「정부지원사업 선정 이력 없음」 · `Customer/검증`
        # 「무료 파일럿 3곳 (2026년 7월 시작)」 · `Product/기능` 「반품·배송비·수수료를
        # 반영한 실질 마진을 채널별로 계산합니다」 · 공고 「우수한 창업 아이디어를
        # 발굴·확산하고자」
        #
        # **대회 결과를 말하지 않는다.** 「첫 실적을 만들 수 있어요」로 쓰고 싶어지지만
        # 그것은 수상을 전제한 문장이고 DESIGN.md §12.2 가 금지한 확률이다. 낼 수 있는
        # 것까지만 적는다 — 이미 가진 재료가 대회가 찾는 것과 같은 종류라는 것이 판단이다.
        #
        # **파일럿 곳수는 3 을 쓴다.** 사업계획서·회사소개서가 3곳이고 피치덱만 4곳인데
        # (`wiki-narin/README.md` §3 · 이유가 어디에도 없다) 위키가 세운 값이 3 이다
        # (`Customer/검증` 「무료 파일럿 3곳」) — 다수결로 고른 것이 아니라 **화면에 뜨는
        # 값과 같게 적는 것**이다. `Product/개발현황` 에 4곳도 같이 서 있어서 갈리면
        # 사용자가 이유와 위키를 대조하다 다른 숫자를 본다
        "정부지원 선정 이력이 아직 없는데, "
        "공고가 창업 아이디어를 발굴하는 대회라 "
        "무료 파일럿 3곳에서 확인한 마진 계산 문제를 그대로 낼 수 있어요",
        3,
    ),
)


def _demo_pick(source: str, external_id: str) -> tuple[str, int] | None:
    """`DEMO_PICKS` 에서 이 공고의 `(이유, 근거 수)` 를 찾는다. 없으면 `None`.

    **추천 목록과 공고 상세가 같은 표를 읽으라고 있는 함수다.** 두 화면이 다른 문장을
    말하면 카드를 눌러 들어간 사람이 다른 판정으로 읽는다 — `_fit()` 의 원래 주석이
    적어 둔 「CLI 가 셋을 찍는데 상세만 다르게 말하면 안 된다」와 같은 자리다.
    """
    for src, eid, reason, n in DEMO_PICKS:
        if (src, eid) == (source, external_id):
            return reason, n
    return None


def _demo_recommendations(s: Session, today: dt.date) -> RecommendationsOut:
    """`DEMO_PICKS` 를 그대로 세운다. **`notice_fit` 을 안 읽는다.**

    제목·기관·마감일·첨부 수는 `notice` 뷰에서 읽는다 — 그 넷까지 지어내면 화면이
    말하는 마감일이 상세와 어긋난다. 지어낸 것은 이유 한 줄과 근거 수뿐이다.

    **마감이 지났는지 안 본다.** 진짜 경로는 빼지만(판정이 어제 돌았어도 오늘
    마감일 수 있다) 여기는 데모라 날짜가 지나도 셋이 그대로 서야 한다 —
    마감으로 빠지면 화면이 그만큼 비고, 데모에서 그 자리를 되살릴 방법이 없다.
    """
    keys = [(src, eid) for src, eid, _reason, _n in DEMO_PICKS]
    rows = {
        (r.source, r.external_id): r
        for r in s.scalars(
            select(Notice).where(tuple_(Notice.source, Notice.external_id).in_(keys))
        )
    }
    # 코퍼스를 다시 세우면 공고가 사라질 수 있다(`dataset --prune` 이 목록 밖을 지우고,
    # 기업마당은 마감되면 API 에서 아예 없어진다).
    # **없는 것을 지어내지 않는다** — 그 자리는 그냥 빠진다
    live = [(p, rows[(p[0], p[1])]) for p in DEMO_PICKS if (p[0], p[1]) in rows]
    counts = _counts(s, [r for _p, r in live])

    return RecommendationsOut(
        items=[
            RecommendationOut(
                **_to_out(r, today, counts.get((r.source, r.external_id), 0)).model_dump(),
                reason=reason,
                evidence_count=n,
            )
            for (_src, _eid, reason, n), r in live
        ],
        computed=True,
    )


def recommendations(
    s: Session, company_id: str, *, today: dt.date | None = None
) -> RecommendationsOut:
    """추천 세 건 (plan/17 T-0075).

    **`notice_fit` 을 읽기만 한다.** 판정은 `python -m finnect.match` 가 미리
    돌린다 — 화면 요청 경로에서 LLM 을 부르지 않는 것(F6-1 과 같은 원칙)이고,
    `match.service` 를 임포트하지 않는 이유도 그것이다: 저쪽이 `llm` 을 끌고
    오는데 `requirements.txt` 에 httpx 가 없어 **배포본만 죽는다**(CLAUDE.md 함정).

    마감이 지난 것은 낸 뒤에 뺀다 — 판정은 어제 돌았어도 오늘 마감일 수 있다.

    **등급이 아니라 이유로 거른다**(T-0076). `애매` 도 이유가 있으면 올린다 — ④ 분야가
    살린 것이라 근거가 `wiki_fact` 에 실제로 있다. `match/service.py` 의 `rep.top` 과
    같은 규칙이어야 한다: **CLI 가 셋을 찍는데 화면이 비면 안 된다.**

    **`DEMO_RECOMMENDATIONS=true` 면 아래가 안 돈다** — `DEMO_PICKS` 가 앞에서
    가로챈다. 기본은 꺼짐이라 평소에는 이 문단이 없는 것과 같다.
    """
    today = today or dt.date.today()

    if settings.demo_recommendations and DEMO_PICKS:
        return _demo_recommendations(s, today)

    fits = list(
        s.scalars(
            select(NoticeFit).where(
                NoticeFit.company_id == company_id,
                NoticeFit.reason != "",
            )
        )
    )
    if not fits:
        # 행이 하나도 없으면 **아직 안 돌린 것**이다. `맞다` 가 0건인 것과 다르다
        any_row = s.scalar(
            select(func.count())
            .select_from(NoticeFit)
            .where(NoticeFit.company_id == company_id)
        )
        return RecommendationsOut(items=[], computed=bool(any_row))

    keys = [(f.source, f.external_id) for f in fits]
    rows = {
        (r.source, r.external_id): r
        for r in s.scalars(
            select(Notice).where(tuple_(Notice.source, Notice.external_id).in_(keys))
        )
    }
    ev = {
        fid: n
        for fid, n in s.execute(
            select(NoticeFitEvidence.fit_id, func.count())
            .where(NoticeFitEvidence.fit_id.in_([f.id for f in fits]))
            .group_by(NoticeFitEvidence.fit_id)
        ).all()
    }

    live = [
        (f, rows[(f.source, f.external_id)])
        for f in fits
        if (f.source, f.external_id) in rows
        and (
            rows[(f.source, f.external_id)].apply_end is None
            or rows[(f.source, f.external_id)].apply_end >= today
        )
    ]
    # **등급 → 분야 일치 → 겹침 수 → 마감 임박.** `match/rank.py` 의 정렬과 같다
    live.sort(
        key=lambda t: (
            0 if t[0].verdict == str(FitVerdict.MATCH) else 1,
            0 if t[0].sector_hit else 1,
            -len(t[0].matched or []),
            _days_left(t[1].apply_end, today) or 10_000,
            t[0].source,
            t[0].external_id,
        )
    )
    live = live[:TOP_N]
    counts = _counts(s, [r for _f, r in live])

    return RecommendationsOut(
        items=[
            RecommendationOut(
                **_to_out(r, today, counts.get((r.source, r.external_id), 0)).model_dump(),
                reason=f.reason,
                evidence_count=ev.get(f.id, 0),
            )
            for f, r in live
        ],
        computed=True,
    )


def list_notices(
    s: Session,
    *,
    q: str = "",
    source: str = "",
    page: int = 1,
    open_only: bool = True,
    today: dt.date | None = None,
) -> NoticeListOut:
    today = today or dt.date.today()

    where = []
    if source in SOURCES:
        where.append(Notice.source == source)
    if q.strip():
        where.append(Notice.title.ilike(f"%{q.strip()}%"))
    if open_only:
        where.append(_open_filter(today))

    total = s.scalar(select(func.count()).select_from(Notice).where(*where)) or 0
    rows = list(
        s.scalars(
            select(Notice)
            .where(*where)
            .order_by(*ORDER)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    )
    counts = _counts(s, rows)

    return NoticeListOut(
        items=[_to_out(r, today, counts.get((r.source, r.external_id), 0)) for r in rows],
        total=total,
        page=page,
        pages=max(1, math.ceil(total / PAGE_SIZE)),
        open_only=open_only,
    )


def get_notice(
    s: Session,
    source: str,
    external_id: str,
    *,
    today: dt.date | None = None,
    company_id: str = "",
) -> NoticeDetailOut | None:
    """공고 하나.

    `company_id` 를 주면 **왜 맞는지**가 같이 온다(plan/21 T-0120). 안 주면 `fit`
    이 `None` 이라 화면이 그 자리를 안 그린다.

    **자격은 안 낸다.** [ADR-0003](../../../docs/adr/0003-판별-비노출.md) 이
    「판정은 뒤에서 하고 화면은 결과만 준다」로 정했고, 자격 결과는 목록에서 빼는
    것으로 이미 나갔다. 여기에 대조표를 두면 그 결정을 되돌린다.
    """
    today = today or dt.date.today()

    row = s.scalars(
        select(Notice).where(Notice.source == source, Notice.external_id == external_id)
    ).first()
    if row is None:
        return None

    attachments = list(
        s.scalars(
            select(Attachment)
            .where(Attachment.source == source, Attachment.external_id == external_id)
            .order_by(Attachment.position)
        )
    )
    # 해독 결과는 URL 로 맞춘다. attachment 는 재수집 때 지워지고 다시 깔린다(ADR-0022).
    files = _files(s, source, external_id)

    out = []
    for a in attachments:
        f = files.get(a.url) if a.url else None
        out.append(
            AttachmentOut(
                position=a.position,
                kind=a.kind,
                filename=a.filename,
                ext=a.ext,
                url=a.url,
                fetch_status=f.fetch_status if f else None,
                parse_status=f.parse_status if f else None,
                text_chars=f.text_chars if f else None,
                detected_ext=f.detected_ext if f else None,
            )
        )

    base = _to_out(row, today, len(attachments))
    return NoticeDetailOut(
        **base.model_dump(),
        summary=to_text(row.summary),
        attachments=out,
        decoded_count=sum(1 for a in out if a.parse_status == "ok"),
        fit=_fit(s, company_id, source, external_id) if company_id else None,
    )


def _fit(s: Session, company_id: str, source: str, external_id: str) -> FitOut | None:
    """왜 맞는지 (plan/21 T-0120).

    **`notice_fit` 을 읽기만 한다.** `recommendations()` 와 같은 표이고 같은 규율이다 —
    `match.service` 를 임포트하면 `llm` 이 딸려 온다.

    **이유가 없으면 안 낸다.** 근거 없는 등급은 [ADR-0013](
    ../../../docs/adr/0013-판정-두-층.md) 이 금지한 것이고, `recommendations()` 도
    같은 조건으로 거른다 — **CLI 가 셋을 찍는데 상세만 다르게 말하면 안 된다.**

    **`DEMO_RECOMMENDATIONS=true` 면 그 셋만 고정 이유를 낸다**(2026-08-23 · 임시).
    추천 카드를 눌러 들어간 자리라 여기가 비면 동선이 거기서 끊긴다. 표 밖의 공고는
    그대로 아래로 흘러가서 진짜 판정을 읽는다 — **데모가 판정을 가리지 않는다.**
    """
    got = _demo_pick(source, external_id) if settings.demo_recommendations else None
    if got is not None:
        reason, n = got
        return FitOut(verdict=str(FitVerdict.MATCH), reason=reason, evidence_count=n)

    fit = s.scalars(
        select(NoticeFit).where(
            NoticeFit.company_id == company_id,
            NoticeFit.source == source,
            NoticeFit.external_id == external_id,
            NoticeFit.reason != "",
        )
    ).first()
    if fit is None:
        return None

    n = s.scalar(
        select(func.count())
        .select_from(NoticeFitEvidence)
        .where(NoticeFitEvidence.fit_id == fit.id)
    )
    return FitOut(verdict=fit.verdict, reason=fit.reason, evidence_count=n or 0)


#: 공고문이 서류를 말하는 줄. 양식이 없을 때 이거라도 넘긴다.
_SUBMIT_HINT = re.compile(r"제출\s*서류|구비\s*서류|신청\s*서류|신청\s*시\s*제출")


def notice_documents(s: Session, source: str, external_id: str) -> NoticeDocumentsOut | None:
    """공고가 요구하는 서류와 그 안의 작성 항목(plan/11 T-0039).

    **공고와 문서를 잇는 표를 만들지 않았다.** `attachment → attachment_file → sha256`
    조인으로 푼다. 재수집이 `attachment` 를 갈아엎어도 조인이 다시 붙는다(ADR-0022).
    """
    if source not in SOURCES:
        return None

    rows = s.execute(
        select(Attachment, AttachmentFile, Document)
        .join(AttachmentFile, AttachmentFile.url == Attachment.url)
        .join(Document, Document.sha256 == AttachmentFile.sha256)
        .where(Attachment.source == source, Attachment.external_id == external_id)
        .order_by(Attachment.position, Document.seq)
    ).all()

    docs: list[DocumentOut] = []
    undecided = 0
    seen: set[int] = set()
    for att, att_file, doc in rows:
        if doc.id in seen:
            continue
        seen.add(doc.id)
        if doc.kind == str(DocumentKind.UNKNOWN):
            undecided += 1
            continue
        if doc.kind == str(DocumentKind.NONE):
            continue

        items = s.scalars(
            select(DocumentItem)
            .where(DocumentItem.document_id == doc.id)
            .order_by(DocumentItem.ordinal)
        ).all()
        docs.append(
            DocumentOut(
                id=doc.id,
                title=doc.title,
                kind=doc.kind,
                decided_by=doc.decided_by,
                filename=att.filename,
                url=att.url,
                sha256=doc.sha256,
                ext=att_file.detected_ext,
                items=_tree(items),
            )
        )

    return NoticeDocumentsOut(
        source=source,
        external_id=external_id,
        documents=docs,
        submit_hint=_hints(s, source, external_id) if not docs else [],
        undecided=undecided,
    )


def _tree(rows: Sequence[DocumentItem]) -> list[DocumentItemOut]:
    """`parent_id` 로 트리를 세운다(plan/11 T-0037).

    **한 번에 다 받아서 메모리에서 잇는다.** 단마다 질의를 날리면 항목 199개짜리
    양식이 199번을 부른다.

    **가지에 쓰는 칸이 붙으면 안 된다.** 화면이 잎만 쓰는 자리로 세는데
    (`FormFill` 의 `leafKeys`) 자식을 안 내보내면 `2 추진배경 및 목표` 가 잎이 되고,
    거기 붙은 칸에 쓴 글은 어느 항목의 것도 아니게 된다.

    순서는 `ordinal` 이다 — 문서 안에서 한 번만 매겨지므로 형제끼리도 이 순서다.
    """
    kids: dict[int | None, list[DocumentItem]] = {}
    for r in rows:
        kids.setdefault(r.parent_id, []).append(r)

    def build(parent: int | None, depth: int) -> list[DocumentItemOut]:
        # 부모는 항상 자식보다 먼저 들어가므로(`extract/service.py` `_add_outline`)
        # 고리가 생길 수 없다. 그래도 막아 두는 이유는 여기가 API 라서다 — 고리
        # 하나가 응답을 못 끝내면 공고 상세가 통째로 안 뜬다.
        if depth > 10:
            return []
        return [
            DocumentItemOut(
                number=i.number,
                title=i.title,
                instruction=i.instruction,
                limit_text=i.limit_text,
                input_kind=i.input_kind,
                children=build(i.id, depth + 1),
            )
            for i in kids.get(parent, [])
        ]

    return build(None, 1)


def _hints(s: Session, source: str, external_id: str) -> list[str]:
    """양식이 없을 때 공고문에서 '무슨 서류를 내나' 만이라도 건진다.

    **빈손으로 보내지 않는다**(DESIGN.md §7-5). 층 1 은 공고문에 있다.
    """
    paths = s.scalars(
        select(AttachmentFile.text_path)
        .join(Attachment, Attachment.url == AttachmentFile.url)
        .where(
            Attachment.source == source,
            Attachment.external_id == external_id,
            AttachmentFile.text_path.is_not(None),
        )
        .limit(4)
    ).all()

    out: list[str] = []
    for p in paths:
        try:
            text = store.abs_path(p).read_text(errors="ignore")
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            line = re.sub(r"\s{2,}", " ", line.replace("\t", " ")).strip()
            if 6 <= len(line) <= 120 and _SUBMIT_HINT.search(line) and line not in out:
                out.append(line)
            if len(out) >= 4:
                return out
    return out
