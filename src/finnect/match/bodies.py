"""공고 본문을 정규화가 읽는 모양으로 만든다 (plan/17 T-0070).

`views.py` 와 같은 자리다 — 두 출처가 필드 이름을 하나도 공유하지 않으므로
(22 · 30 · 교집합 0) 매핑이 한 곳에만 있어야 한다.

## `notice-filter/` 를 임포트하지 않는다

절 나누기가 저쪽에도 있다(`clean_summary` · `first_clause` · `second_clause`).
**베껴 쓴다.** 저쪽은 제품 코드가 아니고 `src/finnect/` 와 `web/` 에 아무것도 안
붙어 있는 것이 그 폴더의 성질이다 — 임포트하면 그 성질이 깨지고, 저쪽 규칙이 바뀌면
제품 판정이 조용히 따라 바뀐다.

**대가를 적어 둔다.** 같은 정규식이 두 곳에 산다. `☞` 규칙이 바뀌면 둘 다 고쳐야
하고, `tests/test_match_bodies.py` 가 그 규칙을 픽스처로 박아 둔다.

## 기업마당 `bsnsSumryCn` 은 HTML 이다

태그와 엔티티를 풀지 않으면 앵커 대조가 깨진다. `&nbsp;` 하나로는 부족하다 — 실측에서
`R&amp;D역량` 이 남아 정상 응답이 버려졌다(아래 `clean_summary`).
"""

from __future__ import annotations

import html
import re

from finnect.match.normalize import NoticeBody

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
#: 기업마당 요약은 `☞ 지원대상 … ☞ 지원내용 …` 이다. U+261E
_POINT = "☞"


def clean_summary(raw: str | None) -> str:
    """태그를 지우고 **HTML 엔티티를 전부 푼다.**

    `notice-filter` 는 `&nbsp;` 하나만 풀었다. 여기서는 `html.unescape` 를 쓴다 —
    실측(2026-08-20)에서 `R&amp;D역량` 이 남아 앵커 대조가 깨졌다. 모델은
    `R&D역량` 으로 **정직하게** 인용했는데 우리 원문이 이스케이프된 채였다.

    저장은 안 건드린다(API 가 준 것을 그대로 담는 원칙) — 여기는 읽는 쪽이고,
    태그를 이미 지우고 있으므로 같은 자리다. `match/sectors.normalize()` 가
    `기술개발(R&amp;D)` 에 같은 일을 하는 것과 같은 이유다.
    """
    s = html.unescape(_TAG.sub(" ", raw or ""))
    return _WS.sub(" ", s)


def first_clause(sm: str) -> str:
    """첫 `☞` 절 = 지원대상."""
    m = re.search(rf"{_POINT}\s*([^{_POINT}]{{3,600}})", sm)
    if not m:
        return ""
    return _WS.sub(" ", re.split(r"※|\n", m.group(1))[0]).strip(" -·ㆍ")


def second_clause(sm: str) -> str:
    """두 번째 `☞` 절 = 지원내용."""
    p = re.split(_POINT, sm)
    if len(p) <= 2:
        return ""
    return _WS.sub(" ", re.split(r"※", p[2])[0]).strip(" -·ㆍ")


def from_bizinfo(row) -> NoticeBody:  # noqa: ANN001
    """`bizinfo_notice` 한 행. **컬럼 이름이 API 필드명 그대로다.**"""
    sm = clean_summary(getattr(row, "bsnsSumryCn", None))
    target = first_clause(sm)
    body = second_clause(sm)
    # 절이 안 갈리는 공고가 있다(`☞` 가 없다). **빈 채로 넘기지 않는다** —
    # 요약 전체를 지원대상 자리에 넣는다. 지역·업종이 거기 있다
    if not target:
        target = sm[:600]
    return NoticeBody(
        source="bizinfo",
        external_id=getattr(row, "pblancId", "") or "",
        title=getattr(row, "pblancNm", "") or "",
        target=target,
        body=body or (getattr(row, "trgetNm", "") or ""),
    )


def from_kstartup(row) -> NoticeBody:  # noqa: ANN001
    """`kstartup_notice` 한 행. **`aply_trgt_ctnt` 가 지원대상이다.**"""
    return NoticeBody(
        source="kstartup",
        external_id=getattr(row, "pbanc_sn", "") or "",
        title=getattr(row, "biz_pbanc_nm", "") or "",
        target=_WS.sub(" ", getattr(row, "aply_trgt_ctnt", None) or ""),
        body=_WS.sub(" ", getattr(row, "pbanc_ctnt", None) or ""),
    )
