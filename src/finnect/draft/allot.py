"""배분 — **어느 사실을 누가 맡나** (plan/16 T-0064).

## 자리가 적어서 겹치는 것이 기본이다

양식이 가리킬 수 있는 자리가 **매칭 정보 14 + 카테고리 10 = 24** 뿐이라(`needs.PLACES`)
항목 수십 개가 그 스물넷을 나눠 쓴다. **안 겹치는 것이 우연이다.** 그런데 겹침을 무조건
막으면 재료가 말라 절반이 `[확인 필요]` 가 된다.

노드 트리는 자라도 이 숫자는 안 는다 — `item_need` 에 `company_id` 가 없어서 양식이
동적 경로를 못 가리킨다(ADR-0056). 대신 `_index` 가 **경로를 조상 전부에 걸어** 카테고리
하나로 그 아래 전부를 받게 한다.

**금지 대상은 사실 공유가 아니라 서사 재사용이다.** 같은 근거로 다른 각도를 쓰는
것은 정상이고, 두 항목이 같은 문단이 되는 것이 문제다.

## 그래서 겹침 쌍에서만 가른다

[T-0063](needs.py)이 "이 둘은 같은 이야기를 부른다" 고 적어 둔 쌍이 있다. **그
쌍 안에서 다투는 사실만** 주인을 정한다. 쌍이 아닌 항목끼리는 같은 사실을 써도 된다.

덕분에 **다투는 것이 없으면 LLM 을 아예 안 부른다.**

## 못 채운 자리는 코드가 센다

F6-6(못 채운 곳)은 판단이 아니라 **뺄셈**이다 — 필요한 자리 중 위키에 사실이 0건인
것. LLM 에 물으면 매번 답이 달라지고, 그 자리가 [ADR-0028](
../../../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md)이 적립 루프의
입구로 삼은 곳이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 사실 문장을 프롬프트에 넣을 때의 상한
_MAX_FACT = 220


@dataclass(frozen=True, slots=True)
class FactView:
    """위키에 선 사실 하나. **DB 도 ORM 도 모른다.**"""

    id: int
    place: str
    text: str
    #: `document` · `user_stated`. F6-12 가 둘을 다르게 다룬다
    source_type: str = "document"


@dataclass(frozen=True, slots=True)
class ItemView:
    """배분 대상 항목 하나."""

    index: int
    number: str | None
    title: str
    instruction: str | None
    #: 없으면 이 항목을 아예 못 쓰는 자리
    places: tuple[str, ...]
    #: 있으면 좋은 자리. **못 채움에 같이 세지 않는다** — 물어볼 목록의 뒷줄이다
    places_optional: tuple[str, ...] = ()
    #: 다른 항목을 압축하는 자리인가. **되풀이하라고 있는 자리라 안 다툰다**
    summary_of_others: bool = False

    @property
    def all_places(self) -> tuple[str, ...]:
        return self.places + self.places_optional


@dataclass(frozen=True, slots=True)
class Allotment:
    """한 항목이 받은 것."""

    index: int
    #: 이 항목이 쓸 사실
    fact_ids: tuple[int, ...]
    #: 필요한데 위키에 없는 자리. **F6-6 이 이것이다**
    missing: tuple[str, ...]
    #: 있으면 좋은데 없는 자리. 물어볼 목록의 뒷줄이다
    missing_optional: tuple[str, ...] = ()


SYSTEM = """\
너는 한 회사의 사업 위키에 있는 **사실**을, 지원사업 양식의 **항목**에 나눠 준다.

# 왜 나누나
아래 항목 쌍은 **같은 이야기를 부를 수 있다고 이미 판정된 것**이다. 그대로 두면
신청자가 같은 에피소드를 두 번 쓰게 된다. 사실 하나가 **어느 항목에서 가장 잘
쓰이는지** 골라라.

# 규칙
1. 사실 하나에 항목 **하나**만 준다. 나눠 주지 않는다
2. 아래 준 후보 항목 중에서만 고른다. 다른 항목을 적지 마라
3. **지시문을 근거로 골라라.** 항목 제목보다 지시문이 무엇을 요구하는지 정확하다
4. 어느 쪽이든 비슷하면 **더 구체적인 것을 요구하는 항목**에 준다
5. 이유를 한 문장으로 적어라. 지어내지 마라

