"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./layout.module.css";

/** 제품 껍데기. 상단 내비는 **3축이다** — 시연(`demo_from_hwi.html` 653·881·1198행)이 그렇다.
 *
 * **왼쪽 사이드바를 두지 않는다** — DESIGN.md §5.4 가 금지한 다섯 조합의 첫째다.
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
 * 물려받지 않게 하려는 것이고 마크업은 그대로다. */

/** 운영 도구(`/admin`)로 나가는 문.
 *
 * **이제 같은 앱 안이다.** 2026-08-17 까지는 로컬 `127.0.0.1:8000` 의 별개 Python 앱을
 * 가리켰고, 그래서 배포본에서 누르면 아무것도 안 열렸다. 옮긴 뒤로 상대 경로다(ADR-0027).
 *
 * 3축 내비 안에 넣지 않는다 — 제품 화면이 아니라 `SPEC.md` §6 밖의 도구다. */
const ADMIN = "/admin/notices";

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  // 상세(`/notices/...`)도 '지원사업'이다. **'/' 하나만 보면 목록에서만 켜진다**
  const wiki = path.startsWith("/wiki");

  return (
    <>
      <header className={styles.bar}>
        <div className={styles.inner}>
          <Link href="/" className={styles.brand}>
            <i className={styles.mark} aria-hidden />
            라스트마일
          </Link>

          <nav className={styles.menu} aria-label="주요 메뉴">
            <Link
              href="/"
              className={wiki ? undefined : styles.on}
              aria-current={wiki ? undefined : "page"}
            >
              지원사업
            </Link>
            <Link
              href="/wiki"
              className={wiki ? styles.on : undefined}
              aria-current={wiki ? "page" : undefined}
            >
              내 사업
            </Link>
            <span className={styles.soon} aria-disabled="true">
              신청 현황
              <span className="srOnly"> — 아직 없어요</span>
            </span>
          </nav>

          <Link href={ADMIN} className={styles.admin}>
            운영 도구
          </Link>
        </div>
      </header>

      <main className={styles.main}>{children}</main>
    </>
  );
}
