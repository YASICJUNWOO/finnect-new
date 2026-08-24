import WikiPurgeTable from "@/components/WikiPurgeTable";
import { getAdminWiki } from "@/lib/admin";
import a from "../admin.module.css";

/** 위키 지우기([ADR-0072](https://github.com/YASICJUNWOO/finnect-new/blob/master/docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).
 *
 * **운영 화면 중 유일하게 지우는 화면이다.** 다른 셋은 세거나 받는다.
 *
 * 여기 있는 이유는 「한 번 세운 위키를 되돌릴 길이 CLI 뿐」이었기 때문이다. 시연은
 * **빈 위키에서 시작해야** 「파일을 던지면 위키가 생긴다」를 보여 줄 수 있는데, 한 번
 * 보여 주고 나면 그 회사의 위키가 서 있어서 다음 시연이 안 된다. */

/** **빌드 때 굳으면 안 된다.** `/admin/attachments` 와 같은 이유다 — 파라미터가 없어서
 *  Next 가 미리 그리려 하고, 그러면 지운 뒤에도 옛 행이 그대로 뜬다. 지우는 화면에서
 *  그것은 「안 지워졌다」로 읽힌다. */
export const dynamic = "force-dynamic";

export default async function AdminWikiPage() {
  const { companies } = await getAdminWiki();

  return (
    <>
      <h1 className={a.h1}>위키</h1>
      <p className={a.lead}>
        회사마다 세워진 사업 위키다. 지우면 그 회사가 <b>파일을 처음 올리는 상태로 돌아간다</b>
        — 시연을 다시 하려면 여기서 지운다.
      </p>

      <h2 className={a.h2}>세워진 위키</h2>
      <p className={a.note}>
        지우는 것은 파일 · 청크 · 사실 · 값 · 자리와 <b>올린 원본 파일</b>이다. CLI 의{" "}
        <code>python -m finnect.wiki --company … --purge</code> 와 같은 함수를 부른다.{" "}
        <b>되돌릴 수 없다.</b> 세우는 중이면 거절된다 — 같은 락을 잡는다.
      </p>
      <p className={a.note}>
        <b>초안과 판정은 안 지운다.</b> 사람이 고친 글이 초안에 있고(ADR-0055), 지우는
        자리는 공고 화면의 「초기화」다(ADR-0062). 판정은{" "}
        <code>match --company</code> 가 다시 만든다.
      </p>

      <WikiPurgeTable initial={companies} />
    </>
  );
}
