"""추출 정확도 채점 — 픽스처가 정답지다 (ADR-0037 결정 3).

`tests/fixtures/wiki/facts.json` 이 **코퍼스 7건에서 사람이 손으로 옮긴 사실 118개**다.
[ADR-0031](../../../docs/adr/0031-사실-추출을-포트-뒤로-미루고-스텁으로-배관을-먼저-세운다.md)
이 "진짜 추출기가 오면 이 파일이 정답지가 된다" 고 적어 둔 그대로다.

    uv run python -m finnect.wiki --score

**모델을 고르는 것이 아니라 재는 일이다.** `gpt-5.6-luna` 로 돌려 부족하면
`gpt-5.6-terra` · `sol` 로 올린다 — 어느 쪽이든 숫자를 근거로 남긴다.

## 트랙 둘을 따로 잰다

호출이 둘이라 점수도 둘이다(ADR-0056 결정 1). **섞으면 못 읽는다** — 트랙 B 가
열넷 중 열둘을 채웠는데 A 가 얇아서 전체가 50% 로 보이면, 무엇을 고쳐야 할지가
사라진다. 그리고 잘한 기준 자체가 다르다.

| | 짝 기준 | 왜 |
|---|---|---|
| B — 매칭 정보 | `(key, 정규화된 값, 시점, 한정어)` | 값이 다르면 다른 사실이다.
  `24,100천원` 과 `24100000` 이 같아야 한다 |
| A — 노드 | `(카테고리, 앵커가 겹치는가)` | 문장은 표현이 달라도 같은 사실일 수 있다.
  **원문의 같은 자리**를 가리키면 같은 것으로 본다 |

**A 를 경로로 못 짝짓는다.** 경로가 동적이라 정답지의 `Product/기능` 과 출력의
`Product/핵심 기능` 이 같은 자리일 수 있고, 그걸 틀렸다고 세면 **동적 트리를 만든
결정 자체를 벌하는 채점**이 된다. 그래서 고정인 층 하나(카테고리)까지만 본다.

**정확도 하나로 말하지 않는다.** 재현율(정답 중 몇 개를 찾았나)과 정밀도(낸 것 중
몇 개가 맞나)를 따로 낸다. 놓친 것과 지어낸 것은 다른 문제다.

## 못 재는 것

**병합 결과는 여기서 안 잰다.** 그건 `build.py` 를 통과해야 나오고, `--rebuild` 로
실제로 세워 본 뒤 `--wiki` 로 봐야 한다. 여기는 추출기 한 겹만 잰다.

**갈라짐도 여기서 안 잰다.** 정답지는 파일 일곱이 서로를 모르는 채로 채점돼서
`Known` 이 늘 비어 있다 — 번호 장치(T-0127)가 실제로 도는지는 `BuildReport.nodes_new`
가 본다(T-0128).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from finnect.config import settings
from finnect.wiki import extract_nodes, extract_profile, tree
from finnect.wiki.extract_nodes import NodeExtractor, NodeFact
from finnect.wiki.extract_profile import ProfileExtractor, ProfileFact
from finnect.wiki.port import FileView, Known

#: `service.py` 와 같은 표여야 한다 — 쪽이 있는 포맷만 번호를 붙인다.
NUMBERED = {"pdf": True, "hwp": True, "hwpx": True, "docx": True, "pptx": True, "xlsx": False}


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _value_key(f: ProfileFact) -> tuple:
    return (f.key, _squash(f.value), f.as_of, (f.qualifier or "").strip())


@dataclass(slots=True)
class TrackScore:
    """트랙 하나의 점수. **파일마다 한 줄이다.**"""

    label: str
    gold: int = 0
    got: int = 0
    hit: int = 0
    #: 앵커가 원문에 없어 버린 것
    dropped: int = 0
    missed: list[str] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)
    #: (파일명, 정답, 낸 것, 맞은 것, 버린 것)
    rows: list[tuple[str, int, int, int, int]] = field(default_factory=list)

    def render(self) -> list[str]:
        recall = self.hit / self.gold * 100 if self.gold else 0
        prec = self.hit / self.got * 100 if self.got else 0
        lines = [
            f"[{self.label}] 정답 {self.gold} · 낸 것 {self.got} · 맞은 것 {self.hit}",
            f"  재현율 {recall:.1f}%  (정답 중 몇 개를 찾았나)",
            f"  정밀도 {prec:.1f}%  (낸 것 중 몇 개가 맞나)",
            "",
            f"  {'파일':34} {'정답':>4} {'낸것':>4} {'맞음':>4} {'버림':>4}",
        ]
        lines += [f"  {n[:34]:34} {g:4} {t:4} {h:4} {d:4}" for n, g, t, h, d in self.rows]
        if self.missed:
            lines += ["", f"  [놓친 것 {len(self.missed)}건 중 앞 15]"]
            lines += [f"    {m}" for m in self.missed[:15]]
        if self.spurious:
            lines += ["", f"  [정답에 없는 것 {len(self.spurious)}건 중 앞 15]"]
            lines += [f"    {s}" for s in self.spurious[:15]]
        return lines


@dataclass(slots=True)
class Score:
    nodes: TrackScore = field(default_factory=lambda: TrackScore("트랙 A — 노드"))
    values: TrackScore = field(default_factory=lambda: TrackScore("트랙 B — 매칭 정보"))

    def render(self) -> str:
        return "\n".join(
            [
                *self.values.render(),
                "",
                *self.nodes.render(),
                "",
                "  **정답에 없다고 전부 틀린 것이 아니다.** 픽스처는 사람이 옮긴 것이라",
                "  빠뜨린 사실이 있을 수 있다. 위 목록을 눈으로 보고 몇 건을 봤는지 함께 적는다.",
                "  **응답의 실제 모델 ID 를 같이 적는다** — `gpt-5.6-luna` 는 별칭이라",
                "  스냅샷이 갈려도 우리 쪽 문자열이 안 바뀐다(CLAUDE.md 함정).",
            ]
        )


@dataclass(frozen=True, slots=True)
class Gold:
    """파일 하나의 정답. **트랙이 갈렸으니 정답도 갈린다.**"""

    filename: str
    nodes: list[NodeFact]
    values: list[ProfileFact]


def _gold(path: Path | None = None) -> dict[str, Gold]:
    """정답지. 스텁이 읽는 것과 같은 파일이고 **같은 함수로 옮긴다.**

    `from_fixture` 를 여기서도 부르는 것이 요점이다 — 채점만 다르게 옮기면 스텁이
    100% 가 아니게 되고, 그러면 이 표가 정답지라는 말이 거짓이 된다.
    """
    raw = json.loads((path or settings.wiki_stub_facts).read_text(encoding="utf-8"))
    out: dict[str, Gold] = {}
    for e in raw["files"]:
        facts = e["facts"]
        out[e["sha256"]] = Gold(
            filename=e.get("filename") or e["sha256"][:12],
            nodes=[f for f in (extract_nodes.from_fixture(d) for d in facts) if f is not None],
            values=[f for f in (extract_profile.from_fixture(d) for d in facts) if f is not None],
        )
    return out


def _views(gold: dict[str, Gold], corpus: Path) -> dict[str, FileView]:
    """**진짜 파일을 파싱해서 청크로 준다.** 실제 파이프라인과 같은 입력이다.

    처음에는 정답 앵커만 이어 붙여 줬다. 파서 성능을 섞지 않으려는 것이었는데
    **그게 가짜 과제였다.** 앵커 더미는 문서가 아니라 조각 더미다.

    2026-08-20 실측 — 문서 작성일(`2025. 08. 22. 기준`)이 앵커 밖에 있어서
    모델이 볼 수가 없었다. 시점 있는 값 22건이 그것 하나로 어긋났고, 그건
    **모델이 못한 게 아니라 우리가 안 보여 준 것**이다.

    파서는 [plan/12](../../../docs/plan/12-사업-위키-구축.md) 가 따로 검증했다.
    여기서 섞이는 것을 감수하고 **실제 입력**을 준다.
    """
    from finnect.attach import extract as attach_extract
    from finnect.wiki import chunk

    out = {}
    for sha, g in gold.items():
        path = corpus / g.filename
        if not path.exists():
            raise FileNotFoundError(f"코퍼스에 없어요 — {path}")
        parsed = attach_extract.parse(
            path, g.filename, allowed=settings.wiki_formats, use_ocr=settings.user_file_ocr
        )
        pages = parsed.pages or [parsed.text or ""]
        pieces = chunk.split(pages, numbered=NUMBERED.get(path.suffix.lstrip(".").lower()))
        out[sha] = FileView(
            sha256=sha, filename=g.filename,
            chunks=tuple((i, pc.text) for i, pc in enumerate(pieces)),
        )
    return out


def run(
    nodes: NodeExtractor | None = None,
    values: ProfileExtractor | None = None,
    *,
    gold_path: Path | None = None,
    corpus: Path | None = None,
) -> Score:
    """정답지의 파일마다 추출기 둘을 돌려 대조한다. **진짜 파일을 파싱한다.**"""
    ex_a = nodes or extract_nodes.get_extractor()
    ex_b = values or extract_profile.get_extractor()
    gold_path = gold_path or settings.wiki_stub_facts
    gold = _gold(gold_path)
    views = _views(gold, corpus or gold_path.parent)
    score = Score()

    for sha, g in gold.items():
        #: **정답지가 파일끼리 서로를 모른다.** 갈라짐 계측은 `BuildReport.nodes_new` 다
        blank = Known()
        _tally(score.values, g.filename, g.values, ex_b, views[sha], blank, _pair_value, _say_value)
        _tally(score.nodes, g.filename, g.nodes, ex_a, views[sha], blank, _pair_node, _say_node)
    return score


def _tally(track, filename, want, ex, view, known, pair, say):  # noqa: ANN001, ANN201, PLR0913
    before = len(getattr(ex, "dropped", []))
    got = ex.extract(view, known)
    dropped = len(getattr(ex, "dropped", [])) - before

    left, hit = list(got), 0
    for w in want:
        found = pair(w, left)
        if found is None:
            track.missed.append(f"[{filename[:16]}] {say(w)}")
            continue
        left.remove(found)
        hit += 1
    track.spurious += [f"[{filename[:16]}] {say(g)}" for g in left]
    track.rows.append((filename, len(want), len(got), hit, dropped))
    track.gold += len(want)
    track.got += len(got)
    track.hit += hit
    track.dropped += dropped


def _say_value(f: ProfileFact) -> str:
    return f"{f.key} = {f.value[:30]}{f' ({f.as_of})' if f.as_of else ''}"


def _say_node(f: NodeFact) -> str:
    return f"{f.kind} {f.path} — {f.text[:44]}"


def _pair_value(want: ProfileFact, pool: list[ProfileFact]) -> ProfileFact | None:
    key = _value_key(want)
    return next((g for g in pool if _value_key(g) == key), None)


def _pair_node(want: NodeFact, pool: list[NodeFact]) -> NodeFact | None:
    """정답 하나에 짝을 찾는다. **찾으면 그 출력은 소비된다** — 하나가 둘을 못 맞춘다.

    카테고리가 같고 **원문의 같은 자리**를 가리키면 같은 것으로 본다. 경로 전체로
    보면 동적 이름 하나 차이에 전부 놓친 것이 되고, 그건 이 트랙이 재려는 것이 아니다.
    """
    cat = tree.category_of(want.path)
    a = _squash(want.anchor)
    best, score = None, 0.0
    for g in pool:
        if tree.category_of(g.path) != cat:
            continue
        r = _overlap(a, _squash(g.anchor))
        if r > score:
            best, score = g, r
    return best if score >= OVERLAP_MIN else None


#: 앵커가 이만큼 겹치면 같은 자리로 본다.
#:
#: **포함 관계로 보면 안 된다.** 2026-08-20 실측에서 같은 사실을 냈는데 앵커를 반 칸
#: 옆으로 잡아 19건이 놓친 것으로 잡혔다 — 정답 `성남·용인 지역 파일럿 매장 12개소에서
#: 실사용을 진행했다` 대 출력 `2025년 6월부터 성남·용인 지역 파일럿 매장 12개소`.
#: 둘 다 같은 문장을 가리키는데 어느 쪽도 다른 쪽을 담지 않는다.
OVERLAP_MIN = 0.5


def _overlap(a: str, b: str) -> float:
    """가장 긴 공통 부분 문자열 / 짧은 쪽 길이. 0~1."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    # a 가 짧은 쪽. 긴 것부터 줄여 가며 b 에 있나 본다
    for size in range(len(a), 0, -1):
        if size / len(a) < OVERLAP_MIN:
            break
        for i in range(len(a) - size + 1):
            if a[i : i + size] in b:
                return size / len(a)
    return 0.0
