import Link from "next/link";
import { currentCompany, getWiki } from "@/lib/wiki";
import { WikiBoard } from "@/components/WikiBoard";
import styles from "./page.module.css";

type Search = { company?: string; spot?: string };

/** S7 내 사업 위키.
 *
 * **인증이 아직 없다.** 누구의 위키를 볼지 주소가 말한다 — `?company=` 없으면 기본값
 * 하나다. 로그인이 붙으면 이 인자가 사라지고 세션이 대신한다.
 *
 * **추출기가 스텁이라 픽스처 회사 밖에서는 자리만 비어서 온다**(ADR-0031). 그 사실을
 * 화면이 숨기지 않는다 — 아래 `note` 가 무엇이 뽑았는지 적는다.
 *
 * `?spot=` 은 그래프에서 고른 자리이고 값이 **기획 트리 경로**다(ADR-0052).
 * **주소에 남겨야 딥링크가 되고 새로고침해도 살아 있다.** */
export default async function WikiPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const company = await currentCompany(sp.company);
  const wiki = await getWiki(company);
  const upload = sp.company?.trim()
    ? `/wiki/files?company=${encodeURIComponent(sp.company.trim())}`
    : "/wiki/files";

  return (
    <>
      <header className={styles.head}>
        <div className={styles.top}>
          <h1 className={styles.title}>내 사업</h1>
          {/* S1 로 가는 문. **주 동작이 아니다** — 이 화면의 일은 보는 것이고 올리는 것은
            * 그 앞 단계다. 그래서 테두리만 두르고 오른쪽 끝으로 민다 */}
          <Link href={upload} className={styles.add}>
            파일 올리기
          </Link>
        </div>
        {/* **머리에 제목과 「파일 올리기」 둘만 있다**(2026-08-24). 찬 자리 수는 그래프
          * 가운데가 `{filled}/{total}` 로 들고 있고(`WikiGraph` 의 `.hubCount`),
          * 「갈 자리를 못 찾은 것」(`Custom/검토 대기` · `wiki.review`)과 「다른 이름으로
          * 들어가기」(ADR-0066)는 여기 있다가 지웠다. **값은 API 에 그대로 오고 자리는
          * 그래프에서 열린다** — 화면에서 셈을 안 하는 것이지 없어진 것이 아니다. */}
      </header>

      <WikiBoard wiki={wiki} initial={sp.spot ?? null} company={sp.company?.trim() || undefined} />

      {/* **무엇이 뽑았는지 밝힌다.** 스텁이 뽑은 값을 진짜 추출 결과처럼 보이게 두지 않는다 */}
      {wiki.extractor?.startsWith("stub") && (
        <p className={styles.note}>
          지금은 시험용 추출기가 사실을 뽑고 있어요. 준비된 예시 파일에서만 돌아요.
        </p>
      )}
    </>
  );
}
