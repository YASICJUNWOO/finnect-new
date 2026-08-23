"""위키 한 벌을 재는 잣대 — plan/23 T-0143.

**같은 회사를 프롬프트 바꿔 가며 잴 때 쓴다.** 세는 것을 코드로 고정해 두지 않으면
회차마다 다른 것을 세게 되고, 그러면 두 회차를 비교할 수 없다.

    uv run python tools/measure-wiki.py c_dasiro

`spike/` 와 달리 버리는 코드가 아니지만 **제품 경로도 아니다** — `src/finnect/` 의
어떤 모듈도 이 파일을 임포트하지 않는다.
"""

from __future__ import annotations

import collections
import re
import sys

from sqlalchemy import func, select

from finnect.db import SessionFactory
from finnect.models import CompanyValue, WikiFact, WikiNode
from finnect.wiki import profile, spots


def main(company: str) -> None:
    with SessionFactory() as s:
        facts = s.scalars(select(WikiFact).where(WikiFact.company_id == company)).all()
        nodes = s.scalars(select(WikiNode).where(WikiNode.company_id == company)).all()
        by_id = {n.id: n for n in nodes}

        review = next((n for n in nodes if n.path == spots.REVIEW.path), None)
        in_review = [f for f in facts if review and f.node_id == review.id]

        names = [f.key for f in facts if f.key]
        values = [f for f in facts if f.key and f.value is not None]

        print(f"══ {company} ══")
        print(f"사실 {len(facts)}  (값 {len(values)} · 서술 {len(facts) - len(values)})")
        print(f"노드 {len(nodes)}")

        # ── 자리표를 지키나 ──
        off = [n.path for n in nodes if n.path not in spots.FOLDERS and spots.spot_of(n.path) is None]
        filled = {
            sp.path
            for n in nodes
            if (sp := spots.spot_of(n.path)) and sp.path != spots.REVIEW.path
            and any(f.node_id == n.id for f in facts)
        }
        print(f"찬 자리 {len(filled)}/{len(spots.SPOTS)}   ·   뼈대(자리표 밖 마디) {len(off)}")

        # ── 검토 대기 ──
        pct = 100 * len(in_review) / len(facts) if facts else 0
        print(f"\n검토 대기 {len(in_review)}건 ({pct:.0f}%)")
        why = collections.Counter()
        for f in in_review:
            m = re.search(r"\[([^\]]+)\]", f.text)
            why[_bucket(m.group(1) if m else "(사유 없음)")] += 1
        for k, v in why.most_common():
            print(f"   {v:>3}  {k}")

        # ── ① 이름이 이력을 세울 만큼 안정적인가 ──
        kinds = len(set(names))
        ratio = len(names) / kinds if kinds else 0
        print(f"\n값 {len(values)} · 서술 {len(facts) - len(values)}")
        print(f"이름 {len(names)}건 / {kinds}종  →  종당 {ratio:.2f}건")
        print("   **1에 가까우면 이력이 안 쌓인다** — 같은 이름이 시점마다 서야 한다")
        dated = [q for q in set(names) if re.search(r"\d{4}\s*년|\d{4}-|분기", q)]
        print(f"   시점이 이름에 박힌 것 {len(dated)}종 — {' · '.join(sorted(dated)[:5])}")
        overlap = sorted({q for q in set(names) if profile.key_of(q)})
        print(f"   매칭 정보와 같은 것 {len(overlap)}종 — {' · '.join(overlap[:6])}")
        # 한 이름에 시점이 여럿 = 이력이 섰다
        import collections as _c
        hist = _c.Counter(f.key for f in values if f.as_of)
        stacked = {k: n for k, n in hist.items() if n > 1}
        print(f"   **이력이 선 이름 {len(stacked)}종** — {' · '.join(sorted(stacked)[:5])}")

        # ── 인스턴스 이름이 자리를 건너뛰나 ──
        print("\n인스턴스 자리")
        seen: dict[str, list[str]] = {}
        for n in sorted(nodes, key=lambda x: x.path):
            sp = spots.spot_of(n.path)
            if sp and not sp.fixed and (name := sp.instance(n.path)):
                seen.setdefault(name, []).append(sp.path)
        for name, where in sorted(seen.items()):
            mark = "  ← 자리 둘에 같은 이름" if len(where) > 1 else ""
            print(f"   {name}{mark}")

        # ── 트랙 B ──
        vals = s.scalars(select(CompanyValue.key).where(CompanyValue.company_id == company)).all()
        print(f"\n매칭 정보 {len(set(vals))}/14 칸")
        _ = by_id, func


def _bucket(why: str) -> str:
    """사유를 묶는다. `spot=47` 과 `spot=65` 는 같은 병이다."""
    if "spot=" in why:
        return "표 밖 번호를 냈다 (spot=47~)"
    if "이름이 안 왔" in why:
        return "인스턴스 이름을 안 채웠다"
    return why[:44]


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "c_dasiro")
