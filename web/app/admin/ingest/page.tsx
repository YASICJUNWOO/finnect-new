import { type Run, getAdminIngest } from "@/lib/admin";
import a from "../admin.module.css";
import styles from "./page.module.css";

/** 수집 실행 기록. Jinja2 `ingest.html` 을 옮긴 것이고 **버튼은 안 옮겼다.**
 *
 * 수집은 응답보다 오래 사는 데몬 스레드로 돈다. K-Startup 전량이 149회이고
 * 첨부 해독은 30분짜리다. 서버리스 함수의 일이 아니라서 실행 경로는 로컬에 남았다
 * (ADR-0026 · ADR-0027). **화면이 그 사실을 숨기지 않고 적는다.**
 *
 * 진행률(`jobs.Progress`)과 '수집 중' 표시도 같이 빠졌다. 그 값은 수집을 돌리는
 * 프로세스 안에서만 사는 것이라 여기서 알 수 없다. 없는 것을 있는 척하지 않는다. */

/** **빌드 때 굳으면 안 된다.** 실행 기록이 배포 시점으로 박히면 그 뒤에 돌린 수집이
 *  화면에 영원히 안 나타난다. `/admin/attachments` 와 같은 이유다. */
export const dynamic = "force-dynamic";
export default async function AdminIngestPage() {
  const { cards, runs } = await getAdminIngest();
  const n = (v: number) => v.toLocaleString("ko-KR");

  return (
    <>
      <h1 className={a.h1}>수집</h1>
      <p className={a.lead}>
        목록 API를 받아 DB에 넣는다. 첨부는 메타데이터만 담고 내려받지 않는다.
      </p>

      {/* 실행이 어디에 사는지 먼저 적는다. 버튼을 찾다가 없다고 여기지 않게 한다 */}
      <div className={styles.where}>
        <p className={styles.whereLead}>이 화면은 기록만 읽는다. 수집은 로컬에서 돌린다.</p>
        <pre className={a.pre}>
          uv run python -m finnect.ingest --source bizinfo{"\n"}
          uv run python -m finnect.ingest --source kstartup{"\n"}
          uv run uvicorn finnect.admin.app:app --reload{"   "}# :8000 /ingest — 버튼과 진행률
        </pre>
        <p className={a.note}>
          CLI로 돌린 것도 아래 같은 표에 남는다. <code>trigger</code> 값만 다르다.
        </p>
      </div>

      <div className={a.cards}>
        {cards.map((c) => (
          <div key={c.name} className={a.card}>
            <h2 className={a.cardTitle}>
              {c.label} <span className={a.tag}>{c.name}</span>
            </h2>
            <p className={a.note}>
              실측 <span data-numeric>{n(c.expected)}</span>건 · {c.requests}
            </p>

            <div className={a.stored}>
              {n(c.stored)}
              <span className={a.storedUnit}>건 저장됨</span>
            </div>

            {c.last ? (
              <p className={a.note}>
                마지막 {stamp(c.last.started_at)} <StatusPill status={c.last.status} /> ·{" "}
                {c.last.elapsed}
                {c.last.status === "ok" && (
                  <>
                    {" "}
                    · 신규 <span data-numeric>{n(c.last.inserted)}</span> · 변경{" "}
                    <span data-numeric>{n(c.last.changed)}</span>
                  </>
                )}
                {c.last.truncated && (
                  <>
                    <br />
                    <span className={a.warn}>
                      ⚠ 맛보기였다 — <span data-numeric>{n(c.last.items)}</span>건만 받았다
                      {c.last.expected && <> (전량 {n(c.last.expected)})</>}
                    </span>
                  </>
                )}
              </p>
            ) : (
              <p className={a.note}>아직 한 번도 안 돌렸다.</p>
            )}

            <p className={styles.cardNote}>{c.note}</p>
          </div>
        ))}
      </div>

      <h2 className={a.h2}>실행 기록</h2>
      <div className={a.wrap}>
        <table className={a.table}>
          <thead>
            <tr>
              <th>시작</th>
              <th>출처</th>
              <th>경로</th>
              <th>상태</th>
              <th className={a.num}>걸린 시간</th>
              <th className={a.num}>응답</th>
              <th className={a.num}>공고</th>
              <th className={a.num}>신규</th>
              <th className={a.num}>변경</th>
              <th className={a.num}>그대로</th>
              <th>남긴 것</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={11} className={a.empty}>
                  아직 실행 기록이 없다.
                </td>
              </tr>
            ) : (
              runs.map((r) => <RunRow key={r.id} r={r} />)
            )}
          </tbody>
        </table>
      </div>

      <p className={a.note}>
        같은 수집을 두 번 돌려도 건수는 같다. 콘텐츠 해시가 같으면 최종 확인 시각만 올린다.
      </p>
    </>
  );
}

function RunRow({ r }: { r: Run }) {
  const n = (v: number) => v.toLocaleString("ko-KR");
  return (
    <tr>
      <td className={`${a.num} ${a.muted}`}>{stamp(r.started_at)}</td>
      <td>
        <span className={a.tag}>{r.source}</span>
        {r.only_open && <> <span className={a.tag}>모집중만</span></>}
        {r.item_limit && (
          <>
            {" "}
            <span className={`${a.tag} ${a.warn}`}>{n(r.item_limit)}건만</span>
          </>
        )}
      </td>
      <td className={a.muted}>{r.trigger}</td>
      <td>
        <StatusPill status={r.status} />
      </td>
      <td className={`${a.num} ${a.muted}`}>{r.elapsed}</td>
      <td className={a.num}>{r.pages}</td>
      <td className={a.num}>{n(r.items)}</td>
      <td className={a.num}>{n(r.inserted)}</td>
      <td className={a.num}>{n(r.changed)}</td>
      <td className={a.num}>{n(r.unchanged)}</td>
      <td>
        {r.error ? (
          <span className={a.bad}>{r.error}</span>
        ) : (
          r.report && <pre className={a.pre}>{r.report}</pre>
        )}
        {/* 처음 보는 필드는 extra 로 흘렀다. **조용히 버리지 않았다는 것을 여기서 말한다** */}
        {Object.keys(r.unknown_fields).length > 0 && (
          <div className={a.warn}>
            ⚠ 처음 보는 필드 → extra:{" "}
            {Object.entries(r.unknown_fields)
              .map(([k, v]) => `${k}(${v})`)
              .join(", ")}
          </div>
        )}
      </td>
    </tr>
  );
}

/** 실행 상태. `running` 은 배포본에서 **거짓일 수 있다** — 프로세스가 죽으면
 *  `runs.reap()` 이 정리하는데 그건 로컬 admin 이 뜰 때 돈다. 그래서 애매한 색이다. */
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
