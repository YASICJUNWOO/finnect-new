import Link from "next/link";
import { notFound } from "next/navigation";
import { FormFill } from "@/components/FormFill";
import { FIXTURES } from "@/lib/fixtures/documents";
import styles from "./page.module.css";

/** 신청서 쓰기 — SPEC §5.2 S4(문서 · F6).
 *
 * **픽스처로 먼저 선다.** 글로 쓰는 양식(`narrative`)이 DB 에 0건이라
 * 실제 공고에 붙이면 칸 이름만 뜬다 — `document_item` 41,330개가 전부 `field` 고
 * `instruction`·`number`·`limit_text` 가 셋 다 0건이다(2026-08-19 실측).
 * 서술형 판별(plan/11 T-0036)이 붙으면 `FIXTURES[case]` 자리가
 * `GET /api/notices/{...}/documents` 로 바뀐다. 타입이 같아서 화면은 안 고친다.
 *
 * 옆 화면(`../`)은 **무슨 서류를 내나**를 읽기로 보여 준다. 여기는 **그 안에 뭘 쓰나**다. */

const CASES: { key: string; label: string; why: string }[] = [
  { key: "pohang", label: "긴 지시문", why: "트리 2단 · 지시문 최장 2,031자" },
  { key: "ai", label: "최악의 밀도", why: "쓰는 항목 67개 · 채울 칸 199개" },
  { key: "empty", label: "양식 없음", why: "공고 셋 중 하나가 여기다" },
];

export function generateStaticParams() {
  return CASES.map((c) => ({ case: c.key }));
}

export default async function WritePage({
  params,
}: {
  params: Promise<{ case: string }>;
}) {
  const { case: key } = await params;
  const data = FIXTURES[key];
  if (!data) notFound();

  return (
    <article className={styles.page}>
      <p className={styles.kicker}>표본으로 보는 중이에요</p>
      <h1 className={styles.title}>{data.notice.title}</h1>

      <nav className={styles.cases} aria-label="표본 고르기">
        {CASES.map((c) => (
          <Link
            key={c.key}
            href={`/documents/${c.key}/write`}
            className={styles.case}
            aria-current={c.key === key ? "page" : undefined}
          >
            <span className={styles.caseLabel}>{c.label}</span>
            <span className={styles.caseWhy}>{c.why}</span>
          </Link>
        ))}
      </nav>

      <FormFill data={data} />

      <p className={styles.note}>
        실제 공고에서 뽑은 항목이에요. 아직 이 세 건만 있고, 나머지 공고에는 안 붙어 있어요.{" "}
        <Link className={styles.back} href={`/documents/${key}`}>
          무슨 서류를 내는지 보기
        </Link>
      </p>
    </article>
  );
}
