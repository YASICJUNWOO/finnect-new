import { NextResponse, type NextRequest } from "next/server";
import { COOKIE } from "@/lib/account";

/** 문 둘이 한 파일에 있다. **거는 것이 다르다.**
 *
 * - `/admin/*` — 운영 자료를 봐도 되는 사람인가([ADR-0067](../docs/adr/0067-운영-화면을-basic-으로-막는다.md)). HTTP Basic
 * - 그 밖 — 회사를 정했나([ADR-0066](../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)). 쿠키
 *
 * **합치지 않는다.** 하나는 운영자를 가리고 하나는 테스터끼리 가른다 — 테스터가
 * 입장했다고 운영 화면이 열리면 안 되고, 운영자라고 남의 위키가 열리면 안 된다.
 *
 * **`middleware.ts` 가 아니라 `proxy.ts` 다.** Next 16 이 그 파일 이름을 폐기하고
 * 이것으로 바꿨다(`node_modules/next/dist/docs/…/file-conventions/proxy.md`).
 * **Node.js 런타임이 기본이라 `process.env` 가 런타임 값이다**(v16) — 자격을 바꿀 때
 * 다시 빌드하지 않아도 되고, 이는 `FINNECT_API` 가 빌드에 박히는 것과 반대다. */

const ADMIN_USER = process.env.ADMIN_USER;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  return pathname.startsWith("/admin") || pathname.startsWith("/api/admin")
    ? admin(req)
    : company(req);
}

/** 운영 화면·운영 라우트(ADR-0067).
 *
 * **자격이 없으면 503 이다.** 비어 있을 때 조용히 열지 않는다 — 이 화면은 사용자
 * 것이 아니라서 설정을 잊었을 때 닫히는 쪽이어야 한다(`api/app.py` 와 같은 규칙).
 *
 * **여기서 막는 것이 화면이고, API 는 제 문을 따로 갖는다.** 여길 통과해도 서버가
 * `Authorization` 을 다시 본다(`require_admin`) — 한 겹이 뚫려도 다른 겹이 남는다. */
function admin(req: NextRequest) {
  if (!ADMIN_USER || !ADMIN_PASSWORD) {
    return new NextResponse("이 배포에 운영 자격이 설정돼 있지 않아요", { status: 503 });
  }
  if (basicOk(req.headers.get("authorization"))) return NextResponse.next();

  // **`WWW-Authenticate` 가 있어야 브라우저가 묻는다.** 없으면 그냥 401 화면이다
  return new NextResponse("운영 자격이 필요해요", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="finnect admin", charset="UTF-8"' },
  });
}

/** `Authorization: Basic <base64(user:pass)>` 를 대조한다.
 *
 * **둘 다 비교하고 중간에 안 빠져나온다** — 아이디에서 먼저 돌아서면 "그 아이디는
 * 있다"가 응답 시간에 새어 나온다. **깨진 base64 에서 던지지 않는다** — 사람이 치는
 * 값이라 실제로 들어오고, 던지면 401 이 아니라 500 이 난다. */
function basicOk(header: string | null): boolean {
  const [scheme, raw] = (header ?? "").split(" ");
  if (scheme?.toLowerCase() !== "basic" || !raw) return false;
  let decoded: string;
  try {
    decoded = Buffer.from(raw, "base64").toString("utf8");
  } catch {
    return false;
  }
  const at = decoded.indexOf(":");
  if (at < 0) return false;
  return (
    same(decoded.slice(0, at), ADMIN_USER!) && same(decoded.slice(at + 1), ADMIN_PASSWORD!)
  );
}

/** 길이를 먼저 보고 나서 전체를 훑는다. `===` 는 다른 글자에서 멈춰서 맞은 글자 수가
 *  응답 시간에 새어 나온다(`api/app.py` 가 `compare_digest` 를 쓰는 것과 같은 이유). */
function same(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** 베타 입장 게이트(ADR-0066).
 *
 * **막는 것은 사고이지 공격이 아니다.** 쿠키를 손으로 고치면 남의 위키가 열린다 —
 * API 는 여전히 부르는 쪽이 말하는 `company_id` 를 그대로 믿는다(ADR-0066 결정 4).
 * 여기서 막는 것은 **「회사를 안 정한 채로 회사가 필요한 화면에 들어가는 것」** 하나다.
 * 그대로 두면 `DEFAULT_COMPANY`(`c_dasiro`)로 조용히 떨어지고, **그 실패가 오류가
 * 아니라 그럴듯한 화면으로 나타난다** — 테스터 셋의 사실이 한 위키에 섞인다. */
function company(req: NextRequest) {
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

/** **이 목록이 두 문의 정본이다.** 위 함수들은 어느 문인지만 가르고 목록을 다시 안 본다.
 *
 * 회사가 있어야 뜻이 서는 화면 셋과 운영 자리 둘이다. **공고 목록(`/`)과 상세는 여기
 * 없다**(ADR-0066 결정 5) — 회사 없이도 도는 화면이라 처음 링크를 받은 사람이
 * 로그인부터 강요당하지 않는다. `/notices/…/write` 만 걸려서, 상세에서 「쓰기」를
 * 누를 때 게이트를 만난다.
 *
 * **`/api/admin/*` 이 들어 있다**(ADR-0067). 화면만 막으면 라우트 핸들러가 그대로
 * 열려 있어서 `POST /api/admin/ingest/run/…` 을 직접 칠 수 있다. 제품 쪽 `/api/*` 는
 * 여기 없다 — 걸면 올리기가 리다이렉트를 받아 HTML 을 JSON 으로 읽고 죽는다.
 *
 * `:path*` 가 **0개 이상**이라 `/wiki`·`/admin` 자신도 걸린다(proxy.md «source path
 * patterns» 3). */
export const config = {
  matcher: [
    "/wiki/:path*",
    "/company/:path*",
    "/notices/:source/:id/write",
    "/admin/:path*",
    "/api/admin/:path*",
  ],
};
