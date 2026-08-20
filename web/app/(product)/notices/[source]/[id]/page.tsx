import Link from "next/link";
import { notFound } from "next/navigation";
import { Attachments } from "@/components/Attachments";
import { FormDocuments } from "@/components/FormDocuments";
import { Deadline } from "@/components/Deadline";
import { NotYet } from "@/components/NotYet";
import { getNotice, getNoticeDocuments } from "@/lib/api";
import { fromApi } from "@/lib/documents";
import { periodOf } from "@/lib/deadline";
import styles from "./page.module.css";

const SOURCE_NAME: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-Startup",
};

/** S5 공고 상세.
 *
 * **배점 섹션이 없다.** 시연에 `25 / 25 / 30 / 20`이 있지만 ADR-0019 와 정면으로 어긋난다.
 * 빈 섹션 넷은 자리를 지키고 "아직 없어요"로 버틴다 — 무엇이 없는지가 화면으로 보여야 한다. */
export default async function NoticeDetailPage({
  params,
}: {
  params: Promise<{ source: string; id: string }>;
}) {
  const { source, id } = await params;
  const external = decodeURIComponent(id);
  // 서류는 없어도 화면이 떠야 한다. 공고와 같이 부르되 실패를 따로 받는다.
  const [notice, docs] = await Promise.all([
    getNotice(source, external),
    getNoticeDocuments(source, external),
  ]);
  if (!notice) notFound();

  const period = periodOf(notice);
  const meta = [notice.organization, notice.supervisor, notice.category].filter(Boolean);

  return (
    <article className={styles.page}>
      <Link href="/" className={styles.back}>
        ← 공고 목록
      </Link>

      <header className={styles.head}>
        <Deadline notice={notice} />
        <h1 className={styles.title}>{notice.title ?? "제목이 없어요"}</h1>
        <p className={styles.meta}>
          {meta.length > 0 ? meta.join(" · ") : "기관을 안 알려줬어요"}
          <span className={styles.dot} aria-hidden="true">
            ·
          </span>
          <span className={styles.source}>{SOURCE_NAME[source] ?? source}</span>
        </p>
      </header>

      <dl className={styles.facts}>
        <dt>접수 기간</dt>
        <dd data-numeric>{period ?? "안 알려줬어요"}</dd>
        {notice.detail_url && (
          <>
            <dt>원문</dt>
            <dd>
              <a href={notice.detail_url} className={styles.ext}>
                공고 원문 보기
              </a>
            </dd>
          </>
        )}
      </dl>

      <section className={styles.summary} aria-labelledby="summary-title">
        <h2 id="summary-title" className={styles.sectionTitle}>
          개요
        </h2>
        {notice.summary ? (
          <div className={styles.body}>
            {notice.summary.split("\n\n").map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        ) : (
          <p className={styles.noBody}>출처가 개요를 안 줬어요. 원문을 열어 보세요.</p>
        )}
      </section>

      {docs && (
        <>
          <FormDocuments
            data={fromApi(docs, {
              id: external,
              source,
              title: notice.title ?? "",
              url: notice.detail_url ?? null,
            })}
          />
          {/* 양식이 있을 때만 문을 연다. **없는 곳으로 보내지 않는다** — 서류가 0개면
              쓰기 화면도 "쓸 양식이 없어요" 밖에 못 보여 준다.
              카피는 `/documents/<표본>` 이 쓰는 것과 같다(DESIGN.md §8.3-3). */}
          {docs.documents.length > 0 && (
            <Link
              href={`/notices/${source}/${encodeURIComponent(external)}/write`}
              className={styles.write}
            >
              여기에 뭘 쓰는지 보기
            </Link>
          )}
        </>
      )}

      <Attachments items={notice.attachments} decoded={notice.decoded_count} />

      {/* 자리는 있고 값이 없는 넷. 예시 데이터를 넣지 않는다 */}
      <div className={styles.gaps}>
        <NotYet
          title="왜 맞는지"
          why="사업 위키가 있어야 공고 취지와 대 볼 수 있어요. 아직 위키가 없어요."
        />
        <NotYet
          title="자격이 되는지"
          why="사업자 정보를 아직 안 받았어요. 받으면 못 넘는 공고는 목록에서 빼 드려요."
        />
        <NotYet
          title="어떻게 심사해요"
          why="서류에서 심사 항목을 아직 안 뽑았어요. 서류 글자는 이미 읽어 뒀어요."
        />
        <NotYet
          title="놓치기 쉬운 것"
          why="심사 항목을 뽑고 나서 알려 드릴 수 있어요."
        />
      </div>
    </article>
  );
}
