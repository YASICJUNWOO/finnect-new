"""추출 포트 — 트랙 둘이 같이 쓰는 것(ADR-0031 그대로 · ADR-0056 결정 1).

트랙이 둘로 갈렸다. 묻는 것도 다르고 스키마도 다르고 잘한 기준도 다르다.

    extract_nodes.py     트랙 A — 「이 문서가 우리 사업에 대해 뭐라고 말하나」
    extract_profile.py   트랙 B — 「소재지·직원 수·업종은 얼마인가」

**같은 것은 셋뿐이다** — 넘기는 입력(`FileView`) · 앵커 규칙(`squash`) · 갈라짐을 막는
장치(`Roster`). 그 셋이 여기 산다. 나머지를 여기 올리면 튜닝 방향이 반대인 둘이 다시
한 파일에서 서로를 끌어당긴다.

## 여기도 DB 를 모른다

`Known` 이 DB 에서 온 값을 들고 있지만 **읽는 것은 `build.py` 다.** 포트는 문자열
목록만 받는다 — 그래야 추출기를 테스트에서 손으로 부를 수 있다.

## 갈라짐을 막는 장치가 이 파일의 요점이다

동적 이름의 유일한 위험은 **같은 얘기가 여러 자리로 흩어지는 것**이다
(`기능` · `주요기능` · `핵심 기능`). 막는 방법이 둘이고 **둘 다 쓴다**(ADR-0056 결정 6).

1. **번호로 답하게 한다.** 프롬프트에 지금 있는 것을 번호와 함께 싣고 `node_ref: 3`
   으로 받는다. 자유 문자열로 받으면 `Product/기능`·`기능`·`Product/ 기능` 이 전부
   새 자리가 된다
2. **코드가 마지막 그물이다.** 새 이름이 와도 정규화 후 기존과 정확히 같으면 조용히
   기존으로 돌린다(`Roster.fold`)

**유사도를 안 쓴다.** 쓰면 같은 문서를 두 번 올릴 때 다른 자리로 가서 비결정론이 된다.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from finnect.wiki import tree


class UnknownFile(Exception):
    """스텁이 모르는 파일. **빈 결과로 넘기지 않는다.**

    조용히 비면 진짜 사용자 파일에 가짜가 섞이거나, 더 나쁘게는 **아무것도 안 나온 것이
    정상처럼 보인다**(ADR-0031).
    """


def squash(s: str) -> str:
    """공백을 지운 형태로 비교한다. **`build.py` 와 같은 규칙이어야 한다** —
    거기서 근거 청크를 찾을 때 쓰는 것과 다르면 여기서 통과한 앵커가 거기서 죽는다."""
    return re.sub(r"\s+", "", s)


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


@dataclass(slots=True)
class Roster:
    """번호 ↔ 이름, 그리고 **코드 그물**(ADR-0056 결정 6).

    번호는 **1부터**다. 0 을 쓰면 「없음」과 「첫째」가 JSON 에서 구분이 안 된다.

    `fold` 가 그물이자 등록이다 — 부를 때마다 목록이 자란다. 그래서 **한 호출 결과
    안에서도** 갈라짐이 막힌다: 프롬프트에 실린 것은 이전 상태라 한 파일에서 `기능` 과
    `기 능` 을 둘 다 만들 수 있는데, 앞엣것이 등록되면서 뒤엣것이 거기로 접힌다.

    **부르는 쪽의 것을 건드리지 않는다.** 추출기는 `copy()` 로 갈래를 떠서 쓴다 —
    추출이 실패해 사실이 하나도 안 앉는 파일이 `Known` 을 오염시키면 안 된다.
    """

    #: 무엇을 같다고 볼 것인가. 경로는 `tree.norm_path`, 이름은 `tree.norm`
    norm: Callable[[str], str] = tree.norm
    names: list[str] = field(default_factory=list)
    #: 정규화된 이름 → 처음 등록된 표기. **먼저 온 표기가 이긴다**
    index: dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, names: Iterable[str], *, norm: Callable[[str], str] = tree.norm) -> Roster:
        r = cls(norm=norm)
        for n in names:
            r.fold(n)
        return r

    def copy(self) -> Roster:
        return Roster(norm=self.norm, names=list(self.names), index=dict(self.index))

    def ref(self, n: int | None) -> str | None:
        """번호로 이름을 꺼낸다. **범위 밖이면 `None`** — 지어내지 않는다.

        모델이 없는 번호를 낼 수 있다. 그때 이름을 만들어 주면 그 사실이 엉뚱한 자리에
        앉고, 앉은 뒤에는 왜 거기 있는지 아무도 못 찾는다. 부르는 쪽이 새 이름 쪽으로
        떨어지게 둔다.
        """
        if n is None:
            return None
        i = int(n) - 1
        return self.names[i] if 0 <= i < len(self.names) else None

    def fold(self, name: str | None) -> str:
        """정규화 정확 일치면 **기존 표기**를, 없으면 등록하고 그대로 돌려준다.

        `기 능` 과 `기능` 은 같은 자리이고 `기능` 과 `주요기능` 은 **다른 자리다.**
        유사도를 쓰면 다시 비결정론이다.
        """
        clean = " ".join((name or "").split()).strip()
        if not clean:
            return ""
        k = self.norm(clean)
        if not k:
            return clean
        got = self.index.get(k)
        if got is not None:
            return got
        self.index[k] = clean
        self.names.append(clean)
        return clean

    def render(self, empty: str = "(아직 없다)") -> str:
        """프롬프트에 싣는 모양. `[1] Company/팀` 꼴이다."""
        if not self.names:
            return empty
        return "\n".join(f"[{i}] {n}" for i, n in enumerate(self.names, 1))


@dataclass(frozen=True, slots=True)
class Known:
    """지금 있는 이름들. **번호로 답하게 하려고 프롬프트에 싣는다.**

    **트랙 B 는 `qualifiers` 만 읽는다.** 거기 key 는 고정 열넷이라 enum 이 막아 주고
    노드가 없다. 그래도 같은 타입을 쓰는 이유는 `build.py` 가 파일마다 하나만 만들면
    되기 때문이다 — 둘로 나누면 같은 조회를 두 번 한다.
    """

    nodes: Roster = field(default_factory=lambda: Roster(norm=tree.norm_path))
    keys: Roster = field(default_factory=Roster)
    qualifiers: Roster = field(default_factory=Roster)

    @classmethod
    def of(
        cls,
        *,
        nodes: Iterable[str] = (),
        keys: Iterable[str] = (),
        qualifiers: Iterable[str] = (),
    ) -> Known:
        return cls(
            nodes=Roster.of(nodes, norm=tree.norm_path),
            keys=Roster.of(keys),
            qualifiers=Roster.of(qualifiers),
        )


def anchored(view: FileView, anchor: str) -> bool:
    """이 앵커가 원문에 있나. **없으면 그 사실은 버린다**(ADR-0014).

    추출기가 자기 출력을 원문에 대조하는 자리다. `build.py` 가 청크를 찾을 때 한 번 더
    보지만, **여기서 걸러야 무엇이 왜 사라졌는지 남는다**(ADR-0037 결정 5).
    """
    a = squash(anchor)
    return bool(a) and a in squash(view.text)
