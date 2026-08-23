"""첨부 하나를 **낼 서류 단위로 쪼갠다**(plan/11 T-0035).

**파일 하나가 서류 하나가 아니다.** 한 파일에 공고문 → `[붙임1] 신청서` →
`[붙임2] 사진` → `[붙임3] 동의서` 가 이어 붙는다. 파일 단위로 판정하면 틀린다 —
실측에서 ✗ 로 분류한 16건 중 8건이 이것 때문이었다
(`docs/adr/evidence/2026-08-17-양식-항목-추출-실측.md` §5).

**구간마다 원문 오프셋을 들고 다닌다.** ADR-0014(통합 그래프와 근거 청크)
가 "위치정보는 파싱 단계에서만 심을 수 있다" 고 못 박았다. 여기서 안 심으면 나중에 못 붙인다.

표지 모양은 실측으로 잡았다. 텍스트 400건에서 753줄이 걸렸고 대부분 이렇게 생겼다.

    [서식 3]      【서식 2】      <서식 5>      (서식1)
    [붙임 1]      [별지 제1호 서식]            서식4)
    [서식1] 컨설팅 신청서          【서식 제2호】 반도체 … 사업계획서
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 서류 표지에 오는 낱말. **`fields.is_marker` 가 같은 것을 쓴다** — 저기는 표
#: 칸 하나를 보고 여기는 줄 하나를 보지만, 낱말이 갈리면 한 파서가 표지로 자른
#: 자리를 다른 파서가 채울 칸으로 뽑는다.
MARKER_WORDS = "붙임|별첨|서식|별지|양식|첨부"

#: 표지 후보. 대괄호가 있으면 번호가 없어도 받고, 없으면 번호를 요구한다.
_MARKER = re.compile(
    r"^\s*"
    r"(?P<open>[\[【<(])?\s*"
    rf"(?P<kind>{MARKER_WORDS})\s*"
    r"(?:제\s*)?"
    r"(?P<no>\d{1,2}(?:\s*[-–]\s*\d{1,2})?)?\s*"
    r"(?:호)?\s*(?:서식)?\s*"
    r"(?P<close>[\]】>)])?"
    r"\s*(?P<tail>.{0,44})$"
)

#: `붙임 1. 온라인 입점 지원사업 신청서 1부.` 는 표지가 아니라 **제출서류 목록**이다.
_SUBMIT_LINE = re.compile(r"\d+\s*부\s*\.?\s*$|각\s*1부")

#: 표지 줄은 짧다. 이보다 길면 본문이다.
_MAX_MARKER_LEN = 60

#: 서류 이름으로 끝나는가. **뒤에 붙는 괄호 주석은 떼고 본다** — `동의서 (지원기업)`.
#: 위 `_MARKER` 와 겹치지 않는다. 저기는 **표지 낱말**(붙임·서식)을 찾고 여기는
#: **서류 이름**을 찾는다 — 코퍼스에는 둘 중 하나만 가진 양식이 흔하다.
#:
#: **`제출서류` 를 안 넣는다.** 서류 한 벌의 이름이 아니라 「내야 할 서류들」을
#: 가리키는 말이라, 공고문의 절(`6. 신청방법 및 제출서류` — 실측)과 안내 문단이
#: 같이 걸린다. 대가로 `…신청시 제출서류` 같은 **안내 장 하나를 놓친다.**
_DOC_NAME = re.compile(
    r"(?:신청서|지원서|계획서|동의서|서약서|확약서|확인서|인감계|각서|위임장|보고서)"
    r"\s*(?:\([^)]{0,20}\))?\s*$"
)

#: 제목만 든 표는 작다. 이보다 크면 본문 표라 첫 칸이 제목이 아니라 **라벨**이다.
_TITLE_TABLE_CELLS = 3

#: 줄머리 기호. **이게 붙으면 목록 항목이지 제목이 아니다.**
#:
#: 표는 「작은 표」 조건이 목록을 걸러 주는데 문단에는 그런 조건이 없다 — 실측에서
#: `­ (필수) 지정 신청서(온라인 신청서식)` 처럼 제출서류 안내가 문단으로 늘어섰고
#: 넷이 서류 제목으로 잡혔다. 그 자리에서 자르면 **안내 문단 하나가 서류 한 벌**이 된다.
#:
#: **숫자는 안 넣는다.** `1. 2026년 0차 타깃마케팅 기본지원서` 가 진짜 제목이다.
#:
#: **`ㅇ`·`o` 는 뒤에 공백을 요구한다.** 한글 이응이 불릿으로 흔히 쓰이는데
#: (`ㅇ 참여기업 각서(별지 제3호 서식)` — 실측) 낱말 첫 글자일 수도 있어서다.
_BULLET_HEAD = re.compile(r"^[-–—*※○◦◇□▢▷▶·∙•●◎◯￮<­]|^[①-⑳]|^[ㅇㅁoO]\s")


@dataclass(slots=True)
class Segment:
    """낼 서류 한 벌. 원문의 [start, end) 구간이다."""

    seq: int
    title: str
    start: int
    end: int
    text: str


def _marker_title(line: str) -> str | None:
    """표지면 제목을, 아니면 None 을 준다."""
    if not line or len(line) > _MAX_MARKER_LEN or "\t" in line:
        return None
    m = _MARKER.match(line)
    if not m:
        return None

    tail = m.group("tail").strip()
    if _SUBMIT_LINE.search(line):
        # 서류 목록이다. 자를 자리가 아니다.
        return None

    bracketed = bool(m.group("open") and m.group("close"))
    if not bracketed and not m.group("no"):
        # `첨부파일` 처럼 맨몸 낱말은 표지로 안 본다. 본문에 흔하다.
        return None
    if not bracketed and len(tail) > 20:
        # 괄호가 없으면 뒤가 길수록 본문일 확률이 높다.
        return None

    head = m.group("kind") + (f" {m.group('no').replace(' ', '')}" if m.group("no") else "")
    return f"{head} {tail}".strip() if tail else head


def doc_titles(tables: list[list[str]], paras: list[str]) -> list[str]:
    """파일 구조에서 **서류 제목**을 골라 낸다 (ADR-0061 결정 1).

    ## 낱말이 없어도 모양이 있다

    한글 양식은 서류 제목을 **표 하나로 감싼다** — 테두리와 음영을 주려고 그렇게
    쓴다. 텍스트로 납작하게 만들면 그 모양이 사라져서 `1. 2026년 0차 타깃마케팅
    기본지원서` 가 평범한 한 줄이 되고, `_MARKER` 가 요구하는 낱말이 없어 못 잡는다.

    구조로 열면 그것은 **칸 셋짜리 작은 표의 한 칸**이고, 같은 모양의 표가 문서에
    반복되면 그게 서류 머리글이다.

    실측(2026-08-23 · hwp 세 파일 · 서류 16장):

        표지 규칙(`_marker_title`)   0장
        이 규칙                     15장   오탐 0

    ## 파일을 여기서 안 연다

    `forms` 어댑터가 뽑아 준 글자만 받는다. 임포트하면 **jpype 와 JVM 이 딸려
    오고** 이 모듈은 읽기 경로에 있다 — 로컬은 통과하고 배포본만 죽는 그 함정이다
    (`api/app.py` 가 `wiki.service` 를 함수 안에서 부르는 것과 같은 자리).

    `tables` 는 표마다 그 표의 칸 글자, `paras` 는 표 **밖** 문단이다. 순서는 안
    본다 — 자를 자리는 `split` 이 원문에서 다시 찾는다.
    """
    cands = [c for t in tables if len(t) <= _TITLE_TABLE_CELLS for c in t]
    cands.extend(paras)

    out: list[str] = []
    seen: set[str] = set()
    for raw in cands:
        t = re.sub(r"\s+", " ", (raw or "").strip())
        if not 2 < len(t) <= _MAX_MARKER_LEN or t in seen:
            continue
        if _BULLET_HEAD.match(t) or not _DOC_NAME.search(t):
            continue
        seen.add(t)
        out.append(t)
    return out


def _locate(text: str, titles: list[str]) -> dict[int, str]:
    """제목마다 원문에서의 줄 시작 오프셋. **한 번만 나올 때 준다.**

    구조가 준 것은 `(구역, 표, 행, 열)` 이라 글자 오프셋이 아니다. 위치정보는
    파싱 단계에서만 심을 수 있으므로([ADR-0014](
    ../../../docs/adr/0014-통합-그래프와-근거-청크.md)) 여기서 원문 대조로 찾는다 —
    위키 추출의 앵커 대조와 같은 수법이다(ADR-0061 결정 5).

    **못 찾거나 두 번 나오면 버린다.** 목차와 본문에 같은 이름이 있는 양식이 있고,
    둘 중 어느 쪽인지 고를 근거가 없다. 고르면 그 선택을 아무도 설명하지 못하고,
    틀리면 **파일은 정상으로 열려서** 제출 직전에야 드러난다([ADR-0063](
    ../../../docs/adr/0063-서술-항목의-좌표를-문단으로-준다.md) 결정 2 와 같은 판단).

    **줄의 첫 셀과 완전히 같아야 한다.** 표 셀이 텍스트에서 탭으로 이어 붙으므로
    (`제목\\t초기창업자`) 줄 전체와 견주면 제목이 든 표를 전부 놓치고, 반대로
    `startswith` 로 풀면 목차가 걸린다 — 경기도 반려동물 실측에서 `…사업계획서` 가
    `…사업계획서 작성 유의사항`·`…작성 목차`·본문 셋에 걸려 **버려졌다.**
    """
    hits: dict[str, list[int]] = {t: [] for t in titles}
    pos = 0
    for line in text.splitlines(keepends=True):
        head = re.sub(r"\s+", " ", line.strip().split("\t")[0].strip())
        for t in titles:
            if head == t:
                hits[t].append(pos)
        pos += len(line)

    return {found[0]: t for t, found in hits.items() if len(found) == 1}


def _merge_heads(cuts: list[tuple[int, str]], text: str) -> list[tuple[int, str]]:
    """**표지 줄만 있고 본문이 없는 경계는 다음 경계의 머리다.**

    서울창업허브 실측에서 `붙임 1.` 과 `2026년 … 신청서` 가 빈 줄을 사이에 두고
    떨어져 있었다. 앞은 표지 규칙이, 뒤는 구조가 잡아서 **서류 하나가 두 구간**이
    됐다 — 앞 구간은 글자가 한 줄뿐이라 판정이 `none` 으로 가고 표지 번호를 잃는다.

    **뒤 제목을 쓴다.** 표지 낱말(`붙임 1`)보다 서류 이름이 화면에서 값을 한다.
    """
    out: list[tuple[int, str]] = []
    #: 본문 없이 지나간 표지 줄의 시작. 다음 경계가 이 자리부터다
    head: int | None = None
    for i, (start, title) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        block = text[start:end]
        #: 표지 줄 자신을 뺀 나머지. 여기 글자가 있으면 제 몫의 본문이 있다
        rest = block.split("\n", 1)[1] if "\n" in block else ""
        if not rest.strip() and i + 1 < len(cuts):
            head = start if head is None else head
            continue
        out.append((start if head is None else head, title))
        head = None
    return out


def split(
    text: str, *, head_title: str = "공고문", titles: list[str] | None = None
) -> list[Segment]:
    """텍스트를 구간으로 쪼갠다. **첫 표지 앞은 그대로 한 구간이다.**

    표지가 하나도 없으면 통째로 한 구간을 준다. 빈 목록을 주지 않는다 —
    "안 잘렸다"와 "내용이 없다"는 다른 사실이다.

    `titles` 는 `doc_titles` 가 파일 구조에서 찾은 서류 제목이다. **표지 규칙과
    같이 쓴다** — 구조는 hwp·docx 만 열리고 pdf 는 표지 규칙밖에 없다(ADR-0061
    결정 2). 같은 줄에 둘 다 걸리면 표지 규칙이 이긴다. 저쪽이 제목을 정규화해
    주고(`[서식 3] …` → `서식 3 …`) 코퍼스에서 이미 검증된 이름이다.
    """
    cuts: list[tuple[int, str]] = []
    pos = 0
    wanted = _locate(text, titles or [])
    for line in text.splitlines(keepends=True):
        title = _marker_title(line.strip()) or wanted.get(pos)
        if title is not None:
            cuts.append((pos, title))
        pos += len(line)
    cuts = _merge_heads(cuts, text)

    if not cuts:
        return [Segment(0, head_title, 0, len(text), text)]

    bounds: list[tuple[int, str]] = []
    if cuts[0][0] > 0:
        bounds.append((0, head_title))
    bounds.extend(cuts)

    out: list[Segment] = []
    for i, (start, title) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(text)
        body = text[start:end]
        if not body.strip():
            continue
        out.append(Segment(len(out), title, start, end, body))
    return out
