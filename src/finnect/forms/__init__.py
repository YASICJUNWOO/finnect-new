"""양식을 채워서 원본 포맷으로 돌려준다 (plan/24 · [ADR-0060](
../../../docs/adr/0060-양식을-채워서-원본-포맷으로-돌려준다.md)).

**이 파일을 임포트해도 무거운 것이 안 딸려 온다.** 어댑터는 `open_form()` 이
포맷을 보고 나서야 임포트한다 — 최상단에 두면 `import finnect.forms` 가 hwp
경로에서 **jpype 와 JVM** 을 끌고 오고, 그러면 로컬은 통과하고 배포본만 죽는다
(`api/app.py` 가 `wiki.service` 를 함수 안에서 부르는 것과 같은 함정).

포맷마다 되는 범위가 다르다.

| | hwp | hwpx | docx |
|---|---|---|---|
| 빈 칸 채우기 | 가능 | 가능 | 가능 |
| 덮어쓰기 | **불가** | 가능 | 가능 |
| 런타임 | **JVM** | 순수 파이썬 | 순수 파이썬 |
| 코퍼스 비율 | **73%** | 14% | 5% |

**hwp 제약이 축이다.** 가장 많은 포맷에서 가장 적게 할 수 있다.
"""

from __future__ import annotations

from finnect.forms.base import (
    Anchor,
    Cell,
    Form,
    FormsUnavailable,
    UnsupportedFormat,
    label_targets,
    norm_label,
)

__all__ = [
    "PLANNED",
    "SUPPORTED",
    "Anchor",
    "Cell",
    "Form",
    "FormsUnavailable",
    "UnsupportedFormat",
    "label_targets",
    "norm_label",
    "open_form",
]

#: **지금 어댑터가 있는 포맷.** 판정은 내용이 한다(`attach/formats.py`) — 파일명의
#: 확장자를 믿으면 3,354건 중 7건이 어긋난다.
#:
#: **hwpx·docx 가 아직 없다.** ADR-0060 이 셋 다 된다고 재 뒀고 `spike/` 에 실측
#: 코드가 있지만 제품 어댑터는 hwp 뿐이다. hwp 를 먼저 한 이유는 **코퍼스의 73%**
#: 이고 제약이 가장 세서다 — 인터페이스가 그 제약을 견디면 나머지 둘은 얹힌다.
#: 여기 목록에 미리 넣지 않는 이유는 **넣으면 화면이 「된다」고 말하기 때문이다.**
SUPPORTED: frozenset[str] = frozenset({"hwp"})

#: 될 것이 확인됐지만 어댑터를 아직 안 쓴 것(plan/24 T-0151 나머지).
#: **`UnsupportedFormat` 과 가르려고 따로 둔다** — 저기는 영영 안 되는 것이다.
PLANNED: frozenset[str] = frozenset({"hwpx", "docx"})


def open_form(path: str, ext: str) -> Form:
    """양식 하나를 연다. **어댑터를 여기서만 임포트한다.**

    `ext` 를 받는 이유는 우리 저장소가 콘텐츠 주소라 **파일 이름에 확장자가 없어서**다
    (`openpyxl` 이 이름을 보고 죽던 것과 같은 자리). 값은 `attachment_file.detected_ext`
    이고 내용으로 판정한 것이다.
    """
    if ext in PLANNED:
        raise UnsupportedFormat(f"{ext} 는 아직 못 채워요 (plan/24 T-0151)")
    if ext not in SUPPORTED:
        raise UnsupportedFormat(f"채울 수 없는 포맷: {ext}")

    from finnect.forms.hwp import HwpForm

    return HwpForm(path)
