"""글자만 있는 파일 — **인코딩을 우리가 정한다**(T-0101).

이 파일이 지키는 것은 하나다. **깨진 글자가 `ok` 로 남지 않는 것.**

레포 전체에 CP949 처리가 0건이었는데 한국 사용자의 `.txt` 는 그쪽이 흔하다. UTF-8 로
그냥 디코드하면 예외가 나거나 — 더 나쁘게는 — 대체 문자로 채워진 문자열이 성공으로
기록된다. `hwp.reject_flags` 가 막는 「107자짜리 해독 성공」과 같은 계열이다.

디스크만 타고 네트워크도 DB 도 안 탄다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finnect.attach import text

# 「매출액은 1억 2천만원이다」
KO = "매출액은 1억 2천만원이다"


def test_utf8_한글을_그대로_읽는다(tmp_path: Path) -> None:
    f = tmp_path / "메모.txt"
    f.write_bytes(KO.encode("utf-8"))

    assert text.from_text(f) == KO


def test_cp949_한글이_안_깨진다(tmp_path: Path) -> None:
    """**이 테스트가 이 모듈의 존재 이유다.**

    윈도 메모장이 오래 CP949 로 저장했고 그 파일이 지금도 온다. UTF-8 만 보면
    여기서 예외가 나거나 대체 문자가 박힌다.
    """
    f = tmp_path / "메모.txt"
    f.write_bytes(KO.encode("cp949"))

    assert text.from_text(f) == KO


def test_두_인코딩이_한글에서_안_겹친다() -> None:
    """**순서가 실무에서 거의 안 걸리는 이유를 재 둔다.**

    UTF-8 한글은 3바이트고 계속바이트가 `0x80` 대인데 그 값이 CP949 의 뒷바이트로
    안 쓰인다. 거꾸로 CP949 한글의 첫 바이트는 UTF-8 에서 앞이 없는 계속바이트다.
    그래서 잘못된 인코딩으로 읽으면 **틀린 글자가 아니라 예외**가 나온다.

    이 성질에 기대는 것이 아니라 **재서 적어 두는 것이다** — 겹치는 바이트열이
    원리적으로 있으므로 `ENCODINGS` 순서는 그대로 지킨다.
    """
    samples = [KO, "다시로", "사업자등록증", "성남시 분당구", "회사소개서입니다"]

    for s in samples:
        with pytest.raises(UnicodeDecodeError):
            s.encode("utf-8").decode("cp949")
        with pytest.raises(UnicodeDecodeError):
            s.encode("cp949").decode("utf-8")


def test_bom_없는_utf16은_조용히_넘어가지_않는다(tmp_path: Path) -> None:
    """**할 수 있는 척하지 않는다.**

    BOM 이 없는 UTF-16 은 원리적으로 못 알아본다 — 추측할 재료가 없다. 메모장은
    UTF-16 을 쓸 때 항상 BOM 을 붙이므로 실무에서 오는 파일은 위 테스트가 덮는다.

    **여기서 중요한 것은 못 읽는다는 사실이 아니라 크게 실패한다는 사실이다.**
    이 입력은 UTF-8 도 CP949 도 아니라 실패로 남는다. 대체 문자로 채웠으면
    `���` 가 사실 추출까지 흘러갔을 것이다.

    다만 **모든 UTF-16 입력에 이 보장이 서는 것은 아니다** — 바이트열에 따라
    CP949 로 읽히는 것이 있을 수 있다. 그래서 BOM 을 먼저 본다.
    """
    f = tmp_path / "메모.txt"
    f.write_bytes(KO.encode("utf-16-le"))  # BOM 없음

    with pytest.raises(ValueError, match="인코딩"):
        text.from_text(f)


@pytest.mark.parametrize("enc", ["utf-8-sig", "utf-16"])
def test_bom이_본문에_안_섞인다(tmp_path: Path, enc: str) -> None:
    """메모장의 「유니코드」 저장이 여기 온다. **BOM 을 본문 첫 글자로 두면 안 된다** —
    청크 오프셋이 한 글자씩 밀리고 근거 앵커가 어긋난다(ADR-0014)."""
    f = tmp_path / "메모.txt"
    f.write_bytes(KO.encode(enc))

    assert text.from_text(f) == KO


def test_어느_인코딩도_아니면_실패한다(tmp_path: Path) -> None:
    """**조용히 대체 문자로 채우지 않는다.** 못 읽은 것은 못 읽었다고 한다."""
    # `\x80` 은 UTF-8 의 이어지는 바이트인데 앞이 없고, CP949 의 첫 바이트로도 못 쓴다.
    f = tmp_path / "깨진.txt"
    f.write_bytes(b"\x80\x80\x80\x80")

    with pytest.raises(ValueError, match="인코딩"):
        text.from_text(f)


def test_빈_파일은_빈_글자다(tmp_path: Path) -> None:
    """실패가 아니다. `extract.parse` 가 `empty` 로 가른다."""
    f = tmp_path / "빈.txt"
    f.write_bytes(b"")

    assert text.from_text(f) == ""


def test_csv가_셀을_탭으로_남긴다(tmp_path: Path) -> None:
    """**xlsx 와 같은 규약이다**(`hwp.sheets_from_xlsx`). 행이 줄, 셀이 탭.

    재무제표를 회계 프로그램에서 내보내면 이 모양으로 온다. 뭉개면 연도-항목-값
    대응이 깨져서 `매출액 24,100,000 86,400,000` 의 두 값이 어느 해인지 알 수 없다.
    """
    f = tmp_path / "손익.csv"
    f.write_text("항목,2024,2025\n매출액,24100000,86400000\n", encoding="utf-8")

    assert text.from_csv(f) == "항목\t2024\t2025\n매출액\t24100000\t86400000"


def test_csv_인용부호_안의_쉼표는_한_칸이다(tmp_path: Path) -> None:
    """직접 쪼개면 여기서 칸이 하나 늘어 열이 통째로 밀린다."""
    f = tmp_path / "거래처.csv"
    f.write_text('업체,주소\n다시로,"성남시 분당구, 3층"\n', encoding="utf-8")

    assert text.from_csv(f) == "업체\t주소\n다시로\t성남시 분당구, 3층"


def test_csv도_cp949를_읽는다(tmp_path: Path) -> None:
    """엑셀이 「CSV(쉼표로 분리)」로 저장하면 한국어 윈도에서 CP949 다."""
    f = tmp_path / "손익.csv"
    f.write_bytes("항목,값\n매출액,120000000\n".encode("cp949"))

    assert text.from_csv(f) == "항목\t값\n매출액\t120000000"


def test_csv_빈_줄은_버린다(tmp_path: Path) -> None:
    """엑셀이 끝에 빈 줄을 남긴다. 탭만 있는 줄이 조각에 섞이면 안 된다."""
    f = tmp_path / "손익.csv"
    f.write_text("항목,값\n\n매출액,120000000\n\n", encoding="utf-8")

    assert text.from_csv(f) == "항목\t값\n매출액\t120000000"
