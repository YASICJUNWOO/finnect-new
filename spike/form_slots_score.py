"""값 자리 판정을 손으로 만든 정답지와 대조한다 (plan/24 T-0153).

**정답지가 사람이 채운 파일이다.** 2026-08-23 `bizinfo:PBLN_000000000125460` 신청서를
나린데이터 값으로 손수 채우고 한/글로 열어 확인했다([실측](
../docs/adr/evidence/2026-08-23-hwp-덮어쓰기가-된다.md)). 그때 「여기가 값 자리다」를
칸마다 사람이 정했으므로, 그 목록이 이 판정의 정답이 된다.

## 이 정답지의 경계

**양식 하나다.** 표 넷 · 칸 65 이고, 재현율을 이 숫자로 일반화할 수 없다. 재는 것은
「같은 양식에서 사람과 LLM 이 같은 칸을 고르나」이고, 특히 **열 머리를 값으로 잘못
고르는지**다 — 그것이 표를 깨뜨리는 유일한 방향이다.

**빈 칸은 안 센다.** `Cell.blank` 가 이미 값 자리로 보므로 판정이 넓힌 폭이 아니다.

    uv run --group forms python spike/form_slots_score.py
"""

from __future__ import annotations

import sys

from finnect.attach import store
from finnect.forms import label_targets, open_form
from finnect.forms.base import Anchor

SHA = "e679598ef461124b9024e6245e3d18756f2e6df8c3a0724f9b90e51425676481"
TITLE = "2026년 서울창업허브M+ 글로벌 오픈 이노베이션 신청서"

#: 사람이 값을 넣은 칸. `(구역, 표, 행, 열)`. **표1 밖에는 하나도 없다** — 서명란은
#: 표가 아니라 문단이라 여기 안 온다.
TRUTH: frozenset[Anchor] = frozenset(
    Anchor(0, 1, r, c)
    for r, c in [
        (0, 1),  # 기업명            주식회사 ○○○○
        (1, 1),  # 서비스명          OO기술이 적용된 …
        (2, 1),  # 대표자명          공동·각자 대표의 경우 모두 기재
        (2, 3),  # 생년월일          yyyy-mm-dd
        (3, 1),  # 연락처            010-1234-5678
        (4, 1),  # 이메일            adc@xxxx.com
        (4, 3),  # 설립일자          yyyy-mm-dd
        (5, 1),  # 사업자등록번호    000-00-00000
        (5, 3),  # 법인등록번호      (빈칸)
        (6, 1),  # 사업장주소        본점 … 기재
        (7, 1),  # 실무자성명        (빈칸)
        (7, 3),  # 실무자직위        (빈칸)
        (8, 1),  # 실무자연락처      010-1234-5678
        (8, 3),  # 실무자이메일      adc@xxxx.com
        (11, 0),  # 매출 2023 국내   000백만원
        (11, 1),  # 매출 2023 국외   (빈칸)
        (11, 2),  # 매출 2024 국내   000백만원
        (11, 3),  # 매출 2024 국외   (빈칸)
        (11, 4),  # 매출 2025 국내   000백만원
        (11, 5),  # 매출 2025 국외   (빈칸)
        (13, 0),  # 주요 투자처      5개사 내외 기재
        (13, 1),  # 누적 투자금액    000백만원
        (14, 1),  # 총 인원          총 (  ) 명
        (14, 3),  # 정규직           (      ) 명
        (15, 1),  # 비정규직         (      ) 명
        (16, 1),  # 기타실적         수상 실적, 글로벌 진출 실적 등
    ]
)

#: 잘못 고르면 표가 깨지는 칸. **이 셋을 값으로 고르면 안 된다** — 한 칸만 보면
#: 값처럼 보이고, 나란한 칸을 같이 봐야 열 머리임이 드러난다.
TRAPS: dict[Anchor, str] = {
    Anchor(0, 1, 9, 1): "2023년 — 매출액 행의 열 머리",
    Anchor(0, 1, 9, 2): "2024년 — 매출액 행의 열 머리",
    Anchor(0, 1, 9, 3): "2025년 — 매출액 행의 열 머리",
    Anchor(0, 1, 10, 1): "국외 — 국내/국외 열 머리",
    Anchor(0, 1, 12, 1): "주요 투자처 — 투자 행의 열 머리",
    Anchor(0, 1, 12, 2): "누적 투자금액 — 투자 행의 열 머리",
    Anchor(0, 1, 14, 2): "정 규 직 — 인력현황 행의 열 머리",
    Anchor(0, 1, 3, 3): "남 — 동그라미 치는 보기",
    Anchor(0, 1, 3, 4): "여 — 동그라미 치는 보기",
}


def main() -> int:
    form = open_form(str(store.abs_path(store.rel_path(SHA))), "hwp")
    cells = form.cells()
    blank = {c.anchor for c in cells if c.blank}
    text = {c.anchor: c.text for c in cells}

    from finnect.forms.slots import LlmSlots

    out = LlmSlots().read(TITLE, cells)

    # **빈 칸을 양쪽에서 뺀다.** 이미 값 자리라 넓힌 폭이 아니다
    got = out.fillable - blank
    want = TRUTH - blank
    hit, miss, over = got & want, want - got, got - want

    print(f"칸 {len(cells)} · 빈 칸 {len(blank)} · 호출 {out.calls}회")
    print(f"정답지 {len(want)}칸 (빈 칸 제외) · 판정 {len(got)}칸")
    print(f"맞음 {len(hit)} · 빠뜨림 {len(miss)} · 잘못 고름 {len(over)}")
    if want:
        print(f"재현율 {len(hit) / len(want):.1%} · 정밀도 {len(hit) / len(got):.1%}")

    for tag, group in (("빠뜨림", miss), ("잘못 고름", over)):
        for a in sorted(group, key=lambda x: (x.table, x.row, x.col)):
            print(f"  [{tag}] {a}  {text.get(a, '')[:50]!r}")

    print()
    print("=== 표를 깨뜨리는 칸 ===")
    bad = [a for a in TRAPS if a in out.fillable]
    for a, why in TRAPS.items():
        print(f"  {'✗ 골랐다' if a in out.fillable else '○ 걸렀다'}  {a}  {why}")

    print()
    tg = label_targets(cells, out.fillable)
    print(f"=== label_targets {len(tg)}쌍 (판정 없이는 {len(label_targets(cells))}쌍) ===")
    for lab, a in tg:
        print(f"  {lab[:26]!r:30s} → {a}  {text.get(a, '')[:34]!r}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
