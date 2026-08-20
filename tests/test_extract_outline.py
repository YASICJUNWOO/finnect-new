"""서술형 항목 트리와 지시문 (plan/11 T-0037 · ADR-0019).

**집필의 축이 여기서 나온다.** 배점이 아니라 양식 목차와 항목별 작성 지침이
축이라고 [ADR-0019](../docs/adr/0019-집필의-축을-양식으로.md)가 정했다.

본문은 실제 공고 첨부에서 옮겼다(창업진흥원 계열 지원프로그램 신청서식).
**지어낸 양식으로 시험하면 우리가 만든 규칙을 우리가 통과시킨다.**
"""

from __future__ import annotations

from finnect.extract import outline

FORM = "\n".join(
    [
        "1. 일반 현황",
        " 1-1. 기업소개",
        "",
        "  - 기업의 미션 및 비전, 주력제품, 조직 등 기업의 일반현황에 대하여 기재",
        "",
        " 1-5. 기타역량",
        "  가.",
        "    · R&D 역량 또는 지식재산권 보유 등 기타 역량에 대하여 기재",
        "2. 사업 내용(지원프로그램 수행 계획)",
        " 2-1. 지원프로그램",
        " 가. 신청 지원 프로그램",
        "신청 지원 프로그램\t정부 지원금\t기업 부담금",
        "예 : 시제품제작지원\t20,000\t2,000",
        " 나. 신청 프로그램의 개요(배경 및 필요성 등)",
        "   - 기업 및 시장 동향, 제품의 문제점 등을 구체적으로 기술",
        "   - 설명을 보충 할 수 있는 그림이나 도식화된 자료를 활용하여 부연 설명",
        "① 예) 시제품제작지원",
        "- 시제품에 대한 구성 및 내용을 도면을 통해 상세하게 기술 (본문은 50페이지 내외로 작성)",
        "※ 제출시 파란색으로 표기된 안내글은 삭제 필요",
    ]
)


def _by_title(items: list[outline.Item], title: str) -> outline.Item:
    return next(i for i in items if i.title.startswith(title))


class Test항목_트리:
    def test_번호_체계로_단이_갈린다(self) -> None:
        items = outline.items(FORM)

        assert _by_title(items, "일반 현황").level == 1
        assert _by_title(items, "기업소개").level == 2
        assert _by_title(items, "신청 지원 프로그램").level == 3
        assert _by_title(items, "예) 시제품").level == 4

    def test_2단을_1단보다_먼저_본다(self) -> None:
        """**`2-1.` 이 `2.` 로 잡히면 트리가 통째로 평평해진다.**"""
        assert _by_title(outline.items(FORM), "지원프로그램").number == "2-1"

    def test_부모를_건다(self) -> None:
        items = outline.items(FORM)
        child = items.index(_by_title(items, "신청 프로그램의 개요"))

        assert items[child].parent == items.index(_by_title(items, "지원프로그램"))

    def test_최상위는_부모가_없다(self) -> None:
        assert _by_title(outline.items(FORM), "일반 현황").parent is None

    def test_제목이_빈_헤딩은_항목이_아니다(self) -> None:
        """`가.` 만 있고 뒤가 빈 줄이 실제로 있다. **지시문은 위 항목이 받는다.**"""
        items = outline.items(FORM)

        assert all(i.title for i in items)
        assert "기타 역량에 대하여 기재" in (_by_title(items, "기타역량").instruction or "")

    def test_표의_한_줄을_헤딩으로_안_읽는다(self) -> None:
        assert not [i for i in outline.items(FORM) if "정부 지원금" in i.title]

    def test_항목이_없으면_빈_목록이다(self) -> None:
        """**지어내지 않는다.** 항목 0개는 판정이 틀렸다는 신호다."""
        assert outline.items("그냥 줄글입니다. 번호도 없고 항목도 없어요.") == []


class Test지시문:
    def test_양식이_쓴_그대로_둔다(self) -> None:
        """**우리가 해요체로 고쳐 쓰지 않는다**(plan/11)."""
        got = _by_title(outline.items(FORM), "기업소개").instruction

        assert got == "기업의 미션 및 비전, 주력제품, 조직 등 기업의 일반현황에 대하여 기재"

    def test_여러_줄을_순서대로_잇는다(self) -> None:
        got = _by_title(outline.items(FORM), "신청 프로그램의 개요").instruction or ""

        assert got.splitlines()[0].startswith("기업 및 시장 동향")
        assert got.splitlines()[1].startswith("설명을 보충")

    def test_지시문이_없으면_None_이다(self) -> None:
        assert _by_title(outline.items(FORM), "신청 지원 프로그램").instruction is None

    def test_별표는_동사가_없어도_지시문이다(self) -> None:
        items = outline.items("1. 안내\n※ 파란 글씨는 그대로 두세요")

        assert items[0].instruction == "파란 글씨는 그대로 두세요"


class Test분량_제한:
    def test_양식이_준_것만_뽑는다(self) -> None:
        assert _by_title(outline.items(FORM), "예) 시제품").limit_text == "50페이지 내외"

    def test_없으면_None_이다(self) -> None:
        assert _by_title(outline.items(FORM), "기업소개").limit_text is None


class Test오프셋:
    def test_잘라내면_그_항목이_나온다(self) -> None:
        """**나중에 붙일 수 없다**(ADR-0014)."""
        item = _by_title(outline.items(FORM), "기업소개")

        assert FORM[item.start : item.end].startswith(" 1-1. 기업소개")

    def test_다음_항목_직전까지다(self) -> None:
        items = outline.items(FORM)
        first, second = items[0], items[1]

        assert first.end == second.start
