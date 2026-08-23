"""2층(추천) — **공고가 주는 것 ∩ 회사가 필요한 것** — 실측용 버리는 코드.

지금 ⑤(취지 키워드 교집합)는 공고의 자유 낱말과 위키의 자유 문장을 문자열로
겹친다. 노드를 30 → 143 으로 늘려도 겹침이 11% → 12% 였다 — **재료가 아니라
축의 문제다.**

여기서 재는 것은 **양쪽이 같은 닫힌 표에서 고르면 만나는가**이다.

    지금   ④ sectors.match(분류 코드값 × 로드맵 노드 grep)
           ⑤ rank.judge(공고 keywords[] × 노드 text 문자열 교집합)
    새로   needs[] (닫힌 15) ∩ needs[] (같은 15)

    uv run python spike/needs.py            # 공고 50건 + 회사 1건 뽑기
    uv run python spike/needs.py --cmp      # 지금 대 새로
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "spike")

from cond_axes import pick  # noqa: E402

from finnect import llm, trace  # noqa: E402
from finnect.db import session_scope  # noqa: E402
from finnect.match import normalize as nz  # noqa: E402
from finnect.match import profile as mp  # noqa: E402
from finnect.match import rank as rk  # noqa: E402
from finnect.match import sectors  # noqa: E402
from finnect.models import BizinfoNotice, KstartupNotice  # noqa: E402

OUT = Path("out")
COMPANY = "c_dasiro"

# ══════════════════════════════════════════════════════════════════
# 닫힌 표 열다섯. **양쪽이 이 표에서만 고른다**
# ══════════════════════════════════════════════════════════════════
NEEDS: dict[str, str] = {
    "funding_investment": "투자 유치",
    "funding_loan": "융자·보증",
    "funding_operating": "사업화 자금",
    "rnd": "기술개발",
    "prototype_cert": "시제품·인증",
    "ip": "특허·기술이전",
    "sales_domestic": "국내 판로",
    "sales_overseas": "해외 판로",
    "public_procurement": "공공 조달",
    "space": "공간·입주",
    "hiring": "채용",
    "equipment": "장비",
    "mentoring": "멘토링·컨설팅",
    "education": "교육",
    "open_innovation": "대기업 협업·오픈이노베이션",
}
_TABLE = "\n".join(f"    {k:20} {v}" for k, v in NEEDS.items())

#: n2 — **칸마다 경계를 적는다.**
#:
#: n1 에서 need 이 0개인 공고가 5건이었고 **그중 4건은 칸이 있는데 안 골랐다** —
#: 딥테크 스튜디오(공공기술 활용)에 `ip` 가 있고, 대기업 매칭에 `open_innovation`
#: 이 있고, 혁신아이콘에 `funding_loan` 이 있고, 1인 창조기업 지원센터에 `space`
#: 가 있었다. **칸이 모자란 것이 아니라 칸의 뜻이 안 적혀 있었다.**
_TABLE_V2 = "\n".join(
    f"    {k:20} {v:14} {d}"
    for (k, v), d in zip(
        NEEDS.items(),
        [
            "IR · 데모데이 · VC 매칭 · 투자 연계",
            "정책자금 대출 · 신용보증 · 이차보전 · 성장자금 보증",
            "인건비 · 외주 · 마케팅비를 직접 준다",
            "R&D 과제 · 기술개발 자금",
            "시제품 제작 · 실증 · 시험 · 인증 취득 비용",
            "출원·등록 비용 · 기술 임치 · 공공기술 이전 · IP 평가",
            "유통 입점 · 홍보 · 국내 전시 · 국내 바이어 매칭",
            "수출 · 해외 전시 · 현지화 · 해외 물류비 · 지사화",
            "조달청 등록 · 공공기관 실증 · 벤처나라 · 공공구매",
            "사무실 · 보육센터 입주 · 임대료 · 창업공간",
            "인건비 지원 · 인력 매칭 · 고용장려금",
            "장비 사용료 · 바우처 · 연구시설 인프라 이용",
            "전문가 자문 · 진단 · 컨설팅 · 애로 해결",
            "교육과정 · 아카데미 · 워크숍",
            "중견·대기업 매칭 · 오픈이노베이션 · 공공데이터 협업 · 네트워킹",
        ],
        strict=True,
    )
)

SYS_NOTICE = f"""\
너는 한국 정부·지자체 지원사업 공고를 읽고 **이 공고가 신청 기업에게 무엇을 주는가**를
고르는 분류기다. 아래 표에서만 고른다.

