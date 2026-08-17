"""구간 분할과 칸 추출(plan/11 T-0035·T-0037).

**모르는 것을 아는 척하지 않는 것**이 이 모듈의 핵심이다. 서술형 양식은 공고문의 절과
생김새가 같아 규칙이 네 번 실패했고, 그래서 여기서는 **칸 채우기만** 판정한다.
"""

from __future__ import annotations

from finnect.extract import fields, segment

FORM = "\n".join(
    [
        "2026년 지원사업 모집 공고",
        "1. 사업개요",
        "2. 신청자격",
        "[서식1] 지원 신청서",
        "기업명\t(주)가나다\t대표자\t홍길동",
        "사업자등록번호\t000-00-00000",
        "업종\t제조업",
        "연락처\t",
        "매출액\t백만원",
        "위와 같이 신청합니다.",
        "2026년 월 일",
        "신청인 (인)",
        "OO시장 귀하",
        "[서식2] 개인정보 동의서",
        "1. 수집·이용 목적",
    ]
)


class Test구간_분할:
    def test_표지로_자른다(self) -> None:
        segs = segment.split(FORM)

        assert [s.title for s in segs] == ["공고문", "서식 1 지원 신청서", "서식 2 개인정보 동의서"]

    def test_구간이_원문_오프셋을_들고_있다(self) -> None:
        """**나중에 붙일 수 없다**(ADR-0014). 잘라내면 그 구간이 그대로 나와야 한다."""
        segs = segment.split(FORM)

        for s in segs:
            assert FORM[s.start : s.end] == s.text

    def test_표지가_없으면_통째로_한_구간이다(self) -> None:
        """빈 목록을 주지 않는다. '안 잘렸다'와 '내용이 없다'는 다른 사실이다."""
        segs = segment.split("공고문만 있는 글")

        assert len(segs) == 1
        assert segs[0].title == "공고문"

    def test_제출서류_목록은_표지가_아니다(self) -> None:
        """`붙임 1. …신청서 1부.` 는 자를 자리가 아니라 서류 목록이다."""
        text = "제출서류\n붙임 1. 온라인 입점 지원사업 신청서 1부.\n붙임 2. 사진 1부.\n"

        assert len(segment.split(text)) == 1


class Test칸_추출:
    def test_신청서는_칸_채우기로_갈린다(self) -> None:
        body = segment.split(FORM)[1].text

        assert fields.is_fields(body)
        assert fields.labels(body)[:3] == ["기업명", "사업자등록번호", "업종"]

    def test_공고문은_칸_채우기가_아니다(self) -> None:
        """**놓치는 쪽이 낫다.** 잘못 잡으면 공고문 표가 '채울 칸'으로 뜬다."""
        head = segment.split(FORM)[0].text

        assert not fields.is_fields(head)

    def test_신호만_있고_표가_없으면_아니다(self) -> None:
        text = "위와 같이 신청합니다.\n신청인 (인)\nOO시장 귀하\n"

        assert not fields.is_fields(text)

    def test_체크상자와_숫자는_라벨이_아니다(self) -> None:
        text = "□ 중소기업\t\n2026. 8. 1.\t\n기업명\t값\n"

        assert fields.labels(text) == ["기업명"]
