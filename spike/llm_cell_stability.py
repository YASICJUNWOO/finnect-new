"""같은 양식을 여러 번 물어 **답이 흔들리는지** 잰다.

레포가 「판정을 프롬프트에 맡기면 흔들린다」를 위키 추출에서 여러 번 겪었다. 트랙 B
값이 회차마다 달라져 **없는 회귀가 넷 보였고**, 추출 정확도 70.3% 는 다시 재니 60.2%
와 58.5% 가 나왔다. 그래서 새 LLM 판정을 채택하기 전에 이 숫자를 먼저 본다.

## 무엇이 흔들리면 곤란한가

**값자리로 고른 칸 집합**이다. 회차마다 다르면 같은 양식을 두 번 읽을 때 채워지는
칸이 달라지고, 사용자가 「어제는 채워졌는데」를 겪는다. 좌표는 DB 에 저장되므로
한 번 정해지면 굳지만, **처음 한 번이 운이면 그 운이 굳는다.**

라벨 매달기(`label_of`)도 같이 본다. 값자리는 같은데 라벨이 갈리면 그 칸에 들어갈
값의 뜻이 달라진다.

**버리는 코드다**(`spike/`).
"""

from __future__ import annotations

import sys
from collections import Counter

from finnect.attach import store
from finnect.forms import open_form
from spike.llm_cell_pick import SCHEMA, SYSTEM, _render

CASES = [
    ("e679598ef461124b9024e6245e3d18756f2e6df8c3a0724f9b90e51425676481", "hwp", "125460 신청서"),
    ("abde9fb7e4d4ebabc70220feef601bc4c51bdf870c64ee159945f7c9315ffd71", "hwp", "178926 신청서"),
]


def _ask(table: str, client) -> dict:  # noqa: ANN001
    got = client.json(
        system=SYSTEM, user=table, schema=SCHEMA, schema_name="cell_roles"
    )
    return {c["n"]: c for c in got["cells"]}


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    from finnect import llm, trace

    client = llm.client()

    for sha, ext, name in CASES:
        form = open_form(str(store.abs_path(store.rel_path(sha))), ext)
        table, at = _render(form.cells())
        print(f"\n{'=' * 62}\n{name} · 칸 {len(at)}개 · {rounds}회\n{'=' * 62}")

        runs: list[dict[int, dict]] = []
        for i in range(rounds):
            try:
                runs.append(_ask(table, client))
            except Exception as e:  # noqa: BLE001
                print(f"  {i + 1}회차 실패: {type(e).__name__}: {e}")
        if len(runs) < 2:
            continue

        picks = [{n for n, c in r.items() if c["role"] == "값자리"} for r in runs]
        for i, p in enumerate(picks):
            print(f"  {i + 1}회차 값자리 {len(p)}개")

        always = set.intersection(*picks)
        ever = set.union(*picks)
        wobbly = ever - always
        print(f"\n  늘 고른 칸   {len(always)}")
        print(f"  한 번이라도  {len(ever)}")
        print(f"  흔들린 칸    {len(wobbly)}  {sorted(wobbly) if wobbly else ''}")
        print(f"  안정도       {len(always) / len(ever) * 100:.1f}%")

        # 흔들린 칸이 무엇이었는지 원문으로 보여 준다
        rev = {n: a for n, a in at.items()}
        for n in sorted(wobbly)[:8]:
            roles = [r.get(n, {}).get("role", "—") for r in runs]
            print(f"     [{n}] {rev[n]}  회차별 역할: {' / '.join(roles)}")

        # 늘 고른 칸에서 라벨 매달기가 같은가
        drift = 0
        for n in sorted(always):
            labs = {r[n].get("label_of") for r in runs}
            if len(labs) > 1:
                drift += 1
                if drift <= 5:
                    print(f"     [{n}] 라벨이 갈림: {labs}")
        print(f"  라벨이 갈린 칸 {drift} / {len(always)}")

        dist = Counter(c["role"] for r in runs for c in r.values())
        print(f"  역할 분포(전 회차 합) {dict(dist)}")

        clash = [
            len({n for n, c in r.items() if c["role"] == "라벨"} & p)
            for r, p in zip(runs, picks, strict=True)
        ]
        print(f"  라벨이면서 값자리 회차별 {clash}")

    trace.flush()


if __name__ == "__main__":
    main()
