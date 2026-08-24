import { NextResponse, type NextRequest } from "next/server";
import { COOKIE } from "@/lib/account";

/** 베타 입장 게이트([ADR-0066](../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **`middleware.ts` 가 아니라 `proxy.ts` 다.** Next 16 이 그 파일 이름을 폐기하고
 * 이것으로 바꿨다(`node_modules/next/dist/docs/…/file-conventions/proxy.md`).
 * 기능은 같고 파일 이름과 export 이름만 다르다.
 *
 * **막는 것은 사고이지 공격이 아니다.** 쿠키를 손으로 고치면 남의 위키가 열린다 —
 * API 는 여전히 부르는 쪽이 말하는 `company_id` 를 그대로 믿는다(ADR-0066 결정 4).
 * 여기서 막는 것은 **「회사를 안 정한 채로 회사가 필요한 화면에 들어가는 것」** 하나다.
 * 그대로 두면 `DEFAULT_COMPANY`(`c_dasiro`)로 조용히 떨어지고, **그 실패가 오류가
 * 아니라 그럴듯한 화면으로 나타난다** — 테스터 셋의 사실이 한 위키에 섞인다. */
export function proxy(req: NextRequest) {
  // **`?company=` 가 있으면 안 막는다**(ADR-0066 결정 6). 데모 링크(`c_dasiro`·
  // `c_narin`)와 이 커밋 이전의 모든 주소가 그대로 산다.
  if (req.nextUrl.searchParams.get("company")?.trim()) return NextResponse.next();
  if (req.cookies.get(COOKIE)?.value) return NextResponse.next();

  // **어디로 가려던 것인지 들고 간다.** 입장한 뒤 첫 화면으로 떨구면 방금 누른
  // 것을 사용자가 다시 찾아야 한다.
  const to = req.nextUrl.clone();
  const back = req.nextUrl.pathname + (req.nextUrl.search || "");
  to.pathname = "/enter";
  to.search = "";
  to.searchParams.set("next", back);
  return NextResponse.redirect(to);
}

/** 회사가 있어야 뜻이 서는 화면. **이 목록이 게이트의 정본이다** — 위 함수는 경로를
 * 다시 안 본다. 두 곳에 적으면 한 곳이 낡고, 그때 게이트가 통과되는데 화면은
 * 회사를 못 찾는다.
 *
 * **공고 목록(`/`)과 상세는 여기 없다**(ADR-0066 결정 5). 회사 없이도 도는 화면이라
 * 처음 링크를 받은 사람이 로그인부터 강요당하지 않는다. **`/notices/…/write` 만
 * 걸린다** — 상세에서 「쓰기」를 누를 때 게이트를 만나고, 그때는 무엇을 하려는지
 * 사용자가 안다.
 *
 * **`/api` 와 정적 파일이 안 걸린다.** 목록이 정확해서 제외 규칙이 필요 없다 —
 * 라우트 핸들러가 리다이렉트되면 올리기가 HTML 을 200 으로 받아 JSON 파싱에서
 * 죽는다(`lib/api.ts` 가 `redirect: "manual"` 을 쓰는 것과 같은 함정).
 *
 * `:path*` 가 **0개 이상**이라 `/wiki` 자신도 걸린다(proxy.md «source path patterns» 3). */
export const config = {
  matcher: ["/wiki/:path*", "/company/:path*", "/notices/:source/:id/write"],
};
