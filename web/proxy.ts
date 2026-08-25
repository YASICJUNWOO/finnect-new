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

/** **2026-08-25 임시 차단. 셋째 문이고 앞의 둘보다 먼저 닫힌다.**
 *
 * 배포본을 잠깐 아무에게도 안 보이게 해야 했다. Vercel Deployment Protection 으로
 * 막으려 했는데 **Hobby 플랜이 프로덕션 배포에는 그것을 안 걸어 준다**
 * (`invalid_sso_protection` · 프리뷰까지만 걸린다). 프로젝트를 지우면 환경변수 넷과
 * `finnect-web.vercel.app` 이름을 잃고, 배포 하나만 지우면 남은 프로덕션 배포로
 * 넘어가는지가 확실하지 않다. **확실한 것은 코드뿐이라 여기서 닫는다.**
 *
 * **`process.env` 로 안 뺐다.** Vercel 은 환경변수를 배포 하나에 묶어서 넣기 때문에
 * (`docs/deploy.md` §5 «값 넷») 값을 바꿔도 재배포가 필요하다 — 환경변수로 만들어도
 * 껐다 켜는 비용이 같은데 **지금 열려 있는지가 코드에 안 보이게** 된다.
 *
 * **푸는 법은 이 커밋을 revert 하는 것이다.** `CLOSED` 만 `false` 로 바꾸면 아래
 * `config.matcher` 가 넓혀진 채로 남아서 정적 파일이 전부 프록시를 탄다.
 *
 * 타입을 `boolean` 으로 적은 것은 의도다 — `true` 리터럴로 좁혀지면 아래 두 문이
 * 도달 불가 코드가 되어 린트가 문다. */
const CLOSED: boolean = true;

export function proxy(req: NextRequest) {
  if (CLOSED) return closed();

  const { pathname } = req.nextUrl;
  return pathname.startsWith("/admin") || pathname.startsWith("/api/admin")
    ? admin(req)
    : company(req);
}

/** **`no-store` 가 있어야 한다.** 없으면 Vercel 엣지와 브라우저가 이 응답을 들고
 *  있어서, 다시 열어도 그 사람에게는 계속 이 화면이 뜬다.
 *
 *  **503 이다.** 404 는 「이런 주소는 없다」이고 이건 「지금은 없다」다. */
function closed(): NextResponse {
  return new NextResponse(CLOSED_PAGE, {
    status: 503,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "retry-after": "172800",
    },
  });
}

/** **한 파일로 끝나야 한다.** matcher 가 정적 파일까지 잡아서 `_next/` 의 CSS 와
 *  웹폰트가 안 나간다 — 스타일을 밖에 두면 이 화면만 스타일 없이 뜬다. 그래서
 *  값을 토큰 이름이 아니라 실값으로 적는다(`DESIGN.md` §2 · `app/tokens.css`).
 *
 *  **서체는 대부분 시스템 고딕으로 뜬다.** IBM Plex Sans KR 을 스택 앞에 적어 두지만
 *  이 응답에는 웹폰트가 안 실려서, 기기에 깔린 사람만 그것으로 본다. */
const CLOSED_PAGE = `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>준비 중이에요 — 라스트마일</title>
<style>
  :root { color-scheme: light }
  body {
    margin: 0; min-height: 100dvh; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center;
    padding: 24px calc(24px + env(safe-area-inset-left)) 24px calc(24px + env(safe-area-inset-right));
    background: #f7f7f8; color: #222;
    font-family: "IBM Plex Sans KR", system-ui, -apple-system, sans-serif;
    font-size: 16px; line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
  main { max-width: 32rem }
  .brand { display: flex; align-items: center; gap: 8px; font-weight: 500 }
  .mark { width: 18px; height: 18px; border-radius: 6px; background: #222 }
  h1 { margin: 24px 0 12px; font-size: 20px; font-weight: 600; line-height: 1.3 }
  p { margin: 0; color: #6b7280 }
</style>
</head>
<body>
<main>
  <span class="brand"><i class="mark" aria-hidden="true"></i>라스트마일</span>
  <h1>준비 중이에요</h1>
  <p>지금은 잠시 닫아 뒀어요. 다시 열리면 이 주소로 그대로 들어올 수 있어요.</p>
</main>
</body>
</html>`;

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
 * 여기서 막는 것은 **「회사를 안 정한 채로 화면에 들어가는 것」** 하나다. 그대로 두면
 * `DEFAULT_COMPANY`(`c_dasiro`)로 조용히 떨어지고, **그 실패가 오류가 아니라 그럴듯한
 * 화면으로 나타난다** — 테스터 셋의 사실이 한 위키에 섞이고, 입장 안 한 사람은 남의
 * 추천을 자기 것으로 본다. **뒤쪽이 실제로 배포본에서 일어나고 있었다**(ADR-0068). */
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
 * **2026-08-24 화면 전부로 넓혔다**([ADR-0068](../docs/adr/0068-게이트를-화면-전부로-넓힌다.md)이
 * ADR-0066 결정 5 를 대체). 그전에는 공고 목록(`/`)과 상세가 게이트 밖이었다 —
 * 「처음 링크를 받은 사람이 로그인부터 강요당하지 않게」가 이유였는데, **그 화면들이
 * 회사를 안 쓰는 것이 아니라 `DEFAULT_COMPANY` 로 떨어지고 있었다.** 입장 안 한
 * 사람이 남의(`c_dasiro`) 추천을 보는 것이 그 결정의 실제 값이었다.
 *
 * 빼는 것 넷이고 이유가 다 다르다.
 *
 * | 뺀 것 | 왜 |
 * |---|---|
 * | `enter` | 게이트 자신이다. 넣으면 자기 자신으로 무한히 돈다 |
 * | `api/` | 제품 API. 걸면 올리기가 리다이렉트를 받아 HTML 을 JSON 으로 읽고 죽는다 |
 * | `_next/` · 그림 · `manifest` · `rhwp/` | 정적 파일. 걸면 로그인 전에 CSS 와 아이콘이 안 나온다 |
 * | (`api/admin/` 은 다시 넣는다) | 위에서 `api/` 로 빠지므로 따로 적는다 — 화면만 막으면 라우트 핸들러를 직접 칠 수 있다(ADR-0067) |
 *
 * **`/admin/*` 을 따로 안 적는다.** 아래 catch-all 이 이미 잡고, `proxy()` 가 경로를
 * 보고 Basic 쪽으로 보낸다. 두 번 적으면 한쪽만 고쳐지는 날이 온다. */
export const config = {
  // **2026-08-25 임시 차단(위 `CLOSED`)이 이 목록을 덮었다.** 원래 두 줄은 바로
  // 아래에 주석으로 남아 있고 커밋을 revert 하면 돌아온다. 넓히는 이유는 화면만으로는
  // 안 닫히기 때문이다 — 원래 목록은 `api/` 와 정적 파일을 빼므로 `/api/account` 와
  // `/icon-192.png` 가 그대로 나간다.
  matcher: ["/", "/:path*"],
  // matcher: [
  //   "/api/admin/:path*",
  //   "/((?!api/|_next/|enter|rhwp/|icon|apple-icon|manifest|favicon).*)",
  // ],
};
