"""청크 → 사실 → 자리. **파이프라인의 아래 절반이다**(plan/12 T-0045 · T-0046).

`service.py` 가 파일 → 청크까지 하고, 여기가 그 뒤를 받는다. 순서는 이렇다.

    청크  →  추출 A(노드)   →  근거 연결  →  병합·충돌
          ↘  추출 B(매칭 정보)  ↗
             ↑ LLM 자리 둘        ↑ 결정론    ↑ 결정론

**LLM 은 첫 칸뿐이고 나머지에 모델이 안 들어간다** — 그래야 같은 파일을 두 번 넣어도
같은 배치가 나온다.

## 호출이 파일마다 둘이다

트랙을 가른 것이 ADR-0056 결정 1 이고 **호출을 나눈 것이 그 결정의 값이다.** A 는 넓게
뽑아야 하고 B 는 빠뜨리면 안 된다 — 튜닝 방향이 반대라 한 프롬프트에 섞으면 둘 다
어중간해진다. 대가는 파일당 호출 하나가 더 나가는 것이고, 얻는 것은 **B 만 정확도를
잴 수 있다**는 성질이다(열넷 중 몇 칸).

## 라우팅 단계가 없어졌다

2026-08-22 까지 `merge.place` 가 `topic` 을 표에서 찾아 자리를 정했다. 이제 **추출기가
자리를 알고 나온다**(T-0126) — 트랙 A 는 노드 경로를, B 는 고정 key 를. 그 표를 우리가
안 들고 있는 것이 이 결정의 요점이라, 여기서는 받은 자리에 앉히기만 한다.

## 파일별로 독립이다

`service.ingest_files` 와 같다(F1-1-8). 한 파일에서 추출이 실패해도 나머지로 위키가
선다. 스텁이 모르는 파일이면 그 파일만 `chunked` 로 남고 이유가 따라 나온다.

## 근거를 못 찾은 사실은 버린다

사실이 든 `anchor` 를 담은 청크가 없으면 **그 사실을 세우지 않고 문제로 보고한다.**
근거 없는 값을 위키에 올리면 ADR-0014 가 막으려던 바로 그것이 된다 — 집필이 값만
들고 문단을 쓰고 모델이 나머지를 지어낸다. 조용히 넘어가지 않는다.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finnect.models import (
    Chunk,
    CompanyValue,
    FactKind,
    SourceType,
    UserFile,
    UserFileStatus,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.wiki import extract_nodes, extract_profile, markdown, merge, profile, spots, tree
from finnect.wiki.extract_nodes import NodeExtractor
from finnect.wiki.extract_profile import ProfileExtractor
from finnect.wiki.port import FileView, Known, UnknownFile


@dataclass(frozen=True, slots=True)
class Extractors:
    """추출기 한 벌. **트랙이 둘이라 둘이다**(ADR-0056 결정 1).

    한 인자로 묶는 이유는 부르는 쪽이 **둘 중 하나만 갈아 끼우는 일이 없어서**다 —
    스텁이면 둘 다 스텁이고 LLM 이면 둘 다 LLM 이다(설정 하나가 정한다).
    """

    nodes: NodeExtractor
    values: ProfileExtractor

    @classmethod
    def default(cls) -> Extractors:
        return cls(nodes=extract_nodes.get_extractor(), values=extract_profile.get_extractor())

    @property
    def name(self) -> str:
        """행에 남는 이름. **둘이 갈리면 둘 다 적는다** — 무엇이 뽑았는지가 흐려지면 안 된다.

        `extractor` 컬럼이 32자라 자른다. 설정 하나가 둘을 고르므로 실제로 갈리는 것은
        테스트에서 한쪽만 갈아 끼울 때뿐이다.
        """
        a, b = self.nodes.name, self.values.name
        return (a if a == b else f"{a}+{b}")[:32]


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
    #: 트랙 B 가 채운 칸 수. **열넷 중 몇 칸인가**(ADR-0056 결정 1)
    profile_keys: int = 0
    #: 트랙 A 의 노드 수
    nodes: int = 0
    #: **이번에 새로 만든 노드.** 갑자기 늘면 이름이 갈리는 중이다(plan/22 T-0128)
    nodes_new: int = 0
    #: 파일마다 `(파일명, 새로 만든 노드, 기존에 붙인 노드)`.
    #:
    #: **총계만으로는 갈라지는 것을 못 본다.** 파일 다섯을 한 번에 올리면 첫 파일이
    #: 트리를 세우고 나머지가 거기 붙는 것이 정상인데, 총계는 그것과 「다섯이 각자
    #: 제 트리를 세웠다」를 같은 숫자로 보여 준다. 뒤쪽 파일이 계속 새 노드를 만들면
    #: **이름이 갈리는 중이다** — 그 판정을 여기서만 할 수 있다(T-0128).
    per_file: list[tuple[str, int, int]] = field(default_factory=list)
    #: 제자리를 못 찾아 `Custom/검토 대기` 로 간 사실 수. **버린 것이 아니다**
    review: int = 0
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


class BuildBusy(RuntimeError):
    """다른 프로세스가 같은 회사를 세우고 있다(plan/12 T-0094)."""


def _lock_key(company_id: str) -> int:
    """회사 하나를 어드바이저리 락 키(bigint)로. **프로세스를 건너 같아야 한다.**

    파이썬 `hash()` 를 쓰면 안 된다 — `PYTHONHASHSEED` 가 프로세스마다 달라서 CLI 와
    서비스가 **다른 키를 잡고 둘 다 통과한다.** 막으려는 것이 정확히 그것이다.
    """
    digest = hashlib.sha256(f"finnect.wiki.build:{company_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _hold(session: Session, company_id: str) -> None:
    """이 회사를 이 트랜잭션 동안 붙잡는다. 못 잡으면 거절한다(plan/12 T-0094).

    `ingest/jobs.py` 의 락은 `threading.Lock` 이라 **한 프로세스 안에서만 산다.**
    2026-08-21 CLI `--build` 가 도는 중에 화면에서 올린 파일이 `chunked` 로 되돌려졌다 —
    둘이 같은 `wiki_fact` 에 쓰면서 부딪혔다. 그 락은 그대로 두고(같은 프로세스 안의
    버튼 두 번을 막는 것은 여전히 그쪽 일이다) 여기서 프로세스 사이를 막는다.

    **트랜잭션 락(`_xact_`)이다.** 커밋·롤백에 저절로 풀려서 새는 자리가 없다 — 세션
    수준 락은 프로세스가 죽으면 연결이 끊길 때까지 남는다.

    **거절이 기본값이다**(`jobs.launch` 와 같은 규칙). 큐에 쌓으면 두 번 도는 것을
    아무도 못 본다.

    SQLite 에서는 아무것도 안 한다 — 테스트가 인메모리로 돌고, 거기는 프로세스가 하나다.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    if not session.scalar(select(func.pg_try_advisory_xact_lock(_lock_key(company_id)))):
        raise BuildBusy(
            f"{company_id}: 지금 다른 곳에서 위키를 세우고 있어요. "
            "끝나고 다시 해 주세요 — 화면에서 올리는 중에 CLI 를 돌리면 이렇게 됩니다"
        )


