"""초안 집필 실행 (plan/16).

**양식 읽기는 회사와 무관하다.** 그래서 `read_forms` 만 `company_id` 를 안 받는다 —
한 번 읽으면 그 양식을 쓰는 모든 회사가 쓴다(T-0063).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from finnect import trace
from finnect.config import settings
from finnect.db import engine
from finnect.draft import allot as al
from finnect.draft import dedupe as dd
from finnect.draft import limits, refs
from finnect.draft import needs as nd
from finnect.draft import write as wr
from finnect.llm import Usage
from finnect.models import (
    WRITABLE_KINDS,
    Attachment,
    AttachmentFile,
    CompanyValue,
    Document,
    DocumentItem,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftItemStatus,
    DraftValueEvidence,
    ItemNeed,
    ItemOverlap,
    SourceType,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.views import Notice
from finnect.wiki import profile

#: 공고 본문을 재료에 넣을 때의 상한. **지원금액이 값으로 오는 필드가 없어서
#: 본문에서만 나온다** — 너무 짧게 자르면 금액이 잘리고, 길면 프롬프트가 커진다
NOTICE_SUMMARY_CHARS = 3_000


@dataclass(slots=True)
class ReadReport:
    forms: int = 0
    items: int = 0
    needs: int = 0
    overlaps: int = 0
    summaries: int = 0
    #: 항목이 하나도 없는 서술형 구간. **판정이 틀렸다는 신호다**(plan/11 T-0037)
    empty: int = 0
    dropped: list[tuple[str, str]] = field(default_factory=list)
    usage: str = ""

    def line(self) -> str:
        out = [
            f"양식 {self.forms:,} · 항목 {self.items:,} · 필요한 자리 {self.needs:,} · "
            f"겹침 쌍 {self.overlaps:,} · 요약 항목 {self.summaries:,}",
        ]
        if self.empty:
            out.append(f"항목이 없는 서술형 구간 {self.empty:,}건 — 판정을 의심한다")
        if self.dropped:
            out.append(f"버림 {len(self.dropped):,}건 — {self.dropped[:3]}")
        if self.usage:
            out.append(self.usage)
        return "\n".join(out)


def read_forms(
    *,
    limit: int | None = None,
    redo: bool = False,
    reader: nd.LlmReader | None = None,
    notice: tuple[str, str] | None = None,
) -> ReadReport:
    """채울 수 있는 양식을 읽어 `item_need` 와 `item_overlap` 을 깐다 (T-0063).

    `reader` 를 넘길 수 있는 이유는 **테스트가 네트워크 없이 돌아야 해서**다.

    `notice` 를 주면 그 공고에 붙은 양식만 읽는다 — 초안 시작이 부르는 길이다.
    """
    reader = reader or nd.LlmReader()
    report = ReadReport()

    with Session(engine) as s:
        q = select(Document).where(Document.kind.in_(WRITABLE_KINDS))
        if notice is not None:
            source, external_id = notice
            q = q.join(AttachmentFile, AttachmentFile.sha256 == Document.sha256).join(
                Attachment, Attachment.url == AttachmentFile.url
            ).where(
                Attachment.source == source,
                Attachment.external_id == external_id,
            )
        docs = s.scalars(q.order_by(Document.sha256, Document.seq)).all()

        for doc in docs:
            if limit is not None and report.forms >= limit:
                break
            rows = s.scalars(
                select(DocumentItem)
                .where(DocumentItem.document_id == doc.id)
                .order_by(DocumentItem.ordinal)
            ).all()
            if not rows:
                report.empty += 1
                continue
            if not redo and any(r.needs_decided_by for r in rows):
                continue  # **같은 양식을 두 번 묻지 않는다**

            views = [
                nd.ItemView(
                    number=r.number,
                    title=r.title,
                    level=_level(r, rows),
                    instruction=r.instruction,
                    limit_text=r.limit_text,
                )
                for r in rows
            ]
            reading = reader.read(doc.title, views)
            _store(s, doc, rows, reading, reader.name, report)
            report.forms += 1

        report.dropped = list(reader.dropped)
        report.usage = _usage_line(reader)
        s.commit()
    return report


def _level(row: DocumentItem, rows: list[DocumentItem]) -> int:
    """`parent_id` 를 타고 올라가 깊이를 센다. **DB 에 단을 따로 안 들고 있다** —
    `outline` 이 만든 트리가 정본이고, 단은 거기서 유도되는 값이다."""
    by_id = {r.id: r for r in rows}
    depth, cur = 1, row
    while cur.parent_id and cur.parent_id in by_id and depth < 10:
        cur = by_id[cur.parent_id]
        depth += 1
    return depth


def _store(
    s: Session,
    doc: Document,
    rows: list[DocumentItem],
    reading: nd.Reading,
    decider: str,
    report: ReadReport,
) -> None:
    ids = [r.id for r in rows]
    s.execute(delete(ItemNeed).where(ItemNeed.document_item_id.in_(ids)))
    s.execute(delete(ItemOverlap).where(ItemOverlap.document_id == doc.id))

    for item in reading.items:
        row = rows[item.index]
        row.summary_of_others = item.summary_of_others
        row.needs_decided_by = decider
        report.items += 1
        report.summaries += int(item.summary_of_others)
        for need in item.needs:
            s.add(
                ItemNeed(
                    document_item_id=row.id,
                    place=need.place,
                    place_kind=nd.PLACE_KIND[need.place],
                    required=need.required,
                )
            )
            report.needs += 1

    for ov in reading.overlaps:
        a, b = rows[ov.a].id, rows[ov.b].id
        s.add(
            ItemOverlap(
                document_id=doc.id,
                a_item_id=min(a, b),
                b_item_id=max(a, b),
                note=ov.note[:500],
            )
        )
        report.overlaps += 1


def _usage_line(obj: object) -> str:
    c = getattr(obj, "client", None)
    usage = getattr(c, "usage", None)
    return usage.line() if usage is not None and getattr(usage, "calls", 0) else ""


# ─────────────────────────────────────────────────────────────────
#
# **세션을 스레드가 만나지 않게 3단으로 가른다** (T-0069).
#
#   ① 조립   세션 안 · 읽기만.  ORM 객체를 밖으로 안 들고 나간다
#   ② 호출   세션 밖 · 스레드.  Writer 를 워커마다 새로 만든다
#   ③ 저장   세션 안 · ordinal 순.  같은 입력에서 같은 초안이 나온다
#
# 앞의 구조는 Session 을 LLM 호출 내내 붙잡고 있어서 스레드를 못 얹었다.
# **생성 버튼이 없다**(F6-1) — 큐는 여기서 정하지 않는다(SPEC §9-7 · ADR-0021).
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _ItemPlan:
    """세션 밖으로 들고 나가는 항목 하나. **ORM 객체를 안 담는다** — 세션이 닫힌
    뒤에도 스레드가 읽어야 한다."""

    row_id: int
    ordinal: int
    number: str | None
    title: str
    instruction: str | None
    limit_text: str | None
    places: tuple[str, ...]
    places_optional: tuple[str, ...]
    summary_of_others: bool


@dataclass(frozen=True, slots=True)
class _FormPlan:
    document_id: int
    doc_title: str
    items: tuple[_ItemPlan, ...]
    #: 겹침 쌍. 인덱스는 `items` 안의 자리다
    pairs: tuple[tuple[int, int], ...]


@dataclass(slots=True)
class BuildReport:
    forms: int = 0
    #: 이미 초안이 있어서 안 썼다. **LLM 을 부르기 전에 걸러진 수다**
    skipped: int = 0
    items: int = 0
    drafted: int = 0
    #: 위키에 없어서 못 썼다. **F6-6 이 가리키는 자리** — 여기만 물어본다
    blank: int = 0
    #: 쓸 자리가 아니다. 상위 묶음 등
    no_needs: int = 0
    #: 위키에는 있는데 다른 항목이 맡았다 (배분)
    yielded: int = 0
    #: 재료는 받았는데 글이 안 나왔다. **집필 실패다**
    unwritten: int = 0
    failed: int = 0
    paragraphs: int = 0
    #: 재료 밖이라 `[확인 필요]` 로 바꾼 것
    unverified: int = 0
    clashes: int = 0
    #: 분량 상한을 넘은 항목 (구멍 2). **넘어도 다시 쓰지 않는다**
    over_limit: int = 0
    #: 제한은 있는데 못 잰 항목. 쪽 수 제한과 `내외` 다
    unmeasured: int = 0
    #: 필요한데 위키에 없는 자리. **F6-6 이 읽는다**
    missing: dict[str, int] = field(default_factory=dict)
    usage: str = ""

    def line(self) -> str:
        miss = " · ".join(
            f"{n} {c}건" for n, c in sorted(self.missing.items(), key=lambda x: -x[1])[:6]
        )
        out = [
            f"양식 {self.forms:,}"
            + (f" (이미 있어서 건너뜀 {self.skipped:,})" if self.skipped else "")
            + f" · 항목 {self.items:,} (썼음 {self.drafted:,} · "
            f"못 채움 {self.blank:,} · 쓸 자리 아님 {self.no_needs:,} · "
            f"배분에서 못 받음 {self.yielded:,} · 글이 안 나옴 {self.unwritten:,} · "
            f"실패 {self.failed:,})",
            f"문단 {self.paragraphs:,} · 확인 필요 {self.unverified:,} · 겹침 {self.clashes:,} · "
            f"분량 초과 {self.over_limit:,} · 분량 못 잼 {self.unmeasured:,}",
        ]
        if miss:
            out.append(f"위키에 없어서 못 쓴 자리: {miss}")
        if self.usage:
            out.append(self.usage)
        return "\n".join(out)


def build_draft(  # noqa: PLR0913
    company_id: str,
    source: str,
    external_id: str,
    *,
    redo: bool = False,
    workers: int | None = None,
    allotter: al.Allotter | None = None,
    writers: Callable[[], wr.LlmWriter] | None = None,
    checker: dd.LlmChecker | None = None,
    prepare: bool = True,
) -> BuildReport:
    """공고 하나에 대해 초안을 세운다 (T-0068 · T-0069).

    **항목 하나가 실패해도 나머지는 남는다**(ADR-0015 결과 절).

    `writers` 는 **집필기를 만드는 함수**다. 워커마다 새로 만들어야 `unverified` ·
    `dropped` · `Usage` 가 안 섞인다 — `Usage.calls += 1` 이 원자적이 아니라서
    하나를 공유하면 **토큰 수가 어긋난다.** lock 을 안 쓰는 이유가 그것이다.

    `prepare` 가 **양식을 여기서 뜯는다**(⓪). 끄는 것은 재료를 손으로 깔아 둔
    테스트뿐이다.

    **`redo` 가 아니면 이미 쓴 양식을 조립 단계에서 걷어낸다**(T-0161). 저장 직전에
    거르면(`_draft_row`) 배분과 집필을 **다 부른 뒤**라 토큰만 나가고 결과가 통째로
    버려진다 — 화면은 그대로인데 돈은 나가서 사용자도 로그도 그것을 못 본다.
    """
    report = BuildReport()
    allotter = allotter or al.Allotter()
    checker = checker or dd.LlmChecker()
    make_writer = writers or wr.LlmWriter
    n = workers or settings.draft_workers

    # ⓪ 준비 — 이 공고의 양식을 뜯고 종류를 가르고 읽는다
    if prepare:
        _prepare(source, external_id)

    # ① 조립 — 세션 안 · 읽기만
    with Session(engine) as s:
        facts = _company_facts(s, company_id)
        notice = _notice_material(s, source, external_id)
        plans = _read_plans(s, source, external_id)
        if not redo:
            done = _drafted_documents(s, company_id, external_id)
            report.skipped = sum(1 for p in plans if p.document_id in done)
            plans = [p for p in plans if p.document_id not in done]

    if not plans:
        return report

    for plan in plans:
        # **초안 한 벌이 한 추적이다.** 항목 67개가 한 화면에 뜬다(`trace.py`)
        with trace.session(f"draft:{company_id}:{source}:{external_id}#{plan.document_id}"):
            _build_one(
                plan, facts, notice, report,
                company_id=company_id, source=source, external_id=external_id,
                redo=redo, workers=n,
                allotter=allotter, make_writer=make_writer, checker=checker,
            )

    report.usage = _total_usage(allotter, checker)
    return report


def _total_usage(*objs: object) -> str:
    """배분·중복점검·집필을 합친다. **하나만 찍으면 나머지가 사라진다.**"""
    total = Usage()
    total.merge(_writer_usage)
    for o in objs:
        total.merge(_usage_of(o))
    _writer_usage.reset()
    return total.line() if total.calls else ""



def _build_one(  # noqa: PLR0913
    plan: _FormPlan,
    facts: dict[int, wr.FactMaterial],
    notice: tuple[tuple[str, str], ...],
    report: BuildReport,
    *,
    company_id: str,
    source: str,
    external_id: str,
    redo: bool,
    workers: int,
    allotter: al.Allotter,
    make_writer: Callable[[], wr.LlmWriter],
    checker: dd.LlmChecker,
) -> None:
    """양식 하나. **3단이 여기 다 들어 있다** — 조립은 부르는 쪽이 이미 했다."""
    views = [
        al.ItemView(
            index=i, number=it.number, title=it.title, instruction=it.instruction,
            places=it.places, places_optional=it.places_optional,
            summary_of_others=it.summary_of_others,
        )
        for i, it in enumerate(plan.items)
    ]
    fact_views = [
        al.FactView(id=f.id, place=f.place, text=f.text, source_type=f.source_type)
        for f in facts.values()
    ]
    # ①-b 배분 — 세션 밖. LLM 0 또는 1회
    allots = allotter.allot(views, fact_views, list(plan.pairs))

    # ② 호출 — 세션 밖 · 스레드
    # **필요한 자리가 0개면 안 부른다.** 상위 묶음은 자식이 쓴다 — 부르면
    # 재료가 없어서 빈 결과가 오고, 그것을 "못 채움" 과 구분할 수 없게 된다
    writable = {i for i, it in enumerate(plan.items) if it.places or it.places_optional}

    # **값 칸은 집필기를 거치지 않는다**(plan/24 T-0154). 답이 문단이 아니라 값
    # 하나인 자리라, 글을 쓰게 하면 신청서 칸에 문장이 앉고 모델이 값을 고쳐 쓸 틈이
    # 생긴다. 가르는 것은 문서 종류가 아니라 **자리**다 — 서술형 양식에도 `상시
    # 근로자 수` 가 있고 칸 서식에도 `협업계획 요약` 이 있다.
    values = {}
    for a in allots:
        if a.index not in writable:
            continue
        answer = _value_answer(plan.items[a.index], a, facts)
        if answer is not None:
            values[a.index] = answer

    jobs = [
        (a, wr.Material(
            number=plan.items[a.index].number,
            title=plan.items[a.index].title,
            instruction=plan.items[a.index].instruction,
            limit_text=plan.items[a.index].limit_text,
            facts=tuple(facts[i] for i in a.fact_ids if i in facts),
            notice=notice,
        ))
        for a in allots
        if a.index in writable and a.index not in values
    ]
    results = _run(jobs, make_writer, workers)
    results.update(values)

    # ③ 저장 — 세션 안 · ordinal 순
    with Session(engine) as s:
        draft = _draft_row(s, company_id, source, external_id, plan.document_id, redo=redo)
        if draft is None:
            return
        draft.allotment = {str(plan.items[a.index].row_id): list(a.fact_ids) for a in allots}
        draft.allotted_by = allotter.name if allotter.client is not None else "none"
        paras = _store_items(s, draft, plan, allots, results, facts, report)
        s.commit()

    report.clashes += _check_clashes(checker, plan, paras)
    report.forms += 1


def _prepare(source: str, external_id: str) -> None:
    """이 공고의 양식을 초안 직전에 뜯는다 (plan/24).

    **미리 전량을 뜯어 두지 않는다.** 코퍼스에서 구간 944개 중 451개가 공고문·
    안내문이었고 아무도 채우지 않는다. 공고 31,327건으로 넓히면 그 헛일이 그대로
    커지는데, 실제로 초안을 쓰는 것은 추천 몇 건이다.

    **늦춰도 안 느리다.** 구간을 가르는 일은 규칙이라 이 공고가 3ms, 코퍼스에서
    가장 큰 공고(56만 자)가 26ms 다. 뒤따르는 집필이 항목마다 LLM 을 부르므로
    이 몫은 사용자가 느낄 수 없다.

    **셋 다 이미 한 것을 건너뛴다.** 뜯기는 `document` 가 있으면, 판정은 `unknown`
    이 아니면, 읽기는 `needs_decided_by` 가 차 있으면 넘어간다 — 같은 공고를 두 번
    열어도 LLM 을 다시 부르지 않는다.

    **`finnect.extract` 를 함수 안에서 임포트한다.** 이 모듈을 읽기 경로가 물면
    파서가 딸려 오고, 그러면 로컬은 통과하고 배포본만 죽는다(ADR-0034 와 같은 함정).
    """
    from finnect.extract import service as ex

    ex.run(notice=(source, external_id))
    ex.classify_unknown(notice=(source, external_id))
    # **좌표를 따로 심는다.** `run()` 은 이미 뜯은 파일을 건너뛰는데, 좌표 코드가
    # 붙기 전에 뜯긴 파일이 그 자리에 남는다 — 다시 뜯으면 초안이 지워지므로
    # (FK CASCADE) 좌표만 갱신하는 길로 간다.
    ex.plant_anchors(notice=(source, external_id))
    read_forms(notice=(source, external_id))


def _value_answer(
    item: _ItemPlan,
    allot: al.Allotment,
    facts: dict[int, wr.FactMaterial],
) -> tuple[list[wr.Paragraph], int, str | None] | None:
    """값 칸이면 답을 만들고, 아니면 `None` (plan/24 T-0154 · ADR-0060 결정 6 옆자리).

    **자리가 전부 매칭 정보일 때만 값 칸이다.** 하나라도 서술 자리가 섞이면 글을
    써야 한다 — `기업소개` 가 `company_name` 과 `Company` 를 같이 요구하는 식이고,
    그때 값만 넣으면 상호 한 줄이 회사 소개 자리에 앉는다.

    **`place_kind` 를 여기서 다시 계산하지 않는다.** `item_need` 에 이미 저장돼
    있지만 세션 밖이라 못 읽고, `nd.PLACE_KIND` 가 그 값을 만든 바로 그 표다.

    재료가 없으면 `None` 을 준다 — **`blank` 로 떨어져 물어볼 자리가 되어야 한다.**
    여기서 빈 문단을 만들면 위키에 값이 없는 것이 「썼다」로 기록된다.
    """
    places = item.places + item.places_optional
    if not places or any(nd.PLACE_KIND.get(p) != "value" for p in places):
        return None

    by_place: dict[str, list[wr.FactMaterial]] = {}
    for i in allot.fact_ids:
        f = facts.get(i)
        if f is not None and f.value:
            by_place.setdefault(f.place, []).append(f)

    # **자리를 하나로 줄이지 않는다.** 한 칸이 값 둘을 요구하는 일이 흔하다 —
    # `사업자등록번호 (법인등록번호)` 가 그렇고 `대표자 정보` 가 이름과 생년월일을
    # 같이 묻는다. 하나만 고르면 **엉뚱한 쪽이 남는다**: 실측에서 `대표자 정보` 칸에
    # 이름 대신 `1992-07-04` 이 앉았다.
    #
    # 순서는 `item_need` 의 것이다 — LLM 이 칸 이름을 읽은 순서라 `(법인등록번호)`
    # 처럼 괄호로 뒤에 온 것이 뒤에 온다.
    texts: list[str] = []
    ids: list[int] = []
    for p in places:
        got = by_place.get(p)
        if not got:
            continue
        # 같은 자리에 값이 여럿이면 **시점이 가장 늦은 것**이다. `headcount` 가
        # 15·10·8 로 서 있고 칸에는 하나만 들어간다.
        best = max(got, key=lambda f: f.as_of or "")
        if best.value and best.value not in texts:
            texts.append(best.value)
            ids.append(best.id)

    if not texts:
        return None
    # **검증을 안 돌린다.** `verify()` 는 모델이 지어낸 숫자를 재료에 대조하는 것인데
    # 이 값은 재료에서 그대로 온 것이라 언제나 통과한다 — 돌리면 검사가 통과했다는
    # 사실이 아무 뜻도 없어진다.
    return [wr.Paragraph(text=" / ".join(texts), fact_ids=tuple(ids))], 0, None


def _run(
    jobs: list[tuple[al.Allotment, wr.Material]],
    make_writer: Callable[[], wr.LlmWriter],
    workers: int,
) -> dict[int, tuple[list[wr.Paragraph], int, str | None]]:
    """항목마다 집필한다. **세션이 열려 있지 않은 구간이다.**

    돌려주는 것은 `{항목 인덱스: (문단[], 확인 필요 수, 오류)}` 다. 예외를 여기서
    잡아 문자열로 바꾸는 이유는 **③에서 다시 던지면 트랜잭션이 통째로 죽어서**다.

    LLM 호출은 I/O 바운드라 스레드로 충분하다. `llm.py` 가 호출마다 `httpx.Client`
    를 열고 닫는 동기 코드라 그대로 얹힌다 — asyncio 로 가면 그 파일을 통째로 다시
    써야 하고 얻는 것이 없다.
    """
    out: dict[int, tuple[list[wr.Paragraph], int, str | None]] = {}
    if not jobs:
        return out
    tally = Usage()

    # **`contextvars` 는 스레드로 안 넘어간다.** 잡기 전에 떠서 워커 안에서 이어받는다 —
    # 안 하면 항목 67개가 한 추적으로 안 묶이고 따로 흩어진다
    parent = trace.current()

    def one(job: tuple[al.Allotment, wr.Material]):  # noqa: ANN202
        trace.adopt(parent)
        allot, material = job
        writer = make_writer()  # **워커마다 새로 만든다.** 집계가 안 섞인다
        try:
            paragraphs, err = writer.write(material), None
        except Exception as e:  # noqa: BLE001 — 항목 하나가 나머지를 안 죽인다
            paragraphs, err = [], f"{type(e).__name__}: {e}"[:500]
        # **집계를 여기서 걷는다.** 안 걷으면 워커와 함께 버려진다 — 실측에서
        # 초안 한 벌이 "호출 1회" 로 보고됐다(실제로는 12회)
        return allot.index, paragraphs, len(writer.unverified), err, _usage_of(writer)

    if workers <= 1:
        for job in jobs:
            i, paras, unv, err, used = one(job)
            out[i] = (paras, unv, err)
            tally.merge(used)
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            for fut in as_completed([pool.submit(one, j) for j in jobs]):
                i, paras, unv, err, used = fut.result()
                out[i] = (paras, unv, err)
                tally.merge(used)
    _writer_usage.merge(tally)
    return out


#: 집필기들이 쓴 토큰. **워커마다 새로 만들어 버리니 여기 걷어 둔다**
_writer_usage = Usage()


def _usage_of(writer: object) -> Usage:
    c = getattr(writer, "client", None)
    return getattr(c, "usage", None) or Usage()


def _read_plans(s: Session, source: str, external_id: str) -> list[_FormPlan]:
    """공고에 붙은 **채울 수 있는 양식**을 평범한 데이터로 읽는다(`WRITABLE`).

    **공고와 문서를 잇는 표를 만들지 않았다.** 조인으로 푼다(ADR-0022).
    """
    docs = s.execute(
        select(Document)
        .join(AttachmentFile, AttachmentFile.sha256 == Document.sha256)
        .join(Attachment, Attachment.url == AttachmentFile.url)
        .where(
            Attachment.source == source,
            Attachment.external_id == external_id,
            Document.kind.in_(WRITABLE_KINDS),
        )
        .order_by(Attachment.position, Document.seq)
    ).scalars().all()

    out: list[_FormPlan] = []
    seen: set[int] = set()
    for doc in docs:
        if doc.id in seen:
            continue
        seen.add(doc.id)

        rows = s.scalars(
            select(DocumentItem)
            .where(DocumentItem.document_id == doc.id)
            .order_by(DocumentItem.ordinal)
        ).all()
        if not rows:
            continue

        ids = [r.id for r in rows]
        req: dict[int, list[str]] = {}
        opt: dict[int, list[str]] = {}
        for n in s.scalars(select(ItemNeed).where(ItemNeed.document_item_id.in_(ids))).all():
            (req if n.required else opt).setdefault(n.document_item_id, []).append(n.place)

        pos = {r.id: i for i, r in enumerate(rows)}
        pairs = tuple(
            (pos[o.a_item_id], pos[o.b_item_id])
            for o in s.scalars(
                select(ItemOverlap).where(ItemOverlap.document_id == doc.id)
            ).all()
            if o.a_item_id in pos and o.b_item_id in pos
        )
        out.append(
            _FormPlan(
                document_id=doc.id,
                doc_title=doc.title,
                items=tuple(
                    _ItemPlan(
                        row_id=r.id,
                        ordinal=r.ordinal,
                        number=r.number,
                        title=r.title,
                        instruction=r.instruction,
                        limit_text=r.limit_text,
                        places=tuple(req.get(r.id, ())),
                        places_optional=tuple(opt.get(r.id, ())),
                        summary_of_others=bool(r.summary_of_others),
                    )
                    for r in rows
                ),
                pairs=pairs,
            )
        )
    return out


def _notice_material(s: Session, source: str, external_id: str) -> tuple[tuple[str, str], ...]:
    """공고가 준 값 (plan/16 구멍 1).

    **여기가 비어 있으면 F6-12 가 자기 자신을 막는다.** F6-12 는 "금액·자격·마감일·
    고유명사는 **공고 데이터와** 근거 청크에서 온 것만" 이라고 허용했는데, 공고
    데이터를 안 넘기면 `verify()` 가 지원금액과 마감일을 지운다.

    `notice` 뷰만 읽는다 — 출처별 표를 직접 읽으면 매핑이 둘이 되고, 그 매핑의
    정본은 `views.py` 다(CLAUDE.md).
    """
    row = s.execute(
        select(
            Notice.title, Notice.organization, Notice.supervisor, Notice.category,
            Notice.apply_period_raw, Notice.apply_start, Notice.apply_end, Notice.summary,
        ).where(Notice.source == source, Notice.external_id == external_id)
    ).first()
    if row is None:
        return ()

    title, org, sup, cat, raw, start, end, summary = row
    period = raw or " ~ ".join(str(d) for d in (start, end) if d)
    pairs = [
        ("사업명", title), ("수행기관", org), ("주관기관", sup),
        ("분야", cat), ("접수기간", period),
        # **공고 본문이다.** 지원금액이 값으로 오는 필드가 없어서 여기서만 나온다
        ("공고 내용", (summary or "")[:NOTICE_SUMMARY_CHARS]),
    ]
    return tuple((k, v) for k, v in pairs if v)


def _company_facts(s: Session, company_id: str) -> dict[int, wr.FactMaterial]:
    """집필이 쓸 재료 전부. **트랙 둘을 여기서 합친다**(plan/22 T-0134).

    트랙 A(노드에 앉은 사실)와 트랙 B(매칭 정보 열다섯)가 표가 다르고 근거 표도 다르다.
    합치는 자리가 여기 하나인 이유는 **아래가 전부 재료 id 하나로 도는** 배관이라서다 —
    배분·집필·중복 점검이 정수 하나만 본다(`refs.py`).

    **트랙 B 를 안 읽으면 조용히 틀린다.** `item_need.place` 가 `headcount` 를 가리킬 수
    있는데(`needs.PLACES`) 재료에 그 자리가 영영 안 나와서 **위키에 값이 있는데도**
    「못 채웠어요」가 된다. 오류가 아니라 빈칸으로 나오는 종류다.

    **근거 없는 사실은 애초에 없다**(ADR-0014).
    """
    out: dict[int, wr.FactMaterial] = {}

    rows = s.execute(
        select(WikiFact, WikiNode.path)
        .join(WikiNode, WikiNode.id == WikiFact.node_id)
        .where(
            WikiFact.company_id == company_id,
            or_(WikiFact.status.is_(None), WikiFact.status != "superseded"),
        )
    ).all()
    for f, path in rows:
        ev = s.execute(
            select(WikiEvidence.chunk_id, WikiEvidence.quote).where(
                WikiEvidence.fact_id == f.id
            )
        ).all()
        out[f.id] = wr.FactMaterial(
            id=f.id, place=path, text=f.text,
            quotes=tuple(q for _, q in ev),
            chunk_ids=tuple(c for c, _ in ev),
            source_type=f.source_type,
        )

    #: 트랙 B. **`place` 가 경로가 아니라 key 다** — `item_need.place` 가 그 이름으로
    #: 가리키고 `allot._index` 가 마디 하나짜리 경로로 받는다.
    #:
    #: **`superseded` 만 뺀다.** 트랙 A 와 같은 규칙이라 `conflict` 는 둘 다 재료로
    #: 간다 — 어느 쪽이 맞는지는 집필이 정할 일이 아니고, 화면이 충돌로 물어볼 자리다
    #: (T-0131). 여기서 하나를 고르면 **고른 근거가 어디에도 안 남는다.**
    values = s.scalars(
        select(CompanyValue).where(
            CompanyValue.company_id == company_id,
            CompanyValue.status != "superseded",
        )
    ).all()
    for v in values:
        ev = s.execute(
            select(ValueEvidence.chunk_id, ValueEvidence.quote).where(
                ValueEvidence.value_id == v.id
            )
        ).all()
        out[refs.value_ref(v.id)] = wr.FactMaterial(
            id=refs.value_ref(v.id),
            place=v.key,
            #: **라벨을 붙여서 넣는다.** 저장값(`120000000`)만 주면 집필이 단위를
            #: 지어낸다. 단위를 붙이는 자리는 `profile.display()` 하나다
            text=_value_text(v),
            quotes=tuple(q for _, q in ev),
            chunk_ids=tuple(c for c, _ in ev),
            source_type=v.source_type,
            #: 값 칸이 그대로 옮긴다. **라벨을 뺀 것이 `text` 와 다른 점이다**
            value=profile.display(v.key, v.value),
            as_of=v.as_of.isoformat() if v.as_of else None,
        )
    return out


def _value_text(v: CompanyValue) -> str:
    """매칭 정보 한 칸을 집필이 읽는 문장으로. **저장값은 안 건드린다.**"""
    spec = profile.PROFILE_KEYS.get(v.key)
    label = spec.label if spec else v.key
    body = f"{label} {profile.display(v.key, v.value)}"
    if v.qualifier:
        body = f"{body} ({v.qualifier})"
    return f"{body} — {v.as_of.isoformat()} 기준" if v.as_of else body


def _store_items(  # noqa: PLR0913
    s: Session,
    draft: Draft,
    plan: _FormPlan,
    allots: list[al.Allotment],
    results: dict[int, tuple[list[wr.Paragraph], int, str | None]],
    facts: dict[int, wr.FactMaterial],
    report: BuildReport,
) -> list[dd.ParaView]:
    """`ordinal` 순으로 깐다.

    **순서를 고정하는 것이 요점이다.** 같은 입력에서 같은 초안이 나와야 `--redo` 로
    무엇이 바뀌었는지 바이트로 본다 — 위키 마크다운에 시각을 안 넣은 것과 같은 이유다.
    """
    out: list[dd.ParaView] = []
    by_index = {a.index: a for a in allots}

    for index, it in enumerate(plan.items):
        paragraphs, unverified, error = results.get(index, ([], 0, None))
        report.items += 1
        report.unverified += unverified

        # **`allot` 이 계산한 것을 그대로 쓴다. 다시 세지 않는다.**
        # F6-6 은 "위키에 정보가 없어 못 쓴 자리" 다. 배분에서 못 받은 것과 다르다 —
        # 다른 항목이 그 사실을 맡았으면 위키에는 있는 것이고, 그건 못 채움이 아니다.
        allot = by_index.get(index)
        missing = list(allot.missing) if allot else list(it.places)
        for place in missing:
            report.missing[place] = report.missing.get(place, 0) + 1

        item = DraftItem(
            draft_id=draft.id,
            document_item_id=it.row_id,
            ordinal=it.ordinal,
            missing=missing,
            missing_optional=list(allot.missing_optional) if allot else [],
        )
        s.add(item)
        s.flush()

        if error:
            item.error = error
            report.failed += 1
            continue
        if not paragraphs:
            # **셋을 가른다.** 같은 이름으로 부르면 화면이 물어볼 자리를 잘못 가리킨다
            if not (it.places or it.places_optional):
                item.status = str(DraftItemStatus.NO_NEEDS)
                report.no_needs += 1
            elif missing:
                item.status = str(DraftItemStatus.BLANK)   # 진짜 F6-6
                report.blank += 1
            elif not (allot and allot.fact_ids):
                # 위키에는 있는데 이 항목이 못 받았다 — 물어볼 자리가 아니다
                item.status = str(DraftItemStatus.YIELDED)
                report.yielded += 1
            else:
                # **재료를 받고도 글이 안 나왔다.** 집필이 실패한 자리다
                item.status = str(DraftItemStatus.UNWRITTEN)
                report.unwritten += 1
            continue

        item.body = "\n\n".join(p.text for p in paragraphs)
        item.status = _status(paragraphs, facts)
        item.written_by = f"llm/{settings.openai_model}"
        report.drafted += 1
        report.paragraphs += len(paragraphs)

        # 분량 검사 (구멍 2). **저장하지 않는다** — 읽을 때마다 만드는 값이다
        check = limits.check(item.body, it.limit_text)
        if check.verdict == "over":
            report.over_limit += 1
        elif check.verdict == "unmeasurable":
            report.unmeasured += 1

        for n, p in enumerate(paragraphs):
            chunks: list[int] = []
            for fid in p.fact_ids:
                f = facts[fid]
                chunks.extend(f.chunk_ids)
                #: **트랙마다 표가 다르다**(T-0134). 부호가 어느 표인지 말한다
                cid = f.chunk_ids[0] if f.chunk_ids else None
                row = (
                    DraftValueEvidence(
                        draft_item_id=item.id, paragraph=n,
                        value_id=refs.value_id(fid), chunk_id=cid,
                        source_type=f.source_type,
                    )
                    if refs.is_value(fid)
                    else DraftEvidence(
                        draft_item_id=item.id, paragraph=n, fact_id=fid,
                        chunk_id=cid, source_type=f.source_type,
                    )
                )
                s.add(row)
            out.append(
                dd.ParaView(
                    item_index=index, paragraph=n, text=p.text,
                    chunk_ids=tuple(chunks), fact_ids=p.fact_ids,
                )
            )
    return out


def _status(paragraphs: list[wr.Paragraph], facts: dict[int, wr.FactMaterial]) -> str:
    """사용자 답변이 들어간 문단이 있으면 `answered` 다(ADR-0028 5번)."""
    used = {i for p in paragraphs for i in p.fact_ids}
    if any(facts[i].source_type == str(SourceType.USER_STATED) for i in used if i in facts):
        return str(DraftItemStatus.ANSWERED)
    return str(DraftItemStatus.DRAFTED)


def _check_clashes(checker: dd.LlmChecker, plan: _FormPlan, paras: list[dd.ParaView]) -> int:
    """겹침을 찾는다. **코드가 먼저, 그다음 LLM 이다.**

    지금은 **세기만 한다.** 겹친 항목을 다시 쓰는 것은 화면이 붙어야 뜻이 있다 —
    무엇이 겹쳤는지 사람이 보고 판단할 자리가 없으면 자동 재작성은 소리 없이 본문을
    바꾸는 일이 된다(F1-5-5).
    """
    summary = frozenset(i for i, it in enumerate(plan.items) if it.summary_of_others)
    found = dd.by_chunk(paras, summary=summary)
    if len(paras) >= 2:
        found += checker.check(paras, summary=summary, known=found)
    return len(found)


def _drafted_documents(s: Session, company_id: str, external_id: str) -> set[int]:
    """이 회사가 이 공고에 대해 **이미 초안을 가진** 문서들 (T-0161).

    `_draft_row` 도 같은 것을 보지만 저기는 저장 직전이다. **거기서만 거르면 늦다** —
    배분과 집필이 끝난 뒤라 버리는 것이 결과가 아니라 이미 쓴 돈이다.
    """
    return set(
        s.scalars(
            select(Draft.document_id).where(
                Draft.company_id == company_id,
                Draft.notice_id == external_id,
            )
        )
    )


def _draft_row(  # noqa: PLR0913
    s: Session,
    company_id: str,
    source: str,
    external_id: str,
    document_id: int,
    *,
    redo: bool,
) -> Draft | None:
    """이미 있으면 안 다시 쓴다. **`redo` 면 항목만 갈고 초안 행은 남긴다.**

    **`redo` 는 사람이 고친 글도 지운다**([ADR-0062](
    ../../../docs/adr/0062-다시-쓰기가-고친-글을-지우되-먼저-알린다.md)). `edited_body`
    가 `draft_item` 에 살아서 이 `delete` 에 같이 쓸려 간다 — ADR-0055 는 **집필기가
    사람 글을 덮지 않는다**는 규칙이고, 사람이 스스로 「새로 써 줘」를 누른 것은 그
    자리가 아니다. 대신 **화면이 무엇이 사라지는지 먼저 말하고 누르게 한다.**

    **이 함수가 조용히 지우지 않게 하는 것이 화면 쪽 책임이다.** 여기서 고친 항목만
    남기면 새 글과 옛 글이 한 문서에 섞이는데, 그 둘의 근거가 서로 다른 사실을
    가리켜 F6-13 의 대조가 문서 단위로는 안 맞게 된다.
    """
    row = s.scalar(
        select(Draft).where(
            Draft.company_id == company_id,
            Draft.notice_id == external_id,
            Draft.document_id == document_id,
        )
    )
    if row is None:
        row = Draft(
            company_id=company_id, notice_id=external_id,
            source=source, document_id=document_id,
        )
        s.add(row)
        s.flush()
        return row
    if not redo:
        return None
    s.execute(delete(DraftItem).where(DraftItem.draft_id == row.id))
    return row
