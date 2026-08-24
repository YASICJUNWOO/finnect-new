"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./ExitAccount.module.css";

/** 다른 이름으로 들어가기([ADR-0066](../../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **상단 막대가 아니라 「내 사업」에 있다.** 저 껍데기는 클라이언트 컴포넌트인데
 * `fc` 는 `httpOnly` 라 스크립트가 못 읽는다 — 거기 두면 **아직 안 들어온 사람에게도
 * 「나가기」가 보인다.** 이 화면은 게이트가 걸려 있어서(`web/proxy.ts`) 여기 온 사람은
 * 반드시 회사가 있다.
 *
 * **확인을 안 받는다.** 잃는 것이 없다 — 위키와 올린 파일은 그대로 남고, 같은 이름과
 * 비밀번호로 다시 들어오면 그대로 열린다. 「초기화」가 고친 글이 있을 때만 묻는 것과
 * 같은 규칙이다(ADR-0062) — **잃을 것이 없는데 확인을 받으면 다음의 진짜 경고까지
 * 흘려본다.** */
export function ExitAccount() {
  const [sending, setSending] = useState(false);
  const router = useRouter();

  async function exit() {
    if (sending) return;
    setSending(true);
    try {
      await fetch("/api/account", { method: "DELETE" });
      router.replace("/enter");
      // 서버 컴포넌트가 쿠키를 읽으므로(`currentCompany`) 캐시된 화면을 버려야 한다
      router.refresh();
    } catch {
      // 못 나갔으면 그대로 둔다. 다시 누르면 된다
      setSending(false);
    }
  }

  return (
    <button className={styles.exit} type="button" onClick={exit} disabled={sending}>
      다른 이름으로 들어가기
    </button>
  );
}
