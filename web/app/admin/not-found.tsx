import Link from "next/link";
import a from "./admin.module.css";

/** 없는 공고. **제품 쪽 `not-found.tsx` 와 문체가 다르다** —
 *  이 화면을 보는 사람은 우리이고, 해요체를 쓰지 않는다(plan/08 T-0023). */
export default function AdminNotFound() {
  return (
    <>
      <h1 className={a.h1}>없는 공고다</h1>
      <p className={a.lead}>
        출처가 <code>bizinfo</code> · <code>kstartup</code> 둘 중 하나인지, 그리고{" "}
        <code>external_id</code> 가 맞는지 본다. 아직 안 받아 온 공고일 수도 있다.
      </p>
      <p className={a.note}>
        <Link href="/admin/notices" className={a.link}>
          ← 목록
        </Link>
      </p>
    </>
  );
}
