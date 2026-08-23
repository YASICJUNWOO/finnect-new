"""값 자리인가 안내인가 — **LLM 이 가른다** (plan/24 T-0153 · ADR-0060 결정 6).

`Cell.blank` 는 글자가 없는 것만 본다. 관공서 양식은 빈칸에 형식을 적어 두고
(`주식회사 ○○○○`·`yyyy-mm-dd`·`000-00-00000`) 거기에 안내를 덧붙이므로
(`OOOOO (법인등기부등본상 상호명)`) **정규식으로 갈리지 않는다** — 실측에서 양식
하나가 그것 때문에 표 115개에서 한 칸도 안 걸렸다.

## 왜 여기가 어려운가

한 칸만 보면 `2023년` 이 값처럼 보인다. 나란한 칸을 같이 봐야 그것이 열 머리임이
드러난다.

    매출액 | 2023년 | 2024년 | 2025년      ← 열 머리. 덮어쓰면 표가 깨진다
    국내   | 국외   | 국내   | 국외        ← 열 머리
    000백만원 | (빈칸) | 000백만원 | (빈칸)  ← 값 자리

그래서 **칸 하나씩 묻지 않고 표를 통째로 보여 준다.** `needs.py` 가 항목을 하나씩
안 묻는 것과 같은 이유다.

## 틀리는 방향이 대칭이 아니다

빠뜨리면 그 칸이 안 채워지고 사용자가 손으로 옮긴다. 잘못 고르면 **열 머리가 값으로
덮여 표가 깨진다.** 그래서 프롬프트가 「확실하지 않으면 빼라」로 기울어 있고, 정확도를
읽을 때도 정밀도를 먼저 본다.

## 좌표를 모델이 안 쓴다

칸에 번호를 붙여 주고 **번호로 답하게 한다.** 좌표 넷을 쓰게 하면 없는 칸을 지어낼
수 있고, 그것이 조용히 다른 칸을 덮는다(`extract_nodes` 가 자리표에서 번호를 고르는
것과 같은 수법 · ADR-0058).
"""

from __future__ import annotations

from dataclasses import dataclass

from finnect.forms.base import Anchor, Cell

#: 한 호출에 실을 칸 수. **표 경계에서 자른다** — 표가 잘리면 나란한 칸을 못 보고
#: 열 머리 판정이 무너진다. 65칸 양식은 한 번에 들어간다.
_BATCH = 150

#: 한 칸의 글자 상한. 서명 문구와 근거 조문이 수백 자다 — 판정에 그만큼이 필요하지
#: 않고, 그것들은 애초에 값 자리가 아니다.
_MAX_TEXT = 120


SYSTEM = """\
너는 한국 정부지원사업 **양식 파일의 표**를 보고, 칸마다 **신청자가 값을 적어야 하는
자리인가**를 판정한다.

# 값 자리인 것
- **비어 있는 칸**
- **형식만 적어 둔 칸** — `주식회사 ○○○○` · `yyyy-mm-dd` · `000-00-00000` ·
  `010-1234-5678` · `adc@xxxx.com` · `(       ) 명` · `OOO백만원`
- **무엇을 적으라고 적어 둔 칸** — `본점 기재` · `5개사 내외 기재` ·
  `수상 실적, 글로벌 진출 실적 등` · `OO기술이 적용된 OO제품·서비스`

# 값 자리가 아닌 것
- **라벨** — `기업명` · `대표자명` · `사업자등록번호` 처럼 무엇을 적으라고 묻는 이름
- **표 머리** — `2023년` · `2024년` · `국내` · `국외` · `주요 투자처` · `정 규 직`
  처럼 열이나 행을 구분하는 이름. **이 칸을 값으로 고르면 표가 깨진다**
- **고르는 보기** — `남` · `여` · `해당` · `미해당` · `있음` · `없음` 처럼 동그라미를
  치거나 표시하는 자리
- 문장이 다 적혀 있는 안내문 · 근거 조문 · 서명 문구 · 서류 제목

# 어떻게 가르나

**같은 행과 열의 이웃을 같이 봐라.** `2023년 | 2024년 | 2025년` 처럼 나란한 칸들이
같은 종류의 이름이면 그것은 표 머리다. 한 칸만 보면 `2023년` 이 값처럼 보인다.

라벨이 왼쪽에 있고 그 오른쪽이 형식이나 안내면, **왼쪽은 라벨이고 오른쪽이 값 자리다.**

# 안 하는 것
- 값을 지어내지 마라. **어느 칸인지만 답한다**
- 신뢰도 점수를 매기지 마라
- **확실하지 않으면 빼라.** 빠뜨리면 사람이 손으로 채우지만, 잘못 고르면 표 머리가
  지워지고 파일은 정상으로 열려서 제출 직전에야 드러난다
"""


