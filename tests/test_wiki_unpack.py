"""묶음을 푼다 — T-0102.

**첨부와 다른 결정이다.** 공고 첨부는 목록만 읽고 안 푼다(ADR-0022 4번) — 166건 안에
799개가 있다는 것만 세어 두고 멈췄다. 사용자 파일은 푼다. 이유가 둘이다.

1. **사용자가 묶어서 던진다.** "가진 파일을 통째로 던지면" 이 제품의 첫 문장인데,
   메일로 받은 제출서류 한 벌은 대개 zip 한 개다. 안 풀면 그 사람의 위키가 빈다.
2. **안쪽 파일이 제 행을 가져야 근거가 산다**(ADR-0014). 청크가 어느 파일에서 나왔는지
   나중에 붙일 수 없다.

디스크만 타고 DB 는 안 탄다 — 행을 만드는 것은 `wiki/service.py` 다.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from finnect.wiki import unpack


def _zip(path: Path, names: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in names.items():
            z.writestr(name, data)
    return path


def _bytes(names: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in names.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_안쪽_파일을_이름과_바이트로_돌려준다(tmp_path: Path) -> None:
    data = _bytes({"별첨1_사업계획서.hwp": b"x" * 10, "별첨2_안내.pdf": b"y" * 20})

    got = unpack.expand(data)

    assert [m.name for m in got.members] == ["별첨1_사업계획서.hwp", "별첨2_안내.pdf"]
    assert got.members[0].data == b"x" * 10
    assert got.skipped == 0


def test_묶음_안의_경로를_이름에_남긴다() -> None:
    """**`별첨1.hwp` 가 아니라 `제출서류/별첨1.hwp` 다.**

    사용자가 자기 묶음에서 그 파일을 찾을 수 있어야 한다. 이름만 남기면 같은 이름이
    폴더 둘에 있을 때 화면에 같은 줄이 두 번 뜬다.
    """
    data = _bytes({"제출서류/별첨1.hwp": b"x", "참고/별첨1.hwp": b"y"})

    got = unpack.expand(data)

    assert [m.name for m in got.members] == ["제출서류/별첨1.hwp", "참고/별첨1.hwp"]


def test_묶음_부스러기를_세고_버린다() -> None:
    """**조용히 버리지 않는다.** 맥이 만든 `__MACOSX/` 와 숨김 파일이 실제로 온다."""
    data = _bytes(
        {
            "사업계획서.hwp": b"x",
            "__MACOSX/._사업계획서.hwp": b"junk",
            ".DS_Store": b"junk",
            "폴더/.gitkeep": b"",
        }
    )

    got = unpack.expand(data)

    assert [m.name for m in got.members] == ["사업계획서.hwp"]
    assert got.skipped == 3


def test_중첩_묶음은_안_푼다() -> None:
    """**깊이 1이다**(T-0102 결정 3).

    안쪽 zip 은 행으로 남아서 있다는 사실은 남지만 풀리지 않는다. 재귀를 열면
    깊이·순환·총합 계산이 전부 다시 필요한데 그걸 정할 실측이 없다.
    """
    inner = _bytes({"깊은곳.hwp": b"z"})
    data = _bytes({"겉.hwp": b"x", "안쪽묶음.zip": inner})

    got = unpack.expand(data)

    names = [m.name for m in got.members]
    assert names == ["겉.hwp", "안쪽묶음.zip"]
    # 안쪽 zip 은 바이트 그대로다. 풀린 흔적이 없다
    assert got.members[1].data == inner
    assert "깊은곳.hwp" not in names


def test_개수_상한에서_멈추고_센다() -> None:
    """**조용히 자르지 않는다.** 몇 개를 못 풀었는지 말한다."""
    data = _bytes({f"파일{i}.hwp": b"x" for i in range(10)})

    got = unpack.expand(data, max_files=4)

    assert len(got.members) == 4
    assert got.dropped == 6
    assert got.limit_hit


def test_총합_상한에서_멈추고_센다() -> None:
    """**개별 상한만으로는 못 막는다.** 50MB 묶음 하나가 풀리면 수십 GB 가 될 수 있다."""
    data = _bytes({f"파일{i}.hwp": b"x" * 1000 for i in range(10)})

    got = unpack.expand(data, max_total_bytes=2500)

    assert len(got.members) == 2  # 1000 + 1000 까지. 셋째가 상한을 넘는다
    assert got.dropped == 8
    assert got.limit_hit


def test_개별_상한을_넘는_것만_버린다() -> None:
    """큰 파일 하나 때문에 나머지가 날아가면 안 된다. **그 파일만 뺀다.**"""
    data = _bytes({"작다.hwp": b"x" * 10, "크다.pdf": b"y" * 5000, "작다2.hwp": b"z" * 10})

    got = unpack.expand(data, max_member_bytes=100)

    assert [m.name for m in got.members] == ["작다.hwp", "작다2.hwp"]
    assert got.dropped == 1
    assert not got.limit_hit  # 총합·개수 상한을 친 것이 아니다


def test_빈_묶음도_실패가_아니다() -> None:
    """풀 것이 없는 것과 못 푸는 것은 다르다."""
    got = unpack.expand(_bytes({}))

    assert got.members == []
    assert got.skipped == 0


def test_깨진_묶음은_예외다(tmp_path: Path) -> None:
    """**조용히 빈 목록을 주지 않는다.** 부르는 쪽이 실패로 남긴다."""
    with pytest.raises(unpack.BadArchive):
        unpack.expand(b"PK\x03\x04" + b"\xff" * 64)


def test_묶음인지_바이트로_판정한다(tmp_path: Path) -> None:
    """이름이 `.zip` 이 아니어도 묶음이면 푼다. **파일명은 거짓말을 한다.**"""
    assert unpack.is_archive(_bytes({"안.hwp": b"x"}))
    assert not unpack.is_archive(b"%PDF-1.7\n")
    # HWPX·DOCX 도 ZIP 이다. **저건 묶음이 아니라 문서다** — 풀면 XML 조각이 쏟아진다
    assert not unpack.is_archive(_bytes({"Contents/section0.xml": b"<hml/>"}))
    assert not unpack.is_archive(_bytes({"word/document.xml": b"<w/>"}))
