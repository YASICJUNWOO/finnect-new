import IngestCard from "@/components/IngestCard";
import { type Run, getAdminIngest } from "@/lib/admin";
import a from "../admin.module.css";

/** 수집 실행 기록과 실행 폼. Jinja2 `ingest.html` 을 옮긴 것이었는데 **버튼을
 * 2026-08-24 에 다시 붙였다**(ADR-0065). ADR-0027 이 "서버리스가 데몬 스레드를 못
 * 돌린다"로 뺐던 자리인데, ADR-0035 로 이 API 가 이 서버의 상시 프로세스가 되면서
 * 그 전제가 없어졌다.
 *
 * **폼과 진행률은 클라이언트 컴포넌트다**(`IngestCard`) — 실행 토큰을 입력받고
 * `running` 일 때만 폴링해야 해서 서버 컴포넌트로는 못 한다. 이 페이지는 처음
 * 그리기만 서버에서 하고 카드마다 그 초기값을 넘긴다. */

/** **빌드 때 굳으면 안 된다.** 실행 기록이 배포 시점으로 박히면 그 뒤에 돌린 수집이
 *  화면에 영원히 안 나타난다. `/admin/attachments` 와 같은 이유다. */
export const dynamic = "force-dynamic";
export default async function AdminIngestPage() {
  const { cards, runs } = await getAdminIngest();

  return (
    <>
      <h1 className={a.h1}>수집</h1>
      <p className={a.lead}>
        목록 API를 받아 DB에 넣는다. 첨부는 메타데이터만 담고 내려받지 않는다. 실행에는
        이 배포에 설정된 실행 토큰이 따로 필요하다 — 없으면 버튼이 503으로 막힌다.
      </p>

      <div className={a.cards}>
        {cards.map((c) => (
          <IngestCard key={c.name} initial={c} />
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
