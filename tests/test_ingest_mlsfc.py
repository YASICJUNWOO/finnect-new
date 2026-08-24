"""중분류 솎기 표가 `notice-filter` 원본과 갈리지 않게 막는다.

**원본을 임포트하지 않는다.** `notice-filter/` 는 층0 이라 `src/finnect/` 가 못 끌어온다
(`tests/test_attach_only.py`·`tests/test_match_only.py` 와 같은 경계). 그래서 파일을
**AST 로 읽어** 상수만 꺼낸다 — 임포트가 아니라 파싱이라 저쪽 의존성이 하나도 안 딸려온다.

두 표가 갈리면 `notice-filter` 의 퍼널과 우리 코퍼스가 다른 모집단이 되고, 어느 쪽이
맞는지 나중에 못 가린다. **조용히 어긋나는 자리라** 테스트로 막는다.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from finnect.ingest import mlsfc

ORIGIN = pathlib.Path(__file__).resolve().parents[1] / "notice-filter" / "filter.py"


def _literal(name: str) -> set[str]:
    """`filter.py` 최상위의 집합 리터럴 하나를 꺼낸다."""
    tree = ast.parse(ORIGIN.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = node.value
            # `SKIP_MLSFC_NOPLAN` 은 순수 리터럴이고 `UNVERIFIED_MLSFC` 는 `| SKIP_MLSFC` 다.
            # 우리가 대조하는 둘은 전자라 리터럴 평가로 충분하다.
            return set(ast.literal_eval(value))
    raise AssertionError(f"{name} 을 {ORIGIN} 에서 못 찾았다")


@pytest.mark.parametrize(
    ("name", "ours"),
    [("SKIP_MLSFC", mlsfc.SKIP_MLSFC), ("SKIP_MLSFC_NOPLAN", mlsfc.SKIP_MLSFC_NOPLAN)],
)
def test_사본이_원본과_같다(name: str, ours: frozenset[str]) -> None:
    theirs = _literal(name)
    assert set(ours) == theirs, (
        f"{name} 이 갈렸다. notice-filter 에만 {theirs - set(ours)}, "
        f"우리에만 {set(ours) - theirs}"
    )


def test_스무_개다() -> None:
    """건수를 박아 둔다. 한쪽이 늘고 다른 쪽이 줄면 집합 비교만으로는 안 걸린다."""
    assert len(mlsfc.SKIPPED) == 20
    assert not (mlsfc.SKIP_MLSFC & mlsfc.SKIP_MLSFC_NOPLAN), "두 축이 겹치면 안 된다"


def test_모르는_값은_남긴다() -> None:
    """표에 없는 중분류가 새로 생겨도 조용히 안 버린다.

    늘어난 쪽은 화면에서 티가 나지만 **줄어든 쪽은 안 난다.**
    """
    assert mlsfc.keeps("아직 없는 분류")
    assert mlsfc.keeps(None)
    assert mlsfc.keeps("")


def test_표에_있는_값은_뺀다() -> None:
    assert not mlsfc.keeps("융자")
    assert not mlsfc.keeps("제도")
    assert not mlsfc.keeps("  융자  "), "앞뒤 공백이 판정을 바꾸면 안 된다"
