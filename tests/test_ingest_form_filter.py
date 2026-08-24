"""첨부에 채울 양식이 없어 보이는 공고를 적재에서 뺀다(2026-08-24 · T-0165).

기업마당은 **첨부 목록이 목록 API 에 같이 온다**(K-Startup 과 다른 점이다). 그래서
파일을 안 받고도 파일명만으로 이 판정이 서고, **요청이 하나도 안 는다.**

2026-08-24 실측 — 중분류 솎기를 통과한 932건에 대고 잰 값이다.

    첨부가 있다(공고문 말고)        714
    신청|계획                       487
    +양식|서식                      551
    +서류                           566   ← 이 표가 남기는 것
    +서약서                         567
    +붙임                           572
    +내용 모를 zip 전부             588

**파일명만 보는 판정이라 확실하지 않다.** 목적이 코퍼스를 줄이는 것이라
**모르는 쪽을 버린다** — 아래 «모르면 버린다» 참조.
"""

from __future__ import annotations

import httpx
import pytest

from finnect.ingest.bizinfo import BizinfoAdapter, has_form


def _biz(**kw: object) -> BizinfoAdapter:
    return BizinfoAdapter(httpx.Client(), api_key="테스트키", **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name",
    [
        "[서식1] 사업계획서.hwp",
        "2026년 지원사업 신청서.hwp",
        "제출서류+양식+일체.zip",
        "AIoT융합부품 성능검증시스템 고도화사업_기업지원서류.hwp",
        "붙임2. 서식 모음.hwpx",
    ],
)
def test_양식으로_보이면_남긴다(name: str) -> None:
    assert has_form(name)


@pytest.mark.parametrize(
    "name",
    [
        "★2026년도_M&A_활성화_지원사업_공고.pdf",
        "인천지역기업 신용평가 지원사업 공고문.hwp",
        "붙임 1. 2026년 창업경진대회 포스터.pdf",
        "친환경인증선박 보급지원사업 시행지침 260713 .hwpx",
        "3. 2026 미스터리쇼퍼 포스터.png",
    ],
)
def test_공고문_포스터_지침은_뺀다(name: str) -> None:
    """실제로 버려진 것들이다. 채울 칸이 없는 파일이다."""
    assert not has_form(name)


class Test모르면_버린다:
    """**코퍼스를 줄이는 것이 이 필터의 목적이다.**

    2026-08-24 결정 — `.zip` 을 무조건 살리던 것을 뺐다(588 → 566). 그 22건에
    `2026년…지원사업 공고.zip` 처럼 이름이 이미 「공고문을 쌌다」고 말하는 것이
    섞여 있었다. **대가는 그중 일부에 진짜 양식이 있을 수 있다는 것이고, 공고가
    API 에서 사라지면 되찾을 수 없다.**
    """

    def test_이름이_아무것도_안_말하는_zip은_버린다(self) -> None:
        assert not has_form("첨부파일.zip")
        assert not has_form("2.붙임자료.zip")
        assert not has_form("2026년 EU CBAM 대응 기업지원 컨설팅 2차 모음.zip")

    def test_낱말이_있는_zip은_확장자와_무관하게_남는다(self) -> None:
        """**`.zip` 이라서 버리는 게 아니다.** 판정은 낱말이 한다."""
        assert has_form("제출서류+양식+일체.zip")
        assert has_form("[붙임] 신청서 서식.zip")

    def test_첨부가_아예_없으면_뺀다(self) -> None:
        """공고문뿐인 것이다. 실측 932건 중 218건 — 채울 것이 없다."""
        assert not has_form("")
        assert not has_form(None)


