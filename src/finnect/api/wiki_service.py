"""사업 위키 조회(S7). **읽기만 한다.**

`wiki/build.py` 가 이미 DB → `NodeView` 를 하고 있어서 여기는 그걸 응답 모양으로 옮기는
얇은 층이다. 조인을 여기서 다시 짜지 않는다 — 두 벌이 되면 한쪽만 고쳐지는 날이 온다.

**`attach.service` · `ingest.service` 를 임포트하지 않는다.** 저 둘이 httpx 와 파서를
끌고 오는데 `requirements.txt` 가 그것들을 뺐다. `wiki.build` 는 `wiki.markdown` 과
`wiki.topics` 만 끌고 오고 둘 다 순수 파이썬이다 — `wiki.service`(해독)는 파서를 쓰므로
**여기서 부르면 안 된다.**
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finnect.api.wiki_schemas import (
    EvidenceOut,
    FileProgressOut,
    ProgressOut,
    StatementOut,
    StepOut,
    ValueOut,
    WikiFileOut,
    WikiNodeOut,
    WikiOut,
)
from finnect.models import WikiFact, WikiPlace
from finnect.wiki import build, markdown, merge, progress, topics


def get_wiki(session: Session, company_id: str) -> WikiOut:
    """S7 한 장. **위키가 없어도 궤도 열다섯을 돌려준다.**

    빈 화면을 "데이터 없음"으로 끝내지 않는 것이 `DESIGN.md` §7-5 다. 자리가 있어야
    사용자가 무엇이 없는지 알고, 무엇을 올려야 하는지 안다.
    """
    nodes = build.read_orbit(session, company_id)
    files = build.read_files(session, company_id)

    conflicts = session.scalar(
        select(func.count())
        .select_from(WikiFact)
        .where(WikiFact.company_id == company_id, WikiFact.status == merge.Status.CONFLICT)
    )
    uncategorized = session.scalar(
        select(func.count())
        .select_from(WikiFact)
        .where(
            WikiFact.company_id == company_id,
            WikiFact.place_kind == WikiPlace.UNCATEGORIZED,
        )
    )
    extractor = session.scalar(
        select(WikiFact.extractor).where(WikiFact.company_id == company_id).limit(1)
    )

    return WikiOut(
        company_id=company_id,
        nodes=[_node(n) for n in nodes],
        files=[
            WikiFileOut(
                filename=uf.filename,
                ext=uf.ext,
                byte_size=uf.byte_size,
                status=uf.status,
                parse_status=uf.parse_status,
                parser=uf.parser,
                parse_error=uf.parse_error,
                chunk_count=uf.chunk_count,
                page_count=uf.page_count,
                nodes=made,
            )
            for uf, made in files
        ],
        sectors=dict(topics.SECTORS),
        filled=sum(n.filled for n in nodes),
        total=len(nodes),
        conflicts=conflicts or 0,
        uncategorized=uncategorized or 0,
        extractor=extractor,
    )


def get_markdown(session: Session, company_id: str) -> str | None:
    """위키 전부를 마크다운 한 덩어리로. 아무것도 없으면 `None`.

    **저장된 파일을 읽는 것이 아니다.** 매번 만든다 — `wiki/markdown.py` 참고.
    """
    nodes = build.read_orbit(session, company_id)
    if not any(n.filled for n in nodes):
        return None
    return markdown.bundle(nodes)


def _node(n: markdown.NodeView) -> WikiNodeOut:
    spot = topics.ORBIT[n.key]
    return WikiNodeOut(
        key=n.key,
        label=n.label,
        kind=n.kind,
        sector=spot.sector,
        eligibility=any(topics.SLOTS[s].eligibility for s in spot.slots),
        values=[
            ValueOut(
                slot=v.slot,
                label=v.label,
                value=v.value,
                display=topics.display(v.slot, v.value),
                qualifier=v.qualifier,
                as_of=v.as_of,
                status=v.status,
                evidence=[_evidence(e) for e in v.evidence],
            )
            for v in n.values
        ],
        statements=[
            StatementOut(
                text=s.text,
                topic=s.topic,
                evidence=[_evidence(e) for e in s.evidence],
            )
            for s in n.statements
        ],
        source_count=n.source_count,
        filled=n.filled,
        conflicted=n.conflicted,
        markdown=markdown.render(n),
    )


def _evidence(e: markdown.Evidence) -> EvidenceOut:
    return EvidenceOut(filename=e.filename, page=e.page, quote=e.quote)


def get_progress(session: Session, company_id: str, *, running: bool) -> ProgressOut:
    """구축 진행 한 장(S1 · SPEC F1-1-9 · plan/15 T-0060).

    **`running` 을 인자로 받는다.** 값은 `ingest.jobs` 의 락에서 오는데 그것은 쓰기 경로의
    것이고 여기는 읽기 경로다. 이 모듈이 락을 직접 들여다보면 조회가 실행에 묶인다 —
    부르는 쪽(`api/app.py`)이 알려 준다.

    **아무것도 안 올렸어도 200 이고 단계 다섯이 온다.** 처음 온 사람도 무엇이 일어날지
    먼저 볼 수 있어야 한다(DESIGN.md §7-5).
    """
    files = build.read_files(session, company_id)
    nodes = build.read_orbit(session, company_id)

    rows: list[FileProgressOut] = []
    for uf, made in files:
        stage = progress.stage_of(uf.status, running=running)
        rows.append(
            FileProgressOut(
                filename=uf.filename,
                ext=uf.ext,
                byte_size=uf.byte_size,
                status=uf.status,
                reached=stage.reached,
                label=stage.label,
                moving=stage.moving,
                ok=stage.ok,
                # **파서가 남긴 것만 낸다.** 사실을 못 뽑은 이유는 DB 에 자리가 없어서
                # 여기서 지어내지 않는다 — 그건 `label` 이 말한다.
                detail=uf.parse_error or None,
                chunk_count=uf.chunk_count,
                page_count=uf.page_count,
                nodes=made,
            )
        )

    conflicts = session.scalar(
        select(func.count())
        .select_from(WikiFact)
        .where(WikiFact.company_id == company_id, WikiFact.status == merge.Status.CONFLICT)
    )
    extractor = session.scalar(
        select(WikiFact.extractor).where(WikiFact.company_id == company_id).limit(1)
    )

    return ProgressOut(
        company_id=company_id,
        steps=[StepOut(key=s.key, label=s.label) for s in progress.STEPS],
        files=rows,
        places={key: spot.label for key, spot in topics.ORBIT.items()},
        total=len(rows),
        done=sum(f.ok for f in rows),
        moving=sum(f.moving for f in rows),
        # **글자가 안 나온 것과 못 읽은 것을 갈라 센다.** 스캔본은 OCR 이 붙으면 읽히고
        # 포맷이 없는 것은 안 읽힌다 — 사용자가 할 일이 다르다.
        needs_review=sum(f.status == "needs_review" for f in rows),
        stuck=sum(not f.ok and not f.moving and f.status != "needs_review" for f in rows),
        running=running,
        filled=sum(n.filled for n in nodes),
        slots=len(nodes),
        conflicts=conflicts or 0,
        extractor=extractor,
    )
