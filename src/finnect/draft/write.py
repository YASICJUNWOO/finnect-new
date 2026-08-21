"""집필 — **재료 조립 → LLM 1회 → 코드 검증** (plan/16 T-0066 · F6-12 · F6-13).

## 도구를 안 쥐어 준다

검색을 열면 어느 청크가 어느 문단에 들어갔는지 **사후에 복원이 안 돼** F6-13 이
깨진다. "나중에 붙이는 것은 불가능하다"([ADR-0014](
../../../docs/adr/0014-통합-그래프와-근거-청크.md))가 이 자리에도 걸린다.

## 환각을 프롬프트가 아니라 계층으로 막는다

컨텍스트를 코드가 조립하므로 **모델이 볼 수 있는 것 자체가** 제한된다. 그 위에
`verify()` 가 출력의 숫자와 고유명사를 재료에 대조한다. 재료 밖이면 그 자리를
`[확인 필요]` 로 바꾼다 — F6-12 가 요구한 그것이다.

위키 쪽 앵커 대조([ADR-0037](
../../../docs/adr/0037-llm-제공자를-openai-로-정하고-gpt-5-6-luna-부터-잰다.md) 결정 5)와
같은 수법이다. **프롬프트에도 쓰고 코드로도 막는다.**

## 사용자 답변은 근거 청크가 없어도 통과한다

[ADR-0028](../../../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md) 5번이
판 제3의 칸이다. 규칙을 엄격히만 지키면 답변을 본문에 못 써서 적립 루프가
무의미해진다. `source_type` 이 `user_stated` 면 그 사실의 문장도 재료다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

#: 재료에 없어서 지운 자리에 박는 말. **F6-12 가 정한 문구다**
UNVERIFIED = "[확인 필요]"

#: 숫자 뒤에 붙으면 사실 주장으로 보는 단위
_UNIT = "원억만천백십명년월일개%건배쪽매장호차"
#: 검사 대상 숫자. `24,100` · `3.5`
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
#: 검사 대상 고유명사. 회사 표기 · 로마자 · 따옴표 안
_PROPER = re.compile(
    r"(?:\(주\)|㈜|주식회사\s*)[가-힣A-Za-z0-9]+"
    r"|[A-Za-z][A-Za-z0-9\-]+"
    r"|[「『\"']([^」』\"']{2,30})[」』\"']"
)


@dataclass(frozen=True, slots=True)
class FactMaterial:
    """사실 하나와 그 근거. **근거 없는 사실은 여기 안 온다**(ADR-0014)."""

    id: int
    place: str
    text: str
    #: 근거 청크에서 잘라 온 조각. 집필이 실제로 읽는 원문이다
    quotes: tuple[str, ...] = ()
    chunk_ids: tuple[int, ...] = ()
    #: `document` · `user_stated`
    source_type: str = "document"


@dataclass(frozen=True, slots=True)
class Material:
    """항목 하나를 쓰는 데 필요한 전부. **코드가 조립한다.**"""

    number: str | None
    title: str
    instruction: str | None
    limit_text: str | None
    facts: tuple[FactMaterial, ...]
    #: 공고가 준 값. `(이름, 값)`. 금액·마감일이 여기서 온다
    notice: tuple[tuple[str, str], ...] = ()

    def corpus(self) -> str:
        """검증이 대조할 원문 뭉치. **프롬프트에 넣은 것과 같아야 한다.**

        갈리면 모델이 본 것을 검증이 모르고, 맞는 값이 `[확인 필요]` 로 지워진다.
        """
        parts = [self.title, self.instruction or "", self.limit_text or ""]
        for f in self.facts:
            parts.append(f.text)
            parts.extend(f.quotes)
        parts.extend(f"{k} {v}" for k, v in self.notice)
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class Paragraph:
    """문단 하나와 그 근거. **F6-13 이 이것이다.**"""

    text: str
    fact_ids: tuple[int, ...]


class Writer(Protocol):
    """항목 하나 → 문단 여럿. **이것이 전부다.**"""

    @property
    def name(self) -> str: ...

    def write(self, material: Material) -> list[Paragraph]: ...


SYSTEM = """\
너는 한국 정부지원사업 신청서의 **항목 하나**를 쓴다.

# 재료 밖으로 나가지 마라
아래 준 사실과 공고 값만 쓴다. **일반 상식·업계 통념·그럴듯한 수치를 넣지 마라.**
특히 금액·날짜·비율·회사명·제품명·기관명은 재료에 적힌 것만 쓴다.
재료에 없으면 그 이야기를 아예 하지 마라. **빈 자리를 메우려 하지 마라.**

# 문단마다 쓴 사실을 적는다
`facts` 에 그 문단이 실제로 근거로 삼은 사실 번호를 적는다. **읽기만 하고 안 쓴
사실은 적지 마라.** 어느 문단이 어디서 나왔는지가 화면에 그대로 뜬다.

근거 없이 이어 붙이는 문장(도입·전환·맺음)은 쓰지 마라. 문단마다 근거가 있어야 한다.

# 지시문을 따른다
양식이 "무엇을 쓰라" 고 적어 뒀으면 그대로 따른다. **지시문을 되풀이하지는 마라** —
요구한 내용을 쓰는 것이지 요구를 옮겨 적는 것이 아니다.

분량 제한이 있으면 지킨다. 없으면 문단 2~4개로 쓴다.

