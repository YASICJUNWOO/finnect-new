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
| 덮어쓰기 | 가능 (판본 I) | 가능 | 가능 |
| 개체 앵커가 든 자리 | **불가** | 가능 | 가능 |
| 런타임 | **순수 파이썬** (일부만 JVM) | 순수 파이썬 | 순수 파이썬 |
| 코퍼스 비율 | **73%** | 14% | 5% |

**2026-08-24 hwp 에서 JVM 이 빠졌다**([ADR-0070](
../../../docs/adr/0070-hwp-를-바이트로-읽고-쓴다.md)). 읽기·자리찾기·쓰기가 전부
`forms/hwp5.py` 의 레코드 편집으로 돈다 — `olefile` 은 이미 기본 의존성이라 새로
드는 것이 없다. **Java 가 붙는 자리는 하나 남았다**: 되쓴 본문이 원본 스트림 크기
안에 안 들어가는 파일(실측 5~8%)에서만 `forms/hwplib.py` 로 넘어간다. 그때 Java 가
없으면 **그 파일만** `FormsUnavailable` 이고 나머지는 그대로 돈다.

**2026-08-23 hwp 의 덮어쓰기 칸이 열렸다**(plan/24 T-0164 · [실측](
../../../docs/adr/evidence/2026-08-23-hwp-덮어쓰기가-된다.md)). 오래 여기 「불가」가
적혀 있었고 그것이 **이 제품의 축**이었다 — 가장 많은 포맷에서 가장 적게 할 수 있다는
말이었다. 남은 hwp 만의 제약은 개체 앵커가 든 문단 하나다.
"""

from __future__ import annotations

from finnect.forms.base import (
    Anchor,
    Cell,
    Form,
    FormsUnavailable,
    Para,
    ParaAnchor,
    Slot,
    UnsupportedFormat,
    is_placeholder,
    label_paths,
    label_targets,
    norm_label,
    outline_targets,
    parse_anchor,
)

__all__ = [
    "PLANNED",
    "SUPPORTED",
    "Anchor",
    "Cell",
    "Form",
    "FormsUnavailable",
    "Para",
    "ParaAnchor",
    "Slot",
    "UnsupportedFormat",
    "is_placeholder",
    "label_paths",
    "label_targets",
    "norm_label",
    "open_form",
    "outline_targets",
    "parse_anchor",
]

#: **지금 어댑터가 있는 포맷.** 판정은 내용이 한다(`attach/formats.py`) — 파일명의
#: 확장자를 믿으면 3,354건 중 7건이 어긋난다.
#:
#: **셋이 다 찼다**(2026-08-23). hwp 를 먼저 한 이유는 코퍼스의 73% 이고 제약이
#: 가장 세서였다 — 인터페이스가 그 제약을 견디니 나머지 둘이 얹혔다.
SUPPORTED: frozenset[str] = frozenset({"hwp", "hwpx", "docx"})

#: 될 것이 확인됐지만 어댑터를 아직 안 쓴 것.
#: **`UnsupportedFormat` 과 가르려고 따로 둔다** — 저기는 영영 안 되는 것이다.
#: **지금은 비어 있다.** 지우지 않는 이유는 xlsx 가 여기 올 자리이기 때문이다.
PLANNED: frozenset[str] = frozenset()

#: 덮어쓸 수 있는 포맷. **셋이 다 찼다**(2026-08-23 · plan/24 T-0164).
#:
#: hwp 가 오래 빠져 있었다 — 기존 글자를 갈아 끼우면 한/글에서 표가 밀렸다
#: (ADR-0060 결정 3, 판본 A~G). 판본 I(`ParaText` 객체를 없앴다 새로 만든다)가
#: 그 파일에서 안 밀렸고 육안으로 확인했다. **ADR 은 아직 그 자리에 있다** — 결정
#: 3 은 양식 20건으로 정해졌고 육안은 두 건이다.
#:
#: 안내문이 든 칸은 덮어써야 채워지므로 **이 집합이 「어느 칸까지 채울 수 있나」를
#: 정한다.** 어느 칸이 값 자리인지는 `forms/slots.py` 가 답한다.
OVERWRITABLE: frozenset[str] = frozenset({"hwp", "hwpx", "docx"})


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

    if ext == "docx":
        from finnect.forms.docx import DocxForm

        return DocxForm(path)

    if ext == "hwpx":
        from finnect.forms.hwpx import HwpxForm

        return HwpxForm(path)

    from finnect.forms.hwp import HwpForm

    return HwpForm(path)