def build_company(
    session: Session,
    company_id: str,
    *,
    extractor: Extractors | None = None,
) -> BuildReport:
    """한 회사의 위키를 세운다. **파일별로 독립이고 마지막에 한 번 상태를 매긴다.**

    상태(current/superseded/conflict)는 **전체를 봐야** 정해진다. 어느 시점이 가장
    늦은지는 파일 하나만 봐서는 모른다.
    """
    _hold(session, company_id)
    ex = extractor or Extractors.default()
    report = BuildReport(company_id=company_id)

    # **`done` 을 다시 읽지 않는다.** 2026-08-21 실측 — `--build` 한 번에 `c_dasiro` 의
    # 사실이 187 → 291 이 됐다(node +93 · slot +10).
    #
    # 스텁 때는 안전했다. 같은 파일에서 같은 사실 118건이 나오고 `dedupe_key` 가 같아서
    # **아무것도 안 늘었다.** LLM 으로 바뀌자 깨졌다 — 같은 문서를 매번 다르게 쪼개서
    # 키가 달라지고 **다른 사실로 앉는다.** event topic 의 분해 단위가 흔들리는 그 성질이다.
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

    report.profile_keys = len(
        set(
            session.scalars(
                select(CompanyValue.key).where(CompanyValue.company_id == company_id)
            ).all()
        )
    )
    nodes = session.scalars(
        select(WikiNode).where(WikiNode.company_id == company_id)
    ).all()
    report.nodes = len(nodes)
    review = next((n for n in nodes if n.path == spots.REVIEW.path), None)
    report.review = (
        session.scalar(
            select(func.count()).select_from(WikiFact).where(WikiFact.node_id == review.id)
        )
        or 0
        if review
        else 0
    )
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


