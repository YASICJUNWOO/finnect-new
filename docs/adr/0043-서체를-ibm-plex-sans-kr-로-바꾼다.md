# ADR-0043: 서체를 IBM Plex Sans KR 로 바꾼다

- 상태: 채택됨
- 날짜: 2026-08-21
- 여는 것: 공고 목록·상세 시안 비교 — [`docs/design/mockup/notice/`](../design/mockup/notice/README.md) `R 적응` 채택
- 관련: [ADR-0041](0041-토큰-실값을-remember-canonical-로-바꾼다.md) 토큰 실값 · [ADR-0018](0018-디자인-방향-이관.md) 시각 정본

## 맥락

`DESIGN.md` §1 이 **「Pretendard 한 벌. 제목용 서체를 따로 들이지 않는다」** 고 적었고 §3 이 그 근거를 적었다 — remember(리멤버) career 라우트에서 Pretendard 가 계산돼 나오고 FontFaceSet 으로 뒷받침되며 본문·조작 요소·카드·제목·입력·목록·다이얼로그에 걸쳐 1,053회 기록됐다.

**그 근거는 레퍼런스가 무엇을 쓰는지에 대한 것이지 우리가 무엇을 써야 하는지에 대한 것이 아니다.** 시안 비교에서 셋을 나란히 놓고 같은 문자열의 렌더 폭으로 쟀다.

| | 같은 제목 한 줄 · 16px/400 | |
|---|---:|---|
| **IBM Plex Sans KR** (IBM) | **378.82px** | 채택 |
| Pretendard (orioncactus) | 370.45px | 예비 · −2.21% |
| Wanted Sans (원티드랩) | 370.66px | 예비 · −2.15% |
| (시스템 대체) | 410.45px | 로드 실패하면 여기로 튄다 |

육안 검토에서 셋 다 읽을 만하다고 나왔고 IBM Plex Sans KR 을 골랐다. 셋 다 한국어 전용 SIL OFL 이라 라이선스가 갈리지 않는다.

**`document.fonts.check()` 로 판정하지 않는다.** Wanted Sans 가 로드되지 않은 문서에서도 `true` 를 준다. 위 값은 전부 렌더 폭 대조로 얻었다.

## 결정

**1. 제품 서체를 IBM Plex Sans KR 로 바꾼다.** 굵기 400·500·600 세 벌을 받는다.

**2. Pretendard 를 대체 서체로 스택에 남긴다.** 지우지 않는다 — Plex 가 안 붙었을 때 시스템 고딕(410.45px)으로 튀는 것보다 Pretendard(370.45px)로 튀는 쪽이 밀도 차가 작다.

**3. 등폭이 필요한 자리는 IBM Plex Mono 다.** 본문 서체와 짝이다. **다만 지금 붙이지 않는다** — `font-variant-numeric: tabular-nums` 가 이미 자릿수 정렬을 하고 있고, 등폭 서체를 하나 더 받는 것은 그것이 부족하다고 잰 뒤에 한다.

**4. `DESIGN.md` §1 과 §3 을 고친다.** §3 «Evidence classes» 표에 이 결정을 **「레포 결정」** 줄로 올린다 — 라이브 관측(Pretendard)과 다른 등급이다. remember 근거로 정당화하지 않는다.

## 결과

- `globals.css` 의 `font-family` 가 바뀐다. 값의 자리는 `tokens.css` 이므로 스택을 토큰(`--font-sans`)으로 올린다.
- **웹폰트를 어떻게 받을지가 이 ADR 밖에 남는다.** 시안은 Google Fonts CDN 을 `@import` 로 받았다. 제품은 `next/font` 로 셀프 호스팅하는 길과 CDN 을 받는 길이 있고, 지금은 **CDN 을 안 쓰고 `next/font/google` 로 받는다** — 배포본이 Vercel 이라 빌드 때 받아 같은 도메인에서 내보내고, 그러면 CDN 이 죽어도 화면이 시스템 고딕으로 안 튄다.
- **밀도 숫자가 전부 다시 잰 값이어야 한다.** 시안 README 의 실측표는 Plex 기준이라 그대로 쓸 수 있지만, 예비 서체로 갈면 2.2% 좁아진다. 예비로 갈 일이 생기면 표를 다시 잰다.
- **포기하는 것** — Pretendard 는 이 레포가 6일 동안 쓰던 서체이고 remember 근거가 붙어 있던 유일한 타입 값이었다. 이제 §3 에서 근거가 붙은 것은 크기·굵기·줄높이뿐이고 서체는 우리가 정한 값이다.
- `docs/design/mockup/notice/` 의 `현행` 대조군(`base.html`)은 Pretendard 를 그대로 둔다. 현행 재현이라 손대면 대조군이 아니게 된다.
