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


class Test구조로_서류_제목_찾기:
    """표지 낱말이 없어도 **모양이 남아 있다** (ADR-0061 결정 1).

    한글 양식은 서류 제목을 표 하나로 감싼다 — 테두리와 음영을 주려고 그렇게 쓴다.
    텍스트로 납작하게 만들면 그 모양이 사라져서 `1. …기본지원서` 가 평범한 한 줄이
    되고, 표지 정규식이 못 잡는다.

    **여기서 파일을 안 연다.** `forms` 가 뽑아 준 글자만 받는다 — 열면 JVM 이
    딸려 오고 이 모듈은 읽기 경로에 있다(`tests/test_forms.py` 와 같은 규율).

    실측(2026-08-23 · hwp 세 파일 · 서류 16장): 표지 규칙 0장 · 이 규칙 15장.
    """

    def test_작은_표의_셀이_서류_이름으로_끝나면_제목이다(self) -> None:
        """경남TP 실측. 표0 이 칸 셋이고 그 하나가 제목이다."""
        tables = [
            ["", "2026. 00. 00.(00) 작성자: 000 직함", "1. 2026년 0차 타깃마케팅(0000) 기본지원서"]
        ]

        assert segment.doc_titles(tables, []) == ["1. 2026년 0차 타깃마케팅(0000) 기본지원서"]

    def test_큰_표의_첫_칸은_제목이_아니다(self) -> None:
        """경남TP 표7 이 44칸이고 첫 칸이 `신청자격 적정성 확인서` 다.

        **놓치는 쪽을 고른다.** 본문 표의 라벨을 제목으로 읽으면 서류 하나가
        여러 조각으로 갈리고, 그건 안 자르는 것보다 나쁘다.
        """
        tables = [["신청자격 적정성 확인서", *[f"칸{i}" for i in range(43)]]]

        assert segment.doc_titles(tables, []) == []

    def test_표_밖_문단도_본다(self) -> None:
        """경남TP `사용인감계 (지원기업)` 는 표가 아니라 문단이다."""
        assert segment.doc_titles([], ["사용인감계 (지원기업)"]) == ["사용인감계 (지원기업)"]

    def test_괄호_주석이_붙어도_잡는다(self) -> None:
        """`동의서 (지원기업)` 처럼 뒤에 대상이 붙는 양식이 실제로 있다."""
        tables = [["기업정보의 수집·이용·제공 및 활용 동의서 (지원기업)"]]

        assert segment.doc_titles(tables, []) == [
            "기업정보의 수집·이용·제공 및 활용 동의서 (지원기업)"
        ]

    def test_서류_이름으로_안_끝나면_아니다(self) -> None:
        """경기도 반려동물 표10~12 가 지시문 한 칸짜리 표다. **작은 표이지만 제목이 아니다.**"""
        tables = [["※ 공모전 주제(키워드)와 제품·서비스가 직접 연결되는 근거 등"]]

        assert segment.doc_titles(tables, []) == []

    def test_긴_줄은_제목이_아니다(self) -> None:
        """작은 표에 본문이 통째로 든 것이 있다(경남TP 표5 의 둘째 칸)."""
        long = "본인 및 당사는 아래 사항을 준수하겠습니다. " * 5 + "서약서"

        assert segment.doc_titles([[long]], []) == []

    def test_같은_제목은_한_번만_낸다(self) -> None:
        assert segment.doc_titles([["참가 신청서"], ["참가 신청서"]], []) == ["참가 신청서"]

    def test_줄머리_기호가_붙으면_목록_항목이다(self) -> None:
        """벤처나라 실측(hwp 30개 육안). 제출서류 안내가 문단으로 늘어선다.

        **표는 「작은 표」 조건이 걸렀는데 문단에는 아무 조건이 없었다.** 넷이
        서류 제목으로 잡혔고 그 자리에서 자르면 안내 문단 하나가 서류 한 벌이 된다.
        """
        paras = [
            "\xad (필수) 지정 신청서(온라인 신청서식)",
            "\xad (필수) 법정 및 품질 인증제품 납품확약서(온라인 신청 시 서식 제공)",
            "< 참고 > ① 추천 관련 문의처, ② 지정신청 제출서류",
            "※ 아래 서식으로 계획서 작성",
            # 한글 이응이 불릿으로 흔히 쓰인다 (`[붙임 2] 완료 보고서…` 실측)
            "ㅇ 참여기업 각서(별지 제3호 서식)",
        ]

        assert segment.doc_titles([], paras) == []

    def test_제출서류는_서류_이름이_아니다(self) -> None:
        """중동 수출물류비 실측(hwpx 육안). `6. 신청방법 및 제출서류` 는 **공고문의 절**이다.

        「내야 할 서류들」을 가리키는 말이라 서류 한 벌의 이름이 아니다. 대가로
        `…신청시 제출서류` 같은 안내 장 하나를 놓친다 — **그쪽이 손해가 작다.**
        """
        paras = ["6. 신청방법 및 제출서류", "￮ 제출서류", "지정신청 제출서류"]

        assert segment.doc_titles([], paras) == []

    def test_번호와_따옴표로_시작하는_제목은_산다(self) -> None:
        """줄머리 기호를 거르면서 **진짜 제목까지 버리면 안 된다.**

        실측에서 살아야 하는 셋이다 — 경남TP `1. …기본지원서` · 경기도 `『…』 신청서` ·
        경남TP `사용인감계 (지원기업)`.
        """
        paras = [
            "1. 2026년 0차 타깃마케팅(0000) 기본지원서",
            "『경기도 반려동물 창업공모전』 참가 신청서",
            "사용인감계 (지원기업)",
        ]

        assert segment.doc_titles([], paras) == paras