def known_names(session: Session, company_id: str) -> Known:
    """지금 있는 자리와 한정어. **프롬프트에 실려 같은 이름을 다시 쓰게 한다.**

    **파일마다 새로 읽는다.** 앞 파일이 만든 자리를 다음 파일이 봐야 거기 붙는다 —
    한 번만 읽고 재사용하면 같은 빌드 안에서 인스턴스 이름이 갈린다.

    한정어는 트랙 둘이 같이 쓴다. 트랙 A 의 값(`Financial/매출` 의 `시드`)과 트랙 B 의
    `funding` 한정어가 같은 말이라, 나눠서 주면 한쪽이 다른 표기를 만든다.
    """
    paths = session.scalars(
        select(WikiNode.path).where(WikiNode.company_id == company_id).order_by(WikiNode.path)
    ).all()
    quals = [
        *session.scalars(
            select(WikiFact.qualifier)
            .where(WikiFact.company_id == company_id, WikiFact.qualifier.is_not(None))
            .distinct()
        ).all(),
        *session.scalars(
            select(CompanyValue.qualifier)
            .where(CompanyValue.company_id == company_id, CompanyValue.qualifier.is_not(None))
            .distinct()
        ).all(),
    ]
    return Known.of(spots=paths, qualifiers=sorted(set(quals)))


