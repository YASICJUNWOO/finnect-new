"""트랙 B — 매칭 정보 추출(ADR-0056 결정 1·5 · plan/22 T-0126).

묻는 것은 **「소재지·직원 수·업종은 얼마인가」** 열넷이다. 질문이 고정이라 **잘한
기준이 「열넷 중 몇 칸」** 이고, 그래서 이쪽만 정확도를 잴 수 있다.

**실패하면 공고가 목록에서 사라진다.** 자격 판별(M1)이 이 값들로 돌아간다 — 문서에
있는데 안 내면 그 회사가 조건을 넘는데도 조용히 빠진다. 트랙 A 는 못 뽑으면 위키가
얇아질 뿐이라 대가가 다르고, **그래서 호출을 나눴다.** 저쪽은 넓게, 여기는 빠짐없이.

## 여기가 사전 문제를 끝낸다

옛 추출기는 문서가 쓴 이름을 그대로 받아 `VALUE_ALIASES` 43개로 찾았다. 표에 없는
이름(`인력 현황`)이 오면 미분류로 떨어졌고, **그건 자격 판별 입력이라 그 회사가 규모
조건 공고에서 조용히 빠졌다**(ADR-0056 맥락 ②).

이제 **key 가 스키마 enum 이다.** 모델이 열넷 중 하나를 고르는 수밖에 없다. `ALIASES` 는
라우팅에서 빠지고 **프롬프트의 힌트로만** 남는다 — 「문서가 이렇게 쓸 수 있다」.

## 평평하다

category 도 node 도 없다. **그래프에 안 뜬다** — 회사 정보 표 한 장이다.
그래서 `node_ref` 같은 번호 장치가 없고, 자유 문자열은 `qualifier` 하나뿐이라
**거기만 코드 그물로 접는다**(T-0127).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from finnect.config import settings
from finnect.wiki import port, profile
from finnect.wiki.port import FileView, Known, UnknownFile


@dataclass(frozen=True, slots=True)
class ProfileFact:
    """매칭 정보 한 칸의 주장 하나. **트리와 무관하다.**"""

    #: 고정 열넷 중 하나(`profile.PROFILE_KEYS`). **스키마 enum 이 막는다**
    key: str
    #: **정규화된 값이다.** 문서가 쓴 표현은 `text` 에 남는다
    value: str
    #: 원문에 그대로 있는 조각. **이걸 담은 청크가 근거가 된다**
    anchor: str
    #: 사람이 읽는 문장. 근거를 눈으로 볼 때 쓴다
    text: str = ""
    #: 언제 기준의 값인가. **`dated=False` 인 key 는 저장할 때 떨어진다**
    as_of: dt.date | None = None
    #: 같은 key 안의 종류. `시드` · `예비창업패키지`
    qualifier: str | None = None


class ProfileExtractor(Protocol):
    """**포트.** 트랙 A 와 같은 모양이고 내는 것만 다르다(ADR-0031 그대로).

    `known` 을 받지만 **읽는 것은 `qualifiers` 뿐이다.** 여기 key 는 고정이라 번호를
    줄 것이 없다.
    """

    name: str

    def extract(self, view: FileView, known: Known) -> list[ProfileFact]: ...


# ══════════════════════════════════════════════════════════════════
# 스텁 — 픽스처가 정답지다 (ADR-0031)
# ══════════════════════════════════════════════════════════════════
class StubProfile:
    """코퍼스에서 손으로 옮긴 값을 돌려준다. **픽스처 밖에는 안 돈다.**

    `facts.json` 이 문서가 쓴 이름(`상시 근로자`)으로 적혀 있어서 여기서 `profile.key_of`
    로 옮긴다. **표에 없는 이름은 안 낸다** — 그건 트랙 A 가 검토 대기로 받는다.
    """

    name = "stub/v1"

    def __init__(self, facts_path: Path | None = None) -> None:
        self._path = facts_path or settings.wiki_stub_facts
        self._by_sha: dict[str, list[ProfileFact]] | None = None

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self._load())

    def extract(self, view: FileView, known: Known | None = None) -> list[ProfileFact]:
        table = self._load()
        if view.sha256 not in table:
            raise UnknownFile(
                f"{view.filename}: 스텁이 모르는 파일이에요. "
                f"실제 추출기(LLM)가 아직 없어서 픽스처 {len(table)}건만 처리할 수 있어요 "
                f"— sha256 {view.sha256[:12]}"
            )
        return table[view.sha256]

    def _load(self) -> dict[str, list[ProfileFact]]:
        if self._by_sha is not None:
            return self._by_sha
        if not self._path.exists():
            raise UnknownFile(
                f"스텁 사실 표가 없어요 — {self._path}. "
                "이 표는 코퍼스에서 손으로 옮긴 것이라 레포 밖에서는 돌지 않아요"
            )
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._by_sha = {
            e["sha256"]: [f for f in (from_fixture(d) for d in e["facts"]) if f is not None]
            for e in raw["files"]
        }
        return self._by_sha


def from_fixture(d: dict) -> ProfileFact | None:
    """픽스처 사실 하나를 트랙 B 모양으로. **트랙 A 것이면 `None`.**"""
    if d.get("kind") != "value":
        return None
    key = profile.key_of(d.get("key"))
    if key is None:
        return None  # `업력` — 트랙 A 가 검토 대기로 받는다
    value = (d.get("value") or "").strip()
    if not value:
        return None
    return ProfileFact(
        key=key,
        value=value,
        anchor=(d.get("anchor") or "").strip(),
        text=(d.get("text") or "").strip(),
        as_of=_date(d.get("as_of")),
        qualifier=d.get("qualifier"),
    )


def _date(s: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        # 날짜가 아니면 시점 없는 값으로 둔다. **지어내지 않는다**
        return None


# ══════════════════════════════════════════════════════════════════
# LLM 추출기 (ADR-0037)
# ══════════════════════════════════════════════════════════════════
_SYSTEM = """\
너는 한국 창업기업 문서에서 **회사 정보 열넷**만 찾는 추출기다. 그 열넷 말고는 아무것도
안 낸다. 서술·소개·계획은 다른 추출기가 따로 읽으니 여기서 손대지 마라.

