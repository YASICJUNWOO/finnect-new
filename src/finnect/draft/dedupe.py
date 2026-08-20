"""중복 점검 — **같은 청크는 코드가 잡는다** (plan/16 T-0067).

## 검사기를 따로 안 만든다

[T-0065](../models.py)가 문단마다 `chunk_id` 를 저장한다(F6-13). **두 항목이 같은
청크를 근거로 들면 그 자체가 신호다.** 문단을 다시 읽을 필요가 없다 — 근거를
저장하기로 한 결정이 낸 배당금이다.

## 못 잡는 것

**다른 청크에서 같은 얘기를 하면 코드가 모른다.** 사업자등록증과 회사소개서에 같은
내용이 적혀 있으면 근거는 다르고 문단은 같다. 거기는 초안 전체를 한 번 읽는 LLM
검사가 필요하고 **문서당 1회라 싸다.**

## 요약 항목은 건드리지 않는다

[T-0063](needs.py)이 표시한 자리다. `요약` · `사업 개요` 는 **일부러 되풀이한다** —
안 거르면 검사가 정상 항목을 때린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParaView:
    """문단 하나. **DB 도 ORM 도 모른다.**"""

    item_index: int
    paragraph: int
    text: str
    chunk_ids: tuple[int, ...]
    fact_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Clash:
    """겹친 문단 쌍. **작은 쪽이 `a` 다.**"""

    a: tuple[int, int]
    b: tuple[int, int]
    #: 어떻게 알았나. `chunk` (코드) · `llm` (같은 얘기 다른 근거)
    found_by: str
    note: str = ""


def by_chunk(
    paras: list[ParaView], *, summary: frozenset[int] = frozenset()
) -> list[Clash]:
    """같은 청크를 근거로 든 문단 쌍. **LLM 을 안 부른다.**

    같은 항목 안의 문단끼리는 보지 않는다 — 한 항목이 한 근거를 여러 문단에서
    푸는 것은 중복이 아니라 전개다.
    """
    out: list[Clash] = []
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for i, p in enumerate(paras):
        if p.item_index in summary:
            continue
        for q in paras[i + 1 :]:
            if q.item_index == p.item_index or q.item_index in summary:
                continue
            shared = set(p.chunk_ids) & set(q.chunk_ids)
            if not shared:
                continue
            key = _key(p, q)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Clash(
                    a=key[0],
                    b=key[1],
                    found_by="chunk",
                    note=f"같은 청크 {sorted(shared)} 를 근거로 든다",
                )
            )
    return out


def _key(p: ParaView, q: ParaView) -> tuple[tuple[int, int], tuple[int, int]]:
    a, b = (p.item_index, p.paragraph), (q.item_index, q.paragraph)
    return (a, b) if a <= b else (b, a)


SYSTEM = """\
너는 한 신청서의 **초안 전체**를 읽고, 서로 다른 항목이 **같은 이야기를 되풀이한
자리**를 찾는다.

# 무엇이 중복인가
같은 에피소드·같은 사례·같은 주장을 **두 항목이 각각 풀어 쓴 것**이 중복이다.

# 무엇이 중복이 아닌가
- 같은 사실을 **다른 각도로** 쓴 것. "6개월 버텼다" 가 한쪽에서는 끈기의 근거이고
  다른 쪽에서는 실행력의 근거일 수 있다
- 회사 이름·업종·소재지처럼 여러 항목에 당연히 나오는 값
- 한 항목 안에서 여러 문단이 같은 이야기를 이어 가는 것

# 답
겹친 문단 쌍만 적는다. **없으면 빈 목록이다.** 억지로 찾지 마라.
`note` 에 무엇이 겹치는지 한 문장으로 적어라.
"""


def _schema(keys: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["clashes"],
        "properties": {
            "clashes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["a", "b", "note"],
                    "properties": {
                        "a": {"type": "string", "enum": keys},
                        "b": {"type": "string", "enum": keys},
                        "note": {"type": "string"},
                    },
                },
            }
        },
    }


@dataclass(slots=True)
class LlmChecker:
    """같은 얘기를 다른 근거로 한 자리를 찾는다. **문서당 1회다.**"""

    client: object | None = None
    dropped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다**(CLAUDE.md 함정)."""
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def check(
        self,
        paras: list[ParaView],
        *,
        summary: frozenset[int] = frozenset(),
        known: list[Clash] | None = None,
    ) -> list[Clash]:
        """`known` 은 코드가 이미 잡은 것이다. **다시 안 묻는다.**"""
        live = [p for p in paras if p.item_index not in summary]
        if len(live) < 2:
            return []

        index = {_label(p): p for p in live}
        already = {(_label_of(c.a), _label_of(c.b)) for c in known or []}
        out = self._c().json(
            system=SYSTEM,
            user=_user_prompt(live),
            schema=_schema(sorted(index)),
            schema_name="draft_clashes",
        )

        found: list[Clash] = []
        seen: set[tuple[str, str]] = set()
        for d in out.get("clashes") or []:
            a, b = (d.get("a") or ""), (d.get("b") or "")
            if a not in index or b not in index or a == b:
                self.dropped.append(("clash", f"{a},{b}"[:30]))
                continue
            pair = (a, b) if a <= b else (b, a)
            if pair in seen or pair in already:
                continue
            if index[pair[0]].item_index == index[pair[1]].item_index:
                continue  # 같은 항목 안은 전개다
            seen.add(pair)
            found.append(
                Clash(
                    a=_parse(pair[0]),
                    b=_parse(pair[1]),
                    found_by="llm",
                    note=(d.get("note") or "").strip(),
                )
            )
        return found


def _label(p: ParaView) -> str:
    return f"{p.item_index}-{p.paragraph}"


def _label_of(k: tuple[int, int]) -> str:
    return f"{k[0]}-{k[1]}"


def _parse(label: str) -> tuple[int, int]:
    a, b = label.split("-")
    return int(a), int(b)


def _user_prompt(paras: list[ParaView]) -> str:
    lines = ["--- 초안 문단 ---"]
    for p in paras:
        lines.append(f"[{_label(p)}] {p.text}")
    return "\n".join(lines)
