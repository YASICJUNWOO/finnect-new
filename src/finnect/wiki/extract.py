"""사실 추출 — **여기가 포트다**(plan/12 T-0045 · ADR-0031).

LLM 제공자가 아직 없다(ADR-0021 G). 그런데 파이프라인에서 LLM 이 하는 일은 함수
하나다 — `청크[] → 사실[]`. 그 아래(라우팅·병합·충돌·근거 연결)는 전부 결정론이라
제공자 없이 만들 수 있다. 그래서 **여기 포트를 파고 구현 둘을 둔다.**

    StubExtractor   코퍼스에서 손으로 옮긴 사실을 돌려준다. 지금 쓰는 것
    LlmExtractor    OpenAI 로 진짜로 뽑는다. 키가 있어야 돈다 (ADR-0037)

## 스텁은 지어낸 값을 돌려주지 않는다

`tests/fixtures/wiki/facts.json` 이 **코퍼스 7건에서 손으로 옮긴 것**이다. 지어낸
값이 아니라 실제 파일에 적힌 문장이라, 이 스텁이 셋을 한꺼번에 한다.

1. T-0044 스키마가 **코퍼스 위에서** 정해진다 — CLAUDE.md 가 "노드 스키마는 코퍼스를
   보고 나서 쓴다"고 한 조건
2. T-0046 병합·충돌이 **진짜로** 검증된다. 픽스처가 함정을 심어 뒀다 — 직원 수 넷은
   시계열이고 시드 3억/2.8억은 충돌이다. 지어낸 값으로는 못 가른다
3. 진짜 추출기가 오면 이 파일이 **정답지**가 된다. 버리는 코드가 아니다

## 못 쓰게 막는다

**픽스처 sha256 화이트리스트다.** 목록 밖의 파일에는 빈 결과가 아니라 `UnknownFile`
을 던진다. 조용히 비면 진짜 사용자 파일에 가짜가 섞이거나, 더 나쁘게는 **아무것도
안 나온 것이 정상처럼 보인다.**

## 근거는 쪽 번호가 아니라 앵커로 찾는다

사실이 청크 번호를 들고 있으면 `--rechunk` 한 번에 전부 어긋난다(`chunk_target_chars`
를 고치면 경계가 바뀐다). 그래서 사실은 **원문 조각(`anchor`)** 을 들고, 그 문자열을
담은 청크를 찾아 연결한다. **못 찾으면 그 사실은 버린다** — 근거 없는 값을 위키에
세우지 않는다(ADR-0014).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from finnect.config import settings
from finnect.wiki import profile, tree

#: 추출기가 낼 수 있는 topic. **임시 어휘다** — plan/22 T-0126 이 카테고리+경로로 바꾼다.
#:
#: `tree.EVENT_PATH` 가 목적지를 정하므로 **그 표의 키에 둘을 더한 것**이다.
#: `company_profile` 과 `application_history` 는 매칭 정보의 재료라 노드 자리가 없고,
#: 서술로 오면 `Custom/검토 대기` 로 간다.
TOPICS: frozenset[str] = frozenset(tree.EVENT_PATH) | {"company_profile", "application_history"}


class UnknownFile(Exception):
    """스텁이 모르는 파일. **빈 결과로 넘기지 않는다.**"""


@dataclass(frozen=True, slots=True)
class Fact:
    """추출된 사실 하나. **구상도 ③의 Fact 와 같은 것이고 `confidence` 만 없다.**

    도면은 사실마다 `confidence: 0.9` 를 붙인다. **안 쓴다** — 0.9 와 0.7 을 가를 눈금이
    없다. 배점 탐지기가 30% → 45% → 25% 로 간 것과 같은 실패다. 대신 근거 청크 유무 ·
    `source_type` · 충돌 여부 셋으로 말한다(plan/12 구상도와의 차이).
    """

    #: 고정 topic 스물다섯 안의 라벨. **임시다** — plan/22 T-0126 이 카테고리+경로로 바꾼다
    topic: str
    #: `slot`=value topic · `node`=event topic. **스키마 값 그대로다** —
    #: ADR-0048 이 층 이름만 바꿨고 프롬프트·스키마는 안 바꿨다.
    #: 한 문장이 둘 다이면 사실을 둘로 낸다
    kind: str
    #: 사실 문장. event topic 은 이게 내용이고, value topic 은 사람이 읽는 설명이다
    text: str
    #: 원문에 그대로 있는 조각. **이걸 담은 청크가 근거가 된다**
    anchor: str

    #: 같은 사실을 문서 여럿에서 묶는 식별자. **event topic 에서만 쓴다.**
    #:
    #: 재구매율 34→51% 가 코퍼스 네 문서에 다른 문장으로 있다. 문자열로는 못 묶어서
    #: 추출기가 같은 키를 준다 — **사실 하나에 근거 넷이어야 하고 사실 넷이 되면
    #: 틀렸다**(픽스처 README 3번). 없으면 문장 자체가 키라 안 묶인다.
    fact_key: str | None = None

    # --- value topic 일 때만 ---
    #: 문서가 쓴 이름. `상시 근로자` · `종업원 수` — key 는 `profile.key_of` 가 정한다
    key: str | None = None
    #: **정규화된 값이다.** 문서가 쓴 표현은 `text` 에 남는다.
    #:
    #: 같은 값이 문서마다 다른 표기로 온다 — `24,100천원 (2024년)` · `2,410만원` ·
    #: `24100000`. 표기를 그대로 두면 셋이 서로 다른 값이 돼 **없는 충돌이 생긴다.**
    #: 단위 환산(천원·만원·억원 → 원)과 날짜 ISO 변환이 추출기의 일이다.
    value: str | None = None
    #: 언제 기준의 값인가. **없으면 시점 없는 값이다**(사업자등록번호)
    as_of: dt.date | None = None
    #: 같은 value topic 안의 종류. `시드` · `정책자금` · `예비창업패키지`
    qualifier: str | None = None

    @property
    def value_topic(self) -> str | None:
        return profile.key_of(self.key) if self.kind == "value" else None

    @property
    def orbit(self) -> str | None:
        return tree.EVENT_PATH.get(self.topic or "") if self.kind == "event" else None


@dataclass(frozen=True, slots=True)
class FileView:
    """추출기에 넘기는 파일 하나. **DB 를 모른다.**"""

    sha256: str
    filename: str
    #: `(ordinal, text)`. 근거를 찾을 대상이다
    chunks: tuple[tuple[int, str], ...]

    @property
    def text(self) -> str:
        return "\n".join(t for _, t in self.chunks)


class FactExtractor(Protocol):
    """**포트.** 제공자가 정해지면 이것만 만족시키면 된다."""

    #: `stub/v1` · `llm/<모델>`. 어느 추출기가 만든 값인지 행에 남는다
    name: str

    def extract(self, view: FileView) -> list[Fact]: ...


class StubExtractor:
    """코퍼스에서 손으로 옮긴 사실을 돌려준다. **픽스처 밖에는 안 돈다.**"""

    name = "stub/v1"

    def __init__(self, facts_path: Path | None = None) -> None:
        self._path = facts_path or settings.wiki_stub_facts
        self._by_sha: dict[str, list[Fact]] | None = None

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self._load())

    def extract(self, view: FileView) -> list[Fact]:
        table = self._load()
        if view.sha256 not in table:
            raise UnknownFile(
                f"{view.filename}: 스텁이 모르는 파일이에요. "
                f"실제 추출기(LLM)가 아직 없어서 픽스처 {len(table)}건만 처리할 수 있어요 "
                f"— sha256 {view.sha256[:12]}"
            )
        return table[view.sha256]

    def _load(self) -> dict[str, list[Fact]]:
        if self._by_sha is not None:
            return self._by_sha
        if not self._path.exists():
            raise UnknownFile(
                f"스텁 사실 표가 없어요 — {self._path}. "
                "이 표는 코퍼스에서 손으로 옮긴 것이라 레포 밖에서는 돌지 않아요"
            )
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._by_sha = {
            entry["sha256"]: [_fact(f) for f in entry["facts"]] for entry in raw["files"]
        }
        return self._by_sha


def _fact(d: dict) -> Fact:
    as_of = d.get("as_of")
    return Fact(
        topic=d["topic"] if d["topic"] in TOPICS else "",
        kind=d["kind"],
        text=d["text"],
        anchor=d["anchor"],
        fact_key=d.get("fact_key"),
        key=d.get("key"),
        value=d.get("value"),
        as_of=dt.date.fromisoformat(as_of) if as_of else None,
        qualifier=d.get("qualifier"),
    )


# ══════════════════════════════════════════════════════════════════
# LLM 추출기 (ADR-0037)
# ══════════════════════════════════════════════════════════════════
_SYSTEM_TEMPLATE = """\
너는 한국 창업기업 문서에서 **사실**을 뽑는 추출기다. 요약하지 말고 문서에 적힌 것만 낸다.

