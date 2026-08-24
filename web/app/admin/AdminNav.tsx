"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./layout.module.css";

/** 운영 내비. **앞 셋과 순서가 Jinja2 `base.html` 과 같다** — T-0023 이
 *  "내비게이션 구조 변경"을 안 하는 것으로 정했고, 옮기는 것은 구조 변경이 아니다.
 *  넷째(위키)는 옮겨 온 것이 아니라 새로 난 화면이라 맨 뒤에 붙는다(ADR-0072).
 *
 *  제품 헤더와 달리 여기는 `usePathname` 을 쓴다. 세 축이 다 살아 있어서
 *  활성 항목을 박아 둘 수 없다. */
const ITEMS = [
  { href: "/admin/notices", label: "공고 목록" },
  { href: "/admin/ingest", label: "수집" },
  { href: "/admin/attachments", label: "첨부 해독" },
  // **넷째가 2026-08-24 붙었다**(ADR-0072). 앞 셋과 성질이 다르다 — 저것들은
  // 코퍼스를 보는 화면이고 이건 사용자 데이터를 **지우는** 화면이라 맨 뒤에 둔다.
  { href: "/admin/wiki", label: "위키" },
];

export function AdminNav() {
  const path = usePathname();

  return (
    <nav className={styles.menu} aria-label="운영 메뉴">
      {ITEMS.map((it) => {
        // 상세(/admin/notices/bizinfo/...)에서도 '공고 목록'이 켜져야 한다.
        const on = path === it.href || path.startsWith(`${it.href}/`);
        return (
          <Link
            key={it.href}
            href={it.href}
            className={on ? styles.on : undefined}
            aria-current={on ? "page" : undefined}
          >
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}
