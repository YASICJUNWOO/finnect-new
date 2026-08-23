"""오탈락을 센다 — **떨어뜨린 것 중 좋았던 게 몇 건인가** (실측용 버리는 코드).

지금까지 잰 것은 전부 **보여 준 것의 정밀도**였다(육안 8/8 은 우리가 통과시킨 8건이다).
「골라 준다」가 제품 약속인데 치명적 실패는 오추천이 아니라 **조용히 떨어뜨리는 것**이고,
ADR-0003 이 판정 근거를 화면에 안 내기로 해서 **사용자가 알아챌 방법도 없다.**

`service.run()` 을 베끼지 않고 같은 재료를 다시 읽는다 — 저기는 집계만 돌려주고
**어느 공고가 왜 떨어졌는지**를 안 남긴다.

    uv run python spike/recall.py            # 사유별 집계
    uv run python spike/recall.py 소재지      # 그 사유로 떨어진 것을 전부 찍는다
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.db import engine
from finnect.match import eligible as el
from finnect.match import profile as pf
from finnect.match import service as sv
from finnect.models import NoticeProfile

COMPANY = "c_dasiro"

#: 탈락 사유 한 줄을 축으로 접는다. `eligible.judge()` 가 만드는 문구 그대로다
_AXIS = (
    ("소재지", re.compile(r"^소재지 ")),
    ("연령", re.compile(r"세\s*(이하|미만|까지)")),
    ("규모", re.compile(r"명$|소상공인|근로자")),
)


def axis_of(reason: str) -> str:
    for name, pat in _AXIS:
        if pat.search(reason):
            return name
    return "기타"


def collect() -> list[dict]:
    today = dt.date.today()
    out: list[dict] = []
    with Session(engine) as s:
        me = pf.load(s, COMPANY, on=today)
        cands = sv._candidates(s, today, None)
        profiles = {
            (p.source, p.external_id): p for p in s.scalars(select(NoticeProfile))
        }
        for c in cands:
            np = profiles.get((c.source, c.external_id))
            if np is None:
                continue
            on = c.apply_end or today
            j = el.judge(
                regions=tuple(np.regions or ()),
                industries=tuple(np.industries or ()),
                conditions=tuple(np.conditions or ()),
                company=me,
                on=on,
            )
            out.append(
                {
                    "key": f"{c.source}:{c.external_id}",
                    "title": (c.title or "")[:64],
                    "verdict": str(j.verdict),
                    "reasons": list(j.reasons),
                    "unknowns": list(j.unknowns),
                    "regions": list(np.regions or ()),
                    "industries": list(np.industries or ()),
                }
            )
    return out


def main() -> None:
    rows = collect()
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    fail = [r for r in rows if r["verdict"] == "fail"]
    unk = [r for r in rows if r["verdict"] == "unknown"]
    ok = [r for r in rows if r["verdict"] == "pass"]

    print(f"후보 {len(rows)} — 통과 {len(ok)} · 탈락 {len(fail)} · 확인필요 {len(unk)}\n")

    print("=== 탈락 사유 (축) ===")
    for a, n in Counter(axis_of(r["reasons"][0]) for r in fail if r["reasons"]).most_common():
        print(f"  {a:8} {n:4}")

    print("\n=== 확인필요 사유 (축) ===")
    for a, n in Counter(
        axis_of(r["unknowns"][0]) for r in unk if r["unknowns"]
    ).most_common():
        print(f"  {a:8} {n:4}")

    if want:
        print(f"\n=== '{want}' 로 떨어진 것 전부 ===")
        for r in fail:
            if not r["reasons"] or axis_of(r["reasons"][0]) != want:
                continue
            print(f"  {r['title']}")
            print(f"     {r['reasons'][0][:88]}")
    else:
        print("\n=== 소재지가 아닌 사유로 떨어진 것 전부 ===")
        for r in fail:
            if not r["reasons"] or axis_of(r["reasons"][0]) == "소재지":
                continue
            print(f"  {r['title']}")
            print(f"     {r['reasons'][0][:88]}")


if __name__ == "__main__":
    main()
