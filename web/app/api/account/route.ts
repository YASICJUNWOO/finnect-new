import { cookies } from "next/headers";
import { ApiError } from "@/lib/api";
import { COOKIE, COOKIE_MAX_AGE, enterAccount } from "@/lib/account";

/** 입장과 나가기([ADR-0066](../../../../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **쿠키를 굽는 유일한 자리다.** `lib/account.ts` 는 FastAPI 와의 경계이고 여기는
 * 브라우저와의 경계다 — `app/api/wiki/[company]/files/route.ts` 와 같은 자리에 있다.
 *
 * **`company_id` 를 응답 본문에 안 싣는다.** 화면이 그 값을 알 필요가 없고, 알면
 * 클라이언트 코드가 그걸 들고 다니기 시작한다 — 격리는 서버가 쿠키에서 읽는 것
 * 하나로 충분하다. 이름만 돌려준다. */
export async function POST(req: Request) {
  let body: { name?: unknown; password?: unknown };
  try {
    body = await req.json();
  } catch {
    return Response.json({ detail: "요청을 읽지 못했어요" }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name : "";
  const password = typeof body.password === "string" ? body.password : "";

  try {
    const account = await enterAccount(name, password);
    // `httpOnly` 라 스크립트가 못 읽는다. **읽을 이유도 없다** — 이 값을 쓰는 것은
    // 서버 컴포넌트뿐이다(`lib/wiki.ts` 의 `currentCompany`).
    //
    // `secure` 를 개발에서 끄는 이유는 `http://localhost` 라서다. 켜 두면 쿠키가
    // 아예 안 앉고 **입장은 성공했는데 다시 입장 화면으로 튕긴다.**
    (await cookies()).set(COOKIE, account.company_id, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: COOKIE_MAX_AGE,
      secure: process.env.NODE_ENV === "production",
    });
    return Response.json({ name: account.name });
  } catch (e) {
    // **서버가 적은 이유를 그대로 옮긴다.** "그 이름에 이 비밀번호가 아니에요" 가
    // "API가 401로 답했어요" 보다 화면에서 할 말이 많다.
    return Response.json({ detail: why(e) }, { status: code(e) });
  }
}

/** 나가기. **쿠키만 지운다** — 위키와 올린 파일은 그대로 남고, 같은 이름과
 *  비밀번호로 다시 들어오면 그대로 열린다. */
export async function DELETE() {
  (await cookies()).delete(COOKIE);
  return Response.json({ ok: true });
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown): string {
  return e instanceof Error ? e.message : "들어가다가 잘못됐어요";
}