{_TABLE}

## 규칙
- **1~3개만 고른다.** 넓게 고르면 아무 회사에나 맞아서 순서가 뜻을 잃는다
- **지원 내용이 실제로 주는 것**을 고른다. 신청 자격이나 대상 업종이 아니다
- 표에 없으면 **빈 배열이다.** 억지로 고르지 마라
- `evidence` 에 그렇게 고른 근거를 **원문에서 그대로** 20자 이상 낸다
"""

#: n2 — 제약을 푼다. n1 에서 「1~3개」와 「표에 없으면 빈 배열」이 너무 세서
#: **『글로벌 교류·투자유치 지원사업』이 `funding_investment` 를 안 골랐다**
#: (제목에 있는데 본문이 해외 진출 중심이라 `sales_overseas` 만 냈다).
SYS_NOTICE_V2 = f"""\
너는 한국 정부·지자체 지원사업 공고를 읽고 **이 공고가 신청 기업에게 무엇을 주는가**를
고르는 분류기다. 아래 표에서만 고른다.

{_TABLE_V2}

## 규칙
- **주된 것을 먼저 내고 1~4개까지 낸다.** 공고가 둘 이상을 주면 둘 이상 낸다 —
  제목에 `투자유치` 가 있으면 본문이 해외 진출 중심이어도 투자 유치를 같이 낸다
- **지원 내용이 실제로 주는 것**을 고른다. 신청 자격이나 대상 업종이 아니다
- **가장 가까운 칸을 고른다.** 낱말이 표와 달라도 하는 일이 같으면 그 칸이다 —
  `기술자료 임치` 는 `ip` 이고 `대기업 매칭` 은 `open_innovation` 이다.
  **정말 표 밖일 때만** 빈 배열이다
- `evidence` 에 그렇게 고른 근거를 **원문에서 그대로** 20자 이상 낸다
"""

SYS_COMPANY = f"""\
너는 한 회사의 사업 위키를 읽고 **이 회사가 지금 무엇이 필요한가**를 고르는 분류기다.
아래 표에서만 고른다. 공고를 고르는 데 쓸 값이다.

{_TABLE}

## 규칙
- **지금·가까운 계획에 있는 것**만 고른다. 언젠가 필요할 것을 다 고르면 안 된다
- 위키에 **근거 문장이 있는 것**만 고른다. 없으면 안 고른다
- 하나마다 `evidence` 에 그 근거를 위키 문장에서 **그대로** 낸다
- 3~6개가 보통이다
"""

#: n2 — **질문을 바꾼다.** n1 은 「지금 필요한 것」을 물었고, 그래서 이미 출원한
#: 특허를 안 골랐다("필요"가 아니라 "보유"다). 그 결과 `[경기] 성남시 기술자료
#: 임치 수수료 지원사업`(공고 need = `ip`)이 교집합에서 빠졌다 —
#: **틀린 답이 아니라 틀린 질문이었다.**
SYS_COMPANY_V2 = f"""\
너는 한 회사의 사업 위키를 읽고 **이 회사가 지원사업에서 받으면 쓸 수 있는 것**을
고르는 분류기다. 아래 표에서만 고른다. 공고를 고르는 데 쓸 값이다.

{_TABLE_V2}

