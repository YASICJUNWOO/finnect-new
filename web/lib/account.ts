import { get, send } from "./api";

/** 베타 입장 게이트([ADR-0066](../../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md)).
 *
 * **`SPEC.md` §6 이 계정을 범위 밖에 두고 있고 이것이 그 예외다.** 베타 테스터끼리
 * 데이터가 안 섞이게 하는 것이 유일한 목적이라 이메일·재설정·세션 만료·권한이 없다.
 *
 * **쿠키를 여기서 안 굽는다.** 이 파일은 FastAPI 와의 경계이고, 쿠키는 브라우저와의
 * 경계라 `app/api/account/route.ts` 가 든다 — `lib/` 가 `next/headers` 를 끌어오면
 * 서버 컴포넌트 밖에서 이 모듈을 못 쓴다. */

export type Account = {
  /** 발급된 격리 키. 이름과 관계없는 값이다(ADR-0066 결정 3) */
  company_id: string;
  /** 사용자가 적은 이름 그대로 */
  name: string;
};

/** 처음 보는 이름이면 만들고, 아는 이름이면 대조한다. **가입과 로그인을 안 나눈다.**
 *
 * 400(빈 값)·401(틀린 비번)이 `ApiError` 로 오고 **서버가 적은 문장을 그대로 든다**
 * (`send()` 가 `detail` 을 옮긴다) — 화면이 그 문장을 인라인으로 보여 준다. */
export function enterAccount(name: string, password: string): Promise<Account> {
  return send<Account>("/api/account", {
    method: "POST",
    body: JSON.stringify({ name, password }),
  });
}

/** 발급된 키로 **입장 때 적은 이름**을 되찾는다. **모르는 회사면 `null` 이다** —
 * `?company=` 로 손으로 적은 값(`c_dasiro`)에는 계정 행이 없다.
 *
 * 쓰는 자리는 S4 의 내려받기 하나다(`파일명_회사이름`). 화면에 이름을 적는 것이
 * 아니므로 **못 불러와도 조용히 지나간다** — 파일명에서 꼬리 하나가 빠질 뿐이다. */
export async function accountName(companyId: string): Promise<string | null> {
  try {
    const account = await get<Account>(`/api/account/${encodeURIComponent(companyId)}`);
    return account.name.trim() || null;
  } catch {
    return null;
  }
}

/** 쿠키 이름. **`web/middleware.ts` 와 `lib/wiki.ts` 가 같은 값을 읽는다** —
 *  세 곳에 문자열로 적으면 한 곳만 고쳐지는 날이 오고, 그날 게이트가 통과되는데
 *  화면은 회사를 못 찾는다. */
export const COOKIE = "fc";

/** 쿠키 수명 1년. **세션 쿠키로 두지 않는다** — 브라우저를 닫을 때마다 다시
 *  입장시키면 테스터가 비밀번호를 잊고 새 이름으로 들어가 위키가 둘이 된다. */
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
