import { EnterForm } from "./EnterForm";
import styles from "./page.module.css";

/** 베타 입장([ADR-0066](../../../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **`(product)` 그룹 밖에 있다.** 저 껍데기는 3축과 「내 사업」을 그리는데, 여기 온
 * 사람은 아직 자기 사업이 없다 — 갈 수 없는 곳으로 가는 문 셋을 보여 주는 화면이 된다.
 *
 * **회원가입 화면이 아니다.** 폼 하나에 버튼 하나이고, 처음 보는 이름이면 만들고
 * 아는 이름이면 대조한다(ADR-0066 결정 1). 「이미 가입하셨나요?」를 사람이 기억하게
 * 만들지 않는다. */
export default async function EnterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const sp = await searchParams;

  return (
    <main className={styles.page}>
      <div className={styles.box}>
        <header className={styles.head}>
          <span className={styles.brand}>
            <i className={styles.mark} aria-hidden />
            라스트마일
          </span>
          <h1 className={styles.title}>내 사업 이름을 알려 주세요</h1>
          <p className={styles.sub}>
            올린 파일과 위키를 이 이름으로 찾아요. 다음에 올 때 같은 이름과 비밀번호를
            적으면 그대로 열려요.
          </p>
        </header>

        <EnterForm next={sp.next} />
      </div>
    </main>
  );
}
