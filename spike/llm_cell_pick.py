"""LLM 에게 **표를 통째로 보여 주고 채울 칸을 고르게** 해 본다.

## 무엇을 재나

지금은 코드 규칙(`label_targets`)이 `라벨 | 빈칸` 짝을 만든다. 그 규칙이 오늘 두 번
틀렸다 — `사업자등록번호` 가 법인등록번호 칸을, `창업여부` 가 설립예정일 칸을 잡았다.
그리고 「행 머리」와 「라벨」을 구조적으로 못 가른다(`신청자 (대표자) | 성명 | (빈칸)`).

사람은 표를 보면 바로 안다. **LLM 도 아는지 재는 것이 이 스크립트다.**

## 어떻게 재나

셀마다 번호를 붙여 표를 그대로 싣고, 칸마다 역할을 답하게 한다. 문자열을 안 받는
이유는 ADR-0058 과 같다 — 모델이 라벨을 다시 쓰면 한 글자만 달라도 못 찾는다.

정답지는 **사람이 표를 보고 적은 것**이고 이 파일 안에 있다. 정답이 없는 파일은
답만 찍어 보고 눈으로 본다.

**버리는 코드다**(`spike/`).
"""

from __future__ import annotations

import json
import sys

from finnect.attach import store
from finnect.forms import open_form

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cells"],
    "properties": {
        "cells": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n", "role", "label_of", "why"],
                "properties": {
                    "n": {"type": "integer", "description": "칸 번호"},
                    "role": {
                        "type": "string",
                        "enum": ["행머리", "라벨", "값자리", "보기", "그밖"],
                        "description": (
                            "행머리 = 그 행 전체를 묶는 제목이고 값이 안 들어간다. "
                            "라벨 = 바로 이 옆(또는 아래)에 값이 들어갈 것을 가리키는 이름. "
                            "값자리 = 신청자가 값을 적는 칸. 비어 있거나 안내문이 들어 있다. "
                            "보기 = 체크 상자나 선택지. 그밖 = 나머지."
                        ),
                    },
                    "label_of": {
                        "type": ["integer", "null"],
                        "description": "role 이 값자리일 때 그 값의 라벨 칸 번호. 아니면 null",
                    },
                    "why": {"type": "string", "description": "한 줄. 왜 그렇게 봤나"},
                },
            },
        }
    },
}

SYSTEM = """너는 한국 관공서·지원사업 신청 양식을 읽는 사람이다.
표의 칸마다 역할을 정한다.

중요한 것 셋:
- **행 머리와 라벨은 다르다.** `신청자 (대표자) | 성명 | (빈칸)` 에서 값이 들어갈 자리는
  성명 옆이고, `신청자 (대표자)` 자체에는 아무것도 안 들어간다.
- **안내문이 든 칸도 값자리다.** `000-00-00000`·`010-1234-5678`·`주식회사 ○○○○` 처럼
  적는 형식을 미리 적어 둔 칸은 신청자가 지우고 자기 값을 넣는 자리다.
- **라벨 칸을 값자리라고 하지 마라.** 거기에 값을 넣으면 표에서 그 이름이 사라진다.

칸 번호를 하나도 빠뜨리지 말고 전부 답한다."""


def _render(cells) -> tuple[str, dict]:  # noqa: ANN001
    """표를 번호 붙여 문자열로. 번호 → 좌표 표를 같이 낸다."""
    rows: dict[tuple[int, int, int], list] = {}
    for c in cells:
        rows.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)

    lines: list[str] = []
    at: dict[int, object] = {}
    n = 0
    last_table = None
    for key in sorted(rows):
        if last_table != key[:2]:
            lines.append(f"\n[표 {key[0]}-{key[1]}]")
            last_table = key[:2]
        parts = []
        for c in sorted(rows[key], key=lambda x: x.anchor.col):
            at[n] = c.anchor
            text = c.text.replace("\n", " ")[:40] or "(빈칸)"
            parts.append(f"[{n}] {text}")
            n += 1
        lines.append("  " + "  |  ".join(parts))
    return "\n".join(lines), at


def main() -> None:
    sha = sys.argv[1] if len(sys.argv) > 1 else (
        "abde9fb7e4d4ebabc70220feef601bc4c51bdf870c64ee159945f7c9315ffd71"
    )
    ext = sys.argv[2] if len(sys.argv) > 2 else "hwp"

    from finnect import llm

    form = open_form(str(store.abs_path(store.rel_path(sha))), ext)
    table, at = _render(form.cells())
    print(table)
    print(f"\n칸 {len(at)}개를 물어본다…\n")

    got = llm.client().json(
        system=SYSTEM,
        user=table,
        schema=SCHEMA,
        schema_name="cell_roles",
    )

    picked = []
    for c in got["cells"]:
        n = c["n"]
        if n not in at:
            print(f"  ! 모르는 번호 {n}")
            continue
        if c["role"] != "값자리":
            continue
        lab = c.get("label_of")
        picked.append((at[n], at.get(lab), c["why"]))

    print(f"값자리로 고른 칸 {len(picked)}개:\n")
    by_n = {c["n"]: c for c in got["cells"]}
    for anchor, lab_anchor, why in picked:
        lab_n = next((k for k, v in at.items() if v == lab_anchor), None)
        lab_text = by_n.get(lab_n, {}).get("role", "?") if lab_n is not None else "—"
        print(f"  {anchor}   라벨={lab_anchor} ({lab_text})   {why[:44]}")

    print("\n역할 분포:")
    dist: dict[str, int] = {}
    for c in got["cells"]:
        dist[c["role"]] = dist.get(c["role"], 0) + 1
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {k:6} {v}")

    #: **라벨로 분류된 칸이 값자리로도 지목됐나.** 이것이 0 이 아니면 검증 계층이 필요하다
    labels = {c["n"] for c in got["cells"] if c["role"] == "라벨"}
    values = {c["n"] for c in got["cells"] if c["role"] == "값자리"}
    clash = labels & values
    print(f"\n라벨이면서 값자리인 칸: {len(clash)}  {sorted(clash) if clash else ''}")

    out = f"out/llm-칸판정-{sha[:8]}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(got, f, ensure_ascii=False, indent=2)
    print(f"\n원본 답: {out}")


if __name__ == "__main__":
    main()
