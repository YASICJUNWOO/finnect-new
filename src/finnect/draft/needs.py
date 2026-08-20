"""양식 읽기 — **항목이 무엇을 요구하나** (plan/16 T-0063).

## 항목 단위 함수가 아니다

항목 제목만 보고 정할 수 없다. 포항시 양식이 그 증거다.

    2-1  사업수행 배경 및 목적   … 배경 및 **필요성**, 과제추진 목적 …
    2-2  지원필요성            … 애로사항 중심으로 **필요성**, 시의성 …

**두 지시문에 "필요성" 이 둘 다 있다.** 항목들 사이 관계를 봐야 해서 문서 하나를
통째로 한 번 읽는다. 그래서 같이 낸다 — **겹침 쌍**과 **요약 항목**.

## 회사와 무관하다

`document` 가 콘텐츠 주소(sha256)라 한 번 읽으면 **그 양식을 쓰는 모든 공고·모든
회사가 쓴다.** 회사 사실을 여기서 보지 않는 이유가 그것이다 — 보면 캐시가 깨진다.
무엇을 누가 맡을지는 회사 사실을 보고 [T-0064](allot.py)가 정한다.

## 자리 이름을 자유 생성하지 않는다

`place` 는 `wiki/topics.py` 의 슬롯 14 · 노드 10 안에서만 고른다. 밖의 이름이 오면
**버리고 센다** — 위키에 없는 자리를 요구하면 그 항목은 영원히 "못 채움" 이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finnect.wiki import topics

#: 고를 수 있는 자리. **슬롯 14 + 노드 10 = 24.** 회사가 커져도 안 늘어난다
PLACES: dict[str, str] = {
    **{k: v.label for k, v in topics.SLOTS.items()},
    **topics.NODES,
}
#: 슬롯인가 노드인가. 화면이 "값이 비었다" 와 "글이 비었다" 를 다르게 말한다
PLACE_KIND: dict[str, str] = {
    **{k: "slot" for k in topics.SLOTS},
    **{k: "node" for k in topics.NODES},
}

#: 지시문을 프롬프트에 넣을 때의 상한. 최장이 2,031자다(plan/11 실측)
_MAX_INSTRUCTION = 600


@dataclass(frozen=True, slots=True)
class ItemView:
    """항목 하나. **DB 도 ORM 도 모른다.**"""

    number: str | None
    title: str
    level: int
    instruction: str | None
    limit_text: str | None


@dataclass(frozen=True, slots=True)
class Need:
    place: str
    required: bool


@dataclass(frozen=True, slots=True)
class ItemReading:
    """항목 하나를 읽은 결과."""

    index: int
    needs: tuple[Need, ...]
    summary_of_others: bool


@dataclass(frozen=True, slots=True)
class Overlap:
    """같은 이야기를 부를 항목 쌍. **작은 쪽이 `a` 다.**"""

    a: int
    b: int
    note: str


@dataclass(frozen=True, slots=True)
class Reading:
    items: tuple[ItemReading, ...]
    overlaps: tuple[Overlap, ...]


SYSTEM = """\
너는 한국 정부지원사업 **양식 하나**를 통째로 읽고, 항목마다 신청자의 사업 위키에서
무엇을 꺼내 와야 그 항목을 쓸 수 있는지 정한다.

# 위키에 있는 자리는 이것뿐이다
아래 목록 **밖의 이름을 지어내지 마라.** 목록에 없으면 그냥 비워라.

{places}

# 항목마다 정할 것

1. **needs** — 이 항목을 쓰는 데 필요한 자리. 보통 1~4개다.
   - `required: true` — 없으면 이 항목을 아예 못 쓴다
   - `required: false` — 있으면 좋지만 없어도 쓴다
   - **필요 없으면 빈 목록이다.** 표지·목차·서명란처럼 신청자가 사업 내용을 쓰지 않는
     자리가 실제로 있다. 억지로 채우지 마라
2. **summary_of_others** — 다른 항목을 압축하는 자리인가.
   `요약` · `사업 개요` · `한 줄 소개` 가 그렇다. 이 자리는 **일부러 되풀이한다.**

# overlaps — 같은 이야기를 부를 항목 쌍

두 항목의 지시문이 **같은 이야기를 요구하면** 쌍으로 적는다. 예를 들어 한쪽이
"배경 및 필요성" 을 묻고 다른 쪽이 "애로사항 중심으로 필요성" 을 물으면 쌍이다.

**같은 자리를 쓴다는 것만으로 쌍이 아니다.** 위키가 작아서 자리는 원래 겹친다.
쌍은 **신청자가 같은 에피소드를 두 번 쓰게 될 때**다.

`summary_of_others` 인 항목은 쌍에 넣지 마라 — 그건 되풀이하라고 있는 자리다.
`note` 에 무엇이 겹치는지 한 문장으로 적어라.