def test_공고문_이름은_안_본다() -> None:
    """**`printFileNm` 은 1,538건 전부에 붙는다**(CLAUDE.md 함정).

    같이 보면 공고문 이름에 우연히 든 낱말로 통과해 버린다 — `keep()` 이 `fileNm`
    만 넘기는지 여기서 잠근다.
    """
    a = _biz()
    item = {
        "pblancId": "PBLN_1",
        "pldirSportRealmMlsfcCodeNm": "사업화지원",
        "fileNm": "",  # 진짜 첨부는 없다
        "printFileNm": "2026년 창업 신청 안내 공고문.hwp",  # '신청' 이 여기 있다
    }
    assert not a.keep(item), "공고문 이름으로 통과하면 안 된다"


class Test두_필터가_같이_걸린다:
    def test_중분류에_걸리면_양식이_있어도_뺀다(self) -> None:
        a = _biz()
        assert not a.keep(
            {"pblancId": "P", "pldirSportRealmMlsfcCodeNm": "융자", "fileNm": "신청서.hwp"}
        )

    def test_중분류를_넘어도_양식이_없으면_뺀다(self) -> None:
        a = _biz()
        assert not a.keep(
            {"pblancId": "P", "pldirSportRealmMlsfcCodeNm": "사업화지원", "fileNm": "포스터.pdf"}
        )

    def test_둘_다_넘으면_남는다(self) -> None:
        a = _biz()
        assert a.keep(
            {"pblancId": "P", "pldirSportRealmMlsfcCodeNm": "사업화지원", "fileNm": "신청서.hwp"}
        )

    def test_끄면_전량이다(self) -> None:
        """`--full` 이 둘을 같이 끈다. `docs/dataset.md` 의 정본 절차가 그것을 쓴다."""
        a = _biz(skip_mlsfc=False, require_form=False)
        assert a.keep(
            {"pblancId": "P", "pldirSportRealmMlsfcCodeNm": "융자", "fileNm": "포스터.pdf"}
        )


class Test표본:
    """공고번호를 나눈 나머지로 더 좁힌다(2026-08-24).

    **양식 필터 뒤에 선다.** 앞에 두면 「낱말로 몇 건이 통과했나」를 못 세고,
    나눗수를 바꿀 때마다 그 수가 같이 흔들려 무엇이 줄인 건지 알 수 없다.

    2026-08-24 실측 — 기업마당 566 · K-Startup(낱말통과) 127 기준.

        나눗수   기업마당   K-Startup   합계
             1        566         127    693
             5        102          27    129
            10         55          17     72   ← 100건 아래
    """

    def _item(self) -> dict[str, str]:
        return {
            "pblancId": "PBLN_000000000103611",
            "pldirSportRealmMlsfcCodeNm": "사업화지원",
            "fileNm": "[서식1] 사업계획서.hwp",
        }

    def test_기본은_전부_남긴다(self) -> None:
        """**표본을 끄는 값이 `None` 이 아니라 1 이다**(`dataset/sample.py` 의 계약)."""
        assert _biz().keep(self._item())
        assert _biz(sample=1).keep(self._item())

    def test_멱등하다(self) -> None:
        """무작위 시드를 안 쓴다. 몇 번을 돌려도 같은 집합이 선다."""
        a = _biz(sample=10)
        first = [a.keep({**self._item(), "pblancId": f"PBLN_{i:012d}"}) for i in range(60)]
        second = [a.keep({**self._item(), "pblancId": f"PBLN_{i:012d}"}) for i in range(60)]
        assert first == second

    def test_대략_나눗수만큼_줄인다(self) -> None:
        """기업마당 공고번호는 숫자가 아니라 sha256 경로를 탄다 — 고르게 퍼지는지 본다."""
        a = _biz(sample=10)
        kept = sum(a.keep({**self._item(), "pblancId": f"PBLN_{i:012d}"}) for i in range(1000))
        assert 60 <= kept <= 140, f"1,000건에서 {kept}건 — 10%에서 너무 벗어난다"

    def test_양식이_없으면_표본을_보기도_전에_빠진다(self) -> None:
        a = _biz(sample=1)
        assert not a.keep({**self._item(), "fileNm": "포스터.pdf"})