# 문체
- 사업계획서 문체. 담백한 사실 진술. **과장·수식·자기 홍보 금지**
- "혁신적인", "최고의", "선도하는" 같은 말을 쓰지 마라
- 재료가 얇으면 **짧게 쓴다.** 늘려 쓰지 마라
"""


def _schema(fact_ids: list[int]) -> dict:
    facts = (
        {"type": "array", "items": {"type": "integer", "enum": fact_ids}}
        if fact_ids
        else {"type": "array", "items": {"type": "integer"}, "maxItems": 0}
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["paragraphs"],
        "properties": {
            "paragraphs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text", "facts"],
                    "properties": {"text": {"type": "string"}, "facts": facts},
                },
            }
        },
    }


@dataclass(slots=True)
class LlmWriter:
    """항목 하나를 LLM 에 넘겨 문단을 받는다 (ADR-0037).

    **재료가 없으면 안 부른다.** 사실이 0건인데 부르면 모델이 지어내고, 그것을
    `verify()` 가 지워서 `[확인 필요]` 만 남은 문단이 된다. 그럴 바에는
    **아무것도 안 쓴 것이 낫다** — 그게 `blank` 이고 F6-6 이 가리키는 자리다.
    """

    client: object | None = None
    #: 재료 밖이라 `[확인 필요]` 로 바꾼 토큰. **조용히 안 넘긴다**
    unverified: list[tuple[str, str]] = field(default_factory=list)
    #: 통째로 버린 문단. 위와 **따로 센다** — 섞으면 "확인 필요 3건" 이 실제로는
    #: 문단 하나를 버린 것일 수 있다
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

    def write(self, material: Material) -> list[Paragraph]:
        if not material.facts:
            return []

        ids = [f.id for f in material.facts]
        out = self._c().json(
            system=SYSTEM,
            user=_user_prompt(material),
            schema=_schema(ids),
            schema_name="draft_item",
        )
        corpus = material.corpus()
        paragraphs: list[Paragraph] = []
        for d in out.get("paragraphs") or []:
            text, killed = verify((d.get("text") or "").strip(), corpus)
            if not text:
                continue
            self.unverified.extend((material.title[:40], k) for k in killed)
            used = tuple(sorted({i for i in (d.get("facts") or []) if i in set(ids)}))
            if not used:
                # **근거를 안 적은 문단은 버린다.** 남기면 근거 없는 문단이 생기고,
                # `wiki_evidence` 없는 `wiki_fact` 를 안 만드는 규율과 어긋난다
                self.dropped.append((material.title[:40], "근거 없는 문단"))
                continue
            paragraphs.append(Paragraph(text=text, fact_ids=used))
        return paragraphs


def verify(text: str, corpus: str) -> tuple[str, list[str]]:
    """재료 밖의 숫자와 고유명사를 `[확인 필요]` 로 바꾼다 (F6-12).

    **문장을 통째로 지우지 않는다.** 지우면 무엇이 문제였는지 화면에서 사라지고,
    사용자는 왜 그 자리가 비었는지 되짚을 수 없다.

    반환은 `(고친 본문, 지운 것 목록)`.
    """
    killed: list[str] = []
    norm = _squash(corpus)

    def kill(m: re.Match[str]) -> str:
        token = m.group(0)
        if _in_corpus(token, norm):
            return token
        killed.append(token)
        return UNVERIFIED

    out = _PROPER.sub(kill, text)
    out = _NUMBER.sub(lambda m: kill(m) if _is_claim(m, out) else m.group(0), out)
    return out.strip(), killed


def _is_claim(m: re.Match[str], text: str) -> bool:
    """사실 주장으로 볼 숫자인가. **한 자리 번호 매김까지 잡으면 목록이 깨진다.**"""
    digits = m.group(0).replace(",", "").replace(".", "")
    after = text[m.end() : m.end() + 1]
    return len(digits) >= 2 or after in _UNIT


def _in_corpus(token: str, norm: str) -> bool:
    """재료에 있나. **조사를 떼고 한 번 더 본다.**

    `(주)다시로는` 은 정규식이 조사까지 삼킨다. 재료에 `(주)다시로가` 로 적혀
    있으면 글자가 달라서 **맞는 회사 이름이 지워진다.** 뒤에서 두 글자까지 떼어
    보고, 그래도 없으면 그때 지운다.
    """
    t = _squash(token)
    if t in norm:
        return True
    return any(
        len(t) > cut + 1 and _HANGUL.match(t[-cut:]) and t[:-cut] in norm for cut in (1, 2)
    )


#: 조사로 볼 수 있는 것. 한글이면 뗀다 — 목록을 만들면 빠진 조사에서 다시 틀린다
_HANGUL = re.compile(r"^[가-힣]+$")


def _squash(s: str) -> str:
    """공백·쉼표를 지우고 비교한다. `24,100 천원` 과 `24,100천원` 이 같아야 한다."""
    return re.sub(r"[\s,]", "", s)


def _user_prompt(material: Material) -> str:
    lines = [f"항목: {material.number or ''} {material.title}".strip()]
    if material.instruction:
        lines.append(f"양식이 요구한 것: {material.instruction}")
    if material.limit_text:
        lines.append(f"분량: {material.limit_text}")
    if material.notice:
        lines += ["", "--- 공고가 준 값 ---"]
        lines += [f"{k}: {v}" for k, v in material.notice]
    lines += ["", "--- 쓸 수 있는 사실 ---"]
    for f in material.facts:
        tag = " (사용자가 직접 말한 것)" if f.source_type == "user_stated" else ""
        lines.append(f"#{f.id} [{f.place}]{tag} {f.text}")
        for q in f.quotes:
            lines.append(f"      원문: {q}")
    return "\n".join(lines)
