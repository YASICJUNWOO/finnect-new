"""출처가 준 본문에서 화면에 쓸 글자를 뽑는다.

기업마당 `bsnsSumryCn` 은 **HTML 통째**다. `<p>`, `<br>`, `style=` 속성, `&nbsp;` 가 섞여 온다.
K-Startup `pbanc_ctnt` 는 대체로 평문이지만 엔티티가 섞인다.

**원문을 고치지 않는다.** DB 에는 받은 그대로 있고 여기서 읽을 때만 편다.
"""

from __future__ import annotations

import html
import re

#: 통째로 버리는 것. 안의 내용도 본문이 아니다.
_DROP_BLOCK = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)

#: 줄바꿈으로 바꿀 태그. 문단이 붙어 버리는 것을 막는다.
_BREAK = re.compile(r"<\s*(br|/p|/div|/li|/tr|/h[1-6])\s*/?\s*>", re.IGNORECASE)

_TAG = re.compile(r"<[^>]+>")

#: 3줄 이상 연속된 빈 줄은 2줄로. 원문에 `<p><br></p>` 가 반복된다.
_BLANK_RUN = re.compile(r"\n{3,}")

#: 줄 안의 연속 공백. 줄바꿈은 건드리지 않는다.
_INLINE_SPACE = re.compile(r"[^\S\n]{2,}")


def to_text(value: str | None) -> str | None:
    """HTML 이 섞인 본문을 평문으로. 빈 값과 '태그뿐인 값'은 None 으로 돌려준다.

    None 을 돌려주는 이유는 화면이 **"내용이 없다"를 알아야 하기 때문**이다.
    빈 문자열로 주면 화면이 빈 문단을 그린다.
    """
    if not value:
        return None

    s = _DROP_BLOCK.sub(" ", value)
    s = _BREAK.sub("\n", s)
    s = _TAG.sub("", s)
    # 엔티티는 태그를 지운 뒤에 푼다. 먼저 풀면 `&lt;p&gt;` 가 태그로 되살아난다.
    s = html.unescape(s)
    # `&nbsp;` 가 푼 뒤 U+00A0 으로 남는다. 보통 공백으로 눕힌다.
    s = s.replace("\xa0", " ")

    s = _INLINE_SPACE.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _BLANK_RUN.sub("\n\n", s).strip()

    return s or None
