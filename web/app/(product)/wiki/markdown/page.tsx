import Link from "next/link";
import { notFound } from "next/navigation";
import { CopyButton } from "@/components/CopyButton";
import { currentCompany, getWikiMarkdown } from "@/lib/wiki";
import styles from "./page.module.css";

type Search = { company?: string };

/** 위키 전부를 마크다운 한 덩어리로.
 *
 * **저장된 파일이 아니다.** 서버가 매번 만든다 — 마크다운은 저장소가 아니라 뷰다
 * (plan/12 `구상도와의 차이`). 사실이 `wiki_fact` 에 있는데 같은 내용을 마크다운으로도
 * 들고 있으면 둘 중 하나가 먼저 낡는다.
 *
 * **F1-6(밖으로 꺼내기)이 아니다.** 저기는 노드마다 `.md` 파일 하나로 떨어져 옵시디언
 * 볼트가 되는 것이고 여기는 한 덩어리다. 그래서 내려받기 버튼이 없고 복사만 있다. */
export default async function WikiMarkdownPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const company = await currentCompany(sp.company);
  const body = await getWikiMarkdown(company);

  // 아직 아무것도 없으면 이 화면 자체가 성립하지 않는다. 빈 <pre> 를 보여 주지 않는다
  if (body === null) notFound();

  return (
    <>
      <header className={styles.head}>
        {/* 절대 경로다. `../wiki` 는 여기서 우연히 맞을 뿐이다 */}
        <Link
          href={sp.company ? `/wiki?company=${encodeURIComponent(company)}` : "/wiki"}
          className={styles.back}
        >
          ← 내 사업
        </Link>
        <h1 className={styles.title}>마크다운</h1>
        <p className={styles.sub}>
          위키를 그대로 옮긴 글이에요. 복사해서 다른 곳에 붙여 넣을 수 있어요.
        </p>
        <CopyButton text={body} label="전체 복사" />
      </header>

      <pre className={styles.body}>{body}</pre>
    </>
  );
}
