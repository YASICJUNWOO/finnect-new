"""파일 하나가 지금 어디까지 왔나(SPEC F1-1-9 · plan/15 T-0060).

**상태는 이미 DB 에 있다.** `UserFileStatus` 일곱 가지를 `service.ingest_file` 과
`build.build_company` 가 실제로 밟는다. 여기가 하는 일은 그 상태를 **사람이 읽는 단계**로
옮기는 것 하나다.

## 단계 이름을 프론트가 짓지 않는다

`topics.display()` 가 단위를 한 자리에서 붙이는 것과 같은 이유다. 화면과 API 가 각자
라벨을 들면 둘이 갈리고, 갈린 순간 어느 쪽이 진짜 상태인지 알 수 없게 된다.

## 멈춘 것과 도는 중인 것을 가른다

**`chunked` 하나가 두 가지 뜻을 갖는다.** 파일을 막 넣었을 때는 "사실을 뽑을 차례"이고,
빌드가 끝난 뒤에도 `chunked` 면 "추출기가 이 파일을 몰라서 되돌려놨다"다(`build._shelve`).
행만 봐서는 구분이 안 된다.

그래서 `running` 을 함께 받는다. 값은 DB 가 아니라 `ingest.jobs` 의 락에서 온다 —
**컬럼을 하나 더 만들면 배포 DB 에도 마이그레이션을 돌려야 하고**(CLAUDE.md 함정),
이 값은 프로세스가 죽으면 같이 죽는 게 맞는 종류다.

이 모듈은 DB 도 파서도 모른다. `finnect.models` 의 상태 이름만 안다.
"""

from __future__ import annotations

from dataclasses import dataclass

from finnect.models import UserFileStatus


@dataclass(frozen=True, slots=True)
class Step:
    """단계 하나. **다섯 개가 전부다.**"""

    key: str
    label: str


#: 파일 하나가 지나는 길. `UserFileStatus` 여덟 중 끝 상태 셋을 뺀 다섯이다.
#:
#: **`chunked` 를 한 칸으로 세는 것이 요점이다.** `models.UserFileStatus` 가 SPEC 의
#: 상태머신에 이 값을 하나 더 둔 이유가 "해독은 됐고 사실은 안 뽑았다"를 말하기 위해서인데,
#: 그 자리를 화면에서 지우면 진행 표시가 다시 거짓이 된다.
STEPS: tuple[Step, ...] = (
    Step("receive", "파일 받기"),
    Step("parse", "글자 읽기"),
    Step("chunk", "조각 내기"),
    Step("extract", "사실 뽑기"),
    Step("link", "자리에 놓기"),
)

#: 더 안 움직이는 상태. 나머지는 도는 중이거나 **멈춘 것**이다
TERMINAL = frozenset({UserFileStatus.DONE, UserFileStatus.NEEDS_REVIEW, UserFileStatus.FAILED})

#: 도는 중일 때 / 멈춰 있을 때. **같은 행이 다른 말을 한다**
_MID: dict[str, tuple[int, str, str]] = {
    UserFileStatus.UPLOADED: (1, "차례를 기다려요", "읽지 못하고 멈췄어요"),
    UserFileStatus.PARSING: (1, "글자를 읽고 있어요", "읽다가 멈췄어요"),
    UserFileStatus.CHUNKED: (3, "사실을 뽑을 차례예요", "사실을 못 뽑았어요"),
    UserFileStatus.EXTRACTING: (3, "사실을 뽑고 있어요", "뽑다가 멈췄어요"),
    UserFileStatus.LINKING: (4, "자리에 놓고 있어요", "놓다가 멈췄어요"),
}

#: 끝난 상태. (끝낸 칸 수, 한 마디, 성공인가)
#:
#: **`needs_review` 와 `failed` 가 같은 칸에서 끝난다.** 둘 다 글자를 못 얻은 것이라
#: 진행 칸으로는 구분이 안 된다 — 무엇이 달랐는지는 글자가 말한다(DESIGN.md §4.1).
_END: dict[str, tuple[int, str, bool]] = {
    UserFileStatus.NEEDS_REVIEW: (1, "글자가 안 나왔어요", False),
    UserFileStatus.DONE: (len(STEPS), "다 됐어요", True),
    UserFileStatus.FAILED: (1, "못 읽었어요", False),
}


@dataclass(frozen=True, slots=True)
class Stage:
    """그 파일의 지금. **`reached` 는 끝낸 칸 수이지 백분율이 아니다.**"""

    #: 끝낸 칸 수. 0 ~ len(STEPS)
    reached: int
    #: 사람이 읽는 한 마디
    label: str
    #: 아직 움직이나. 화면이 계속 물어볼지를 이 값 하나로 정한다
    moving: bool
    #: 끝났고 성공인가. 움직이는 중이면 항상 False 다 — **아직 모른다**
    ok: bool


def stage_of(status: str | None, *, running: bool, failed: bool = False) -> Stage:
    """상태 하나를 단계로 옮긴다.

    `running` 은 이 회사의 빌드가 지금 도는 중인가다. 모르는 상태가 오면 0칸으로 두고
    이름을 그대로 보여 준다 — **아는 척해서 다 됐다고 말하지 않는다.**

    `failed` 는 `user_file.extract_error` 가 찼나다(plan/12 T-0093). **`running` 만으로는
    틀리는 자리가 있었다** — 되돌려진 파일 옆에서 다른 파일의 빌드가 돌고 있으면
    `running=True` 라 "사실을 뽑을 차례예요" 로 보이고 화면이 영영 물어본다. 이 값이
    있으면 `chunked` 의 뜻이 하나로 정해진다.
    """
    if status in _END:
        reached, label, ok = _END[status]
        return Stage(reached=reached, label=label, moving=False, ok=ok)

    if status in _MID:
        reached, going, stopped = _MID[status]
        moving = running and not failed
        return Stage(
            reached=reached,
            label=going if moving else stopped,
            moving=moving,
            ok=False,
        )

    return Stage(reached=0, label=f"모르는 상태예요 — {status}", moving=False, ok=False)
