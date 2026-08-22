"""추출 정확도 채점 — 픽스처가 정답지다 (ADR-0037 결정 3).

`tests/fixtures/wiki/facts.json` 이 **코퍼스 7건에서 사람이 손으로 옮긴 사실 118개**다.
[ADR-0031](../../../docs/adr/0031-사실-추출을-포트-뒤로-미루고-스텁으로-배관을-먼저-세운다.md)
이 "진짜 추출기가 오면 이 파일이 정답지가 된다" 고 적어 둔 그대로다.

    uv run python -m finnect.wiki --company _ --score

**모델을 고르는 것이 아니라 재는 일이다.** `gpt-5.6-luna` 로 돌려 부족하면
`gpt-5.6-terra` · `sol` 로 올린다 — 어느 쪽이든 숫자를 근거로 남긴다.

## 무엇을 맞다고 보나

정답과 출력을 **짝지어** 센다. 짝의 기준이 종류마다 다르다.

| | 짝 기준 | 왜 |
|---|---|---|
| value topic | `(value topic, 정규화된 값, 시점)` | 값이 다르면 다른 사실이다.
  `24,100천원` 과 `24100000` 이 같아야 한다 |
| event topic | `(orbit, 앵커가 겹치는가)` | 문장은 표현이 달라도 같은 사실일 수 있다.
  **원문의 같은 자리**를 가리키면 같은 것으로 본다 |

**정확도 하나로 말하지 않는다.** 재현율(정답 중 몇 개를 찾았나)과 정밀도(낸 것 중
몇 개가 맞나)를 따로 낸다. 놓친 것과 지어낸 것은 다른 문제다.

## 못 재는 것

**`fact_key` 묶기와 병합 결과는 여기서 안 잰다.** 그건 `build.py` 를 통과해야 나오고,
`--rebuild` 로 실제로 세워 본 뒤 `--wiki` 로 봐야 한다. 여기는 추출기 한 겹만 잰다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from finnect.config import settings
from finnect.wiki import extract, topics
from finnect.wiki.extract import Fact, FactExtractor, FileView

#: `service.py` 와 같은 표여야 한다 — 쪽이 있는 포맷만 번호를 붙인다.
NUMBERED = {"pdf": True, "hwp": True, "hwpx": True, "docx": True, "pptx": True, "xlsx": False}


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _value_key(f: Fact) -> tuple:
    return ("value", f.value_topic, (f.value or "").strip(), f.as_of, (f.qualifier or "").strip())


@dataclass(slots=True)
class FileScore:
    filename: str
    gold: int = 0
    got: int = 0
    hit: int = 0
    dropped: int = 0  # 앵커가 원문에 없어 버린 것
    missed: list[str] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Score:
    files: list[FileScore] = field(default_factory=list)
    by_topic: Counter = field(default_factory=Counter)
    gold_by_topic: Counter = field(default_factory=Counter)

    @property
    def gold(self) -> int:
        return sum(f.gold for f in self.files)

    @property
    def got(self) -> int:
        return sum(f.got for f in self.files)

    @property
    def hit(self) -> int:
        return sum(f.hit for f in self.files)

    def render(self) -> str:
        recall = self.hit / self.gold * 100 if self.gold else 0
        prec = self.hit / self.got * 100 if self.got else 0
        lines = [
            f"[추출 채점] 정답 {self.gold} · 낸 것 {self.got} · 맞은 것 {self.hit}",
            f"  재현율 {recall:.1f}%  (정답 중 몇 개를 찾았나)",
            f"  정밀도 {prec:.1f}%  (낸 것 중 몇 개가 맞나)",
            "",
            f"  {'파일':34} {'정답':>4} {'낸것':>4} {'맞음':>4} {'버림':>4}",
        ]
        for f in self.files:
            lines.append(
                f"  {f.filename[:34]:34} {f.gold:4} {f.got:4} {f.hit:4} {f.dropped:4}"
            )
        miss = [m for f in self.files for m in f.missed]
        spur = [s for f in self.files for s in f.spurious]
        if miss:
            lines += ["", f"  [놓친 것 {len(miss)}건 중 앞 15]"]
            lines += [f"    {m}" for m in miss[:15]]
        if spur:
            lines += ["", f"  [정답에 없는 것 {len(spur)}건 중 앞 15]"]
            lines += [f"    {s}" for s in spur[:15]]
        lines += [
            "",
            "  **정답에 없다고 전부 틀린 것이 아니다.** 픽스처는 사람이 옮긴 것이라",
            "  빠뜨린 사실이 있을 수 있다. 위 목록을 눈으로 보고 몇 건을 봤는지 함께 적는다.",
        ]
        return "\n".join(lines)


def _gold(path: Path | None = None) -> dict[str, tuple[str, list[Fact]]]:
    """정답지. `StubExtractor` 가 읽는 것과 같은 파일이다."""
    raw = json.loads((path or settings.wiki_stub_facts).read_text(encoding="utf-8"))
    return {
        e["sha256"]: (e.get("filename") or e["sha256"][:12],
                      [extract._fact(f) for f in e["facts"]])
        for e in raw["files"]
    }


def _views(gold: dict, corpus: Path) -> dict[str, FileView]:
    """**진짜 파일을 파싱해서 청크로 준다.** 실제 파이프라인과 같은 입력이다.

    처음에는 정답 앵커만 이어 붙여 줬다. 파서 성능을 섞지 않으려는 것이었는데
    **그게 가짜 과제였다.** 앵커 더미는 문서가 아니라 조각 더미다.

    2026-08-20 실측 — 문서 작성일(`2025. 08. 22. 기준`)이 앵커 밖에 있어서
    모델이 볼 수가 없었다. 시점 있는 value topic 22건이 그것 하나로 어긋났고, 그건
    **모델이 못한 게 아니라 우리가 안 보여 준 것**이다.

    파서는 [plan/12](../../../docs/plan/12-사업-위키-구축.md) 가 따로 검증했다.
    여기서 섞이는 것을 감수하고 **실제 입력**을 준다.
    """
    from finnect.attach import extract as attach_extract
    from finnect.wiki import chunk

    out = {}
    for sha, (name, _) in gold.items():
        path = corpus / name
        if not path.exists():
            raise FileNotFoundError(f"코퍼스에 없어요 — {path}")
        parsed = attach_extract.parse(
            path, name, allowed=settings.wiki_formats, use_ocr=settings.user_file_ocr
        )
        pages = parsed.pages or [parsed.text or ""]
        pieces = chunk.split(pages, numbered=NUMBERED.get(path.suffix.lstrip(".").lower()))
        out[sha] = FileView(
            sha256=sha, filename=name,
            chunks=tuple((i, pc.text) for i, pc in enumerate(pieces)),
        )
    return out


def run(
    extractor: FactExtractor | None = None,
    *,
    gold_path: Path | None = None,
    corpus: Path | None = None,
) -> Score:
    """정답지의 파일마다 추출기를 돌려 대조한다. **진짜 파일을 파싱한다.**"""
    ex = extractor or extract.get_extractor()
    gold_path = gold_path or settings.wiki_stub_facts
    gold = _gold(gold_path)
    views = _views(gold, corpus or gold_path.parent)
    score = Score()

    for sha, (name, want) in gold.items():
        fs = FileScore(filename=name, gold=len(want))
        before = len(getattr(ex, "dropped", []))
        got = ex.extract(views[sha])
        fs.dropped = len(getattr(ex, "dropped", [])) - before
        fs.got = len(got)

        left = list(got)
        for w in want:
            score.gold_by_topic[w.topic] += 1
            hit = _find(w, left)
            if hit is None:
                fs.missed.append(f"[{name[:16]}] {w.kind} {w.topic} — {w.text[:44]}")
                continue
            left.remove(hit)
            fs.hit += 1
            score.by_topic[w.topic] += 1
        fs.spurious = [f"[{name[:16]}] {g.kind} {g.topic} — {g.text[:44]}" for g in left]
        score.files.append(fs)
    return score


def _find(want: Fact, pool: list[Fact]) -> Fact | None:
    """정답 하나에 짝을 찾는다. **찾으면 그 출력은 소비된다** — 하나가 둘을 못 맞춘다."""
    if want.kind == "value":
        key = _value_key(want)
        return next((g for g in pool if g.kind == "value" and _value_key(g) == key), None)
    # 서술은 **원문의 같은 자리**를 가리키면 같은 것으로 본다
    node = topics.orbit_of(want.topic)
    a = _squash(want.anchor)
    best, score = None, 0.0
    for g in pool:
        if g.kind != "event" or topics.orbit_of(g.topic) != node:
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
