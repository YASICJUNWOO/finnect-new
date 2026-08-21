import Link from "next/link";
import { notFound } from "next/navigation";
import { FormFill } from "@/components/FormFill";
import { getNotice, getNoticeDocuments } from "@/lib/api";
import { fromApi } from "@/lib/documents";
import styles from "./page.module.css";

/** 신청서 쓰기 — SPEC §5.2 S4(F6). **실제 공고다.**
 *
 * `/documents/<표본>/write` 가 픽스처로 먼저 세운 그 화면이고, 여기는 같은 컴포넌트에
 * DB 를 물린 것이다. 타입(`NoticeDocuments`)이 처음부터 같아서 화면을 안 고쳤다.
 *
 * **모든 공고에 항목이 뜨지는 않는다.** 서술형 판별(plan/11 T-0036)이 예산 때문에
 * 일부만 돌았다 — 안 돌아간 공고는 칸 채우기 서식만 뜨거나 "쓸 양식이 없어요" 가 된다.
 * 그것이 사실이므로 그대로 보여 준다. 픽스처를 대신 끼워 넣지 않는다.
 *
 * 옆 화면(`../`)은 **무슨 서류를 내나**를 읽기로 보여 준다. 여기는 **그 안에 뭘 쓰나**다. */
export default async function NoticeWritePage({
  params,
}: {
  params: Promise<{ source: string; id: string }>;
}) {
  const { source, id } = await params;
  const external = decodeURIComponent(id);
  const [notice, docs] = await Promise.all([
    getNotice(source, external),
    getNoticeDocuments(source, external),
  ]);
  if (!notice) notFound();

  const back = `/notices/${source}/${encodeURIComponent(external)}`;

  return (
    <article className={styles.page}>
      <Link href={back} className={styles.back}>
        ← 공고로 돌아가기
      </Link>

      <h1 className={styles.title}>{notice.title ?? "제목이 없어요"}</h1>

      {docs ? (
        <FormFill
          data={fromApi(docs, {
            id: external,
            source,
            title: notice.title ?? "",
            url: notice.detail_url ?? null,
          })}
        />
      ) : (
        /* **`null` 은 "양식이 없다"가 아니라 "모른다"다**(`lib/api.ts`). 빈 화면을
           띄우면 우리가 못 읽은 것을 공고 탓으로 돌린다. 빈 화면은 서버가 빈 목록을
           줬을 때만 `FormFill` 안에서 뜬다. */
        <p className={styles.failed}>
          서류를 지금 못 불러왔어요. 잠시 뒤에 다시 열어 주세요.{" "}
          {notice.detail_url && (
            <a className={styles.link} href={notice.detail_url}>
              공고 원문 보기
            </a>
          )}
        </p>
      )}
    </article>
  );
}
