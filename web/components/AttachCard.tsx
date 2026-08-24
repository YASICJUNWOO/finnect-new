"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import a from "../app/admin/admin.module.css";
import type { AdminAttach, AttachProgress } from "@/lib/admin";
import styles from "./IngestCard.module.css";

/** 첨부 받기 카드 — [ADR-0071](../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md).
 *
 * **`IngestCard` 의 CSS 를 그대로 쓴다.** 폼·막대·메시지가 같은 모양이어야 하는
 * 자리라 두 벌로 두지 않는다 — 갈리면 같은 화면에 다른 버튼이 선다.
 *
 * **끝나면 페이지를 새로 그린다**(`router.refresh()`). 이 카드 아래의 해독 현황이
 * 서버 컴포넌트라, 안 그러면 방금 받은 것이 표에 안 나타나서 **아무 일도 안 일어난
 * 것처럼 보인다.** */
export default function AttachCard({ initial }: { initial: AdminAttach }) {
  const [state, setState] = useState(initial);
  const [token, setToken] = useState("");
  const [limit, setLimit] = useState("");
  const [redo, setRedo] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!state.running) {
      if (timer.current) clearInterval(timer.current);
      return;
    }
    timer.current = setInterval(async () => {
      try {
        const res = await fetch("/api/admin/attach", { cache: "no-store" });
        if (!res.ok) return;
        const fresh = (await res.json()) as AdminAttach;
        setState(fresh);
        // 방금 끝났다. 아래 해독 현황은 서버가 그린 옛 숫자라 다시 받아야 한다.
        if (!fresh.running) router.refresh();
      } catch {
        // 폴링 실패는 조용히 다음 차례를 기다린다. 버튼을 막을 이유가 아니다.
      }
    }, 1500);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [state.running, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/attach/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, redo, limit: limit ? Number(limit) : undefined }),
      });
      const data = (await res.json()) as { detail?: string; started?: boolean; reason?: string };
      if (!res.ok) {
        setMessage({ kind: "error", text: data.detail ?? "실행하다가 잘못됐어요" });
        return;
      }
      if (!data.started) {
        setMessage({ kind: "info", text: data.reason || "이미 돌고 있어요" });
      } else {
        setToken("");
      }
      const fresh = await fetch("/api/admin/attach", { cache: "no-store" }).then(
        (r) => r.json() as Promise<AdminAttach>,
      );
      setState(fresh);
    } catch {
      setMessage({ kind: "error", text: "API에 못 붙었어요" });
    } finally {
      setSubmitting(false);
    }
  }

  const n = (v: number) => v.toLocaleString("ko-KR");
  const nothing = state.pending === 0 && !redo;

  return (
    <div className={a.card}>
      <h3 className={a.cardTitle}>첨부 받기</h3>

      <div className={a.stored}>
        {n(state.pending)}
        <span className={a.storedUnit}>건 아직 안 받음</span>
      </div>
      <p className={a.note}>
        첨부 URL <span data-numeric>{n(state.urls)}</span>개 중이다. 받아 둔 것은 대상에서
        빠지고, 받기가 실패한 것도 다시 두드리지 않는다 — 그건 <code>다시 해독</code>이
        한다.
      </p>

      {state.running && (
        <>
          <div className={styles.meter}>
            <i
              className={styles.meterFill}
              style={{ width: `${state.progress?.percent ?? 0}%` }}
            />
          </div>
          <p className={styles.running}>{progressText(state.progress)}</p>
        </>
      )}

      {!state.running && state.last && (
        <p className={`${a.note} ${state.last.ok ? "" : a.bad}`}>
          마지막 실행 — {state.last.ok ? state.last.detail || "끝났어요" : state.last.detail}
        </p>
      )}

      <form className={styles.form} onSubmit={onSubmit}>
        <input
          type="password"
          placeholder="실행 토큰"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          disabled={state.running || submitting}
          required
        />
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={redo}
            onChange={(e) => setRedo(e.target.checked)}
            disabled={state.running || submitting}
          />
          다시 해독
        </label>
        <input
          type="number"
          min={1}
          placeholder="맛보기"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          disabled={state.running || submitting}
        />
        <button
          type="submit"
          className={styles.submit}
          disabled={state.running || submitting || nothing}
        >
          {state.running ? "받는 중이에요" : nothing ? "다 받았어요" : "받아요"}
        </button>
      </form>
      {message && (
        <p
          className={`${styles.message} ${
            message.kind === "error" ? styles.messageError : styles.messageInfo
          }`}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}

/** **첫 보고 전에는 진행이 없다.** 그때 0/0 을 그리면 "받을 게 없다" 로 읽히는데
 *  사실은 대상을 세는 중이다 — 3,354건에서 디스크를 한 번씩 확인한다. */
function progressText(p: AttachProgress | null): string {
  const n = (v: number) => v.toLocaleString("ko-KR");
  if (p === null) return "받을 것을 세는 중이에요";
  const mb = Math.round(p.bytes_in / 1024 / 1024);
  // **분모는 `goal` 이다.** 맛보기 2건을 받는 중이면 386 이 아니라 2 여야 막대가 맞는다.
  const of = p.goal ? ` / ${n(p.goal)}건` : "건";
  const left = p.target !== null && p.total > p.target ? ` (남은 것 ${n(p.total)}건)` : "";
  return `받는 중 — ${n(p.done)}${of} · ${n(mb)}MB${left}`;
}
