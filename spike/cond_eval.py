"""축 조건이 실제 자격 판정을 바꾸나 — 다시로 한 회사로 잰다.

    지금  conditions[] 자유 문자열  →  eligible.py 정규식
    새로  축 조건 + **코드가 정하는 OR**

**OR 을 모델에 안 묻는다.** `alt` 를 물어 봤더니 같은 공고에서 회차마다 갈렸다
(9/18 일치). 대신 축 족보로 코드가 정한다 — 규모 족(소상공인·중소기업·직원수)에서
둘 이상이 오면 OR 이고, `예비창업자` 와 `업력` 이 같이 오면 OR 이다.
둘 다 **같이 요구될 수 없는 조건**이라 코드가 알 수 있다.
"""
from __future__ import annotations
import sys; sys.path.insert(0, "spike")
from cond_axes import load, regex_axis
import json

#: 다시로 — 실제 위키 값
ME = {"location": "경기도 성남시", "headcount": 10, "years": 2.4,
      "entity": "법인", "sme": True, "small_business": False}

SIZE = {"small_business", "sme", "headcount"}
PASS, FAIL, UNK = "통과", "탈락", "확인필요"


def judge_one(c: dict) -> str:
    ax, op, v = c["axis"], c["op"], c.get("value")
    if ax == "business_years" and v is not None:
        if op in ("lte", "lt"):
            return PASS if ME["years"] <= v else FAIL
        if op in ("gte", "gt"):
            return PASS if ME["years"] >= v else FAIL
        return UNK
    if ax == "headcount" and v is not None:
        if op in ("lte", "lt"):
            return PASS if ME["headcount"] < v else FAIL
        if op in ("gte", "gt"):
            return PASS if ME["headcount"] >= v else FAIL
        return UNK
    if ax == "small_business":
        return FAIL if not ME["small_business"] else PASS
    if ax == "sme":
        return PASS if ME["sme"] else FAIL
    if ax == "entity_type":
        return FAIL if "예비창업" in c["quote"] or "창업예정" in c["quote"] else UNK
    return UNK  # certification · revenue · capital · funding · gov_program


def judge_new(conds: list[dict]) -> str:
    live = [c for c in conds if c["axis"] != "other"]
    if not live:
        return UNK
    # --- 코드가 정하는 OR ---
    size = [c for c in live if c["axis"] in SIZE]
    preli = [c for c in live if c["axis"] == "entity_type"
             and ("예비창업" in c["quote"] or "창업예정" in c["quote"])]
    yrs = [c for c in live if c["axis"] == "business_years"]
    groups: list[list[dict]] = []
    used = set()
    if len(size) >= 2:
        groups.append(size); used |= {id(c) for c in size}
    if preli and yrs:
        g = preli + yrs
        groups.append(g); used |= {id(c) for c in g}
    for c in live:
        if id(c) not in used:
            groups.append([c])
    # 그룹 하나는 안에서 OR, 그룹끼리는 AND
    outs = []
    for g in groups:
        vs = [judge_one(c) for c in g]
        outs.append(PASS if PASS in vs else (UNK if UNK in vs else FAIL))
    if FAIL in outs:
        return FAIL
    return UNK if UNK in outs else PASS


def judge_old(conds: list[str]) -> str:
    read = [(c, regex_axis(c)) for c in conds]
    live = [(c, a) for c, a in read if a != "unhandled"]
    if not live:
        return UNK if not conds else PASS  # 못 읽으면 조용히 통과한다
    for c, a in live:
        if a == "small_business" and not ME["small_business"]:
            return FAIL
        if a == "headcount":
            return UNK
    return PASS


old_raw = {r["key"]: r["A"] for r in json.load(open("out/spike-cond-axes.json"))}
new = {r["key"]: r for r in load("v2") if "error" not in r}

rows = []
for k, nr in new.items():
    a = old_raw.get(k, {})
    o = judge_old(a.get("conditions", [])) if "error" not in a else UNK
    n = judge_new(nr["conditions"])
    rows.append((k, nr["title"][:34], o, n))

from collections import Counter
print(f"{'':10}{'통과':>6}{'탈락':>6}{'확인필요':>8}")
for lbl, i in (("지금", 2), ("새로", 3)):
    c = Counter(r[i] for r in rows)
    print(f"  {lbl:8}{c[PASS]:>6}{c[FAIL]:>6}{c[UNK]:>8}")
print()
print("=== 판정이 갈린 공고 ===")
for k, t, o, n in rows:
    if o == n:
        continue
    print(f"  {o:>4} → {n:<4}  {k[:24]:26} {t}")