## 두 종류
- `value` — 정형 값. 아래 `key` 목록에 있는 것
- `event` — 서술 문장. 문제 인식·솔루션·목표 고객·시장·팀·로드맵 등

한 문장이 둘 다이면 **사실을 둘로 낸다.**

## key — 아래 한국어 이름 중 하나를 쓴다 (value 일 때만)

{value_vocab}

**영어나 snake_case 를 쓰지 마라.** 우리 자리 표가 한국어 표현으로 돼 있어서
`company_name` 같은 것을 주면 어느 자리인지 못 찾고 그 사실이 미분류로 떨어진다.

문서가 위 목록에 없는 이름을 쓰면 **문서가 쓴 그대로** 준다. 억지로 끼워 맞추지 마라.

**업력과 만 나이는 value 가 아니다.** 개업연월일과 생년월일만 낸다 —
업력은 공고마다 기준일이 달라 저장하면 틀린 값이 된다.

## anchor — 가장 중요하다
`anchor` 는 **원문에서 그대로 복사한 조각**이다. 한 글자도 바꾸지 마라.
띄어쓰기·조사·괄호·숫자 표기를 손대면 그 사실은 근거를 잃고 **버려진다.**
10~60자 정도로, 그 사실이 실제로 적힌 자리를 잡아라.

