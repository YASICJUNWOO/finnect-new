import Link from "next/link";
import { notFound } from "next/navigation";
import { FormDocuments } from "@/components/FormDocuments";
import { FIXTURES } from "@/lib/fixtures/documents";
import styles from "./page.module.css";

/** plan/11 T-0039 — 내야 할 서류 화면.
 *
 * **아직 고정 데이터로 돈다.** 파이프라인(T-0035~T-0038)이 붙으면
 * `FIXTURES[case]` 자리가 `GET /api/notices/{id}/documents` 로 바뀐다.
 * 타입(`NoticeDocuments`)이 그때와 같아서 화면은 안 고친다.
 *
 * 순서를 뒤집은 이유는 계획에 적었다 — 화면이 "항목 102개를 어떻게 접을 것인가" 를
 * 먼저 물어야 그 답이 저장 모델에 들어간다. */

const CASES: { key: string; label: string; why: string }[] = [
  { key: "pohang", label: "긴 지시문", why: "트리 2단 · 지시문 최장 2,031자" },
  { key: "ai", label: "최악의 밀도", why: "최상위 67개 · 채울 칸 199개" },
  { key: "empty", label: "양식 없음", why: "공고 셋 중 하나가 여기다" },
];

export function generateStaticParams() {
  return CASES.map((c) => ({ case: c.key }));
}

export default async function DocumentsPreviewPage({
  params,
}: {
  params: Promise<{ case: string }>;
}) {
  const { case: key } = await params;
  const data = FIXTURES[key];
  if (!data) notFound();

  // `(product)/layout.tsx` 가 이미 <main> 을 갖는다. 겹치지 않게 article 을 쓴다.
  return (
    <article className={styles.page}>
      <p className={styles.kicker}>표본으로 보는 중이에요</p>
      <h1 className={styles.title}>{data.notice.title}</h1>

      <nav className={styles.cases} aria-label="표본 고르기">
        {CASES.map((c) => (
          <Link
            key={c.key}
            href={`/documents/${c.key}`}
            className={styles.case}
            aria-current={c.key === key ? "page" : undefined}
          >
            <span className={styles.caseLabel}>{c.label}</span>
            <span className={styles.caseWhy}>{c.why}</span>
          </Link>
        ))}
      </nav>

      <FormDocuments data={data} />

      {/* 아직 없는 것을 있는 척하지 않는다 */}
      <p className={styles.note}>
        실제 공고에서 뽑은 값이에요. 아직 이 세 건만 있고, 나머지 공고에는 안 붙어 있어요.
      </p>
    </article>
  );
}
