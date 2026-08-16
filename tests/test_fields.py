"""필드 설명 — 공식 문서에서 온 것만 담겨 있는지.

**이 모듈의 위험은 하나뿐이다. 그럴듯한 추측이 섞여 들어가는 것.** 필드 이름이
`pldirSportRealmMlsfcCodeNm` 이면 '지원분야 중분류'라고 적고 싶어지는데, 문서에 없으면
그건 추측이다. 그 추측은 L1 추출 스키마까지 따라간다.
"""

from __future__ import annotations

from finnect import fields
from finnect.models import BizinfoNotice, KstartupNotice

#: 2026-08-16 공식 문서 응답표에 없던 기업마당 필드. 늘어나면 문서를 다시 봤다는 뜻이다.
BIZINFO_UNDOCUMENTED = {"pldirSportRealmMlsfcCodeNm", "updtPnttm"}


class Test기업마당:
    def test_문서에_있는_20개만_담는다(self) -> None:
        assert set(fields.BIZINFO) == BizinfoNotice.API_FIELDS - BIZINFO_UNDOCUMENTED
        assert len(fields.BIZINFO) == 20

    def test_문서에_없는_필드는_None_이다(self) -> None:
        """빈 문자열이 아니라 None 이어야 화면이 '문서에 없음'을 구분해 적는다."""
        for name in BIZINFO_UNDOCUMENTED:
            assert fields.describe("bizinfo", name) is None

    def test_설명이_필드_이름의_복사본이_아니다(self) -> None:
        for name, desc in fields.BIZINFO.items():
            assert desc.strip()
            assert desc != name

    def test_실제_응답_이름을_쓴다(self) -> None:
        """문서는 hashTags 라고 쓰지만 실제 응답은 hashtags 다. 우리는 받는 쪽을 따른다."""
        assert "hashtags" in fields.BIZINFO
        assert "hashTags" not in fields.BIZINFO


#: 활용가이드 v2.0 의 getAnnouncementInformation01 응답 표에 없던 필드.
#: biz_aply_url 은 같은 문서의 XML 예시에만 나오고 표에는 없다. id 는 어디에도 없다.
KSTARTUP_UNDOCUMENTED = {"biz_aply_url", "id"}


class TestKStartup:
    def test_문서에_있는_28개만_담는다(self) -> None:
        assert set(fields.KSTARTUP) == KstartupNotice.API_FIELDS - KSTARTUP_UNDOCUMENTED
        assert len(fields.KSTARTUP) == 28

    def test_문서에_없는_필드는_None_이다(self) -> None:
        for name in KSTARTUP_UNDOCUMENTED:
            assert fields.describe("kstartup", name) is None

    def test_실제_응답_이름을_쓴다(self) -> None:
        """문서 표기와 실제 응답이 어긋나는 곳이 둘이다. 받는 쪽을 따른다."""
        assert "aply_excl_trgt_ctnt" in fields.KSTARTUP  # 문서는 aply_exclt_trgt_ctnt
        assert "aply_exclt_trgt_ctnt" not in fields.KSTARTUP
        assert "rcrt_prgs_yn" in fields.KSTARTUP  # 문서는 Rcrt_prgs_yn
        assert "Rcrt_prgs_yn" not in fields.KSTARTUP

    def test_설명_열이_뒤바뀐_두_행을_바로잡았다(self) -> None:
        """문서 표의 '항목설명' 열이 이 두 행에서 서로 바뀌어 있다. 항목명(국문)이 맞다."""
        assert fields.KSTARTUP["biz_gdnc_url"] == "사업 안내 URL"
        assert fields.KSTARTUP["prch_cnpl_no"] == "담당자 연락처"


class Test우리_컬럼:
    def test_출처와_무관하게_설명이_있다(self) -> None:
        for source in ("bizinfo", "kstartup"):
            assert fields.describe(source, "content_hash")
            assert fields.describe(source, "derived_apply_end")


class Test적용률:
    def test_문서에_있는_수와_전체를_센다(self) -> None:
        assert fields.coverage("bizinfo", sorted(BizinfoNotice.API_FIELDS)) == (20, 22)
        assert fields.coverage("kstartup", sorted(KstartupNotice.API_FIELDS)) == (28, 30)

    def test_모르는_출처는_0개(self) -> None:
        assert fields.coverage("onticheongnyeon", ["a", "b"]) == (0, 2)


class Test출처_표기:
    def test_두_출처_다_어디서_옮겼는지_적혀_있다(self) -> None:
        for source in ("bizinfo", "kstartup"):
            assert fields.DOCS[source].label.strip()

    def test_기업마당은_링크가_있고_K_Startup_은_문서_파일이다(self) -> None:
        """활용가이드는 내려받은 파일이라 걸 링크가 없다. 없는 링크를 지어내지 않는다."""
        assert fields.DOCS["bizinfo"].url
        assert fields.DOCS["kstartup"].url is None
