"""내려받기 방어 — **HTTP 200 이 성공이 아니다.**

기업마당은 오류를 200 + HTML 로 준다. 목록 API 가 실패를 200 으로 주는 것과 같은 함정이고,
안 거르면 3KB 짜리 오류 페이지가 hwp 로 저장돼 '파서 실패'로 둔갑한다.
네트워크도 DB 도 안 탄다.
"""

from __future__ import annotations

import pytest

from finnect.attach import download


@pytest.mark.parametrize(
    ("data", "ctype"),
    [
        (b"<!DOCTYPE html><html>...", "text/html;charset=utf-8"),
        (b"\n  <html><body>\xec\x98\xa4\xeb\xa5\x98", None),
        (b"", "application/x-download"),  # 0바이트도 파일이 아니다
    ],
)
def test_파일이_아닌_것을_가려낸다(data: bytes, ctype: str | None) -> None:
    assert download.is_html(data, ctype) is True


@pytest.mark.parametrize(
    "head",
    [b"%PDF-1.7\n", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"],
)
def test_진짜_파일은_통과시킨다(head: bytes) -> None:
    # 기업마당은 정상 파일에도 application/x-download 를 준다. content-type 만 믿지 않는다.
    assert download.is_html(head + b"\x00" * 64, "application/x-download") is False


def test_파일명은_헤더에서_온다() -> None:
    """URL 에는 파일명이 없다. Content-Disposition 이 유일한 출처다."""
    got = download.filename_of(
        "attachment; filename=2. %EC%82%AC%EC%97%85%EA%B3%84%ED%9A%8D%EC%84%9C.hwp"
    )

    assert got == "2. 사업계획서.hwp"


def test_rfc5987_형식도_받는다() -> None:
    got = download.filename_of("attachment; filename*=UTF-8''%EA%B3%B5%EA%B3%A0%EB%AC%B8.pdf")

    assert got == "공고문.pdf"


def test_헤더가_없으면_없다고_한다() -> None:
    assert download.filename_of(None) is None
    assert download.filename_of("attachment") is None


def test_기업마당에는_referer를_단다() -> None:
    """그냥 UA 로는 403 이다. 상대가 브라우저를 기대한다."""
    h = download.headers_for("bizinfo")

    assert "Referer" in h
    assert "Mozilla" in h["User-Agent"]
