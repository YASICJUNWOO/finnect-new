"""노드 한 장의 마크다운 — plan/14.

**마크다운은 저장소가 아니라 뷰다**(plan/12 `구상도와의 차이`). 그래서 여기서 보는 것은
"저장된 글이 맞나"가 아니라 **"같은 DB 에서 항상 같은 글이 나오나"** 다. 시각이 들어가면
그 성질이 깨지고, 깨지면 바이트로 비교할 수 없다.

DB 도 파일도 안 쓴다 — `NodeView` 를 손으로 만들어 넣는다.
"""

from __future__ import annotations

from finnect.wiki import markdown, topics
from finnect.wiki.markdown import Evidence, NodeView, Statement, Value
from finnect.wiki.merge import Status


def _node(**kw) -> NodeView:  # noqa: ANN003
    base = dict(
        key="finance",
        label="자금 현황",
        kind="content",
        sector="성과와 자금",
        company_id="c_t",
        values=(),
        statements=(),
    )
    return NodeView(**{**base, **kw})


def _V(slot: str, value: str) -> Value:
    return Value(slot, topics.SLOTS[slot].label, value, None, None, Status.CURRENT, (E1,))


E1 = Evidence("사업계획서.docx", None, "시드 투자 3억원")
E2 = Evidence("재무제표.xlsx", None, "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다")
E3 = Evidence("피치덱.pptx", 11, "시드 라운드 2.8억원")


def test_시각이_안_들어간다():
    """**두 번 만들면 바이트가 같아야 한다.** `generated:` 같은 것을 넣으면 매일 달라진다."""
    n = _node(statements=(Statement("무엇이든", "cost", (E1,)),))
    assert markdown.render(n) == markdown.render(n)
    assert "generated" not in markdown.render(n)


def test_빈_노드도_한_장이_나온다():
    """**비어 있다는 것도 사실이고 물어야 할 자리다**(ADR-0028)."""
    out = markdown.render(_node())
    assert "# 자금 현황" in out
    assert "아직 비어 있어요" in out


def test_프론트매터가_옵시디언이_읽는_모양이다():
    """F1-6 이 이걸 그대로 쓴다. `kind` 를 넣어 밖에서도 종류가 색으로 갈리게 한다."""
    out = markdown.render(_node(statements=(Statement("사실 하나", "cost", (E1,)),)))
    head = out.split("---")[1]
    for line in ["node: finance", "title: 자금 현황", "kind: content", "company: c_t"]:
        assert line in head


def test_충돌은_둘_다_적고_말로_알린다():
    """**다수결로 안 푼다.** 3억이 근거 둘이어도 2.8억을 지우지 않는다."""
    n = _node(
        values=(
            Value(
                "funding", "조달액", "300000000", "시드", "2025-09-30", Status.CONFLICT, (E1, E2)
            ),
            Value("funding", "조달액", "280000000", "시드", "2025-09-30", Status.CONFLICT, (E3,)),
        )
    )
    out = markdown.render(n)
    assert markdown.CONFLICT_NOTE in out
    assert "conflict: true" in out
    assert "**300,000,000원**" in out
    assert "**280,000,000원**" in out


def test_이전_값은_접어서_아래_적는다():
    """지우지 않는다(F1-1-7). 현재값이 먼저 오고 이력이 뒤에 온다."""
    n = _node(
        key="team",
        label="팀 구성",
        values=(
            Value("headcount", "직원 수", "7", None, "2025-08-22", Status.SUPERSEDED, (E1,)),
            Value("headcount", "직원 수", "15", None, "2026-08-31", Status.CURRENT, (E3,)),
        ),
    )
    out = markdown.render(n)
    assert out.index("**15명**") < out.index("이전 값")
    assert "- 7명 · 2025-08-22" in out


def test_단위가_붙는다():
    """`120000000` 을 그대로 두면 1억 2천만과 1천 2백만이 눈으로 구분되지 않는다."""
    assert topics.display("capital", "120000000") == "120,000,000원"
    assert topics.display("headcount", "15") == "15명"
    #: 저장값이 숫자가 아니면 손대지 않는다. **추출기가 못 고친 값을 여기서 꾸미지 않는다**
    assert topics.display("capital", "1억 2천") == "1억 2천"
    #: 시점·이름은 단위가 없다
    assert topics.display("founded_on", "2024-03-11") == "2024-03-11"


def test_근거가_쪽까지_적힌다():
    """`회사소개서.pdf` 가 아니라 `회사소개서.pdf 3쪽` 이어야 한다(ADR-0014)."""
    out = markdown.render(_node(statements=(Statement("사실", "cost", (E3,)),)))
    assert "피치덱.pptx 11쪽" in out
    #: 쪽이 없는 포맷에는 안 붙인다 — **없는 번호를 만들어 붙이면 근거가 거짓이 된다**
    assert "사업계획서.docx 쪽" not in markdown.render(
        _node(statements=(Statement("사실", "cost", (E1,)),))
    )