## value — 정규화한다 (value 일 때만)

**숫자만 정규화한다.**
- 금액: `24,100천원` → `24100000` · `2,410만원` → `24100000` · `3억원` → `300000000`
- 날짜: `2024. 3. 5.` → `2024-03-05` · `2024년03월11일` → `2024-03-11`
- 수: `15명` → `15`

**이름·주소·등록번호는 숫자가 아니다. 표기를 바꾸지 마라.**
- 등록번호: `501-86-33271` 그대로. **하이픈을 빼지 마라**
- 사업자등록증은 스캔본이라 **띄어쓰기가 뭉개져 온다.** 자연스러운 한국어 띄어쓰기로
  되돌린다 — `주식회사다시로` → `주식회사 다시로` ·
  `경기도성남시분당구판교로255,3층(삼평동)` → `경기도 성남시 분당구 판교로 255, 3층 (삼평동)`
  **뭉갠 채로 두면 다른 문서의 같은 값과 안 맞아 없는 충돌이 생긴다.**

**한 자리에 값을 둘 넣지 마라.** 문서가 두 칸으로 준 것은 사실 둘이다.
- 업태와 종목은 **다른 자리**다. `정보통신업 / 응용 소프트웨어 개발 및 공급업` 처럼
  붙이면 안 된다 — 업태 `정보통신업` · 종목 `응용 소프트웨어 개발 및 공급업` 둘로 낸다
- 상호에 영문 병기를 넣지 마라. `주식회사 다시로 (DASIRO Inc.)` 가 아니라 `주식회사 다시로`

## qualifier — 같은 자리 안의 종류 (value 일 때만)

조달액과 정부지원 이력은 건이 여럿이라 **무엇인지를 `qualifier` 에 적고 금액을
`value` 에 적는다.** `예비창업패키지 38,000천원` 이면
`key=지원금 · qualifier=예비창업패키지 · value=38000000` 이다.
**사업명을 value 에 넣으면 금액이 사라진다.**

문서가 쓴 표현은 `text` 에 남긴다. **단위·쉼표·한글 수사를 value 에 넣지 마라.**

## as_of — 언제 기준 값인가 (value 일 때만)

`2024년 매출` 이면 `2024-12-31` · `2025. 08. 기준` 이면 `2025-08-31`.

**문서 어딘가에 작성 기준일이 있으면 시점 있는 자리 전부에 그 날짜를 쓴다.**
`작성 기준일: 2025. 08. 22.` · `2026년 1월 현재` 같은 것이다. 소재지·업태·종목·
직원 수·자본금·매출액은 **언제 기준인지가 값의 일부다** — 비워 두면 나중에 다른
문서의 값과 어느 쪽이 최신인지 못 가린다.

값 옆에 더 구체적인 날짜가 있으면 그쪽이 이긴다.
어디에도 날짜가 없으면 비운다. **지어내지 마라.**

시점이 없는 자리도 있다 — 사업자등록번호·법인등록번호·상호·대표자·개업연월일.
이것들은 비운다.

## fact_key — 같은 사실 묶기 (event 일 때만)
같은 내용이 문서 여럿에 다른 문장으로 있으면 **같은 키**를 준다(`retention_34_to_51` 처럼).
확신이 없으면 비운다. 잘못 묶는 것보다 안 묶는 것이 낫다.

