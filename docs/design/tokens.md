# design/tokens.md — 디자인 토큰

화면 구현에 그대로 쓸 값이다. 방침은 [`README.md`](README.md)에 있다.

---

## 1. 색

**GitHub Primer 라이트 모드 값을 그대로 쓴다.** 명도 대비가 이미 검증된 값이라 따로 계산하지 않는다. 의미가 있는 곳에만 색을 쓰고 나머지는 무채색이다.

| 토큰 | 값 | Primer 원본 | 용도 |
|------|-----|-------------|------|
| `--bg` | `#ffffff` | canvas.default | 기본 배경 |
| `--bg-subtle` | `#f6f8fa` | canvas.subtle | LNB, 표 헤더, 섹션 배경 |
| `--border` | `#d1d9e0` | border.default | 기본 구분선 |
| `--border-muted` | `#e4e8ed` | border.muted | 표 내부 옅은 선 |
| `--text` | `#1f2328` | fg.default | 본문 |
| `--text-muted` | `#59636e` | fg.muted | 보조 설명 |
| `--text-subtle` | `#818b98` | fg.subtle | 라벨, 비활성 |
| `--accent` | `#0969da` | accent.fg | 주요 액션, 링크, 현재 위치 |
| `--accent-subtle` | `#ddf4ff` | accent.subtle | 선택 상태 배경 |
| `--accent-muted` | `#54aeff` | accent.muted | 포커스 링 |
| `--attention` | `#9a6700` | attention.fg | 마감 임박 D-7 이내 |
| `--attention-subtle` | `#fff8c5` | attention.subtle | 마감 경고 배너 배경 |
| `--danger` | `#d1242f` | danger.fg | 탈락 조건, 오류 |
| `--danger-subtle` | `#ffebe9` | danger.subtle | 오류 배경 |
| `--success` | `#1a7f37` | success.fg | 완료 상태 |
| `--success-subtle` | `#dafbe1` | success.subtle | 완료 배경 |
| `--chart` | `#0969da` | accent.emphasis | 막대 |
| `--chart-track` | `#e4e8ed` | border.muted | 막대 트랙 |

### 색 사용 규칙 넷

1. 마감 임박은 `--attention`, 탈락으로 이어지는 조항은 `--danger`로 나눈다. **둘을 섞지 않는다.**
2. 색을 쓸 때 반드시 텍스트나 기호를 함께 둔다. D-day 표시는 색 점과 숫자를 같이 쓴다.
3. 포커스 링은 `--accent-muted` 2px 외곽선으로 통일한다.
4. 본문 영역에는 색을 쓰지 않는다. 링크만 `--accent`다.

---

## 2. 타이포

| 토큰 | 값 | 용도 |
|------|-----|------|
| 폰트 스택 | `Pretendard, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif` | 전역 |
| `--fs-display` | 22px / 600 / 1.4 | 화면 제목 |
| `--fs-title` | 17px / 600 / 1.5 | 섹션 제목, 목록 행 제목 |
| `--fs-body` | 14px / 400 / 1.65 | 본문 |
| `--fs-label` | 13px / 500 / 1.5 | 라벨, 표 헤더 |
| `--fs-caption` | 12px / 400 / 1.5 | 보조 설명 |

한글은 라틴보다 글자당 정보 밀도가 높아 행간을 넉넉히 잡는다. 본문 1.65는 그 값이다.

---

## 3. 간격과 형태

| 토큰 | 값 |
|------|-----|
| 간격 스케일 | 4, 8, 12, 16, 20, 24, 32, 40 |
| `--radius-sm` | 4px |
| `--radius` | 6px |
| `--radius-lg` | 10px |
| 목록 행 높이 | 최소 64px |
| LNB 너비 | 200px |
| 본문 최대 너비 | 880px |
| 표 행 높이 | 40px |