class Test제목을_받아_자르기:
    """구조가 찾은 제목을 원문에서 대조해 경계로 쓴다 (ADR-0061 결정 5).

    **위치는 우리가 찾는다.** 구조 쪽 좌표는 `(구역, 표, 행, 열)` 이라 글자 오프셋이
    아니고, 오프셋 없이는 근거 청크를 못 연다(ADR-0014).
    """

    TEXT = "\n".join(
        [
            "2026. 00. 00.(00) 작성자: 000",
            "1. 2026년 0차 타깃마케팅 기본지원서",
            "기 업 명\t대 표 자",
            "2. 2026년 0차 타깃마케팅 활동계획서",
            "1. 목적 및 필요성",
            "사용인감계 (지원기업)",
            "주 소 :",
        ]
    )
    TITLES = [
        "1. 2026년 0차 타깃마케팅 기본지원서",
        "2. 2026년 0차 타깃마케팅 활동계획서",
        "사용인감계 (지원기업)",
    ]

    def test_받은_제목에서_자른다(self) -> None:
        segs = segment.split(self.TEXT, titles=self.TITLES)

        assert [s.title for s in segs] == ["공고문", *self.TITLES]

    def test_오프셋이_그대로다(self) -> None:
        for s in segment.split(self.TEXT, titles=self.TITLES):
            assert self.TEXT[s.start : s.end] == s.text

    def test_원문에_없는_제목은_버린다(self) -> None:
        """**앵커 대조다.** 못 찾으면 지어내지 않는다 — 구조에서 읽은 글자와 텍스트
        파서가 낸 글자가 언제나 같지는 않다(이미지 상자·머리글).
        """
        segs = segment.split(self.TEXT, titles=["없는 신청서", *self.TITLES])

        assert [s.title for s in segs] == ["공고문", *self.TITLES]

    def test_원문에_두_번_나오는_제목은_버린다(self) -> None:
        """목차와 본문에 같은 이름이 있는 양식이 있다. **어느 쪽인지 못 고른다** —
        고르면 그 선택을 아무도 설명 못 한다(ADR-0063 결정 2 와 같은 판단).
        """
        text = "참가 신청서\n가운데\n참가 신청서\n끝\n"

        assert len(segment.split(text, titles=["참가 신청서"])) == 1

    def test_표지_마커와_같이_쓴다(self) -> None:
        """**둘 다 산다.** 구조는 hwp·docx 만 열리고 pdf 는 표지 규칙뿐이다."""
        text = "머리말\n[붙임 1] 신청서\n내용\n2. 활동계획서\n내용\n"

        segs = segment.split(text, titles=["2. 활동계획서"])

        assert [s.title for s in segs] == ["공고문", "붙임 1 신청서", "2. 활동계획서"]

    def test_표지_줄만_있는_구간은_다음과_합친다(self) -> None:
        """서울창업허브 실측. `붙임 1.` 과 제목이 **빈 줄을 사이에 두고** 떨어져 있다.

        합치지 않으면 서류 하나가 두 구간이 되고, 앞 구간은 `붙임 1.` 한 줄뿐이라
        판정이 `none` 으로 가서 **뒤 구간만 남는다** — 표지 번호를 잃는다.
        """
        text = "붙임 1.\n\n\n2026년 오픈 이노베이션 신청서\n기업명\t값\n"

        segs = segment.split(text, titles=["2026년 오픈 이노베이션 신청서"])

        assert [s.title for s in segs] == ["2026년 오픈 이노베이션 신청서"]
        assert segs[0].start == 0  # 표지 줄부터가 그 서류다

    def test_제목이_줄의_첫_셀과_같아야_한다(self) -> None:
        """경기도 반려동물 실측. 목차에 `사업계획서 작성 목차` 가 있어서 `사업계획서`
        로 **시작하는** 줄이 셋이었고 제목이 통째로 버려졌다.

        표 셀은 탭으로 이어 붙으므로 **첫 셀만** 본다 — 목차 줄은 첫 셀이 통째로
        `…사업계획서 작성 목차` 라 안 걸린다.
        """
        text = (
            "『공모전』 사업계획서 작성 목차\n"
            "항목\t세부항목\n"
            "『공모전』 사업계획서\t초기창업자\n"
            "내용\n"
        )

        segs = segment.split(text, titles=["『공모전』 사업계획서"])

        assert [s.title for s in segs] == ["공고문", "『공모전』 사업계획서"]

    def test_제목이_없으면_옛_동작_그대로다(self) -> None:
        assert [s.title for s in segment.split(FORM)] == [
            "공고문",
            "서식 1 지원 신청서",
            "서식 2 개인정보 동의서",
        ]