## 안 하는 것
- 문서에 없는 것을 채우지 않는다. 추측·일반 상식 금지
- 목차·머리말·쪽 번호·표 머리글만 있는 조각에서는 아무것도 안 낸다
- 신뢰도 점수를 매기지 않는다
"""

def _value_vocab() -> str:
    """`VALUE_ALIASES` 에서 만든다. **손으로 적으면 표와 어긋난다.**"""
    by: dict[str, list[str]] = {}
    for alias, slot in profile.ALIASES.items():
        by.setdefault(slot, []).append(alias)
    # **별칭만 보인다.** 라벨(`업종(종목)`)을 왼쪽에 두면 모델이 그걸 key 로 쓰는데
    # 라벨은 `VALUE_ALIASES` 에 없어서 value topic 이 `None` 으로 떨어진다. 실측으로 겪었다.
    return "\n".join(f"- {' · '.join(names)}" for names in by.values())


def system_prompt() -> str:
    return _SYSTEM_TEMPLATE.format(value_vocab=_value_vocab())


_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["facts"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "topic", "kind", "text", "anchor",
                    "fact_key", "key", "value", "as_of", "qualifier",
                ],
                "properties": {
                    "topic": {"type": "string", "enum": sorted(TOPICS)},
                    "kind": {"type": "string", "enum": ["value", "event"]},
                    "text": {"type": "string"},
                    "anchor": {"type": "string"},
                    "fact_key": {"type": ["string", "null"]},
                    "key": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "as_of": {"type": ["string", "null"]},
                    "qualifier": {"type": ["string", "null"]},
                },
            },
        }
    },
}


def _squash(s: str) -> str:
    """공백을 지운 형태로 비교한다. **`build.py` 와 같은 규칙이어야 한다** —
    거기서 근거 청크를 찾을 때 쓰는 것과 다르면 여기서 통과한 앵커가 거기서 죽는다."""
    return re.sub(r"\s+", "", s)


@dataclass(slots=True)
class LlmExtractor:
    """청크를 LLM 에 넘겨 사실을 받는다 (ADR-0037).

    **자기 출력을 원문에 대조한다.** 앵커가 원문에 없으면 그 사실을 버리고 센다 —
    `build.py` 가 한 번 더 찾지만, 여기서 걸러야 무엇이 왜 사라졌는지 남는다.
    """

    client: object | None = None
    #: 앵커가 원문에 없어 버린 사실. **조용히 사라지면 '아무것도 안 나온 것' 과
    #: 구분이 안 된다**(ADR-0037 결정 5)
    dropped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        c = self._c()
        return f"llm/{c.model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다.** 최상단에 두면 `import finnect.api.app` 이
        `wiki.service → build → extract → llm` 을 타고 httpx 를 끌고 와
        **로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정 · `tests/test_admin_api.py`).
        """
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def extract(self, view: FileView) -> list[Fact]:
        c = self._c()
        out = c.json(
            system=system_prompt(),
            user=_user_prompt(view),
            schema=_SCHEMA,
            schema_name="wiki_facts",
        )
        body = _squash(view.text)
        facts: list[Fact] = []
        for d in out.get("facts") or []:
            anchor = (d.get("anchor") or "").strip()
            if not anchor or _squash(anchor) not in body:
                self.dropped.append((view.filename, anchor[:60]))
                continue
            facts.append(_fact_from_llm(d))
        return facts


def _user_prompt(view: FileView) -> str:
    body = "\n\n".join(f"[{i}] {t}" for i, t in view.chunks)
    return f"파일 이름: {view.filename}\n\n--- 원문 ---\n{body}"


def _fact_from_llm(d: dict) -> Fact:
    """스키마가 `strict` 라 키는 다 온다. **값의 뜻을 여기서 다시 검사한다.**"""
    as_of = (d.get("as_of") or "").strip()
    try:
        parsed = dt.date.fromisoformat(as_of) if as_of else None
    except ValueError:
        parsed = None  # 날짜가 아니면 시점 없는 값으로 둔다. 지어내지 않는다
    kind = d["kind"] if d.get("kind") in ("value", "event") else "event"
    return Fact(
        topic=d["topic"] if d.get("topic") in TOPICS else "",
        kind=kind,
        text=(d.get("text") or "").strip(),
        anchor=(d.get("anchor") or "").strip(),
        # **event topic 에서만 쓴다.** value topic 에 오면 병합 키가 어긋난다
        fact_key=(d.get("fact_key") or None) if kind == "event" else None,
        key=(d.get("key") or None) if kind == "value" else None,
        value=(d.get("value") or None) if kind == "value" else None,
        as_of=parsed if kind == "value" else None,
        qualifier=(d.get("qualifier") or None) if kind == "value" else None,
    )


def get_extractor() -> FactExtractor:
    """설정이 고른 추출기.

    **`llm` 은 키가 있어야 돈다.** 없으면 `llm.MissingKey` 로 멈춘다 — 조용히 스텁으로
    물러나지 않는다(ADR-0037 결정 4). 물러나면 픽스처 7건만 처리하고 나머지를 조용히
    버리는데, 그게 ADR-0031 이 `UnknownFile` 로 막은 상황이다.
    """
    choice = settings.wiki_extractor
    if choice == "stub":
        return StubExtractor()
    if choice == "llm":
        return LlmExtractor()
    raise NotImplementedError(
        f"추출기 '{choice}' 를 몰라요. `stub` 또는 `llm` 이에요 — ADR-0037"
    )
