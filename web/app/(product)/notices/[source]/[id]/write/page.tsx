import Link from "next/link";
import { notFound } from "next/navigation";
import { DraftView } from "@/components/DraftView";
import { FormFill } from "@/components/FormFill";
import { getNotice, getNoticeDocuments } from "@/lib/api";
import { getDraft } from "@/lib/draft";
import type { Draft } from "@/lib/draft";
import { fromApi } from "@/lib/documents";
import { DEFAULT_COMPANY } from "@/lib/wiki";
import styles from "./page.module.css";

/** S4 문서 — SPEC §5.2(F6). **이 화면은 2026-08-22 까지 이름이 없었다**(ADR-0053).
 *
 * **초안이 먼저고 빈 칸이 그다음이다**(ADR-0028 · plan/21 T-0122).
 *
 * - 초안이 있으면 `DraftView` 가 **써진 글과 근거**를 보여 주고 고친 것을 저장한다
 * - 아직 없으면 「초안 쓰기」를 눌러 만든다(T-0121)
 * - 글로 쓰는 양식이 아예 없으면 `FormFill` 이 **칸 채우기 서식**을 그대로 보여 준다.
 *   그쪽은 저장이 없다 — 저장 모델이 서술형 항목(`draft_item`)에 걸려 있어서
 *   칸 채우기에는 앉을 자리가 없다. **그 사실을 화면이 말한다**
 *
 * **모든 공고에 항목이 뜨지는 않는다.** 서술형 판별(plan/11 T-0036)이 안 돈 공고는
 * 칸 채우기 서식만 뜨거나 "쓸 양식이 없어요" 가 된다. 그것이 사실이므로 그대로
 * 보여 준다. 픽스처를 대신 끼워 넣지 않는다.
 *
 * **`company` 를 주소가 말한다.** 인증이 없어서다 — `/wiki` 와 같은 규칙이고,
 * 로그인이 붙으면 셋 다 세션에서 온다. */
export default async function NoticeWritePage({
  params,
  searchParams,
}: {
  params: Promise<{ source: string; id: string }>;
  searchParams: Promise<{ company?: string }>;
}) {
  const { source, id } = await params;
  const sp = await searchParams;
  const external = decodeURIComponent(id);
  const company = sp.company?.trim() || DEFAULT_COMPANY;

  // 초안을 못 불러와도 **양식은 떠야 한다.** 셋을 같이 부르되 실패를 따로 받는다 —
  // `getNoticeDocuments` 가 배포본에서 상세를 통째로 500 으로 만든 적이 있다.
  const [notice, docs, draft] = await Promise.all([
    getNotice(source, external, company),
    getNoticeDocuments(source, external),
    safeDraft(source, external, company),
  ]);
  if (!notice) notFound();

  const back = `/notices/${source}/${encodeURIComponent(external)}?company=${encodeURIComponent(company)}`;
  // 글로 쓰는 양식이 하나도 없으면 초안이 설 자리가 없다. 그때만 빈 칸 화면이 주인이다
  const hasNarrative =
    draft !== null && (draft.documents.length > 0 || draft.pending_documents > 0);

  return (
    <article className={styles.page}>
      <Link href={back} className={styles.back}>
        ← 공고로 돌아가기
      </Link>

      <h1 className={styles.title}>{notice.title ?? "제목이 없어요"}</h1>

      {draft !== null && hasNarrative && (
        <DraftView
          initial={draft}
          source={source}
          externalId={external}
          company={company}
        />
      )}

      {/* 칸 채우기 서식. **초안이 서는 자리가 아니다** — `draft_item` 이 서술형
        * 항목에 걸려 있어서 여기 쓴 값은 저장되지 않는다. `FormFill` 이 그 사실을
        * 제 안에서 말한다. **둘을 한 컴포넌트로 합치지 않는다** */}
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
           띄우면 우리가 못 읽은 것을 공고 탓으로 돌린다. */
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

/** 초안을 못 불러오는 것과 초안이 없는 것을 가른다. **`null` 은 모른다는 뜻이다.** */
async function safeDraft(
  source: string,
  external: string,
  company: string,
): Promise<Draft | null> {
  try {
    return await getDraft(source, external, company);
  } catch (e) {
    console.error("초안을 못 불러왔다 — 양식은 그대로 띄운다", e);
    return null;
  }
}