**빠뜨리면 그 회사가 지원사업에서 조용히 빠진다.** 자격 판별이 이 값들로 돌아가서,
문서에 적혀 있는데 안 내면 조건을 넘는 공고가 목록에서 사라진다. 요약하지 말고 문서에
적힌 것을 전부 낸다.

## key — 아래 열넷 중 하나. **다른 이름을 만들지 마라**

{keys}

오른쪽은 문서가 그 값을 부르는 말들이다. 목록에 없는 말(`인력 현황`)로 적혀 있어도
**뜻이 같으면 왼쪽 key 를 쓴다.** 열넷 어디에도 안 맞으면 그 값은 내지 않는다.

## anchor — 가장 중요하다

`anchor` 는 **원문에서 그대로 복사한 조각**이다. 한 글자도 바꾸지 마라.
띄어쓰기·조사·괄호·숫자 표기를 손대면 그 값은 근거를 잃고 **버려진다.**
10~60자 정도로, 그 값이 실제로 적힌 자리를 잡아라.

## value — 정규화한다

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

**한 자리에 값을 둘 넣지 마라.** 문서가 두 칸으로 준 것은 값 둘이다.
- 업태 `정보통신업` 과 종목 `응용 소프트웨어 개발 및 공급업` 은 **다른 key** 다
- 상호에 영문 병기를 넣지 마라. `주식회사 다시로 (DASIRO Inc.)` 가 아니라 `주식회사 다시로`

문서가 쓴 표현은 `text` 에 남긴다. **단위·쉼표·한글 수사를 value 에 넣지 마라.**

## as_of — 언제 기준 값인가

`2024년 매출` 이면 `2024-12-31` · `2025. 08. 기준` 이면 `2025-08-31`.

**문서 어딘가에 작성 기준일이 있으면 시점 있는 자리 전부에 그 날짜를 쓴다.**
`작성 기준일: 2025. 08. 22.` · `2026년 1월 현재` 같은 것이다. 소재지·업태·종목·
직원 수·자본금·매출액은 **언제 기준인지가 값의 일부다** — 비워 두면 나중에 다른
문서의 값과 어느 쪽이 최신인지 못 가린다.

값 옆에 더 구체적인 날짜가 있으면 그쪽이 이긴다.
어디에도 날짜가 없으면 비운다. **지어내지 마라.**

시점이 없는 자리도 있다 — 사업자등록번호·법인등록번호·상호·대표자·개업연월일.
이것들은 비운다.

## qualifier — 같은 자리 안의 종류

