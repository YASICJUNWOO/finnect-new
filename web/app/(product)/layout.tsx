"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Install } from "@/components/Install";
import styles from "./layout.module.css";

/** 제품 껍데기. 상단 내비는 **3축이다** — 시연(`demo_from_hwi.html` 653·881·1198행)이 그렇다.
 *
 * **왼쪽 사이드바를 두지 않는다** — DESIGN.md §5 가 금지한 다섯 조합의 첫째다.
 * 3축을 위로 올린 것이 그 답이다.
 *
 * 셋 중 '지원사업'과 '내 사업'이 있다. **'신청 현황'(S6)만 화면이 없어서
 * 누를 수 없는 채로 자리를 지킨다.** 없는 곳으로 보내지 않고, 없다는 것을 보여 준다.
 *
 * 2026-08-18 '내 사업'(S7)이 켜졌다. 축이 둘이 되면서 **활성 표시를 `usePathname` 으로
 * 옮겼고, 그래서 이 파일이 클라이언트 컴포넌트가 됐다.** 활성 축을 못 박아 두면
 * 위키에 들어가서도 '지원사업'이 켜져 있다.
 *
 * 2026-08-17 루트 레이아웃에서 여기로 내려왔다(ADR-0027). 운영 화면이 이 헤더를
 * 물려받지 않게 하려는 것이고 마크업은 그대로다.
 *
 * 2026-08-21 **같은 3축이 좁은 화면에서 아래로 내려간다**(ADR-0039 · DESIGN.md §12).
 * 설치하면 브라우저 크롬이 없어서 상단 막대가 유일한 크롬이 되고, 폰에서 그 자리는
 * 엄지가 안 닿는다. 축은 그대로 셋이고 자리만 바뀐다. */

/** 운영 도구(`/admin`)로 나가는 문.
 *
 * **이제 같은 앱 안이다.** 2026-08-17 까지는 로컬 `127.0.0.1:8000` 의 별개 Python 앱을
 * 가리켰고, 그래서 배포본에서 누르면 아무것도 안 열렸다. 옮긴 뒤로 상대 경로다(ADR-0027).
 *
 * 3축 내비 안에 넣지 않는다 — 제품 화면이 아니라 `SPEC.md` §6 밖의 도구다. */
const ADMIN = "/admin/notices";

/** 3축. **상단 막대와 하단 탭 바가 이 배열 하나를 읽는다.**
 *
 * 축을 두 곳에 적으면 넷째 축이 생기는 날 한쪽만 고쳐지고, 그때 위아래가 다른 메뉴를
 * 보여 준다. `href` 가 `null` 인 축은 화면이 없는 축이다(S6).
 *
 * `on` 을 축마다 함수로 두는 이유는 **상세도 자기 축이기 때문이다** — `/notices/...` 는
 * '지원사업'이고 `'/' === path` 로 보면 목록에서만 켜진다. */
const AXES = [
  { href: "/", label: "지원사업", on: (p: string) => !p.startsWith("/wiki") },
  { href: "/wiki", label: "내 사업", on: (p: string) => p.startsWith("/wiki") },
  { href: null, label: "신청 현황", on: () => false },
] as const;

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  return (
    <>
      <header className={styles.bar}>
        <div className={styles.inner}>
          <Link href="/" className={styles.brand}>
            <i className={styles.mark} aria-hidden />
            라스트마일
          </Link>

          <nav className={styles.menu} aria-label="주요 메뉴">
            {AXES.map((a) =>
              a.href === null ? (
                <span key={a.label} className={styles.soon} aria-disabled="true">
                  {a.label}
                  <span className="srOnly"> — 아직 없어요</span>
                </span>
              ) : (
                <Link
                  key={a.label}
                  href={a.href}
                  className={a.on(path) ? styles.on : undefined}
                  aria-current={a.on(path) ? "page" : undefined}
                >
                  {a.label}
                </Link>
              ),
            )}
          </nav>

          <Link href={ADMIN} className={styles.admin}>
            운영 도구
          </Link>
        </div>
      </header>

      <Install />

      <main className={styles.main}>{children}</main>

      {/* 같은 3축. 좁은 화면에서만 뜨고 상단의 `.menu` 는 그때 숨는다 —
        * 둘이 같이 뜨면 같은 메뉴가 화면에 두 번 있다. 규칙은 CSS 한 곳에 있다.
        *
        * `aria-hidden` 을 걸지 않는다. 숨는 쪽이 `display: none` 이라 스크린 리더가
        * 어차피 하나만 읽는다 — 여기에 걸면 폰에서 내비가 아예 안 읽힌다. */}
      <nav className={styles.tabs} aria-label="주요 메뉴">
        {AXES.map((a) =>
          a.href === null ? (
            <span key={a.label} className={styles.soon} aria-disabled="true">
              {a.label}
              <span className="srOnly"> — 아직 없어요</span>
            </span>
          ) : (
            <Link
              key={a.label}
              href={a.href}
              className={a.on(path) ? styles.on : undefined}
              aria-current={a.on(path) ? "page" : undefined}
            >
              {a.label}
            </Link>
          ),
        )}
      </nav>
    </>
  );
}
