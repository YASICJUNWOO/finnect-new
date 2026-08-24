"use client";

import { useEffect, useRef, useState } from "react";
import a from "../app/admin/admin.module.css";
import type { AdminIngestCard, Run } from "@/lib/admin";
import styles from "./IngestCard.module.css";

/** 수집 카드 하나 — 정보 표시는 서버가 그린 값 그대로, 실행 폼과 진행률만
 *  클라이언트가 맡는다(ADR-0065). **폴링은 `running` 일 때만 돈다** — 기본
 *  수집이 이제 몇 초면 끝나서(ADR-0064) 대부분은 한 번도 안 돈다. */
export default function IngestCard({ initial }: { initial: AdminIngestCard }) {
  const [card, setCard] = useState(initial);
  const [token, setToken] = useState("");
  const [full, setFull] = useState(false);
  const [limit, setLimit] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!card.running) {
      if (timer.current) clearInterval(timer.current);
      return;
    }
    timer.current = setInterval(async () => {
      try {
        const res = await fetch("/api/admin/ingest", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { cards: AdminIngestCard[] };
        const found = data.cards.find((c) => c.name === card.name);
        if (found) setCard(found);
      } catch {
        // 폴링 실패는 조용히 다음 차례를 기다린다. 버튼을 막을 이유가 아니다.
      }
    }, 1500);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [card.running, card.name]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/ingest/run/${card.name}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          token,
          full,
          limit: limit ? Number(limit) : undefined,
        }),
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
      const fresh = await fetch("/api/admin/ingest", { cache: "no-store" }).then(
        (r) => r.json() as Promise<{ cards: AdminIngestCard[] }>,
      );
      const found = fresh.cards.find((c) => c.name === card.name);
      if (found) setCard(found);
    } catch {
      setMessage({ kind: "error", text: "API에 못 붙었어요" });
    } finally {
      setSubmitting(false);
    }
  }

  const n = (v: number) => v.toLocaleString("ko-KR");

  return (
    <div className={a.card}>
      <h2 className={a.cardTitle}>
        {card.label} <span className={a.tag}>{card.name}</span>
      </h2>
      <p className={a.note}>
        실측 <span data-numeric>{n(card.expected)}</span>건 · {card.requests}
      </p>

      <div className={a.stored}>
        {n(card.stored)}
        <span className={a.storedUnit}>건 저장됨</span>
      </div>

      {card.running && card.progress && (
        <>
          <div className={styles.meter}>
            <i
              className={styles.meterFill}
              style={{ width: `${card.progress.percent ?? 0}%` }}
            />
          </div>
          <p className={styles.running}>
            수집 중 — 응답 {n(card.progress.pages)}건 · 공고 {n(card.progress.items)}건
            {card.progress.goal ? ` / ${n(card.progress.goal)}건` : ""}
          </p>
        </>
      )}

      {!card.running && (
        <LastRun run={card.last} />
      )}

      <p className={styles.cardNote}>{card.note}</p>

      <form className={styles.form} onSubmit={onSubmit}>
        <input
          type="password"
          placeholder="실행 토큰"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          disabled={card.running || submitting}
          required
        />
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={full}
            onChange={(e) => setFull(e.target.checked)}
            disabled={card.running || submitting}
          />
          전량
        </label>
        <input
          type="number"
          min={1}
          placeholder="맛보기"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          disabled={card.running || submitting}
        />
        <button type="submit" className={styles.submit} disabled={card.running || submitting}>
          {card.running ? "수집 중이에요" : "수집해요"}
        </button>
      </form>
      {message && (
        <p className={`${styles.message} ${message.kind === "error" ? styles.messageError : styles.messageInfo}`}>
          {message.text}
        </p>
      )}
    </div>
  );
}

function LastRun({ run }: { run: Run | null }) {
  const n = (v: number) => v.toLocaleString("ko-KR");
  if (!run) return <p className={a.note}>아직 한 번도 안 돌렸다.</p>;
  return (
    <p className={a.note}>
      마지막 {stamp(run.started_at)} <StatusPill status={run.status} /> · {run.elapsed}
      {run.status === "ok" && (
        <>
          {" "}
          · 신규 <span data-numeric>{n(run.inserted)}</span> · 변경{" "}
          <span data-numeric>{n(run.changed)}</span>
          {run.filtered > 0 && (
            <>
              {" "}
              · 솎음 <span data-numeric>{n(run.filtered)}</span>
            </>
          )}
        </>
      )}
      {run.truncated && (
        <>
          <br />
          <span className={a.warn}>
            ⚠ 맛보기였다 — <span data-numeric>{n(run.items)}</span>건만 받았다
            {run.expected && <> (전량 {n(run.expected)})</>}
          </span>
        </>
      )}
    </p>
  );
}

/** `page.tsx` 의 `RunRow` 안 것과 같은 톤 매핑이다. 상태가 아홉인데 색은 넷뿐이다 —
 *  좋다/나쁘다/애매하다/안 했다. 뜻은 글자가 말하고 색은 그 넷만 가른다. */
function StatusPill({ status }: { status: string }) {
  const tone =
    status === "ok"
      ? a.pillOk
      : status === "failed"
        ? a.pillBad
        : status === "running"
          ? a.pillNone
          : a.pillWarn;
  return <span className={`${a.pill} ${tone}`}>{status}</span>;
}

function stamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (v: number) => String(v).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