@dataclass(frozen=True, slots=True)
class SlotReading:
    """읽은 결과. **호출 수를 같이 낸다** — 양식마다 비용이 다르다."""

    fillable: frozenset[Anchor]
    calls: int = 0
    #: 번호가 범위 밖이라 버린 것. **조용히 안 넘긴다**
    dropped: tuple[str, ...] = ()


@dataclass(slots=True)
class LlmSlots:
    """양식 하나의 칸들을 LLM 에 넘겨 값 자리를 가른다 (ADR-0037).

    **회사와 무관하다.** `document` 가 콘텐츠 주소라 한 번 읽으면 그 양식을 쓰는
    모든 회사가 쓴다 — `item_need` 에 `company_id` 가 없는 것과 같은 자리다.
    """

    client: object | None = None

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다**(CLAUDE.md 함정 · `needs.py` 와 같다)."""
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def read(self, title: str, cells: list[Cell]) -> SlotReading:
        """값 자리의 좌표를 돌려준다. **빈 칸은 안 묻는다** — 이미 값 자리다."""
        asking = [c for c in cells if not c.blank]
        if not asking:
            return SlotReading(frozenset(c.anchor for c in cells))

        fillable: set[Anchor] = {c.anchor for c in cells if c.blank}
        dropped: list[str] = []
        calls = 0
        for batch in _batches(asking):
            calls += 1
            out = self._c().json(
                system=SYSTEM,
                user=_user_prompt(title, batch, cells),
                schema=_schema(len(batch)),
                schema_name="form_slots",
            )
            seen: set[int] = set()
            for i in out.get("slots") or []:
                if not isinstance(i, int) or not (0 <= i < len(batch)) or i in seen:
                    dropped.append(repr(i)[:20])
                    continue
                seen.add(i)
                fillable.add(batch[i].anchor)
        return SlotReading(frozenset(fillable), calls=calls, dropped=tuple(dropped))


def _batches(cells: list[Cell]) -> list[list[Cell]]:
    """표 경계에서 자른다. **표 하나가 상한보다 크면 그 표는 안 자른다** — 자르면
    나란한 칸을 못 보고, 그것이 이 판정의 전부다."""
    out: list[list[Cell]] = []
    cur: list[Cell] = []
    key: tuple[int, int] | None = None
    for c in cells:
        k = (c.anchor.section, c.anchor.table)
        if key is not None and k != key and len(cur) >= _BATCH:
            out.append(cur)
            cur = []
        key = k
        cur.append(c)
    if cur:
        out.append(cur)
    return out


def _schema(n: int) -> dict:
    """칸 수를 알고 만든다. **번호 범위를 스키마가 막는다**(`needs._schema` 와 같다)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["slots"],
        "properties": {
            "slots": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0, "maximum": max(n - 1, 0)},
            }
        },
    }


def _user_prompt(title: str, batch: list[Cell], every: list[Cell]) -> str:
    """표마다 행을 묶어서 낸다. **행이 한 줄이라 나란한 칸이 눈에 보인다.**

    번호는 `batch` 의 칸에만 붙고, **빈 칸은 `(빈칸)` 으로 같이 그린다** — 묻지는
    않지만 옆 칸이 비어 있다는 사실이 라벨과 값을 가르는 재료다. 지우면
    `사업자등록번호 | 000-00-00000 | 법인등록번호` 만 남아 셋이 같은 종류로 보인다.
    """
    at = {c.anchor: i for i, c in enumerate(batch)}
    tables = {(c.anchor.section, c.anchor.table) for c in batch}
    rows: dict[tuple[int, int, int], list[Cell]] = {}
    for c in every:
        k = (c.anchor.section, c.anchor.table)
        if k not in tables:
            continue
        rows.setdefault((*k, c.anchor.row), []).append(c)

    lines = [f"양식 이름: {title}", ""]
    table: tuple[int, int] | None = None
    for (sec, tab, _row), row in sorted(rows.items()):
        if (sec, tab) != table:
            table = (sec, tab)
            lines.append(f"--- 표 {sec}:{tab} ---")
        parts = []
        for c in sorted(row, key=lambda x: x.anchor.col):
            i = at.get(c.anchor)
            text = c.text[:_MAX_TEXT].replace("\n", " ")
            parts.append(f"[{i}] {text}" if i is not None else "(빈칸)")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
