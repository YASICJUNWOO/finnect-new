import Link from "next/link";
import { currentCompany, getWiki } from "@/lib/wiki";
import { ExitAccount } from "@/components/ExitAccount";
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
        {/* **찬 자리 수를 여기서 안 적는다**(2026-08-24). 그래프 가운데가 이미
          * `{filled}/{total}` 을 들고 있어서(`WikiGraph` 의 `.hubCount`) 같은 숫자가
          * 한 화면에 두 번 섰다 — `DESIGN.md` §2 가 「찬 자리/전체」를 글자로 서는
          * 둘 중 하나로 꼽은 그 자리가 그래프 쪽이다.
          *
          * **갈 자리를 못 찾은 것은 남는다.** 저건 그래프에 점이 없어서 여기서
          * 말하지 않으면 아무도 말하지 않는다(`Custom/검토 대기`).
          *
          * 막대를 만들지 않는다 — 숫자가 근거를 갖는 값이라 막대로 그리면 비율처럼
          * 읽히고, 그러면 §7 이 막은 것과 같은 물건이 된다 */}
        {wiki.review > 0 && (
          <p className={styles.counts}>
            <span data-numeric>갈 자리를 못 찾은 것 {wiki.review}건</span>
          </p>
        )}

        {/* 다른 이름으로 들어가기(ADR-0066). **상단 막대가 아니라 여기 있다** —
          * 저 껍데기는 `fc` 쿠키를 못 읽어서(`httpOnly`) 아직 안 들어온 사람에게도
          * 「나가기」를 보여 주게 된다. 이 화면은 게이트가 걸려 있다. */}
        <p className={styles.exit}>
          <ExitAccount />
        </p>
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