# 안 하는 것
- 사실을 고치거나 요약하지 마라. 주인만 정한다
- 어느 항목에도 안 맞는다고 답하지 마라. 후보 중 하나는 고른다
"""


def _schema(fact_ids: list[int], item_indexes: list[int]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["assign"],
        "properties": {
            "assign": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["fact", "item", "why"],
                    "properties": {
                        "fact": {"type": "integer", "enum": fact_ids},
                        "item": {"type": "integer", "enum": item_indexes},
                        "why": {"type": "string"},
                    },
                },
            }
        },
    }


@dataclass(slots=True)
class Allotter:
    """겹침 쌍에서 다투는 사실의 주인을 정한다.

    **다투는 것이 없으면 LLM 을 안 부른다.** 부를 이유가 없다 — 나눌 것이 없으면
    각 항목이 자기 자리의 사실을 그냥 다 쓴다.
    """

    client: object | None = None
    #: 후보 밖의 답이 와서 버린 것. **조용히 안 넘긴다**
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

    def allot(
        self,
        items: list[ItemView],
        facts: list[FactView],
        pairs: list[tuple[int, int]],
    ) -> list[Allotment]:
        by_place = _index(facts)

        cand = {
            it.index: {f.id for p in it.all_places for f in by_place.get(p, [])}
            for it in items
        }
        contested = _contested(items, cand, pairs)
        owner = self._decide(items, facts, contested) if contested else {}

        out: list[Allotment] = []
        for it in items:
            mine = {
                fid
                for fid in cand[it.index]
                if fid not in contested or owner.get(fid) == it.index
            }
            required, optional = _missing(it, by_place)
            out.append(
                Allotment(
                    index=it.index,
                    fact_ids=tuple(sorted(mine)),
                    missing=required,
                    missing_optional=optional,
                )
            )
        return out

    def _decide(
        self, items: list[ItemView], facts: list[FactView], contested: dict[int, set[int]]
    ) -> dict[int, int]:
        """다투는 사실마다 주인 하나. **후보 밖의 답은 버리고, 그러면 아무도 안 쓴다.**

        버린 사실을 양쪽 다 주면 중복이 그대로 나오고, 임의로 한쪽에 주면 그
        선택을 아무도 설명하지 못한다. **안 쓰는 쪽이 낫다** — `[확인 필요]` 로
        드러난다.
        """
        by_id = {f.id: f for f in facts}
        by_index = {it.index: it for it in items}
        fact_ids = sorted(contested)
        item_indexes = sorted({i for s in contested.values() for i in s})

        out = self._c().json(
            system=SYSTEM,
            user=_user_prompt(by_index, by_id, contested),
            schema=_schema(fact_ids, item_indexes),
            schema_name="fact_allotment",
        )
        owner: dict[int, int] = {}
        for d in out.get("assign") or []:
            fid, idx = d.get("fact"), d.get("item")
            if fid not in contested:
                self.dropped.append(("fact", str(fid)[:20]))
                continue
            if idx not in contested[fid]:
                # **후보가 아닌 항목에 줬다.** 그 항목은 이 자리를 필요로 하지도 않는다
                self.dropped.append(("item", f"{fid}→{idx}"))
                continue
            owner[fid] = idx
        return owner


def _contested(
    items: list[ItemView], cand: dict[int, set[int]], pairs: list[tuple[int, int]]
) -> dict[int, set[int]]:
    """겹침 쌍 안에서 둘 다 후보로 가진 사실. **쌍이 아니면 다투지 않는다.**"""
    summary = {it.index for it in items if it.summary_of_others}
    out: dict[int, set[int]] = {}
    for a, b in pairs:
        if a in summary or b in summary:
            continue  # **요약 항목은 되풀이하라고 있는 자리다**
        for fid in cand.get(a, set()) & cand.get(b, set()):
            out.setdefault(fid, set()).update((a, b))
    return out


def _index(facts: list[FactView]) -> dict[str, list[FactView]]:
    """자리 이름 → 사실들. **노드 경로를 조상 전부에 걸어 둔다**(ADR-0056).

    `item_need.place` 는 **카테고리 열이나 매칭 정보 열다섯**만 가리킨다 — 양식이 회사와
    무관해서 동적 경로를 못 가리킨다(`item_need` 에 `company_id` 가 없다). 그런데 사실은
    `Customer/고객문제` 같은 경로를 든다. 그래서 `Customer` 로도 찾을 수 있게 조상마다
    걸어 둔다.

    같은 사실이 여러 키에 걸리지만 **id 로 모으므로 두 번 세어지지 않는다.**
    """
    out: dict[str, list[FactView]] = {}
    for f in facts:
        for anc in _ancestors(f.place):
            out.setdefault(anc, []).append(f)
    return out


def _ancestors(path: str) -> list[str]:
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _missing(
    it: ItemView, by_place: dict[str, list[FactView]]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """필요한데 위키에 사실이 0건인 자리. **판단이 아니라 뺄셈이다.**

    필수와 선택을 나눠 낸다. 화면이 둘을 같이 세면 **"못 채운 곳 9군데" 가 뜨고
    그중 둘만 진짜 막힌 것**이라 물어볼 순서가 무너진다.
    """
    return (
        tuple(p for p in it.places if not by_place.get(p)),
        tuple(p for p in it.places_optional if not by_place.get(p)),
    )


def _user_prompt(
    items: dict[int, ItemView], facts: dict[int, FactView], contested: dict[int, set[int]]
) -> str:
    lines: list[str] = ["--- 후보 항목 ---"]
    for idx in sorted({i for s in contested.values() for i in s}):
        it = items[idx]
        lines.append(f"[{idx}] {it.number or ''} {it.title}".rstrip())
        if it.instruction:
            lines.append(f"      지시문: {it.instruction[:400]}")
    lines += ["", "--- 다투는 사실 ---"]
    for fid in sorted(contested):
        f = facts[fid]
        who = " · ".join(f"[{i}]" for i in sorted(contested[fid]))
        lines.append(f"#{fid} ({f.place}) {f.text[:_MAX_FACT]}   → 후보 {who}")
    return "\n".join(lines)
