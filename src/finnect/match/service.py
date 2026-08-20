"""맞는 공고 고르기 — 오케스트레이션 (plan/17).

    normalize()   ① 공고 정규화. LLM. 공고당 1회 · 회사와 무관
    run()         ②~⑤ 회사와 대조. **LLM 0회**
    report()      퍼널

## 후보를 어디서 받나

**층0 은 이 계획 밖에 있다.** `notice-filter/` 가 기업마당 1,524 → 542 · K-Startup
29,789 → 15,643 을 내는데 그 폴더는 제품 코드가 아니다. `attach --only` 와 같은
방식으로 **목록 파일**을 받는다 — 이쪽은 목록을 누가 만들었는지 모른다.

    python3 notice-filter/filter.py --ids > out/후보.txt
    uv run python -m finnect.match --company c_dasiro --only out/후보.txt

`--only` 가 없으면 **열린 공고 전량**(1,830건)이 후보다. 그것도 돈다 — 층0 이 미는
것을 ④가 대부분 다시 미는데, 그게 겹치는지는 `--report` 가 보여 준다.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from finnect.config import settings
from finnect.db import engine
from finnect.llm import Usage
from finnect.match import bodies
from finnect.match import eligible as el
from finnect.match import normalize as nz
from finnect.match import profile as pf
from finnect.match import rank as rk
from finnect.match import sectors as sc
from finnect.models import (
    BizinfoNotice,
    FitVerdict,
    KstartupNotice,
    NoticeFit,
    NoticeFitEvidence,
    NoticeProfile,
)
from finnect.views import Notice

#: 추천에 올리는 건수. `SPEC.md` F4-1 — "적합도순 **3건.** 전체를 늘어놓지 않는다"
TOP_N = 3

#: 몇 건마다 커밋하나. **끝에 한 번만 커밋하면 안 된다** — 1,790건을 도는 작업에서
#: 마지막 한 건이 죽으면 앞의 1,789회가 다 날아간다. 실제로 그렇게 만들어 놓고
#: 고쳤다(2026-08-20).
_COMMIT_EVERY = 50


# ─────────────────────────────── ① 정규화 ───────────────────────────────


@dataclass(slots=True)
class NormalizeReport:
    seen: int = 0
    #: 새로 뽑았다
    written: int = 0
    #: 본문이 그대로라 안 불렀다
    cached: int = 0
    #: 앵커가 원문에 없어 버렸다. **조용히 안 넘긴다**
    dropped: list[tuple[str, str]] = field(default_factory=list)
    #: 호출이 실패했다. 공고 단위로 남는다
    failed: list[tuple[str, str]] = field(default_factory=list)
    usage: str = ""

    def line(self) -> str:
        out = [
            f"공고 {self.seen:,} · 새로 뽑음 {self.written:,} · 그대로 {self.cached:,}"
        ]
        if self.dropped:
            out.append(f"앵커 없음 {len(self.dropped):,}건 — {self.dropped[:3]}")
        if self.failed:
            out.append(f"실패 {len(self.failed):,}건 — {self.failed[:3]}")
        if self.usage:
            out.append(self.usage)
        return "\n".join(out)


def _open_ids(s: Session, today: dt.date) -> list[tuple[str, str]]:
    """열린 공고. 마감일이 없는 것도 열린 것으로 센다(기업마당 접수 기간의 57%)."""
    rows = s.execute(
        select(Notice.source, Notice.external_id).where(
            (Notice.apply_end.is_(None)) | (Notice.apply_end >= today)
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


def _bodies(s: Session, keys: list[tuple[str, str]]) -> list[nz.NoticeBody]:
    """출처별 원본 표에서 읽는다. **`notice` 뷰에는 지원대상 절이 없다.**"""
    biz = [k[1] for k in keys if k[0] == "bizinfo"]
    ks = [k[1] for k in keys if k[0] == "kstartup"]
    out: list[nz.NoticeBody] = []
    if biz:
        for row in s.scalars(
            select(BizinfoNotice).where(BizinfoNotice.pblancId.in_(biz))
        ):
            out.append(bodies.from_bizinfo(row))
    if ks:
        for row in s.scalars(
            select(KstartupNotice).where(KstartupNotice.pbanc_sn.in_(ks))
        ):
            out.append(bodies.from_kstartup(row))
    return out


def normalize(
    *,
    limit: int | None = None,
    redo: bool = False,
    dry: bool = False,
    only: set[str] | None = None,
    today: dt.date | None = None,
    normalizer: nz.LlmNormalizer | None = None,
    workers: int | None = None,
) -> NormalizeReport:
    """열린 공고를 정규화한다 (T-0070).

    `normalizer` 를 넘길 수 있는 이유는 **테스트가 네트워크 없이 돌아야 해서**다.
    `dry` 는 찍어만 보고 저장하지 않는다 — 손 라벨과 대조할 때 쓴다.

    **공고끼리 독립이라 병렬로 돈다.** 하나가 실패해도 나머지가 남는다 —
    `draft/service.py` 의 항목 병렬과 같은 모양이다(plan/16 T-0069). `workers=1`
    이면 순차이고, **결과는 같아야 한다** — 저장 순서가 답을 바꾸지 않는다.
    """
    today = today or dt.date.today()
    nrm = normalizer or nz.LlmNormalizer()
    workers = workers if workers is not None else settings.match_workers
    rep = NormalizeReport()

    with Session(engine) as s:
        keys = _open_ids(s, today)
        if only is not None:
            keys = [k for k in keys if k[1] in only]
        views = _bodies(s, keys)
        if limit:
            views = views[:limit]
        rep.seen = len(views)

        have = {
            (p.source, p.external_id): p.body_hash
            for p in s.scalars(select(NoticeProfile))
        }
        todo: list[nz.NoticeBody] = []
        for b in views:
            if have.get((b.source, b.external_id)) == b.body_hash and not redo:
                rep.cached += 1
            else:
                todo.append(b)

        since = 0
        for b, got, err in _read_all(nrm, todo, workers):
            if err is not None:
                rep.failed.append((f"{b.source}:{b.external_id}", err))
                continue
            if got is None:
                continue
            rep.written += 1
            if dry:
                print(
                    f"  {b.source}:{b.external_id}  지역{list(got.regions)} "
                    f"업종{list(got.industries)} 조건{list(got.conditions)}\n"
                    f"      키워드{list(got.keywords)} · {got.purpose}"
                )
                continue
            _save_profile(s, b, got, nrm.name)
            since += 1
            if since >= _COMMIT_EVERY:
                s.commit()
                since = 0
                print(f"  … {rep.written:,}/{len(todo):,}", flush=True)
        rep.dropped = list(nrm.dropped)
        if not dry:
            s.commit()

    c = getattr(nrm, "client", None)
    usage = getattr(c, "usage", None)
    if isinstance(usage, Usage) and usage.calls:
        rep.usage = usage.line()
    return rep


def _read_all(nrm, todo: list, workers: int):  # noqa: ANN001, ANN202
    """정규화를 돌리며 **도착하는 대로 흘려준다.** `(본문, 결과, 오류)`.

    모아서 한 번에 돌려주면 안 된다 — 그러면 커밋도 끝에 한 번뿐이라 마지막 한
    건이 죽을 때 앞의 전부가 날아간다.

    **DB 를 워커 안에서 안 만진다.** 저장은 부르는 쪽이 한 세션에서 한다 —
    스레드마다 세션을 열면 `_save_profile` 의 `select` 가 서로 못 본 행을 두 번 만든다.

    순서는 병렬일 때 완료 순이다. **답이 안 바뀐다** — `_save_profile` 이
    `(source, external_id)` 로 갈아 쓰므로 저장 순서가 결과에 안 들어간다.
    """

    def one(b):  # noqa: ANN001, ANN202
        try:
            return b, nrm.read(b), None
        except Exception as e:  # noqa: BLE001 — 공고 하나가 나머지를 막지 않는다
            return b, None, type(e).__name__

    if workers <= 1 or len(todo) <= 1:
        for b in todo:
            yield one(b)
        return

    with ThreadPoolExecutor(max_workers=min(workers, len(todo))) as pool:
        for fut in as_completed([pool.submit(one, b) for b in todo]):
            yield fut.result()


def _save_profile(s: Session, b: nz.NoticeBody, p: nz.Profile, by: str) -> None:
    row = s.scalars(
        select(NoticeProfile).where(
            NoticeProfile.source == b.source,
            NoticeProfile.external_id == b.external_id,
        )
    ).first()
    if row is None:
        row = NoticeProfile(source=b.source, external_id=b.external_id)
        s.add(row)
    row.body_hash = b.body_hash
    row.regions = list(p.regions)
    row.industries = list(p.industries)
    row.conditions = list(p.conditions)
    row.keywords = list(p.keywords)
    row.purpose = p.purpose
    row.decided_by = by
    row.updated_at = dt.datetime.now(dt.UTC)


# ─────────────────────────────── ②~⑤ 대조 ───────────────────────────────


@dataclass(slots=True)
class MatchReport:
    company_id: str = ""
    candidates: int = 0
    #: ③ 자격
    failed_eligibility: int = 0
    unknown_eligibility: int = 0
    no_profile: int = 0
    #: ④ 분야
    sector_hit: int = 0
    #: ⑤ 등급
    match: int = 0
    maybe: int = 0
    miss: int = 0
    #: 규칙이 못 읽은 조건. **`SPEC.md` §2.1 이 모른다고 적어 둔 숫자다**
    unhandled: dict[str, int] = field(default_factory=dict)
    #: 표에 없는 지원분야 값
    unknown_sectors: list[str] = field(default_factory=list)
    top: list[tuple[str, str, str]] = field(default_factory=list)

    def line(self) -> str:
        out = [
            f"후보 {self.candidates:,}",
            f"  ③ 자격      탈락 {self.failed_eligibility:,} · "
            f"확인 필요 {self.unknown_eligibility:,} · 정규화 없음 {self.no_profile:,}",
            f"  ④ 분야      맞음 {self.sector_hit:,}",
            f"  ⑤ 적합도    맞다 {self.match:,} · 애매 {self.maybe:,} · 아니다 {self.miss:,}",
        ]
        if self.unhandled:
            top = sorted(self.unhandled.items(), key=lambda x: -x[1])[:5]
            out.append(
                f"  규칙이 못 읽은 조건 {sum(self.unhandled.values()):,}건 "
                f"({len(self.unhandled):,}종) — {top}"
            )
        if self.unknown_sectors:
            out.append(f"  표에 없는 지원분야 — {self.unknown_sectors}")
        if self.top:
            out.append("")
            out.append(f"추천 {len(self.top)}건")
            for _src, title, reason in self.top:
                out.append(f"  {title[:64]}")
                out.append(f"    {reason}")
        return "\n".join(out)


@dataclass(frozen=True, slots=True)
class _Candidate:
    source: str
    external_id: str
    title: str
    category: str | None
    apply_end: dt.date | None


def _candidates(s: Session, today: dt.date, only: set[str] | None) -> list[_Candidate]:
    rows = s.execute(
        select(
            Notice.source, Notice.external_id, Notice.title, Notice.apply_end
        ).where((Notice.apply_end.is_(None)) | (Notice.apply_end >= today))
    ).all()
    keys = [(r[0], r[1]) for r in rows]
    if only is not None:
        keys = [k for k in keys if k[1] in only]
    wanted = set(keys)

    # 지원분야는 뷰에 중분류가 없다. **출처별 표에서 읽는다**
    cat: dict[tuple[str, str], str | None] = {}
    biz = [k[1] for k in keys if k[0] == "bizinfo"]
    ks = [k[1] for k in keys if k[0] == "kstartup"]
    if biz:
        for a, b in s.execute(
            select(
                BizinfoNotice.pblancId, BizinfoNotice.pldirSportRealmMlsfcCodeNm
            ).where(BizinfoNotice.pblancId.in_(biz))
        ).all():
            cat[("bizinfo", a)] = b
    if ks:
        for a, b in s.execute(
            select(KstartupNotice.pbanc_sn, KstartupNotice.supt_biz_clsfc).where(
                KstartupNotice.pbanc_sn.in_(ks)
            )
        ).all():
            cat[("kstartup", a)] = b

    return [
        _Candidate(r[0], r[1], r[2] or "", cat.get((r[0], r[1])), r[3])
        for r in rows
        if (r[0], r[1]) in wanted
    ]


def run(
    company_id: str,
    *,
    only: set[str] | None = None,
    today: dt.date | None = None,
    save: bool = True,
) -> MatchReport:
    """회사 하나에 대해 ②~⑤ 를 돌린다. **LLM 0회다.**"""
    today = today or dt.date.today()
    rep = MatchReport(company_id=company_id)

    with Session(engine) as s:
        me = pf.load(s, company_id, on=today)
        cands = _candidates(s, today, only)
        rep.candidates = len(cands)
        rep.unknown_sectors = sc.unknown_categories(
            "bizinfo", [c.category for c in cands if c.source == "bizinfo"]
        ) + sc.unknown_categories(
            "kstartup", [c.category for c in cands if c.source == "kstartup"]
        )

        profiles = {
            (p.source, p.external_id): p for p in s.scalars(select(NoticeProfile))
        }
        need = me.need_text()
        scored: list[tuple[tuple, _Candidate, rk.Fit]] = []

        for c in cands:
            np = profiles.get((c.source, c.external_id))
            # ③ 자격 — 기준일은 마감일이 있으면 마감일, 없으면 오늘.
            # plan/03 실측: 초기창업패키지 양식이 "(모집마감일 기준)" 이라고 적었다
            on = c.apply_end or today
            if np is None:
                rep.no_profile += 1
                scored.append(
                    (
                        rk.sort_key(str(FitVerdict.UNKNOWN), False, 0, _days(c, today)),
                        c,
                        rk.Fit(FitVerdict.UNKNOWN, "", (), (), False),
                    )
                )
                continue

            j = el.judge(
                regions=tuple(np.regions or ()),
                industries=tuple(np.industries or ()),
                conditions=tuple(np.conditions or ()),
                company=me,
                on=on,
            )
            for u in j.unhandled:
                rep.unhandled[u] = rep.unhandled.get(u, 0) + 1
            if j.verdict is el.Verdict.FAIL:
                rep.failed_eligibility += 1
                continue
            if j.verdict is el.Verdict.UNKNOWN:
                rep.unknown_eligibility += 1
                scored.append(
                    (
                        rk.sort_key(str(FitVerdict.UNKNOWN), False, 0, _days(c, today)),
                        c,
                        rk.Fit(FitVerdict.UNKNOWN, "", (), (), False),
                    )
                )
                continue

            # ④ 분야
            m = sc.match(c.source, c.category, need)
            if m.hit:
                rep.sector_hit += 1

            # ⑤ 순서와 이유
            fit = rk.judge(
                keywords=tuple(np.keywords or ()), nodes=me.nodes, sector_hit=m.hit
            )
            if fit.verdict is FitVerdict.MATCH:
                rep.match += 1
            elif fit.verdict is FitVerdict.MAYBE:
                rep.maybe += 1
            else:
                rep.miss += 1
            scored.append(
                (
                    rk.sort_key(
                        str(fit.verdict), m.hit, len(fit.matched), _days(c, today)
                    ),
                    c,
                    fit,
                )
            )

        scored.sort(key=lambda t: t[0])
        rep.top = [
            (c.source, c.title, f.reason)
            for _k, c, f in scored
            if f.verdict is FitVerdict.MATCH
        ][:TOP_N]

        if save:
            _save_fits(s, company_id, scored)
            s.commit()

    return rep


def _days(c: _Candidate, today: dt.date) -> int | None:
    return None if c.apply_end is None else (c.apply_end - today).days


def _save_fits(s: Session, company_id: str, scored: list) -> None:
    """**`맞다` 와 `애매` 만 앉힌다.**

    `아니다` 를 다 앉히면 회사마다 수백 행이 쌓이는데 재계산이 공짜라(0.36초)
    저장이 손해다. `확인 필요` 도 안 앉힌다 — 그건 아직 안 본 것이라 남길 값이 없다.
    """
    ids = s.scalars(
        select(NoticeFit.id).where(NoticeFit.company_id == company_id)
    ).all()
    if ids:
        s.execute(delete(NoticeFitEvidence).where(NoticeFitEvidence.fit_id.in_(ids)))
        s.execute(delete(NoticeFit).where(NoticeFit.id.in_(ids)))
        s.flush()

    for _k, c, f in scored:
        if f.verdict not in (FitVerdict.MATCH, FitVerdict.MAYBE):
            continue
        row = NoticeFit(
            company_id=company_id,
            source=c.source,
            external_id=c.external_id,
            verdict=str(f.verdict),
            reason=f.reason,
            sector_hit=f.sector_hit,
            matched=list(f.matched),
            computed_at=dt.datetime.now(dt.UTC),
        )
        s.add(row)
        s.flush()
        for fid in f.evidence:
            s.add(NoticeFitEvidence(fit_id=row.id, fact_id=fid))


# ─────────────────────────────── 퍼널 ───────────────────────────────


def report(*, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    with Session(engine) as s:
        total = s.scalar(select(func.count()).select_from(Notice)) or 0
        keys = _open_ids(s, today)
        prof = s.scalar(select(func.count()).select_from(NoticeProfile)) or 0
        fits = s.scalar(select(func.count()).select_from(NoticeFit)) or 0
        companies = sorted(set(s.scalars(select(NoticeFit.company_id))))
    out = [
        f"전량 {total:,}",
        f"열린 공고 {len(keys):,}",
        f"  ① 정규화된 것 {prof:,}"
        + ("   ← 0 이다. 키가 없거나 아직 안 돌렸다" if prof == 0 else ""),
        f"  ⑤ 저장된 적합도 {fits:,} · 회사 {len(companies):,} {companies[:5]}",
    ]
    return "\n".join(out)
