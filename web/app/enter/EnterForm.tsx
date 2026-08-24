"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./page.module.css";

/** 입장 폼([ADR-0066](../../../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **가입과 로그인을 안 나눈다.** 버튼이 하나이고 문구가 「시작하기」다 — 처음 온
 * 사람과 다시 온 사람이 같은 것을 누른다.
 *
 * **오류를 인라인으로 낸다.** 서버가 적은 문장을 그대로 옮긴다(`route.ts` 가
 * `detail` 을 넘긴다) — "그 이름에 이 비밀번호가 아니에요" 가 무엇을 해야 하는지 말한다. */
export function EnterForm({ next }: { next?: string }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (sending) return;
    setError(null);
    setSending(true);

    try {
      const res = await fetch("/api/account", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, password }),
      });
      const data = (await res.json()) as { detail?: string };
      if (!res.ok) {
        setError(data.detail ?? `들어가다가 잘못됐어요 (${res.status})`);
        return;
      }
      // **`router.refresh()` 가 필요하다.** 서버 컴포넌트가 쿠키를 읽는데(`currentCompany`)
      // 캐시된 것을 그대로 쓰면 방금 앉힌 회사가 아니라 옛 화면이 뜬다.
      router.replace(safeNext(next));
      router.refresh();
    } catch {
      setError("연결이 끊겼어요. 잠시 뒤에 다시 눌러 주세요");
    } finally {
      setSending(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <label className={styles.field}>
        <span className={styles.label}>사업 이름</span>
        <input
          className={styles.input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="organization"
          autoFocus
          required
        />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>비밀번호</span>
        <input
          className={styles.input}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {/* **되찾을 방법이 없다는 것을 미리 말한다.** 베타라 재설정을 안 만들었고
          * (ADR-0066), 잊은 뒤에 알려 주면 그 사람의 위키가 그대로 잠긴다 */}
        <span className={styles.hint}>
          찾아 드릴 방법이 없어요. 적어 두시는 게 좋아요.
        </span>
      </label>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <button className={styles.submit} type="submit" disabled={sending}>
        {sending ? "들어가는 중이에요" : "시작하기"}
      </button>
    </form>
  );
}

/** **주소를 그대로 믿지 않는다.** `?next=` 는 사용자가 고칠 수 있어서, 남의 사이트로
 * 보내는 값이 오면 우리 화면에서 출발하는 리다이렉트가 된다(오픈 리다이렉트).
 * 우리 앱 안의 절대 경로만 받는다 — `//evil.com` 은 `/` 로 시작하지만 바깥이다. */
function safeNext(next?: string): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/wiki/files";
  return next;
}