def test_한_사실에_근거_여럿이_한_줄로_붙는다():
    out = markdown.render(_node(statements=(Statement("같은 말", "cost", (E1, E2, E3)),)))
    assert "> 근거 3 — 사업계획서.docx · 재무제표.xlsx · 피치덱.pptx 11쪽" in out


def test_근거_파일_목록이_끝에_붙는다():
    """**어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다."""
    out = markdown.render(_node(statements=(Statement("사실", "cost", (E1, E1, E3)),)))
    tail = out.split("## 근거 파일")[1]
    assert "- 사업계획서.docx" in tail and "- 피치덱.pptx" in tail
    #: 같은 파일이 두 번 나와도 한 줄이다
    assert tail.count("사업계획서.docx") == 1


def test_한정어가_제목에_붙는다():
    """시드와 정책자금은 같은 슬롯이지만 다른 것이다."""
    n = _node(
        values=(
            Value("funding", "조달액", "300000000", "시드", "2025-09-30", Status.CURRENT, (E1,)),
            Value("funding", "조달액", "50000000", "정책자금", "2025-04-30", Status.CURRENT, (E2,)),
        )
    )
    out = markdown.render(n)
    assert "## 조달액 [시드]" in out
    assert "## 조달액 [정책자금]" in out


def test_묶음은_노드를_순서대로_잇는다():
    a = _node(key="team", label="팀 구성", statements=(Statement("가", "team", (E1,)),))
    b = _node(key="finance", label="자금 현황", statements=(Statement("나", "cost", (E2,)),))
    out = markdown.bundle([a, b])
    assert out.startswith("# 사업 위키 — c_t")
    assert out.index("# 팀 구성") < out.index("# 자금 현황")


# ─────────────────────────────────────────────────────────────────
# topic 절 — ADR-0048 결정 5
# ─────────────────────────────────────────────────────────────────


def test_event_topic_이_둘_이상이면_절로_가른다():
    """**이게 ADR-0048 이 얻으려던 것이다.** 섞여 있던 것이 절로 갈린다."""
    out = markdown.render(
        _node(
            key="solution",
            label="솔루션과 기술",
            statements=(
                Statement("대시보드를 제공한다.", "service_feature", (E1,)),
                Statement("출원번호 10-2025-0012345.", "patent", (E1,)),
            ),
        )
    )
    assert "## 기능" in out
    assert "## 특허" in out
    assert out.index("## 기능") < out.index("## 특허")
    assert out.index("대시보드를 제공한다.") < out.index("## 특허")


def test_빈_topic_도_절이_선다():
    """비어 있다는 것도 사실이고 물어야 할 자리다(ADR-0028)."""
    out = markdown.render(
        _node(key="solution", label="솔루션과 기술", statements=(Statement("ㄱ", "patent", (E1,)),))
    )
    assert f"## 인증\n\n{markdown.EMPTY_TOPIC}" in out
    assert out.count(markdown.EMPTY_TOPIC) == 6


def test_event_topic_이_하나뿐이면_절을_안_세운다():
    """`# 목표 고객` 밑의 `## 목표 고객` 은 DESIGN.md §10 을 어긴다."""
    out = markdown.render(
        _node(
            key="customer",
            label="목표 고객",
            statements=(Statement("소상공인이다.", "target_customer", (E1,)),),
        )
    )
    assert "##" not in out.split("## 근거 파일")[0]
    assert "소상공인이다." in out


def test_절이_안_서는_자리는_빈_것을_따로_안_알린다():
    """제목이 없어서 「아직 없어요」 한 줄만 뜨면 무엇이 없다는 말인지 알 수 없다."""
    out = markdown.render(
        _node(key="team", label="팀 구성", values=(_V("headcount", "15"),), statements=())
    )
    assert markdown.EMPTY_TOPIC not in out


def test_표에_없는_topic_으로_온_것도_버리지_않는다():
    """라우팅 표를 고치면 옛 topic 이 붙은 행이 남는다."""
    out = markdown.render(
        _node(
            key="solution",
            label="솔루션과 기술",
            statements=(Statement("옛 것", "meeting", (E1,)),),
        )
    )
    assert "옛 것" in out


def test_topic_한국어_이름이_event_topic_전부에_있다():
    """**하나라도 없으면 화면에 영문 키가 나간다.**"""
    assert topics.EVENT_TOPICS - set(topics.TOPIC_LABELS) == set()


def test_topic_이름이_orbit_이름과_안_겹친다():
    """겹치면 `# X` 밑에 `## X` 가 서서 DESIGN.md §10 을 어긴다."""
    assert set(topics.TOPIC_LABELS.values()) & {o.label for o in topics.ORBIT.values()} == set()


def test_node_어휘가_orbit_과_한_벌이다():
    """**노드 이름은 orbit 키와 같다.** ADR-0048 결정 3 이 마이그레이션을 안 하는 근거다."""
    assert set(topics.EVENT_ORBITS) == {k for k, o in topics.ORBIT.items() if o.node}
    assert all(topics.EVENT_ORBITS[k] == topics.ORBIT[k].label for k in topics.EVENT_ORBITS)
    assert all(o.node == k for k, o in topics.ORBIT.items() if o.node)