## 두 가지가 해당한다
1. **지금 계획에 있어서 필요한 것** — 로드맵·자금계획·채용계획에 적혀 있는 것
2. **이미 가진 것이 있어서 그 분야 지원을 쓸 수 있는 것** —
   특허를 출원했으면 `ip` 를 쓸 수 있고, 시제품이 있으면 `prototype_cert` 를 쓸 수 있다

**2번을 빠뜨리지 마라.** 「필요」만 보면 이미 가진 것이 다 빠지는데, 지원사업은
가진 것을 요구하는 경우가 많다.

## 규칙
- 위키에 **근거 문장이 있는 것**만 고른다. 없으면 안 고른다
- 하나마다 `evidence` 에 그 근거를 위키 문장에서 **그대로** 낸다
- 4~8개가 보통이다
"""

ROUNDS: dict[str, tuple[str, str]] = {
    "n1": (SYS_NOTICE, SYS_COMPANY),
    "n2": (SYS_NOTICE_V2, SYS_COMPANY_V2),
}


def _schema(with_ev: bool) -> dict:
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["need", "evidence"],
        "properties": {
            "need": {"type": "string", "enum": list(NEEDS)},
            "evidence": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["needs"],
        "properties": {"needs": {"type": "array", "items": item}},
    }


def notice_needs(round_: str) -> None:
    system, _ = ROUNDS[round_]
    picks = pick()
    cats = _categories()

    def one(t):  # noqa: ANN001, ANN202
        b, _ = t
        c = llm.client()
        rec = {"key": f"{b.source}:{b.external_id}", "title": b.title[:70],
               "category": cats.get((b.source, b.external_id), "")}
        try:
            out = c.json(system=system, user=nz.user_prompt(b),
                         schema=_schema(True), schema_name="notice_needs")
            rec["needs"] = out.get("needs") or []
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        rec["_u"] = (c.usage.calls, c.usage.input_tokens, c.usage.output_tokens)
        return rec

    with ThreadPoolExecutor(max_workers=8) as ex:
        recs = list(ex.map(one, picks))
    total = llm.Usage()
    for r in recs:
        a, i, o = r.pop("_u", (0, 0, 0))
        total.merge(llm.Usage(calls=a, input_tokens=i, output_tokens=o))
    (OUT / f"spike-needs-notice-{round_}.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{round_}] 공고 {len(recs)}건 · {total.line()}")


def _categories() -> dict[tuple[str, str], str]:
    """④가 읽는 분류 코드값. **기업마당은 중분류다**(`service.py:314`)."""
    from sqlalchemy import select
    out: dict[tuple[str, str], str] = {}
    with session_scope() as s:
        for i, c in s.execute(select(
            BizinfoNotice.pblancId, BizinfoNotice.pldirSportRealmMlsfcCodeNm)):
            out[("bizinfo", i)] = c or ""
        for i, c in s.execute(select(
            KstartupNotice.pbanc_sn, KstartupNotice.supt_biz_clsfc)):
            out[("kstartup", i)] = c or ""
    return out


def company_needs(round_: str) -> None:
    """회사 쪽. **위키 노드를 그대로 넣는다** — 트랙 B 에 칸을 더하기 전의 대역이다."""
    _, system = ROUNDS[round_]
    with session_scope() as s:
        prof = mp.load(s, COMPANY)
    #: ④가 읽는 갈래를 앞에 두고 나머지를 붙인다. 노드가 220개라 다 넣으면 길다
    head = [n for n in prof.nodes if n.place.split("/", 1)[0] in mp.NEED_NODES]
    rest = [n for n in prof.nodes if n not in head]
    text = "\n".join(f"[{n.place}] {n.text}" for n in (head + rest))[:14000]
    c = llm.client()
    out = c.json(system=system, user=text,
                 schema=_schema(True), schema_name="company_needs")
    (OUT / f"spike-needs-company-{round_}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{round_}] 회사 {COMPANY} · {c.usage.line()}")
    for n in out.get("needs", []):
        print(f"  {NEEDS[n['need']]:16} ← {n['evidence'][:52]}")


def compare(round_: str) -> None:
    """지금(④+⑤) 대 새로(need 교집합). **같은 50건이다.**"""
    notices = json.loads(
        (OUT / f"spike-needs-notice-{round_}.json").read_text(encoding="utf-8"))
    mine = json.loads(
        (OUT / f"spike-needs-company-{round_}.json").read_text(encoding="utf-8"))
    my_needs = {n["need"] for n in mine.get("needs", [])}
    my_ev = {n["need"]: n["evidence"] for n in mine.get("needs", [])}
    # ⑤의 입력 — 지금 스키마로 뽑은 keywords
    prod = {r["key"]: r for r in json.loads(
        (OUT / "spike-prod-profile.json").read_text(encoding="utf-8")) if "error" not in r}

    with session_scope() as s:
        prof = mp.load(s, COMPANY, on=dt.date.today())
    need_text = prof.need_text()

    print(f"내 필요 — {' · '.join(NEEDS[n] for n in sorted(my_needs))}\n")
    rows = []
    for r in notices:
        if "error" in r:
            continue
        src = r["key"].split(":", 1)[0]
        # --- 지금 ④ ---
        m = sectors.match(src, r["category"], need_text)
        # --- 지금 ⑤ ---
        p = prod.get(r["key"], {})
        fit = rk.judge(keywords=tuple(p.get("keywords", ())), nodes=prof.nodes,
                       sector_label=sectors.label(m.bucket), sector_cues=m.cues)
        # --- 새로 ---
        their = {n["need"] for n in r.get("needs", [])}
        inter = sorted(their & my_needs)
        rows.append({
            "key": r["key"], "title": r["title"],
            "old_verdict": str(fit.verdict), "old_reason": fit.reason,
            "old_sector": m.bucket if m.hit else "",
            "their": sorted(their), "inter": inter,
            "new_reason": (f"{NEEDS[inter[0]]}{'·' + NEEDS[inter[1]] if len(inter) > 1 else ''}"
                           f"{rk.josa(NEEDS[inter[-1]], '이', '가')} 필요하다고 하셨어요. "
                           f"{my_ev.get(inter[0], '')[:46]}") if inter else "",
        })
    (OUT / f"spike-needs-cmp-{round_}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    old_rec = [r for r in rows if r["old_reason"]]
    new_rec = [r for r in rows if r["inter"]]
    print(f"{'':22}{'지금 ④+⑤':>12}{'새로 need':>12}")
    print(f"  {'이유가 만들어진 공고':20}{len(old_rec):>12}{len(new_rec):>12}")
    print(f"  {'맞다(MATCH)':20}{sum(1 for r in rows if r['old_verdict']=='맞다'):>12}{'—':>12}")
    print(f"  {'④ 분야가 걸린 공고':20}{sum(1 for r in rows if r['old_sector']):>12}{'—':>12}")
    print(f"  {'need 이 붙은 공고':20}{'—':>12}{sum(1 for r in rows if r['their']):>12}")
    print()
    print("=== 공고 쪽 need 분포 — 갈라 주나 ===")
    cnt = Counter(n for r in rows for n in r["their"])
    for k, v in cnt.most_common():
        print(f"  {NEEDS[k]:16} {v:3}  {'█'*v}")
    print(f"\n  need 이 0개인 공고 {sum(1 for r in rows if not r['their'])}건")


if __name__ == "__main__":
    #: `python spike/needs.py n2` · `python spike/needs.py n2 --cmp`
    rnd = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ROUNDS else "n1"
    what = next((a for a in sys.argv[1:] if a.startswith("--")), "--all")
    OUT.mkdir(exist_ok=True)
    if what in ("--all", "--notice"):
        notice_needs(rnd)
    if what in ("--all", "--company"):
        company_needs(rnd)
    if what in ("--all", "--cmp"):
        compare(rnd)
    trace.flush()
