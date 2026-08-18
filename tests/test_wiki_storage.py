"""사용자 파일 저장과 격리 — ADR-0029.

`attach/store.py` 와 닮았지만 검증할 것이 다르다. 저쪽은 "같은 내용을 두 번 안 쓴다"였고
여기는 **"다른 회사 것에 닿지 않는다"** 다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finnect.config import settings
from finnect.wiki import storage


@pytest.fixture(autouse=True)
def _tmp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "user_file_dir", tmp_path)


def test_같은_회사가_같은_파일을_다시_올리면_다시_안_쓴다() -> None:
    sha = storage.put("c_001", b"hello")
    written = storage.abs_path("c_001", sha).stat().st_mtime_ns

    again = storage.put("c_001", b"hello")

    assert again == sha
    assert storage.abs_path("c_001", sha).stat().st_mtime_ns == written, "같은 내용을 다시 썼다"


def test_다른_회사가_같은_파일을_올리면_두_벌_저장된다() -> None:
    """**의도한 것이다**(ADR-0029 4번).

    해시를 공유하면 한쪽이 탈퇴할 때 원본을 지울지가 정해지지 않는다. 중복 제거는 저장
    최적화이고 격리는 정확성이라, 부딪히면 정확성이 이긴다.
    """
    a = storage.put("c_001", b"same-government-form")
    b = storage.put("c_002", b"same-government-form")

    assert a == b, "해시는 같아야 한다"
    assert storage.abs_path("c_001", a) != storage.abs_path("c_002", b)
    assert storage.exists("c_001", a) and storage.exists("c_002", b)


def test_한_회사를_지워도_다른_회사_것은_남는다() -> None:
    sha = storage.put("c_001", b"same-government-form")
    storage.put("c_002", b"same-government-form")

    assert storage.purge("c_001") is True

    assert storage.exists("c_001", sha) is False
    assert storage.exists("c_002", sha) is True, "남의 파일이 같이 날아갔다"


def test_company_id_로_경로를_탈출할_수_없다() -> None:
    """**격리를 경로에서 걸었으므로 여기가 방어선이다**(ADR-0029 3번)."""
    for bad in ["../../etc", "a/b", "..", "", "  ", "c/../../x", "a" * 65]:
        with pytest.raises(storage.IsolationError):
            storage.abs_path(bad, "ff" * 32)


def test_해독_텍스트는_원본_옆에_txt_로_둔다() -> None:
    """청킹 규칙을 고쳤을 때 원본을 다시 파싱하지 않으려면 이게 있어야 한다."""
    sha = storage.put("c_001", b"raw-bytes")
    storage.put_text("c_001", sha, "뽑아낸 글자")

    assert storage.read_text("c_001", sha) == "뽑아낸 글자"
    assert storage.read_text("c_002", sha) is None, "격리가 깨졌다"


def test_없는_것을_읽거나_지워도_터지지_않는다() -> None:
    assert storage.exists("c_001", "ff" * 32) is False
    assert storage.delete("c_001", "ff" * 32) is False
    assert storage.purge("c_none") is False
    assert storage.read_text("c_001", "ff" * 32) is None
