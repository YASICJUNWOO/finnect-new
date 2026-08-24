"use client";

import { useState } from "react";
import a from "../app/admin/admin.module.css";
import form from "./IngestCard.module.css";
import type { AdminWikiCompany } from "@/lib/admin";
import styles from "./WikiPurgeTable.module.css";

/** 회사별 위키 지우기([ADR-0072](../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).
 *
 * **토큰 입력이 화면에 하나다.** 행마다 두면 같은 값을 회사 수만큼 치게 된다 —
 * 어차피 문이 하나라(`x-ingest-trigger-token`) 나눌 것이 없다.
 *
 * **누르면 바로 안 지운다.** 확인 줄이 그 행 아래에 펼쳐지고 거기서 한 번 더 누른다.
 * 되돌릴 수 없는 동작이고 원본 파일까지 지우므로 [ADR-0062](../../docs/adr/0062-다시-쓰기가-고친-글을-지우되-먼저-알린다.md)
 * 와 같은 자리다 — 다만 **저기와 달리 항상 묻는다.** 이 표에 선 행은 정의상 지울 것이
 * 있는 행이라 「잃을 게 없는 확인」이 아예 없다.
 *
 * **지우는 버튼에 액센트를 안 준다**(선 버튼). 채운 검정을 주면 권하는 말이 된다. */
export default function WikiPurgeTable({ initial }: { initial: AdminWikiCompany[] }) {
  const [rows, setRows] = useState(initial);
  const [token, setToken] = useState("");
  /** 확인 줄을 펼친 회사. 한 번에 하나다 — 둘을 같이 열면 어느 것을 누르는지 흐려진다 */
  const [asking, setAsking] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);

  async function purge(row: AdminWikiCompany) {
    setBusy(row.company_id);
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/wiki/purge/${encodeURIComponent(row.company_id)}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = (await res.json()) as {
        detail?: string;
        files?: number;
        facts?: number;
        storage?: boolean;
      };
      if (!res.ok) {
        setMessage({ kind: "error", text: data.detail ?? "지우다가 잘못됐어요" });
        return;
      }
      setAsking(null);
      setMessage({
        kind: "info",
        text:
          `${label(row)} 위키를 지웠어요 — 파일 ${data.files ?? 0}건 · 사실 ${data.facts ?? 0}건 · ` +
          `원본 ${data.storage ? "지움" : "없음"}. 이제 다시 올릴 수 있어요`,
      });
      // **목록을 다시 받는다.** 지운 행을 화면에서만 빼면 남은 숫자가 옛 값이고,
      // 그 표를 보고 다음 판단을 한다.
      const fresh = await fetch("/api/admin/wiki", { cache: "no-store" });
      if (fresh.ok) setRows(((await fresh.json()) as { companies: AdminWikiCompany[] }).companies);
    } catch {
      setMessage({ kind: "error", text: "API에 못 붙었어요" });
    } finally {
      setBusy(null);
    }
  }

  const n = (v: number) => v.toLocaleString("ko-KR");

  if (rows.length === 0) {
    return <p className={a.note}>세워진 위키가 없어요. 파일을 올리면 여기 생겨요.</p>;
  }

  return (
    <>
      <form className={form.form} onSubmit={(e) => e.preventDefault()}>
        <input
          type="password"
          placeholder="실행 토큰"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          aria-label="실행 토큰"
        />
      </form>

      <div className={a.wrap}>
        <table className={a.table}>
          <thead>
            <tr>
              <th>회사</th>
              <th className={a.num}>파일</th>
              <th className={a.num}>청크</th>
              <th className={a.num}>사실</th>
              <th className={a.num}>값</th>
              <th className={a.num}>자리</th>
              <th>마지막 올린 때</th>
              <th className={a.num}>안 지우는 것</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Row
                key={r.company_id}
                row={r}
                n={n}
                asking={asking === r.company_id}
                busy={busy === r.company_id}
                locked={!token || busy !== null}
                onAsk={() => setAsking(r.company_id)}
                onCancel={() => setAsking(null)}
                onPurge={() => purge(r)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {message && (
        <p
          className={`${form.message} ${
            message.kind === "error" ? form.messageError : form.messageInfo
          }`}
        >
          {message.text}
        </p>
      )}
    </>
  );
}

function Row({
  row,
  n,
  asking,
  busy,
  locked,
  onAsk,
  onCancel,
  onPurge,
}: {
  row: AdminWikiCompany;
  n: (v: number) => string;
  asking: boolean;
  busy: boolean;
  locked: boolean;
  onAsk: () => void;
  onCancel: () => void;
  onPurge: () => void;
}) {
  return (
    <>
      <tr>
        <td>
          <b>{row.name ?? "이름 없음"}</b>
          <div className={styles.id}>
            <code>{row.company_id}</code>
            {row.name === null && <span className={a.muted}> — CLI 로 만든 회사예요</span>}
          </div>
        </td>
        <td className={a.num}>{n(row.files)}</td>
        <td className={a.num}>{n(row.chunks)}</td>
        <td className={a.num}>{n(row.facts)}</td>
        <td className={a.num}>{n(row.values)}</td>
        <td className={a.num}>{n(row.nodes)}</td>
        <td className={a.num}>{row.uploaded_at ? when(row.uploaded_at) : "—"}</td>
        {/* **안 지우는 것을 같은 표에 적는다.** 안 적으면 남은 초안이 고장으로 읽힌다 */}
        <td className={a.num}>
          {row.drafts || row.fits ? (
            <span className={a.muted}>
              초안 {n(row.drafts)} · 판정 {n(row.fits)}
            </span>
          ) : (
            <span className={a.muted}>—</span>
          )}
        </td>
        <td className={styles.act}>
          {!asking && (
            <button
              type="button"
              className={styles.danger}
              onClick={onAsk}
              disabled={locked}
              title={locked ? "실행 토큰을 먼저 입력하세요" : undefined}
            >
              지워요
            </button>
          )}
        </td>
      </tr>

      {asking && (
        <tr>
          <td colSpan={9} className={styles.confirm}>
            <b>{label(row)} 위키를 지워요.</b> 파일 {n(row.files)}건과 사실 {n(row.facts)}건,
            올린 원본까지 없어지고 <b>되돌릴 수 없어요.</b>
            {(row.drafts > 0 || row.fits > 0) && (
              <>
                {" "}
                초안 {n(row.drafts)}건과 판정 {n(row.fits)}건은 그대로 남아요 — 초안은 공고
                화면의 「초기화」가 지워요.
              </>
            )}
            <span className={styles.buttons}>
              <button type="button" className={styles.danger} onClick={onPurge} disabled={busy}>
                {busy ? "지우는 중이에요" : "지워요"}
              </button>
              <button type="button" className={styles.quiet} onClick={onCancel} disabled={busy}>
                그만둘게요
              </button>
            </span>
          </td>
        </tr>
      )}
    </>
  );
}

function label(row: AdminWikiCompany): string {
  return row.name ?? row.company_id;
}

/** **날짜 계산을 화면이 안 한다.** 서버가 준 ISO 를 그대로 자른다 — `days_left` 를
 *  서버가 만드는 것과 같은 규칙이고, 여기는 운영 화면이라 원본 값이 더 쓸모 있다. */
function when(iso: string): string {
  return iso.slice(0, 16).replace("T", " ");
}