# 안 하는 것
- 항목을 새로 만들거나 합치지 마라. 준 순서와 개수 그대로 index 로 답한다
- 신뢰도 점수를 매기지 마라
- 양식에 없는 것을 추측하지 마라
"""


def _schema(n: int) -> dict:
    """항목 수를 알고 만든다. **index 범위를 스키마가 막는다.**"""
    idx = {"type": "integer", "minimum": 0, "maximum": max(n - 1, 0)}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items", "overlaps"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", "needs", "summary_of_others"],
                    "properties": {
                        "index": idx,
                        "summary_of_others": {"type": "boolean"},
                        "needs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["place", "required"],
                                "properties": {
                                    "place": {"type": "string", "enum": sorted(PLACES)},
                                    "required": {"type": "boolean"},
                                },
                            },
                        },
                    },
                },
            },
            "overlaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["a", "b", "note"],
                    "properties": {"a": idx, "b": idx, "note": {"type": "string"}},
                },
            },
        },
    }


@dataclass(slots=True)
class LlmReader:
    """양식 하나를 LLM 에 넘겨 읽는다 (ADR-0037).

    **문서당 호출 하나다.** 항목마다 부르면 항목들 사이 관계를 못 본다 — 그게 이
    작업의 전부다.
    """

    client: object | None = None
    #: 자리 이름이 목록 밖이거나 index 가 범위 밖이라 버린 것. **조용히 안 넘긴다**
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

    def read(self, title: str, items: list[ItemView]) -> Reading:
        if not items:
            return Reading((), ())
        out = self._c().json(
            system=SYSTEM.format(places=_place_list()),
            user=_user_prompt(title, items),
            schema=_schema(len(items)),
            schema_name="form_needs",
        )
        return Reading(
            items=tuple(self._items(out, len(items))),
            overlaps=tuple(self._overlaps(out, len(items))),
        )

    def _items(self, out: dict, n: int):  # noqa: ANN202
        seen: set[int] = set()
        for d in out.get("items") or []:
            i = d.get("index")
            if not isinstance(i, int) or not (0 <= i < n) or i in seen:
                self.dropped.append(("index", repr(i)[:30]))
                continue
            seen.add(i)
            needs: list[Need] = []
            for nd in d.get("needs") or []:
                place = (nd.get("place") or "").strip()
                if place not in PLACES:
                    # **위키에 없는 자리를 요구하면 그 항목은 영원히 "못 채움" 이다**
                    self.dropped.append(("place", place[:30]))
                    continue
                needs.append(Need(place=place, required=bool(nd.get("required"))))
            yield ItemReading(
                index=i,
                needs=tuple(_dedupe(needs)),
                summary_of_others=bool(d.get("summary_of_others")),
            )

    def _overlaps(self, out: dict, n: int):  # noqa: ANN202
        seen: set[tuple[int, int]] = set()
        for d in out.get("overlaps") or []:
            a, b = d.get("a"), d.get("b")
            if not (isinstance(a, int) and isinstance(b, int)):
                self.dropped.append(("overlap", f"{a!r},{b!r}"[:30]))
                continue
            if a == b or not (0 <= a < n and 0 <= b < n):
                self.dropped.append(("overlap", f"{a},{b}"))
                continue
            pair = (min(a, b), max(a, b))
            if pair in seen:
                continue
            seen.add(pair)
            yield Overlap(a=pair[0], b=pair[1], note=(d.get("note") or "").strip())


def _dedupe(needs: list[Need]) -> list[Need]:
    """같은 자리가 두 번 오면 **`required` 가 센 쪽을 남긴다.**"""
    best: dict[str, Need] = {}
    for nd in needs:
        cur = best.get(nd.place)
        if cur is None or (nd.required and not cur.required):
            best[nd.place] = nd
    return list(best.values())


def _place_list() -> str:
    slots = " · ".join(f"`{k}` {v.label}" for k, v in topics.SLOTS.items())
    nodes = " · ".join(f"`{k}` {v}" for k, v in topics.NODES.items())
    return f"정형 값 — {slots}\n서술 글 — {nodes}"


def _user_prompt(title: str, items: list[ItemView]) -> str:
    lines = [f"양식 이름: {title}", "", "--- 항목 ---"]
    for i, it in enumerate(items):
        head = f"[{i}] {'  ' * (it.level - 1)}{it.number or ''} {it.title}".rstrip()
        lines.append(head)
        if it.instruction:
            body = it.instruction[:_MAX_INSTRUCTION].replace("\n", " / ")
            lines.append(f"      지시문: {body}")
        if it.limit_text:
            lines.append(f"      분량: {it.limit_text}")
    return "\n".join(lines)
