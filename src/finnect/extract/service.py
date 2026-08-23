"""해독된 텍스트를 구간으로 쪼개고 칸을 꺼내 저장한다(plan/11 T-0035·T-0037·T-0038).

**같은 파일을 두 번 하지 않는다.** 키가 `sha256` 이라 같은 양식이 여러 공고에 붙어도
한 번만 돈다.

`attach` 와 달리 네트워크를 쓰지 않는다. 파일은 이미 디스크에 있다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from finnect.attach import store
from finnect.db import engine
from finnect.extract import classify as cl
from finnect.extract import fields as fx
from finnect.extract import outline as ol
from finnect.extract import segment as sg
from finnect.models import (
    Attachment,
    AttachmentFile,
    Document,
    DocumentItem,
    DocumentKind,
    ParseStatus,
)

#: 무엇이 판정했는지 남긴다. LLM 이 붙으면 `llm/<모델>` 로 덮인다(T-0036).
DECIDER = "rule/v1"


@dataclass(slots=True)
class ExtractReport:
    files: int = 0
    segments: int = 0
    fields_docs: int = 0
    items: int = 0
    skipped: int = 0
    #: 파일 안 좌표를 심은 칸 (plan/24 T-0152). **칸 수보다 적은 것이 정상이다** —
    #: 라벨이 겹치거나 구간이 여럿이면 안 심는다
    anchored: int = 0
    #: 열려다 실패한 파일. **0 이 아니면 봐야 한다**
    anchor_failed: int = 0
    kinds: dict[str, int] = field(default_factory=dict)

    def line(self) -> str:
        k = " · ".join(f"{v} {n}" for n, v in sorted(self.kinds.items(), key=lambda x: -x[1]))
        out = [
            f"파일 {self.files:,} · 구간 {self.segments:,} · "
            f"칸 서식 {self.fields_docs:,} · 칸 {self.items:,} · 건너뜀 {self.skipped:,}",
            f"좌표를 심은 칸 {self.anchored:,}",
            f"구간 종류: {k or '없음'}",
        ]
        if self.anchor_failed:
            out.insert(2, f"열지 못한 파일 {self.anchor_failed:,}건 — 봐야 한다")
        return "\n".join(out)


def run(
    *,
    limit: int | None = None,
    redo: bool = False,
    notice: tuple[str, str] | None = None,
) -> ExtractReport:
    """첨부 텍스트를 구간과 칸으로 가른다. **네트워크를 안 쓴다.**

    `notice` 를 주면 그 공고에 붙은 첨부만 본다 — 초안 시작이 부르는 길이다.
    **미리 전량을 뜯어 두지 않는 이유는 대부분이 버려져서다**: 코퍼스에서 구간
    944개 중 451개가 공고문·안내문이었고 아무도 채우지 않는다.

    **단위는 그대로 `sha256` 이다.** 공고로 좁히는 것은 「어느 것을 뜯을까」이지
    「몇 번 뜯을까」가 아니다 — 콘텐츠 주소라 같은 양식이 여러 공고에 붙어도 한 번만
    뜯고, 그 성질을 잃으면 같은 파일을 공고 수만큼 다시 판정하게 된다.
    """
    report = ExtractReport()

    with Session(engine) as s:
        q = select(AttachmentFile).where(
            AttachmentFile.parse_status == str(ParseStatus.OK),
            AttachmentFile.text_path.is_not(None),
            AttachmentFile.sha256.is_not(None),
        )
        if notice is not None:
            source, external_id = notice
            q = q.join(Attachment, Attachment.url == AttachmentFile.url).where(
                Attachment.source == source,
                Attachment.external_id == external_id,
            )
        rows = s.scalars(q).all()

        done: set[str] = set()
        seen: set[str] = set()
        if not redo:
            done = set(s.scalars(select(Document.sha256).distinct()).all())

        for row in rows:
            sha = row.sha256
            assert sha is not None
            if sha in seen:
                continue  # 같은 내용의 파일이 여러 URL 로 온다
            seen.add(sha)
            if sha in done:
                report.skipped += 1
                continue

            try:
                text = store.abs_path(row.text_path).read_text(errors="ignore")  # type: ignore[arg-type]
            except FileNotFoundError:
                report.skipped += 1
                continue

            # 이미 디스크에 있는 텍스트에는 NUL 이 남아 있다. `attach/extract.py` 가
            # 앞으로는 안 넣지만 다시 해독하기 전까지는 여기서 막는다.
            # **지우지 않고 공백으로 바꾼다** — 길이가 달라지면 오프셋이 어긋난다.
            text = text.replace("\x00", " ")

            _replace(s, sha, text, report, ext=row.detected_ext)
            report.files += 1
            if limit is not None and report.files >= limit:
                break

        s.commit()
    return report


def _replace(
    s: Session, sha: str, text: str, report: ExtractReport, *, ext: str | None = None
) -> None:
    """이 파일의 구간을 다시 깐다. **부분 갱신을 하지 않는다** — 파서가 바뀌면 경계가 바뀐다.

    ## 여기가 초안을 지운다

    `draft_item.document_item_id` 의 FK 가 **CASCADE** 라, 항목을 지우면 그 항목에
    쓴 초안이 따라 지워진다. `draft` 도 `document_id` 로 매달려 있어 같이 사라진다.
    **사람이 고친 글(`edited_body`)도 함께 없어진다**(ADR-0055 가 지키려던 바로 그 값).

    2026-08-23 좌표를 심으려고 `--redo` 를 한 번 돌렸다가 `kstartup:178881` 의 초안
    17칸이 통째로 날아갔다. 파싱을 고치는 사람과 초안을 쓴 사람이 다른 자리라 **다시
    밟기 쉽다.**

    평소 경로는 안전하다 — `run()` 이 `redo` 없이는 `document` 가 있는 파일을
    건너뛰고, 초안 시작이 부르는 `_prepare()` 도 `redo` 를 안 넘긴다. **위험한 것은
    `--redo` 하나다.**
    """
    old = s.scalars(select(Document.id).where(Document.sha256 == sha)).all()
    if old:
        s.execute(delete(DocumentItem).where(DocumentItem.document_id.in_(old)))
        s.execute(delete(Document).where(Document.id.in_(old)))

    fields_docs: list[int] = []
    for seg in sg.split(text):
        kind = _classify(seg.text)
        doc = Document(
            sha256=sha,
            seq=seg.seq,
            title=seg.title[:300],
            kind=str(kind),
            char_start=seg.start,
            char_end=seg.end,
            decided_by=DECIDER,
        )
        s.add(doc)
        s.flush()

        report.segments += 1
        report.kinds[str(kind)] = report.kinds.get(str(kind), 0) + 1

        if kind is not DocumentKind.FIELDS:
            continue

        report.fields_docs += 1
        fields_docs.append(doc.id)
        for i, label in enumerate(fx.labels(seg.text)):
            s.add(
                DocumentItem(
                    document_id=doc.id,
                    ordinal=i,
                    number=None,
                    title=label,
                    instruction=None,
                    input_kind="field",
                )
            )
            report.items += 1

    _plant_anchors(s, sha, ext, fields_docs, report)


def _plant_anchors(
    s: Session,
    sha: str,
    ext: str | None,
    fields_docs: list[int],
    report: ExtractReport,
) -> None:
    """칸 서식 항목에 **파일 안 좌표**를 심는다 (plan/24 T-0152 · ADR-0060).

    **나중에 붙일 수 없다.** 위치정보는 파싱 단계에서만 심을 수 있다(ADR-0014).

    ## 안 심는 자리가 셋이다

    **① 칸 서식 구간이 파일에 여럿이면 안 심는다**(코퍼스의 31%). 표가 어느 구간의
    것인지 가릴 근거가 없다 — 텍스트 구간과 파일 구조는 다른 축이라 `char_start` 로
    표를 못 찾는다.

    **② 라벨이 파일 안에서 겹치면 그 항목만 비운다.** 실측에서 우리가 채운 17칸 중
    둘이 그랬다(`기업명` 3회 · `합계` 3회 · `spike/anchor_check.py`). 하나를 고르면
    그 선택이 조용히 일어나고, **틀려도 파일은 정상으로 열려** 제출 직전에야 드러난다.

    **③ 못 여는 포맷이면 통째로 비운다.** pdf·zip 이 그렇고 JVM 이 없는 서버도 그렇다.

    셋 다 결과가 같다 — `anchor` 가 NULL 이고 그 칸은 안 채워진다. **모르는 것을
    아는 척하지 않는다.**
    """
    if len(fields_docs) != 1 or not ext:
        return

    from finnect.forms import (  # 함수 안에서 — JVM 을 최상단으로 끌고 오지 않는다
        UnsupportedFormat,
        label_targets,
        norm_label,
        open_form,
    )
    from finnect.forms.base import FormsUnavailable

    try:
        form = open_form(str(store.abs_path(store.rel_path(sha))), ext)
        targets = label_targets(form.cells())
    except (UnsupportedFormat, FormsUnavailable, FileNotFoundError):
        return
    except Exception as e:  # noqa: BLE001 — 파일 하나가 수집 전체를 안 죽인다
        report.anchor_failed += 1
        print(f"[좌표] {sha[:8]} 를 못 열었다: {type(e).__name__}: {e}", flush=True)
        return

    # 겹치는 라벨은 **아예 뺀다.** 첫 번째를 고르는 것이 이 방식이 부러진 자리다.
    seen: dict[str, object | None] = {}
    for label, anchor in targets:
        key = norm_label(label)
        seen[key] = None if key in seen else anchor

    rows = s.scalars(
        select(DocumentItem).where(DocumentItem.document_id == fields_docs[0])
    ).all()
    for row in rows:
        hit = seen.get(norm_label(row.title))
        if hit is not None:
            row.anchor = str(hit)
            report.anchored += 1


def _classify(text: str) -> DocumentKind:
    """**규칙으로 갈리는 것만 가른다.**

    칸 채우기는 신호가 뚜렷하다. 서술형은 공고문의 절과 생김새가 같아서
    규칙이 네 번 실패했으므로 `UNKNOWN` 으로 남긴다 — T-0036 이 채운다.
    **모르는 것을 `NONE` 이라고 하지 않는다.** 그러면 나중에 다시 볼 대상이 사라진다.
    """
    if fx.is_fields(text):
        return DocumentKind.FIELDS
    return DocumentKind.UNKNOWN


# ─────────────────────────────────────────────────────────────────
# 양식 구간 판별 (plan/11 T-0036)
#
# **분할과 따로 돈다.** `run()` 은 규칙이고 결정론이라 언제 다시 돌려도 같은
# 경계가 나온다. 판정은 LLM 이라 돈이 들고 답이 매번 같지 않다. 붙여 두면
# 파서를 한 줄 고칠 때마다 7,717번을 다시 물어야 한다.
# ─────────────────────────────────────────────────────────────────

#: 몇 건마다 커밋하고 진행을 찍나. **끝에 한 번만 커밋하면 안 된다** —
#: 3,112회를 도는 작업에서 마지막 하나가 죽으면 앞의 전부가 롤백된다.
#: `match/service.py` 가 1,790건에서 같은 것을 겪고 고쳤다(2026-08-20).
#:
#: **커밋과 진행 표시가 같은 자리인 것이 요점이다.** 커밋 전에는 다른 세션에서
#: `document` 를 세도 0 이라, 이 줄이 진행을 말하는 유일한 자리다.
_COMMIT_EVERY = 50


@dataclass(slots=True)
class ClassifyReport:
    asked: int = 0
    changed: int = 0
    items: int = 0
    unreadable: int = 0
    #: 표지 한 줄만 남은 구간. **안 물어본다** (classify.MIN_BODY_CHARS)
    too_short: int = 0
    #: 모델이 스스로 "판단할 내용이 없다" 고 답한 것
    declined: int = 0
    kinds: dict[str, int] = field(default_factory=dict)
    #: 판정기가 되돌린 것. **조용히 넘기지 않는다**
    dropped: list[tuple[str, str]] = field(default_factory=list)
    #: 비용. 지어내지 않고 센다
    usage: str = ""

    def line(self) -> str:
        k = " · ".join(f"{v} {n}" for n, v in sorted(self.kinds.items(), key=lambda x: -x[1]))
        out = [
            f"물어봄 {self.asked:,} · 바뀜 {self.changed:,} · 칸 {self.items:,} · "
            f"못 읽음 {self.unreadable:,} · 너무 짧아 안 물어봄 {self.too_short:,} · "
            f"모른다고 답함 {self.declined:,}",
            f"판정: {k or '없음'}",
        ]
        if self.dropped:
            out.append(f"되돌림 {len(self.dropped):,}건 — {self.dropped[:3]}")
        if self.usage:
            out.append(self.usage)
        return "\n".join(out)


def classify_unknown(  # noqa: PLR0913
    *,
    limit: int | None = None,
    redo: bool = False,
    dry: bool = False,
    title_like: str | None = None,
    notice: tuple[str, str] | None = None,
) -> ClassifyReport:
    """`unknown` 구간에 종류를 붙인다.

    `dry` 면 **아무것도 안 쓴다.** 손 분류와 대조할 때 쓴다 — 40건을 눈으로 보고
    나서 저장할지 정한다(plan/11 T-0036 완료 조건).

    `title_like` 는 **표본 고르기다. 판정 규칙이 아니다.**

    `--limit N` 만 주면 sha256 순서로 앞에서 N개를 집는데, 그러면 파일 몇 개에
    몰린다(실측: 40건이 5~6개 파일에서 나왔고 서술형이 2건뿐이었다). 서술형 양식을
    보고 싶을 때 `계획` 으로 좁히면 160개 후보가 나온다.

    **제목으로 종류를 정하는 것이 아니다** — 그건 네 번 실패한 규칙이다. 여기서
    제목은 **어느 구간을 물어볼지**만 고르고, 판정은 LLM 이 원문을 읽고 한다.

    `notice` 를 주면 그 공고의 구간만 묻는다 — 초안 시작이 부르는 길이다.

    **후보를 먼저 세고 없으면 분류기를 안 만든다.** `get_classifier()` 가 키를 요구해서
    (없으면 멈춘다), 물어볼 것이 없는데 키가 없다는 이유로 초안 전체가 죽으면 안 된다.
    """
    report = ClassifyReport()

    with Session(engine) as s:
        q = select(Document).where(Document.kind == str(DocumentKind.UNKNOWN))
        if redo:
            q = select(Document).where(
                or_(
                    Document.kind == str(DocumentKind.UNKNOWN),
                    Document.decided_by.startswith("llm/"),
                )
            )
        if title_like:
            q = q.where(Document.title.ilike(f"%{title_like}%"))
        if notice is not None:
            source, external_id = notice
            q = q.join(AttachmentFile, AttachmentFile.sha256 == Document.sha256).join(
                Attachment, Attachment.url == AttachmentFile.url
            ).where(
                Attachment.source == source,
                Attachment.external_id == external_id,
            )
        docs = s.scalars(q.order_by(Document.sha256, Document.seq)).all()

        if not docs:
            return report  # **분류기를 안 만든다** — 키가 없어도 여기는 지나가야 한다
        clf = cl.get_classifier()

        if not dry:
            # **후보 수를 먼저 말한다.** 첫 커밋까지 `_COMMIT_EVERY` 회가 걸리는데
            # 그동안 화면이 비어 있으면 안 도는 것과 구분이 안 된다.
            print(f"[판정] 후보 {len(docs):,} 구간 · {_COMMIT_EVERY}건마다 커밋한다", flush=True)

        t0 = time.monotonic()
        since = 0
        texts: dict[str, str | None] = {}
        for doc in docs:
            if limit is not None and report.asked >= limit:
                break

            if doc.sha256 not in texts:
                texts[doc.sha256] = _text_of(s, doc.sha256)
            whole = texts[doc.sha256]
            if whole is None:
                report.unreadable += 1
                continue

            body = whole[doc.char_start : doc.char_end]
            if not body.strip():
                report.unreadable += 1
                continue
            if len(body.strip()) < cl.MIN_BODY_CHARS:
                # **표지 한 줄만 남은 구간이다.** 물으면 셋 중 하나를 강제하게 되고
                # 모델이 `reason` 에 "제목만 있다" 고 적으면서 답을 낸다(실측 40건 중 6)
                report.too_short += 1
                continue

            verdict = clf.classify(cl.SegmentView(title=doc.title, text=body))
            report.asked += 1
            report.kinds[str(verdict.kind)] = report.kinds.get(str(verdict.kind), 0) + 1

            if dry:
                print(f"  {str(verdict.kind):<10} {doc.title[:44]:<46} {verdict.reason[:70]}")
                continue

            # **`unclear` 로 되돌린 것도 여기서 센다.** 아래 `continue` 뒤에 두면
            # 거절이 몰릴 때 진행이 멎은 것처럼 보인다.
            since += 1
            if since >= _COMMIT_EVERY:
                s.commit()
                since = 0
                _tick(report, len(docs), t0)

            if verdict.kind is DocumentKind.UNKNOWN:
                continue  # 판정기가 모른다고 했다. **`none` 으로 밀지 않는다**

            doc.kind = str(verdict.kind)
            doc.decided_by = clf.name
            report.changed += 1

            # **항목을 안 뽑으면 그 구간은 종류만 있고 속이 빈 채로 남고,
            # 화면이 빈 서류를 그린다.** 서술형은 여기서 처음 생긴다(T-0037).
            report.items += _add_items(s, doc, body, verdict.kind)

        report.dropped = list(getattr(clf, "dropped", []))
        report.declined += len(getattr(clf, "declined", []))
        report.usage = _usage_line(clf)
        if dry:
            s.rollback()
        else:
            s.commit()
    return report


def _tick(report: ClassifyReport, total: int, t0: float) -> None:
    """진행 한 줄. **남은 시간은 추정이고 조금 길게 나온다** — 속도를 물어본 건수로
    재는데 남은 것에는 안 묻고 지나가는 짧은 구간이 섞여 있다. 짧게 나오는 것보다 낫다.
    """
    seen = report.asked + report.too_short + report.unreadable
    elapsed = time.monotonic() - t0
    rate = report.asked / elapsed if elapsed > 0 else 0.0
    left = (total - seen) / rate / 60 if rate > 0 else 0.0
    print(
        f"  … {seen:,}/{total:,} · 물음 {report.asked:,} · 바뀜 {report.changed:,} · "
        f"{rate * 60:,.0f}건/분 · 남은 ~{left:,.0f}분",
        flush=True,
    )


def _text_of(s: Session, sha: str) -> str | None:
    """그 파일의 해독 텍스트. **오프셋이 어긋나지 않게 `run()` 과 같이 읽는다.**"""
    path = s.scalar(
        select(AttachmentFile.text_path)
        .where(AttachmentFile.sha256 == sha, AttachmentFile.text_path.is_not(None))
        .limit(1)
    )
    if not path:
        return None
    try:
        return store.abs_path(path).read_text(errors="ignore").replace("\x00", " ")
    except FileNotFoundError:
        return None


def _add_items(s: Session, doc: Document, body: str, kind: DocumentKind) -> int:
    """판정된 종류에 맞는 항목을 깐다. **이미 있으면 안 만든다** — `--redo` 로 두 번
    돌 때 항목이 두 벌이 된다."""
    if s.scalar(
        select(func.count()).select_from(DocumentItem).where(DocumentItem.document_id == doc.id)
    ):
        return 0
    if kind is DocumentKind.FIELDS:
        return _add_fields(s, doc, body)
    if kind is DocumentKind.NARRATIVE:
        return _add_outline(s, doc, body)
    return 0


def _add_fields(s: Session, doc: Document, body: str) -> int:
    n = 0
    for i, label in enumerate(fx.labels(body)):
        s.add(
            DocumentItem(
                document_id=doc.id, ordinal=i, number=None,
                title=label, instruction=None, input_kind="field",
            )
        )
        n += 1
    return n


def _add_outline(s: Session, doc: Document, body: str) -> int:
    """서술형 항목 트리 (T-0037).

    **오프셋에 구간 시작을 더한다.** `outline` 은 넘겨받은 텍스트 기준으로 세는데
    화면은 파일 원문에서 잘라 보여 준다 — 안 더하면 엉뚱한 데가 열린다.

    부모를 걸려면 자식보다 먼저 `id` 가 있어야 해서 **한 줄씩 flush 한다.**
    항목이 수십 개라 감당된다(최악이 102개).
    """
    ids: list[int] = []
    for i, it in enumerate(ol.items(body)):
        row = DocumentItem(
            document_id=doc.id,
            parent_id=ids[it.parent] if it.parent is not None else None,
            ordinal=i,
            number=it.number,
            title=it.title[:300],
            instruction=it.instruction,
            limit_text=it.limit_text,
            input_kind="narrative",
            char_start=doc.char_start + it.start,
            char_end=doc.char_start + it.end,
        )
        s.add(row)
        s.flush()
        ids.append(row.id)
    return len(ids)


def _usage_line(clf: object) -> str:
    """LLM 을 실제로 부른 판정기만 집계를 들고 있다."""
    c = getattr(clf, "client", None)
    usage = getattr(c, "usage", None)
    return usage.line() if usage is not None and getattr(usage, "calls", 0) else ""
