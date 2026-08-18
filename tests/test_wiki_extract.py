"""스텁 추출기와 사실 표 — plan/12 T-0045 · ADR-0031.

**이 파일이 스텁의 정직함을 지킨다.** 스텁이 돌려주는 사실은 지어낸 값이 아니라 코퍼스에
실제로 적힌 문장이어야 하는데, 그걸 보장하는 방법은 **앵커를 원문에서 직접 찾아 보는
것뿐이다.** 하나라도 못 찾으면 그 사실은 근거가 없고, 근거 없는 값은 위키에 서면 안 된다
(ADR-0014).

`test_모든_앵커가_원문에_있다` 가 파일을 실제로 해독하므로 느리다. OCR 이 필요한 둘은
`--ocr` 를 붙였을 때만 본다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from finnect.attach import extract as attach_extract
from finnect.attach import ocr
from finnect.config import settings
from finnect.wiki import topics
from finnect.wiki.extract import FileView, StubExtractor, UnknownFile, get_extractor

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"
FACTS = FIXTURES / "facts.json"

#: OCR 이 있어야 글자가 나오는 것들. 나머지 다섯은 파서만으로 읽힌다.
NEEDS_OCR = {"사업자등록증_스캔.pdf", "현장사진_파일럿매장.jpg"}


def _squash(s: str) -> str:
    return "".join(s.split())


@pytest.fixture(scope="module")
def table() -> dict:
    if not FACTS.exists():
        pytest.skip("사실 표가 없다")
    return json.loads(FACTS.read_text(encoding="utf-8"))


def _entries(table: dict) -> list[dict]:
    return table["files"]


# ─────────────────────────────────────────────────────────────────
# 표가 코퍼스와 맞는가
# ─────────────────────────────────────────────────────────────────


def test_표가_코퍼스_일곱_건을_전부_덮는다(table: dict):
    names = {e["filename"] for e in _entries(table)}
    on_disk = {p.name for p in FIXTURES.iterdir() if p.suffix.lower() not in {".md", ".json"}}
    assert names == on_disk


def test_sha256_이_실제_파일과_같다(table: dict):
    """**화이트리스트가 해시라 여기가 어긋나면 스텁이 통째로 안 돈다.**"""
    import hashlib

    for e in _entries(table):
        actual = hashlib.sha256((FIXTURES / e["filename"]).read_bytes()).hexdigest()
        assert actual == e["sha256"], e["filename"]


def test_모든_topic_이_온톨로지_안에_있다(table: dict):
    """**자유 생성 금지**(구상도 ④). 밖의 라벨이 있으면 통째로 검토 대기에 쌓인다."""
    for e in _entries(table):
        for f in e["facts"]:
            assert f["topic"] in topics.TOPICS, f"{e['filename']}: {f['topic']}"


def test_정형_사실의_항목_이름이_전부_별칭_표에_있다(table: dict):
    """딱 하나 예외가 `업력` 이고, **그건 일부러다** — 문서에 박힌 업력은 믿으면 안 된다."""
    unknown = {
        f["key"]
        for e in _entries(table)
        for f in e["facts"]
        if f["kind"] == "slot" and topics.slot_of(f.get("key")) is None
    }
    assert unknown == {"업력"}


@pytest.mark.parametrize("entry_name", [p.name for p in sorted(FIXTURES.iterdir())
                                        if p.suffix.lower() not in {".md", ".json"}])
def test_모든_앵커가_원문에_있다(table: dict, entry_name: str, request: pytest.FixtureRequest):
    """**스텁이 지어낸 값을 돌려주지 않는다는 것을 여기서만 증명할 수 있다.**

    앵커는 근거 청크를 찾는 열쇠라, 원문에 없으면 그 사실은 위키에 못 선다.
    """
    if entry_name in NEEDS_OCR and not ocr.available():
        pytest.skip("OCR 이 없다 — uv sync --group ocr")

    entry = next(e for e in _entries(table) if e["filename"] == entry_name)
    parsed = attach_extract.parse(
        FIXTURES / entry_name,
        entry_name,
        allowed=settings.wiki_formats,
        use_ocr=entry_name in NEEDS_OCR,
    )
    body = _squash(parsed.text or "")
    missing = [f["anchor"] for f in entry["facts"] if _squash(f["anchor"]) not in body]
    assert not missing, f"{entry_name}: 원문에 없는 앵커 {missing}"


def test_픽스처가_심어_둔_함정이_표에_들어_있다(table: dict):
    """코퍼스 README 가 기대값으로 적어 둔 것들. **빠지면 T-0046 이 검증되지 않는다.**"""
    facts = [f for e in _entries(table) for f in e["facts"]]

    heads = sorted(f["value"] for f in facts if topics.slot_of(f.get("key")) == "headcount")
    assert heads == ["10", "15", "7", "8"], "직원 수 넷이 다 있어야 한다"

    seed = sorted({f["value"] for f in facts if f.get("qualifier") == "시드"})
    assert seed == ["280000000", "300000000"], "시드 3억과 2.8억이 둘 다 있어야 한다"

    programs = {f["qualifier"] for f in facts if topics.slot_of(f.get("key")) == "gov_program"}
    assert len(programs) == 3, "정부지원 수혜 이력 셋 — HWPX 에만 있다"

    retention = [f for f in facts if f.get("fact_key") == "pilot_retention_34_51"]
    assert len(retention) == 4, "재구매율이 네 문서에 있어야 한다"


# ─────────────────────────────────────────────────────────────────
# 못 쓰게 막는가
# ─────────────────────────────────────────────────────────────────


def test_픽스처_밖의_파일은_거부한다():
    """**조용히 비면 진짜 사용자 파일에 가짜가 섞이거나 아무것도 안 나온 게 정상처럼 보인다.**"""
    stub = StubExtractor()
    view = FileView(sha256="0" * 64, filename="남의_사업계획서.hwp", chunks=(( 0, "무엇이든"),))
    with pytest.raises(UnknownFile, match="스텁이 모르는 파일"):
        stub.extract(view)


def test_표가_없으면_아예_안_돈다(tmp_path: Path):
    """레포 밖(배포본)에는 이 표가 없다. 없는 채로 도는 것보다 멈추는 편이 낫다."""
    stub = StubExtractor(facts_path=tmp_path / "없음.json")
    with pytest.raises(UnknownFile, match="스텁 사실 표가 없어요"):
        stub.extract(FileView(sha256="0" * 64, filename="x", chunks=()))


def test_llm_을_고르면_없다고_말한다(monkeypatch: pytest.MonkeyPatch):
    """**없는 것을 있는 척하지 않는다.** 제공자가 정해지면 여기 한 줄이 늘어난다."""
    monkeypatch.setattr(settings, "wiki_extractor", "llm")
    with pytest.raises(NotImplementedError, match="아직 없어요"):
        get_extractor()


def test_아는_파일은_사실을_돌려준다(table: dict):
    stub = StubExtractor()
    entry = next(e for e in _entries(table) if e["filename"].endswith(".docx"))
    facts = stub.extract(FileView(sha256=entry["sha256"], filename=entry["filename"], chunks=()))
    assert len(facts) == len(entry["facts"])
    assert all(f.anchor for f in facts)
