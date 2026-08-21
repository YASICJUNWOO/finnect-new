import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "라스트마일 — 지원사업",
  description: "맞는 공고를 골라 주고, 들어가면 문서가 이미 써져 있어요.",
  // iOS 는 매니페스트의 `display` 를 안 본다. 크롬 없이 열려면 이게 있어야 한다.
  // `title` 을 따로 주는 이유는 홈 화면 아래 글자가 `metadata.title` 이면 너무 길어서다
  appleWebApp: {
    capable: true,
    title: "라스트마일",
    statusBarStyle: "default",
  },
  // **Next 는 `mobile-web-app-capable` 만 낸다** — 접두사 없는 최신 이름이다.
  // iOS 는 17.4 부터 그걸 읽고, 그 아래는 `apple-` 붙은 옛 이름만 안다. 없으면
  // 홈 화면에서 열어도 **크롬이 그대로 있는 브라우저 창으로 뜬다.** 한 줄이 그걸 막는다.
  // 둘이 같이 있어도 뜻이 같아서 충돌하지 않는다
  other: { "apple-mobile-web-app-capable": "yes" },
};

/** **`viewportFit: "cover"` 가 이 파일의 요점이다.**
 *
 * 이게 없으면 `env(safe-area-inset-*)` 이 전부 0 이라, 노치 있는 폰에서 상단 막대가
 * 시계 밑으로 들어가고 하단 탭 바가 홈 인디케이터에 깔린다. **CSS 만 적어 두면
 * 조용히 0 이 되어 로컬에서는 멀쩡해 보인다** — 값을 여는 것은 여기다.
 *
 * `themeColor` 는 상태 막대 색이고 바로 아래 상단 막대(`--surface`)와 맞춘다.
 * **`manifest.ts` 의 `theme_color` 와 같은 값이어야 한다** — 갈리면 브라우저와 설치본이
 * 다른 색을 쓴다. 결정은 `DESIGN.md` §12.3, 값의 정본은 `tokens.css` 다.
 * `--surface` 를 고치면 여기와 `manifest.ts` 를 같이 고친다.
 *
 * **`maximumScale` 과 `userScalable` 을 건드리지 않는다.** 앱처럼 보이게 하려고
 * 확대를 막는 자리인데, 막으면 접근성이 깨진다. */
export const viewport: Viewport = {
  themeColor: "#fff",
  viewportFit: "cover",
};

/** 껍데기. **여기에 헤더를 두지 않는다.**
 *
 * 앱이 두 겹이라 그렇다(ADR-0027). `(product)/` 는 제품 화면이고 3축 내비를 얹는다.
 * `admin/` 은 운영 도구고 자기 내비를 얹는다. **둘이 같은 헤더를 쓰면 안 된다** —
 * 운영 화면 위에 '지원사업 / 내 사업 / 신청 현황'이 뜨면 그게 제품처럼 읽힌다.
 *
 * 루트 레이아웃이 html·body 와 토큰만 갖고, 헤더와 `main` 은 각 층이 가진다. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
