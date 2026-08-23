"""표본을 늘려 **칸 판정이 포맷과 양식 구조를 건너 버티는지** 잰다.

앞선 실측(`llm_cell_stability.py`)은 hwp 두 건이었다. 여기서는 포맷을 섞고 건수를
늘린다. 재는 것은 셋이다.

1. **안정도** — 같은 양식을 두 번 물어 값자리 집합이 같은가
2. **불변식 위반** — 라벨로 분류한 칸을 값자리로도 골랐나. **0 이어야 한다**
3. **코드 규칙과의 차이** — `label_targets` 가 몇 칸을 내고 LLM 이 몇 칸을 내나

## 스레드를 쓰되 JVM 은 메인에서만 만진다

파일을 여는 것은 hwp 에서 JVM 을 부른다. **표 문자열을 먼저 다 만들어 두고** LLM
호출만 병렬로 돌린다 — jpype 핸들이 스레드를 건너가지 않는다.

**클라이언트를 스레드마다 만든다.** `Usage.calls += 1` 이 원자적이 아니라 하나를
공유하면 토큰 수가 어긋난다(`draft/write.py` 가 같은 이유로 만드는 함수를 받는다).

**버리는 코드다**(`spike/`).
"""

from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from finnect.attach import store
from finnect.db import SessionFactory
from finnect.forms import SUPPORTED, label_targets, open_form
from finnect.models import AttachmentFile, Document
from spike.llm_cell_pick import SCHEMA, SYSTEM, _render

#: 프롬프트 상한. **처음에 220 으로 걸었던 것은 근거가 없었다** — 실측에서 452칸
#: 양식이 8,105자였다. 자르면 큰 양식이 통째로 빠져 **쉬운 표본만 재게 된다.**
#: 지금 남은 걱정은 입력이 아니라 **출력**이다(칸마다 답하므로 칸 수에 비례한다).
MAX_CELLS = 500
#: 표가 없거나 한 줄뿐이면 잴 것이 없다
MIN_CELLS = 6


def _pick(want: dict[str, int]) -> list[tuple[str, str, int]]:
    """포맷별로 골고루. **`document` 가 있는 파일만** — 제품이 실제로 읽는 것들이다."""
    out: list[tuple[str, str, int]] = []
    with SessionFactory() as s:
        rows = s.execute(
            select(Document.sha256, AttachmentFile.detected_ext, func.count(Document.id))
            .join(AttachmentFile, AttachmentFile.sha256 == Document.sha256)
            .where(AttachmentFile.detected_ext.in_(sorted(SUPPORTED)))
            .group_by(Document.sha256, AttachmentFile.detected_ext)
            .order_by(Document.sha256)
        ).all()
    left = dict(want)
    for sha, ext, n in rows:
        if left.get(ext, 0) <= 0:
            continue
        out.append((sha, ext, n))
        left[ext] -= 1
        if not any(v > 0 for v in left.values()):
            break
    return out


def _ask(table: str) -> dict[int, dict] | None:
    from finnect import llm

    try:
        got = llm.client().json(
            system=SYSTEM, user=table, schema=SCHEMA, schema_name="cell_roles"
        )
    except Exception as e:  # noqa: BLE001
        print(f"    ! 호출 실패 {type(e).__name__}: {e}", flush=True)
        return None
    return {c["n"]: c for c in got["cells"]}


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    want = {"hwp": 9, "hwpx": 4, "docx": 3}
    #: **큰 양식만 본다.** 앞 회차가 상한에 걸려 작은 것만 쟀고, 빠진 넷이 진짜
    #: 사업계획서였다. `--big` 이 그 편향을 뒤집어 확인하는 자리다
    big_only = "--big" in sys.argv

    # ── 1단계: 파일을 열어 표를 만든다 (JVM · 메인 스레드)
    cases: list[tuple[str, str, str, dict, int]] = []
    for sha, ext, _ in _pick(want):
        try:
            cells = open_form(str(store.abs_path(store.rel_path(sha))), ext).cells()
        except Exception as e:  # noqa: BLE001
            print(f"  ! {sha[:8]} {ext} 못 엶: {type(e).__name__}")
            continue
        low = 240 if big_only else MIN_CELLS
        if not (low <= len(cells) <= MAX_CELLS):
            print(f"  · {sha[:8]} {ext} 칸 {len(cells)}개라 건너뜀")
            continue
        table, at = _render(cells)
        cases.append((sha, ext, table, at, len(label_targets(cells))))

    print(f"\n표본 {len(cases)}건 · 각 {rounds}회 · 호출 {len(cases) * rounds}회\n")

    # ── 2단계: LLM 호출만 병렬로
    jobs = [(i, r) for i in range(len(cases)) for r in range(rounds)]
    with ThreadPoolExecutor(max_workers=6) as ex:
        answers = list(ex.map(lambda j: _ask(cases[j[0]][2]), jobs))

    by_case: dict[int, list[dict]] = {}
    for (i, _), ans in zip(jobs, answers, strict=True):
        if ans is not None:
            by_case.setdefault(i, []).append(ans)

    # ── 3단계: 집계
    tally = Counter()
    print(f"{'파일':10} {'포맷':5} {'칸':>4} {'규칙':>5} {'LLM':>5} {'안정도':>7} {'충돌':>5} {'헛참조':>6}")
    print("─" * 60)
    for i, (sha, ext, _, at, rule_n) in enumerate(cases):
        runs = by_case.get(i, [])
        if len(runs) < 2:
            print(f"{sha[:8]:10} {ext:5} {len(at):4} {rule_n:5}     회차 부족")
            tally["회차 부족"] += 1
            continue

        picks = [{n for n, c in r.items() if c["role"] == "값자리"} for n_, r in enumerate(runs)]
        always, ever = set.intersection(*picks), set.union(*picks)
        stable = len(always) / len(ever) * 100 if ever else 100.0

        # 불변식 ① 라벨이면서 값자리
        clash = sum(
            len({n for n, c in r.items() if c["role"] == "라벨"} & p)
            for r, p in zip(runs, picks, strict=True)
        )
        # 불변식 ② label_of 가 라벨이 아닌 칸을 가리킴
        dangle = 0
        for r in runs:
            for n, c in r.items():
                if c["role"] != "값자리":
                    continue
                lab = c.get("label_of")
                if lab is None or r.get(lab, {}).get("role") not in ("라벨", "행머리"):
                    dangle += 1

        tally["표본"] += 1
        tally["규칙 쌍"] += rule_n
        tally["LLM 값자리"] += len(always)
        tally["충돌"] += clash
        tally["헛참조"] += dangle
        if stable == 100.0:
            tally["안정도 100%"] += 1
        print(
            f"{sha[:8]:10} {ext:5} {len(at):4} {rule_n:5} {len(always):5} "
            f"{stable:6.1f}% {clash:5} {dangle:6}"
        )

    print("─" * 60)
    print(f"\n표본 {tally['표본']}건 · 안정도 100% 인 것 {tally['안정도 100%']}건")
    print(f"코드 규칙 {tally['규칙 쌍']}쌍  →  LLM {tally['LLM 값자리']}칸")
    print(f"**라벨이면서 값자리(있으면 안 된다): {tally['충돌']}**")
    print(f"라벨을 안 가리키는 값자리: {tally['헛참조']}")
    if tally["회차 부족"]:
        print(f"회차가 모자라 못 잰 것: {tally['회차 부족']}건")

    from finnect import trace

    trace.flush()


if __name__ == "__main__":
    main()
