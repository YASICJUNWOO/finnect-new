import { DEFAULT_COMPANY, getWiki } from "@/lib/wiki";
import { WikiBoard } from "@/components/WikiBoard";
import styles from "./page.module.css";

type Search = { company?: string; node?: string };

/** S7 내 사업 위키.
 *
 * **인증이 아직 없다.** 누구의 위키를 볼지 주소가 말한다 — `?company=` 없으면 기본값
 * 하나다. 로그인이 붙으면 이 인자가 사라지고 세션이 대신한다.
 *
 * **추출기가 스텁이라 픽스처 회사 밖에서는 자리만 비어서 온다**(ADR-0031). 그 사실을
 * 화면이 숨기지 않는다 — 아래 `note` 가 무엇이 뽑았는지 적는다.
 *
 * `?node=` 는 궤도에서 고른 자리다. **주소에 남겨야 딥링크가 되고 새로고침해도 살아 있다.** */
export default async function WikiPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const company = sp.company?.trim() || DEFAULT_COMPANY;
  const wiki = await getWiki(company);

  return (
    <>
      <header className={styles.head}>
        <h1 className={styles.title}>내 사업</h1>
        <p className={styles.sub}>
          올린 파일에서 뽑은 것들이에요. 값마다 어느 파일 몇 쪽에서 왔는지 볼 수 있어요.
        </p>

        {/* 채움 상태(F1-4-2). **막대를 만들지 않는다** — 숫자가 근거를 갖는 값이라
          * 막대로 그리면 비율처럼 읽히고, 그러면 §6 이 막은 것과 같은 물건이 된다 */}
        <p className={styles.counts}>
          <span data-numeric>
            자리 {wiki.total}개 중 <b>{wiki.filled}개</b>가 찼어요
          </span>
          {wiki.conflicts > 0 && (
            <span className={styles.warn} data-numeric>
              값이 갈린 곳 {wiki.conflicts}건
            </span>
          )}
          {wiki.uncategorized > 0 && (
            <span data-numeric>갈 자리를 못 찾은 것 {wiki.uncategorized}건</span>
          )}
        </p>
      </header>

      <WikiBoard wiki={wiki} initial={sp.node ?? null} company={sp.company?.trim() || undefined} />

      {/* **무엇이 뽑았는지 밝힌다.** 스텁이 뽑은 값을 진짜 추출 결과처럼 보이게 두지 않는다 */}
      {wiki.extractor?.startsWith("stub") && (
        <p className={styles.note}>
          지금은 시험용 추출기가 사실을 뽑고 있어요. 준비된 예시 파일에서만 돌아요.
        </p>
      )}
    </>
  );
}
