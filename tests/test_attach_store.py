"""콘텐츠 주소 저장.

**이름을 내용으로 짓는 이유는 재수집이다.** 공고가 갱신되면 `attachment` 행이 통째로
지워지고 다시 깔린다. 파일 이름을 공고 ID 나 첨부 ID 로 지으면 그때 고아가 된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finnect.attach import store
from finnect.config import settings


@pytest.fixture(autouse=True)
def _tmp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "attachment_dir", tmp_path)


def test_같은_내용은_같은_자리에_한_번만_쓴다() -> None:
    first = store.put(b"hello")
    written = store.abs_path(first).stat().st_mtime_ns

    second = store.put(b"hello")

    assert first == second
    assert store.abs_path(second).stat().st_mtime_ns == written, "같은 내용을 다시 썼다"


def test_다른_내용은_다른_자리다() -> None:
    assert store.put(b"hello") != store.put(b"world")


def test_경로가_해시_앞_두_글자로_갈린다() -> None:
    rel = store.put(b"hello")
    sha = store.digest(b"hello")

    assert rel == f"{sha[:2]}/{sha}"
    assert store.abs_path(rel).read_bytes() == b"hello"


def test_추출_텍스트는_원본_해시로_이름을_짓는다() -> None:
    """원본과 파생물이 같은 자리에 있어야 파서를 고쳤을 때 다시 안 받는다."""
    body = "원본".encode()
    sha = store.digest(body)
    store.put(body)

    rel = store.put_text(sha, "뽑은 텍스트")

    assert rel == f"{sha[:2]}/{sha}.txt"
    assert store.abs_path(rel).read_text(encoding="utf-8") == "뽑은 텍스트"


def test_반쪽짜리_파일이_안_남는다() -> None:
    """임시 파일에 쓰고 이름을 바꾼다. .part 가 남아 있으면 안 된다."""
    rel = store.put(b"hello")

    assert store.exists(rel)
    assert list(store.abs_path(rel).parent.glob("*.part")) == []


def test_없는_경로는_없다고_한다() -> None:
    assert store.exists(None) is False
    assert store.exists("aa/" + "0" * 64) is False
