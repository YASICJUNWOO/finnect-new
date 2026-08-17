import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "라스트마일 — 지원사업",
  description: "맞는 공고를 골라 주고, 들어가면 문서가 이미 써져 있어요.",
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