def _build_file(
    session: Session, ex: Extractors, uf: UserFile, report: BuildReport
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
    known = known_names(session, uf.company_id)
    #: **이 파일이 들어오기 전의 노드 수.** 뒤에서 「새로 만든 것」을 빼는 기준이다
    made_before = report.nodes_new
    touched: set[int] = set()

    #: **트랙 A 를 먼저 부른다.** 순서가 결과를 바꾸지는 않지만, A 가 터지면 B 호출값을
    #: 안 쓰고 버리게 되므로 비싼 쪽을 먼저 실패시킨다
    node_facts = ex.nodes.extract(view, known)
    value_facts = ex.values.extract(view, known)

    # 앵커로 청크를 찾는다. **청크 번호를 사실에 박지 않는 이유가 이것이다** —
    # `--rechunk` 로 경계가 바뀌어도 앵커는 그대로다.
    squashed = [(c, _squash(c.text)) for c in chunks]
    uf.status = UserFileStatus.LINKING

    missing = 0
    for fact in value_facts:
        hit = _chunk_of(squashed, fact.anchor)
        if hit is None:
            missing += 1
            report.problems.append(
                (uf.filename, f"근거를 못 찾아 버렸어요 — {fact.anchor[:40]!r}")
            )
            continue
        #: 트랙 B — 회사 정보 표로 간다. **트리에 안 앉는다**(ADR-0056 결정 1)
        key = merge.value_key(fact)
        row = session.scalar(
            select(CompanyValue).where(
                CompanyValue.company_id == uf.company_id, CompanyValue.dedupe_key == key
            )
        )
        if row is None:
            row = CompanyValue(
                company_id=uf.company_id,
                key=fact.key,
                value=fact.value,
                qualifier=fact.qualifier,
                as_of=profile.as_of_for(fact.key, fact.as_of),
                status=merge.Status.CURRENT,
                dedupe_key=key,
                source_type=str(SourceType.DOCUMENT),
                extractor=ex.values.name,
            )
            session.add(row)
            session.flush()
            report.facts += 1
        else:
            report.merged += 1
        _attach(session, ValueEvidence, "value_id", row.id, uf, hit, fact, report)

    for fact in node_facts:
        hit = _chunk_of(squashed, fact.anchor)
        if hit is None:
            missing += 1
            report.problems.append(
                (uf.filename, f"근거를 못 찾아 버렸어요 — {fact.anchor[:40]!r}")
            )
            continue

        #: 트랙 A — 노드에 앉는다. **조상까지 만든다**
        node = _ensure_node(session, uf.company_id, fact.path, report)
        touched.add(node.id)
        key = merge.node_key(fact)
        row = session.scalar(
            select(WikiFact).where(WikiFact.company_id == uf.company_id, WikiFact.dedupe_key == key)
        )
        if row is None:
            is_value = fact.kind == "value"
            row = WikiFact(
                company_id=uf.company_id,
                node_id=node.id,
                kind=str(FactKind.VALUE if is_value else FactKind.EVENT),
                dedupe_key=key,
                text=fact.text if not fact.why else f"{fact.text}  [{fact.why}]",
                value=fact.value if is_value else None,
                qualifier=fact.qualifier if is_value else None,
                #: **서술에도 시점을 남긴다**(ADR-0057 결정 2). 값 필드와 달리 시점은
                #: 종류를 안 가린다 — 있으면 한 자리 안에서 이력으로 쌓인다
                as_of=fact.as_of,
                #: 기획 §5 의 자료 등급. **`실측` 과 `미정` 은 여기 안 온다** —
                #: 저 둘은 사용자 답변(ADR-0028)과 빈 자리가 정한다
                grade=fact.grade or None,
                source=fact.source or None,
                source_type=str(SourceType.DOCUMENT),
                extractor=ex.nodes.name,
            )
            session.add(row)
            session.flush()
            report.facts += 1
        else:
            report.merged += 1
        _attach(session, WikiEvidence, "fact_id", row.id, uf, hit, fact, report)

    #: **이 파일이 새로 만든 노드와 남의 노드에 붙은 수**(T-0128).
    #:
    #: 새로 만든 것은 조상까지 포함한다 — `Custom/특허/등록-10-2025` 하나가 노드 셋을
    #: 세우고, 그게 「트리가 자랐다」의 실제 크기다. 붙은 것은 **이 파일이 사실을 얹은
    #: 노드 중 이미 있던 것**만 센다(`touched` 에서 새로 만든 몫을 뺀다).
    made = report.nodes_new - made_before
    report.per_file.append((uf.filename, made, max(len(touched) - made, 0)))

    # **근거를 못 찾은 것이 있으면 done 이 아니다.** 사람이 봐야 한다.
    uf.status = UserFileStatus.NEEDS_REVIEW if missing else UserFileStatus.DONE
    #: **지난 실패를 지운다.** 안 지우면 추출기를 바꿔 성공한 뒤에도 화면이 옛 이유를
    #: 계속 말한다 — `_shelve` 가 상태를 되돌려 주는 것과 짝이다
    uf.extract_error = None
    report.built += 1


def _chunk_of(squashed: list[tuple[Chunk, str]], anchor: str) -> Chunk | None:
    """앵커를 담은 첫 청크. **못 찾으면 그 사실은 안 선다**(ADR-0014)."""
    needle = _squash(anchor)
    return next((c for c, body in squashed if needle and needle in body), None)


def _attach(session, model, col, row_id, uf, chunk, fact, report):  # noqa: ANN001, ANN201, PLR0913
    """근거 하나를 맨다. **이미 있으면 안 더한다** — 같은 청크가 두 번 세어지면 안 된다."""
    exists = session.scalar(
        select(model).where(getattr(model, col) == row_id, model.chunk_id == chunk.id)
    )
    if exists is not None:
        return
    session.add(
        model(
            company_id=uf.company_id,
            chunk_id=chunk.id,
            user_file_id=uf.id,
            quote=fact.anchor,
            **{col: row_id},
        )
    )
    report.evidence += 1


def _ensure_node(session: Session, company_id: str, path: str, report: BuildReport) -> WikiNode:
    """노드 하나와 **그 조상 전부**를 만든다. 뼈대가 없으면 트리가 안 선다.

    **정규화 정확 일치로 한 번 더 찾는다**(ADR-0056 결정 6). LLM 이 `기 능` 을 내도
    `기능` 이 이미 있으면 거기 붙는다 — **유사도는 안 쓴다.**

    새로 만든 노드를 센다. **이걸 안 세면 위키가 갈라지는 걸 볼 방법이 없다**(T-0128).
    """
    node = None
    for cur in tree.ancestors(path):
        node = session.scalar(
            select(WikiNode).where(WikiNode.company_id == company_id, WikiNode.path == cur)
        ) or session.scalar(
            select(WikiNode).where(
                WikiNode.company_id == company_id, WikiNode.norm_path == tree.norm_path(cur)
            )
        )
        if node is None:
            node = WikiNode(
                company_id=company_id,
                path=cur,
                category=tree.category_of(cur),
                name=tree.name_of(cur),
                parent=tree.parent_of(cur),
                norm_path=tree.norm_path(cur),
            )
            session.add(node)
            session.flush()
            report.nodes_new += 1
    assert node is not None
    return node


def restate(session: Session, company_id: str) -> int:
    """매칭 정보에 상태를 다시 매긴다. **한 회사 전부를 한 번에 본다.**

    돌려주는 값은 충돌 건수다. 부분만 보고 매기면 틀린다 — 어느 시점이 가장 늦은지는
    전체를 봐야 안다.

    **트랙 A 는 여기 안 들어온다.** `key` 가 없어지면서 한 자리 안에서 무엇과 무엇을
    견줄지가 정해지지 않는다 — `Market/시장규모` 의 TAM·SAM·SOM 은 같은 시점에 값이
    셋이고 그건 충돌이 아니라 원래 셋이다. 자리만 보고 판정하면 셋 다 `conflict` 가
    된다. 그래서 **트랙 A 값의 `status` 는 NULL 이고**, 화면은 시점 내림차순으로만
    세운다(`markdown.group`).
    """
    return _restate_values(session, company_id)


def _restate_values(session: Session, company_id: str) -> int:
    """트랙 B. 자리가 `key` 하나다."""
    rows = session.scalars(
        select(CompanyValue).where(CompanyValue.company_id == company_id)
    ).all()
    claims = [
        merge.Claim(key=r.key, qualifier=r.qualifier, as_of=r.as_of, value=r.value or "")
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
    n = (session.scalar(
        select(func.count()).select_from(WikiFact).where(WikiFact.company_id == company_id)
    ) or 0) + (session.scalar(
        select(func.count()).select_from(CompanyValue).where(CompanyValue.company_id == company_id)
    ) or 0)
    session.execute(sa_delete(WikiEvidence).where(WikiEvidence.company_id == company_id))
    session.execute(sa_delete(ValueEvidence).where(ValueEvidence.company_id == company_id))
    session.execute(sa_delete(WikiFact).where(WikiFact.company_id == company_id))
    session.execute(sa_delete(CompanyValue).where(CompanyValue.company_id == company_id))
    #: **노드도 지운다.** 사실이 없는 뼈대만 남으면 다음 빌드가 옛 이름을 재사용한다
    session.execute(sa_delete(WikiNode).where(WikiNode.company_id == company_id))
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
class ValueView:
    """회사 정보 한 칸(트랙 B). 값 하나와 이력·충돌이 같이 온다."""

    key: str
    label: str
    eligibility: bool
    #: 지금 값들. 충돌이면 둘 이상이다
    current: tuple[CompanyValue, ...]
    #: 더 늦은 값이 있어 밀린 것들
    history: tuple[CompanyValue, ...]

    @property
    def conflicted(self) -> bool:
        return any(v.status == merge.Status.CONFLICT for v in self.current)


def read_profile(session: Session, company_id: str) -> list[ValueView]:
    """회사 정보 열넷을 채워서 돌려준다. **빈 칸도 돌려준다.**

    **빈 칸이 물어볼 자리다**(ADR-0028). 열넷이 고정이라 못 채운 것을 셀 수 있고,
    셀 수 있어서 물어볼 수 있다 — 트랙 A 는 정답지가 없어 이걸 못 한다.
    """
    rows = session.scalars(
        select(CompanyValue)
        .where(CompanyValue.company_id == company_id)
        .order_by(CompanyValue.key, CompanyValue.qualifier, CompanyValue.as_of)
    ).all()

    out = []
    for key, spec in profile.PROFILE_KEYS.items():
        mine = [r for r in rows if r.key == key]
        out.append(
            ValueView(
                key=key,
                label=spec.label,
                eligibility=spec.eligibility,
                current=tuple(r for r in mine if r.status != merge.Status.SUPERSEDED),
                history=tuple(r for r in mine if r.status == merge.Status.SUPERSEDED),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class NodeView:
    """노드 하나와 그 위에 앉은 사실들(트랙 A). **DB 를 모르는 화면 쪽 모양이다.**"""

    path: str
    category: str
    name: str
    parent: str
    facts: tuple[markdown.Statement, ...]

    @property
    def filled(self) -> bool:
        return bool(self.facts)

    @property
    def depth(self) -> int:
        return self.path.count("/")

    @property
    def source_count(self) -> int:
        """근거로 쓰인 **파일 수**. 근거 개수가 아니다."""
        return len({e.filename for f in self.facts for e in f.evidence})


def read_nodes(session: Session, company_id: str) -> list[NodeView]:
    """자리 트리 전부. **비어 있는 폴더도 돌려준다.**

    폴더 열은 사실이 없어도 선다 — 무엇이 없는지 보여야 한다(`DESIGN.md` §7-5).
    순서는 `spots.FOLDERS` 표가 정하고 그 안에서는 경로순이다. **표가 정하고 데이터가
    정하지 않는다.**

    쿼리를 노드마다 돌리지 않는다. 사실과 근거를 한 번씩 읽고 파이썬에서 묶는다.
    """
    nodes = session.scalars(
        select(WikiNode).where(WikiNode.company_id == company_id)
    ).all()
    facts = session.scalars(
        select(WikiFact).where(WikiFact.company_id == company_id).order_by(WikiFact.id)
    ).all()

    rows = session.execute(
        select(
            WikiEvidence.fact_id, UserFile.filename, Chunk.page, WikiEvidence.quote, UserFile.sha256
        )
        .join(Chunk, Chunk.id == WikiEvidence.chunk_id)
        .join(UserFile, UserFile.id == WikiEvidence.user_file_id)
        .where(WikiEvidence.company_id == company_id)
        .order_by(UserFile.filename, Chunk.ordinal)
    ).all()
    by_fact: dict[int, list[markdown.Evidence]] = {}
    for fid, filename, page, quote, sha in rows:
        by_fact.setdefault(fid, []).append(markdown.Evidence(filename, page, quote, sha))

    by_node: dict[int, list[WikiFact]] = {}
    for f in facts:
        by_node.setdefault(f.node_id, []).append(f)

    #: 있는 노드 + **비어도 서는 폴더 열**
    seen = {n.path: n for n in nodes}
    out: list[NodeView] = []
    for cat in spots.FOLDERS:
        mine = sorted(
            (n for n in nodes if n.category == cat), key=lambda n: (n.path.count("/"), n.path)
        )
        if cat not in seen:
            out.append(NodeView(cat, cat, cat, "", ()))
        for n in mine:
            out.append(
                NodeView(
                    path=n.path,
                    category=n.category,
                    name=n.name,
                    parent=n.parent,
                    facts=tuple(
                        markdown.Statement(
                            text=f.text,
                            evidence=tuple(by_fact.get(f.id, ())),
                            source_type=f.source_type,
                            updated_at=f.updated_at.date() if f.updated_at else None,
                            #: **값 칸 셋을 같이 싣는다.** 안 실으면 뷰가 `text` 만 보고
                            #: `유료 매장 — 102` 를 문장 한 줄로 뭉갠다
                            kind=f.kind,
                            value=f.value,
                            qualifier=f.qualifier,
                            as_of=f.as_of,
                            #: 기획 §5 파일 머리의 재료. **장 하나가 여러 사실을 받으니
                            #: 등급도 여럿이고, 하나로 고르는 것은 `export.grade_of` 다**
                            grade=f.grade or "",
                            source=f.source or "",
                        )
                        for f in by_node.get(n.id, [])
                    ),
                )
            )
    return out


def read_files(session: Session, company_id: str) -> list[tuple[UserFile, list[str]]]:
    """올린 파일과 **그 파일이 채운 노드**(F1-4-7).

    "어느 파일을 지우면 무엇이 사라지나"를 보여 주는 자리다. 읽히지 않은 파일도 그대로
    돌려준다 — 실패를 안 보여 주면 사용자는 올린 줄 안다.

    **트랙 A 만 센다.** 회사 정보(트랙 B)는 트리에 자리가 없다.
    """
    files = session.scalars(
        select(UserFile).where(UserFile.company_id == company_id).order_by(UserFile.filename)
    ).all()

    rows = session.execute(
        select(WikiEvidence.user_file_id, WikiNode.path)
        .join(WikiFact, WikiFact.id == WikiEvidence.fact_id)
        .join(WikiNode, WikiNode.id == WikiFact.node_id)
        .where(WikiEvidence.company_id == company_id)
    ).all()

    made: dict[int, set[str]] = {}
    for file_id, path in rows:
        made.setdefault(file_id, set()).add(path)

    return [(uf, sorted(made.get(uf.id, set()))) for uf in files]
