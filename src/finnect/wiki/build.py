"""청크 → 사실 → 노드. **파이프라인의 아래 절반이다**(plan/12 T-0045 · T-0046).

`service.py` 가 파일 → 청크까지 하고, 여기가 그 뒤를 받는다. 순서는 이렇다.

    청크  →  추출(포트)  →  라우팅(표)  →  근거 연결  →  병합·충돌
             ↑ LLM 자리      ↑ 결정론      ↑ 결정론      ↑ 결정론

**LLM 은 첫 칸 하나뿐이고 지금은 스텁이다**(ADR-0031). 나머지 셋에 모델이 안 들어가는
것이 요점이다 — 그래야 같은 파일을 두 번 넣어도 같은 배치가 나온다.

## 파일별로 독립이다

`service.ingest_files` 와 같다(F1-1-8). 한 파일에서 추출이 실패해도 나머지로 위키가
선다. 스텁이 모르는 파일이면 그 파일만 `chunked` 로 남고 이유가 따라 나온다.

## 근거를 못 찾은 사실은 버린다

사실이 든 `anchor` 를 담은 청크가 없으면 **그 사실을 세우지 않고 문제로 보고한다.**
근거 없는 값을 위키에 올리면 ADR-0014 가 막으려던 바로 그것이 된다 — 집필이 값만
들고 문단을 쓰고 모델이 나머지를 지어낸다. 조용히 넘어가지 않는다.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.models import (
    Chunk,
    SourceType,
    UserFile,
    UserFileStatus,
    WikiEvidence,
    WikiFact,
    WikiPlace,
)
from finnect.wiki import markdown, merge, topics
from finnect.wiki.extract import FactExtractor, FileView, UnknownFile, get_extractor


@dataclass(slots=True)
class BuildReport:
    company_id: str = ""
    files: int = 0
    #: 사실이 나온 파일
    built: int = 0
    #: 스텁이 모르거나 청크가 없어 건너뛴 파일
    skipped: int = 0
    facts: int = 0
    #: 이미 있어서 근거만 더 붙은 것
    merged: int = 0
    evidence: int = 0
    slots: int = 0
    nodes: int = 0
    uncategorized: int = 0
    conflicts: int = 0
    status: Counter[str] = field(default_factory=Counter)
    #: (파일명, 사유). **조용히 버리지 않는다**
    problems: list[tuple[str, str]] = field(default_factory=list)


def _squash(s: str) -> str:
    """공백을 전부 지운다. 앵커를 청크에서 찾을 때만 쓴다.

    파서마다 줄바꿈과 들여쓰기가 달라서 원문 문자열이 그대로 안 맞는다. 공백을 지우면
    **경계는 유지한 채** 표기 차이만 무시된다.
    """
    return "".join(s.split())


def build_company(
    session: Session,
    company_id: str,
    *,
    extractor: FactExtractor | None = None,
) -> BuildReport:
    """한 회사의 위키를 세운다. **파일별로 독립이고 마지막에 한 번 상태를 매긴다.**

    상태(current/superseded/conflict)는 **전체를 봐야** 정해진다. 어느 시점이 가장
    늦은지는 파일 하나만 봐서는 모른다.
    """
    ex = extractor or get_extractor()
    report = BuildReport(company_id=company_id)

    # **`done` 을 다시 읽지 않는다.** 2026-08-21 실측 — `--build` 한 번에 `c_dasiro` 의
    # 사실이 187 → 291 이 됐다(node +93 · slot +10).
    #
    # 스텁 때는 안전했다. 같은 파일에서 같은 사실 118건이 나오고 `dedupe_key` 가 같아서
    # **아무것도 안 늘었다.** LLM 으로 바뀌자 깨졌다 — 같은 문서를 매번 다르게 쪼개서
    # 키가 달라지고 **다른 사실로 앉는다.** 서술 노드의 분해 단위가 흔들리는 그 성질이다.
    #
    # 다시 읽는 길은 `--rebuild` 다. `clear()` 가 `done` 을 `chunked` 로 되돌리므로
    # 여기가 `chunked` 만 봐도 재추출이 된다 — **지우고 세우니 늘어나지 않는다.**
    files = session.scalars(
        select(UserFile)
        .where(
            UserFile.company_id == company_id,
            UserFile.status == UserFileStatus.CHUNKED,
        )
        .order_by(UserFile.filename)
    ).all()
    report.files = len(files)

    for uf in files:
        try:
            _build_file(session, ex, uf, report)
        except UnknownFile as e:
            _shelve(uf, report, str(e))
        except Exception as e:  # noqa: BLE001 — 이 파일만 건너뛰고 다음으로 간다
            _shelve(uf, report, f"{type(e).__name__}: {e}")

    report.conflicts = restate(session, company_id)

    counts = session.execute(
        select(WikiFact.place_kind, WikiFact.place).where(WikiFact.company_id == company_id)
    ).all()
    report.slots = len({p for k, p in counts if k == WikiPlace.SLOT})
    report.nodes = len({p for k, p in counts if k == WikiPlace.NODE})
    report.uncategorized = sum(1 for k, _ in counts if k == WikiPlace.UNCATEGORIZED)
    for uf in files:
        report.status[uf.status] += 1
    return report


def _shelve(uf: UserFile, report: BuildReport, why: str) -> None:
    """추출이 실패한 파일을 **`chunked` 로 되돌린다.** 이 모듈 첫 문단이 약속한 상태다.

    `_build_file` 이 추출을 부르기 전에 `extracting` 으로 올리는데, 터진 채 두면 그 파일이
    `build_company` 의 `chunked`/`done` 목록에서 빠져 **다음 `--build` 에 아예 안 보인다.**
    추출기가 LLM 으로 바뀌어도 영영 안 걸리고, 다시 올려도 `duplicate` 로 튕겨
    (`service.ingest_file`) 상태를 고칠 길이 없다. 2026-08-18 실측 — 스텁이 모르는 파일
    하나를 넣고 `--rebuild` 하니 `읽은 파일 0 / 0` 이었다.

    되돌리는 값이 `done` 이 아니라 `chunked` 인 것이 요점이다. `--rebuild` 는 사실을 먼저
    지우고 다시 세우니(`clear`), 실패한 뒤 `done` 으로 두면 **사실이 없는데 다 됐다고
    말하는 행**이 남는다.
    """
    uf.status = UserFileStatus.CHUNKED
    #: **이유를 DB 에 남긴다**(T-0093). 전에는 `BuildReport` 에만 담겨서 CLI 를 돌린
    #: 사람만 봤고, 화면은 "사실을 못 뽑았어요" 만 말했다. 2026-08-21 그것 때문에
    #: 배포가 스텁으로 돌고 있다는 것을 찾는 데 오래 걸렸다.
    uf.extract_error = why
    report.skipped += 1
    report.problems.append((uf.filename, why))


def _build_file(
    session: Session, ex: FactExtractor, uf: UserFile, report: BuildReport
) -> None:
    chunks = session.scalars(
        select(Chunk).where(Chunk.user_file_id == uf.id).order_by(Chunk.ordinal)
    ).all()
    if not chunks:
        raise UnknownFile(f"{uf.filename}: 청크가 없어요")

    uf.status = UserFileStatus.EXTRACTING
    view = FileView(
        sha256=uf.sha256,
        filename=uf.filename,
        chunks=tuple((c.ordinal, c.text) for c in chunks),
    )
    facts = ex.extract(view)

    # 앵커로 청크를 찾는다. **청크 번호를 사실에 박지 않는 이유가 이것이다** —
    # `--rechunk` 로 경계가 바뀌어도 앵커는 그대로다.
    squashed = [(c, _squash(c.text)) for c in chunks]
    uf.status = UserFileStatus.LINKING

    missing = 0
    for fact in facts:
        needle = _squash(fact.anchor)
        hit = next((c for c, body in squashed if needle and needle in body), None)
        if hit is None:
            missing += 1
            report.problems.append(
                (uf.filename, f"근거를 못 찾아 버렸어요 — {fact.anchor[:40]!r}")
            )
            continue

        spot = merge.place(fact)
        key = merge.dedupe_key(fact, spot)
        row = session.scalar(
            select(WikiFact).where(WikiFact.company_id == uf.company_id, WikiFact.dedupe_key == key)
        )
        if row is None:
            row = WikiFact(
                company_id=uf.company_id,
                place_kind=spot.kind,
                place=spot.name,
                dedupe_key=key,
                topic=fact.topic,
                text=fact.text if spot.ok else f"{fact.text}  [{spot.reason}]",
                slot_key=fact.key,
                value=fact.value,
                qualifier=fact.qualifier,
                as_of=merge.as_of_for(spot.name, fact.as_of) if spot.kind == "slot" else None,
                source_type=str(SourceType.DOCUMENT),
                extractor=ex.name,
            )
            session.add(row)
            session.flush()
            report.facts += 1
        else:
            report.merged += 1

        exists = session.scalar(
            select(WikiEvidence).where(
                WikiEvidence.fact_id == row.id, WikiEvidence.chunk_id == hit.id
            )
        )
        if exists is None:
            session.add(
                WikiEvidence(
                    company_id=uf.company_id,
                    fact_id=row.id,
                    chunk_id=hit.id,
                    user_file_id=uf.id,
                    quote=fact.anchor,
                )
            )
            report.evidence += 1

    # **근거를 못 찾은 것이 있으면 done 이 아니다.** 사람이 봐야 한다.
    uf.status = UserFileStatus.NEEDS_REVIEW if missing else UserFileStatus.DONE
    #: **지난 실패를 지운다.** 안 지우면 추출기를 바꿔 성공한 뒤에도 화면이 옛 이유를
    #: 계속 말한다 — `_shelve` 가 상태를 되돌려 주는 것과 짝이다
    uf.extract_error = None
    report.built += 1


def restate(session: Session, company_id: str) -> int:
    """정형 슬롯에 상태를 다시 매긴다. **한 회사 전부를 한 번에 본다.**

    돌려주는 값은 충돌 건수다. 부분만 보고 매기면 틀린다 — 어느 시점이 가장 늦은지는
    전체를 봐야 안다.
    """
    rows = session.scalars(
        select(WikiFact).where(
            WikiFact.company_id == company_id, WikiFact.place_kind == WikiPlace.SLOT
        )
    ).all()
    claims = [
        merge.Claim(slot=r.place, qualifier=r.qualifier, as_of=r.as_of, value=r.value or "")
        for r in rows
    ]
    verdict = merge.decide(claims)
    conflicts = 0
    for row, claim in zip(rows, claims, strict=True):
        row.status = verdict[claim]
        conflicts += row.status == merge.Status.CONFLICT
    return conflicts


def clear(session: Session, company_id: str) -> int:
    """세운 위키를 지운다. **원본과 청크는 남는다** — 추출기를 바꿔 다시 돌릴 때 쓴다."""
    n = len(
        session.scalars(select(WikiFact).where(WikiFact.company_id == company_id)).all()
    )
    session.execute(sa_delete(WikiEvidence).where(WikiEvidence.company_id == company_id))
    session.execute(sa_delete(WikiFact).where(WikiFact.company_id == company_id))
    for uf in session.scalars(
        select(UserFile).where(
            UserFile.company_id == company_id,
            UserFile.status.in_([UserFileStatus.DONE, UserFileStatus.NEEDS_REVIEW]),
        )
    ):
        if uf.chunk_count:
            uf.status = UserFileStatus.CHUNKED
    return n


@dataclass(frozen=True, slots=True)
class SlotView:
    """화면에 넘길 슬롯 하나. 값 하나와 이력·충돌이 같이 온다."""

    name: str
    label: str
    eligibility: bool
    #: current 인 주장들. 충돌이면 여럿이다
    current: list[WikiFact]
    #: superseded. 최신순
    history: list[WikiFact]

    @property
    def conflicted(self) -> bool:
        return any(f.status == merge.Status.CONFLICT for f in self.current)


def read_slots(session: Session, company_id: str) -> list[SlotView]:
    """정형 슬롯을 `topics.SLOTS` 순서로 편다. **빈 슬롯도 자리를 지킨다** — 물어야 한다."""
    rows = session.scalars(
        select(WikiFact)
        .where(WikiFact.company_id == company_id, WikiFact.place_kind == WikiPlace.SLOT)
        .order_by(WikiFact.place, WikiFact.qualifier, WikiFact.as_of)
    ).all()

    out = []
    for name, spec in topics.SLOTS.items():
        mine = [r for r in rows if r.place == name]
        cur = [r for r in mine if r.status in (merge.Status.CURRENT, merge.Status.CONFLICT)]
        old = [r for r in mine if r.status == merge.Status.SUPERSEDED]
        out.append(
            SlotView(
                name=name,
                label=spec.label,
                eligibility=spec.eligibility,
                current=cur,
                history=sorted(old, key=lambda r: (r.as_of or dt.date.min), reverse=True),
            )
        )
    return out


def read_orbit(session: Session, company_id: str) -> list[markdown.NodeView]:
    """궤도 열다섯을 채워서 돌려준다. **빈 자리도 돌려준다.**

    비어 있는 것도 사실이고 물어야 할 자리다(ADR-0028). 화면이 자리를 지우면 사용자는
    무엇이 없는지 모른다 — `DESIGN.md` §7-5 가 "데이터 없음으로 끝내지 않는다"고 한 것.

    쿼리를 자리마다 돌리지 않는다. 사실과 근거를 한 번씩 읽고 파이썬에서 묶는다 —
    열다섯 자리에 조인 서른 번은 화면 하나에 너무 많다.
    """
    facts = session.scalars(
        select(WikiFact)
        .where(WikiFact.company_id == company_id)
        .order_by(WikiFact.place, WikiFact.qualifier, WikiFact.as_of, WikiFact.id)
    ).all()

    rows = session.execute(
        select(WikiEvidence.fact_id, UserFile.filename, Chunk.page, WikiEvidence.quote)
        .join(Chunk, Chunk.id == WikiEvidence.chunk_id)
        .join(UserFile, UserFile.id == WikiEvidence.user_file_id)
        .where(WikiEvidence.company_id == company_id)
        .order_by(UserFile.filename, Chunk.ordinal)
    ).all()

    by_fact: dict[int, list[markdown.Evidence]] = {}
    for fact_id, filename, page, quote in rows:
        by_fact.setdefault(fact_id, []).append(markdown.Evidence(filename, page, quote))

    slot_facts: dict[str, list[WikiFact]] = {}
    node_facts: dict[str, list[WikiFact]] = {}
    for f in facts:
        if f.place_kind == WikiPlace.SLOT:
            slot_facts.setdefault(f.place, []).append(f)
        elif f.place_kind == WikiPlace.NODE:
            node_facts.setdefault(f.place, []).append(f)

    out = []
    for key, spot in topics.ORBIT.items():
        values = tuple(
            markdown.Value(
                slot=f.place,
                label=topics.SLOTS[f.place].label,
                value=f.value or "",
                qualifier=f.qualifier,
                as_of=f.as_of.isoformat() if f.as_of else None,
                status=f.status or merge.Status.CURRENT,
                evidence=tuple(by_fact.get(f.id, ())),
            )
            for slot in spot.slots
            for f in slot_facts.get(slot, [])
        )
        statements = tuple(
            markdown.Statement(text=f.text, topic=f.topic, evidence=tuple(by_fact.get(f.id, ())))
            for f in (node_facts.get(spot.node, []) if spot.node else [])
        )
        out.append(
            markdown.NodeView(
                key=key,
                label=spot.label,
                kind=spot.kind,
                sector=topics.SECTORS[spot.sector],
                company_id=company_id,
                values=values,
                statements=statements,
            )
        )
    return out


def read_files(session: Session, company_id: str) -> list[tuple[UserFile, list[str]]]:
    """올린 파일과 **그 파일이 만든 자리**(F1-4-7).

    "어느 파일을 지우면 무엇이 사라지나"를 보여 주는 자리다. 읽히지 않은 파일도 그대로
    돌려준다 — 실패를 안 보여 주면 사용자는 올린 줄 안다.
    """
    files = session.scalars(
        select(UserFile).where(UserFile.company_id == company_id).order_by(UserFile.filename)
    ).all()

    rows = session.execute(
        select(WikiEvidence.user_file_id, WikiFact.place_kind, WikiFact.place)
        .join(WikiFact, WikiFact.id == WikiEvidence.fact_id)
        .where(WikiEvidence.company_id == company_id)
    ).all()

    #: 사실이 앉은 자리(슬롯·노드)를 궤도 자리로 되돌린다. 화면이 궤도로 말하기 때문이다
    home: dict[tuple[str, str], str] = {}
    for key, spot in topics.ORBIT.items():
        for slot in spot.slots:
            home[(WikiPlace.SLOT, slot)] = key
        if spot.node:
            home[(WikiPlace.NODE, spot.node)] = key

    made: dict[int, set[str]] = {}
    for file_id, kind, place in rows:
        spot_key = home.get((kind, place))
        if spot_key:
            made.setdefault(file_id, set()).add(spot_key)

    return [
        (uf, sorted(made.get(uf.id, set()), key=list(topics.ORBIT).index)) for uf in files
    ]
