"""사실 추출 — **여기가 포트다**(plan/12 T-0045 · ADR-0031).

LLM 제공자가 아직 없다(ADR-0021 G). 그런데 파이프라인에서 LLM 이 하는 일은 함수
하나다 — `청크[] → 사실[]`. 그 아래(라우팅·병합·충돌·근거 연결)는 전부 결정론이라
제공자 없이 만들 수 있다. 그래서 **여기 포트를 파고 구현 둘을 둔다.**

    StubExtractor   코퍼스에서 손으로 옮긴 사실을 돌려준다. 지금 쓰는 것
    (LlmExtractor)  아직 없다. 제공자가 정해지면 이 Protocol 만 만족시키면 된다

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
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from finnect.config import settings
from finnect.wiki import topics


class UnknownFile(Exception):
    """스텁이 모르는 파일. **빈 결과로 넘기지 않는다.**"""


@dataclass(frozen=True, slots=True)
class Fact:
    """추출된 사실 하나. **구상도 ③의 Fact 와 같은 것이고 `confidence` 만 없다.**

    도면은 사실마다 `confidence: 0.9` 를 붙인다. **안 쓴다** — 0.9 와 0.7 을 가를 눈금이
    없다. 배점 탐지기가 30% → 45% → 25% 로 간 것과 같은 실패다. 대신 근거 청크 유무 ·
    `source_type` · 충돌 여부 셋으로 말한다(plan/12 구상도와의 차이).
    """

    #: `topics.TOPICS` 안의 라벨. 밖이면 `uncategorized` 로 선다
    topic: str
    #: `slot` 정형 · `node` 서술. **한 문장이 둘 다이면 사실을 둘로 낸다**
    kind: str
    #: 사실 문장. 서술 노드는 이게 내용이고, 정형 슬롯은 사람이 읽는 설명이다
    text: str
    #: 원문에 그대로 있는 조각. **이걸 담은 청크가 근거가 된다**
    anchor: str

    #: 같은 사실을 문서 여럿에서 묶는 식별자. **서술 노드에서만 쓴다.**
    #:
    #: 재구매율 34→51% 가 코퍼스 네 문서에 다른 문장으로 있다. 문자열로는 못 묶어서
    #: 추출기가 같은 키를 준다 — **사실 하나에 근거 넷이어야 하고 사실 넷이 되면
    #: 틀렸다**(픽스처 README 3번). 없으면 문장 자체가 키라 안 묶인다.
    fact_key: str | None = None

    # --- 정형 슬롯일 때만 ---
    #: 문서가 쓴 이름. `상시 근로자` · `종업원 수` — 슬롯은 `topics.slot_of` 가 정한다
    key: str | None = None
    #: **정규화된 값이다.** 문서가 쓴 표현은 `text` 에 남는다.
    #:
    #: 같은 값이 문서마다 다른 표기로 온다 — `24,100천원 (2024년)` · `2,410만원` ·
    #: `24100000`. 표기를 그대로 두면 셋이 서로 다른 값이 돼 **없는 충돌이 생긴다.**
    #: 단위 환산(천원·만원·억원 → 원)과 날짜 ISO 변환이 추출기의 일이다.
    value: str | None = None
    #: 언제 기준의 값인가. **없으면 시점 없는 값이다**(사업자등록번호)
    as_of: dt.date | None = None
    #: 같은 슬롯 안의 종류. `시드` · `정책자금` · `예비창업패키지`
    qualifier: str | None = None

    @property
    def slot(self) -> str | None:
        return topics.slot_of(self.key) if self.kind == "slot" else None

    @property
    def node(self) -> str | None:
        return topics.node_of(self.topic) if self.kind == "node" else None


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
        topic=d["topic"] if d["topic"] in topics.TOPICS else topics.UNCATEGORIZED,
        kind=d["kind"],
        text=d["text"],
        anchor=d["anchor"],
        fact_key=d.get("fact_key"),
        key=d.get("key"),
        value=d.get("value"),
        as_of=dt.date.fromisoformat(as_of) if as_of else None,
        qualifier=d.get("qualifier"),
    )


def get_extractor() -> FactExtractor:
    """설정이 고른 추출기. **지금은 스텁 하나뿐이다.**

    `llm` 을 고르면 여기서 막는다 — 없는 것을 있는 척하지 않는다(ADR-0031).
    """
    choice = settings.wiki_extractor
    if choice == "stub":
        return StubExtractor()
    raise NotImplementedError(
        f"추출기 '{choice}' 는 아직 없어요. LLM 제공자가 안 정해졌어요 "
        "— ADR-0021 G · plan/11 T-0036 · plan/12 T-0045"
    )
