import Link from "next/link";
import { DEFAULT_COMPANY, getProfile } from "@/lib/wiki";
import { CompanyTable } from "@/components/CompanyTable";
import styles from "./page.module.css";

type Search = { company?: string };

/** 회사 정보 (트랙 B · ADR-0056 결정 1·5).
 *
 * **그래프와 다른 화면이다.** 위키가 「이 문서가 우리 사업에 대해 뭐라고 말하나」라면
 * 여기는 「소재지·직원 수·업종은 얼마인가」다. 자격 판별(M1)이 읽는 것이 이쪽이고,
 * 그래서 **그래프가 어떻게 자라도 이 표는 안 흔들린다**.
 *
 * **열넷이 고정이라 빈 칸을 셀 수 있다.** 그게 물어볼 자리다(ADR-0028) — 트랙 A 는
 * 정답지가 없어서 이걸 못 한다. */
export default async function CompanyPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const company = sp.company?.trim() || DEFAULT_COMPANY;
  const profile = await getProfile(company);
  const upload = sp.company?.trim()
    ? `/wiki/files?company=${encodeURIComponent(sp.company.trim())}`
    : "/wiki/files";

  return (
    <>
      <header className={styles.head}>
        <div className={styles.top}>
          <h1 className={styles.title}>회사 정보</h1>
          <Link href={upload} className={styles.add}>
            파일 올리기
          </Link>
        </div>
        <p className={styles.sub}>
          맞는 공고를 고를 때 쓰는 값이에요. 빈 칸이 있으면 그만큼 못 걸러요.
        </p>

        {/* 채움 상태. **막대를 만들지 않는다**(DESIGN.md §7) — 숫자가 근거를 갖는 값이라
          * 막대로 그리면 비율처럼 읽힌다 */}
        <p className={styles.counts}>
          <span data-numeric>
            {profile.total}칸 중 <b>{profile.filled}칸</b>이 찼어요
          </span>
          {profile.conflicts > 0 && (
            <span className={styles.warn} data-numeric>
              값이 갈린 곳 {profile.conflicts}건
            </span>
          )}
        </p>
      </header>

      <CompanyTable profile={profile} upload={upload} />
    </>
  );
}
