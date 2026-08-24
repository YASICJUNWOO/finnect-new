import { currentCompany, getProgress } from "@/lib/wiki";
import { Upload } from "@/components/Upload";
import styles from "./page.module.css";

type Search = { company?: string };

/** S1 파일 올리기(SPEC §5.2 · plan/15).
 *
 * **첫 진입 화면이라 축에 안 걸린다**(SPEC §5.1). 상단 내비 3축에 넣지 않고 '내 사업'
 * 안에서만 연다 — 흐름의 처음이지 상시 들르는 자리가 아니다.
 *
 * **누구의 위키에 올릴지는 `currentCompany()` 가 정한다**(ADR-0066). 주소가 말하면
 * (`?company=`) 그것이 이기고, 아니면 입장 게이트가 앉힌 쿠키다. S7 과 같은 규칙이다.
 *
 * 첫 진행 상태를 서버에서 받아 넘긴다. 화면이 뜨자마자 빈 상태를 그렸다가 채우면
 * 이미 올려 둔 파일이 한 박자 늦게 나타난다. */
export default async function UploadPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const company = await currentCompany(sp.company);
  const progress = await getProgress(company);

  return (
    <>
      <header className={styles.head}>
        <h1 className={styles.title}>파일 올리기</h1>
        <p className={styles.sub}>
          가진 파일을 그냥 던지세요. 무슨 파일인지 우리가 읽고, 읽은 것에서 사업
          정보를 뽑아 내 사업 위키를 세워요.
        </p>
      </header>

      <Upload company={company} initial={progress} />
    </>
  );
}