class Test구조_읽기의_경계:
    """`finnect.forms` 는 hwp 경로에서 **jpype 와 JVM 을 끌고 온다.**

    이 모듈은 초안 시작이 부른다(`draft/service.py` `_prepare`). 최상단에 두면
    **로컬은 통과하고 배포본만 죽는다** — `api/app.py` 가 `wiki.service` 를 함수
    안에서 부르는 것과 같은 자리다(ADR-0034).
    """

    def test_추출_서비스가_jpype_를_안_끌고_온다(self) -> None:
        import subprocess
        import sys

        code = "import finnect.extract.service, sys; print('jpype' in sys.modules)"
        out = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )

        assert out.stdout.strip() == "False", out.stderr

    def test_구조가_없는_포맷은_열지_않는다(self) -> None:
        """pdf 와 스캔본은 표 구조가 없어 텍스트로 물러난다(ADR-0061 결정 2).

        **실패로 세지 않는다** — 열려다 실패한 것과 애초에 안 여는 것은 다르다.
        """
        from finnect.extract.service import ExtractReport, _form_titles

        report = ExtractReport()

        assert _form_titles("aa/bb", "pdf", report) == []
        assert _form_titles(None, "hwp", report) == []
        assert report.form_failed == 0


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


class Test서류_표지는_라벨이_아니다:
    """**한글 양식이 서류 제목을 표 하나로 감싼다.**

        | 붙임 1 | (빈칸) | (빈칸) | 임대신청서 및 사업계획서 서식 |

    그러면 `붙임 1` 이 라벨이 되고 **옆의 장식용 빈 칸이 값 자리로 판정된다.**
    2026-08-23 실제로 거기에 회사 이름이 들어갔고, 칸이 좁아서 한/글에서 글자가
    세로로 눌려 나왔다. 코퍼스에서 그렇게 잡힌 항목이 166개였다.
    """

    def test_표지_낱말은_라벨에서_빠진다(self) -> None:
        for s in ("붙임 1", "붙임1", "[서식 3]", "별지 제1호", "첨부 2", "양식 4"):
            assert fields.is_marker(s), s

    def test_보통_라벨은_안_걸린다(self) -> None:
        """**번호를 요구한다.** `붙임` 만 있는 낱말은 본문에 흔하다."""
        for s in ("기업명", "대표자", "사업자등록번호", "붙임", "서식"):
            assert not fields.is_marker(s), s

    def test_표지가_섞인_표에서_라벨만_남는다(self) -> None:
        text = "붙임 1\t\t임대신청서 및 사업계획서 서식\n기업명\t\n대표자\t\n"
        assert fields.labels(text) == ["기업명", "대표자"]
