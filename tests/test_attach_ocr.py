"""OCR — ADR-0030.

**해상도가 조용한 실패를 만든다.** PDF 경로는 300dpi 로 렌더하는데 그림 경로가 원본
크기를 그대로 넣으면, 같은 글자를 PDF 에서는 읽고 사진에서는 못 읽는다. 실제로
1400x1050 사진에서 글자 하나(`Ⅲ`)만 읽고 `ok` 로 기록됐다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finnect.attach import ocr

FIXTURE = Path(__file__).parent / "fixtures" / "wiki" / "현장사진_파일럿매장.jpg"


def _img(w: int, h: int):  # noqa: ANN202
    PIL = pytest.importorskip("PIL.Image")
    return PIL.new("RGB", (w, h), (255, 255, 255))


def test_작은_그림은_PDF_경로와_같은_해상도까지_키운다() -> None:
    out = ocr.upscale(_img(1400, 1050))

    assert max(out.size) >= ocr.MIN_LONG_SIDE
    assert out.width / out.height == pytest.approx(1400 / 1050), "가로세로 비가 바뀌었다"


def test_이미_큰_그림은_그대로_둔다() -> None:
    src = _img(3000, 2000)

    assert ocr.upscale(src) is src, "쓸데없이 늘리면 인식만 느려진다"


def test_확대에_상한이_있다() -> None:
    """아이콘만 한 그림을 아무리 늘려도 없던 글자가 생기지는 않는다."""
    out = ocr.upscale(_img(100, 100))

    assert max(out.size) <= 100 * ocr.MAX_SCALE


@pytest.mark.skipif(not ocr.available(), reason="rapidocr 가 없다 (uv sync --group ocr)")
def test_사진_속_글자를_읽는다() -> None:
    """확대 전에는 `Ⅲ` 한 글자였다."""
    if not FIXTURE.exists():
        pytest.skip("픽스처가 없다")

    text = ocr.from_image(FIXTURE)

    assert "2025.07.14" in text
    assert "자체QR부착구간" in text.replace(" ", "")
