"""맞는 공고 고르기 — M 계층 (plan/17).

**LLM 이 회사 쪽을 안 본다.** 공고를 한 번 정규화하면 회사 수와 무관하게 모두가
쓴다(`normalize.py`). 회사와의 대조는 전부 코드다 —

    profile.py    위키 → CompanyProfile.  읽기만 한다
    eligible.py   ③ 자격 (M1).  못 넘으면 뺀다
    sectors.py    ④ 분야 (M2 앞단).  뒤로 민다
    rank.py       ⑤ 순서와 이유.  템플릿이 만든다
"""
