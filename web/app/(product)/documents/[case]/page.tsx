import Link from "next/link";
import { notFound } from "next/navigation";
import { FormDocuments } from "@/components/FormDocuments";
import { FIXTURES } from "@/lib/fixtures/documents";
import styles from "./page.module.css";

/** plan/11 T-0039 — 내야 할 서류 화면. **표본 화면이고 제품 경로가 아니다.**
 *
 * 2026-08-17 파이프라인(T-0035~T-0038) 앞에 세웠고, 순서를 뒤집은 이유는 계획에 적었다 —
 * 화면이 "항목 102개를 어떻게 접을 것인가" 를 먼저 물어야 그 답이 저장 모델에 들어간다.
 *
 * **그 뒤 읽기는 계획대로 DB 로 옮겼다**(plan/README 「T-0039 화면이 픽스처에서 DB 로
 * 옮겼다」). `/notices/[source]/[id]` 가 **같은 `FormDocuments`** 에 `fromApi(docs)` 를
 * 먹인다 — 타입(`NoticeDocuments`)을 맞춰 둔 것이 그때 값을 했고, 여기는 그 컴포넌트의
 * **둘째 호출자**로 남았다. 이 라우트가 API 로 바뀔 일은 이제 없다.
 *
 * **남겨 두는 이유는 표본 셋이 일부러 고른 극단이라서다** — 지시문 2,031자 · 칸 199개 ·
 * 양식 없음. 실제 코퍼스에 그만한 입력이 없으면 레이아웃이 버티는지 볼 자리가 여기뿐이다.
 * 지우려면 `write/` · `components/FormFill.*` · `lib/fixtures/documents.ts` 와
 * `(product)/layout.tsx` 의 경로 규칙 셋이 같이 간다. */

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

      {/* 표본 화면이라 회사가 없다. 픽스처의 `sha256` 이 빈 문자열이라
          「이 양식으로 쓰기」 링크도 원본 뷰어도 안 뜬다 — 그게 맞다 */}
      <FormDocuments data={data} company="" />

      {/* 아직 없는 것을 있는 척하지 않는다 */}
      <p className={styles.note}>
        실제 공고에서 뽑은 값이에요. 아직 이 세 건만 있고, 나머지 공고에는 안 붙어 있어요.{" "}
        <Link className={styles.next} href={`/documents/${key}/write`}>
          여기에 뭘 쓰는지 보기
        </Link>
      </p>
    </article>
  );
}
