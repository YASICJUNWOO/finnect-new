import Link from "next/link";
import { notFound } from "next/navigation";
import { FormFill } from "@/components/FormFill";
import { FIXTURES } from "@/lib/fixtures/documents";
import styles from "./page.module.css";

/** 신청서 쓰기 — SPEC §5.2 S4(문서 · F6). **표본 화면이고 제품 경로가 아니다.**
 *
 * 옆 화면(`../`)은 **무슨 서류를 내나**를 읽기로 보여 준다. 여기는 **그 안에 뭘 쓰나**다.
 *
 * **읽기와 달리 쓰기는 갈라졌다.** 실제 쓰기는 `/notices/[source]/[id]/write` 이고 저기는
 * `WritePanes`·`DraftView` 를 쓴다 — `FormFill` 이 양식의 **빈 칸**을 보여 주고 `DraftView`
 * 가 **쓴 초안**을 보여 주므로 다른 물건이다(`DraftView.tsx` 머리). 그래서 **`FormFill` 은
 * 이 라우트에서만 부른다** — 여기를 지우면 그 컴포넌트가 같이 죽는다.
 *
 * ~~글로 쓰는 양식(`narrative`)이 DB 에 0건이라 픽스처로 먼저 선다~~ — **그 전제는 깨졌다.**
 * 2026-08-24 로컬 실측이 `document` 1,067(`narrative` 20) · `document_item` 4,691
 * (`field` 3,881 · `narrative` 810) · `instruction` 213 · `number` 810 · `limit_text` 18 이다.
 * 넷 다 0 이 아니므로 **데이터 공백은 더 이상 이 화면의 근거가 아니다.**
 *
 * 남는 근거는 하나다 — 표본 셋이 일부러 고른 극단이라서(지시문 2,031자 · 칸 199개 · 양식
 * 없음) 실제 코퍼스에 그만한 입력이 없으면 레이아웃이 버티는지 볼 자리가 여기뿐이다. */

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