조달액과 정부지원 이력은 건이 여럿이라 **무엇인지를 `qualifier` 에 적고 금액을
`value` 에 적는다.** `예비창업패키지 38,000천원` 이면
`key=gov_program · qualifier=예비창업패키지 · value=38000000` 이다.
**사업명을 value 에 넣으면 금액이 사라진다.**

### 지금 있는 한정어

{qualifiers}

같은 것이면 **위와 똑같이 적어라.** 표기가 갈리면 같은 투자가 행 둘이 된다.

## 안 하는 것

- 문서에 없는 것을 채우지 않는다. 추측·일반 상식 금지
- **업력과 만 나이를 내지 않는다.** 개업연월일과 생년월일만 낸다 — 업력은 공고마다
  기준일이 달라 저장하면 틀린 값이 된다
- 신뢰도 점수를 매기지 않는다
"""


def _keys() -> str:
    """`PROFILE_KEYS` 와 `ALIASES` 에서 만든다. **손으로 적으면 표와 어긋난다.**"""
    by: dict[str, list[str]] = {}
    for alias, key in profile.ALIASES.items():
        by.setdefault(key, []).append(alias)
    lines = []
    for key, spec in profile.PROFILE_KEYS.items():
        hint = f" — 문서가 이렇게 쓴다: {' · '.join(by[key])}" if key in by else ""
        lines.append(f"- `{key}` {spec.label}{hint}")
    return "\n".join(lines)


def system_prompt(known: Known) -> str:
    return _SYSTEM.format(keys=_keys(), qualifiers=known.qualifiers.render())


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["values"],
    "properties": {
        "values": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "value", "text", "as_of", "qualifier", "anchor"],
                "properties": {
                    #: **여기가 사전 문제를 끝내는 자리다.** 열넷 밖으로 못 나간다
                    "key": {"type": "string", "enum": sorted(profile.PROFILE_KEYS)},
                    "value": {"type": "string"},
                    "text": {"type": ["string", "null"]},
                    "as_of": {"type": ["string", "null"]},
                    "qualifier": {"type": ["string", "null"]},
                    "anchor": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(slots=True)
class LlmProfile:
    """청크를 LLM 에 넘겨 회사 정보를 받는다 (ADR-0037).

    **자기 출력을 원문에 대조한다.** 앵커가 원문에 없으면 그 값을 버리고 센다.
    """

    client: object | None = None
    dropped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다.** 최상단에 두면 배포본이 httpx 를 끌고 온다 —
        `extract_nodes.LlmNodes._c` 와 같은 이유(CLAUDE.md 함정)."""
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def extract(self, view: FileView, known: Known | None = None) -> list[ProfileFact]:
        known = known or Known()
        out = self._c().json(
            system=system_prompt(known),
            user=_user_prompt(view),
            schema=SCHEMA,
            schema_name="wiki_profile",
        )
        #: **갈래를 뜬다.** 부르는 쪽의 `Known` 을 늘리지 않는다
        quals = known.qualifiers.copy()

        facts: list[ProfileFact] = []
        for d in out.get("values") or []:
            anchor = (d.get("anchor") or "").strip()
            if not port.anchored(view, anchor):
                self.dropped.append((view.filename, anchor[:60]))
                continue
            key = d.get("key")
            value = (d.get("value") or "").strip()
            #: **enum 을 어겼거나 값이 비면 안 낸다.** 지어내지 않는다
            if key not in profile.PROFILE_KEYS or not value:
                self.dropped.append((view.filename, f"{key!r} 값이 비었어요"))
                continue
            facts.append(
                ProfileFact(
                    key=key,
                    value=value,
                    anchor=anchor,
                    text=(d.get("text") or "").strip(),
                    as_of=_date(d.get("as_of")),
                    qualifier=quals.fold(d.get("qualifier") or "") or None,
                )
            )
        return facts


def _user_prompt(view: FileView) -> str:
    body = "\n\n".join(f"[{i}] {t}" for i, t in view.chunks)
    return f"파일 이름: {view.filename}\n\n--- 원문 ---\n{body}"


def get_extractor() -> ProfileExtractor:
    """설정이 고른 추출기. **트랙 A 와 같은 설정을 읽는다**(`WIKI_EXTRACTOR`)."""
    choice = settings.wiki_extractor
    if choice == "stub":
        return StubProfile()
    if choice == "llm":
        return LlmProfile()
    raise NotImplementedError(
        f"추출기 '{choice}' 를 몰라요. `stub` 또는 `llm` 이에요 — ADR-0037"
    )
